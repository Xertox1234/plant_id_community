"""CORS preflight must permit every custom header a browser client sends.

`CORS_ALLOW_HEADERS` is an ALLOWLIST, and a header missing from it fails in the
quietest way this codebase offers: the preflight still returns **200**, the
response simply omits the header from `Access-Control-Allow-Headers`, and the
browser then declines to send the real request. Django never sees the call, so
there is no 4xx, no traceback and no server log line — only a request that is
never made. `CORS_PREFLIGHT_MAX_AGE` (86400) then caches that refusal for a day.

This bit for real: the forum composer's image upload started sending
`Idempotency-Key` (M36) in todo 357. The backend had honoured that header since
M35, but only the Flutter app had ever sent one — and a native HTTP client is
not subject to CORS — so nothing had ever exercised the browser path. Every
jsdom unit test passed (jsdom does not enforce CORS) and the endpoint's own
backend tests passed (the Django test client does not either). It surfaced only
in `web/e2e/forum-image-upload.spec.js`, as three tests timing out waiting for a
POST that the browser had silently refused to send.

These tests are therefore deliberately about the MIDDLEWARE's answer, not about
the constant: they assert what a browser is actually told.
"""

import pytest
from django.test import override_settings

# One entry per custom (non CORS-safelisted) request header any browser client
# sends. `Accept`/`Content-Type` are safelisted and need no allowlist entry, but
# they are listed in settings and cost nothing to assert.
#
# ADD A ROW HERE WHENEVER A WEB CLIENT STARTS SENDING A NEW HEADER — that is the
# whole point of this file. `web/src/services/*.ts` is where they originate.
BROWSER_SENT_HEADERS = [
    "authorization",  # Bearer tokens (httpClient)
    "content-type",
    "idempotency-key",  # retry-safe writes, M35/M36 — forum composer upload
    "x-csrftoken",  # every unsafe method
    "x-request-id",  # distributed tracing
    "x-requested-with",
]

ORIGIN = "https://web.test"


def _preflight(client, path, requested_header):
    """Issue the exact OPTIONS a browser sends before a cross-origin POST."""
    return client.options(
        path,
        HTTP_ORIGIN=ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=requested_header,
    )


@pytest.mark.parametrize("header", BROWSER_SENT_HEADERS)
@override_settings(CORS_ALLOWED_ORIGINS=[ORIGIN], CORS_ALLOW_ALL_ORIGINS=False)
def test_preflight_permits_every_header_a_browser_client_sends(client, header):
    response = _preflight(client, "/api/v1/forum/images/", header)

    # The origin must be allowed at all, or allow-headers is absent entirely and
    # the assertion below would fail for a misleading reason.
    assert response["Access-Control-Allow-Origin"] == ORIGIN

    allowed = {
        value.strip().lower()
        for value in response["Access-Control-Allow-Headers"].split(",")
    }
    assert header in allowed, (
        f"{header!r} is not in Access-Control-Allow-Headers, so a browser will "
        f"refuse to send a cross-origin request carrying it. Add it to "
        f"CORS_ALLOW_HEADERS in settings.py. Allowed: {sorted(allowed)}"
    )


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGIN], CORS_ALLOW_ALL_ORIGINS=False)
def test_preflight_returns_200_even_for_a_header_it_refuses(client):
    """Pin the failure mode itself, so the docstring above cannot go stale.

    If this ever starts returning 4xx (a django-cors-headers change, say), the
    header-missing bug has become LOUD and this module's reasoning is obsolete.
    That is a documentation fix, not a test bug: rewrite the module docstring
    and the two `docs/rules` entries it is cited from, and update this test to
    assert the new status. Do not "repair" it back to 200.
    """
    response = _preflight(
        client, "/api/v1/forum/images/", "x-totally-unregistered-header"
    )

    assert response.status_code == 200
    allowed = {
        value.strip().lower()
        for value in response["Access-Control-Allow-Headers"].split(",")
    }
    assert "x-totally-unregistered-header" not in allowed
