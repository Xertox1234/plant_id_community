# Forum Spec 2 — PR-1: Backend Cleanup (AC1 schema + AC3 compound sync cursor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the two self-contained backend acceptance criteria of todo 231 — read-view OpenAPI annotations (AC1) and a livelock-proof compound `(updated_at, id)` delta-sync cursor (AC3) — as one low-risk PR that introduces no route changes and keeps the host route-parity test green.

**Architecture:** Both changes are internal to the reusable `wagtail_forum` package (`backend/packages/wagtail_forum/`). AC1 decorates the existing `TopicDetailView`/`PostListView` with `@extend_schema` and adds `swagger_fake_view` guards to their `get_queryset` (required because `PostListView.get_queryset` calls `get_object_or_404`, which would raise during schema generation). AC3 changes `SyncView` from a `updated_at >= since` filter to a strict compound-key filter, adding a `next_since_id` continuation field while leaving the existing `next_since` field untouched (backward-compatible — the two existing sync tests keep passing). The host throttled wrappers subclass the package views, so no host edit is needed and `app_name`/route names are unchanged → route-parity test untouched.

**Tech Stack:** Django 5 / DRF, drf-spectacular, Wagtail, pytest + `pytest-django`, real Postgres (CI) / SQLite (backend-checks).

## Global Constraints

- **No plant imports in the package core** — `wagtail_forum` is zero-plant-coupling; a reusability test runs against a minimal settings module. Add nothing that imports from `apps/`.
- **`versioning_class = None` on every forum view** — already set on both views being touched; do not remove. Omitting it is a silent 404 under the host's `NamespaceVersioning`.
- **No route adds/renames in this PR** — keep the host route-parity test (`apps/forum_host/tests/test_ratelimits.py::test_host_api_routes_match_package`) green with zero edits to `api_urls.py`.
- **Optional schema import** — `extend_schema` is imported through the existing try/except shim at `views.py:15-23` (hosts without drf-spectacular still import the module). Reuse that symbol; do not add a hard `drf_spectacular` import.
- **Test invocation** — forum API tests set `pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")` and hit `APIClient().get("/forum/…")`. Match this exactly in new tests.
- **Run tests from `backend/`** with the venv active: `cd backend && source venv/bin/activate`.

---

## Epic roadmap (context — NOT part of this PR)

This PR is the first of three that together close todo 231 (forum Spec 2). Plans
for PR-2 and PR-3 are written when each is reached (PR-2's web composer tasks are
gated on a TipTap→StreamField round-trip spike).

- **PR-1 (this plan):** AC1 read-view `@extend_schema` + AC3 compound sync cursor. Backend-only, no route changes.
- **PR-2 (write path):** route rationalization (`…/topics/create/` → `POST …/topics/`; `…/posts/create/` → `POST …/posts/`), new `PostUpdateView` (PATCH) + `PostDeleteView` (DELETE) per resolved Q1/Q2/Q3, migrate `forumService.ts` write fns (`createThread`/`createPost`/edit/delete/reactions) off the machina dialect, re-enable the web compose/edit/delete/react UI, update host wrappers + route-parity + rate-limit tests in lockstep.
- **PR-3 (images):** `PostImageUploadView` (4-layer validation into a forum-scoped Wagtail collection), relax `validate_forum_body` to accept in-collection `image` blocks (IDOR-safe), add the `image` case to the web `StreamFieldRenderer`, wire the client image flow.

After PR-2 lands, AC2 (web off machina) flips; AC4 (route-parity green with the final URL surface) is satisfied continuously by every PR keeping the parity test green. Todo 231 archives only after PR-3.

---

## File Structure

| File | Responsibility | PR-1 change |
|------|----------------|-------------|
| `backend/packages/wagtail_forum/wagtail_forum/api/views.py` | DRF views | Annotate `TopicDetailView`/`PostListView` (AC1); rewrite `SyncView.get` filter + add `next_since_id` (AC3) |
| `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py` | **New** — AC1 verification | Assert read-view operations appear in the generated OpenAPI schema with a documented 200 |
| `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py` | Sync/search API tests | Add the same-timestamp livelock test (AC3); refresh one stale comment |

