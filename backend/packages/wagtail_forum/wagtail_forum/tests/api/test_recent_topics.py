"""Cross-board latest-topics rail: GET topics/recent/ (Task 5, Canopy PR)."""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumIndex,
    Post,
    Topic,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(board_slug="general", board_title="General"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title=board_title, slug=board_slug))


def _two_boards():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board_a = index.add_child(instance=ForumBoard(title="General", slug="general"))
    board_b = index.add_child(
        instance=ForumBoard(title="Show & Tell", slug="show-tell")
    )
    return board_a, board_b


@pytest.mark.django_db
def test_recent_topics_empty_forum_returns_empty_results():
    """No boards/topics at all -> the flat envelope with an empty list."""
    resp = APIClient().get("/forum/topics/recent/")
    assert resp.status_code == 200
    assert resp.data == {"results": []}


@pytest.mark.django_db
def test_recent_topics_orders_by_activity_across_boards():
    """Newest-activity-first, spanning boards, with correct board + reply_count.

    topic1 is created FIRST but its last_post_at is bumped (a later reply)
    PAST topic2's — proving the ordering key is last_post_at, not creation
    order or id.
    """
    board_a, board_b = _two_boards()
    author = User.objects.create_user(username="ada")
    now = timezone.now()

    topic1 = Topic.objects.create(
        board=board_a,
        title="Topic One",
        slug="topic-one",
        author=author,
        live=True,
        last_post_at=now - datetime.timedelta(minutes=10),
        reply_count=0,
    )
    topic2 = Topic.objects.create(
        board=board_b,
        title="Topic Two",
        slug="topic-two",
        author=author,
        live=True,
        last_post_at=now - datetime.timedelta(minutes=5),
        reply_count=0,
        # Positive case for is_pinned (topic1's is only asserted False below) —
        # this endpoint's order_by is `-last_post_at` alone, not
        # `-is_pinned, -last_post_at` like TopicListView, so pinning topic2
        # does not reorder the results and stays a pure serialization check.
        is_pinned=True,
    )
    # A later reply on topic1 bumps its activity past topic2's.
    topic1.last_post_at = now
    topic1.reply_count = 1
    topic1.save(update_fields=["last_post_at", "reply_count"])

    resp = APIClient().get("/forum/topics/recent/")
    assert resp.status_code == 200
    results = resp.data["results"]
    assert [r["id"] for r in results] == [topic1.id, topic2.id]
    assert results[0]["board"] == {
        "id": board_a.id,
        "name": "General",
        "slug": "general",
    }
    assert results[0]["reply_count"] == 1
    assert results[0]["is_pinned"] is False
    assert results[1]["board"] == {
        "id": board_b.id,
        "name": "Show & Tell",
        "slug": "show-tell",
    }
    assert results[1]["reply_count"] == 0
    assert results[1]["is_pinned"] is True


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_RECENT_TOPICS_MAX_LIMIT=2)
def test_recent_topics_limit_is_respected_and_capped():
    """?limit= is honored when under the cap, and clamped when over it."""
    board = _board()
    author = User.objects.create_user(username="ada")
    now = timezone.now()
    topics = [
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=now - datetime.timedelta(minutes=i),
        )
        for i in range(3)
    ]
    client = APIClient()

    resp = client.get("/forum/topics/recent/", {"limit": 1})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    assert resp.data["results"][0]["id"] == topics[0].id  # most recent activity

    # WAGTAILFORUM_RECENT_TOPICS_MAX_LIMIT=2 above; 3 topics exist, so an
    # explicit ?limit= above the cap is clamped, not honored verbatim.
    resp = client.get("/forum/topics/recent/", {"limit": 100})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 2


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_RECENT_TOPICS_DEFAULT_LIMIT=2)
def test_recent_topics_uses_default_limit_when_omitted():
    """No ?limit= at all -> RECENT_TOPICS_DEFAULT_LIMIT applies.

    This is the endpoint's most-exercised production call shape (the landing
    rail never sends ?limit=), and `int(request.query_params.get("limit",
    ""))` takes the `except ValueError` branch to reach it — untested by the
    explicit-?limit= cases above, which never exercise the omitted-param path.
    """
    board = _board()
    author = User.objects.create_user(username="ada")
    now = timezone.now()
    for i in range(3):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=now - datetime.timedelta(minutes=i),
        )

    resp = APIClient().get("/forum/topics/recent/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 2  # the overridden default, not all 3


@pytest.mark.django_db
def test_recent_topics_thumbnail_resolution():
    """Three sources for thumbnail_url: opening-post image, identification
    attachment (fallback), and neither -> null.

    "a topic with neither image -> null" implies a THIRD topic with an
    attachment image but no body image, to prove the fallback branch (not
    just the "there is definitely no image anywhere" branch) actually runs.
    """
    board = _board()
    author = User.objects.create_user(username="ada")
    collection = get_forum_image_collection()
    now = timezone.now()

    # 1) Opening post carries an image block.
    body_image = get_image_model().objects.create(
        title="body.jpg", file=get_test_image_file(), collection=collection
    )
    topic_body_image = Topic.objects.create(
        board=board,
        title="Body image",
        slug="body-image",
        author=author,
        live=True,
        last_post_at=now,
    )
    Post.objects.create(
        topic=topic_body_image,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "image", "value": body_image.id}],
    )

    # 2) No body image, but an identification-attachment image (fallback path,
    #    api/views.py's `image_id_by_topic.setdefault(att.topic_id, ...)`).
    attachment_image = get_image_model().objects.create(
        title="attachment.jpg", file=get_test_image_file(), collection=collection
    )
    topic_attachment_image = Topic.objects.create(
        board=board,
        title="Attachment image",
        slug="attachment-image",
        author=author,
        live=True,
        last_post_at=now - datetime.timedelta(minutes=1),
    )
    Post.objects.create(
        topic=topic_attachment_image,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>no image in the body</p>"}],
    )
    ForumIdentificationAttachment.objects.create(
        topic=topic_attachment_image,
        image=attachment_image,
        provider="plant_id",
        candidates=[
            {
                "name": "Monstera deliciosa",
                "scientific_name": "Monstera deliciosa",
                "confidence": 0.9,
            }
        ],
    )

    # 3) Neither a body image nor an attachment image.
    topic_no_image = Topic.objects.create(
        board=board,
        title="No image",
        slug="no-image",
        author=author,
        live=True,
        last_post_at=now - datetime.timedelta(minutes=2),
    )
    Post.objects.create(
        topic=topic_no_image,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>text only</p>"}],
    )

    resp = APIClient().get("/forum/topics/recent/")
    assert resp.status_code == 200
    by_id = {r["id"]: r for r in resp.data["results"]}

    body_thumb = by_id[topic_body_image.id]["thumbnail_url"]
    assert body_thumb is not None
    assert body_thumb.startswith("http://testserver")  # absolute URL

    attachment_thumb = by_id[topic_attachment_image.id]["thumbnail_url"]
    assert attachment_thumb is not None
    assert attachment_thumb.startswith("http://testserver")

    assert by_id[topic_no_image.id]["thumbnail_url"] is None


