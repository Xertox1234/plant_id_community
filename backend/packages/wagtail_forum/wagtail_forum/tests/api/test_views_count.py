"""Who an anonymous topic view belongs to (todo 730, audit 2026-11-21 L15).

The view-count dedup key for an anonymous reader was raw ``REMOTE_ADDR``.
Behind a reverse proxy that is the proxy's address, so every anonymous reader
shared one key and a topic gained one view per dedup window, whoever read it.
The host now names its trusted client-address resolver in
``WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER``; the package never reads forwarding
headers itself. The host's own resolver is covered in
``apps/forum_host/tests/test_view_count_client_ip.py``.
"""

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail_forum.models import Topic
from wagtail_forum.tests.factories import make_forum

pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

HERE = "wagtail_forum.tests.api.test_views_count"
PROXY = "10.0.0.7"  # the one address every request arrives from


def forwarded_client(request):
    """A stand-in for a host's resolver: the proxy-appended client address."""
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()


def broken_resolver(request):
    raise RuntimeError("resolver bug")


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _topic(slug):
    board = make_forum(name="General", slug=f"{slug}-board")
    return Topic.objects.create(board=board, title="VC", slug=slug, live=True)


def _read(topic, client_ip):
    return APIClient().get(
        f"/forum/topics/{topic.id}/",
        REMOTE_ADDR=PROXY,
        HTTP_X_FORWARDED_FOR=client_ip,
    )


def _views(topic):
    topic.refresh_from_db()
    return topic.view_count


@override_settings(WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER=f"{HERE}.forwarded_client")
def test_two_anonymous_readers_behind_one_proxy_both_count(
    django_capture_on_commit_callbacks,
):
    topic = _topic("vc-two")

    with django_capture_on_commit_callbacks(execute=True):
        assert _read(topic, "203.0.113.10").status_code == 200
        assert _read(topic, "203.0.113.20").status_code == 200

    assert _views(topic) == 2


@override_settings(WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER=f"{HERE}.forwarded_client")
def test_one_anonymous_reader_is_still_counted_once_per_window(
    django_capture_on_commit_callbacks,
):
    topic = _topic("vc-same")

    with django_capture_on_commit_callbacks(execute=True):
        _read(topic, "203.0.113.10")
        _read(topic, "203.0.113.10")

    assert _views(topic) == 1


def test_without_a_host_resolver_the_key_is_remote_addr(
    django_capture_on_commit_callbacks,
):
    """The package default: right with no proxy in front, and the undercount
    this todo fixed when there is one. It never trusts a forwarding header on
    its own."""
    topic = _topic("vc-default")

    with django_capture_on_commit_callbacks(execute=True):
        _read(topic, "203.0.113.10")
        _read(topic, "203.0.113.20")

    assert _views(topic) == 1


@override_settings(WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER=f"{HERE}.broken_resolver")
def test_a_resolver_that_raises_falls_back_and_never_fails_the_read(
    django_capture_on_commit_callbacks,
):
    topic = _topic("vc-broken")

    with django_capture_on_commit_callbacks(execute=True):
        assert _read(topic, "203.0.113.10").status_code == 200
        assert _read(topic, "203.0.113.20").status_code == 200

    assert _views(topic) == 1  # REMOTE_ADDR again: counted, once


@override_settings(WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER=f"{HERE}.forwarded_client")
def test_the_dedup_key_holds_no_raw_client_address():
    """Review round 2 (todo 730): the resolver's answer is the reader's real
    address, so it is hashed before it becomes a cache key next to a topic."""
    from django.test import RequestFactory
    from wagtail_forum.api.views import _anonymous_viewer_key

    def key(address):
        request = RequestFactory().get(
            "/", REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=address
        )
        return _anonymous_viewer_key(request)

    first = key("203.0.113.10")
    assert "203.0.113.10" not in first
    assert first == key("203.0.113.10")
    assert first != key("203.0.113.20")
