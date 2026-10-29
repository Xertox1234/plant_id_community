"""Changing a forum row's type in the admin (todo 667). Owner decision
2026-10-29: forum ↔ category only (link conversions are todo 670); a
category that still holds forums is refused, and no category or link ever
ends up holding a topic."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from wagtail_forum.models import Forum, Post, Topic
from wagtail_forum.services import forum_structure
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()

NS = "wagtail_forum_forums"

pytestmark = pytest.mark.django_db


def _url(name, *args):
    return reverse(f"{NS}:{name}", args=args)


@pytest.fixture
def admin_client(client):
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))
    return client


def _topic(board, slug):
    author = User.objects.get_or_create(username="ada")[0]
    topic = Topic.objects.create(board=board, title=slug, slug=slug, author=author)
    Post.objects.create(
        topic=topic, author=author, is_opening_post=True
    ).save_revision().publish()
    return topic


def _no_topics_on_categories_or_links():
    return not Topic.objects.exclude(board__forum_type=Forum.FORUM).exists()


# --- forum -> category ---


def test_edit_page_offers_change_type(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")

    resp = admin_client.get(_url("edit", forum.pk))

    assert _url("change_type", forum.pk) in resp.content.decode()


def test_an_empty_forum_becomes_a_category(admin_client):
    make_category(name="First", slug="first")
    forum = make_forum(name="Ferns", slug="ferns")

    resp = admin_client.post(_url("change_type", forum.pk), {})

    assert resp.status_code == 302, resp.content.decode()[:2000]
    forum.refresh_from_db()
    assert forum.forum_type == Forum.CATEGORY
    assert forum.parent is None
    assert (forum.topic_count, forum.post_count) == (0, 0)
    # It ranks after the existing categories.
    assert forum.position == (
        Forum.objects.filter(forum_type=Forum.CATEGORY)
        .exclude(pk=forum.pk)
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
        + 1
    )


def test_a_forum_with_topics_is_refused_without_a_choice(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")
    _topic(forum, "a")

    page = admin_client.get(_url("change_type", forum.pk))
    resp = admin_client.post(_url("change_type", forum.pk), {})

    assert "must be moved to another forum or deleted first" in page.content.decode()
    assert resp.status_code == 200
    assert "topics_action" in resp.context["form"].errors
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM
    assert Topic.objects.filter(board=forum).count() == 1


def test_a_forum_becomes_a_category_after_its_topics_move(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    topic = _topic(forum, "a")

    resp = admin_client.post(
        _url("change_type", forum.pk),
        {"topics_action": forum_structure.MOVE, "target": target.pk},
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    forum.refresh_from_db()
    target.refresh_from_db()
    topic.refresh_from_db()
    assert forum.forum_type == Forum.CATEGORY
    assert topic.board_id == target.pk
    assert (target.topic_count, target.post_count) == (1, 1)
    assert _no_topics_on_categories_or_links()


def test_a_forum_becomes_a_category_after_its_topics_are_deleted(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")
    topic = _topic(forum, "a")

    resp = admin_client.post(
        _url("change_type", forum.pk), {"topics_action": forum_structure.DELETE}
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    forum.refresh_from_db()
    assert forum.forum_type == Forum.CATEGORY
    assert not Topic.objects.filter(pk=topic.pk).exists()
    assert _no_topics_on_categories_or_links()


@pytest.mark.parametrize("kind", ["self", "category", "link"])
def test_a_forum_to_category_move_target_is_validated(admin_client, kind):
    forum = make_forum(name="Ferns", slug="ferns")
    _topic(forum, "a")
    target_id = {
        "self": lambda: forum.pk,
        "category": lambda: forum.parent_id,
        "link": lambda: Forum.objects.create(
            forum_type=Forum.LINK, parent=forum.parent, name="Shop", slug="shop"
        ).pk,
    }[kind]()

    resp = admin_client.post(
        _url("change_type", forum.pk),
        {"topics_action": forum_structure.MOVE, "target": target_id},
    )

    assert resp.status_code == 200
    assert "target" in resp.context["form"].errors
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM
    assert _no_topics_on_categories_or_links()


def test_a_forum_whose_slug_a_category_uses_is_refused(admin_client):
    make_category(name="Ferns", slug="ferns")
    forum = make_forum(name="Ferns", slug="ferns")

    resp = admin_client.post(_url("change_type", forum.pk), {})

    assert resp.status_code == 200
    assert resp.context["form"].non_field_errors()
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM


# --- category -> forum ---


def test_a_category_with_forums_is_refused(admin_client):
    category = make_category()
    other = make_category(name="Outdoor", slug="outdoor")
    make_forum(name="Ferns", slug="ferns", category=category)

    page = admin_client.get(_url("change_type", category.pk))
    resp = admin_client.post(
        _url("change_type", category.pk), {"target_category": other.pk}
    )

    assert "This category still holds 1 forum." in page.content.decode()
    assert resp.status_code == 200
    assert resp.context["form"].non_field_errors()
    category.refresh_from_db()
    assert category.forum_type == Forum.CATEGORY


def test_the_service_refuses_a_category_with_forums():
    category = make_category()
    other = make_category(name="Outdoor", slug="outdoor")
    make_forum(name="Ferns", slug="ferns", category=category)

    with pytest.raises(forum_structure.ValidationError):
        forum_structure.change_type(category, Forum.FORUM, category=other)

    category.refresh_from_db()
    assert category.forum_type == Forum.CATEGORY


def test_an_empty_category_becomes_a_forum_in_the_chosen_category(admin_client):
    category = make_category(name="Ferns", slug="ferns")
    home = make_category(name="Outdoor", slug="outdoor")
    make_forum(name="Trees", slug="trees", category=home, position=2)

    resp = admin_client.post(
        _url("change_type", category.pk), {"target_category": home.pk}
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    category.refresh_from_db()
    assert category.forum_type == Forum.FORUM
    assert category.parent_id == home.pk
    assert category.position == 3


@pytest.mark.parametrize("kind", ["none", "self", "forum", "missing"])
def test_category_to_forum_needs_a_real_category(admin_client, kind):
    category = make_category(name="Ferns", slug="ferns")
    forum = make_forum(name="Trees", slug="trees")
    data = {
        "none": {},
        "self": {"target_category": category.pk},
        "forum": {"target_category": forum.pk},
        "missing": {"target_category": forum.pk + 1000},
    }[kind]

    resp = admin_client.post(_url("change_type", category.pk), data)

    assert resp.status_code == 200
    assert "target_category" in resp.context["form"].errors
    category.refresh_from_db()
    assert category.forum_type == Forum.CATEGORY


# --- links and permissions ---


def test_a_link_cannot_change_type_yet(admin_client):
    category = make_category()
    link = Forum.objects.create(
        forum_type=Forum.LINK, parent=category, name="Shop", slug="shop"
    )

    page = admin_client.get(_url("change_type", link.pk))
    resp = admin_client.post(_url("change_type", link.pk), {})

    assert "cannot be changed yet" in page.content.decode()
    assert resp.status_code == 200
    link.refresh_from_db()
    assert link.forum_type == Forum.LINK


def test_change_type_needs_the_change_permission(client):
    forum = make_forum(name="Ferns", slug="ferns")
    user = User.objects.create_user(username="viewer", email="v@x.io")
    user.user_permissions.set(
        Permission.objects.filter(codename__in=["access_admin", "add_forum"])
    )
    client.force_login(user)

    resp = client.post(
        _url("change_type", forum.pk), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )

    assert resp.status_code == 403
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM
