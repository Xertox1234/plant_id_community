import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail_forum.models import Post, Reaction, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()


def _post(author):
    board = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post.objects.create(topic=topic, author=author, is_opening_post=True)


@pytest.mark.django_db
def test_recount_updates_post_counts():
    a = User.objects.create_user(username="a")
    b = User.objects.create_user(username="b")
    post = _post(a)

    Reaction.objects.create(post=post, user=a, reaction_type=Reaction.LIKE)
    Reaction.objects.create(post=post, user=b, reaction_type=Reaction.LIKE)
    Reaction.objects.create(post=post, user=b, reaction_type=Reaction.THANKS)
    Reaction.recount(post)

    post.refresh_from_db()
    assert post.reaction_counts == {"like": 2, "thanks": 1}


@pytest.mark.django_db
def test_one_reaction_per_user_per_type():
    a = User.objects.create_user(username="a")
    post = _post(a)
    Reaction.objects.create(post=post, user=a, reaction_type=Reaction.LIKE)
    with pytest.raises(IntegrityError):
        Reaction.objects.create(post=post, user=a, reaction_type=Reaction.LIKE)
