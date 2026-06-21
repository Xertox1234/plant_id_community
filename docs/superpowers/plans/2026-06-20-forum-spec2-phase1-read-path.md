# Forum Spec 2 — Phase 1 (Read Path) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deployed web forum browsable again by building the two missing read endpoints (topic detail + post list), extending search to posts, seeding a default board, and migrating the React read path off the retired machina API — killing the live "Error loading categories: Request failed."

**Architecture:** Add `TopicDetailView` + `PostListView` (cursor-paginated) to the `wagtail_forum` package, mount them unwrapped in `forum_host` (matching the existing read-view precedent), extend the package `SearchView` to also search post bodies, and add an idempotent `seed_default_forum` management command. Then rewrite the read half of the React forum client to the new contract and render post bodies as StreamField JSON via the existing `StreamFieldRenderer`.

**Tech Stack:** Django 5 / DRF, Wagtail 7 (snippets, StreamField, `expand_db_html`), pytest + `CaptureQueriesContext`; React 19 + TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-20-forum-spec2-read-write-client-design.md` (Phase 1 only).

## Global Constraints

- **Every new DRF view MUST set `versioning_class = None`** — the host mounts the package under a `NamespaceVersioning` `v1` namespace that 404s package routes otherwise.
- **No plant imports in `backend/packages/wagtail_forum/`** — the package core stays domain-agnostic (a reusability test enforces this).
- **Route-parity test must stay green** — every package route in `wagtail_forum/api/urls.py` must have an identical `(pattern, name)` entry in `apps/forum_host/api_urls.py` (`apps/forum_host/tests/test_ratelimits.py::test_host_api_routes_match_package`).
- **No DB mocks; real Postgres test DB.** Query counts are pinned **exactly** (`len(ctx.captured_queries) == N`), never `<=` (per `docs/rules/testing.md`).
- **Post body is StreamField JSON.** On read, `paragraph` (RichText) blocks are serialized through Wagtail `expand_db_html()` — never raw `value.source`.
- **Visibility rule:** a hidden/draft topic, or one on a non-live/restricted board, is **404** (never 403) — mirror `_visible_boards()` = `ForumBoard.objects.live().public()`.
- **Backend tests** run with `pytest.mark.urls("wagtail_forum.tests.api.urls")` and hit paths under `/forum/...`. **Web CI gates:** `npm run type-check`, `npm run lint`, `npm run test` must pass.

---

## File Structure

**Backend (package — `backend/packages/wagtail_forum/wagtail_forum/`):**

- `api/serializers.py` — add `serialize_forum_body()`, `TopicDetailSerializer`, `PostSerializer`.
- `api/pagination.py` — add `PostCursorPagination`.
- `api/views.py` — add `TopicDetailView`, `PostListView`; extend `SearchView` to topics + posts.
- `api/urls.py` — add `topic-detail` + `post-list` routes.
- `tests/api/test_topic_detail.py`, `tests/api/test_post_list.py` — new.
- `tests/api/test_search_sync.py` — extend for post hits.

**Backend (host — `backend/apps/forum_host/`):**

- `api_urls.py` — mount the two new read views (unwrapped).
- `management/commands/seed_default_forum.py` — new, idempotent board seeding.
- `tests/test_seed_command.py` — new.

**Web (`web/src/`):**

- `services/forumMappers.ts` — replace machina backend shapes with the new API shapes + mappers.
- `services/forumService.ts` — rewrite read functions to the new contract.
- `types/forum.ts` — adjust types (cursor pagination, StreamField body).
- `pages/forum/CategoryListPage.tsx`, `ThreadListPage.tsx`, `ThreadDetailPage.tsx` (read only), `SearchPage.tsx` — update to the new service.
- `components/forum/PostCard.tsx` — render `post.body` via `StreamFieldRenderer`.
- Corresponding `*.test.ts(x)` files.

---

## Task 1: Topic detail endpoint

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Modify: `backend/apps/forum_host/api_urls.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py`

**Interfaces:**

- Produces: `TopicDetailSerializer` (fields below); `TopicDetailView` (GET `topics/<int:topic_id>/`, name `topic-detail`).

- [ ] **Step 1: Write the failing test**

Create `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


