"""Approving a thread from the admin publishes both halves (todo 422).

A new topic from an untrusted author is two drafts: the Topic and its opening
Post. The API path links them only post -> topic (the opening post going live
publishes its topic). A moderator who published only the topic in the admin
put an empty thread live: title, no body. These tests drive the real admin
publish and pin that either half now carries the other, under the same
author-match guard as before.
"""

from contextlib import contextmanager

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail_forum.models import ForumProfile, Post, Topic
from wagtail_forum.signals import topic_created
from wagtail_forum.tests.factories import make_forum
from wagtail_forum.workflow import (
    ensure_default_workflow,
    submit_edit_for_moderation,
    submit_for_moderation,
)

User = get_user_model()

SPAM = "http://a.com http://b.com http://c.com http://d.com http://e.com http://f.com"


def _board():
    return make_forum(name="General", slug="general")


def _pending_thread(author, board, *, post_author=None):
    """A draft topic whose opening post the spam check left pending, the
    state production reached for topic 44 / post 289."""
    ensure_default_workflow()
    ForumProfile.for_user(author)  # trust NEW: screened, not autopublished
    topic = Topic.objects.create(
        board=board, title="video post", slug="video-post", author=author, live=False
    )
    post = Post(
        topic=topic,
        author=post_author or author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{SPAM}</p>"}],
    )
    post.save()
    assert submit_for_moderation(post, post_author or author) == "pending"
    topic.refresh_from_db()
    assert topic.live is False
    return topic, post


def _admin_publish_topic(client, topic):
    url = reverse(Topic.snippet_viewset.get_url_name("edit"), args=(topic.pk,))
    resp = client.post(
        url,
        {
            "board": topic.board_id,
            "title": topic.title,
            "slug": topic.slug,
            "tags": "",
            "action-publish": "action-publish",
        },
    )
    assert resp.status_code == 302, resp.content[:2000]


@pytest.fixture
def moderator(client):
    admin = User.objects.create_superuser(username="mod", email="m@x.io")
    client.force_login(admin)
    return admin


@pytest.mark.django_db
def test_admin_publishing_a_topic_publishes_its_pending_opening_post(client, moderator):
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())

    _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True
    assert post.live is True
    # The spam workflow's NEEDS_CHANGES state is cancelled by the publish, so
    # the dashboard's awaiting-moderation count drops with it.
    assert post.current_workflow_state is None


@pytest.mark.django_db
def test_admin_publishing_a_topic_never_publishes_another_authors_opening_post(
    client, moderator
):
    owner = User.objects.create_user(username="owner")
    other = User.objects.create_user(username="other")
    topic, post = _pending_thread(owner, _board(), post_author=other)

    _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True
    assert post.live is False


@pytest.mark.django_db
def test_topic_created_receives_the_live_opening_post_on_admin_approval(
    client, moderator
):
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    seen = []

    def on_created(sender, post, topic, **kwargs):
        seen.append((post.pk if post else None, post.live if post else None))

    topic_created.connect(on_created)
    try:
        _admin_publish_topic(client, topic)
    finally:
        topic_created.disconnect(on_created)

    assert seen == [(post.pk, True)]


@pytest.mark.django_db
def test_publishing_a_pending_opening_post_publishes_its_draft_topic(moderator):
    # The dashboard link now lands on the Posts list, so approving from there
    # must not leave the mirror-image bug: a live body under a draft topic.
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())

    post.save_revision(user=moderator).publish(user=moderator)

    topic.refresh_from_db()
    assert topic.live is True


@pytest.mark.django_db
def test_republishing_an_opening_post_never_revives_a_taken_down_topic(moderator):
    # First publish only: a moderator who unpublished the topic keeps it down
    # when the author's later edit to the opening post is published.
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    post.save_revision(user=moderator).publish(user=moderator)
    topic.refresh_from_db()
    topic.unpublish(user=moderator)

    post.refresh_from_db()
    post.save_revision(user=moderator).publish(user=moderator)

    topic.refresh_from_db()
    assert topic.live is False


