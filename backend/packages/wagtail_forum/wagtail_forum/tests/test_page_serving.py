"""Audit 2026-07-11 H17: ForumIndex/ForumBoard are live-routable Pages; serving
them directly (admin "View live", sitemap entries, crawlers) must render the
minimal fallback template, not 500 with TemplateDoesNotExist. The SPA remains
the real forum UI."""

import pytest
from django.test import RequestFactory
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic


def _tree():
    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title="Forum", slug="forum", intro="<p>Welcome</p>")
    )
    board = index.add_child(
        instance=ForumBoard(title="General", slug="general", description="General talk")
    )
    return index, board


@pytest.mark.django_db
def test_forum_index_serves_directly():
    index, _board = _tree()

    response = index.serve(RequestFactory().get("/forum/"))
    response.render()

    assert response.status_code == 200
    html = response.content.decode()
    assert "Forum" in html
    assert "General" in html  # child board listed


@pytest.mark.django_db
def test_forum_board_serves_directly_and_lists_only_live_topics():
    _index, board = _tree()
    Topic.objects.create(board=board, title="Visible topic", slug="v", live=True)
    Topic.objects.create(board=board, title="Hidden draft", slug="h", live=False)

    response = board.serve(RequestFactory().get("/forum/general/"))
    response.render()

    assert response.status_code == 200
    html = response.content.decode()
    assert "Visible topic" in html
    assert "Hidden draft" not in html
