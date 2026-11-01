"""Per-forum display settings (todo 669).

A closed forum (phpBB "locked"; `is_closed` because the API's `is_locked`
already means an un-unlocked password forum) refuses new topics and replies
from members with 403 ``forum_closed`` and lets staff through. A forum's
``topics_per_page`` and ``default_sort`` shape its topic list. Colour, icon,
rules URL and the rest are validated on the model, which the admin form runs.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.api.pagination import TopicCursorPagination
from wagtail_forum.models import ForumModerator, ForumProfile, Post, Topic, TrustLevel
from wagtail_forum.models.boards import FORUM_SORT_CHOICES
from wagtail_forum.tests.factories import make_forum
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

BODY = [{"type": "paragraph", "value": "<p>Hello.</p>"}]


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _client(user):
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    client = APIClient()
    client.force_authenticate(user)
    return client


def _topic(forum, author, slug, *, created, views=0):
    topic = Topic.objects.create(
        board=forum,
        title=slug.title(),
        slug=slug,
        author=author,
        live=True,
        view_count=views,
        last_post_at=created,
    )
    Topic.objects.filter(pk=topic.pk).update(created_at=created)
    Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True, body=BODY
    )
    return topic


def _create_topic(client, forum, slug="new"):
    return client.post(
        f"/forum/boards/{forum.slug}/topics/",
        {"title": "New", "slug": slug, "body": BODY},
        format="json",
    )


def _reply(client, topic):
    return client.post(
        f"/forum/topics/{topic.pk}/posts/", {"body": BODY}, format="json"
    )


# ------------------------------------------------------------------ closed


def test_posting_to_a_closed_forum_is_403_for_members_and_allowed_for_staff():
    ensure_default_workflow()
    forum = make_forum(name="Archive", slug="archive", is_closed=True)
    author = User.objects.create_user(username="op")
    topic = _topic(forum, author, "old", created=timezone.now())
    member = _client(User.objects.create_user(username="member"))

    resp = _create_topic(member, forum)
    assert resp.status_code == 403
    assert resp.json()["code"] == "forum_closed"
    resp = _reply(member, topic)
    assert resp.status_code == 403
    assert resp.json()["code"] == "forum_closed"

    staff = _client(User.objects.create_user(username="staff", is_staff=True))
    assert _create_topic(staff, forum, slug="staff-topic").status_code == 201
    assert _reply(staff, topic).status_code == 201

    # The forum's own moderators are exempt too.
    moderator = User.objects.create_user(username="mod")
    ForumModerator.objects.create(forum=forum, user=moderator)
    mod_client = _client(moderator)
    assert _create_topic(mod_client, forum, slug="mod-topic").status_code == 201


def test_a_closed_forum_row_says_so_and_offers_members_no_composer():
    forum = make_forum(name="Archive", slug="archive", is_closed=True)
    member = _client(User.objects.create_user(username="member"))
    row = next(
        f
        for c in member.get("/forum/categories/").json()["results"]
        for f in c["forums"]
        if f["id"] == forum.pk
    )
    assert row["is_closed"] is True
    assert row["can_post"] is False and row["can_reply"] is False


# ---------------------------------------------- topics per page, default sort


def test_topics_per_page_and_default_sort_change_the_topic_list():
    author = User.objects.create_user(username="op")
    now = timezone.now()
    forum = make_forum(name="Ferns", slug="ferns")
    oldest = _topic(forum, author, "oldest", created=now - timedelta(days=3))
    _topic(forum, author, "middle", created=now - timedelta(days=2), views=50)
    newest = _topic(forum, author, "newest", created=now - timedelta(days=1))
    client = APIClient()

    def slugs(response):
        assert response.status_code == 200
        return [t["slug"] for t in response.json()["results"]]

    # Site defaults: every topic, latest activity first.
    assert slugs(client.get("/forum/boards/ferns/topics/")) == [
        "newest",
        "middle",
        "oldest",
    ]

    forum.topics_per_page = 2
    forum.default_sort = "created_at"
    forum.save()
    cache.clear()
    first = client.get("/forum/boards/ferns/topics/")
    assert slugs(first) == ["oldest", "middle"]
    # The next page keeps the forum's order and page size.
    nxt = first.json()["next"]
    assert nxt
    assert slugs(client.get(nxt)) == ["newest"]

    # An explicit ?sort= and ?page_size= still win.
    assert slugs(client.get("/forum/boards/ferns/topics/?sort=-view_count"))[0] == (
        "middle"
    )
    assert len(slugs(client.get("/forum/boards/ferns/topics/?page_size=3"))) == 3
    assert oldest.pk != newest.pk


def test_default_sort_choices_match_the_topic_list_sorts():
    assert [value for value, _ in FORUM_SORT_CHOICES] == list(
        TopicCursorPagination.SORT_ORDERINGS
    )


# --------------------------------------------------------------- validation


@pytest.mark.parametrize("colour", ["red", "#ff0000", "var(--gt-ink)", "SAGE"])
def test_invalid_colour_values_are_rejected(colour):
    forum = make_forum(name="Ferns", slug="ferns")
    forum.colour = colour
    with pytest.raises(ValidationError) as exc:
        forum.full_clean()
    assert "colour" in exc.value.message_dict


@pytest.mark.parametrize("colour", ["", "sage", "pollen", "bloom", "orchid"])
def test_canopy_accent_colours_are_accepted(colour):
    forum = make_forum(name="Ferns", slug="ferns")
    forum.colour = colour
    forum.full_clean()


@pytest.mark.parametrize("icon", ["a", "ab", "🌿 ", "🌿🌵", "1", "<b>", "★x"])
def test_an_icon_must_be_one_emoji(icon):
    forum = make_forum(name="Ferns", slug="ferns")
    forum.icon = icon
    with pytest.raises(ValidationError) as exc:
        forum.full_clean()
    assert "icon" in exc.value.message_dict


@pytest.mark.parametrize("icon", ["", "🌿", "🌵", "☘️", "👩🏽‍🌾", "🇬🇧", "#️⃣"])
def test_single_emoji_icons_are_accepted(icon):
    forum = make_forum(name="Ferns", slug="ferns")
    forum.icon = icon
    forum.full_clean()


def test_rules_url_must_be_a_web_address_and_page_size_is_bounded():
    forum = make_forum(name="Ferns", slug="ferns")
    forum.rules_url = "javascript:alert(1)"
    forum.topics_per_page = 101
    with pytest.raises(ValidationError) as exc:
        forum.full_clean()
    assert {"rules_url", "topics_per_page"} <= set(exc.value.message_dict)


def test_display_settings_are_served_on_the_forum_row():
    forum = make_forum(
        name="Ferns",
        slug="ferns",
        rules="Be kind.\nNo spam.",
        rules_url="https://example.com/rules",
        icon="🌿",
        colour="sage",
        topics_per_page=10,
        default_sort="-created_at",
    )
    category = forum.parent
    category.icon = "🪴"
    category.colour = "bloom"
    category.save()
    data = APIClient().get("/forum/categories/").json()["results"][0]
    assert (data["icon"], data["colour"]) == ("🪴", "bloom")
    row = data["forums"][0]
    assert row["rules"] == "Be kind.\nNo spam."
    assert row["rules_url"] == "https://example.com/rules"
    assert (row["icon"], row["colour"]) == ("🌿", "sage")
    assert (row["topics_per_page"], row["default_sort"]) == (10, "-created_at")
    assert row["image_url"] is None
    assert row["is_closed"] is False
