"""M40 (todo 277): pin the five list-envelope shapes the README documents.

The `## List envelopes` section of the package README is the authoritative
statement that these five shapes diverge *on purpose*. Prose alone re-rots — the
review of this very PR found the README's own `## Search backend` paragraph still
claiming search had "no pagination and no `has_more` flag" long after paging
shipped. So the top-level key set of each envelope is asserted here against a
live response: change a shape without changing the README (or vice versa) and
this goes red.

Deliberately TOP-LEVEL keys only. Item-level fields belong to the serializer
tests (`test_topics_list.py`, `test_post_list.py`, `test_search_sync.py`); this
file guards the envelope contract, which is the thing the README promises.
"""

import pytest
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

# One entry per row of the README's `## List envelopes` table.
CURSOR_ENVELOPE = {"results", "next", "previous"}
FLAT_ENVELOPE = {"results", "intro"}
SEARCH_ENVELOPE = {"topics", "posts", "topics_has_more", "posts_has_more", "page"}
SYNC_ENVELOPE = {"topics", "deleted", "has_more", "next_since", "next_since_id"}
RESULTS_ONLY_ENVELOPE = {"results"}


def _seeded_board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-env"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general-env"))
    topic = Topic.objects.create(
        board=board, title="Monstera care", slug="monstera-env", live=True
    )
    Post.objects.create(
        topic=topic,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>monstera watering</p>"}],
    )
    return board, topic


@pytest.mark.django_db
def test_board_list_is_the_flat_envelope():
    _seeded_board()
    resp = APIClient().get("/forum/boards/")
    assert resp.status_code == 200
    # Flat, NOT cursor: boards are few and unpaginated, so a permanently-null
    # `next` would imply paging that does not exist. `intro` (todo 278) is the
    # forum index's welcome copy — same screen, same fetch, so it rides here
    # instead of taking a second round-trip. Content is pinned in
    # test_board_list.py; this file guards only the key set.
    assert set(resp.json()) == FLAT_ENVELOPE


@pytest.mark.django_db
def test_topic_and_post_lists_are_the_cursor_envelope():
    board, topic = _seeded_board()
    for path in (
        f"/forum/boards/{board.slug}/topics/",
        f"/forum/topics/{topic.id}/posts/",
    ):
        resp = APIClient().get(path)
        assert resp.status_code == 200, path
        assert set(resp.json()) == CURSOR_ENVELOPE, path


@pytest.mark.django_db
def test_search_is_the_two_section_envelope():
    _seeded_board()
    resp = APIClient().get("/forum/search/", {"q": "monstera"})
    assert resp.status_code == 200
    # Two independently-paged sections in one response — the reason this cannot
    # become the single-`results` cursor envelope.
    assert set(resp.json()) == SEARCH_ENVELOPE


@pytest.mark.django_db
def test_sync_is_the_delta_envelope():
    _seeded_board()
    resp = APIClient().get("/forum/sync/")
    assert resp.status_code == 200
    # `deleted` (tombstones) and the resumable compound cursor are what no
    # `results` list can carry.
    assert set(resp.json()) == SYNC_ENVELOPE


@pytest.mark.django_db
def test_recent_topics_and_experts_are_the_results_only_envelope():
    _seeded_board()
    for path in ("/forum/topics/recent/", "/forum/users/experts/"):
        resp = APIClient().get(path)
        assert resp.status_code == 200, path
        assert set(resp.json()) == RESULTS_ONLY_ENVELOPE, path


@pytest.mark.django_db
def test_the_five_envelopes_are_actually_distinct():
    """Guards the premise, not just the shapes.

    If a future change quietly converged two of these, every assertion above
    could still pass while the README's "five shapes" framing became false.
    """
    shapes = [
        CURSOR_ENVELOPE,
        FLAT_ENVELOPE,
        SEARCH_ENVELOPE,
        SYNC_ENVELOPE,
        RESULTS_ONLY_ENVELOPE,
    ]
    assert len({frozenset(s) for s in shapes}) == 5
