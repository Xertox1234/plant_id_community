"""The host throttles on the forum-row endpoints (todos 670, 671, 673): the
link redirect is limited per IP, because every request is a counted click,
and the read marks and collapse save each have their own scope."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail_forum.models import Forum
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _member():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="ada", email="a@x.io"))
    return client


@override_settings(FORUM_RATELIMITS={"link_go": "1/m"})
def test_the_link_redirect_is_throttled_per_ip_and_stops_counting():
    link = Forum.objects.create(
        forum_type=Forum.LINK,
        parent=make_category(),
        name="Shop",
        slug="shop",
        link_url="https://shop.example.com/",
        track_clicks=True,
    )
    url = f"/api/v1/forum/links/{link.pk}/go/"

    with freeze_time("2026-10-30 12:00:00"):
        first = APIClient().get(url)
        second = APIClient().get(url)

    assert first.status_code == 302
    assert second.status_code == 429
    link.refresh_from_db()
    assert link.click_count == 1


@override_settings(FORUM_RATELIMITS={"forum_mark_read": "1/m"})
def test_marking_a_forum_read_is_throttled():
    board = make_forum()
    client = _member()
    url = f"/api/v1/forum/boards/{board.slug}/read/"

    with freeze_time("2026-10-30 12:00:00"):
        assert client.post(url).status_code < 400
        assert client.post(url).status_code == 429


@override_settings(FORUM_RATELIMITS={"forum_mark_all_read": "1/m"})
def test_marking_everything_read_is_throttled():
    client = _member()
    url = "/api/v1/forum/read-all/"

    with freeze_time("2026-10-30 12:00:00"):
        assert client.post(url).status_code < 400
        assert client.post(url).status_code == 429


@override_settings(FORUM_RATELIMITS={"collapsed_categories_update": "1/m"})
def test_the_collapse_save_is_throttled_on_its_own_scope():
    client = _member()
    url = "/api/v1/forum/me/collapsed-categories/"
    body = {"collapsed_categories": [1]}

    with freeze_time("2026-10-30 12:00:00"):
        assert client.put(url, body, format="json").status_code == 200
        assert client.put(url, body, format="json").status_code == 429
