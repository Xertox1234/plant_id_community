"""Approving a thread from the admin publishes both halves (todo 422).

A new topic from an untrusted author is two drafts: the Topic and its opening
Post. The API path links them only post -> topic (the opening post going live
publishes its topic). A moderator who published only the topic in the admin
put an empty thread live: title, no body. These tests drive the real admin
publish and pin that either half now carries the other, under the same
author-match guard as before.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic
from wagtail_forum.signals import topic_created
from wagtail_forum.workflow import (
    ensure_default_workflow,
    submit_edit_for_moderation,
    submit_for_moderation,
)

User = get_user_model()

SPAM = "http://a.com http://b.com http://c.com http://d.com http://e.com"


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


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
    reply = Post.objects.create(
        topic=topic,
        author=other,
        body=[{"type": "paragraph", "value": "<p>A reply</p>"}],
    )
    Post.objects.filter(pk=reply.pk).update(
        live=True,
        first_published_at=reply.created_at,
        last_published_at=reply.created_at,
    )
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
    # The failure is injected at Revision.publish, not Post.save_revision:
    # the link publishes the author's pending revision here (todo 432), so
    # it never calls save_revision and patching that would not fail it.
    from unittest import mock

    from wagtail.models import Revision

    real_publish = Revision.publish

    def publish_failing_for_posts(self, *args, **kwargs):
        if self.content_type.model_class() is Post:
            raise RuntimeError("boom")
        return real_publish(self, *args, **kwargs)

    author = User.objects.create_user(username="plantadmin")
    board = _board()
    topic, post = _pending_thread(author, board)
    _reset(recount_spies)

    with mock.patch.object(Revision, "publish", publish_failing_for_posts):
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
