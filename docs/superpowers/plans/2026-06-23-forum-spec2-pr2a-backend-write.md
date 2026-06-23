# Forum Spec 2 — PR-2a: Backend Write Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the forum write API — REST-rationalized create routes, post edit (PATCH) and post delete (DELETE), and an edit-moderation helper that re-screens edits without ever unpublishing live content — entirely within the backend, with the host route-parity and rate-limit tests green. No web client changes (that is PR-2b).

**Architecture:** Three changes inside the reusable `wagtail_forum` package plus their host throttle wrappers. (1) Collapse the two `…/create/` POST routes into REST `POST` on the existing collection paths by merging each create view into its sibling list view (one view class per path, GET=list + POST=create); the host throttles only the `post` handler via `@method_decorator(..., name="post")`, exactly as today's wrappers throttle an inherited handler. (2) Add `submit_edit_for_moderation(post, user)` to `workflow.py` — it captures `edited=True` in a new revision and routes by **author** trust, but never forces `live=False`, so an untrusted author's flagged edit waits as a pending revision while the last-approved body keeps serving. (3) Add `PostWriteView` at `posts/<id>/` with `patch` (edit) + `delete` (soft-delete = `unpublish()`), each host-throttled on its own method. Denormalized counters (`reply_count`, `last_post_at`, board/profile counts) are maintained by the existing `published`/`unpublished` signal receivers — the views call `publish()`/`unpublish()` and never recount by hand.

**Tech Stack:** Django 6 / DRF, drf-spectacular, Wagtail 6 (DraftState/Revision/Workflow mixins), pytest + `pytest-django`, real Postgres (CI) / SQLite (backend-checks). nh3 sanitizer (unchanged).

## Global Constraints