@pytest.mark.django_db
def test_dashboard_moderation_link_lands_on_the_pending_content_page(client, moderator):
    # Todo 423 moved the link from the Posts list to the pending-content
    # page, where one Approve publishes the whole thread.
    author = User.objects.create_user(username="plantadmin")
    _pending_thread(author, _board())

    # Resolved, never a hardcoded admin path: the mount is host config (todo 495).
    resp = client.get(reverse("wagtailadmin_home"))

    expected = reverse("wagtail_forum_pending:index")
    assert f'href="{expected}"'.encode() in resp.content


# --- Review round 1 (PR #815) ---


@pytest.mark.django_db
def test_admin_publishing_a_topic_never_revives_a_taken_down_opening_post(
    client, moderator
):
    # Finding 3: the gate is "never published", not "not live".
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    Topic.objects.filter(pk=topic.pk).update(author=None)  # decouple the halves
    post.save_revision(user=moderator).publish(user=moderator)
    post.refresh_from_db()
    post.unpublish(user=moderator)  # a moderator takes the body down
    Topic.objects.filter(pk=topic.pk).update(author=author)
    topic.refresh_from_db()

    _admin_publish_topic(client, topic)

    post.refresh_from_db()
    assert post.live is False


@pytest.mark.django_db
def test_republishing_the_opening_post_repairs_a_never_published_topic(moderator):
    # Finding 2: a live body under a never-published topic (the pre-fix admin
    # path, or a failed link) is repaired by publishing the post again.
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    Post.objects.filter(pk=post.pk).update(
        live=True, first_published_at=post.created_at, last_published_at=post.created_at
    )
    post.refresh_from_db()

    post.save_revision(user=moderator).publish(user=moderator)

    topic.refresh_from_db()
    assert topic.live is True


@pytest.mark.django_db
def test_a_failed_topic_link_never_aborts_the_opening_posts_publish(moderator):
    # Finding 1: the link runs inside the post's `published` receiver; if it
    # raises, the post's own publish must still finish (its activity row
    # comes after the signal).
    from unittest import mock

    from wagtail_forum.models import ForumActivityDate

    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())

    with mock.patch.object(Topic, "save_revision", side_effect=RuntimeError("boom")):
        post.save_revision(user=moderator).publish(user=moderator)

    post.refresh_from_db()
    topic.refresh_from_db()
    assert post.live is True
    assert topic.live is False
    assert ForumActivityDate.objects.filter(user=author).count() == 1


@pytest.mark.django_db
def test_admin_approval_is_attributed_to_the_moderator_not_the_author(moderator):
    # Finding 5: the workflow Approve action republishes the AUTHOR's
    # revision; the topic's publish must still be logged as the moderator's.
    from wagtail.log_actions import LogContext
    from wagtail.models import ModelLogEntry

    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    authors_revision = post.get_latest_revision()
    assert authors_revision.user_id == author.pk

    with LogContext(user=moderator):
        authors_revision.publish(user=moderator)

    entry = ModelLogEntry.objects.get(
        content_type__model="topic", object_id=str(topic.pk), action="wagtail.publish"
    )
    assert entry.user_id == moderator.pk


@pytest.mark.django_db
def test_two_deleted_authors_are_not_the_same_author(client, moderator):
    # Finding 6: SET_NULL makes both author_ids None; None == None must not
    # pass the IDOR guard.
    owner = User.objects.create_user(username="owner")
    other = User.objects.create_user(username="other")
    topic, post = _pending_thread(owner, _board(), post_author=other)
    Topic.objects.filter(pk=topic.pk).update(author=None)
    Post.objects.filter(pk=post.pk).update(author=None)
    topic.refresh_from_db()

    topic.save_revision(user=moderator).publish(user=moderator)

    post.refresh_from_db()
    assert post.live is False


# --- Todo 432: the approval publishes the author's pending edit ---


