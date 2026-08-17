import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_forum_boards_endpoint_is_mounted():
    resp = APIClient().get("/api/v1/forum/boards/")
    assert resp.status_code == 200
    assert "results" in resp.data


@pytest.mark.django_db
def test_search_many_term_query_is_bounded_not_500():
    # Todo 290: an anonymous many-term query recursed Wagtail's search-query
    # AND-tree construction (one nesting level per term) into a
    # RecursionError/500. The bound lives in the package SearchView.get, but
    # prod serves this route through the throttled forum_host SUBCLASS
    # (see test_host_mounted_reads_carry_m42_cache_headers above), so pin the
    # fix through that real mount, not just the package test urlconf.
    resp = APIClient().get("/api/v1/forum/search/?q=" + "tomato " * 500)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_host_mounted_reads_carry_m42_cache_headers():
    # M42 (todo 261): the caching mixin lives on the PACKAGE read views, but prod
    # serves through this host mount — some views straight from the package
    # (boards) and some via throttled host SUBCLASSES (search). Both must still
    # emit the anon cache headers. The package's own test_read_cache_headers.py
    # runs under the package test urlconf, so this is the one check on the real
    # forum_host path. No fixtures: boards → {"results": []}, empty search → 200.
    client = APIClient()
    for path in ("/api/v1/forum/boards/", "/api/v1/forum/search/"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "public" in resp["Cache-Control"], path
        assert "s-maxage=60" in resp["Cache-Control"], path
        assert "Cookie" in resp["Vary"] and "Authorization" in resp["Vary"], path


@pytest.mark.django_db
def test_host_mounted_private_reads_carry_no_store_cache_headers():
    # Todo 303: PrivateForumReadCacheMixin lives on the PACKAGE views, but
    # three of the six fixed views (MeProfileView, NotificationUnreadCountView,
    # UserMentionSearchView) are re-wrapped here by forum_host's `_throttled`
    # host subclasses. Each subclass body is just `pass`, and `_throttled`
    # decorates the HTTP-method function (`get`), not `finalize_response` — so
    # the mixin's response-header logic, which runs in `finalize_response`,
    # stays intact through the subclass. This test pins that through the real
    # mount rather than relying on the reasoning alone (mirrors
    # test_host_mounted_reads_carry_m42_cache_headers above for the anon
    # case). NotificationListView is mounted straight from the package (no
    # host subclass) and is already covered there; skipped here as redundant.
    user = User.objects.create_user(username="privatereader")
    client = APIClient()
    client.force_authenticate(user)
    for path in (
        "/api/v1/forum/me/profile/",
        "/api/v1/forum/notifications/unread-count/",
        "/api/v1/forum/users/search/?q=a",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        cache_control = resp["Cache-Control"]
        assert "no-store" in cache_control, path
        assert "private" in cache_control, path
        assert "public" not in cache_control, path
        assert "Cookie" in resp["Vary"] and "Authorization" in resp["Vary"], path
