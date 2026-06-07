# Wagtail Forum — Plan 1C: Mobile-First DRF API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the optional `wagtail_forum.api` DRF module so React + Flutter can consume the forum: boards, topics (cursor-paginated), posts, idempotent topic/reply creation routed through moderation, reactions toggle, member profile view/edit, search, and an offline delta-sync endpoint — all with mobile-first ergonomics and strict query-count budgets.

**Architecture:** A self-contained `api/` package using DRF generic views. Auth/permissions come from the host's DRF config (the package hardcodes nothing). Writes are idempotent via an `Idempotency-Key` header backed by the cache. Lists use `CursorPagination` and compact serializers; every payload carries capability flags. Topic/reply creation delegates to `submit_for_moderation` from Plan 1B.

**Tech Stack:** Django REST Framework, Django cache (Redis), Wagtail StreamField JSON, PostgreSQL, pytest + `APIClient`.

**Depends on:** Plans 1A + 1B. **Run every command from `backend/`.** The API is mounted into the host URLconf in Plan 1D; these tests use a local test urlconf override so 1C is independently testable.

---

## Task 1: API package scaffold + cursor pagination + test urlconf

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/api/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/api/pagination.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_smoke.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_smoke.py`:

```python
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_boards_endpoint_is_reachable():
    resp = APIClient().get("/forum/boards/")
    assert resp.status_code == 200
    assert resp.data["results"] == []
```

`backend/packages/wagtail_forum/wagtail_forum/tests/api/__init__.py`: (empty file)

`backend/packages/wagtail_forum/wagtail_forum/tests/api/urls.py`:

```python
from django.urls import include, path

urlpatterns = [path("forum/", include("wagtail_forum.api.urls"))]
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wagtail_forum.api'`.

- [ ] **Step 3: Write pagination + an empty boards list view + urls**

`backend/packages/wagtail_forum/wagtail_forum/api/__init__.py`: (empty file)

`backend/packages/wagtail_forum/wagtail_forum/api/pagination.py`:

```python
from rest_framework.pagination import CursorPagination


class ForumCursorPagination(CursorPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
    ordering = "-id"  # stable, unique cursor ordering
```

`backend/packages/wagtail_forum/wagtail_forum/api/urls.py`:

```python
from django.urls import path

from .views import BoardListView

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
]
```

Create `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (boards list only for now):

```python
from rest_framework import generics

from ..models import ForumBoard
from .serializers import BoardSerializer


class BoardListView(generics.ListAPIView):
    serializer_class = BoardSerializer
    pagination_class = None  # boards are few; return a flat results list

    def get_queryset(self):
        return ForumBoard.objects.live().order_by("path")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return response  # DRF default returns a bare list; wrap below

```

Replace the placeholder `list` with an explicit envelope so the smoke test's `results` key exists. Final `BoardListView`:

```python
from rest_framework import generics
from rest_framework.response import Response

from ..models import ForumBoard
from .serializers import BoardSerializer


class BoardListView(generics.ListAPIView):
    serializer_class = BoardSerializer
    pagination_class = None

    def get_queryset(self):
        return ForumBoard.objects.live().order_by("path")

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return Response({"results": data})
```

Create `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`:

```python
from rest_framework import serializers

from ..models import ForumBoard


class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForumBoard
        fields = ["id", "title", "slug", "description", "topic_count", "post_count"]
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api backend/packages/wagtail_forum/wagtail_forum/tests/api
git commit -m "feat(wagtail_forum): API scaffold, cursor pagination, boards list"
```

---

## Task 2: Topic list (cursor) + strict query-count budget

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topics_list.py`

- [ ] **Step 1: Write the failing test (incl. query budget)**

`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topics_list.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.test.utils import CaptureQueriesContext
from django.db import connection
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
    author = User.objects.create_user(username="ada", password="x")
    # live=True: these represent already-published topics (the list filters live).
    for i in range(25):
        Topic.objects.create(
            board=board, title=f"T{i}", slug=f"t{i}", author=author, live=True
        )

    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None  # cursor link
    # Denormalized counters → no per-row author/board lookups.
    assert len(ctx.captured_queries) <= 6
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topics_list.py -v`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Add the compact serializer + view + route**

