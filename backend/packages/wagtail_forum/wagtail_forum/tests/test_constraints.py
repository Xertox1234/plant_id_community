import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


def _topic():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="op", password="x")
    return Topic.objects.create(board=board, title="T", slug="t", author=author)


@pytest.mark.django_db
def test_only_one_opening_post_per_topic():
    topic = _topic()
    Post.objects.create(topic=topic, author=topic.author, is_opening_post=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Post.objects.create(topic=topic, author=topic.author, is_opening_post=True)
    # Non-opening replies are unconstrained.
    Post.objects.create(topic=topic, author=topic.author, is_opening_post=False)
    Post.objects.create(topic=topic, author=topic.author, is_opening_post=False)
