"""The Forum create/edit admin (todo 666): a ModelViewSet for categories and
forums under the Wagtail *Forum* menu (delete and type changes: todo 667)."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from wagtail_forum.models import Forum
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()

NS = "wagtail_forum_forums"


def _url(name, *args):
    return reverse(f"{NS}:{name}", args=args)


def _staff(username, *codenames):
    """An admin-entering user holding exactly ``codenames`` on Forum."""
    user = User.objects.create_user(username=username, email=f"{username}@x.io")
    perms = ["access_admin", *codenames]
    user.user_permissions.set(Permission.objects.filter(codename__in=perms))
    return User.objects.get(pk=user.pk)  # drop the permission cache


def _payload(**overrides):
    data = {
        "forum_type": Forum.FORUM,
        "parent": "",
        "name": "Succulents",
        "slug": "succulents",
        "description": "Cacti and friends",
    }
    data.update(overrides)
    return data


# --- AC0: menu + create for staff with the model permissions; 403 without ---


@pytest.mark.django_db
def test_staff_with_forum_permissions_sees_the_forum_menu_entry(client):
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.get(reverse("wagtailadmin_home"))

    assert resp.status_code == 200
    assert _url("index") in resp.content.decode()


@pytest.mark.django_db
def test_staff_without_forum_permissions_does_not_see_the_menu_entry(client):
    client.force_login(_staff("nobody"))

    resp = client.get(reverse("wagtailadmin_home"))

    assert resp.status_code == 200
    assert _url("index") not in resp.content.decode()


@pytest.mark.django_db
def test_staff_with_forum_permissions_creates_a_category_and_a_forum(client):
    client.force_login(_staff("editor", "add_forum", "change_forum"))
    assert client.get(_url("index")).status_code == 200
    assert client.get(_url("add")).status_code == 200

    resp = client.post(
        _url("add"),
        _payload(forum_type=Forum.CATEGORY, name="Outdoor", slug="outdoor"),
    )
    assert resp.status_code == 302, resp.content.decode()[:2000]
    category = Forum.objects.get(slug="outdoor")
    assert category.forum_type == Forum.CATEGORY
    assert category.parent is None

    resp = client.post(_url("add"), _payload(parent=category.pk))
    assert resp.status_code == 302, resp.content.decode()[:2000]
    forum = Forum.objects.get(slug="succulents")
    assert forum.forum_type == Forum.FORUM
    assert forum.parent == category
    assert forum.description == "Cacti and friends"


# Wagtail's admin raises PermissionDenied (403) in the view; for a browser
# request its `require_admin_access` wrapper turns that into a redirect to the
# dashboard with "Sorry, you do not have permission" (wagtail.admin.auth
# permission_denied), and only an XHR request sees the bare 403. Both halves
# are asserted: the 403 is the view's own refusal, the redirect is what a
# person in the browser gets.
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _assert_denied(client, method, url, data=None):
    send = getattr(client, method)
    assert send(url, data or {}, **XHR).status_code == 403
    resp = send(url, data or {})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("wagtailadmin_home")
    page = client.get(resp["Location"]).content.decode()
    assert "Sorry, you do not have permission to access this area." in page


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["index", "add"])
def test_staff_without_forum_permissions_gets_403(client, view):
    client.force_login(_staff("nobody"))

    _assert_denied(client, "get", _url(view))


@pytest.mark.django_db
def test_staff_without_forum_permissions_cannot_post_a_new_forum(client):
    category = make_category()
    client.force_login(_staff("nobody"))

    _assert_denied(client, "post", _url("add"), _payload(parent=category.pk))

    assert not Forum.objects.filter(slug="succulents").exists()


@pytest.mark.django_db
def test_staff_without_change_permission_gets_403_on_edit(client):
    forum = make_forum(name="Ferns", slug="ferns")
    client.force_login(_staff("adder", "add_forum"))

    _assert_denied(
        client,
        "post",
        _url("edit", forum.pk),
        _payload(parent=forum.parent_id, name="Hijacked", slug="ferns"),
    )

    forum.refresh_from_db()
    assert forum.name == "Ferns"


# --- AC1: server-side type/parent validation ---


@pytest.mark.django_db
def test_form_rejects_a_forum_without_a_category(client):
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(_url("add"), _payload(parent=""))

    assert resp.status_code == 200
    assert "parent" in resp.context["form"].errors
    assert not Forum.objects.filter(slug="succulents").exists()


@pytest.mark.django_db
def test_form_rejects_a_category_with_a_parent(client):
    other = make_category()
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("add"),
        _payload(
            forum_type=Forum.CATEGORY, name="Outdoor", slug="outdoor", parent=other.pk
        ),
    )

    assert resp.status_code == 200
    assert "parent" in resp.context["form"].errors
    assert not Forum.objects.filter(slug="outdoor").exists()


@pytest.mark.django_db
def test_form_rejects_a_link_type_in_this_slice(client):
    category = make_category()
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(_url("add"), _payload(forum_type=Forum.LINK, parent=category.pk))

    assert resp.status_code == 200
    assert "forum_type" in resp.context["form"].errors
    assert not Forum.objects.filter(slug="succulents").exists()


@pytest.mark.django_db
def test_form_rejects_a_duplicate_forum_slug_as_a_field_error(client):
    existing = make_forum(name="Ferns", slug="ferns")
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("add"), _payload(name="Ferns 2", slug="ferns", parent=existing.parent_id)
    )

    assert resp.status_code == 200
    assert resp.context["form"].errors["slug"] == ["This slug is already in use."]
    assert Forum.objects.filter(slug="ferns").count() == 1


@pytest.mark.django_db
def test_form_rejects_a_duplicate_category_slug_but_not_a_forum_of_the_same_slug(
    client,
):
    category = Forum.objects.create(
        forum_type=Forum.CATEGORY, name="Outdoor", slug="outdoor"
    )
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    dup = client.post(
        _url("add"),
        _payload(forum_type=Forum.CATEGORY, name="Outdoor 2", slug="outdoor"),
    )
    ok = client.post(_url("add"), _payload(slug="outdoor", parent=category.pk))

    assert dup.status_code == 200
    assert dup.context["form"].errors["slug"] == ["This slug is already in use."]
    assert ok.status_code == 302
    assert Forum.objects.filter(slug="outdoor").count() == 2


@pytest.mark.django_db
def test_form_rejects_a_forum_slug_already_used_by_a_link(client):
    category = make_category()
    Forum.objects.create(
        forum_type=Forum.LINK, parent=category, name="Shop", slug="shop"
    )
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(_url("add"), _payload(slug="shop", parent=category.pk))

    assert resp.status_code == 200
    assert resp.context["form"].errors["slug"] == ["This slug is already in use."]


@pytest.mark.django_db
def test_editing_a_row_keeps_its_own_slug(client):
    forum = make_forum(name="Ferns", slug="ferns")
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("edit", forum.pk),
        _payload(parent=forum.parent_id, name="Ferns!", slug="ferns"),
    )

    assert resp.status_code == 302


@pytest.mark.django_db
def test_type_is_read_only_on_edit(client):
    forum = make_forum(name="Ferns", slug="ferns")
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("edit", forum.pk),
        _payload(forum_type=Forum.CATEGORY, parent="", name="Ferns!", slug="ferns"),
    )

    # The disabled type field ignores the posted value: the row stays a
    # forum, and an emptied parent is still refused for a forum.
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM
    assert resp.status_code == 200
    assert "parent" in resp.context["form"].errors

    resp = client.post(
        _url("edit", forum.pk),
        _payload(
            forum_type=Forum.CATEGORY,
            parent=forum.parent_id,
            name="Ferns!",
            slug="ferns",
        ),
    )
    assert resp.status_code == 302
    forum.refresh_from_db()
    assert forum.forum_type == Forum.FORUM
    assert forum.name == "Ferns!"


@pytest.mark.django_db
def test_editing_a_category_ignores_a_posted_parent(client):
    category = make_category()
    other = Forum.objects.create(forum_type=Forum.CATEGORY, name="Other", slug="other")
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("edit", category.pk),
        _payload(
            forum_type=Forum.CATEGORY,
            parent=other.pk,
            name="Renamed",
            slug=category.slug,
        ),
    )

    assert resp.status_code == 302
    category.refresh_from_db()
    assert category.parent is None
    assert category.name == "Renamed"


@pytest.mark.django_db
def test_create_form_offers_only_category_and_forum_and_wires_the_parent_rule(client):
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.get(_url("add"))

    choices = [value for value, _ in resp.context["form"].fields["forum_type"].choices]
    assert choices == [Forum.CATEGORY, Forum.FORUM]
    html = resp.content.decode()
    assert 'data-controller="w-rules"' in html
    assert 'data-w-rules-show-match="not"' in html
    # The picker is also disabled (not just hidden) for a category, so a
    # value picked before switching the type is not posted.
    parent_attrs = resp.context["form"].fields["parent"].widget.attrs
    assert parent_attrs["data-w-rules-target"] == "enable"
    assert parent_attrs["data-w-rules-enable-match"] == "not"
    assert json.loads(parent_attrs["data-w-rules-enable"]) == {
        "forum_type": [Forum.CATEGORY]
    }
    assert 'data-w-rules-target="enable"' in html


@pytest.mark.django_db
def test_new_rows_go_to_the_end_of_their_level_and_blank_slug_is_derived(client):
    category = make_category()
    make_forum(name="Ferns", slug="ferns", category=category, position=4)
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("add"), _payload(name="Air Plants", slug="", parent=category.pk)
    )

    assert resp.status_code == 302
    forum = Forum.objects.get(slug="air-plants")
    assert forum.position == 5


@pytest.mark.django_db
def test_a_new_category_goes_after_the_last_category(client):
    category = make_category()
    Forum.objects.filter(pk=category.pk).update(position=7)
    # A forum's higher position must not count: categories rank among
    # categories only.
    make_forum(name="Ferns", slug="ferns", category=category, position=20)
    client.force_login(_staff("editor", "add_forum", "change_forum"))

    resp = client.post(
        _url("add"),
        _payload(forum_type=Forum.CATEGORY, name="Outdoor", slug="outdoor"),
    )

    assert resp.status_code == 302
    assert Forum.objects.get(slug="outdoor").position == 8


# --- AC2 (todo 666) superseded by todo 667: delete is now the safe-delete
# flow (tests/test_admin_forum_delete.py), so the route exists and the edit
# page links it. These pin only the wiring. ---


@pytest.mark.django_db
def test_delete_url_is_routed_to_the_safe_delete_view(client):
    forum = make_forum(name="Ferns", slug="ferns")
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))

    edit = client.get(_url("edit", forum.pk))
    confirm = client.get(_url("delete", forum.pk))

    assert edit.status_code == 200
    assert _url("delete", forum.pk) in edit.content.decode()
    assert confirm.status_code == 200
    assert confirm.context["form"].__class__.__name__ == "ForumDeleteForm"


# --- AC3 (API half): a forum created in the admin is on the index at once ---


@pytest.mark.django_db
def test_admin_created_forum_appears_on_the_web_index_endpoint(client):
    client.force_login(_staff("editor", "add_forum", "change_forum"))
    client.post(
        _url("add"),
        _payload(forum_type=Forum.CATEGORY, name="Outdoor", slug="outdoor"),
    )
    category = Forum.objects.get(slug="outdoor")
    client.post(_url("add"), _payload(parent=category.pk))
    client.logout()

    resp = client.get("/api/v1/forum/categories/")

    assert resp.status_code == 200
    rows = {row["slug"]: row for row in resp.json()["results"]}
    assert [f["slug"] for f in rows["outdoor"]["forums"]] == ["succulents"]