@pytest.mark.django_db
def test_admin_publishing_a_topic_publishes_its_opening_posts_pending_edit(
    client, moderator
):
    # An edit to a never-published post is a revision only:
    # submit_edit_for_moderation never writes the row of a post that is not
    # live. Approving the topic must publish that edit, not a fresh revision
    # built from the row, which still holds the ORIGINAL body.
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    post.body = [{"type": "paragraph", "value": "<p>The edited body</p>"}]
    assert submit_edit_for_moderation(post, author) == "pending"
    row = Post.objects.get(pk=post.pk)
    assert SPAM in row.body.raw_data[0]["value"]  # the premise: row untouched
    assert "edited body" not in row.body.raw_data[0]["value"]

    _admin_publish_topic(client, topic)

    post.refresh_from_db()
    assert post.live is True
    assert post.body.raw_data[0]["value"] == "<p>The edited body</p>"
    assert post.current_workflow_state is None


@pytest.mark.django_db
def test_admin_publishing_a_topic_publishes_an_opening_post_row_newer_than_its_revision(
    client, moderator
):
    # The other branch: a row written after its latest revision (a direct
    # save, no revision) is the newer content, so it is what goes live.
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    post.body = [{"type": "paragraph", "value": "<p>Saved to the row</p>"}]
    post.save()

    _admin_publish_topic(client, topic)

    post.refresh_from_db()
    assert post.live is True
    assert post.body.raw_data[0]["value"] == "<p>Saved to the row</p>"


# --- Todo 431: an approved thread recounts the board and profiles once ---


@pytest.fixture
def recount_spies():
    """Spies on the recount helpers. The receiver resolves them as module
    globals at call time, so patching the module attribute sees every call,
    nested publishes included."""
    from unittest import mock

    from wagtail_forum import signals

    names = ("_refresh_board_counters", "_refresh_profile", "_refresh_topic_counters")
    patchers = [
        mock.patch.object(signals, name, wraps=getattr(signals, name)) for name in names
    ]
    spies = dict(zip(names, (p.start() for p in patchers)))
    yield spies
    for p in patchers:
        p.stop()


def _reset(spies):
    for spy in spies.values():
        spy.reset_mock()


@contextmanager
def _post_publishes_fail():
    """Every Post revision publish raises; Topic publishes still run. The
    failure is injected at Revision.publish, not Post.save_revision: the link
    publishes the author's pending revision (todo 432), so it never calls
    save_revision and patching that would not fail it."""
    from unittest import mock

    from wagtail.models import Revision

    real_publish = Revision.publish

    def publish_failing_for_posts(self, *args, **kwargs):
        if self.content_type.model_class() is Post:
            raise RuntimeError("boom")
        return real_publish(self, *args, **kwargs)

    with mock.patch.object(Revision, "publish", publish_failing_for_posts):
        yield


def _live_reply(topic, author, text="A reply"):
    """A reply already live in ``topic``, written straight to the row so no
    publish signal runs while the test sets up."""
    reply = Post.objects.create(
        topic=topic,
        author=author,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )
    Post.objects.filter(pk=reply.pk).update(
        live=True,
        first_published_at=reply.created_at,
        last_published_at=reply.created_at,
    )
    reply.refresh_from_db()
    return reply


def _assert_thread_counted_once(spies, author, board, topic, post):
    assert spies["_refresh_board_counters"].call_count == 1
    assert [c.args for c in spies["_refresh_profile"].call_args_list] == [(author.pk,)]
    assert [c.args for c in spies["_refresh_topic_counters"].call_args_list] == [
        (topic.pk,)
    ]
    # The single recounts still land on the final, all-live state.
    board.refresh_from_db()
    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True and post.live is True
    assert (board.topic_count, board.post_count) == (1, 1)
    assert ForumProfile.objects.get(user=author).post_count == 1
    # Todo 422's ordering rule: the topic's counters are fresh.
    assert topic.last_post_at == post.first_published_at
    assert topic.last_post_author_id == author.pk


