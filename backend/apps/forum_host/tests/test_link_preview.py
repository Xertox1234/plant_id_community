import time
from unittest.mock import ANY, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.forum_host import constants
from apps.forum_host.link_preview import (
    InvalidPreviewURL,
    _fetch_html,
    _open_connection,
    _read_document,
    _request_path,
    _Target,
    fetch_link_preview,
    normalize_public_url,
)

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
        _Target(url, "https", "93.184.216.34", 443, "93.184.216.34")
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
        "https://user:pass@93.184.216.34/",
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


def test_failed_preview_uses_the_short_cache_ttl():
    url = "https://93.184.216.34/unavailable"
    with (
        patch("apps.forum_host.link_preview._fetch_html", return_value=None),
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

        def read(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    assert _read_document(Response({"Content-Type": "application/pdf"}, b"data")) is None
    with patch.object(constants, "LINK_PREVIEW_MAX_BODY_BYTES", 4):
        assert (
            _read_document(
                Response(
                    {"Content-Type": "text/html", "Content-Length": "5"},
                    b"large",
                )
            )
            is None
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

        def read(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

        def close(self):
            pass

    class Connection:
        def __init__(self, response):
            self.response = response

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
        assert _fetch_html(target) == (final_url, b"<title>ok</title>")

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
    with patch("apps.forum_host.link_preview._open_connection", return_value=Connection()) as open_connection:
        assert _fetch_html(target) is None

    open_connection.assert_called_once_with(target)


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
