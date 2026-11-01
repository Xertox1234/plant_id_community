import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from wagtail_forum.models import Post, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()


def _topic():
    board = make_forum(name="General", slug="general")
    author = User.objects.create_user(username="op")
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
