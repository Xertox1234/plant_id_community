"""`provider` is validated before it can reach a redirect URL (todo 354).

The OAuth views are routed as ``oauth/<str:provider>/...``. Django's ``str``
converter matches anything except ``/``, and ``request.path_info`` is
percent-decoded before resolution — so a crafted ``%3F`` arrives as a literal
``?`` inside ``provider`` and reshapes the query string of the frontend URL the
view redirects to (``.../auth/x?a=b/callback?error=no_code``).

It was never an open redirect: the host comes from ``settings.FRONTEND_BASE_URL``
and the ``str`` converter cannot escape the path prefix upward. But eight CodeQL
``py/url-redirection`` alerts sat on it, and every one is closed by refusing an
unknown provider before the first redirect.

The view is mounted twice, so both mounts are exercised.
"""

import pytest
from django.core.cache import cache
from django.test import Client


@pytest.fixture(autouse=True)
def _clear_ratelimit_cache():
    """Both views are @ratelimit(rate="10/m", key=client_ip_key) and every test
    here comes from the same IP, so without this the suite trips its own limit
    (the repo's other rate-limit tests clear the cache the same way)."""
    cache.clear()
    yield
    cache.clear()


# `%3F` decodes to `?` in path_info, which `<str:provider>` happily matches.
# No `/` in the payload: the `str` converter stops at one, which is exactly why
# this was never an open redirect — only same-origin query/fragment reshaping.
CRAFTED = "google%3Fa%3Dinjected%23frag"
RAW_CRAFTED = "google?a=injected#frag"

# Mount A: plant_community_backend/urls.py -> apps.users.oauth_urls
# Mount B: apps/users/urls.py, included under api/v1/auth/
MOUNTS = [
    "/api/auth/oauth/{provider}/callback/",
    "/api/v1/auth/oauth/{provider}/callback/",
]


@pytest.mark.django_db
@pytest.mark.parametrize("template", MOUNTS)
def test_unknown_provider_never_reaches_a_redirect(template):
    resp = Client().get(template.format(provider=CRAFTED))

    # Not a redirect at all — so no Location header can carry the raw value.
    assert resp.status_code == 400, resp.status_code
    assert "Location" not in resp
    assert RAW_CRAFTED not in resp.content.decode()
    assert "injected" not in resp.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("template", MOUNTS)
def test_plain_unknown_provider_is_refused(template):
    """The allowlist is an allowlist, not a metacharacter filter."""
    resp = Client().get(template.format(provider="facebook"))

    assert resp.status_code == 400
    assert "Location" not in resp
    # The rejected value is not echoed back either.
    assert "facebook" not in resp.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("template", MOUNTS)
@pytest.mark.parametrize("provider", ["google", "github"])
def test_supported_providers_still_redirect(template, provider):
    """The guard must not break the real flow: a supported provider with no
    `code` still redirects to the frontend as before."""
    resp = Client().get(template.format(provider=provider))

    assert resp.status_code == 302
    assert f"/auth/{provider}/callback" in resp["Location"]


@pytest.mark.django_db
def test_login_endpoint_refuses_an_unknown_provider():
    resp = Client().get(f"/api/auth/oauth/{CRAFTED}/login/")

    assert resp.status_code == 400
    assert RAW_CRAFTED not in resp.content.decode()