---

## Task 1: AC1 — annotate read views + `swagger_fake_view` guards

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (`TopicDetailView` ~L128-137, `PostListView` ~L139-150)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py` (new)

**Interfaces:**

- Consumes: the existing `extend_schema` shim symbol (`views.py:15-23`); serializers `TopicDetailSerializer`, `PostSerializer` (already imported in `views.py:32-41`).
- Produces: `TopicDetailView` and `PostListView` carry class-level `@extend_schema`; their `get_queryset` returns `Model.objects.none()` when `getattr(self, "swagger_fake_view", False)`.

- [ ] **Step 1: Write the failing test**

Create `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py`:

```python
"""AC1: the read endpoints are OpenAPI-annotated (todo 231).

Generating the schema also exercises the swagger_fake_view guards — without
them, PostListView.get_queryset's get_object_or_404 raises during generation.
"""

import pytest

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_read_views_appear_in_openapi_schema_with_documented_200():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    detail = paths["/forum/topics/{topic_id}/"]["get"]
    assert detail["responses"]["200"]["content"]["application/json"]["schema"]
    assert detail.get("description")

    post_list = paths["/forum/topics/{topic_id}/posts/"]["get"]
    assert post_list["responses"]["200"]["content"]["application/json"]["schema"]
    assert post_list.get("description")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py -v`
Expected: FAIL — either `KeyError`/missing `description` (views not yet annotated) or a drf-spectacular generation error from `PostListView`'s un-guarded `get_object_or_404`.

- [ ] **Step 3: Annotate the views and guard their querysets**

In `views.py`, replace the `TopicDetailView` class (currently L128-137) with:

```python
@extend_schema(
    responses={200: TopicDetailSerializer, 404: dict},
    description=(
        "Retrieve a topic's detail. Returns 404 for a non-live topic or a "
        "topic on a hidden/non-live board (no existence leak)."
    ),
)
class TopicDetailView(generics.RetrieveAPIView):
    serializer_class = TopicDetailSerializer
    versioning_class = None
    lookup_url_kwarg = "topic_id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        return Topic.objects.filter(
            live=True, board__in=_visible_boards()
        ).select_related("board", "author", "last_post_author")
```

Replace the `PostListView` class (currently L139-150) with:

```python
@extend_schema(
    responses={200: PostSerializer(many=True)},
    description=(
        "List a topic's live posts, oldest first (cursor-paginated). Returns "
        "404 if the topic is non-live or on a hidden/non-live board."
    ),
)
class PostListView(generics.ListAPIView):
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination
    versioning_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Post.objects.none()
        topic = get_object_or_404(
            Topic.objects.filter(live=True, board__in=_visible_boards()),
            id=self.kwargs["topic_id"],
        )
        return topic.posts.filter(live=True).select_related("author")
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Verify the project schema command still succeeds (CI backend-checks gate)**

Run: `cd backend && source venv/bin/activate && python manage.py spectacular --file /tmp/schema.yml 2>&1 | tail -5`
Expected: exits 0 and writes the file (warnings are acceptable/pre-existing; an **error** is a regression). Confirm no new error mentions `TopicDetailView` or `PostListView`.

- [ ] **Step 6: Confirm read-path query-count pins still pass (no behaviour change)**

Run: `cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py -v`
Expected: PASS (the guard only changes behaviour under `swagger_fake_view`, never at request time).

- [ ] **Step 7: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_schema.py
git commit -m "231(AC1): OpenAPI-annotate forum read views + swagger_fake_view guards"
```

---

## Task 2: AC3 — compound `(updated_at, id)` sync cursor + livelock test

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (`SyncView.get` ~L429-464; add `Q` import at top)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py` (add one test; refresh one comment)

**Interfaces:**