@pytest.mark.django_db
def test_approving_a_thread_from_its_topic_recounts_each_once(
    client, moderator, recount_spies
):
    author = User.objects.create_user(username="plantadmin")
    board = _board()
    topic, post = _pending_thread(author, board)
    _reset(recount_spies)  # only the approval's recounts are under test

    _admin_publish_topic(client, topic)

    _assert_thread_counted_once(recount_spies, author, board, topic, post)


@pytest.mark.django_db
def test_approving_a_thread_from_its_opening_post_recounts_each_once(
    moderator, recount_spies
):
    author = User.objects.create_user(username="plantadmin")
    board = _board()
    topic, post = _pending_thread(author, board)
    _reset(recount_spies)

    post.save_revision(user=moderator).publish(user=moderator)

    _assert_thread_counted_once(recount_spies, author, board, topic, post)


@pytest.mark.django_db
def test_a_failed_topic_link_still_recounts_the_board_and_author(
    moderator, recount_spies
):
    # The post branch skips its own board and profile recount because the
    # nested topic publish redoes it; when that publish fails, the recount is
    # still owed.
    from unittest import mock

    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    _reset(recount_spies)

    with mock.patch.object(Topic, "save_revision", side_effect=RuntimeError("boom")):
        post.save_revision(user=moderator).publish(user=moderator)

    # The link really failed (todo 504, finding 7): the success path also
    # recounts once, so without this the fallback could go unexercised.
    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is False
    assert post.live is True
    assert recount_spies["_refresh_board_counters"].call_count == 1
    assert [c.args for c in recount_spies["_refresh_profile"].call_args_list] == [
        (author.pk,)
    ]


# --- Todo 504: PR #906 review follow-ups ---


@pytest.mark.django_db
def test_approving_a_thread_recounts_a_second_author_in_the_topic(
    client, moderator, recount_spies
):
    # Findings 2/3: the linked publish excludes only the opening post's
    # author from the topic-wide recount. Anyone else with a live post in the
    # topic still owes a recount now that the topic is visible.
    author = User.objects.create_user(username="plantadmin")
    other = User.objects.create_user(username="replier")
    board = _board()
    topic, post = _pending_thread(author, board)
    _live_reply(topic, other)
    ForumProfile.for_user(other)
    _reset(recount_spies)

    _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True and post.live is True  # the link succeeded
    assert [c.args for c in recount_spies["_refresh_profile"].call_args_list] == [
        (author.pk,),
        (other.pk,),
    ]
    assert recount_spies["_refresh_board_counters"].call_count == 1
    assert ForumProfile.objects.get(user=author).post_count == 1
    assert ForumProfile.objects.get(user=other).post_count == 1


@pytest.mark.django_db
def test_a_failed_opening_post_link_still_recounts_the_board(
    client, moderator, recount_spies
):
    # Findings 4/5/6/8: the topic branch skips its board recount only when
    # the opening post's nested publish ran. When that publish fails,
    # linked_author_id stays None and the topic must recount the board.
    author = User.objects.create_user(username="plantadmin")
    board = _board()
    topic, post = _pending_thread(author, board)
    _reset(recount_spies)

    with _post_publishes_fail():
        _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True
    assert post.live is False  # the link really failed
    assert recount_spies["_refresh_board_counters"].call_count == 1
    # The author has no live post in the topic, so no profile is owed a
    # recount: _refresh_topic_authors only walks live posts.
    assert recount_spies["_refresh_profile"].call_args_list == []
    board.refresh_from_db()
    assert (board.topic_count, board.post_count) == (1, 0)


