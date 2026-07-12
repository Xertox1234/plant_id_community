import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


def _topic(user):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
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
