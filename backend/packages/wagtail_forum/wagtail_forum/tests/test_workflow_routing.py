import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from wagtail_forum.models import ForumProfile, Post, Topic, TrustLevel
from wagtail_forum.spam.base import SpamBackend
from wagtail_forum.tests.factories import make_forum
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()


class DatabaseErrorSpamBackend(SpamBackend):
    """A backend whose failure is a DB error: Postgres aborts the transaction
    it ran in, so any later write in it raises (todo 588)."""

    def check(self, obj):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1/0")


def _post(author, text="hello world"):
    board = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )


@pytest.mark.django_db
def test_trusted_user_publishes_instantly():
    user = User.objects.create_user(username="reg")
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    ensure_default_workflow()

    post = _post(user)
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert status == "published"
    assert post.live is True


@pytest.mark.django_db
def test_new_user_clean_post_publishes_after_spam_check():
    user = User.objects.create_user(username="new")
    ForumProfile.for_user(user)  # trust NEW
    ensure_default_workflow()

    post = _post(user, "a friendly normal hello")
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert post.live is True
    assert status == "published"


@pytest.mark.django_db
def test_new_user_spam_stays_pending():
    user = User.objects.create_user(username="spammer")
    ForumProfile.for_user(user)
    ensure_default_workflow()

    spam = (
        "http://a.com http://b.com http://c.com http://d.com http://e.com http://f.com"
    )
    post = _post(user, spam)
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert post.live is False
    assert status == "pending"


@pytest.mark.django_db
def test_untrusted_no_workflow_fails_closed():
    # SECURITY: with no moderation workflow configured, an untrusted user's
    # content must NOT publish unscreened — it stays a draft (fail closed).
    user = User.objects.create_user(username="nowf")
    ForumProfile.for_user(user)  # trust NEW
    # Deliberately do NOT call ensure_default_workflow(). A host (apps.forum_host)
    # may bootstrap one into the shared test DB on post_migrate, so clear any
    # workflow state to genuinely test the no-workflow fail-closed path.
    from wagtail.models import Workflow, WorkflowContentType

    WorkflowContentType.objects.all().delete()
    Workflow.objects.all().delete()

    post = _post(user, "a friendly normal hello")
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert post.live is False
    assert status == "pending"


@pytest.mark.django_db
def test_untrusted_author_via_trusted_caller_is_screened():
    # SECURITY: trust is derived from the content's author, not the caller. An
    # untrusted author's spam must still be screened even when a trusted caller
    # submits it — no riding a privileged caller's trust level.
    author = User.objects.create_user(username="newauthor")
    ForumProfile.for_user(author)  # trust NEW
    caller = User.objects.create_user(username="leadercaller")
    caller_profile = ForumProfile.for_user(caller)
    caller_profile.trust_level = TrustLevel.LEADER
    caller_profile.save()
    ensure_default_workflow()

    spam = (
        "http://a.com http://b.com http://c.com http://d.com http://e.com http://f.com"
    )
    post = _post(author, spam)
    post.save()
    status = submit_for_moderation(post, caller)

    post.refresh_from_db()
    assert post.live is False
    assert status == "pending"