@pytest.mark.django_db
def test_approving_a_thread_whose_opening_post_is_scheduled_counts_the_topic(
    client, moderator, recount_spies
):
    # Finding 1: an opening post scheduled for later is not live after the
    # linked publish. The board must still count the now-live topic. Wagtail
    # 8 still sends `published` for a scheduled first publish, so the nested
    # post receiver is what recounts the board and author, once each.
    # Pinned Wagtail 8.0 behaviour, `PublishRevisionAction._publish_revision`
    # (wagtail/actions/publish_revision.py): a future `go_live_at` returns
    # before `_after_publish()`, the `published` send, only when
    # `object.live_revision_id` is set; a never-published object is saved
    # live=False and still gets the signal. A bump that moves `_after_publish()`
    # under `if object.live:` or widens that early return turns this test red.
    # The board assertions below (one recount, `(1, 0)`) are the invariant
    # such a bump must keep: the topic branch's `linked_author_id` gate in
    # signals.py changes then. The `_refresh_profile` pin does not survive it:
    # `[(author.pk,)]` is the nested Post receiver's 0 -> 0 recount, and with
    # that signal gone the author has no live post, so the list becomes `[]`
    # (todo 517 findings 2/3, todo 557).
    from datetime import timedelta

    from django.utils import timezone

    author = User.objects.create_user(username="plantadmin")
    board = _board()
    topic, post = _pending_thread(author, board)
    post.go_live_at = timezone.now() + timedelta(days=1)
    post.save()  # the row is now newer than its revision, so the link publishes it
    _reset(recount_spies)

    _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True
    assert post.live is False
    assert post.revisions.filter(approved_go_live_at__isnull=False).count() == 1
    assert recount_spies["_refresh_board_counters"].call_count == 1
    assert [c.args for c in recount_spies["_refresh_profile"].call_args_list] == [
        (author.pk,)
    ]
    board.refresh_from_db()
    assert (board.topic_count, board.post_count) == (1, 0)


# --- Todo 517: PR #929 review follow-ups ---


@pytest.mark.django_db
def test_a_failed_opening_post_link_still_recounts_the_authors_live_reply(
    client, moderator, recount_spies
):
    # Finding 1: in the failed-link test above the opening author has no live
    # post, so `_refresh_topic_authors` walks nobody and excluding the author
    # on a failed link too would pass it. The exclusion is owed only when the
    # linked publish recounted the author with the topic live. Here the author
    # also has a live reply in the never-published topic, the link fails, and
    # the topic's own recount must still reach that author.
    author = User.objects.create_user(username="plantadmin")
    board = _board()
    topic, post = _pending_thread(author, board)
    reply = _live_reply(topic, author)
    _reset(recount_spies)

    with _post_publishes_fail():
        _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    post.refresh_from_db()
    reply.refresh_from_db()
    assert topic.live is True
    assert post.live is False  # the link really failed
    assert reply.live is True
    assert recount_spies["_refresh_board_counters"].call_count == 1
    # Nothing recounted the author with the topic live, so the topic branch
    # owes it: the live reply funds post_count now that the topic is visible.
    assert [c.args for c in recount_spies["_refresh_profile"].call_args_list] == [
        (author.pk,)
    ]
    assert ForumProfile.objects.get(user=author).post_count == 1
    board.refresh_from_db()
    assert (board.topic_count, board.post_count) == (1, 1)


# --- Todo 557: PR #947 review follow-ups ---


@pytest.mark.django_db
def test_approving_a_thread_recounts_an_author_with_two_live_replies_once(
    client, moderator, recount_spies
):
    # Finding 1: Post.Meta.ordering put created_at into the SELECT DISTINCT,
    # so `_refresh_topic_authors` walked one row per live post, and an author
    # with N live replies got N locked recounts instead of one.
    author = User.objects.create_user(username="plantadmin")
    other = User.objects.create_user(username="replier")
    board = _board()
    topic, post = _pending_thread(author, board)
    _live_reply(topic, other, "first")
    _live_reply(topic, other, "second")
    ForumProfile.for_user(other)
    _reset(recount_spies)

    _admin_publish_topic(client, topic)

    topic.refresh_from_db()
    assert topic.live is True
    assert [c.args for c in recount_spies["_refresh_profile"].call_args_list] == [
        (author.pk,),
        (other.pk,),
    ]
    assert ForumProfile.objects.get(user=other).post_count == 2


# --- Todo 579: an edit to a never-published opening post is screened, never
# published (owner decision 2026-10-10, mechanism and paths 2026-10-11) ---