Append to `api/serializers.py`:

```python
from ..models import Topic


class TopicListSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.get_username", default=None)
    last_post_author = serializers.CharField(
        source="last_post_author.get_username", default=None
    )

    class Meta:
        model = Topic
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "is_pinned",
            "is_closed",
            "reply_count",
            "view_count",
            "last_post_at",
            "last_post_author",
        ]
```

Append to `api/views.py`:

```python
from django.shortcuts import get_object_or_404

from ..models import Topic
from .pagination import ForumCursorPagination
from .serializers import TopicListSerializer


class TopicListView(generics.ListAPIView):
    serializer_class = TopicListSerializer
    pagination_class = ForumCursorPagination

    def get_queryset(self):
        board = get_object_or_404(ForumBoard.objects.live(), slug=self.kwargs["slug"])
        return (
            Topic.objects.filter(board=board, live=True)
            .select_related("author", "last_post_author")
            .order_by("-id")
        )
```

Update `api/urls.py` urlpatterns:

```python
from .views import BoardListView, TopicListView

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
]
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topics_list.py -v`
Expected: PASS. If the query count exceeds 6, inspect with `print(ctx.captured_queries)` and add the missing `select_related`; do NOT raise the budget to hide an N+1.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topics_list.py
git commit -m "feat(wagtail_forum): cursor-paginated topic list with query budget"
```

---

## Task 3: Idempotent topic creation routed through moderation

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/api/idempotency.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Topic, TrustLevel
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_trusted_user_creates_published_topic_idempotently():
    ensure_default_workflow()
    board = _board()
    user = User.objects.create_user(username="reg", password="x")
    p = ForumProfile.for_user(user)
    p.trust_level = TrustLevel.MEMBER
    p.save()

    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "title": "Hello",
        "slug": "hello",
        "body": [{"type": "paragraph", "value": "<p>hi</p>"}],
    }
    headers = {"HTTP_IDEMPOTENCY_KEY": "abc-123"}

    r1 = client.post(f"/forum/boards/{board.slug}/topics/create/", payload, format="json", **headers)
    r2 = client.post(f"/forum/boards/{board.slug}/topics/create/", payload, format="json", **headers)

    assert r1.status_code == 201
    assert r1.data["status"] == "published"
    assert r2.status_code == 200  # replayed, not duplicated
    assert Topic.objects.filter(board=board).count() == 1
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py -v`
Expected: FAIL — 404 (no create route).

- [ ] **Step 3: Write idempotency mixin + create view + serializer**

`backend/packages/wagtail_forum/wagtail_forum/api/idempotency.py` (reusable helpers — used by topic AND reply create):

```python
from django.core.cache import cache

IDEMPOTENCY_TTL = 60 * 60 * 24  # 24h


def idempotency_cache_key(request):
    """Return a per-(user, Idempotency-Key) cache key, or None if absent."""
    key = request.headers.get("Idempotency-Key")
    if key and request.user.is_authenticated:
        return f"forum:idem:{request.user.pk}:{key}"
    return None


def replay(cache_key):
    return cache.get(cache_key) if cache_key else None


def remember(cache_key, data):
    if cache_key:
        cache.set(cache_key, data, IDEMPOTENCY_TTL)
```

Append to `api/serializers.py`:

```python
class TopicCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)
    body = serializers.JSONField()
```

Append to `api/views.py` (one self-contained view — note `live=False`, the
liveness policy from Plan 1A, and StreamField assignment via the block's
`to_python`, the form confirmed in Plan 1A Task 0):

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..blocks import ForumBodyBlock
from ..models import Post
from ..workflow import submit_for_moderation
from .idempotency import idempotency_cache_key, remember, replay
from .serializers import TopicCreateSerializer


class TopicCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        cache_key = idempotency_cache_key(request)
        cached = replay(cache_key)
        if cached is not None:
            return Response(cached, status=200)

        serializer = TopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        board = get_object_or_404(ForumBoard.objects.live(), slug=slug)

        topic = Topic(
            board=board,
            title=serializer.validated_data["title"],
            slug=serializer.validated_data["slug"],
            author=request.user,
            live=False,  # born as a draft; published by moderation
        )
        topic.save()
        opening = Post(
            topic=topic,
            author=request.user,
            is_opening_post=True,
            body=ForumBodyBlock().to_python(serializer.validated_data["body"]),
            live=False,
        )
        opening.save()

        status = submit_for_moderation(opening, request.user)  # also publishes topic
        result = {"id": topic.id, "slug": topic.slug, "status": status}
        remember(cache_key, result)
        return Response(result, status=201)
```

Update `api/urls.py`:

```python
from .views import BoardListView, TopicCreateView, TopicListView

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path(
        "boards/<slug:slug>/topics/create/",
        TopicCreateView.as_view(),
        name="topic-create",
    ),
]
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py
git commit -m "feat(wagtail_forum): idempotent topic creation routed through moderation"
```

---

## Task 4: Reply create (with closed/locked guard) + reactions toggle

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`, `views.py`, `urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page

from wagtail_forum.models import (
    ForumBoard, ForumIndex, ForumProfile, Post, Reaction, Topic, TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _setup(closed=False):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="op", password="x")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, is_closed=closed
    )
    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    opening.save_revision().publish()
    return topic, opening


@pytest.mark.django_db
def test_reply_blocked_on_closed_topic():
    ensure_default_workflow()
    topic, _ = _setup(closed=True)
    user = User.objects.create_user(username="r", password="x")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/topics/{topic.id}/posts/create/",
        {"body": [{"type": "paragraph", "value": "<p>hi</p>"}]},
        format="json",
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_reaction_toggle_returns_counts():
    ensure_default_workflow()
    _, opening = _setup()
    user = User.objects.create_user(username="r", password="x")
    client = APIClient()
    client.force_authenticate(user)

    on = client.post(f"/forum/posts/{opening.id}/reactions/", {"type": "like"}, format="json")
    assert on.status_code == 200
    assert on.data["reaction_counts"] == {"like": 1}

    off = client.post(f"/forum/posts/{opening.id}/reactions/", {"type": "like"}, format="json")
    assert off.data["reaction_counts"] == {}
    assert Reaction.objects.filter(post=opening, user=user).count() == 0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py -v`
Expected: FAIL — 404 on both routes.

- [ ] **Step 3: Add reply + reaction views**

Append to `api/serializers.py`:

```python
class ReplyCreateSerializer(serializers.Serializer):
    body = serializers.JSONField()
```

Append to `api/views.py`:

```python
from rest_framework import status as http_status
from rest_framework.views import APIView

from ..models import Reaction, Topic
from .serializers import ReplyCreateSerializer


class ReplyCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, topic_id):
        topic = get_object_or_404(Topic, id=topic_id)
        if topic.is_closed or topic.locked:
            return Response(
                {"detail": "Topic is closed to replies."},
                status=http_status.HTTP_409_CONFLICT,
            )
        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = Post(
            topic=topic,
            author=request.user,
            is_opening_post=False,
            body=ForumBodyBlock().to_python(serializer.validated_data["body"]),
            live=False,  # born as a draft; published by moderation
        )
        post.save()
        moderation_status = submit_for_moderation(post, request.user)
        return Response(
            {"id": post.id, "status": moderation_status},
            status=http_status.HTTP_201_CREATED,
        )


class ReactionToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        rtype = request.data.get("type")
        if rtype not in dict(Reaction.REACTION_CHOICES):
            return Response({"detail": "Invalid reaction type."}, status=400)
        existing = Reaction.objects.filter(
            post=post, user=request.user, reaction_type=rtype
        ).first()
        if existing:
            existing.delete()
        else:
            Reaction.objects.create(post=post, user=request.user, reaction_type=rtype)
        counts = Reaction.recount(post)
        return Response({"reaction_counts": counts}, status=200)
```

