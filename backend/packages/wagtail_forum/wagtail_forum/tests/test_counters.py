import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.models import ForumProfile, Post, Topic, TrustLevel
from wagtail_forum.tests.factories import make_forum

User = get_user_model()


def _topic(author):
    board = make_forum(name="General", slug="general")
    return Topic.objects.create(board=board, title="T", slug="t", author=author)


def _publish(topic, author, opening=False):
    post = Post.objects.create(topic=topic, author=author, is_opening_post=opening)
    post.save_revision().publish()
    return post


@pytest.mark.django_db
def test_reply_updates_topic_and_board_and_profile_counters():
    user = User.objects.create_user(username="ada")
    topic = _topic(user)
    _publish(topic, user, opening=True)
    _publish(topic, user)  # one reply

    topic.refresh_from_db()
    topic.board.refresh_from_db()
    profile = ForumProfile.for_user(user)

    assert topic.reply_count == 1
    assert topic.last_post_author_id == user.id
    assert topic.last_post_at is not None
    assert topic.board.post_count == 2
    assert topic.board.topic_count == 1
    assert profile.post_count == 2
    # 2 posts clears the BASIC threshold (TRUST_THRESHOLDS {1: 1}).
    assert profile.trust_level == TrustLevel.BASIC


@pytest.mark.django_db
def test_post_count_promotes_trust_level_to_member():
    # _maybe_promote: TRUST_THRESHOLDS {1:1, 2:5, ...} → 5 live posts == MEMBER.
    user = User.objects.create_user(username="climber")
    topic = _topic(user)
    _publish(topic, user, opening=True)
    for _ in range(4):
        _publish(topic, user)  # 5 published posts total

    profile = ForumProfile.for_user(user)
    assert profile.post_count == 5
    assert profile.trust_level == TrustLevel.MEMBER


# ---- a move in the /cms/ editor recounts BOTH sides (audit 2026-11-21 M2) ----


@pytest.mark.django_db
def test_moving_a_topic_to_another_forum_recounts_the_forum_it_left():
    user = User.objects.create_user(username="mover")
    source = make_forum(name="Pests", slug="pests")
    target = make_forum(name="Care", slug="care")
    topic = Topic.objects.create(board=source, title="T", slug="t", author=user)
    _publish(topic, user, opening=True)
    _publish(topic, user)
    topic.save_revision().publish()
    source.refresh_from_db()
    assert (source.topic_count, source.post_count) == (1, 2)

    # What the editor's Board field does: a revision with the new board,
    # published (publish saves a copy built from the revision).
    topic.refresh_from_db()
    topic.board = target
    topic.save_revision().publish()

    source.refresh_from_db()
    target.refresh_from_db()
    assert (source.topic_count, source.post_count) == (0, 0)
    assert (target.topic_count, target.post_count) == (1, 2)


@pytest.mark.django_db
def test_moving_a_reply_to_another_topic_recounts_the_topic_it_left():
    user = User.objects.create_user(username="replymover")
    other = User.objects.create_user(username="other")
    board = make_forum(name="General", slug="general")
    old = Topic.objects.create(board=board, title="Old", slug="old", author=user)
    new = Topic.objects.create(board=board, title="New", slug="new", author=user)
    _publish(old, user, opening=True)
    _publish(new, user, opening=True)
    reply = _publish(old, other)
    old.refresh_from_db()
    assert (old.reply_count, old.last_post_author_id) == (1, other.pk)

    reply.refresh_from_db()
    reply.topic = new
    reply.save_revision().publish()

    old.refresh_from_db()
    new.refresh_from_db()
    assert (old.reply_count, old.last_post_author_id) == (0, user.pk)
    assert (new.reply_count, new.last_post_author_id) == (1, other.pk)


@pytest.mark.django_db
def test_moving_a_reply_to_a_topic_on_another_forum_recounts_both_forums():
    user = User.objects.create_user(username="crossmover")
    source = make_forum(name="Pests", slug="pests")
    target = make_forum(name="Care", slug="care")
    old = Topic.objects.create(board=source, title="Old", slug="old", author=user)
    new = Topic.objects.create(board=target, title="New", slug="new", author=user)
    for topic in (old, new):
        _publish(topic, user, opening=True)
        topic.save_revision().publish()
    reply = _publish(old, user)
    source.refresh_from_db()
    assert source.post_count == 2

    reply.refresh_from_db()
    reply.topic = new
    reply.save_revision().publish()

    source.refresh_from_db()
    target.refresh_from_db()
    assert (source.post_count, target.post_count) == (1, 2)
