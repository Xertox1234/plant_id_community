import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()


def _post(author, text="hello world"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )


@pytest.mark.django_db
def test_trusted_user_publishes_instantly():
    user = User.objects.create_user(username="reg", password="x")
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
    user = User.objects.create_user(username="new", password="x")
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
    user = User.objects.create_user(username="spammer", password="x")
    ForumProfile.for_user(user)
    ensure_default_workflow()

    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
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
    user = User.objects.create_user(username="nowf", password="x")
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
    author = User.objects.create_user(username="newauthor", password="x")
    ForumProfile.for_user(author)  # trust NEW
    caller = User.objects.create_user(username="leadercaller", password="x")
    caller_profile = ForumProfile.for_user(caller)
    caller_profile.trust_level = TrustLevel.LEADER
    caller_profile.save()
    ensure_default_workflow()

    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
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
        user = User.objects.create_user(username="sig", password="x")
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