- **No plant imports in the package core** — `wagtail_forum` is zero-plant-coupling; a reusability test runs against a minimal settings module. Add nothing that imports from `apps/`. (The edit helper lives in the package `workflow.py`; throttling lives only in the host `apps/forum_host/`.)
- **`versioning_class = None` on every forum view** — omitting it is a silent 404 under the host's `NamespaceVersioning`. The new `PostWriteView` must set it; the merged list/create views already have it.
- **Route-parity is a hard gate** — after every route add/rename, `apps/forum_host/tests/test_ratelimits.py::test_host_api_routes_match_package` (the `{(pattern, name)}` set) **and** `::test_wrapped_routes_use_the_throttled_views` (the route-name → throttled-class dict) must both be green. Update package `urls.py` and host `api_urls.py` in lockstep.
- **Trust derives from `post.author`, never the caller** — same security stance as `submit_for_moderation` (a privileged caller must not launder an untrusted author's content through their own trust).
- **Never `post.save()` the new body on the untrusted edit path** — only `save_revision()`. Any `.save()` writing `body` to the live row publishes the edit unscreened. The helper captures `edited` in the revision so no separate `.save()` is ever needed. (Validated by the spike, 2026-06-23.)
- **Optional schema import** — reuse the existing `extend_schema` try/except shim at `views.py:16-24`; do not add a hard `drf_spectacular` import.
- **No DB mocks** — real Postgres + real Wagtail revision/workflow machinery (CLAUDE.md testing rules).
- **Test invocation** — package API tests set `pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")` and hit `APIClient().get("/forum/…")`; host tests run against the real project urlconf at `/api/v1/forum/…`. Run from `backend/` with the venv: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate`.

---

## Epic roadmap (context — NOT part of this PR)

Todo 231 (forum Spec 2) closes across these PRs; PR-1 has landed (merged as PR #394).

- **PR-1 (done):** AC1 read-view `@extend_schema` + AC3 compound sync cursor. Backend-only, no route changes.
- **PR-2a (this plan):** backend write path — route rationalization + `PostWriteView` (PATCH/DELETE) + `submit_edit_for_moderation`. No web changes; images still rejected by `validate_forum_body`.
- **PR-2b (web):** migrate `forumService.ts` write fns (`createThread`/`createPost`/`updatePost`/`deletePost`) onto the new REST routes with `body:[…]` payloads; adapt `toggleReaction` to the `{reaction_counts, reacted}` shape; **delete** `fetchReactions` (`ReactionToggleView` has no `GET`); drive edit/delete affordances off `can_edit`/`can_delete`; composer emits `[{type:'paragraph', value:'<p>…</p>'}]`; re-enable compose/edit/delete/react UI; rewrite tests, delete machina-shape tests. `createThread` must send the board **slug** + a client-slugified topic **slug** (`TopicCreateSerializer` requires a `SlugField`; the backend auto-suffixes dupes). After PR-2b lands, AC2 flips (web off machina forum paths).
- **PR-3 (images):** `PostImageUploadView` + relax `validate_forum_body` to accept in-collection `image` blocks (IDOR-safe) + web `StreamFieldRenderer` `image` case. Todo 231 archives only after PR-3.

AC4 (route-parity green with the final URL surface) is satisfied continuously — every PR keeps the parity test green.

### Spike result that grounds this plan (2026-06-23)

A throwaway pytest exercised the proposed edit helper on real Postgres + Wagtail. All four assertions passed:

1. **Trusted edit** → new body live immediately, `edited=True`.
2. **Untrusted flagged edit** → OLD body keeps serving, flagged body never goes live, `edited` stays `False`, `has_unpublished_changes is True` (a pending revision exists).
3. **Untrusted clean edit** → `SpamCheckTask` auto-approves → publishes → new body, `edited=True`.
4. **HTML round-trip** → `bold/italic/external-link/inline-code/ul-li` survive `validate_forum_body` (nh3) → `to_python` → `serialize_forum_body` (`expand_db_html`).

The helper code below is exactly what the spike validated.

---

## File Structure

| File | Responsibility | PR-2a change |
|------|----------------|--------------|
| `backend/packages/wagtail_forum/wagtail_forum/workflow.py` | Moderation routing | **Add** `submit_edit_for_moderation(post, user)` |
| `backend/packages/wagtail_forum/wagtail_forum/api/views.py` | DRF views | Merge `TopicCreateView`→`TopicListView.post`, `ReplyCreateView`→`PostListView.post`; **add** `PostWriteView` (patch/delete) |
| `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py` | Serializers | **Add** `PostEditSerializer` (body-only, `validate_forum_body`) |
| `backend/packages/wagtail_forum/wagtail_forum/api/urls.py` | Package routes | Drop `…/create/` routes; **add** `posts/<id>/` (`post-detail`) |
| `backend/apps/forum_host/api.py` | Throttle wrappers | Wrap merged `TopicListView`/`PostListView` (`post`) + new `PostWriteView` (`patch`/`delete`); drop `TopicCreateView`/`ReplyCreateView` wrappers |
| `backend/apps/forum_host/api_urls.py` | Host mount | Mirror package routes; import merged list views + `PostWriteView` from `.api` |
| `backend/apps/forum_host/constants.py` | Rate limits | **Add** `post_update`, `post_delete` |
| `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py` | **New** — edit/delete API tests | Author/mod/closed/malformed/opening-post-409/recount/visibility |
| `backend/packages/wagtail_forum/wagtail_forum/tests/workflow/test_edit_moderation.py` | **New** — helper unit tests | The four spike assertions, against the real helper |
| `test_topic_create.py`, `test_replies_reactions.py`, `test_visibility.py` | Existing create tests | Mechanical `…/create/` → `…/` URL swap |
| `apps/forum_host/tests/test_ratelimits.py` | Host throttle/parity tests | `…/create/` → `…/`; update wrapped-class dict |

---

## Task 1: `submit_edit_for_moderation` helper + unit tests

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/workflow.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/workflow/test_edit_moderation.py` (new; create the `tests/workflow/` package with an empty `__init__.py`)

**Interfaces:**

- Consumes: `ForumProfile.for_user`, `get_setting("TRUST_AUTOPUBLISH_LEVEL")`, Wagtail `save_revision`/`revision.publish`/`get_workflow`/`workflow.start` (all already used by `submit_for_moderation`).
- Produces: `submit_edit_for_moderation(post, user) -> "published" | "pending"`. Caller sets `post.body` to the new (validated) StreamField value **before** calling; the helper sets `edited`, snapshots a revision, and publishes-or-queues. After it returns, `post` is `refresh_from_db()`-fresh.

- [ ] **Step 1: Create the test package + write the failing tests**

Create `backend/packages/wagtail_forum/wagtail_forum/tests/workflow/__init__.py` (empty) and `backend/packages/wagtail_forum/wagtail_forum/tests/workflow/test_edit_moderation.py`:

```python
"""submit_edit_for_moderation: re-screen an edit without unpublishing live
content (Spec 2 Q2). Mirrors the PR-2a spike, now against the real helper."""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from wagtail.models import Page
from wagtail_forum.blocks import ForumBodyBlock
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import (
    ensure_default_workflow,
    submit_edit_for_moderation,
    submit_for_moderation,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _author(username, trust):
    u = User.objects.create_user(username=username, password="x")
    p = ForumProfile.for_user(u)
    p.trust_level = trust
    p.save()
    return u


def _body(html):
    return ForumBodyBlock().to_python([{"type": "paragraph", "value": html}])


def _live_post(board, author, html="<p>original</p>", slug="t"):
    topic = Topic(board=board, title="t", slug=slug, author=author, live=False)
    topic.save()
    post = Post(
        topic=topic, author=author, is_opening_post=True, body=_body(html), live=False
    )
    post.save()
    submit_for_moderation(post, author)
    post.refresh_from_db()
    return post


def test_trusted_edit_publishes_immediately():
    ensure_default_workflow()
    author = _author("trusted", TrustLevel.MEMBER)
    post = _live_post(_board(), author)
    post.body = _body("<p>edited by trusted</p>")
    status = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "published"
    assert fresh.live and "edited by trusted" in fresh.body[0].value.source
    assert fresh.edited is True


def test_untrusted_flagged_edit_keeps_old_body_live():
    ensure_default_workflow()
    author = _author("newbie", TrustLevel.NEW)
    post = _live_post(_board(), author, "<p>original clean</p>")
    post.body = _body("<p>spamzzz buy now</p>")
    with override_settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["spamzzz"]):
        status = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "pending"
    assert fresh.live, "post stays live during a pending edit"
    assert "original clean" in fresh.body[0].value.source, "OLD body keeps serving"
    assert "spamzzz" not in fresh.body[0].value.source
    assert fresh.edited is False
    assert fresh.has_unpublished_changes is True


def test_untrusted_clean_edit_auto_publishes():
    ensure_default_workflow()
    author = _author("newbie2", TrustLevel.NEW)
    post = _live_post(_board(), author, "<p>original2</p>")
    post.body = _body("<p>clean edit here</p>")
    status = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "published"
    assert fresh.live and "clean edit here" in fresh.body[0].value.source
    assert fresh.edited is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/workflow/test_edit_moderation.py -v`
Expected: FAIL — `ImportError: cannot import name 'submit_edit_for_moderation'`.

- [ ] **Step 3: Implement the helper**

In `backend/packages/wagtail_forum/wagtail_forum/workflow.py`, append after `submit_for_moderation`:

```python
def submit_edit_for_moderation(obj, user):
    """Re-screen an EDITED post WITHOUT unpublishing live content (Spec 2 Q2).

    The caller has already set obj.body to the new, validated StreamField value.
    Unlike submit_for_moderation (create-shaped: force-drafts live=False then
    publishes), an edit must never take approved content dark:

    - Trusted author (trust >= TRUST_AUTOPUBLISH_LEVEL): publish the new revision
      immediately.
    - Untrusted author: save a new revision and start the moderation workflow on
      it. Clean content auto-approves -> publishes; flagged content is rejected
      and the revision stays pending while the live row keeps its last-approved
      body. live is NEVER forced False; obj.save() is NEVER called with the new
      body (that would publish it unscreened).

    `edited` is set in memory and captured in the revision, so publish() writes
    it back atomically with the new body — it flips to True iff the edit goes
    live. Trust derives from obj.author (the content's owner), never the caller.

    Returns 'published' (the edit is now live) or 'pending' (awaiting moderation).
    """
    obj.edited = True  # captured in the revision; published atomically with body
    profile = ForumProfile.for_user(obj.author)
    revision = obj.save_revision(user=user)
    if profile.trust_level >= get_setting("TRUST_AUTOPUBLISH_LEVEL"):
        revision.publish(user=None)
    else:
        workflow = obj.get_workflow()
        if workflow is not None:
            # Clean -> auto-approve -> publish; flagged -> rejected, stays pending.
            workflow.start(obj, None)
        # Fail closed: no workflow -> the edit stays a pending revision.
    obj.refresh_from_db()
    # has_unpublished_changes is True after save_revision and cleared by publish();
    # it is the single signal of whether the edit reached the live row.
    return "pending" if obj.has_unpublished_changes else "published"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/workflow/test_edit_moderation.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/workflow.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/workflow/
git commit -m "231(PR-2a): add submit_edit_for_moderation (re-screen edits, never unpublish live)"
```

---

## Task 2: Route rationalization — merge create routes into REST POST

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (merge `TopicCreateView`→`TopicListView`, `ReplyCreateView`→`PostListView`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Modify: `backend/apps/forum_host/api.py`, `backend/apps/forum_host/api_urls.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py`, `test_replies_reactions.py`, `test_visibility.py`
- Modify: `backend/apps/forum_host/tests/test_ratelimits.py`

**Interfaces:**

- Produces: `POST /boards/<slug>/topics/` (create topic) and `POST /topics/<id>/posts/` (reply) replace the `…/create/` paths. GET on both paths is unchanged (list). Route names stay `topic-list` / `post-list`; names `topic-create` / `reply-create` are removed.

- [ ] **Step 1: Update the package create tests to the new URLs (these become the failing tests)**

These are mechanical, deterministic URL swaps. Run from the repo root:

```bash
cd /Users/williamtower/projects/plant_id_community
sed -i '' 's#/topics/create/#/topics/#g; s#/posts/create/#/posts/#g' \
  backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py \
  backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py \
  backend/packages/wagtail_forum/wagtail_forum/tests/api/test_visibility.py
```

Verify nothing else changed (the `idempotency_cache_key(..., "topic-create")` namespace strings in `views.py` are untouched — they have no leading slash and were not in the sed scope):

```bash
grep -rn "create/" backend/packages/wagtail_forum/wagtail_forum/tests/api/ ; echo "exit: $?"
```

Expected: no matches in the three files (exit 1 from grep = none found is success here).

- [ ] **Step 2: Run the affected suites to verify they now fail**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py -q`
Expected: FAIL — POSTs to `/forum/boards/<slug>/topics/` and `/forum/topics/<id>/posts/` 405 (the merged `post` handler does not exist yet; GET-only views reject POST).

- [ ] **Step 3: Merge the create logic into the list views**

In `backend/packages/wagtail_forum/wagtail_forum/api/views.py`:

(a) Replace the `TopicListView` class (currently L115-126) with a GET-list + POST-create view. Move `TopicCreateView`'s `post` and `_create_topic` onto it verbatim, and add `get_permissions` so only POST requires auth:

```python
class TopicListView(generics.ListAPIView):
    serializer_class = TopicListSerializer
    pagination_class = TopicCursorPagination
    versioning_class = None

    def get_permissions(self):
        # POST (create) needs auth; GET (list) stays public like the read path.
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        board = _get_board(self.kwargs["slug"])
        return (
            Topic.objects.filter(board=board, live=True)
            .select_related("author", "last_post_author")
            .order_by("-last_post_at", "-id")
        )

    @extend_schema(
        request=TopicCreateSerializer,
        responses={201: dict, 409: dict, 422: dict},
        description=(
            "Create a topic (with its opening post) and route it through "
            "moderation. Supports an Idempotency-Key header: a retry with the "
            "same key replays the original response (original status code); "
            "reuse with a different payload returns 422. A taken slug is "
            "auto-suffixed (-2, -3, …) — read the final slug from the response."
        ),
    )
    def post(self, request, slug):
        cache_key = idempotency_cache_key(request, "topic-create")
        payload_fp = (
            fingerprint({"slug": slug, "body": request.data}) if cache_key else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        serializer = TopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        board = _get_board(slug)

        reserve(cache_key)
        topic, opening = self._create_topic(request, board, serializer.validated_data)

        try:
            status = submit_for_moderation(opening, request.user)
        except Exception:
            logger.exception(
                "[ERROR] submit_for_moderation failed for post %s; left as draft",
                opening.pk,
            )
            status = "pending"

        result = {"id": topic.id, "slug": topic.slug, "status": status}
        remember(cache_key, result, http_status.HTTP_201_CREATED, payload_fp)
        return Response(result, status=http_status.HTTP_201_CREATED)

    @staticmethod
    def _create_topic(request, board, validated):
        """Create the draft topic + opening post atomically (born live=False).

        A taken slug is auto-suffixed instead of 409ing: the unique constraint
        also covers DRAFT topics, so a conflict response would leak a hidden
        draft's existence (audit L4). Each attempt runs in its own transaction
        so an IntegrityError can't poison an outer atomic block.
        """
        base_slug = validated["slug"]
        for attempt in range(MAX_SLUG_ATTEMPTS):
            if attempt == 0:
                slug_try = base_slug
            else:
                suffix = f"-{attempt + 1}"
                slug_try = f"{base_slug[:255 - len(suffix)]}{suffix}"
            try:
                with transaction.atomic():
                    topic = Topic(
                        board=board,
                        title=validated["title"],
                        slug=slug_try,
                        author=request.user,
                        live=False,
                    )
                    topic.save()
                    opening = Post(
                        topic=topic,
                        author=request.user,
                        is_opening_post=True,
                        body=ForumBodyBlock().to_python(validated["body"]),
                        live=False,
                    )
                    opening.save()
                return topic, opening
            except IntegrityError:
                continue
        raise Conflict("Could not allocate a unique slug for this topic.")
```

(b) Delete the now-redundant standalone `TopicCreateView` class (currently L171-259).

(c) Add a `post` to `PostListView` (the AC1-annotated read view, currently L149-168). Keep the existing class-level `@extend_schema` (it documents the GET 200) and add a method-level `@extend_schema` on `post` (drf-spectacular applies the method-level one to POST). Add `get_permissions`, and move `ReplyCreateView.post`'s body onto it:

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

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Post.objects.none()
        topic = get_object_or_404(
            Topic.objects.filter(live=True, board__in=_visible_boards()),
            id=self.kwargs["topic_id"],
        )
        return topic.posts.filter(live=True).select_related("author")

    @extend_schema(
        request=ReplyCreateSerializer,
        responses={201: dict, 404: dict, 409: dict, 422: dict},
        description=(
            "Reply to a topic; the reply routes through moderation. Supports "
            "an Idempotency-Key header (a mobile retry must not create a "
            "duplicate reply)."
        ),
    )
    def post(self, request, topic_id):
        cache_key = idempotency_cache_key(request, "reply-create")
        payload_fp = (
            fingerprint({"topic": topic_id, "body": request.data})
            if cache_key
            else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        topic = get_object_or_404(
            Topic.objects.filter(live=True, board__in=_visible_boards()),
            id=topic_id,
        )
        if topic.is_closed or topic.locked:
            raise Conflict("Topic is closed to replies.")
        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reserve(cache_key)
        post = Post(
            topic=topic,
            author=request.user,
            is_opening_post=False,
            body=ForumBodyBlock().to_python(serializer.validated_data["body"]),
            live=False,
        )
        post.save()

        try:
            moderation_status = submit_for_moderation(post, request.user)
        except Exception:
            logger.exception(
                "[ERROR] submit_for_moderation failed for reply %s; left as draft",
                post.pk,
            )
            moderation_status = "pending"

        result = {"id": post.id, "status": moderation_status}
        remember(cache_key, result, http_status.HTTP_201_CREATED, payload_fp)
        return Response(result, status=http_status.HTTP_201_CREATED)
```

(d) Delete the now-redundant standalone `ReplyCreateView` class (currently L262-322).

- [ ] **Step 4: Update the package URLconf**

In `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`, drop `TopicCreateView`/`ReplyCreateView` from the import and remove the two `…/create/` `path()` entries (the `topic-list` / `post-list` routes already exist and now serve POST too). Resulting `urlpatterns`:

```python
from django.urls import path

from .views import (
    BoardListView,
    MeProfileView,
    PostListView,
    ReactionToggleView,
    SearchView,
    SyncView,
    TopicDetailView,
    TopicListView,
)

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path("topics/<int:topic_id>/posts/", PostListView.as_view(), name="post-list"),
    path(
        "posts/<int:post_id>/reactions/",
        ReactionToggleView.as_view(),
        name="reaction-toggle",
    ),
    path("me/profile/", MeProfileView.as_view(), name="me-profile"),
    path("search/", SearchView.as_view(), name="search"),
    path("sync/", SyncView.as_view(), name="sync"),
]
```

- [ ] **Step 5: Update the host throttle wrappers + mount**

In `backend/apps/forum_host/api.py`, replace the `TopicCreateView`/`ReplyCreateView` wrappers with wrappers around the merged list views (throttle only `post`):

```python
@method_decorator(
    ratelimit(key="user", rate=_rate("topic_create"), method="POST"), name="post"
)
class TopicListView(forum_views.TopicListView):
    pass


@method_decorator(
    ratelimit(key="user", rate=_rate("reply_create"), method="POST"), name="post"
)
class PostListView(forum_views.PostListView):
    pass
```

Leave `ReactionToggleView`, `MeProfileView`, `SearchView`, `SyncView` wrappers unchanged. In `backend/apps/forum_host/api_urls.py`, import the GET-only views (`BoardListView`, `TopicDetailView`) from the package and the throttled `TopicListView`/`PostListView` (+ the rest) from `.api`; mirror the package routes exactly:

```python
from django.urls import path
from wagtail_forum.api.views import BoardListView, TopicDetailView

from .api import (
    MeProfileView,
    PostListView,
    ReactionToggleView,
    SearchView,
    SyncView,
    TopicListView,
)

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path("topics/<int:topic_id>/posts/", PostListView.as_view(), name="post-list"),
    path(
        "posts/<int:post_id>/reactions/",
        ReactionToggleView.as_view(),
        name="reaction-toggle",
    ),
    path("me/profile/", MeProfileView.as_view(), name="me-profile"),
    path("search/", SearchView.as_view(), name="search"),
    path("sync/", SyncView.as_view(), name="sync"),
]
```

- [ ] **Step 6: Update the host rate-limit/parity tests**

In `backend/apps/forum_host/tests/test_ratelimits.py`:

- Swap the four `…/boards/{board.slug}/topics/create/` POST URLs to `…/boards/{board.slug}/topics/` (in `test_topic_create_is_throttled_per_user` and `test_throttle_is_per_user_not_global`).
- In `test_wrapped_routes_use_the_throttled_views`, replace the `wrapped` dict with the new route-name → throttled-class map:

```python
    wrapped = {
        "topic-list": throttled.TopicListView,
        "post-list": throttled.PostListView,
        "reaction-toggle": throttled.ReactionToggleView,
        "me-profile": throttled.MeProfileView,
        "search": throttled.SearchView,
        "sync": throttled.SyncView,
    }
```

(`board-list` and `topic-detail` stay GET-only/unthrottled package views — correctly absent.)

- [ ] **Step 7: Run the merged-route suites + host parity/throttle tests**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py packages/wagtail_forum/wagtail_forum/tests/api/test_topics_list.py packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py packages/wagtail_forum/wagtail_forum/tests/api/test_visibility.py apps/forum_host/tests/test_ratelimits.py -q`
Expected: PASS (create via REST POST works; GET list still works; parity + throttle green).

- [ ] **Step 8: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/api/urls.py \
        backend/apps/forum_host/api.py backend/apps/forum_host/api_urls.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_create.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_visibility.py \
        backend/apps/forum_host/tests/test_ratelimits.py
git commit -m "231(PR-2a): rationalize create routes to REST POST on collection paths"
```

---

## Task 3: `PostWriteView` — edit (PATCH) + delete (DELETE)

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (add `PostWriteView`, import `PermissionDenied` + `submit_edit_for_moderation` + `PostEditSerializer`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py` (add `PostEditSerializer`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py` (add `posts/<id>/`)
- Modify: `backend/apps/forum_host/api.py`, `api_urls.py`, `constants.py`
- Modify: `backend/apps/forum_host/tests/test_ratelimits.py` (add `post-detail` to wrapped dict)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py` (new)

**Interfaces:**

- Consumes: `submit_edit_for_moderation` (Task 1); `PostSerializer` (read shape, already imported).
- Produces: `PATCH /posts/<id>/` → `200` `PostSerializer` body **plus** a top-level `moderation_status: published|pending`; `DELETE /posts/<id>/` → `204`. Both: `404` hidden/missing, `403` non-author-non-mod, `409` closed/locked (PATCH) or opening-post (DELETE), `400` malformed body (PATCH). Route name `post-detail`; host rates `post_update` (PATCH) + `post_delete` (DELETE).

- [ ] **Step 1: Write the failing API tests**

Create `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py`:

```python
"""PostWriteView: edit (PATCH) + soft-delete (DELETE). Spec 2 Q1/Q2/Q3."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.blocks import ForumBodyBlock
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _member(username):
    u = User.objects.create_user(username=username, password="x")
    p = ForumProfile.for_user(u)
    p.trust_level = TrustLevel.MEMBER  # >= autopublish, so create+edit go live
    p.save()
    return u


def _body(html):
    return ForumBodyBlock().to_python([{"type": "paragraph", "value": html}])


def _topic_with_reply(board, author, reply_html="<p>a reply</p>"):
    ensure_default_workflow()
    topic = Topic(board=board, title="t", slug="t", author=author, live=False)
    topic.save()
    opening = Post(
        topic=topic, author=author, is_opening_post=True, body=_body("<p>op</p>"),
        live=False,
    )
    opening.save()
    submit_for_moderation(opening, author)
    reply = Post(topic=topic, author=author, body=_body(reply_html), live=False)
    reply.save()
    submit_for_moderation(reply, author)
    topic.refresh_from_db()
    return topic, opening, reply


def test_author_edit_publishes_new_body():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["moderation_status"] == "published"
    assert any("edited" in b["value"] for b in resp.data["body"])
    assert resp.data["edited_at"] is not None


def test_non_author_cannot_edit():
    board = _board()
    author = _member("ada")
    intruder = _member("eve")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(intruder)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>hax</p>"}]},
        format="json",
    )
    assert resp.status_code == 403


def test_edit_on_closed_topic_conflicts():
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    Topic.objects.filter(id=topic.id).update(is_closed=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code == 409


def test_edit_malformed_body_is_400_not_500():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/", {"body": "not-a-list"}, format="json"
    )
    assert resp.status_code == 400


def test_author_delete_soft_deletes_and_recounts():
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    assert topic.reply_count == 1
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 204
    assert Post.objects.get(id=reply.id).live is False
    topic.refresh_from_db()
    assert topic.reply_count == 0  # signal-maintained recount, not manual


def test_delete_opening_post_conflicts():
    board = _board()
    author = _member("ada")
    _topic, opening, _reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{opening.id}/")
    assert resp.status_code == 409
    assert Post.objects.get(id=opening.id).live is True


def test_edit_hidden_post_is_404():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    Post.objects.filter(id=reply.id).update(live=False)  # now hidden
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>x</p>"}]},
        format="json",
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py -q`
Expected: FAIL — `404` for every PATCH/DELETE (`posts/<id>/` route does not exist yet).

- [ ] **Step 3: Add `PostEditSerializer`**

In `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`, after `ReplyCreateSerializer`:

```python
class PostEditSerializer(serializers.Serializer):
    body = serializers.JSONField()

    def validate_body(self, value):
        return validate_forum_body(value)
```

- [ ] **Step 4: Add `PostWriteView` and its imports**

In `backend/packages/wagtail_forum/wagtail_forum/api/views.py`:

Add to the DRF exceptions import (currently `from rest_framework.exceptions import NotFound, ValidationError`):

```python
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
```

Add to the workflow import (currently `from ..workflow import submit_for_moderation`):

```python
from ..workflow import submit_edit_for_moderation, submit_for_moderation
```

Add `PostEditSerializer` to the serializers import block.

Add the view (place it after `PostListView`):

```python
class PostWriteView(APIView):
    """Edit (PATCH) or soft-delete (DELETE) a single post. Author or moderator."""

    permission_classes = [IsAuthenticated]
    versioning_class = None

    def _get_editable(self, request, post_id):
        # Hide non-live posts / posts on non-live topics / hidden boards (404),
        # never 403 — no existence leak (mirrors ReplyCreateView, audit M6/M7).
        post = get_object_or_404(
            Post.objects.select_related("topic", "author"), id=post_id
        )
        if (
            not post.live
            or not post.topic.live
            or not _visible_boards().filter(pk=post.topic.board_id).exists()
        ):
            raise NotFound()
        # Trust the author OR a moderator (the change_post perm). can_edit/
        # can_delete in PostSerializer compute the same predicate for the client.
        if not (
            request.user == post.author
            or request.user.has_perm("wagtail_forum.change_post")
        ):
            raise PermissionDenied()
        return post

    @extend_schema(
        request=PostEditSerializer,
        responses={200: PostSerializer, 400: dict, 403: dict, 404: dict, 409: dict},
        description=(
            "Edit a post (author or moderator). Re-screened by author trust: a "
            "trusted edit publishes immediately; an untrusted edit awaits "
            "moderation while the last-approved body keeps serving. Response is "
            "the post plus moderation_status (published|pending). 409 if the "
            "topic is closed/locked."
        ),
    )
    def patch(self, request, post_id):
        post = self._get_editable(request, post_id)
        if post.topic.is_closed or post.topic.locked:
            raise Conflict("Topic is closed to edits.")
        serializer = PostEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post.body = ForumBodyBlock().to_python(serializer.validated_data["body"])
        try:
            moderation_status = submit_edit_for_moderation(post, request.user)
        except Exception:
            logger.exception(
                "[ERROR] submit_edit_for_moderation failed for post %s", post.pk
            )
            moderation_status = "pending"
        post.refresh_from_db()
        data = PostSerializer(post, context={"request": request}).data
        data["moderation_status"] = moderation_status
        return Response(data)

    @extend_schema(
        responses={204: None, 403: dict, 404: dict, 409: dict},
        description=(
            "Soft-delete a post (author or moderator) by unpublishing it; the "
            "topic's reply_count recounts via the unpublish signal. Deleting an "
            "opening post returns 409 (delete the topic instead)."
        ),
    )
    def delete(self, request, post_id):
        post = self._get_editable(request, post_id)
        if post.is_opening_post:
            raise Conflict("Cannot delete the opening post; delete the topic.")
        # unpublish() fires Wagtail's `unpublished` signal -> the forum's counter
        # receivers recount reply_count/last_post_at/board/profile. Do NOT recount
        # by hand (that double-processes). user=None: forum authors are not
        # Wagtail editors, matching submit_for_moderation's publish(user=None).
        post.unpublish(user=None)
        return Response(status=http_status.HTTP_204_NO_CONTENT)
```

> **Verify during Step 6:** `post.unpublish(user=None)` must fire the `unpublished` signal and drop `reply_count` (the `test_author_delete_soft_deletes_and_recounts` assertion). If a Wagtail version quirk requires a real user, switch to `user=request.user`; the test is the gate.

- [ ] **Step 5: Add the route + host wrapper + rate limits**

Package `urls.py` — add to the import and `urlpatterns` (place after the `post-list` route):

```python
    path("posts/<int:post_id>/", PostWriteView.as_view(), name="post-detail"),
```

(add `PostWriteView` to the `from .views import (...)` block).

Host `constants.py` — add two keys to `DEFAULT_FORUM_RATELIMITS`:

```python
    "post_update": "30/h",
    "post_delete": "20/h",
```

Host `api.py` — add the wrapper (two throttled methods on one class):

```python
@method_decorator(
    ratelimit(key="user", rate=_rate("post_update"), method="PATCH"), name="patch"
)
@method_decorator(
    ratelimit(key="user", rate=_rate("post_delete"), method="DELETE"), name="delete"
)
class PostWriteView(forum_views.PostWriteView):
    pass
```

Host `api_urls.py` — import `PostWriteView` from `.api` and add the mirrored route:

```python
    path("posts/<int:post_id>/", PostWriteView.as_view(), name="post-detail"),
```

Host `tests/test_ratelimits.py` — add to the `wrapped` dict in `test_wrapped_routes_use_the_throttled_views`:

```python
        "post-detail": throttled.PostWriteView,
```

- [ ] **Step 6: Run the edit/delete suite + host parity**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py apps/forum_host/tests/test_ratelimits.py -v`
Expected: PASS (all edit/delete cases + route parity + wrapped-class pin).

- [ ] **Step 7: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/api/serializers.py \
        backend/packages/wagtail_forum/wagtail_forum/api/urls.py \
        backend/apps/forum_host/api.py backend/apps/forum_host/api_urls.py \
        backend/apps/forum_host/constants.py \
        backend/apps/forum_host/tests/test_ratelimits.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py
git commit -m "231(PR-2a): add PostWriteView (PATCH edit re-moderates, DELETE soft-deletes)"
```

---

## Task 4: Full-suite gate + schema + work-log

**Files:** `todos/231-in_progress-p1-forum-spec2-read-api-web-client.md` (work log only).

- [ ] **Step 1: Run the whole forum package + host suite**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/ apps/forum_host/ -q`
Expected: all pass (PR-1 baseline 116 + Task 1's 3 + Task 3's 7 new ≈ 126; no regressions).

- [ ] **Step 2: Confirm the OpenAPI schema still generates (CI backend-checks gate)**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python manage.py spectacular --file /tmp/schema.yml 2>&1 | tail -8`
Expected: exits 0. No **new error** mentioning `TopicListView`, `PostListView`, or `PostWriteView` (pre-existing warnings from todo 238 are acceptable). Confirm `/forum/posts/{post_id}/` appears with `patch` + `delete` operations:

```bash
grep -A2 "/forum/posts/{post_id}/:" /tmp/schema.yml | head -5
```

- [ ] **Step 3: Confirm the package zero-coupling test still passes**

Run: `cd /Users/williamtower/projects/plant_id_community/backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_smoke.py -q`
Expected: PASS (no `apps.*` import added to the package core).

- [ ] **Step 4: Update the todo 231 work log**

Append a `### 2026-06-23 - PR-2a (backend write path) landed` entry to `todos/231-in_progress-p1-forum-spec2-read-api-web-client.md`: route rationalization done, `PostWriteView` (PATCH/DELETE) + `submit_edit_for_moderation` landed, Q1/Q2/Q3 enforced, parity/rate-limit/schema green. Note PR-2b (web) + PR-3 (images) remain; the todo stays `in_progress` (archives only after PR-3). Do **not** flip AC2/AC4 yet.

- [ ] **Step 5: Commit the work-log update**

```bash
git add todos/231-in_progress-p1-forum-spec2-read-api-web-client.md
git commit -m "231: log PR-2a backend write path"
```

---

## Self-Review

- **Spec coverage:** route rationalization (Phase 2 "Route rationalization") → Task 2; `PostUpdateView`/`PostDeleteView` (Phase 2 table) → Task 3; resolved Q1 (opening-post delete → 409) → `test_delete_opening_post_conflicts`; Q2 (edit re-moderation, never unpublish; dedicated edit helper) → Task 1 + `submit_edit_for_moderation`; Q3 (delete = unpublish, no new field, recount) → Task 3 delete + `test_author_delete_soft_deletes_and_recounts`. Images (Phase 3) and all web/composer work (Phase 1/2 client) are explicitly out of PR-2a (Epic roadmap). The TipTap→StreamField round-trip de-risk was completed as a spike (result recorded above); the composer itself is PR-2b.
- **Placeholder scan:** none — every code step shows full code; every run step shows the command + expected result. The one runtime uncertainty (`unpublish(user=None)` firing the recount) is gated by an explicit test, with the fallback named.
- **Type consistency:** `submit_edit_for_moderation(post, user) -> str` defined in Task 1 is imported and called in Task 3; `PostEditSerializer` defined in Task 3 Step 3 is imported in Step 4; `post-detail` route name added in Task 3 Step 5 is asserted in the same step's `wrapped` dict update; the merged `post` handlers (Task 2) are what the host `name="post"` decorators target (Task 2 Step 5).
- **Parity invariant:** Task 2 and Task 3 each end with `test_ratelimits.py` green; package `urls.py` and host `api_urls.py` are edited together in both tasks.
- **No migration:** Q3 adds no field; `edited` already exists. Confirmed — nothing in this PR runs `makemigrations`.
