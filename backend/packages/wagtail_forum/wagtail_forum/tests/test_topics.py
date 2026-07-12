import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

User = get_user_model()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_topic_publishes_via_revision():
    user = User.objects.create_user(username="ada")
    topic = Topic(board=_board(), title="Pothos help", slug="pothos-help", author=user)
    topic.save()

    revision = topic.save_revision()
    revision.publish()
    topic.refresh_from_db()

    assert topic.live is True
    assert topic.latest_revision is not None
    # The canonical `revisions` GenericRelation (base_content_type) resolves the
    # topic's own revision — guards the relation against silent content-type drift.
    assert topic.revisions.count() == 1
    assert topic.reply_count == 0
    assert topic.is_closed is False


@pytest.mark.django_db
def test_topic_slug_unique_per_board():
    from django.db import IntegrityError

    board = _board()
    Topic.objects.create(board=board, title="A", slug="dup")
    with pytest.raises(IntegrityError):
        Topic.objects.create(board=board, title="B", slug="dup")