@pytest.mark.django_db
def test_moderation_decided_signal_fires_with_outcome():
    from wagtail_forum.signals import moderation_decided

    received = {}

    def handler(sender, obj, status, **kwargs):
        received["status"] = status
        received["obj_pk"] = obj.pk

    moderation_decided.connect(handler)
    try:
        user = User.objects.create_user(username="sig")
        profile = ForumProfile.for_user(user)
        profile.trust_level = TrustLevel.MEMBER
        profile.save()
        ensure_default_workflow()

        post = _post(user)
        post.save()
        status = submit_for_moderation(post, user)
    finally:
        moderation_decided.disconnect(handler)

    assert status == "published"
    assert received == {"status": "published", "obj_pk": post.pk}


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_SPAM_BACKEND="wagtail_forum.tests.api.test_topic_create.RaisingSpamBackend"
)
def test_moderation_decided_signal_still_fires_when_spam_backend_crashes():
    # The view layer already catches this to avoid a 500 (api/views.py); this
    # pins the separate, easy-to-miss gap: without a wrap INSIDE
    # submit_for_moderation, a spam-backend exception exits the function
    # before it ever reaches notify(moderation_decided, ...), so hosts
    # silently never hear about a crashed-but-pending post (audit H16).
    from wagtail_forum.signals import moderation_decided

    received = {}

    def handler(sender, obj, status, **kwargs):
        received["status"] = status
        received["obj_pk"] = obj.pk

    moderation_decided.connect(handler)
    try:
        user = User.objects.create_user(username="crash")  # NEW trust — untrusted
        ensure_default_workflow()

        post = _post(user)
        post.save()
        status = submit_for_moderation(post, user)
    finally:
        moderation_decided.disconnect(handler)

    assert status == "pending"
    assert post.live is False
    assert received == {"status": "pending", "obj_pk": post.pk}

    # Since todo 561 a crashed spam backend no longer rolls the workflow
    # back: SpamCheckTask rejects with the error as its comment, so the post
    # is held in NEEDS_CHANGES with a task state the pending page's Approve
    # publishes. Todo 254 pinned that the count missed a crashed post; it is
    # counted, as the pending-content page's row.
    from wagtail_forum.wagtail_hooks import _pending_moderation_count

    state = post.current_workflow_state
    assert state.status == state.STATUS_NEEDS_CHANGES
    assert "spam check could not run" in state.current_task_state.comment
    assert _pending_moderation_count() == 1


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_SPAM_BACKEND=(
        "wagtail_forum.tests.test_workflow_routing.DatabaseErrorSpamBackend"
    )
)
def test_spam_backend_db_error_still_fails_closed_with_a_record():
    """Todo 588: a backend that fails with a DB error runs inside Wagtail's
    atomic workflow start. Without a savepoint around the backend call the
    error poisons that transaction, and SpamCheckTask's reject() (a DB write)
    raises TransactionManagementError: the fail-closed record is lost and the
    backend's own error is masked. With it, the post is held in NEEDS_CHANGES
    with the error named, exactly as a non-DB backend crash is."""
    user = User.objects.create_user(username="dbcrash")  # NEW trust: untrusted
    ensure_default_workflow()

    post = _post(user)
    post.save()
    status = submit_for_moderation(post, user)

    assert status == "pending"
    post.refresh_from_db()
    assert post.live is False
    state = post.current_workflow_state
    assert state is not None
    assert state.status == state.STATUS_NEEDS_CHANGES
    comment = state.current_task_state.comment
    assert "spam check could not run" in comment
    assert "DataError" in comment  # the backend's own error, not masked


@pytest.mark.django_db
def test_opening_post_by_another_author_cannot_publish_someone_elses_topic():
    """The IDOR author-guard in submit_for_moderation (audit M18): a trusted
    user's opening post must never force ANOTHER author's draft topic live."""
    ensure_default_workflow()
    owner = User.objects.create_user(username="owner")
    attacker = User.objects.create_user(username="attacker")
    p = ForumProfile.for_user(attacker)
    p.trust_level = TrustLevel.MEMBER  # autopublishes their own content
    p.save()

    board = make_forum(name="General2", slug="general2")
    draft_topic = Topic.objects.create(
        board=board, title="T", slug="t", author=owner, live=False
    )
    post = Post.objects.create(
        topic=draft_topic, author=attacker, is_opening_post=True, live=False
    )

    submit_for_moderation(post, attacker)

    draft_topic.refresh_from_db()
    post.refresh_from_db()
    assert post.live is True  # the attacker's own content may publish
    assert draft_topic.live is False  # but never the owner's draft topic