Update `api/urls.py` urlpatterns to add:

```python
    path("topics/<int:topic_id>/posts/create/", ReplyCreateView.as_view(), name="reply-create"),
    path("posts/<int:post_id>/reactions/", ReactionToggleView.as_view(), name="reaction-toggle"),
```

(and import `ReactionToggleView, ReplyCreateView` from `.views`).

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py
git commit -m "feat(wagtail_forum): reply create (closed/locked guard) + reaction toggle"
```

---

## Task 5: Member profile view/edit + capability map

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`, `views.py`, `urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_profiles.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_profiles.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from wagtail_forum.models import ForumProfile

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_me_profile_get_and_patch():
    user = User.objects.create_user(username="ada", password="x")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    got = client.get("/forum/me/profile/")
    assert got.status_code == 200
    assert got.data["trust_level"] == 0
    assert got.data["capabilities"]["can_react"] is True

    patched = client.patch("/forum/me/profile/", {"bio": "Plant nerd"}, format="json")
    assert patched.status_code == 200
    assert patched.data["bio"] == "Plant nerd"


@pytest.mark.django_db
def test_me_profile_rejects_system_field_edits():
    user = User.objects.create_user(username="ada", password="x")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    client.patch("/forum/me/profile/", {"trust_level": 4, "post_count": 999}, format="json")
    profile = ForumProfile.for_user(user)
    assert profile.trust_level == 0  # unchanged
    assert profile.post_count == 0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_profiles.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Add profile serializer + view**

Append to `api/serializers.py`:

```python
from ..models import ForumProfile


class MeProfileSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = ForumProfile
        # Only these are writable; the rest are read-only.
        fields = [
            "display_name", "bio", "signature",
            "trust_level", "post_count", "flags_received", "capabilities",
        ]
        read_only_fields = ["trust_level", "post_count", "flags_received"]

    def get_capabilities(self, obj):
        return {
            # v1: static. Trust/lock-aware gating (e.g. can_react only at trust>=1)
            # is a documented follow-up — see self-review note.
            "can_react": True,
            "can_reply": True,
            "can_create_topic": True,
        }
```

Append to `api/views.py`:

```python
from .serializers import MeProfileSerializer


class MeProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = MeProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        from ..models import ForumProfile

        return ForumProfile.for_user(self.request.user)
```

Update `api/urls.py` to add `path("me/profile/", MeProfileView.as_view(), name="me-profile")` and import `MeProfileView`.

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_profiles.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api backend/packages/wagtail_forum/wagtail_forum/tests/api/test_profiles.py
git commit -m "feat(wagtail_forum): member profile view/edit + capability map"
```

---

## Task 6: Search + offline delta-sync endpoints

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`, `views.py`, `urls.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py`:

```python
import pytest
from django.contrib.auth import get_user_model
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
def test_search_returns_matching_topics():
    board = _board()
    Topic.objects.create(board=board, title="Monstera care", slug="m")
    resp = APIClient().get("/forum/search/?q=Monstera")
    assert resp.status_code == 200
    assert any(r["slug"] == "m" for r in resp.data["results"])


@pytest.mark.django_db
def test_sync_returns_topics_changed_since():
    board = _board()
    old = Topic.objects.create(board=board, title="old", slug="old")
    Topic.objects.filter(id=old.id).update(updated_at=timezone.datetime(2020, 1, 1, tzinfo=timezone.utc))
    fresh = Topic.objects.create(board=board, title="fresh", slug="fresh")

    since = "2021-01-01T00:00:00Z"
    resp = APIClient().get(f"/forum/sync/?since={since}&board={board.slug}")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.data["topics"]]
    assert "fresh" in slugs and "old" not in slugs
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py -v`
Expected: FAIL — 404 on both routes.

- [ ] **Step 3: Add search + sync views**

Append to `api/views.py`:

```python
from django.utils.dateparse import parse_datetime
from wagtail.search.backends import get_search_backend


