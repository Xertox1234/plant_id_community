"""Anonymous topic views are counted per real client, not per proxy (todo
730, audit 2026-11-21 L15).

Behind Cloudflare and Railway ``REMOTE_ADDR`` is the proxy's address. The
host points the forum's ``WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER`` at the rate
limiter's trusted resolver, so the view-count dedup follows the same rule as
every per-IP limit.
"""

import pytest
from apps.core import ratelimit
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from rest_framework.test import APIClient
from wagtail_forum.models import Topic
from wagtail_forum.tests.factories import make_forum

PROXY = "10.0.0.7"


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _read(topic, forwarded):
    return APIClient().get(
        f"/api/v1/forum/topics/{topic.id}/",
        REMOTE_ADDR=PROXY,
        HTTP_X_FORWARDED_FOR=forwarded,
    )


def test_the_forum_dedup_uses_the_rate_limiters_resolver():
    assert (
        settings.WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER
        == "apps.core.ratelimit.request_client_id"
    )
    request = RequestFactory().get(
        "/", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR="203.0.113.10"
    )
    with override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1):
        assert ratelimit.request_client_id(request) == "203.0.113.10"
        assert ratelimit.request_client_id(request) == ratelimit.client_ip_key(
            None, request
        )


@pytest.mark.django_db
@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1, RATELIMIT_CLIENT_IP_HEADER="")
def test_two_anonymous_readers_with_different_ips_behind_one_proxy_both_count(
    django_capture_on_commit_callbacks,
):
    board = make_forum(name="General", slug="vc-host-board")
    topic = Topic.objects.create(board=board, title="VC", slug="vc-host", live=True)

    with django_capture_on_commit_callbacks(execute=True):
        assert _read(topic, "203.0.113.10").status_code == 200
        assert _read(topic, "203.0.113.20").status_code == 200
        # The first reader again, inside the window: not a third view.
        assert _read(topic, "203.0.113.10").status_code == 200
        # A forged left-hand entry cannot mint a new viewer: the trusted
        # position is counted from the right.
        assert _read(topic, "198.51.100.99, 203.0.113.20").status_code == 200

    topic.refresh_from_db()
    assert topic.view_count == 2