@pytest.mark.django_db
def test_topic_detail_returns_live_topic():
    board = _board()
    author = User.objects.create_user(username="ada", password="x")
    topic = Topic.objects.create(
        board=board, title="Hello", slug="hello", author=author, live=True
    )
    opening = Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True
    )

    resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200
    assert resp.data["id"] == topic.id
    assert resp.data["title"] == "Hello"
    assert resp.data["board"]["slug"] == "general"
    assert resp.data["author"] == "ada"
    assert resp.data["opening_post_id"] == opening.id


@pytest.mark.django_db
def test_topic_detail_hides_draft_topic():
    board = _board()
    topic = Topic.objects.create(board=board, title="Draft", slug="draft", live=False)
    assert APIClient().get(f"/forum/topics/{topic.id}/").status_code == 404


@pytest.mark.django_db
def test_topic_detail_hides_topic_on_unpublished_board():
    board = _board()
    board.live = False
    board.save()
    topic = Topic.objects.create(board=board, title="X", slug="x", live=True)
    assert APIClient().get(f"/forum/topics/{topic.id}/").status_code == 404
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd backend && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py -v`
Expected: FAIL — 404 (route does not exist yet).

- [ ] **Step 3: Add `TopicDetailSerializer`**

In `api/serializers.py`, after `TopicListSerializer`, add:

```python
class TopicDetailSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.get_username", default=None)
    last_post_author = serializers.CharField(
        source="last_post_author.get_username", default=None
    )
    board = serializers.SerializerMethodField()
    opening_post_id = serializers.SerializerMethodField()
    locked = serializers.BooleanField()

    class Meta:
        model = Topic
        fields = [
            "id",
            "title",
            "slug",
            "board",
            "author",
            "is_pinned",
            "is_closed",
            "locked",
            "reply_count",
            "view_count",
            "created_at",
            "last_post_at",
            "last_post_author",
            "opening_post_id",
        ]

    def get_board(self, obj):
        return {"id": obj.board.id, "slug": obj.board.slug, "title": obj.board.title}

    def get_opening_post_id(self, obj):
        post = obj.posts.filter(is_opening_post=True, live=True).only("id").first()
        return post.id if post else None
```

- [ ] **Step 4: Add `TopicDetailView`**

In `api/views.py`, after `TopicListView`, add (note `_visible_boards()` already exists in this module):

```python
class TopicDetailView(generics.RetrieveAPIView):
    serializer_class = TopicDetailSerializer
    versioning_class = None
    lookup_url_kwarg = "topic_id"

    def get_queryset(self):
        return (
            Topic.objects.filter(live=True, board__in=_visible_boards())
            .select_related("board", "author", "last_post_author")
        )
```

Add `TopicDetailSerializer` to the `from .serializers import (...)` block.

- [ ] **Step 5: Register the route (package + host)**

In `api/urls.py`, add to `urlpatterns` (import `TopicDetailView`):

```python
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
```

In `apps/forum_host/api_urls.py`, add `TopicDetailView` to the
`from wagtail_forum.api.views import ...` line and add the **identical** route:

```python
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
```

- [ ] **Step 6: Run the tests, verify they pass**

Run: `cd backend && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py apps/forum_host/tests/test_ratelimits.py::test_host_api_routes_match_package -v`
Expected: PASS (detail tests + parity guard).

- [ ] **Step 7: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/serializers.py \
        backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/api/urls.py \
        backend/apps/forum_host/api_urls.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py
git commit -m "feat(forum): add GET /topics/{id}/ topic-detail endpoint"
```

---

## Task 2: Post list endpoint (cursor-paginated, StreamField body)

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/pagination.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Modify: `backend/apps/forum_host/api_urls.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py`

**Interfaces:**

- Consumes: `_board()` test helper, `_visible_boards()`.
- Produces: `serialize_forum_body(stream_value) -> list[dict]`; `PostSerializer`; `PostCursorPagination`; `PostListView` (GET `topics/<int:topic_id>/posts/`, name `post-list`).

