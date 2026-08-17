import pytest
from rest_framework.test import APIClient


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
