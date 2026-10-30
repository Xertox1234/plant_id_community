"""The forum structure tree (todo 668): the *Categories & forums* landing
screen and its one move endpoint, for drag and drop and the move buttons."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from wagtail_forum.models import Forum
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()

NS = "wagtail_forum_forums"
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

pytestmark = pytest.mark.django_db


def _url(name, *args):
    return reverse(f"{NS}:{name}", args=args)


def _staff(username, *codenames):
    user = User.objects.create_user(username=username, email=f"{username}@x.io")
    user.user_permissions.set(
        Permission.objects.filter(codename__in=["access_admin", *codenames])
    )
    return User.objects.get(pk=user.pk)


@pytest.fixture
def admin_client(client):
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))
    return client


@pytest.fixture
def structure():
    """Two categories and three forums, with GAPPED positions (0, 5, 9), so
    a passing test proves the move renumbers rather than keeps them."""
    indoor = make_category(name="Indoor", slug="indoor", position=0)
    outdoor = make_category(name="Outdoor", slug="outdoor", position=5)
    ferns = make_forum(name="Ferns", slug="ferns", category=indoor, position=0)
    cacti = make_forum(name="Cacti", slug="cacti", category=indoor, position=5)
    palms = make_forum(name="Palms", slug="palms", category=indoor, position=9)
    roses = make_forum(name="Roses", slug="roses", category=outdoor, position=3)
    return {
        "indoor": indoor,
        "outdoor": outdoor,
        "ferns": ferns,
        "cacti": cacti,
        "palms": palms,
        "roses": roses,
    }


def _move(client, row, parent, position, **extra):
    return client.post(
        _url("move"),
        {
            "forum_id": row.pk,
            "parent_id": "" if parent is None else parent.pk,
            "position": position,
        },
        **extra,
    )


def _level(parent):
    """[(name, position)] of one level in display order."""
    rows = Forum.objects.filter(parent=parent)
    if parent is None:
        rows = rows.filter(forum_type=Forum.CATEGORY)
    return list(rows.order_by("position", "pk").values_list("name", "position"))


def _contiguous(parent):
    positions = [position for _name, position in _level(parent)]
    return positions == list(range(len(positions)))


def _snapshot():
    return sorted(Forum.objects.values_list("pk", "parent_id", "position"))


# --- the tree is the landing screen ---


def test_the_index_is_the_structure_tree(admin_client, structure):
    resp = admin_client.get(_url("index"))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'id="wf-structure"' in html
    assert f'data-move-url="{_url("move")}"' in html
    assert "wagtail_forum/js/vendor/Sortable.min.js" in html
    assert "wagtail_forum/js/forum-structure.js" in html
    # Categories in position order, each forum under its own category.
    shown = ["indoor", "ferns", "cacti", "palms", "outdoor", "roses"]
    order = [html.index(f'id="forum-row-{structure[k].pk}"') for k in shown]
    assert order == sorted(order)
    # Row actions: edit, add forum, delete.
    indoor = structure["indoor"]
    assert _url("edit", indoor.pk) in html
    assert _url("delete", indoor.pk) in html
    assert f"{_url('add')}?forum_type=forum&amp;parent={indoor.pk}" in html


def test_view_only_staff_see_the_tree_without_move_controls(client, structure):
    client.force_login(_staff("viewer", "view_forum"))

    html = client.get(_url("index")).content.decode()

    assert 'data-can-change="false"' in html
    assert "wf-structure__handle" not in html
    assert 'data-move="up"' not in html
    assert "Sortable.min.js" not in html


def test_add_forum_link_prefills_the_category(admin_client, structure):
    indoor = structure["indoor"]

    resp = admin_client.get(f"{_url('add')}?forum_type=forum&parent={indoor.pk}")

    assert resp.status_code == 200
    form = resp.context["form"]
    assert form["forum_type"].value() == Forum.FORUM
    assert str(form["parent"].value()) == str(indoor.pk)


@pytest.mark.parametrize("parent", ["²", "abc", "-1"])
def test_add_forum_ignores_a_malformed_parent(admin_client, structure, parent):
    # "²".isdigit() is True but int("²") raises, so isdigit() is not enough.
    resp = admin_client.get(_url("add"), {"forum_type": "forum", "parent": parent})

    assert resp.status_code == 200
    assert resp.context["form"]["parent"].value() is None


# --- AC0: each of the three moves persists, positions contiguous per parent ---


def test_reordering_categories_persists_and_renumbers(admin_client, structure):
    resp = _move(admin_client, structure["outdoor"], None, 0, **XHR)

    assert resp.status_code == 200, resp.content
    assert resp.json()["position"] == 0
    assert _level(None) == [("Outdoor", 0), ("Indoor", 1)]
    assert _contiguous(None)


def test_reordering_forums_within_a_category_persists(admin_client, structure):
    indoor = structure["indoor"]

    resp = _move(admin_client, structure["palms"], indoor, 0, **XHR)

    assert resp.status_code == 200, resp.content
    assert _level(indoor) == [("Palms", 0), ("Ferns", 1), ("Cacti", 2)]
    assert _contiguous(indoor)


def test_moving_a_forum_to_another_category_persists(admin_client, structure):
    indoor, outdoor = structure["indoor"], structure["outdoor"]

    resp = _move(admin_client, structure["cacti"], outdoor, 0, **XHR)

    assert resp.status_code == 200, resp.content
    structure["cacti"].refresh_from_db()
    assert structure["cacti"].parent_id == outdoor.pk
    assert _level(outdoor) == [("Cacti", 0), ("Roses", 1)]
    assert _level(indoor) == [("Ferns", 0), ("Palms", 1)]
    assert _contiguous(outdoor) and _contiguous(indoor)


def test_a_position_past_the_end_means_last(admin_client, structure):
    indoor = structure["indoor"]

    resp = _move(admin_client, structure["ferns"], indoor, 99, **XHR)

    assert resp.status_code == 200, resp.content
    assert _level(indoor) == [("Cacti", 0), ("Palms", 1), ("Ferns", 2)]


def test_move_button_without_javascript_redirects_to_the_tree(admin_client, structure):
    """The keyboard alternative posts the same form without JavaScript: a
    blank position ("move to category") goes to the end of the category."""
    outdoor = structure["outdoor"]

    resp = admin_client.post(
        _url("move"), {"forum_id": structure["ferns"].pk, "parent_id": outdoor.pk}
    )

    assert resp.status_code == 302
    assert resp["Location"] == f"{_url('index')}#forum-row-{structure['ferns'].pk}"
    assert _level(outdoor) == [("Roses", 0), ("Ferns", 1)]
    assert _contiguous(structure["indoor"])


def test_the_tree_renders_move_buttons_with_the_positions(admin_client, structure):
    html = admin_client.get(_url("index")).content.decode()

    assert 'data-move="up"' in html
    assert 'data-move="down"' in html
    assert 'data-move="to"' in html


def test_the_move_buttons_post_without_javascript(structure):
    """The up/down forms are the no-JS path, so each must carry its own CSRF
    token; one posted as the browser would, CSRF enforced, moves the row."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))
    html = client.get(_url("index")).content.decode()

    forms = re.findall(
        r'<form[^>]*data-move="(?:up|down)"[^>]*>(.*?)</form>', html, re.S
    )
    assert forms
    assert all('name="csrfmiddlewaretoken"' in f for f in forms)

    ferns = structure["ferns"].pk
    down = next(
        f for f in forms if f'name="forum_id" value="{ferns}"' in f and "down" in f
    )
    fields = dict(
        re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', down)
    )
    resp = client.post(_url("move"), fields)

    assert resp.status_code == 302
    assert _level(structure["indoor"]) == [("Cacti", 0), ("Ferns", 1), ("Palms", 2)]