- [ ] **Step 1: Write the failing test (body shape + query-count pin)**

Create `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _topic_with_posts(n):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada", password="x")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    for i in range(n):
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=(i == 0),
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )
    return topic


@pytest.mark.django_db
def test_post_list_serializes_streamfield_body():
    topic = _topic_with_posts(1)
    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    post = resp.data["results"][0]
    assert post["topic_id"] == topic.id
    assert post["author"]["username"] == "ada"
    assert post["is_opening_post"] is True
    assert post["body"] == [{"type": "paragraph", "value": "<p>hi</p>", "id": post["body"][0]["id"]}]
    assert post["reaction_counts"] == {}
    assert post["can_edit"] is False  # anonymous


@pytest.mark.django_db
def test_post_list_is_cursor_paginated_with_bounded_queries():
    topic = _topic_with_posts(25)
    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None
    # topic visibility lookup, posts page (select_related author), cursor has-next probe.
    # Pinned EXACTLY (docs/rules/testing.md). If this changes, explain the new number.
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_post_list_hides_posts_on_hidden_topic():
    topic = _topic_with_posts(1)
    topic.live = False
    topic.save()
    assert APIClient().get(f"/forum/topics/{topic.id}/posts/").status_code == 404
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd backend && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py -v`
Expected: FAIL — 404 (route missing).

- [ ] **Step 3: Add the body serializer + `PostSerializer`**

In `api/serializers.py`, add near the top (imports) and after `TopicDetailSerializer`:

```python
from wagtail.blocks import RichTextBlock
from wagtail.rich_text import expand_db_html

from ..models import Post  # add Post to the existing model import


def serialize_forum_body(stream_value):
    """StreamField -> [{type, value, id}] for the React StreamFieldRenderer.

    RichText (paragraph) blocks are run through expand_db_html() so Wagtail's
    link rewriter runs (SECURITY: blocks.py:18-21) — never raw value.source.
    Phase 1 bodies contain only text blocks (heading/paragraph/quote/code);
    image-block rendition serialization arrives in Phase 3.
    """
    blocks = []
    for bound in stream_value:
        if isinstance(bound.block, RichTextBlock):
            value = expand_db_html(bound.value.source)
        else:
            value = bound.block.get_api_representation(bound.value)
        blocks.append({"type": bound.block_type, "value": value, "id": bound.id})
    return blocks


class PostAuthorSerializer(serializers.Serializer):
    username = serializers.CharField(source="get_username")
    display_name = serializers.SerializerMethodField()
    trust_level = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        full = obj.get_full_name()
        return full or obj.get_username()

    def get_trust_level(self, obj):
        return None  # populated in a later plan when ForumProfile is joined


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField()
    edited_at = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "topic_id",
            "author",
            "body",
            "created_at",
            "updated_at",
            "edited_at",
            "is_opening_post",
            "status",
            "reaction_counts",
            "can_edit",
            "can_delete",
        ]

    def get_author(self, obj):
        if obj.author is None:
            return {"username": "[deleted]", "display_name": "[deleted]", "trust_level": None}
        return PostAuthorSerializer(obj.author).data

    def get_body(self, obj):
        return serialize_forum_body(obj.body)

    def get_edited_at(self, obj):
        return obj.updated_at if obj.edited else None

    def get_status(self, obj):
        return "live" if obj.live else "pending"

    def _is_owner_or_mod(self, obj):
        user = self.context.get("request").user if self.context.get("request") else None
        if not user or not user.is_authenticated:
            return False
        return user == obj.author or user.has_perm("wagtail_forum.change_post")

    def get_can_edit(self, obj):
        return self._is_owner_or_mod(obj)

    def get_can_delete(self, obj):
        return self._is_owner_or_mod(obj)
```

Note: `edited_by` is intentionally omitted — the `Post` model has no such field (a future `edited_by` is out of scope; `PostCard` already renders the "by …" clause conditionally).

