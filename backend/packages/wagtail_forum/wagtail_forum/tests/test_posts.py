import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.models import Post, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()


def _topic(user):
    board = make_forum(name="General", slug="general")
    return Topic.objects.create(board=board, title="T", slug="t", author=user)


@pytest.mark.django_db
def test_opening_post_has_body_and_flag():
    user = User.objects.create_user(username="ada")
    topic = _topic(user)
    post = Post.objects.create(
        topic=topic,
        author=user,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>First!</p>"}],
    )

    post.refresh_from_db()
    assert post.is_opening_post is True
    assert post.reaction_counts == {}
    assert post.body[0].block_type == "paragraph"


@pytest.mark.django_db
def test_post_publishes_via_revision():
    user = User.objects.create_user(username="ada")
    post = Post.objects.create(topic=_topic(user), author=user)
    revision = post.save_revision()
    revision.publish()
    post.refresh_from_db()
    assert post.live is True
    assert post.revisions.count() == 1


@pytest.mark.django_db
def test_can_be_reported_by_blocks_self_report_and_anonymous():
    author = User.objects.create_user(username="ada")
    other = User.objects.create_user(username="bea")
    post = Post.objects.create(topic=_topic(author), author=author)

    assert post.can_be_reported_by(author) is False  # self-report
    assert post.can_be_reported_by(other) is True
    assert post.can_be_reported_by(None) is False
