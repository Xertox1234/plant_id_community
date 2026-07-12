import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Reaction, Topic

User = get_user_model()


def _post(author):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
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