def test_leaving_a_hidden_category_for_a_visible_one_hides_the_forum(
    admin_client, structure
):
    indoor = structure["indoor"]
    indoor.is_hidden = True
    indoor.save()

    resp = _move(admin_client, structure["ferns"], structure["outdoor"], 0, **XHR)

    assert resp.status_code == 200, resp.content
    assert resp.json()["is_hidden"] is True
    structure["ferns"].refresh_from_db()
    assert structure["ferns"].is_hidden is True


def test_moving_between_visible_categories_keeps_the_forum_visible(
    admin_client, structure
):
    resp = _move(admin_client, structure["ferns"], structure["outdoor"], 0, **XHR)

    assert resp.status_code == 200, resp.content
    structure["ferns"].refresh_from_db()
    assert structure["ferns"].is_hidden is False


# --- AC1: illegal drops are refused and change nothing ---


@pytest.fixture
def link(structure):
    return Forum.objects.create(
        forum_type=Forum.LINK,
        parent=structure["indoor"],
        name="Shop",
        slug="shop",
        position=10,
    )


def _assert_refused(client, row, parent, position=0):
    before = _snapshot()
    resp = _move(client, row, parent, position, **XHR)
    assert resp.status_code == 400, resp.content
    assert resp.json()["message"]
    assert _snapshot() == before
    return resp