def _edit(post, author, text):
    post.body = [{"type": "paragraph", "value": f"<p>{text}</p>"}]
    return submit_edit_for_moderation(post, author)


def _latest_task_state(post):
    from wagtail.models import TaskState

    return TaskState.objects.filter(revision_id=post.latest_revision_id).get()


def _trusted(user):
    profile = ForumProfile.for_user(user)
    profile.trust_level = 3
    profile.save()


@pytest.mark.django_db
def test_a_spammy_edit_to_a_pending_opening_post_is_screened_and_held():
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    held_before = post.latest_revision_id

    assert _edit(post, author, f"still spam {SPAM}") == "pending"

    post.refresh_from_db()
    assert post.latest_revision_id != held_before
    task = _latest_task_state(post)  # the screen ran on the edited body
    assert task.status == task.STATUS_REJECTED
    state = post.current_workflow_state
    assert state.status == state.STATUS_NEEDS_CHANGES
    assert state.current_task_state_id == task.pk
    topic.refresh_from_db()
    assert (post.live, topic.live) == (False, False)


@pytest.mark.parametrize("trusted", [False, True], ids=["untrusted", "trusted"])
@pytest.mark.django_db
def test_a_clean_edit_to_a_pending_opening_post_never_publishes_the_thread(
    client, moderator, trusted
):
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    if trusted:
        _trusted(author)  # trust gained after the hold: still only screened

    assert _edit(post, author, "The fixed body") == "pending"

    post.refresh_from_db()
    topic.refresh_from_db()
    task = _latest_task_state(post)
    assert task.status == task.STATUS_APPROVED  # screened clean
    assert post.current_workflow_state is None  # the workflow finished
    assert (post.live, post.first_published_at) == (False, None)
    assert (topic.live, topic.first_published_at) == (False, None)

    _admin_publish_topic(client, topic)  # the moderator's approval is the gate

    post.refresh_from_db()
    topic.refresh_from_db()
    assert (post.live, topic.live) == (True, True)
    assert post.body.raw_data[0]["value"] == "<p>The fixed body</p>"


@pytest.mark.django_db
def test_resubmitting_a_held_opening_post_screens_it_without_publishing():
    # The admin's Resubmit resumes the held workflow: a re-screen, so a clean
    # verdict publishes nothing (SpamCheckTask, not the edit path, decides).
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    post.body = [{"type": "paragraph", "value": "<p>clean now</p>"}]
    post.save_revision(user=author)

    post.current_workflow_state.resume(user=None)

    post.refresh_from_db()
    topic.refresh_from_db()
    assert _latest_task_state(post).status == "approved"
    assert (post.live, topic.live) == (False, False)


@pytest.mark.django_db
def test_the_first_screen_of_a_new_opening_post_still_publishes_clean_content():
    # The create path is not a re-screen: an untrusted member's clean topic
    # still goes live on its spam check alone.
    ensure_default_workflow()
    author = User.objects.create_user(username="newbie")
    ForumProfile.for_user(author)
    topic = Topic.objects.create(
        board=_board(), title="Hi", slug="hi", author=author, live=False
    )
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>hello</p>"}],
    )
    post.save()

    assert submit_for_moderation(post, author) == "published"

    topic.refresh_from_db()
    assert topic.live is True


@pytest.mark.django_db
def test_an_edit_to_a_taken_down_opening_post_is_never_republished():
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    _trusted(author)  # a trusted author's edit would publish a live post
    moderator = User.objects.create_superuser(username="mod2", email="m2@x.io")
    post.save_revision(user=moderator).publish(user=moderator)
    post.refresh_from_db()
    post.unpublish(user=moderator)
    post.refresh_from_db()
    states_before = post.workflow_states.count()

    assert _edit(post, author, "bring it back") == "pending"

    post.refresh_from_db()
    assert post.live is False
    assert post.workflow_states.count() == states_before  # no screen, no publish