@pytest.mark.django_db
def test_recent_topics_excludes_non_live_topics():
    board = _board()
    author = User.objects.create_user(username="ada")
    now = timezone.now()
    live_topic = Topic.objects.create(
        board=board,
        title="Live",
        slug="live",
        author=author,
        live=True,
        last_post_at=now,
    )
    Topic.objects.create(
        board=board,
        title="Hidden",
        slug="hidden",
        author=author,
        live=False,
        last_post_at=now,
    )

    resp = APIClient().get("/forum/topics/recent/")
    assert resp.status_code == 200
    assert [r["id"] for r in resp.data["results"]] == [live_topic.id]


@pytest.mark.django_db
def test_recent_topics_query_count_is_pinned():
    """Query-count pin: 5 topics, 2 carrying an opening-post image.

    Q1: `_visible_boards()`'s `.public()` EAGERLY evaluates
        `PageViewRestriction.objects.select_related("page").all()` inside
        `wagtail/query.py`'s `private_q()` (a plain Python `for` loop over the
        queryset, run the moment `.public()` is called) to build its exclusion
        Q object — one query, independent of board/topic count. This is the
        ".public() costs one extra query" rule from docs/rules/testing.md.
    Q2: the topics page itself — `select_related("board")` folds the board
        join into this same SELECT, so it costs no separate query.
    Q3: opening posts for all 5 topics in one query
        (`topic_id__in=topic_ids, is_opening_post=True, live=True`) — flat
        regardless of how many of the 5 carry a body image block.
    Q4: `ForumIdentificationAttachment` lookup for all 5 topics — ONE query,
        even though this fixture creates zero attachment rows (the query
        still executes; a topic-count-scaled version would be the bug this
        pin exists to catch).
    Q5: `Image.objects.in_bulk()` batching every image id collected above —
        ONE query for both of this fixture's images. NOTE: `in_bulk([])`
        short-circuits with ZERO queries (Django), so a fixture with no
        images at all would pin 4, not 5 — the empty-forum test above
        legitimately has a different count for this reason, not by mistake.

    Rendition lookups (`thumb()`'s `image.get_rendition("fill-80x80")`,
    called once per topic, NOT batched via `prefetch_renditions`) add ZERO
    further queries in this pinned, WARMED measurement — empirically
    verified, not assumed. This view calls `get_rendition()` per-topic, but
    Wagtail's own `AbstractImage.find_existing_renditions` checks
    `Rendition.cache_backend` (a Django cache, e.g. LocMemCache in tests)
    BEFORE ever touching the database, and `get_rendition()` populates that
    cache on every call (hit or miss). So after the warm-up GET below
    populates the cache for both images, the pinned GET's two
    `get_rendition()` calls are served entirely from cache — the DB is never
    touched for them, which is a genuinely different (better) mechanism than
    `test_post_list.py`'s `prefetch_renditions()` batching, not the same one.

    This is still the correct thing to pin: the FIRST-EVER request for an
    image (uncached) pays a real SELECT+INSERT per image-bearing topic (this
    view issues one `get_rendition()` call per topic, so that part IS
    per-topic, not batched) — `test_recent_topics_thumbnail_resolution`
    above exercises that cold path directly and asserts it resolves a real
    URL. Per docs/rules/testing.md ("Wagtail GENERATES a rendition on first
    access, which is indistinguishable from an N+1... warm every request
    whose count you compare"), this pin measures the STEADY STATE — the
    request pattern every request after the first actually sees in
    production, once Wagtail's rendition cache is warm — not the one-time
    cold cost, which is inherent to Wagtail's rendition system everywhere in
    this codebase, not specific to this view.

    Total: 5. Pre-warmed with an identical GET before the pinned request
    (`test_post_list.py`'s idiom).

    Pinned EXACTLY (docs/rules/testing.md) — explain any change to this number.
    """
    board = _board()
    author = User.objects.create_user(username="ada")
    collection = get_forum_image_collection()
    now = timezone.now()

    for i in range(5):
        topic = Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=now - datetime.timedelta(minutes=i),
        )
        if i < 2:
            # Distinct images per topic so get_rendition() is never called
            # twice on the same Image instance (which could mask an N+1).
            image = get_image_model().objects.create(
                title=f"img{i}.jpg", file=get_test_image_file(), collection=collection
            )
            body = [{"type": "image", "value": image.id}]
        else:
            body = [{"type": "paragraph", "value": "<p>text</p>"}]
        Post.objects.create(
            topic=topic, author=author, is_opening_post=True, live=True, body=body
        )

    client = APIClient()
    # Warm renditions (generated once, then cached) so the pin measures the
    # production steady state, not first-render rendition generation — same
    # idiom as test_post_list.py::test_post_list_with_images_is_not_n_plus_one.
    assert client.get("/forum/topics/recent/").status_code == 200
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/topics/recent/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 5
    assert len(ctx.captured_queries) == 5
