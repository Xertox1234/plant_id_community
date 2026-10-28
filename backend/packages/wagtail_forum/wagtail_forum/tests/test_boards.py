"""The Forum model (todo 665): validation, slug uniqueness, PROTECT."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from wagtail_forum.models import Forum, Topic
from wagtail_forum.tests.factories import make_category, make_forum


@pytest.mark.django_db
def test_forum_sits_under_its_category():
    board = make_forum(name="General", slug="general", description="Chat")

    assert board.forum_type == Forum.FORUM
    assert board.parent.forum_type == Forum.CATEGORY
    assert board.title == "General"  # the page-era key the API still serves
    assert board.topic_count == 0
    assert board.post_count == 0
    assert list(board.parent.children.all()) == [board]


@pytest.mark.django_db
def test_deleting_a_forum_with_topics_is_protected():
    board = make_forum()
    Topic.objects.create(board=board, title="T", slug="t")

    with pytest.raises(ProtectedError):
        board.delete()
    assert Topic.objects.filter(board=board).count() == 1


@pytest.mark.django_db
def test_deleting_a_category_with_forums_is_protected():
    board = make_forum()

    with pytest.raises(ProtectedError):
        board.parent.delete()


@pytest.mark.django_db
def test_validation_rejects_a_category_with_a_parent():
    category = make_category()
    child = Forum(forum_type=Forum.CATEGORY, parent=category, name="Sub", slug="sub")

    with pytest.raises(ValidationError) as exc:
        child.full_clean()
    assert "parent" in exc.value.message_dict


@pytest.mark.django_db
def test_validation_rejects_a_forum_without_a_category():
    for forum_type in (Forum.FORUM, Forum.LINK):
        orphan = Forum(forum_type=forum_type, name="Orphan", slug="orphan")
        with pytest.raises(ValidationError) as exc:
            orphan.full_clean()
        assert "parent" in exc.value.message_dict


@pytest.mark.django_db
def test_validation_rejects_a_forum_as_a_parent():
    board = make_forum()
    nested = Forum(forum_type=Forum.FORUM, parent=board, name="Sub", slug="sub")

    with pytest.raises(ValidationError) as exc:
        nested.full_clean()
    assert "parent" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("board_type", [Forum.CATEGORY, Forum.LINK])
def test_a_topic_cannot_sit_on_a_category_or_link(board_type):
    """Topic.board is limited to forums (todo 665 round-1 review): a topic on a
    category or link would vanish from the API, which lists forums only."""
    category = make_category()
    if board_type == Forum.CATEGORY:
        board = category
    else:
        board = Forum.objects.create(
            forum_type=Forum.LINK, parent=category, name="Docs", slug="docs"
        )

    with pytest.raises(ValidationError) as exc:
        Topic(board=board, title="T", slug="t").full_clean()
    assert "board" in exc.value.message_dict
    assert Topic._meta.get_field("board").get_limit_choices_to() == {
        "forum_type": Forum.FORUM
    }


@pytest.mark.django_db
def test_a_topic_on_a_forum_validates():
    Topic(board=make_forum(), title="T", slug="t").full_clean()


@pytest.mark.django_db
def test_validation_accepts_a_forum_under_a_category():
    category = make_category()
    Forum(forum_type=Forum.FORUM, parent=category, name="Ok", slug="ok").full_clean()
    Forum(forum_type=Forum.CATEGORY, name="Top", slug="top").full_clean()


@pytest.mark.django_db
def test_forum_slugs_are_unique_forum_wide():
    """A forum or link slug is unique across every category (DB constraint)."""
    make_forum(slug="ferns", category=make_category(slug="a"))

    with pytest.raises(IntegrityError), transaction.atomic():
        make_forum(slug="ferns", category=make_category(slug="b"))
    with pytest.raises(IntegrityError), transaction.atomic():
        Forum.objects.create(
            forum_type=Forum.LINK,
            parent=make_category(slug="a"),
            name="Link",
            slug="ferns",
        )


@pytest.mark.django_db
def test_category_slugs_share_a_namespace_only_with_categories():
    make_forum(slug="general")
    # A category may reuse a forum's slug (the 0041 default category does)...
    make_category(name="General", slug="general")
    # ...but not another category's.
    with pytest.raises(IntegrityError), transaction.atomic():
        Forum.objects.create(forum_type=Forum.CATEGORY, name="Again", slug="general")