- Consumes: `Topic.Meta` already declares `models.Index(fields=["updated_at", "id"], condition=Q(live=True))` (`models/topics.py:89`) — the compound filter/order rides this partial index.
- Produces: `/forum/sync/` accepts an optional `since_id` query param (int, default 0) and returns a new `next_since_id` field alongside the unchanged `next_since`.

- [ ] **Step 1: Write the failing livelock test**

Add to `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py`:

```python
@pytest.mark.django_db
def test_sync_compound_cursor_advances_through_same_timestamp_rows(monkeypatch):
    """AC3: >MAX_TOPICS topics sharing one updated_at must paginate, not livelock.

    The old `updated_at >= since` cursor returned the same first page forever
    when a whole page shared one timestamp (bulk import). The compound
    (updated_at, id) cursor advances by id within the tie.
    """
    from wagtail_forum.api import views as forum_views

    monkeypatch.setattr(forum_views.SyncView, "MAX_TOPICS", 2)
    board = _board()
    ids = []
    for i in range(3):
        t = Topic.objects.create(board=board, title=f"t{i}", slug=f"t{i}", live=True)
        ids.append(t.id)
    shared = datetime.datetime(2026, 6, 23, tzinfo=datetime.timezone.utc)
    Topic.objects.filter(id__in=ids).update(updated_at=shared)
    ids.sort()  # order_by("updated_at", "id") => ascending id within the tie

    client = APIClient()
    page1 = client.get(f"/forum/sync/?board={board.slug}").data
    assert [t["id"] for t in page1["topics"]] == ids[:2]
    assert page1["has_more"] is True

    since = page1["next_since"]
    since_id = page1["next_since_id"]
    if not isinstance(since, str):  # DRF may render datetime un-serialized in .data
        since = since.isoformat()
    page2 = client.get(
        f"/forum/sync/?board={board.slug}&since={since}&since_id={since_id}"
    ).data
    # Progress: the third row only, never a repeat of the first page.
    assert [t["id"] for t in page2["topics"]] == [ids[2]]
    assert page2["has_more"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && python -m pytest "packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py::test_sync_compound_cursor_advances_through_same_timestamp_rows" -v`
Expected: FAIL — `KeyError: 'next_since_id'` (field not yet returned), or `page2` repeats `ids[:2]` (old gte cursor livelocks).

- [ ] **Step 3: Implement the compound cursor**

In `views.py`, add `Q` to the Django imports near the top (the file already has `from django.db import IntegrityError, transaction`):

```python
from django.db.models import Q
```

Replace the body of `SyncView.get` (currently L429-464) — from `raw_since = …` through the final `return Response(...)` — with:

```python
        raw_since = request.query_params.get("since", "")
        since = None
        if raw_since:
            since = parse_datetime(raw_since)
            if since is None or timezone.is_naive(since):
                # A silently-ignored bad value degrades to a full resync; a
                # naive datetime is interpreted in the server TZ (audit M11).
                raise ValidationError(
                    {"since": "Provide an ISO-8601 datetime with a timezone offset."}
                )
        try:
            since_id = int(request.query_params.get("since_id", 0) or 0)
        except (TypeError, ValueError):
            raise ValidationError({"since_id": "Provide an integer topic id."})

        qs = Topic.objects.filter(live=True, board__in=_visible_boards())
        board_slug = request.query_params.get("board")
        if board_slug:
            qs = qs.filter(board__slug=board_slug)
        if since:
            # Strict compound-key cursor: advance past every row already seen
            # (updated_at, id) without re-sending the boundary row and without
            # livelocking when a full page shares one updated_at (bulk import).
            # since_id defaults to 0, so a `since` with no `since_id` behaves like
            # the old >= boundary (first sync loses nothing).
            qs = qs.filter(
                Q(updated_at__gt=since) | Q(updated_at=since, id__gt=since_id)
            )
        batch = list(qs.order_by("updated_at", "id")[: self.MAX_TOPICS + 1])
        has_more = len(batch) > self.MAX_TOPICS
        batch = batch[: self.MAX_TOPICS]
        topics = [
            {"id": t.id, "slug": t.slug, "title": t.title, "updated_at": t.updated_at}
            for t in batch
        ]
        # Tombstones (ids deleted since `since`) require a soft-delete log added in
        # a later plan; return an empty list for now.
        return Response(
            {
                "topics": topics,
                "deleted": [],
                "has_more": has_more,
                "next_since": batch[-1].updated_at if batch else raw_since or None,
                "next_since_id": batch[-1].id if batch else (since_id or None),
            }
        )
```