def test_a_category_cannot_be_dropped_into_a_category(admin_client, structure):
    resp = _assert_refused(admin_client, structure["outdoor"], structure["indoor"])
    assert "category cannot have a parent" in resp.json()["message"]


def test_a_forum_cannot_be_dropped_at_the_root(admin_client, structure):
    resp = _assert_refused(admin_client, structure["ferns"], None)
    assert "must belong to a category" in resp.json()["message"]


def test_nothing_can_be_dropped_under_a_forum(admin_client, structure):
    _assert_refused(admin_client, structure["ferns"], structure["cacti"])
    _assert_refused(admin_client, structure["indoor"], structure["cacti"])


def test_nothing_can_be_dropped_under_a_link(admin_client, structure, link):
    _assert_refused(admin_client, structure["ferns"], link)
    _assert_refused(admin_client, structure["indoor"], link)


def test_a_row_cannot_be_dropped_into_itself(admin_client, structure):
    _assert_refused(admin_client, structure["indoor"], structure["indoor"])


def test_a_refused_move_without_javascript_redirects_with_the_message(
    admin_client, structure
):
    before = _snapshot()

    resp = admin_client.post(
        _url("move"),
        {"forum_id": structure["ferns"].pk, "parent_id": "", "position": 0},
        follow=True,
    )

    assert resp.redirect_chain[-1][0] == _url("index")
    assert "must belong to a category" in resp.content.decode()
    assert _snapshot() == before


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"forum_id": "x", "parent_id": "", "position": 0},
        {"forum_id": 1, "parent_id": "abc", "position": 0},
        {"forum_id": 1, "parent_id": "", "position": "-1"},
    ],
)
def test_a_malformed_move_is_a_400(admin_client, structure, data):
    if data.get("forum_id") == 1:
        data = {**data, "forum_id": structure["indoor"].pk}
    before = _snapshot()

    resp = admin_client.post(_url("move"), data, **XHR)

    assert resp.status_code == 400
    assert _snapshot() == before


def test_a_missing_row_or_parent_is_refused(admin_client, structure):
    resp = admin_client.post(
        _url("move"), {"forum_id": 999999, "parent_id": "", "position": 0}, **XHR
    )
    assert resp.status_code == 404

    resp = admin_client.post(
        _url("move"),
        {"forum_id": structure["ferns"].pk, "parent_id": 999999, "position": 0},
        **XHR,
    )
    assert resp.status_code == 400


# --- AC2: the change permission and a CSRF token ---


@pytest.mark.parametrize(
    "codenames", [(), ("view_forum",), ("add_forum", "delete_forum")]
)
def test_moving_needs_the_change_permission(client, structure, codenames):
    client.force_login(_staff("staff", *codenames))
    before = _snapshot()

    resp = _move(client, structure["outdoor"], None, 0, **XHR)

    assert resp.status_code == 403
    assert _snapshot() == before


def test_an_anonymous_move_is_sent_to_the_login_page(client, structure):
    before = _snapshot()

    resp = _move(client, structure["outdoor"], None, 0)

    assert resp.status_code == 302
    assert "/login/" in resp["Location"]
    assert _snapshot() == before


def test_change_permission_alone_may_move(client, structure):
    client.force_login(_staff("arranger", "change_forum"))

    resp = _move(client, structure["outdoor"], None, 0, **XHR)

    assert resp.status_code == 200, resp.content
    assert _level(None) == [("Outdoor", 0), ("Indoor", 1)]


def test_moving_needs_a_csrf_token(structure):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(
        User.objects.create_superuser(username="root", email="r@x.io")
    )
    before = _snapshot()

    resp = _move(csrf_client, structure["outdoor"], None, 0, **XHR)

    assert resp.status_code == 403
    assert _snapshot() == before

    # The session's CSRF cookie token is accepted.
    csrf_client.get(_url("index"))
    token = csrf_client.cookies["csrftoken"].value
    resp = _move(
        csrf_client, structure["outdoor"], None, 0, HTTP_X_CSRFTOKEN=token, **XHR
    )

    assert resp.status_code == 200, resp.content
    assert _level(None) == [("Outdoor", 0), ("Indoor", 1)]


def test_moving_is_post_only(admin_client, structure):
    assert admin_client.get(_url("move"), **XHR).status_code == 405
