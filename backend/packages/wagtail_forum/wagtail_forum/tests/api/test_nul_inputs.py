"""A NUL (\\x00) in a search query, a mention-search query or a username in
the URL answers an empty result or a 404, never a 500 (forum audit F210).

PostgreSQL rejects a NUL in any text parameter ("A string literal cannot
contain NUL (0x00) characters"), so an unguarded one reaching the ORM raises
ValueError and the request 500s.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail_forum.models import Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

NUL = "%00"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params",
    [
        f"q=Mon{NUL}stera",
        f"q={NUL}",
        f"q=Monstera&board=gen{NUL}eral",
    ],
)
def test_search_with_a_nul_answers_empty(params):
    board = make_forum(name="General", slug="general")
    Topic.objects.create(board=board, title="Monstera care", slug="m", live=True)

    resp = APIClient().get(f"/forum/search/?{params}")

    assert resp.status_code == 200
    assert resp.data["topics"] == []
    assert resp.data["posts"] == []


@pytest.mark.django_db
def test_mention_search_with_a_nul_answers_empty():
    User.objects.create_user(username="alice")
    requester = User.objects.create_user(username="requester_nul")
    client = APIClient()
    client.force_authenticate(requester)

    resp = client.get(f"/forum/users/search/?q=ali{NUL}")

    assert resp.status_code == 200
    assert resp.data == []


USERNAME_ROUTES = [
    ("get", "/forum/users/{u}/"),
    ("post", "/forum/users/{u}/block/"),
    ("delete", "/forum/users/{u}/block/"),
    ("post", "/forum/users/{u}/mute/"),
    ("delete", "/forum/users/{u}/mute/"),
    ("post", "/forum/users/{u}/messages/"),
    ("get", "/forum/conversations/with/{u}/"),
    ("delete", "/forum/conversations/{c}/participants/{u}/"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("method,route", USERNAME_ROUTES)
def test_a_nul_username_in_the_url_is_not_found(method, route):
    User.objects.create_user(username="alice")
    User.objects.create_user(username="bob")
    requester = User.objects.create_user(username="requester_nul_path")
    client = APIClient()
    client.force_authenticate(requester)
    # A real group the requester created, so the participant route gets past
    # its conversation lookup to the username one.
    group = client.post(
        "/forum/conversations/",
        {"title": "Seed swap", "usernames": ["alice", "bob"], "body": "hello"},
        format="json",
    )
    assert group.status_code == 201, group.data

    resp = getattr(client, method)(
        route.format(c=group.data["id"], u=f"ali{NUL}ce"),
        {"body": "hi"},
        format="json",
    )

    assert resp.status_code == 404
