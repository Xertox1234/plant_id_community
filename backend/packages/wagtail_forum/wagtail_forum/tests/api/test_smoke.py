import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_boards_endpoint_is_reachable():
    resp = APIClient().get("/forum/boards/")
    assert resp.status_code == 200
    assert resp.data["results"] == []
