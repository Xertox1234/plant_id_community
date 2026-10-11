import time
import unittest
from unittest.mock import ANY, patch

import pytest
from apps.forum_host import constants
from apps.forum_host.link_preview import (
    InvalidPreviewURL,
    _fetch_html,
    _FetchFailed,
    _LookupTimedOut,
    _open_connection,
    _read_document,
    _request_path,
    _Target,
    fetch_link_preview,
    normalize_public_url,
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_preview_cache():
    cache.clear()
    yield
    cache.clear()


def test_fetch_link_preview_extracts_open_graph_metadata_and_caches_result():
    url = "https://93.184.216.34/plants"
    body = b"""
    <html><head>
      <title>Fallback title</title>
      <meta property="og:title" content="Plant guide &amp; care">
      <meta property="og:description" content="A useful guide for growers.">
      <meta property="og:site_name" content="Plant Library">
      <meta property="og:image" content="/images/guide.jpg">
    </head></html>
    """
    with patch(
        "apps.forum_host.link_preview._fetch_html",
        return_value=(url, body),
    ) as fetch:
        result = fetch_link_preview(url)
        cached = fetch_link_preview(url)

    expected = {
        "url": url,
        "title": "Plant guide & care",
        "description": "A useful guide for growers.",
        "image_url": "https://93.184.216.34/images/guide.jpg",
        "site_name": "Plant Library",
        "domain": "93.184.216.34",
        "available": True,
    }
    assert result == expected
    assert cached == expected
    fetch.assert_called_once_with(
        _Target(url, "https", "93.184.216.34", 443, "93.184.216.34"), ANY
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.4/",
        "http://169.254.169.254/latest/",
        "http://[::1]/",
        "https://93.184.216.34:8443/",
        "http://93.184.216.34:22/",
        "ftp://93.184.216.34/file",
        "https://user:pass@93.184.216.34/",  # pragma: allowlist secret
    ],
)
def test_normalize_public_url_rejects_non_public_targets(url):
    with pytest.raises(InvalidPreviewURL):
        normalize_public_url(url)


def test_normalize_public_url_rejects_hostname_with_any_private_dns_answer():
    infos = [
        (2, 1, 6, "", ("93.184.216.34", 0)),
        (2, 1, 6, "", ("192.168.1.10", 0)),
    ]
    with patch("apps.forum_host.link_preview.socket.getaddrinfo", return_value=infos):
        with pytest.raises(InvalidPreviewURL):
            normalize_public_url("https://example.com/page")


def test_normalize_public_url_times_out_slow_dns_resolution():
    def slow_getaddrinfo(*args, **kwargs):
        time.sleep(0.2)
        return []

    with (
        patch(
            "apps.forum_host.link_preview.socket.getaddrinfo",
            side_effect=slow_getaddrinfo,
        ),
        patch(
            "apps.forum_host.constants.LINK_PREVIEW_DNS_TIMEOUT_SECONDS",
            0.01,
        ),
    ):
        started = time.monotonic()
        with pytest.raises(InvalidPreviewURL):
            normalize_public_url("https://example.com/page")

    assert time.monotonic() - started < 0.15


def test_539_item5_only_a_lookup_that_ran_out_of_time_is_flagged_as_one():
    """The resolver flags its own timeout; a private answer is a plain
    refusal, however long its lookup took."""

    def slow_getaddrinfo(*args, **kwargs):
        time.sleep(0.2)
        return []

    with (
        patch(
            "apps.forum_host.link_preview.socket.getaddrinfo",
            side_effect=slow_getaddrinfo,
        ),
        patch("apps.forum_host.constants.LINK_PREVIEW_DNS_TIMEOUT_SECONDS", 0.01),
    ):
        with pytest.raises(_LookupTimedOut):
            normalize_public_url("https://example.com/page")

    private = [(2, 1, 6, "", ("10.0.0.5", 443))]
    with patch("apps.forum_host.link_preview.socket.getaddrinfo", return_value=private):
        with pytest.raises(InvalidPreviewURL) as refused:
            normalize_public_url("https://example.com/page")
    assert not isinstance(refused.value, _LookupTimedOut)