Also update the `@extend_schema` description on `SyncView` (L420-428) to mention the compound cursor — replace the description string with:

```python
        description=(
            "Mobile delta-sync. Query params: since (ISO-8601, tz-aware), "
            "since_id (int, the last id seen at `since`), board (slug). Returns "
            "topics after the compound (updated_at, id) cursor plus has_more, "
            "next_since and next_since_id for continuation."
        ),
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `cd backend && source venv/bin/activate && python -m pytest "packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py::test_sync_compound_cursor_advances_through_same_timestamp_rows" -v`
Expected: PASS.

- [ ] **Step 5: Refresh the now-stale comment in the existing truncation test**

In the same file, in `test_sync_truncation_sets_has_more_and_boundary_next_since`, replace the comment:

```python
    # next_since is the LAST RETURNED row's timestamp; with the >= boundary the
    # client re-receives that row and upserts by id — never loses one.
```

with:

```python
    # next_since is the LAST RETURNED row's timestamp; paired with next_since_id
    # the compound cursor resumes strictly after it (no repeat, no loss).
```

- [ ] **Step 6: Run the full sync/search suite to confirm no regression**

Run: `cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py -v`
Expected: PASS — including the two pre-existing `next_since` assertions (unchanged field) and the new livelock test.

- [ ] **Step 7: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py
git commit -m "231(AC3): compound (updated_at, id) delta-sync cursor + livelock test"
```

---

## Task 3: Full-suite gate + route-parity confirmation

**Files:** none (verification only).

- [ ] **Step 1: Run the whole forum package API suite**

Run: `cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/ -q`
Expected: all pass (the Phase 1 baseline was 114 backend tests green; this adds 2).

- [ ] **Step 2: Confirm the host route-parity + rate-limit tests are untouched and green**

Run: `cd backend && source venv/bin/activate && python -m pytest apps/forum_host/tests/test_ratelimits.py -q`
Expected: PASS — this PR changed no routes, so parity holds with zero `api_urls.py` edits.

- [ ] **Step 3: Update the todo 231 work log**

Append a `### 2026-06-23 - PR-1 (backend cleanup) landed` entry to
`todos/231-*-forum-spec2-read-api-web-client.md` noting AC1 + AC3 are satisfied,
AC2/AC4 remain (PR-2/PR-3), and flip AC1 + AC3 checkboxes to `- [x]` with the
quoted passing-test summary. (The todo stays `pending`/`in_progress` — it archives
only after PR-3.)

- [ ] **Step 4: Commit the work-log update**

```bash
git add todos/231-*-forum-spec2-read-api-web-client.md
git commit -m "231: log PR-1 backend cleanup (AC1+AC3 done)"
```

---

## Self-Review

- **Spec coverage:** AC1 → Task 1; AC3 → Task 2; route-parity (AC4) preserved → Task 3 Step 2. AC2 + the write/image surface are explicitly out of this PR (Epic roadmap). The spec's "deferred — compound cursor + schema annotations" items are exactly AC3/AC1, now planned here.
- **Placeholder scan:** none — every code step shows full code; every run step shows the command + expected result.
- **Type consistency:** `next_since_id` returned in Task 2 Step 3 is the field asserted in Task 2 Step 1; `swagger_fake_view` guard added in Task 1 Step 3 is what Task 1 Step 1's schema generation depends on; `since_id` param parsed in Step 3 matches the test's query string in Step 1.
