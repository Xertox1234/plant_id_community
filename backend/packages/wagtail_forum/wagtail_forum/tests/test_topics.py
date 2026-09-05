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


@pytest.mark.django_db
def test_topic_with_an_account_deleted_author_can_still_be_republished():
    """SET_NULL leaves ``author`` NULL once the account is deleted, and
    ``save_revision()`` runs ``full_clean()``, which rejects a NULL-but-not-
    blank FK — so without ``blank=True`` (todo 338, the Post.author precedent
    from LEARNINGS 2026-07-03) the "hide → fix slug → republish" moderation
    flow raised ValidationError({'author': ['This field cannot be blank.']})
    on exactly the topics a moderator most needs to clean up."""
    user = User.objects.create_user(username="deleted-soon")
    topic = Topic(board=_board(), title="Orphaned", slug="orphaned", author=user)
    topic.save()
    topic.save_revision().publish()

    user.delete()
    topic.refresh_from_db()
    assert topic.author_id is None

    topic.unpublish()
    topic.slug = "orphaned-fixed"
    topic.save()
    topic.save_revision().publish()
    topic.refresh_from_db()

    assert topic.live is True
    assert topic.slug == "orphaned-fixed"
    assert topic.author_id is None
