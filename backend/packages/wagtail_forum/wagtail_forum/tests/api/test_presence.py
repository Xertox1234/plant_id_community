"""Throttled ForumProfile.last_seen touch on authenticated forum requests
(todo 301). Exercised via BoardListView (`GET boards/`) — it never touches
ForumProfile itself, so any last_seen write observed is unambiguously the
presence touch (api/presence.py), not a side effect of the view under test.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_presence_cache():
    """LocMemCache is process-global — stop the throttle key bleeding between
    tests (same convention as test_solutions.py's clear_idempotency_cache)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_touch_last_seen_writes_on_an_authenticated_request():
    user = User.objects.create_user(username="visitor")
    profile = ForumProfile.for_user(user)
    assert profile.last_seen is None  # sanity

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/boards/")

    assert resp.status_code == 200
    profile.refresh_from_db()
    assert profile.last_seen is not None


@pytest.mark.django_db
def test_touch_last_seen_skips_anonymous_requests():
    """No user, no write — and no ForumProfile row appears for anyone."""
    resp = APIClient().get("/forum/boards/")
    assert resp.status_code == 200
    assert not ForumProfile.objects.exists()


@pytest.mark.django_db
def test_touch_last_seen_skips_an_authenticated_user_with_no_profile_row():
    """`.filter().update()`, not `get_or_create()` — a user who has never
    triggered profile creation gets no write AND no row is created here."""
    user = User.objects.create_user(username="freshuser")
    assert not ForumProfile.objects.filter(user=user).exists()  # sanity

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/boards/")

    assert resp.status_code == 200
    assert not ForumProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_touch_last_seen_is_throttled_within_the_window():
    """Two rapid requests -> one write (todo 301 AC2).

    The default throttle (5 min) comfortably covers "rapid" — no need to
    override it. A sentinel last_seen proves the second request's touch was
    skipped rather than merely re-writing ~the same timestamp.
    """
    user = User.objects.create_user(username="visitor")
    profile = ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    resp1 = client.get("/forum/boards/")
    assert resp1.status_code == 200
    profile.refresh_from_db()
    first_touch = profile.last_seen
    assert first_touch is not None

    sentinel = first_touch - timedelta(hours=1)
    ForumProfile.objects.filter(user=user).update(last_seen=sentinel)

    resp2 = client.get("/forum/boards/")
    assert resp2.status_code == 200
    profile.refresh_from_db()
    # Still the sentinel — the second request's touch was throttled away,
    # not merely coincidentally close to the first.
    assert profile.last_seen == sentinel


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_PRESENCE_TOUCH_THROTTLE_SECONDS=0)
def test_touch_last_seen_writes_again_after_the_throttle_window_expires():
    """Mirrors test_view_count_recounts_after_dedup_window_expires's TTL=0
    technique (test_topic_detail.py): an instantly-expiring throttle proves
    the gate is a real window, not a permanent one-write-ever latch."""
    user = User.objects.create_user(username="visitor")
    profile = ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    client.get("/forum/boards/")
    profile.refresh_from_db()
    first_touch = profile.last_seen
    assert first_touch is not None

    sentinel = first_touch - timedelta(hours=1)
    ForumProfile.objects.filter(user=user).update(last_seen=sentinel)

    client.get("/forum/boards/")
    profile.refresh_from_db()
    assert profile.last_seen != sentinel


@pytest.mark.django_db
def test_touch_last_seen_fails_open_on_a_db_error():
    """A DB error on the presence write (contention, transient blip) must
    not 500 an otherwise-successful request (code review finding #1) — this
    mixin composes into every forum view, so an unguarded write would put
    incidental telemetry in the failure path of the whole API surface."""
    user = User.objects.create_user(username="visitor")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    with patch(
        "wagtail_forum.models.ForumProfile.objects.filter",
        side_effect=Exception("boom"),
    ):
        resp = client.get("/forum/boards/")

    assert resp.status_code == 200
