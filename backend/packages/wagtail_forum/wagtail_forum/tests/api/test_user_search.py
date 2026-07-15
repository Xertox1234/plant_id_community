import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_search_matches_username_prefix():
    User.objects.create_user(username="alice")
    User.objects.create_user(username="alicia")
    User.objects.create_user(username="bob")
    # Contains "ali" but doesn't START with it — an icontains regression
    # (instead of istartswith) would wrongly surface this (todo 253 slice 4
    # review).
    User.objects.create_user(username="malice")
    requester = User.objects.create_user(username="requester")

    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/users/search/?q=ali")

    assert resp.status_code == 200
    usernames = {row["username"] for row in resp.data}
    assert usernames == {"alice", "alicia"}


@pytest.mark.django_db
def test_search_response_excludes_email():
    User.objects.create_user(username="carol", email="carol@example.com")
    requester = User.objects.create_user(username="requester2")

    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/users/search/?q=car")

    assert resp.status_code == 200
    assert set(resp.data[0].keys()) == {"username", "display_name"}


@pytest.mark.django_db
def test_search_requires_auth():
    resp = APIClient().get("/forum/users/search/?q=a")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_search_with_empty_query_returns_empty_list():
    requester = User.objects.create_user(username="requester3")

    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/users/search/")

    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_search_escapes_sql_wildcards():
    """A literal "_"/"%" in the query must not act as a SQL wildcard —
    escaped per backend CLAUDE.md convention, matching every other
    istartswith/icontains filter in the codebase."""
    User.objects.create_user(username="dave_1")
    User.objects.create_user(username="daveX1")
    # Contains "dave_" but doesn't START with it — pins istartswith, not
    # icontains (todo 253 slice 4 review).
    User.objects.create_user(username="xdave_1")
    requester = User.objects.create_user(username="requester4")

    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/users/search/?q=dave_")

    assert resp.status_code == 200
    usernames = {row["username"] for row in resp.data}
    # An unescaped "_" (SQL "any one character") would also match "daveX1".
    assert usernames == {"dave_1"}


@pytest.mark.django_db
def test_search_excludes_inactive_users():
    inactive = User.objects.create_user(username="erin")
    inactive.is_active = False
    inactive.save()
    requester = User.objects.create_user(username="requester5")

    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/users/search/?q=erin")

    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_search_caps_results():
    for i in range(15):
        User.objects.create_user(username=f"frank{i}")
    requester = User.objects.create_user(username="requester6")

    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/users/search/?q=frank")

    assert resp.status_code == 200
    assert len(resp.data) == 10