- [ ] **Step 4: Add `PostCursorPagination`**

In `api/pagination.py`, add:

```python
class PostCursorPagination(ForumCursorPagination):
    # Posts read oldest-first (Post.Meta.ordering = ["created_at"]); id is the
    # unique tiebreak that keeps the cursor deterministic when created_at ties.
    ordering = ("created_at", "id")
```

- [ ] **Step 5: Add `PostListView`**

In `api/views.py`, after `TopicDetailView`, add (import `PostSerializer`, `PostCursorPagination`):

```python
class PostListView(generics.ListAPIView):
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination
    versioning_class = None

    def get_queryset(self):
        topic = get_object_or_404(
            Topic.objects.filter(live=True, board__in=_visible_boards()),
            id=self.kwargs["topic_id"],
        )
        return topic.posts.filter(live=True).select_related("author")
```

- [ ] **Step 6: Register the route (package + host)**

In `api/urls.py` add (import `PostListView`):

```python
    path(
        "topics/<int:topic_id>/posts/",
        PostListView.as_view(),
        name="post-list",
    ),
```

In `apps/forum_host/api_urls.py` add `PostListView` to the package-views import and the **identical** route.

- [ ] **Step 7: Run the tests, verify they pass**

Run: `cd backend && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py apps/forum_host/tests/test_ratelimits.py -v`
Expected: PASS. If the query-count assertion is off, read the captured queries and adjust the pin **with an explanation comment** — do not loosen to `<=`.

- [ ] **Step 8: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/ backend/apps/forum_host/api_urls.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py
git commit -m "feat(forum): add GET /topics/{id}/posts/ cursor-paginated post list"
```

---

## Task 3: Extend search to post bodies (full parity)

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (`SearchView`)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py`

**Interfaces:**

- Consumes: `Post.search_fields` (already declares `index.SearchField("body")`).
- Produces: `GET /search/?q=` response shape `{"topics": [...], "posts": [...]}`.

- [ ] **Step 1: Write the failing test**

