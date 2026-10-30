"""Link forums with click tracking (todo 670; spec 2026-10-28 §2).

A link is a row on the index that sends readers to an http(s) URL; tracked
links go through ``/forum/links/{id}/go/``, which counts the click. Links
never hold topics, never reach ``/forum/boards/`` (Flutter would fetch
``/topics/`` on one), and type changes to or from ``link`` keep 667's rules.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail_forum.models import Forum, Post, Topic
from wagtail_forum.tests.factories import hide_forum, make_category, make_forum

User = get_user_model()

NS = "wagtail_forum_forums"

pytestmark = pytest.mark.django_db


def _link(category=None, slug="shop", **fields):
    fields.setdefault("link_url", "https://shop.example.com/")
    return Forum.objects.create(
        forum_type=Forum.LINK,
        parent=category or make_category(),
        name="Shop",
        slug=slug,
        **fields,
    )


def _admin_url(name, *args):
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


# --- AC0: the redirect counts once per request; bad schemes refused at save ---


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_a_tracked_click_increments_once_per_request_and_redirects():
    link = _link(track_clicks=True)
    client = APIClient()

    first = client.get(f"/forum/links/{link.pk}/go/")
    link.refresh_from_db()
    assert link.click_count == 1
    second = client.get(f"/forum/links/{link.pk}/go/")
    link.refresh_from_db()

    assert first.status_code == second.status_code == 302
    assert first["Location"] == "https://shop.example.com/"
    assert link.click_count == 2
    # Never shared-cached: a CDN hit would swallow the count.
    assert "no-store" in first["Cache-Control"] or "no-cache" in first["Cache-Control"]


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_an_untracked_link_redirects_without_counting():
    link = _link(track_clicks=False)

    resp = APIClient().get(f"/forum/links/{link.pk}/go/")

    assert resp.status_code == 302
    link.refresh_from_db()
    assert link.click_count == 0


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_the_redirect_404s_for_a_forum_a_hidden_link_or_a_bad_stored_scheme():
    forum = make_forum(name="Ferns", slug="ferns")
    hidden = _link(slug="hidden")
    hide_forum(hidden)
    # Written around the model's validation: must never be followed.
    forged = _link(slug="forged")
    Forum.objects.filter(pk=forged.pk).update(link_url="javascript:alert(1)")
    client = APIClient()

    for row in (forum, hidden, forged):
        assert client.get(f"/forum/links/{row.pk}/go/").status_code == 404
    forged.refresh_from_db()
    assert forged.click_count == 0


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,hi",
        "ftp://files.example.com/",
        "mailto:a@example.com",
        "",
    ],
)
def test_a_link_url_other_than_http_or_https_is_rejected_at_save(url):
    link = Forum(
        forum_type=Forum.LINK,
        parent=make_category(),
        name="Shop",
        slug="shop",
        link_url=url,
    )

    with pytest.raises(ValidationError) as excinfo:
        link.full_clean()

    assert "link_url" in excinfo.value.message_dict


def test_http_and_https_link_urls_are_accepted():
    category = make_category()
    for n, url in enumerate(["http://a.example.com/", "https://b.example.com/x?y=1"]):
        Forum(
            forum_type=Forum.LINK,
            parent=category,
            name="Shop",
            slug=f"shop-{n}",
            link_url=url,
        ).full_clean()


def test_the_admin_form_rejects_a_javascript_url(admin_client):
    category = make_category()

    resp = admin_client.post(
        _admin_url("add"),
        {
            "forum_type": Forum.LINK,
            "parent": category.pk,
            "name": "Shop",
            "slug": "shop",
            "description": "",
            "link_url": "javascript:alert(1)",
            "track_clicks": "on",
        },
    )

    assert resp.status_code == 200
    assert "link_url" in resp.context["form"].errors
    assert not Forum.objects.filter(slug="shop").exists()


# --- AC1: a link never accepts a topic ---


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_creating_a_topic_in_a_link_forum_is_refused():
    link = _link()
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="ada", email="a@x.io"))

    resp = client.post(
        f"/forum/boards/{link.slug}/topics/",
        {
            "title": "Hello there",
            "slug": "hello-there",
            "body": [{"type": "paragraph", "value": "<p>Hi</p>"}],
        },
        format="json",
    )

    assert resp.status_code == 404
    assert not Topic.objects.filter(board=link).exists()


def test_a_link_is_never_a_topic_move_target():
    from wagtail_forum.services import forum_structure

    forum = make_forum(name="Ferns", slug="ferns")
    _topic(forum, "a")
    link = _link()

    with pytest.raises(ValidationError):
        forum_structure.move_topics(forum, link)
    assert not Topic.objects.filter(board=link).exists()


# --- AC2: links never reach /forum/boards/; they ride /forum/categories/ ---


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_link_forums_never_appear_in_the_board_list():
    category = make_category()
    board = make_forum(name="General", slug="general", category=category)
    _link(category, track_clicks=True)
    _link(category, slug="docs", track_clicks=False)

    results = APIClient().get("/forum/boards/").json()["results"]

    assert [r["id"] for r in results] == [board.pk]


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_links_are_listed_under_their_category_with_a_click_count_when_tracked():
    category = make_category()
    make_forum(name="General", slug="general", category=category)
    tracked = _link(category, track_clicks=True, click_count=7, position=1)
    plain = _link(category, slug="docs", track_clicks=False, position=2)

    (row,) = APIClient().get("/forum/categories/").json()["results"]

    assert [f["slug"] for f in row["forums"]] == ["general"]
    assert row["links"] == [
        {
            "id": tracked.pk,
            "title": "Shop",
            "slug": "shop",
            "description": "",
            "link_url": "https://shop.example.com/",
            "track_clicks": True,
            "click_count": 7,
        },
        {
            "id": plain.pk,
            "title": "Shop",
            "slug": "docs",
            "description": "",
            "link_url": "https://shop.example.com/",
            "track_clicks": False,
            "click_count": None,
        },
    ]


# --- AC3: the admin form offers link and requires a valid URL ---


def test_the_admin_form_offers_the_link_type(admin_client):
    resp = admin_client.get(_admin_url("add"))

    choices = [
        value for value, _label in resp.context["form"].fields["forum_type"].choices
    ]
    assert Forum.LINK in choices
    assert "link_url" in resp.context["form"].fields


def test_the_admin_form_requires_a_url_for_a_link(admin_client):
    category = make_category()

    resp = admin_client.post(
        _admin_url("add"),
        {
            "forum_type": Forum.LINK,
            "parent": category.pk,
            "name": "Shop",
            "slug": "shop",
            "description": "",
            "link_url": "",
        },
    )

    assert resp.status_code == 200
    assert "link_url" in resp.context["form"].errors
    assert not Forum.objects.filter(slug="shop").exists()


def test_the_admin_form_creates_a_link_with_a_valid_url(admin_client):
    category = make_category()

    resp = admin_client.post(
        _admin_url("add"),
        {
            "forum_type": Forum.LINK,
            "parent": category.pk,
            "name": "Shop",
            "slug": "shop",
            "description": "Our plant shop",
            "link_url": "https://shop.example.com/",
            "track_clicks": "on",
        },
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    link = Forum.objects.get(slug="shop")
    assert (link.forum_type, link.parent_id) == (Forum.LINK, category.pk)
    assert (link.link_url, link.track_clicks) == ("https://shop.example.com/", True)


def test_a_forum_saved_with_a_url_typed_in_keeps_none(admin_client):
    category = make_category()

    resp = admin_client.post(
        _admin_url("add"),
        {
            "forum_type": Forum.FORUM,
            "parent": category.pk,
            "name": "Ferns",
            "slug": "ferns",
            "description": "",
            "link_url": "https://shop.example.com/",
        },
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    assert Forum.objects.get(slug="ferns").link_url == ""


# --- AC4: type changes to and from link keep 667's rules ---


def test_a_forum_with_topics_cannot_become_a_link_without_a_choice(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")
    _topic(forum, "a")

    resp = admin_client.post(
        _admin_url("change_type", forum.pk),
        {"to_type": Forum.LINK, "link_url": "https://shop.example.com/"},
    )

    assert resp.status_code == 200
    assert "topics_action" in resp.context["form"].errors
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM


def test_a_forum_becomes_a_link_once_its_topics_are_moved(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Palms", slug="palms")
    topic = _topic(forum, "a")

    resp = admin_client.post(
        _admin_url("change_type", forum.pk),
        {
            "to_type": Forum.LINK,
            "topics_action": "move",
            "target": target.pk,
            "link_url": "https://shop.example.com/",
            "track_clicks": "on",
        },
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    forum.refresh_from_db()
    topic.refresh_from_db()
    assert forum.forum_type == Forum.LINK
    assert forum.link_url == "https://shop.example.com/"
    assert (forum.topic_count, forum.post_count) == (0, 0)
    assert forum.parent_id == target.parent_id  # a link stays in its category
    assert topic.board_id == target.pk
    assert not Topic.objects.filter(board=forum).exists()


def test_becoming_a_link_needs_a_valid_url(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")

    for url in ("", "javascript:alert(1)"):
        resp = admin_client.post(
            _admin_url("change_type", forum.pk),
            {"to_type": Forum.LINK, "link_url": url},
        )
        assert resp.status_code == 200
        assert "link_url" in resp.context["form"].errors
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM


def test_a_category_with_forums_cannot_become_a_link(admin_client):
    category = make_category(name="Plants", slug="plants")
    other = make_category(name="Other", slug="other")
    make_forum(name="Ferns", slug="ferns", category=category)

    resp = admin_client.post(
        _admin_url("change_type", category.pk),
        {
            "to_type": Forum.LINK,
            "target_category": other.pk,
            "link_url": "https://shop.example.com/",
        },
    )

    assert resp.status_code == 200
    category.refresh_from_db()
    assert category.forum_type == Forum.CATEGORY


def test_an_empty_category_becomes_a_link_in_the_chosen_category(admin_client):
    category = make_category(name="Plants", slug="plants")
    other = make_category(name="Other", slug="other")

    resp = admin_client.post(
        _admin_url("change_type", category.pk),
        {
            "to_type": Forum.LINK,
            "target_category": other.pk,
            "link_url": "https://shop.example.com/",
        },
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    category.refresh_from_db()
    assert category.forum_type == Forum.LINK
    assert category.parent_id == other.pk
    assert category.link_url == "https://shop.example.com/"


@pytest.mark.parametrize("new_type", [Forum.FORUM, Forum.CATEGORY])
def test_a_link_changing_type_clears_its_url(admin_client, new_type):
    link = _link(track_clicks=True, click_count=12)

    resp = admin_client.post(_admin_url("change_type", link.pk), {"to_type": new_type})

    assert resp.status_code == 302, resp.content.decode()[:2000]
    link.refresh_from_db()
    assert link.forum_type == new_type
    assert link.link_url == ""
    assert link.click_count == 0
    if new_type == Forum.CATEGORY:
        assert link.parent is None
    else:
        assert link.parent is not None


def test_the_edit_page_of_a_link_offers_change_type(admin_client):
    link = _link()

    resp = admin_client.get(_admin_url("edit", link.pk))

    assert _admin_url("change_type", link.pk) in resp.content.decode()


def test_a_link_saved_without_a_url_can_still_be_moved():
    # Rows saved before todo 670 can be links with no URL. A tree move only
    # changes the parent, so it must not trip the "a link needs a URL" rule.
    from wagtail_forum.services.forum_structure import move_forum

    other = make_category(slug="elsewhere")
    legacy = _link(link_url="")

    moved = move_forum(legacy.pk, other.pk, 0)

    assert moved.parent_id == other.pk
    legacy.refresh_from_db()
    assert legacy.parent_id == other.pk
