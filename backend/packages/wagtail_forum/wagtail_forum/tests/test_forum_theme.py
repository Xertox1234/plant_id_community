"""Per-forum theme (todo 681): only the four listed themes, or none, are
accepted, and the forum row serves the stored value."""

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from wagtail_forum.models.boards import FORUM_THEME_CHOICES
from wagtail_forum.tests.factories import make_forum

pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]


def test_the_theme_list_is_the_owners_four():
    assert [value for value, _ in FORUM_THEME_CHOICES] == [
        "botanical",
        "moss",
        "terracotta",
        "slate",
    ]


@pytest.mark.parametrize("theme", ["", "botanical", "moss", "terracotta", "slate"])
def test_listed_themes_are_accepted(theme):
    forum = make_forum(name="Ferns", slug="ferns")
    forum.theme = theme
    forum.full_clean()


@pytest.mark.parametrize("theme", ["dark", "Moss", "neon", "moss; color:red"])
def test_unlisted_themes_are_rejected(theme):
    forum = make_forum(name="Ferns", slug="ferns")
    forum.theme = theme
    with pytest.raises(ValidationError) as exc:
        forum.full_clean()
    assert "theme" in exc.value.message_dict


def test_the_forum_row_serves_its_theme():
    make_forum(name="Ferns", slug="ferns", theme="terracotta")
    row = APIClient().get("/forum/categories/").json()["results"][0]["forums"][0]
    assert row["theme"] == "terracotta"