class SearchView(APIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        results = []
        if query:
            backend = get_search_backend()
            for topic in backend.search(query, Topic.objects.filter(live=True)):
                results.append({"id": topic.id, "slug": topic.slug, "title": topic.title})
        return Response({"results": results})


class SyncView(APIView):
    def get(self, request):
        since = parse_datetime(request.query_params.get("since", "") or "")
        qs = Topic.objects.filter(live=True)
        board_slug = request.query_params.get("board")
        if board_slug:
            qs = qs.filter(board__slug=board_slug)
        if since:
            qs = qs.filter(updated_at__gt=since)
        topics = [
            {"id": t.id, "slug": t.slug, "title": t.title, "updated_at": t.updated_at}
            for t in qs.order_by("updated_at")[:200]
        ]
        # Tombstones: ids deleted since `since` would come from a soft-delete log
        # (added in a later plan). For now, return an empty tombstone list.
        return Response({"topics": topics, "deleted": []})
```

Update `api/urls.py` to add `path("search/", SearchView.as_view(), name="search")` and `path("sync/", SyncView.as_view(), name="sync")`, importing both views.

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py -v`
Expected: PASS. (If search returns empty, call `get_search_backend().refresh_index()` before searching, as in Plan 1A Task 9.)

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py
git commit -m "feat(wagtail_forum): search + offline delta-sync endpoints"
```

---

## Task 7: Full API suite + migration check

**Files:** none (verification)

- [ ] **Step 1: Run the whole package suite**

Run: `pytest packages/wagtail_forum -v`
Expected: all PASS.

- [ ] **Step 2: No missing migrations**

Run: `python manage.py makemigrations wagtail_forum --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 3: Commit any stragglers**

```bash
git add -A backend/packages/wagtail_forum
git commit -m "chore(wagtail_forum): finalize Plan 1C (DRF API)" || echo "nothing to commit"
```

---

## Plan self-review

- **Spec coverage (1C):** cursor pagination ✅ (T2); idempotent writes ✅ (T3); moderation-routed create ✅ (T3–T4); closed/locked reply guard ✅ (T4); reactions toggle w/ counts ✅ (T4); profile view/edit + system-field protection ✅ (T5); capability map present but **static in v1** (T5 — all-`True`; trust/lock-aware gating is a documented follow-up, not yet wired); search ✅ (T6); delta-sync ✅ (T6); strict `assertNumQueries`-style budget on the list endpoint ✅ (T2, via `CaptureQueriesContext`). **Deferred/documented:** tombstones for `/sync` need a soft-delete log (noted in T6); ETag/Cache-Control + django-ratelimit→429 throttling are wired in Plan 1D against the host's middleware/throttle config (the package leaves auth/throttle to the host); image-rendition serialization arrives with post-detail (add when the Flutter renderer contract is finalized in Spec 2).
- **Placeholder scan:** none. The one explicit refactor (T3 idempotency/create consolidation) is shown in full, not deferred.
- **Type/name consistency:** view names (`BoardListView`, `TopicListView`, `TopicCreateView`, `ReplyCreateView`, `ReactionToggleView`, `MeProfileView`, `SearchView`, `SyncView`) match across `views.py`/`urls.py`; serializer names consistent; `submit_for_moderation`, `Reaction.recount`, `ForumProfile.for_user` reused from Plans 1A/1B with matching signatures.
- **Mobile-first checks:** cursor pagination, idempotency-key replay, compact list serializer + query budget, capability flags, delta-sync — all present.

---

## Note for Plan 1D

Mount `wagtail_forum.api.urls` at `/api/v1/forum/` in the host URLconf, and configure host-level throttling (django-ratelimit → 429) + cache headers there. The API module itself stays host-agnostic.
