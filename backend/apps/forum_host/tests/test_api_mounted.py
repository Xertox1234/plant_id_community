import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_forum_boards_endpoint_is_mounted():
    resp = APIClient().get("/api/v1/forum/boards/")
    assert resp.status_code == 200
    assert "results" in resp.data


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
