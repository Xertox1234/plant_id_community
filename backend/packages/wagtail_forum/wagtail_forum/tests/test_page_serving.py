"""Audit 2026-07-11 H17: ForumIndex/ForumBoard are live-routable Pages; serving
them directly (admin "View live", sitemap entries, crawlers) must render the
minimal fallback template, not 500 with TemplateDoesNotExist. The SPA remains
the real forum UI."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

User = get_user_model()


def _tree():
    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title="Forum", slug="forum", intro="<p>Welcome</p>")
    )
    board = index.add_child(
        instance=ForumBoard(title="General", slug="general", description="General talk")
    )
    return index, board


@pytest.mark.django_db
def test_forum_index_serves_directly():
    index, _board = _tree()

    response = index.serve(RequestFactory().get("/forum/"))
    response.render()

    assert response.status_code == 200
    html = response.content.decode()
    assert "Forum" in html
    assert "General" in html  # child board listed


@pytest.mark.django_db
def test_forum_board_serves_directly_and_lists_only_live_topics():
    _index, board = _tree()
    Topic.objects.create(board=board, title="Visible topic", slug="v", live=True)
    Topic.objects.create(board=board, title="Hidden draft", slug="h", live=False)

    response = board.serve(RequestFactory().get("/forum/general/"))
    response.render()

    assert response.status_code == 200
    html = response.content.decode()
    assert "Visible topic" in html
    assert "Hidden draft" not in html


# Todo 299: the fallback pages share wagtail_forum/base.html, which renders
# {% wagtailuserbar %} so an editor landing on "View live" has a route back to
# the admin. The tag emits nothing for anonymous (or userless) requests, which
# is also why the two serve tests above keep passing with bare RequestFactory
# requests.


def _request_as(user, path):
    request = RequestFactory().get(path)
    request.user = user
    return request


@pytest.mark.django_db
@pytest.mark.parametrize(
    "page_picker", [lambda i, b: i, lambda i, b: b], ids=["index", "board"]
)
def test_userbar_renders_for_admin_user(page_picker):
    index, board = _tree()
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    page = page_picker(index, board)

    response = page.serve(_request_as(admin, "/forum/"))
    response.render()

    assert response.status_code == 200
    html = response.content.decode()
    assert "wagtail-userbar" in html
    # The wrapper shell renders even when the userbar can't resolve the page,
    # so also pin the actual "route back to the admin": the edit-page link.
    assert reverse("wagtailadmin_pages:edit", args=[page.pk]) in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "page_picker", [lambda i, b: i, lambda i, b: b], ids=["index", "board"]
)
def test_userbar_absent_for_anonymous_user(page_picker):
    index, board = _tree()

    response = page_picker(index, board).serve(_request_as(AnonymousUser(), "/forum/"))
    response.render()

    assert response.status_code == 200
    assert "wagtail-userbar" not in response.content.decode()
