import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_topics_list_is_cursor_paginated_with_bounded_queries():
    board = _board()
    author = User.objects.create_user(username="ada")
    # Live topics with DISTINCT last_post_at so the activity-ordered cursor is
    # deterministic. t0 is the most recent.
    base = timezone.now()
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=base - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None  # cursor link
    assert resp.data["results"][0]["slug"] == "t0"  # most-recent activity first
    # Exactly 3: board lookup (live+public), topics page (select_related pulls
    # author/last_post_author in the same query), cursor has-next probe.
    # Pinned EXACTLY (docs/rules/testing.md) — an N+1 hiding under a <= ceiling
    # passes silently; if this changes, explain the new number here.
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_pinned_topics_float_above_activity_ordering():
    # Audit 2026-07-11 H5: the cursor ordering ignored is_pinned, so a
    # moderator-pinned topic sank as normal activity accrued.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="Board rules",
        slug="rules",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=30),  # stale activity
    )
    Topic.objects.create(
        board=board,
        title="Fresh question",
        slug="fresh",
        author=author,
        live=True,
        last_post_at=base,
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["rules", "fresh"]


@pytest.mark.django_db
def test_list_payload_includes_locked_flag():
    # Audit 2026-07-11 L3: the write guard is `is_closed OR locked`, but the
    # list serializer omitted `locked` — a Wagtail-locked-but-open topic showed
    # no lock badge until opened.
    board = _board()
    author = User.objects.create_user(username="ada")
    Topic.objects.create(
        board=board,
        title="Locked topic",
        slug="locked-topic",
        author=author,
        live=True,
        locked=True,
        last_post_at=timezone.now(),
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    item = resp.data["results"][0]
    assert item["locked"] is True
    assert item["is_closed"] is False  # distinct flags, both serialized


@pytest.mark.django_db
def test_ordering_query_param_is_inert():
    # Phase 6 review (2026-07-11 audit): the views inherited the host's global
    # OrderingFilter, so a client ?ordering= replaced the cursor tuple entirely
    # (un-pinning pinned topics) and ?ordering=author__get_username — a dotted
    # serializer source, not a column — raised FieldError → an unauthenticated
    # 500 (both reproduced). filter_backends=[] makes list order a fixed
    # package contract regardless of host DEFAULT_FILTER_BACKENDS.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="AAA rules",  # alphabetically FIRST so -title would reorder
        slug="rules",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=30),
    )
    Topic.objects.create(
        board=board,
        title="ZZZ fresh",
        slug="fresh",
        author=author,
        live=True,
        last_post_at=base,
    )

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/", {"ordering": "-title"})
    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["rules", "fresh"]

    resp = client.get(
        f"/forum/boards/{board.slug}/topics/", {"ordering": "author__get_username"}
    )
    assert resp.status_code == 200  # was a FieldError 500
    assert [t["slug"] for t in resp.data["results"]] == ["rules", "fresh"]


@pytest.mark.django_db
def test_pinned_ordering_is_cursor_stable_across_pages():
    # The pinned-first ordering must not break cursor traversal: every topic
    # appears exactly once across pages, pinned ones all on page 1's head.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="Pinned old",
        slug="pinned-old",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=30),
    )
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=base - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.data["results"]]
    assert slugs[0] == "pinned-old"  # pinned heads page 1 despite stale activity

    # Follow the absolute cursor URL verbatim (docs/rules/api.md).
    while resp.data["next"]:
        resp = client.get(resp.data["next"])
        assert resp.status_code == 200
        slugs.extend(t["slug"] for t in resp.data["results"])

    assert len(slugs) == 26
    assert len(set(slugs)) == 26  # no duplicates, no omissions across pages