@pytest.mark.urls("wagtail_forum.tests.api.urls")
@pytest.mark.django_db
def test_the_author_can_patch_their_pending_opening_post_and_it_stays_pending():
    from django.core.cache import cache
    from rest_framework.test import APIClient

    cache.clear()
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    payload = {"body": [{"type": "paragraph", "value": "<p>Fixed by the author</p>"}]}

    stranger = APIClient()
    stranger.force_authenticate(User.objects.create_user(username="stranger"))
    assert (
        stranger.patch(f"/forum/posts/{post.pk}/", payload, format="json").status_code
        == 404
    )

    api = APIClient()
    api.force_authenticate(author)
    resp = api.patch(f"/forum/posts/{post.pk}/", payload, format="json")

    assert resp.status_code == 200, resp.content
    assert resp.data["moderation_status"] == "pending"
    post.refresh_from_db()
    topic.refresh_from_db()
    assert (post.live, topic.live) == (False, False)
    assert _latest_task_state(post).status == "approved"
    # DELETE does not reach it: only the edit path was opened.
    assert api.delete(f"/forum/posts/{post.pk}/").status_code == 404


@pytest.mark.urls("wagtail_forum.tests.api.urls")
@pytest.mark.django_db
def test_the_author_cannot_patch_an_opening_post_under_a_taken_down_topic():
    from django.core.cache import cache
    from rest_framework.test import APIClient

    cache.clear()
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    Topic.objects.filter(pk=topic.pk).update(first_published_at=topic.created_at)
    api = APIClient()
    api.force_authenticate(author)

    resp = api.patch(
        f"/forum/posts/{post.pk}/",
        {"body": [{"type": "paragraph", "value": "<p>x</p>"}]},
        format="json",
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_a_moderators_admin_draft_of_a_pending_opening_post_is_screened(moderator):
    # The snippet editor's "Save draft" runs EditAction and then the
    # after_edit_snippet hooks; drive both as the edit view does (its
    # StreamField form is JS-rendered, so it is not posted here).
    from django.test import RequestFactory
    from wagtail import hooks
    from wagtail.actions.edit import EditAction
    from wagtail_forum.wagtail_hooks import screen_admin_edit_of_a_pending_opening_post

    assert screen_admin_edit_of_a_pending_opening_post in hooks.get_hooks(
        "after_edit_snippet"
    )
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    draft = post.get_latest_revision_as_object()
    draft.body = [{"type": "paragraph", "value": "<p>Moderator fix</p>"}]
    EditAction(draft, user=moderator).execute(skip_permission_checks=True)
    request = RequestFactory().post("/cms/", {"title": "x"})
    request.user = moderator

    for hook in hooks.get_hooks("after_edit_snippet"):
        hook(request, draft)

    post.refresh_from_db()
    topic.refresh_from_db()
    task = _latest_task_state(post)
    assert task.status == task.STATUS_APPROVED
    assert (post.live, topic.live) == (False, False)

    # Publish is the moderator approving: the hook leaves it alone.
    publish = RequestFactory().post("/cms/", {"action-publish": "action-publish"})
    publish.user = moderator
    before = post.workflow_states.count()
    screen_admin_edit_of_a_pending_opening_post(publish, post)
    assert post.workflow_states.count() == before


@pytest.mark.django_db
def test_an_autosave_of_a_pending_opening_post_is_not_screened(moderator):
    # PR #1035 review: Wagtail 8 autosaves the snippet editor as a JSON save
    # with no action-* key. Screening each one would restart the workflow and
    # call the paid spam backend every few seconds on half-typed text.
    from django.test import RequestFactory
    from wagtail_forum.wagtail_hooks import screen_admin_edit_of_a_pending_opening_post

    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    before = post.workflow_states.count()
    autosave = RequestFactory().post(
        "/cms/", {"title": "x"}, HTTP_ACCEPT="application/json"
    )
    autosave.user = moderator

    screen_admin_edit_of_a_pending_opening_post(autosave, post)

    assert post.workflow_states.count() == before


@pytest.mark.django_db
def test_a_topic_publish_never_puts_a_held_edit_of_its_opening_post_live(
    client, moderator
):
    # PR #1035 review: the author can PATCH a pending opening post (todo 579).
    # A Topic Publish from the snippet editor used to publish the post's
    # newest revision, so an edit the spam screen held went live unseen. The
    # body the moderator approved, the row, goes live instead (todo 422).
    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    assert _edit(post, author, f"sneaked in {SPAM}") == "pending"
    post.refresh_from_db()
    assert post.current_workflow_state.status == "needs_changes"

    _admin_publish_topic(client, topic)

    post.refresh_from_db()
    topic.refresh_from_db()
    assert (post.live, topic.live) == (True, True)
    assert post.body.raw_data[0]["value"] == f"<p>{SPAM}</p>"


# --- Todo 561 finding 2: a Topic revision never reverts row-only state ---


@pytest.mark.django_db
def test_publishing_an_older_topic_revision_keeps_the_live_counters_and_answer(
    moderator,
):
    from django.utils import timezone

    author = User.objects.create_user(username="plantadmin")
    topic, post = _pending_thread(author, _board())
    topic.save_revision(user=moderator).publish(
        user=moderator, skip_permission_checks=True
    )
    topic.refresh_from_db()
    post.refresh_from_db()
    stale = topic.save_revision(user=moderator)  # snapshots the counters now
    answered_at = timezone.now()
    Topic.objects.filter(pk=topic.pk).update(
        view_count=42, solved_post=post, solved_at=answered_at
    )
    topic.refresh_from_db()
    counters = (topic.reply_count, topic.last_post_at, topic.last_post_author_id)

    stale.publish(user=moderator, skip_permission_checks=True)

    topic.refresh_from_db()
    assert topic.view_count == 42
    assert (topic.solved_post_id, topic.solved_at) == (post.pk, answered_at)
    assert (
        topic.reply_count,
        topic.last_post_at,
        topic.last_post_author_id,
    ) == counters


@pytest.mark.django_db
def test_a_topic_revision_keeps_the_row_counters_when_read_back(moderator):
    author = User.objects.create_user(username="plantadmin")
    topic, _post = _pending_thread(author, _board())
    revision = topic.save_revision(user=moderator)
    Topic.objects.filter(pk=topic.pk).update(view_count=7, reply_count=3)
    topic.refresh_from_db()

    obj = topic.with_content_json(revision.content)

    assert (obj.view_count, obj.reply_count) == (7, 3)


# --- Todo 574: the rules the "Pending opening posts" doc states, pinned ---


@pytest.mark.django_db
def test_an_edit_to_a_pending_opening_post_never_moves_its_row():
    # The topic-publish link publishes whichever is newer, the latest
    # revision or the row (updated_at). The edit path must leave the row
    # alone, or a later approval would publish the row and drop the edit.
    author = User.objects.create_user(username="plantadmin")
    _topic, post = _pending_thread(author, _board())
    before = Post.objects.get(pk=post.pk)

    _edit(post, author, "The fixed body")

    after = Post.objects.get(pk=post.pk)
    assert after.updated_at == before.updated_at
    assert list(after.body.raw_data) == list(before.body.raw_data)
    assert after.latest_revision.created_at > after.updated_at


@pytest.mark.django_db
def test_queue_approve_publishes_the_revision_even_when_the_row_is_newer(client):
    # Unlike the topic-publish link, the pending page's Approve ignores the
    # row: it publishes the revision the row stands for (todos 432 and 561).
    from wagtail_forum.admin_views import approve_pending_post, pending_posts

    author = User.objects.create_user(username="plantadmin")
    _topic, post = _pending_thread(author, _board())
    _edit(post, author, "The screened edit")
    Post.objects.filter(pk=post.pk).update(
        body=[{"type": "paragraph", "value": "<p>Written to the row</p>"}]
    )
    moderator = User.objects.create_superuser(username="mod3", email="m3@x.io")
    pending = pending_posts().get(pk=post.pk)

    approve_pending_post(pending, moderator)

    post.refresh_from_db()
    assert post.live is True
    assert post.body.raw_data[0]["value"] == "<p>The screened edit</p>"
