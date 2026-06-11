"""Counter/trust reconciliation across the full content lifecycle.

Covers the 2026-06-10 forum audit findings:
- H3: unpublish/delete must recount counters and re-derive trust (a spammer must
  not keep autopublish trust earned from removed posts).
- M2: `published` fires on EVERY publish — notifications must fire only on the
  first publish, and topic activity (`last_post_at`) must not be corrupted by
  an edit-republish of an old post.
"""

import pytest
from django.contrib.auth import get_user_model
from wagtail.actions.unpublish import UnpublishAction
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.signals import reply_added, topic_created

User = get_user_model()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _topic(board, author, slug="t"):
    return Topic.objects.create(board=board, title="T", slug=slug, author=author)


def _publish(topic, author, opening=False):
    post = Post.objects.create(topic=topic, author=author, is_opening_post=opening)
    post.save_revision().publish()
    return post


@pytest.mark.django_db
def test_unpublish_reply_recounts_topic_board_and_profile():
    user = User.objects.create_user(username="ada", password="x")
    board = _board()
    topic = _topic(board, user)
    _publish(topic, user, opening=True)
    reply = _publish(topic, user)

    UnpublishAction(reply).execute()

    topic.refresh_from_db()
    board.refresh_from_db()
    profile = ForumProfile.for_user(user)
    assert topic.reply_count == 0
    assert board.post_count == 1
    assert profile.post_count == 1


@pytest.mark.django_db
def test_delete_reply_recounts_topic_board_and_profile():
    user = User.objects.create_user(username="ada", password="x")
    board = _board()
    topic = _topic(board, user)
    _publish(topic, user, opening=True)
    reply = _publish(topic, user)

    reply.delete()

    topic.refresh_from_db()
    board.refresh_from_db()
    profile = ForumProfile.for_user(user)
    assert topic.reply_count == 0
    assert board.post_count == 1
    assert profile.post_count == 1


@pytest.mark.django_db
def test_unpublish_topic_recounts_board_topic_count():
    user = User.objects.create_user(username="ada", password="x")
    board = _board()
    topic = _topic(board, user)
    _publish(topic, user, opening=True)
    board.refresh_from_db()
    assert board.topic_count == 1

    UnpublishAction(topic).execute()

    board.refresh_from_db()
    assert board.topic_count == 0


@pytest.mark.django_db
def test_removed_posts_demote_auto_earned_trust():
    # 5 live posts auto-earn MEMBER (autopublish). Removing them as spam must
    # revoke that trust, or the moderation gate is permanently defeated.
    user = User.objects.create_user(username="spammer", password="x")
    board = _board()
    topic = _topic(board, user)
    posts = [_publish(topic, user, opening=True)]
    posts += [_publish(topic, user) for _ in range(4)]
    profile = ForumProfile.for_user(user)
    assert profile.trust_level == TrustLevel.MEMBER

    for post in posts[1:]:  # moderator removes 4 of the 5
        UnpublishAction(post).execute()

    profile.refresh_from_db()
    assert profile.post_count == 1
    assert profile.trust_level == TrustLevel.BASIC


@pytest.mark.django_db
def test_manually_granted_trust_survives_post_removal():
    # An admin-granted level above what post_count earns must NOT be clawed
    # back by the automatic reconciliation.
    user = User.objects.create_user(username="vip", password="x")
    board = _board()
    topic = _topic(board, user)
    post = _publish(topic, user, opening=True)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.LEADER  # manual grant (1 post earns BASIC)
    profile.save(update_fields=["trust_level"])

    UnpublishAction(post).execute()

    profile.refresh_from_db()
    assert profile.trust_level == TrustLevel.LEADER


@pytest.mark.django_db
def test_republish_does_not_refire_notifications():
    user = User.objects.create_user(username="ada", password="x")
    board = _board()
    topic = _topic(board, user)
    _publish(topic, user, opening=True)
    reply = _publish(topic, user)

    fired = []

    def on_reply(sender, **kwargs):
        fired.append(kwargs)

    reply_added.connect(on_reply)
    try:
        # Refresh first — admin edit-republish always loads fresh from the DB;
        # republishing a stale instance would corrupt first_published_at itself.
        reply.refresh_from_db()
        reply.save_revision().publish()  # moderator edit-republish
    finally:
        reply_added.disconnect(on_reply)

    assert fired == []


@pytest.mark.django_db
def test_republish_of_old_post_does_not_corrupt_topic_activity():
    user = User.objects.create_user(username="ada", password="x")
    other = User.objects.create_user(username="bob", password="x")
    board = _board()
    topic = _topic(board, user)
    old_post = _publish(topic, user, opening=True)
    _publish(topic, other)  # newest activity: bob

    topic.refresh_from_db()
    at_before, author_before = topic.last_post_at, topic.last_post_author_id

    old_post.refresh_from_db()
    old_post.save_revision().publish()  # edit-republish post #1

    topic.refresh_from_db()
    assert topic.last_post_at == at_before
    assert topic.last_post_author_id == author_before


@pytest.mark.django_db
def test_topic_created_fires_once_and_only_when_topic_is_live():
    user = User.objects.create_user(username="ada", password="x")
    board = _board()

    fired = []

    def on_created(sender, topic, post, **kwargs):
        # The host deep-links immediately — the topic must already be live.
        fired.append(topic.live)

    topic_created.connect(on_created)
    try:
        topic = _topic(
            board, user
        )  # objects.create() → born live → no revision publish yet
        _publish(topic, user, opening=True)
        topic.save_revision().publish()  # first revision-publish of the topic
        topic.refresh_from_db()
        topic.save_revision().publish()  # re-publish (edit) — must not re-fire
    finally:
        topic_created.disconnect(on_created)

    assert fired == [True]


@pytest.mark.django_db
def test_removing_the_only_live_post_keeps_last_post_at_non_null():
    # Cursor-pagination invariant: a live topic NEVER has a null last_post_at
    # (NULLS FIRST floats it to the top; a None cursor position 500s).
    user = User.objects.create_user(username="ada", password="x")
    board = _board()
    topic = _topic(board, user)
    only_post = _publish(topic, user, opening=True)

    UnpublishAction(only_post).execute()

    topic.refresh_from_db()
    assert topic.live is True
    assert topic.last_post_at is not None


@pytest.mark.django_db
def test_topic_takedown_revokes_trust_and_board_post_count():
    # Unpublishing the TOPIC (not each post) must stop its posts funding
    # board.post_count and the author's autopublish trust (review finding 6).
    user = User.objects.create_user(username="spammer", password="x")
    board = _board()
    topic = _topic(board, user)
    _publish(topic, user, opening=True)
    for _ in range(4):
        _publish(topic, user)
    profile = ForumProfile.for_user(user)
    assert profile.trust_level == TrustLevel.MEMBER

    UnpublishAction(topic).execute()

    board.refresh_from_db()
    profile.refresh_from_db()
    assert board.post_count == 0
    assert profile.post_count == 0
    assert profile.trust_level < TrustLevel.MEMBER


@pytest.mark.django_db
def test_topic_delete_reconciles_board_and_trust():
    user = User.objects.create_user(username="ada", password="x")
    board = _board()
    topic = _topic(board, user)
    _publish(topic, user, opening=True)
    _publish(topic, user)
    board.refresh_from_db()
    assert board.post_count == 2

    topic.delete()

    board.refresh_from_db()
    profile = ForumProfile.for_user(user)
    assert board.topic_count == 0
    assert board.post_count == 0
    assert profile.post_count == 0
