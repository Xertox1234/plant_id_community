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
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

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
def test_dashboard_moderation_link_lands_on_the_posts_list(client, moderator):
    author = User.objects.create_user(username="plantadmin")
    _pending_thread(author, _board())

    resp = client.get("/cms/")

    expected = reverse(Post.snippet_viewset.get_url_name("list"))
    assert f'href="{expected}?live=false"'.encode() in resp.content


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
