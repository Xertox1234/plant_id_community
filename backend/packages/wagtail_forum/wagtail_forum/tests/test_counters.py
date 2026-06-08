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

User = get_user_model()


def _topic(author):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    return Topic.objects.create(board=board, title="T", slug="t", author=author)


def _publish(topic, author, opening=False):
    post = Post.objects.create(topic=topic, author=author, is_opening_post=opening)
    post.save_revision().publish()
    return post


@pytest.mark.django_db
def test_reply_updates_topic_and_board_and_profile_counters():
    user = User.objects.create_user(username="ada", password="x")
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
    user = User.objects.create_user(username="climber", password="x")
    topic = _topic(user)
    _publish(topic, user, opening=True)
    for _ in range(4):
        _publish(topic, user)  # 5 published posts total

    profile = ForumProfile.for_user(user)
    assert profile.post_count == 5
    assert profile.trust_level == TrustLevel.MEMBER
