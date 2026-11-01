"""Per-forum topic template (todo 678): plain text, edited on the forum's
Posting tab and exposed on the forum rows of ``GET /forum/categories/``."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail_forum.models import Forum
from wagtail_forum.tests.factories import make_forum

pytestmark = pytest.mark.django_db
TEMPLATE = "What plant is it?\nWhat changed?\nPhotos of the leaves"


def _rows():
    resp = APIClient().get("/forum/categories/")
    assert resp.status_code == 200
    return {f["slug"]: f for c in resp.json()["results"] for f in c["forums"]}


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_the_forum_row_exposes_the_topic_template():
    make_forum(name="Problems", slug="problems", topic_template=TEMPLATE)
    make_forum(name="Chat", slug="chat")

    rows = _rows()

    assert rows["problems"]["topic_template"] == TEMPLATE
    assert rows["chat"]["topic_template"] == ""


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_the_flat_board_list_keeps_its_flutter_keys():
    make_forum(name="Problems", slug="problems", topic_template=TEMPLATE)

    board = APIClient().get("/forum/boards/").json()["results"][0]

    assert "topic_template" not in board


def test_the_posting_tab_saves_the_template(client):
    forum = make_forum(name="Problems", slug="problems")
    admin = get_user_model().objects.create_superuser(username="root")
    client.force_login(admin)

    resp = client.post(
        reverse("wagtail_forum_forums:edit", args=(forum.pk,)),
        {
            "parent": forum.parent_id,
            "name": forum.name,
            "slug": forum.slug,
            "description": "",
            "link_url": "",
            "topic_template": TEMPLATE,
            "moderator_users": "",
        },
    )

    assert resp.status_code == 302, resp.content.decode()[:3000]
    assert Forum.objects.get(pk=forum.pk).topic_template == TEMPLATE
