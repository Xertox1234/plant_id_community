"""The forum *Permissions* screen (todo 675): a principal × role grid and
"copy permissions from", behind the Forum ``change`` permission."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from wagtail_forum.models import ForumGrant, ForumRole
from wagtail_forum.services.forum_permissions import set_grant
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = pytest.mark.django_db
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _url(forum):
    return reverse("wagtail_forum_forums:permissions", args=(forum.pk,))


def _staff(username, *codenames):
    user = User.objects.create_user(username=username)
    user.user_permissions.set(
        Permission.objects.filter(codename__in=["access_admin", *codenames])
    )
    return User.objects.get(pk=user.pk)


def _rows(forum):
    return set(
        ForumGrant.objects.filter(forum=forum).values_list("principal", "group", "role")
    )


def test_the_permissions_tab_requires_the_change_permission(client):
    forum = make_forum()
    client.force_login(_staff("viewer", "view_forum", "add_forum"))

    # The view's own refusal is the 403 an XHR sees; a browser request is
    # sent to the dashboard with Wagtail's "Sorry, ..." (test_forum_admin).
    assert client.get(_url(forum), **XHR).status_code == 403
    denied = client.post(_url(forum), {"members": ForumRole.NO_ACCESS})
    assert denied.status_code == 302
    assert denied["Location"] == reverse("wagtailadmin_home")
    assert not ForumGrant.objects.filter(forum=forum).exists()


def test_a_change_user_sees_the_grid_and_the_edit_page_links_to_it(client):
    forum = make_forum()
    Group.objects.create(name="Experts")
    client.force_login(_staff("editor", "change_forum"))

    resp = client.get(_url(forum))
    edit = client.get(reverse("wagtail_forum_forums:edit", args=(forum.pk,)))

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Guests" in body and "All members" in body and "Experts" in body
    assert _url(forum) in edit.content.decode()


def test_saving_the_grid_writes_one_row_per_chosen_role(client):
    forum = make_forum()
    experts = Group.objects.create(name="Experts")
    Group.objects.create(name="Lurkers")
    set_grant(forum, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    client.force_login(_staff("editor", "change_forum"))

    resp = client.post(
        _url(forum),
        {
            "action": "save",
            "anonymous": "",  # back to the default: the row goes
            "members": ForumRole.READ_ONLY,
            f"group_{experts.pk}": ForumRole.FULL,
        },
    )

    assert resp.status_code == 302
    assert _rows(forum) == {
        (ForumGrant.MEMBERS, None, ForumRole.READ_ONLY),
        (ForumGrant.GROUP, experts.pk, ForumRole.FULL),
    }


def test_copy_permissions_asks_first_then_overwrites_exactly(client):
    source = make_forum(name="Source", slug="source")
    target = make_forum(name="Target", slug="target")
    set_grant(source, ForumGrant.MEMBERS, ForumRole.LIMITED)
    set_grant(target, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    client.force_login(_staff("editor", "change_forum"))

    asked = client.post(_url(target), {"action": "copy", "source": source.pk})

    assert asked.status_code == 200
    assert "cannot be undone" in asked.content.decode()
    assert _rows(target) == {(ForumGrant.ANONYMOUS, None, ForumRole.NO_ACCESS)}

    done = client.post(
        _url(target), {"action": "copy", "source": source.pk, "confirm": "on"}
    )

    assert done.status_code == 302
    assert (
        _rows(target)
        == _rows(source)
        == {(ForumGrant.MEMBERS, None, ForumRole.LIMITED)}
    )