def test_failed_preview_uses_the_short_cache_ttl():
    url = "https://93.184.216.34/unavailable"
    with (
        patch(
            "apps.forum_host.link_preview._fetch_html",
            side_effect=_FetchFailed("HTTP 500"),
        ),
        patch("apps.forum_host.link_preview.cache.set") as cache_set,
    ):
        result = fetch_link_preview(url)

    cache_set.assert_called_once_with(
        ANY,
        result,
        constants.LINK_PREVIEW_FAILURE_CACHE_TTL_SECONDS,
    )


def test_read_document_rejects_non_html_and_oversized_content():
    class Response:
        def __init__(self, headers, body):
            self.headers = headers
            self.body = body

        def getheader(self, name):
            return self.headers.get(name)

        def read1(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    deadline = time.monotonic() + 5
    with pytest.raises(_FetchFailed, match="not HTML"):
        _read_document(Response({"Content-Type": "application/pdf"}, b"data"), deadline)
    with patch.object(constants, "LINK_PREVIEW_MAX_BODY_BYTES", 4):
        with pytest.raises(_FetchFailed, match="too large"):
            _read_document(
                Response(
                    {"Content-Type": "text/html", "Content-Length": "5"},
                    b"large",
                ),
                deadline,
            )


def test_request_path_percent_encodes_unicode_components():
    target = _Target(
        "https://example.com/plants/monstéra?q=árbol",
        "https",
        "example.com",
        443,
        "93.184.216.34",
    )
    assert _request_path(target) == "/plants/monst%C3%A9ra?q=%C3%A1rbol"


def test_open_connection_uses_the_validated_ip_instead_of_resolving_again():
    target = _Target(
        "https://example.com/start",
        "https",
        "example.com",
        443,
        "93.184.216.34",
    )
    with patch(
        "apps.forum_host.link_preview.socket.create_connection",
        return_value=object(),
    ) as create_connection:
        connection = _open_connection(target)
        try:
            connection._create_connection(("example.com", 443), 2, None)
        finally:
            connection.close()

    create_connection.assert_called_once_with(("93.184.216.34", 443), 2, None)


def test_fetch_html_follows_a_public_redirect_and_returns_the_final_url():
    class Response:
        def __init__(self, status, headers, body=b""):
            self.status = status
            self.headers = headers
            self.body = body

        def getheader(self, name):
            return self.headers.get(name)

        length = None

        def read1(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

        def close(self):
            pass

    class Connection:
        sock = None

        def __init__(self, response):
            self.response = response

        def connect(self):
            pass

        def request(self, method, path, headers):
            pass

        def getresponse(self):
            return self.response

        def close(self):
            pass

    target = _Target(
        "https://93.184.216.34/start",
        "https",
        "93.184.216.34",
        443,
        "93.184.216.34",
    )
    final_url = "https://93.184.216.34/final"
    connections = [
        Connection(Response(302, {"Location": final_url})),
        Connection(Response(200, {"Content-Type": "text/html"}, b"<title>ok</title>")),
    ]
    with patch(
        "apps.forum_host.link_preview._open_connection",
        side_effect=connections,
    ) as open_connection:
        assert _fetch_html(target, time.monotonic() + 5) == (
            final_url,
            b"<title>ok</title>",
        )

    assert open_connection.call_count == 2
    assert open_connection.call_args_list[1].args[0].url == final_url


def test_fetch_html_does_not_follow_redirect_to_private_target():
    class RedirectResponse:
        status = 302

        def getheader(self, name):
            return "http://127.0.0.1/secret" if name == "Location" else None

        def close(self):
            pass

    class Connection:
        sock = None

        def connect(self):
            pass

        def request(self, method, path, headers):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            pass

    target = _Target(
        "https://93.184.216.34/start",
        "https",
        "93.184.216.34",
        443,
        "93.184.216.34",
    )
    with patch(
        "apps.forum_host.link_preview._open_connection", return_value=Connection()
    ) as open_connection:
        with pytest.raises(_FetchFailed, match="redirect refused"):
            _fetch_html(target, time.monotonic() + 5)

    open_connection.assert_called_once()
    assert open_connection.call_args.args[0] == target


@pytest.mark.django_db
def test_link_preview_endpoint_requires_authentication():
    response = APIClient().get(
        "/api/v1/forum/link-preview/?url=https%3A%2F%2Fexample.com%2F"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_link_preview_endpoint_rejects_private_url_for_authenticated_user():
    user = User.objects.create_user(username="preview-private-target")
    client = APIClient()
    client.force_authenticate(user)
    response = client.get("/api/v1/forum/link-preview/?url=http%3A%2F%2F127.0.0.1%2F")

    assert response.status_code == 400
    assert response.data == {"detail": "A public HTTP(S) URL is required."}


@pytest.mark.django_db
def test_link_preview_endpoint_returns_metadata_for_authenticated_user():
    user = User.objects.create_user(username="preview-reader")
    client = APIClient()
    client.force_authenticate(user)
    preview = {
        "url": "https://example.com/",
        "title": "Example",
        "description": "Example description",
        "image_url": None,
        "site_name": "Example",
        "domain": "example.com",
        "available": True,
    }
    with patch(
        "apps.forum_host.link_preview.fetch_link_preview",
        return_value=preview,
    ) as fetch:
        response = client.get(
            "/api/v1/forum/link-preview/?url=https%3A%2F%2Fexample.com%2F"
        )

    assert response.status_code == 200
    assert response.data == preview
    assert response["Cache-Control"] == "private, no-store"
    assert "Cookie" in response["Vary"] and "Authorization" in response["Vary"]
    fetch.assert_called_once_with("https://example.com/")


@pytest.mark.django_db
@override_settings(FORUM_RATELIMITS={"link_preview": "1/m"})
def test_link_preview_endpoint_is_rate_limited():
    user = User.objects.create_user(username="preview-rate-limited")
    client = APIClient()
    client.force_authenticate(user)
    with patch(
        "apps.forum_host.link_preview.fetch_link_preview",
        return_value={"available": False},
    ):
        with freeze_time("2026-09-05 12:00:00"):
            first = client.get(
                "/api/v1/forum/link-preview/?url=https%3A%2F%2Fexample.com%2Fone"
            )
            second = client.get(
                "/api/v1/forum/link-preview/?url=https%3A%2F%2Fexample.com%2Ftwo"
            )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second["Retry-After"] == "60"


# --- the forum package's LINK_PREVIEW_FETCHER hook (todo 428) -----------------


def test_snapshot_hook_returns_the_card_text_and_never_a_third_party_image():
    """The page's og:image goes to the image cache (todo 428 slice B); the
    snapshot carries only the cache's answer, never the third-party URL."""
    from apps.forum_host.link_preview import link_preview_snapshot

    preview = {
        "url": "https://example.com/",
        "title": "Title",
        "description": "Description",
        "image_url": "https://cdn.example.com/og.png",
        "site_name": "Example",
        "domain": "example.com",
        "available": True,
    }
    with (
        patch(
            "apps.forum_host.link_preview.fetch_link_preview", return_value=preview
        ) as fetch,
        patch(
            "apps.forum_host.link_preview._cache_preview_image", return_value=""
        ) as cache_image,
    ):
        snapshot = link_preview_snapshot("https://example.com/")

    fetch.assert_called_once_with("https://example.com/", deadline=ANY)
    cache_image.assert_called_once_with("https://cdn.example.com/og.png", ANY)
    assert snapshot == {
        "title": "Title",
        "description": "Description",
        "site_name": "Example",
        "domain": "example.com",
        "image": "",
    }


@pytest.mark.parametrize(
    "outcome",
    [
        InvalidPreviewURL(),
        {"url": "https://example.com/", "available": False},
    ],
)
def test_snapshot_hook_answers_none_when_there_is_no_card(outcome):
    from apps.forum_host.link_preview import link_preview_snapshot

    kwargs = (
        {"side_effect": outcome}
        if isinstance(outcome, Exception)
        else {"return_value": outcome}
    )
    with patch("apps.forum_host.link_preview.fetch_link_preview", **kwargs):
        assert link_preview_snapshot("http://10.0.0.1/") is None


def test_snapshot_hook_budgets_the_image_from_the_package_deadline():
    """Todo 448 item 9: the image gets what is left of the package's window
    (its deadline, counted from submit) minus the margin, not a fresh budget
    from when the pool thread started."""
    from apps.forum_host import constants
    from apps.forum_host.link_preview import link_preview_snapshot

    preview = {
        "url": "https://example.com/",
        "title": "Title",
        "image_url": "https://cdn.example.com/og.png",
        "available": True,
    }
    with (
        patch("apps.forum_host.link_preview.fetch_link_preview", return_value=preview),
        patch(
            "apps.forum_host.link_preview._cache_preview_image", return_value=""
        ) as cache_image,
    ):
        link_preview_snapshot("https://example.com/", deadline=1000.0)

    cache_image.assert_called_once_with(
        "https://cdn.example.com/og.png",
        1000.0 - constants.LINK_PREVIEW_SNAPSHOT_MARGIN_SECONDS,
    )


def test_the_host_names_this_snapshot_hook_as_the_package_fetcher():
    """Production turns cards on with this path (todo 428 slice C); test runs
    keep the setting itself off. A rename here must fail a test, not quietly
    degrade every card to a link (the package logs a non-importing path and
    treats it as unset)."""
    from apps.forum_host.link_preview import link_preview_snapshot
    from django.conf import settings
    from django.utils.module_loading import import_string

    assert import_string(settings.LINK_PREVIEW_FETCHER_PATH) is link_preview_snapshot
    assert settings.WAGTAILFORUM_LINK_PREVIEW_FETCHER is None


# --- todo 448 item 5: the page fetch has a wall clock -------------------------


@pytest.mark.parametrize(
    "prefix",
    [
        # The status line arrives, the headers never finish.
        b"HTTP/1.1 200 OK\r\n",
        # The headers finish; the body drips a byte at a time. Each recv
        # beats the socket timeout, so only the deadline ends it.
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>",
    ],
    ids=["headers", "body"],
)
def test_a_page_that_drips_past_the_deadline_is_abandoned_on_time(
    prefix, loopback_drip
):
    port = loopback_drip(prefix)
    target = _Target(
        f"http://127.0.0.1:{port}/page", "http", "127.0.0.1", port, "127.0.0.1"
    )
    started = time.monotonic()
    with pytest.raises(_FetchFailed) as failure:
        _fetch_html(target, time.monotonic() + 0.3)
    elapsed = time.monotonic() - started

    assert failure.value.reason == "deadline"
    assert elapsed < 1.5  # the drip runs 3 s


def test_a_composer_preview_gets_the_page_deadline():
    """No caller deadline (the composer endpoint): the fetch is still
    bounded, by LINK_PREVIEW_PAGE_DEADLINE_SECONDS."""
    url = "https://93.184.216.34/page"
    with patch(
        "apps.forum_host.link_preview._fetch_html",
        return_value=(url, b"<title>ok</title>"),
    ) as fetch:
        before = time.monotonic()
        fetch_link_preview(url)

    deadline = fetch.call_args.args[1]
    assert 0 < deadline - before <= constants.LINK_PREVIEW_PAGE_DEADLINE_SECONDS + 0.5


def test_the_snapshot_passes_its_budget_to_the_page_fetch():
    from apps.forum_host.link_preview import link_preview_snapshot

    with patch(
        "apps.forum_host.link_preview.fetch_link_preview",
        return_value={"available": False},
    ) as fetch:
        link_preview_snapshot("https://example.com/", deadline=1000.0)

    fetch.assert_called_once_with(
        "https://example.com/",
        deadline=1000.0 - constants.LINK_PREVIEW_SNAPSHOT_MARGIN_SECONDS,
    )


def test_a_failure_from_running_out_of_budget_is_not_cached():
    """A snapshot that waited in a busy pool runs out of OUR time, not the
    site's: caching that would blank the composer preview and the next
    post's card for a minute."""
    url = "https://93.184.216.34/page"
    with (
        patch(
            "apps.forum_host.link_preview._fetch_html",
            side_effect=_FetchFailed("deadline"),
        ),
        patch("apps.forum_host.link_preview.cache.set") as cache_set,
    ):
        result = fetch_link_preview(url, deadline=time.monotonic() + 5)

    assert result["available"] is False
    cache_set.assert_not_called()


# --- todo 448 item 12: a failed fetch says why ---------------------------------

LOGGER = "apps.forum_host.link_preview"


def _logs():
    """``assertLogs`` on the module's logger: it attaches its own handler, so
    it sees records that never propagate to pytest's ``caplog``."""
    return unittest.TestCase().assertLogs(LOGGER, "INFO")


@pytest.mark.parametrize(
    "reason",
    ["timeout", "HTTP 503", "redirect refused", "not HTML", "deadline"],
)
def test_a_failed_fetch_logs_its_reason_and_host_but_not_the_url(reason):
    url = "https://93.184.216.34/secret-path?token=abc"
    with patch(
        "apps.forum_host.link_preview._fetch_html", side_effect=_FetchFailed(reason)
    ):
        with _logs() as logged:
            fetch_link_preview(url)

    lines = [r.getMessage() for r in logged.records]
    assert lines == [
        f"[LINK_PREVIEW] page fetch failed ({reason}) for host 93.184.216.34"
    ]
    assert "secret-path" not in lines[0] and "token" not in lines[0]


def test_a_cached_failure_logs_nothing():
    url = "https://93.184.216.34/page"
    with patch(
        "apps.forum_host.link_preview._fetch_html",
        side_effect=_FetchFailed("timeout"),
    ) as fetch:
        with _logs():
            fetch_link_preview(url)
        with unittest.TestCase().assertNoLogs(LOGGER, "INFO"):
            fetch_link_preview(url)

    assert fetch.call_count == 1


def _fetch_with(response_or_exc):
    """``_fetch_html`` against one fake connection whose ``getresponse``
    returns ``response_or_exc`` or raises it."""

    class Connection:
        sock = None

        def connect(self):
            pass

        def request(self, method, path, headers):
            pass

        def getresponse(self):
            if isinstance(response_or_exc, Exception):
                raise response_or_exc
            return response_or_exc

        def close(self):
            pass

    target = _Target(
        "https://93.184.216.34/start", "https", "93.184.216.34", 443, "93.184.216.34"
    )
    with patch(
        "apps.forum_host.link_preview._open_connection", return_value=Connection()
    ):
        with pytest.raises(_FetchFailed) as failure:
            _fetch_html(target, time.monotonic() + 5)
    return failure.value.reason


def test_fetch_html_names_each_failure():
    class Status:
        def __init__(self, status, location=None):
            self.status = status
            self.location = location

        def getheader(self, name):
            return self.location if name == "Location" else None

        def close(self):
            pass

    assert _fetch_with(Status(503)) == "HTTP 503"
    assert _fetch_with(Status(302)) == "redirect without a location"
    assert _fetch_with(TimeoutError("timed out")) == "timeout"
    assert _fetch_with(ConnectionResetError()) == (
        "connection failed (ConnectionResetError)"
    )


def test_the_snapshot_logs_a_url_it_cannot_fetch_by_host_only():
    from apps.forum_host.link_preview import link_preview_snapshot

    with patch(
        "apps.forum_host.link_preview.fetch_link_preview",
        side_effect=InvalidPreviewURL(),
    ):
        with _logs() as logged:
            assert link_preview_snapshot("http://10.0.0.1/admin?k=v") is None

    lines = [r.getMessage() for r in logged.records]
    assert lines == [
        "[LINK_PREVIEW] not a public URL, or DNS failed, for host 10.0.0.1"
    ]


def test_the_connect_timeout_is_capped_at_the_time_left():
    """The watchdog is armed only after connect(), so the connect itself is
    bounded by the socket timeout, which must not outlast the deadline."""
    target = _Target(
        "https://93.184.216.34/start", "https", "93.184.216.34", 443, "93.184.216.34"
    )
    with patch(
        "apps.forum_host.link_preview._open_connection",
        side_effect=TimeoutError("connect timed out"),
    ) as open_connection:
        with pytest.raises(_FetchFailed):
            _fetch_html(target, time.monotonic() + 0.5)

    assert open_connection.call_args.kwargs["timeout"] <= 0.5


# --- todo 535: follow-ups from todo 448's reviews ------------------------------


def test_item4_a_redirect_lookup_that_runs_out_of_time_is_a_deadline():
    """The redirect hop's DNS lookup gets only the time left. A lookup that
    ran out of it is our deadline, not a refused redirect, so it is not
    cached as one."""

    class RedirectResponse:
        status = 302

        def getheader(self, name):
            return "https://slow-dns.example/next" if name == "Location" else None

        def close(self):
            pass

    import socket as socket_module

    class Connection:
        # A real socket: the watchdog fires during the slow lookup.
        def __init__(self):
            self.sock, self._peer = socket_module.socketpair()

        def connect(self):
            pass

        def request(self, method, path, headers):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            self.sock.close()
            self._peer.close()

    def lookup_times_out(url, *, dns_timeout=None):
        time.sleep(0.3)
        # What _resolve_addresses raises when the lookup itself runs out
        # of time (todo 539 item 5).
        raise _LookupTimedOut

    target = _Target(
        "https://93.184.216.34/start", "https", "93.184.216.34", 443, "93.184.216.34"
    )
    with (
        patch(
            "apps.forum_host.link_preview._open_connection", return_value=Connection()
        ),
        patch(
            "apps.forum_host.link_preview._target_for_url", side_effect=lookup_times_out
        ),
    ):
        with pytest.raises(_FetchFailed) as failure:
            _fetch_html(target, time.monotonic() + 0.2)

    assert failure.value.reason == "deadline"


def test_539_item5_a_refusal_whose_lookup_finished_late_is_still_a_refusal():
    """A redirect to a private address whose lookup FINISHED after the
    deadline is a refusal, not our deadline, so it is cached like any other
    failure (todo 539 item 5). Before, any refusal past the deadline was
    relabelled ``deadline`` and went uncached."""
    import socket as socket_module

    class RedirectResponse:
        status = 302

        def getheader(self, name):
            return "https://private.example/next" if name == "Location" else None

        def close(self):
            pass

    class Connection:
        def __init__(self):
            self.sock, self._peer = socket_module.socketpair()

        def connect(self):
            pass

        def request(self, method, path, headers):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            self.sock.close()
            self._peer.close()

    def late_refusal(url, *, dns_timeout=None):
        time.sleep(0.3)
        raise InvalidPreviewURL  # a private answer, not a timed-out lookup

    target = _Target(
        "https://93.184.216.34/start", "https", "93.184.216.34", 443, "93.184.216.34"
    )
    with (
        patch(
            "apps.forum_host.link_preview._open_connection", return_value=Connection()
        ),
        patch("apps.forum_host.link_preview._target_for_url", side_effect=late_refusal),
    ):
        with pytest.raises(_FetchFailed) as failure:
            _fetch_html(target, time.monotonic() + 0.2)

    assert failure.value.reason == "redirect refused"


def test_item5_the_composer_caches_a_deadline_failure():
    """The composer's budget is fixed, so its deadline failure means the site
    was slow: cached like any other failure, so a site that drips a byte a
    second is not fetched again on every composer request."""
    url = "https://93.184.216.34/page"
    with patch(
        "apps.forum_host.link_preview._fetch_html",
        side_effect=_FetchFailed("deadline"),
    ) as fetch:
        assert fetch_link_preview(url)["available"] is False
        assert fetch_link_preview(url)["available"] is False

    assert fetch.call_count == 1


def test_item5_a_snapshot_deadline_failure_is_still_not_cached():
    url = "https://93.184.216.34/page"
    with patch(
        "apps.forum_host.link_preview._fetch_html",
        side_effect=_FetchFailed("deadline"),
    ) as fetch:
        fetch_link_preview(url, deadline=time.monotonic() + 5)
        fetch_link_preview(url, deadline=time.monotonic() + 5)

    assert fetch.call_count == 2


class _RecordingSocket:
    def __init__(self):
        self.timeouts = []
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def close(self):
        self.closed = True


def test_item6_the_socket_gets_only_the_time_left_after_the_tcp_connect():
    """The TLS handshake runs on the socket's timeout after the TCP connect
    returns; that timeout is cut to what is left of the deadline."""
    target = _Target(
        "https://example.com/start", "https", "example.com", 443, "93.184.216.34"
    )
    sock = _RecordingSocket()
    deadline = time.monotonic() + 0.5
    with patch(
        "apps.forum_host.link_preview.socket.create_connection", return_value=sock
    ):
        connection = _open_connection(target, timeout=4, deadline=deadline)
        assert connection._create_connection(("example.com", 443), 4, None) is sock

    assert len(sock.timeouts) == 1 and 0 < sock.timeouts[0] <= 0.5


def test_item6_a_tcp_connect_that_used_up_the_deadline_is_a_timeout():
    target = _Target(
        "https://example.com/start", "https", "example.com", 443, "93.184.216.34"
    )
    sock = _RecordingSocket()
    with patch(
        "apps.forum_host.link_preview.socket.create_connection", return_value=sock
    ):
        connection = _open_connection(
            target, timeout=4, deadline=time.monotonic() - 0.01
        )
        with pytest.raises(TimeoutError):
            connection._create_connection(("example.com", 443), 4, None)

    assert sock.closed


@pytest.mark.parametrize(
    "connect_seconds",
    [0.2, 1.3],
    ids=["connect-leaves-time", "connect-uses-the-budget"],
)
def test_item6_a_slow_connect_then_a_stalled_handshake_ends_at_the_deadline(
    loopback_drip, connect_seconds
):
    """The TCP connect takes part (or all) of a 1 s budget, then the server
    stalls the TLS handshake. Before, the handshake got a fresh timeout and
    the fetch ran past its deadline. Asserted on the timeout the socket was
    handed, not on wall time (todo 539 item 7).

    Each case lands in its branch by a wide margin, not by the test's own
    clock read (todo 550 items 2 and 3): the old ``if connected_at <
    deadline`` raced production's later read, and its else branch, reached
    only on a loaded runner, also passed under the bug. A connect that used
    the whole budget must now never reach the handshake at all."""
    import socket as socket_module
    import ssl

    port = loopback_drip(b"\x16\x03\x03\x40\x00")
    real_create_connection = socket_module.create_connection
    real_wrap_socket = ssl.SSLContext.wrap_socket
    connected = []
    handshaken = []

    def slow_connect(address, timeout, *args, **kwargs):
        time.sleep(connect_seconds)
        sock = real_create_connection(address, timeout, *args, **kwargs)
        connected.append((sock, time.monotonic()))
        return sock

    def recording_wrap_socket(context, sock, *args, **kwargs):
        handshaken.append(sock)
        return real_wrap_socket(context, sock, *args, **kwargs)

    target = _Target(
        f"https://127.0.0.1:{port}/page", "https", "127.0.0.1", port, "127.0.0.1"
    )
    deadline = time.monotonic() + 1.0
    with (
        patch(
            "apps.forum_host.link_preview.socket.create_connection",
            side_effect=slow_connect,
        ),
        patch.object(ssl.SSLContext, "wrap_socket", recording_wrap_socket),
    ):
        with pytest.raises(_FetchFailed) as failure:
            _fetch_html(target, deadline)

    [(sock, connected_at)] = connected
    if connect_seconds < 1.0:
        # The handshake got at most what the connect left of the budget.
        assert handshaken == [sock]
        assert sock.gettimeout() <= deadline - connected_at
        assert failure.value.reason in {"deadline", "timeout"}
    else:
        # The socket was closed instead of handed to the handshake.
        assert handshaken == []
        assert sock.fileno() == -1
        assert failure.value.reason == "deadline"


def test_545_item2_a_drip_server_nothing_connected_to_stops_promptly():
    """Teardown must not wait on ``accept()`` waking from another thread's
    ``close()``: Linux never wakes it, so a test whose fetch aborted before
    connecting stalled the fixture's join for its full timeout."""
    from apps.forum_host.tests.conftest import DripServer

    server = DripServer(b"prefix")
    server.stop(timeout=2)

    assert not server.thread.is_alive()


def test_550_item5_a_client_that_never_sends_does_not_stall_stop():
    """A client that connects and sends nothing left the drip thread blocked
    in ``recv()``, which ``stop()`` could not wake: teardown waited out the
    whole join.

    A thread still alive after ``stop()``'s join is the failure; no
    wall-clock bound, which a loaded runner could trip (todo 576 item 4)."""
    import socket as socket_module

    from apps.forum_host.tests.conftest import DripServer

    server = DripServer(b"prefix")
    with socket_module.create_connection(("127.0.0.1", server.port)):
        time.sleep(0.2)  # several accept polls: the server is in recv()
        server.stop(timeout=2)

    assert not server.thread.is_alive()


def test_576_item2_a_client_that_closes_before_sending_gets_nothing():
    """A clean EOF before any request is the client leaving, not a request
    (todo 576 item 2): the drip ends without sending the prefix, and
    ``hung_up`` stays reserved for a client that hangs up mid-drip.

    The client half-closes (``SHUT_WR``) and keeps reading, so anything the
    server sent would arrive; before, the drip sent the prefix to it."""
    import socket as socket_module

    from apps.forum_host.tests.conftest import DripServer

    server = DripServer(b"prefix")
    try:
        with socket_module.create_connection(
            ("127.0.0.1", server.port), timeout=2
        ) as client:
            client.shutdown(socket_module.SHUT_WR)
            received = client.recv(64)
        server.thread.join(2)
    finally:
        server.stop(timeout=2)

    assert received == b""
    assert not server.thread.is_alive()
    assert not server.hung_up


def test_550_item6_a_transient_accept_error_does_not_end_the_server():
    """``accept()`` failing for one client (ECONNABORTED) is not the
    listener closing: the server keeps listening and drips to the next
    client."""
    import errno
    import socket as socket_module

    from apps.forum_host.tests.conftest import DripServer

    real_accept = socket_module.socket.accept
    aborted = []

    def flaky_accept(listener):
        if not aborted:
            aborted.append(errno.ECONNABORTED)
            raise ConnectionAbortedError(errno.ECONNABORTED, "connection aborted")
        return real_accept(listener)

    with patch.object(socket_module.socket, "accept", flaky_accept):
        server = DripServer(b"prefix")
        try:
            with socket_module.create_connection(
                ("127.0.0.1", server.port), timeout=2
            ) as client:
                client.sendall(b"GET / HTTP/1.1\r\n\r\n")
                received = b""
                while len(received) < len(b"prefix"):
                    chunk = client.recv(len(b"prefix") - len(received))
                    if not chunk:
                        break
                    received += chunk
        finally:
            server.stop(timeout=2)

    # The abort really was injected (todo 576 item 4: a call count proved
    # nothing, since the accept poll calls accept repeatedly anyway).
    assert aborted == [errno.ECONNABORTED]
    assert received == b"prefix"


def test_545_item2_a_client_reset_ends_the_drip_thread_quietly():
    """A client that resets the connection mid-drip ends the drip thread
    without an unhandled exception in it.

    The reset now comes only after the client has read the prefix, so the
    server is past ``accept()`` and inside its send loop, and the reset must
    reach its ``except OSError`` (todo 550 item 1): before, the RST could
    beat the 50 ms accept poll and the thread ended in ``_accept`` instead."""
    import socket as socket_module
    import struct
    import threading

    from apps.forum_host.tests.conftest import DripServer

    raised = []
    server = DripServer(b"prefix")
    with patch.object(threading, "excepthook", side_effect=raised.append):
        client = socket_module.create_connection(("127.0.0.1", server.port), timeout=2)
        client.sendall(b"GET / HTTP/1.1\r\n\r\n")
        received = b""
        while len(received) < len(b"prefix"):
            chunk = client.recv(len(b"prefix") - len(received))
            if not chunk:
                break  # the server closed early: fail below, never spin
            received += chunk
        # SO_LINGER 0: close() sends a RST, not a FIN.
        client.setsockopt(
            socket_module.SOL_SOCKET,
            socket_module.SO_LINGER,
            struct.pack("ii", 1, 0),
        )
        client.close()
        server.thread.join(2)
        server.stop(timeout=2)

    assert received == b"prefix"
    assert not server.thread.is_alive()
    assert server.hung_up
    assert raised == []


@pytest.mark.parametrize(
    "url, logged",
    [
        ("http://ex\x1bample.com/admin", "'ex\\x1bample.com'"),
        ("http://" + "a" * 600 + "/x", repr("a" * 253)),
    ],
    ids=["control-character", "too-long"],
)
def test_item7_a_rejected_url_logs_a_quoted_truncated_host(url, logged):
    from apps.forum_host.link_preview import link_preview_snapshot

    with patch(
        "apps.forum_host.link_preview.fetch_link_preview",
        side_effect=InvalidPreviewURL(),
    ):
        with _logs() as logged_records:
            assert link_preview_snapshot(url) is None

    lines = [r.getMessage() for r in logged_records.records]
    assert lines == [
        f"[LINK_PREVIEW] not a public URL, or DNS failed, for host {logged}"
    ]
    assert "\x1b" not in lines[0]


def test_item8_the_snapshot_image_warning_names_the_host_only():
    from apps.forum_host.link_preview import link_preview_snapshot

    image_url = "https://93.184.216.34/secret-path/og.png?token=abc"
    with (
        patch(
            "apps.forum_host.link_preview.fetch_link_preview",
            return_value={
                "available": True,
                "title": "t",
                "image_url": image_url,
            },
        ),
        patch(
            "apps.forum_host.link_preview._cache_preview_image",
            side_effect=RuntimeError("boom"),
        ),
    ):
        with _logs() as logged:
            assert link_preview_snapshot("https://93.184.216.34/page")["image"] == ""

    lines = [r.getMessage() for r in logged.records]
    assert lines == ["[LINK_PREVIEW] preview image failed for host 93.184.216.34"]