Append to `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py` (reuse that file's existing `_board`/user fixtures; if it lacks one, mirror the `_board()` helper from Task 1):

```python
@pytest.mark.django_db
def test_search_returns_topics_and_posts():
    board = _board()
    author = User.objects.create_user(username="ada", password="x")
    topic = Topic.objects.create(
        board=board, title="Monstera care", slug="monstera", author=author, live=True
    )
    Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True,
        body=[{"type": "paragraph", "value": "<p>watering a monstera</p>"}],
    )

    resp = APIClient().get("/forum/search/?q=monstera")

    assert resp.status_code == 200
    assert "topics" in resp.data and "posts" in resp.data
    assert any(t["id"] == topic.id for t in resp.data["topics"])
```

(Ensure `Post` is imported in this test module.)

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd backend && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py::test_search_returns_topics_and_posts -v`
Expected: FAIL — `KeyError`/missing `posts` (current shape is `{"results": [...]}`).

- [ ] **Step 3: Extend `SearchView`**

Replace the `get` body of `SearchView` in `api/views.py` with topics + posts (keep `MAX_RESULTS`, `versioning_class = None`):

```python
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        topics, posts = [], []
        if query:
            backend = get_search_backend()
            boards = _visible_boards()
            topic_hits = backend.search(
                query, Topic.objects.filter(live=True, board__in=boards)
            )
            for t in topic_hits[: self.MAX_RESULTS]:
                topics.append({"id": t.id, "slug": t.slug, "title": t.title})
            post_hits = backend.search(
                query,
                Post.objects.filter(live=True, topic__live=True, topic__board__in=boards)
                .select_related("topic"),
            )
            for p in post_hits[: self.MAX_RESULTS]:
                posts.append(
                    {
                        "id": p.id,
                        "topic_id": p.topic_id,
                        "topic_title": p.topic.title,
                        "excerpt": p.body.render_as_block()[:200] if p.body else "",
                    }
                )
        return Response({"topics": topics, "posts": posts})
```

(`Post` is already imported in `views.py`.)

- [ ] **Step 4: Run the tests, verify they pass**

Run: `cd backend && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py -v`
Expected: PASS (the new test + existing search/sync tests; the existing throttle test in `test_ratelimits.py` still gets a 200).

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py
git commit -m "feat(forum): search returns topic + post hits (full parity)"
```

---

## Task 4: `seed_default_forum` management command

> **Mechanism note (deviation from the spec's "post_migrate" wording):** auto-seeding inside `post_migrate` creates a `ForumIndex(slug="forum")`/`ForumBoard(slug="general")` in **every test database**, which collides with the test suite's own `_board()` helpers (two `slug="general"` siblings → `_get_board` raises `Conflict` 409, breaking list/detail tests). A management command — idempotent, run on deploy like the existing `warm_moderation_cache` — gives the same "board out of the box" result without polluting tests. Run it in the release/deploy step and after local setup.

**Files:**

- Create: `backend/apps/forum_host/management/commands/seed_default_forum.py`
- Create: `backend/apps/forum_host/management/__init__.py` and `.../commands/__init__.py` if absent
- Test: `backend/apps/forum_host/tests/test_seed_command.py`

**Interfaces:**

- Produces: `python manage.py seed_default_forum` — ensures one `ForumIndex` + one `ForumBoard`, idempotently.

- [ ] **Step 1: Write the failing test**

Create `backend/apps/forum_host/tests/test_seed_command.py`:

```python
import pytest
from django.core.management import call_command
from wagtail_forum.models import ForumBoard, ForumIndex


@pytest.mark.django_db
def test_seed_default_forum_is_idempotent():
    call_command("seed_default_forum")
    call_command("seed_default_forum")  # second run must not duplicate
    assert ForumIndex.objects.count() == 1
    assert ForumBoard.objects.count() == 1
    board = ForumBoard.objects.get()
    assert board.live is True
    assert board.slug == "general-discussion"
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd backend && python -m pytest apps/forum_host/tests/test_seed_command.py -v`
Expected: FAIL — `CommandError: Unknown command 'seed_default_forum'`.

- [ ] **Step 3: Implement the command**

Create the package dirs if missing (`management/__init__.py`, `management/commands/__init__.py`), then `seed_default_forum.py`:

```python
from django.core.management.base import BaseCommand
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex


class Command(BaseCommand):
    help = "Idempotently ensure a ForumIndex + a starter ForumBoard exist."

    def handle(self, *args, **options):
        index = ForumIndex.objects.first()
        if index is None:
            root = Page.objects.filter(depth=1).first()
            index = root.add_child(
                instance=ForumIndex(title="Forum", slug="forum")
            )
            self.stdout.write(self.style.SUCCESS("Created ForumIndex 'forum'."))

        if not index.get_children().type(ForumBoard).exists():
            index.add_child(
                instance=ForumBoard(
                    title="General Discussion",
                    slug="general-discussion",
                    description="Talk about anything plant-related.",
                )
            )
            self.stdout.write(self.style.SUCCESS("Created board 'general-discussion'."))
        else:
            self.stdout.write("Forum already seeded; nothing to do.")
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd backend && python -m pytest apps/forum_host/tests/test_seed_command.py -v`
Expected: PASS.

- [ ] **Step 5: Document the deploy step**

In `backend/CLAUDE.md`, under the "Cache warming (run after deploy…)" block, add a line:

```bash
python manage.py seed_default_forum    # ensure the forum has a default board (idempotent)
```

- [ ] **Step 6: Commit**

```bash
git add backend/apps/forum_host/management backend/apps/forum_host/tests/test_seed_command.py backend/CLAUDE.md
git commit -m "feat(forum): seed_default_forum idempotent board-seeding command"
```

---

## Task 5: Rewrite the web client read contract (service + mappers + types)

**Files:**

- Modify: `web/src/services/forumMappers.ts`
- Modify: `web/src/services/forumService.ts`
- Modify: `web/src/types/forum.ts`
- Test: `web/src/services/forumMappers.test.ts`, `web/src/services/forumService.test.ts`

**Interfaces:**

- Consumes (backend, this plan): `GET /boards/` → `{results: BackendBoard[]}`; `GET /boards/{slug}/topics/` → `{results, next, previous}`; `GET /topics/{id}/` → `BackendTopicDetail`; `GET /topics/{id}/posts/` → `{results, next, previous}`; `GET /search/?q=` → `{topics, posts}`.
- Produces: `fetchCategories`, `fetchCategory(slug)`, `fetchThreads({board, cursor})`, `fetchThread(topicId)`, `fetchPosts({thread, cursor})`, `searchForum` — all returning the existing React domain types.

- [ ] **Step 1: Replace the backend shapes + mappers**

In `forumMappers.ts`, replace the machina `BackendForum`/`BackendTopic`/`BackendPost` interfaces and their mappers with the new API shapes. Key mappers:

```typescript
export interface BackendBoard {
  id: number;
  title: string;
  slug: string;
  description?: string;
  topic_count?: number;
  post_count?: number;
}

export interface BackendTopicListItem {
  id: number;
  title: string;
  slug: string;
  author: string | null;
  is_pinned: boolean;
  is_closed: boolean;
  reply_count: number;
  view_count: number;
  last_post_at: string | null;
  last_post_author: string | null;
}

export interface BackendBodyBlock { type: string; value: unknown; id: string }

export interface BackendPost {
  id: number;
  topic_id: number;
  author: { username: string; display_name?: string; trust_level?: string | null };
  body: BackendBodyBlock[];
  created_at: string;
  updated_at?: string;
  edited_at?: string | null;
  is_opening_post: boolean;
  status: 'live' | 'pending';
  reaction_counts: Record<string, number>;
  can_edit: boolean;
  can_delete: boolean;
}

export function mapBoardToCategory(b: BackendBoard): Category {
  return {
    id: String(b.id),
    name: b.title,
    slug: b.slug,
    description: b.description,
    thread_count: b.topic_count ?? 0,
    post_count: b.post_count ?? 0,
    created_at: '',
  };
}
```

Write `mapTopicListItemToThread`, `mapTopicDetailToThread`, and `mapPostToPost` (carrying `body` blocks, `is_first_post = is_opening_post`, `reaction_counts`, `edited_at`). The full mapper bodies follow the field names above; keep the `[deleted]` author fallback when `author` is null.

- [ ] **Step 2: Adjust `types/forum.ts`**

Add `body?: BackendBodyBlock[]`-shaped field to `Post` for StreamField rendering (reuse the `StreamFieldBlock` type from `@/types/blog`); change `PaginatedResponse.meta` to carry cursor links (`next?: string | null; previous?: string | null` — already present; drop reliance on `count`). Remove machina-only types that no longer have a producer (`content_html` stays optional for back-compat in tests but is no longer populated).

- [ ] **Step 3: Rewrite the read functions in `forumService.ts`**

Point `FORUM_BASE` calls at the new paths:

```typescript
export async function fetchCategories(): Promise<Category[]> {
  const data = await authenticatedFetch<{ results: BackendBoard[] }>(`${FORUM_BASE}/boards/`);
  return (data.results || []).map(mapBoardToCategory);
}
export const fetchCategoryTree = fetchCategories;

export async function fetchThreads(
  options: { board?: string; cursor?: string } = {}
): Promise<PaginatedResponse<Thread>> {
  const { board, cursor } = options;
  if (!board) throw new Error('A board slug is required');
  const url = cursor || `${FORUM_BASE}/boards/${board}/topics/`;
  const data = await authenticatedFetch<DrfPage<BackendTopicListItem>>(url);
  return {
    items: (data.results || []).map(mapTopicListItemToThread),
    meta: { count: 0, next: data.next, previous: data.previous },
  };
}

export async function fetchThread(topicId: number): Promise<Thread> {
  const data = await authenticatedFetch<BackendTopicDetail>(`${FORUM_BASE}/topics/${topicId}/`);
  return mapTopicDetailToThread(data);
}

export async function fetchPosts(
  options: { thread: number; cursor?: string }
): Promise<PaginatedResponse<Post>> {
  const { thread, cursor } = options;
  if (thread == null) throw new Error('Thread id is required');
  const url = cursor || `${FORUM_BASE}/topics/${thread}/posts/`;
  const data = await authenticatedFetch<DrfPage<BackendPost>>(url);
  return {
    items: (data.results || []).map((p) => mapPostToPost(p, String(thread))),
    meta: { count: 0, next: data.next, previous: data.previous },
  };
}

export async function searchForum(options: SearchForumOptions): Promise<SearchForumResponse> {
  const { q } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  const data = await authenticatedFetch<{ topics: BackendSearchTopic[]; posts: BackendSearchPost[] }>(
    `${FORUM_BASE}/search/?${params}`
  );
  const threads = (data.topics || []).map(mapSearchTopicToThread);
  const posts = (data.posts || []).map(mapSearchPostToPost);
  return { query: q.trim(), threads, posts, total_threads: threads.length,
    total_posts: posts.length, has_next_threads: false, has_next_posts: false,
    page: 1, page_size: threads.length + posts.length } as SearchForumResponse;
}
```

Delete `fetchCategory(forumId: number)`'s id-scan and replace with a slug lookup over `fetchCategories()`. Leave the **write** functions (`createThread`, `createPost`, `updatePost`, `deletePost`, `toggleReaction`, image fns) untouched in this phase — Phase 2/3 rewrite them; they are not exercised by the read pages after Task 6.

- [ ] **Step 4: Rewrite the service + mapper unit tests**

Update `forumService.test.ts` and `forumMappers.test.ts` to assert the new request paths (`/boards/`, `/topics/{id}/`, `/topics/{id}/posts/`, `/search/`) and the new mapped shapes. Delete machina-shape assertions.

- [ ] **Step 5: Run the tests + type-check**

Run: `cd web && npm run test -- forumService forumMappers && npm run type-check`
Expected: PASS, zero type errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/services/forumMappers.ts web/src/services/forumService.ts web/src/types/forum.ts \
        web/src/services/forumMappers.test.ts web/src/services/forumService.test.ts
git commit -m "feat(web/forum): migrate read service to wagtail_forum API contract"
```

---

## Task 6: Update the forum read pages + PostCard rendering

**Files:**

- Modify: `web/src/pages/forum/CategoryListPage.tsx`
- Modify: `web/src/pages/forum/ThreadListPage.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx` (read paths only)
- Modify: `web/src/pages/forum/SearchPage.tsx`
- Modify: `web/src/components/forum/PostCard.tsx`
- Test: the corresponding `*.test.tsx` files

**Interfaces:**

- Consumes: the Task 5 service functions and the `body` blocks on `Post`.

- [ ] **Step 1: PostCard renders the StreamField body**

In `PostCard.tsx`, replace the `sanitizedContent` `useMemo` + the `dangerouslySetInnerHTML` content `<div>` with the shared renderer:

```tsx
import StreamFieldRenderer from '../StreamFieldRenderer';
// ...
<div className="prose prose-sm sm:prose-base max-w-none mb-4 break-words ...">
  <StreamFieldRenderer blocks={post.body} />
</div>
```

Remove the now-unused `sanitizeHtml` import. (The `image` block case is Phase 3; Phase 1 bodies are heading/paragraph/quote/code, which `StreamFieldRenderer` already handles. An unknown `image` type would render the renderer's "Unsupported block type" placeholder — acceptable until Phase 3.)

- [ ] **Step 2: Update the pages to the new service signatures**

- `CategoryListPage.tsx`: unchanged call (`fetchCategoryTree()`), but it now resolves boards. Verify the empty-state renders when `results: []`.
- `ThreadListPage.tsx`: change `fetchThreads({ category })` to `fetchThreads({ board: <categorySlug> })`; replace page-number "Load More" with cursor (`meta.next`) — keep a `nextCursor` state and pass it as `{ board, cursor: nextCursor }`.
- `ThreadDetailPage.tsx`: `fetchThread(topicId)` + `fetchPosts({ thread: topicId })` unchanged in spirit; replace page-number pagination with cursor (`postsData.meta.next`); compute "remaining" from `thread.post_count` minus loaded. Leave reply/delete/react handlers in place but expect them to no-op against the unbuilt write endpoints until Phase 2 (or hide the compose UI behind a `// Phase 2` comment — do not delete).
- `SearchPage.tsx`: consume `{ threads, posts }` from `searchForum` (shape unchanged from the existing `SearchForumResponse`).

- [ ] **Step 3: Update the page tests**

Adjust `CategoryListPage.test.tsx`, `ThreadListPage.test.tsx`, `ThreadDetailPage.test.tsx`, `SearchPage.test.tsx` mocks to the new service signatures and assert: boards render, a thread's StreamField body renders (mock `post.body = [{type:'paragraph', value:'<p>hi</p>', id:'1'}]` and assert the text appears), cursor "Load More" calls the service with `{ cursor }`.

- [ ] **Step 4: Run the full web test suite + gates**

Run: `cd web && npm run type-check && npm run lint && npm run test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/forum web/src/components/forum/PostCard.tsx
git commit -m "feat(web/forum): render boards/threads/posts against the new read API"
```

---

## Task 7: End-to-end verification against a local backend

**Files:** none (manual verification).

- [ ] **Step 1: Seed + run the backend**

```bash
cd backend && source venv/bin/activate
python manage.py migrate
python manage.py seed_default_forum
python manage.py runserver
```

- [ ] **Step 2: Create content**

In `/cms/`, create one `Topic` with an opening `Post` under "General Discussion" (or via the topic-create API). Publish it.

- [ ] **Step 3: Run the web app and confirm the error is gone**

```bash
cd web && npm run dev   # http://localhost:5174
```

Visit `/forum`: the board list renders (no "Error loading categories"). Click the board → thread list → a thread → posts render with the StreamField body. Run a search and confirm topic + post hits appear.

- [ ] **Step 4: Confirm the backend suite is green**

Run: `cd backend && python -m pytest packages/wagtail_forum apps/forum_host -q`
Expected: PASS (new endpoints, parity guard, seeding, search, plus the pre-existing forum suite).

---

## Self-Review

**Spec coverage (Phase 1 rows):** topic-detail (Task 1) ✓; post-list + StreamField body + `assertNumQueries` (Task 2) ✓; `versioning_class = None` (every view, Global Constraints + each view) ✓; host wrappers + parity test (Tasks 1–2) ✓; full-parity search topics+posts (Task 3) ✓; board auto-seed (Task 4, as a command — deviation flagged) ✓; client read rewrite, boards-by-slug/topics-by-id, cursor pagination, `grep categories/` empties (Tasks 5–6) ✓; `PostCard` → `StreamFieldRenderer` (Task 6) ✓; `expand_db_html` + `nh3` N+1 guard via pinned query count (Task 2) ✓; error-status surfacing — the new JSON-returning endpoints remove the HTML-404 "Request failed" path (intrinsic to Tasks 1–2). Deferred to Phase 2/3 (correctly absent): writes, edit/delete, images, route rationalization.

**Placeholder scan:** no TBD/TODO; every code step carries real code; query-count pins are exact with explanation comments.

**Type consistency:** `serialize_forum_body` → `[{type,value,id}]` consumed by `StreamFieldRenderer` (`block.type`/`block.value`); `PostSerializer.body` (method) → same shape; client `BackendPost.body` → `mapPostToPost` → `Post.body` → `StreamFieldRenderer`. `post-list`/`topic-detail` route names match between `api/urls.py` and `forum_host/api_urls.py` (parity test enforces). `fetchThreads({board, cursor})` / `fetchPosts({thread, cursor})` signatures match their callers in Task 6.

**Open items intentionally deferred to the plan's execution, not blockers:** `trust_level` in `PostAuthorSerializer` returns `None` until a `ForumProfile` join is added (a later plan); `edited_by` omitted (no model field).
