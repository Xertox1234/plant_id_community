# Forum Wave 2 · Slice 1 — Author Display Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the real forum `trust_level` and `display_name` for post/notification authors (currently `trust_level` is hardcoded `None`), and render the integer trust level as a human label in the web UI — without regressing query counts or the badge behaviour.

**Architecture:** `PostAuthorSerializer` joins the author's `ForumProfile` (reverse OneToOne `wagtail_forum_profile`) and returns its integer `trust_level` (0–4) and `display_name`. The two list endpoints that serialize authors (`PostListView`, `NotificationListView`) add the profile to their `select_related` so the join folds into the existing single SELECT — no N+1. The web side, which today types the forum author `trust_level` as a **string** and renders it raw, is standardized on `number` and maps the integer to a label (`New/Basic/Member/Regular/Leader`) at render, keeping `NEW` (0) un-badged.

**Tech Stack:** Django REST Framework serializers, `wagtail_forum` package; React 19 + TypeScript + Vitest.

## Global Constraints

- **`trust_level` is an integer enum 0–4** (0=New, 1=Basic, 2=Member, 3=Regular, 4=Leader). The backend already commits to integer in TWO places — `AUTHOR_SCHEMA` (`{"type": "integer", "nullable": true}`) and `/forum/me/profile/` (`test_profiles.py` asserts `trust_level == 0`). Do **not** change the API to return a string label; that would force `AUTHOR_SCHEMA` and MeProfile to diverge and break `test_profiles.py`. The integer localizes the fix to the web side, which is the internally-inconsistent one.
- **Backend change is serializer-only for this slice:** no new models, migrations, or endpoints (profiles, avatars, and profile pages are Wave 4).
- **No N+1.** Every queryset feeding `PostAuthorSerializer` must `select_related` the author's `ForumProfile`. The existing `CaptureQueriesContext` pins must stay EXACT: post-list `== 3` (`test_post_list.py`), notifications `== 2` (`test_notifications_api.py`).
- **Preserve the "hide NEW" behaviour.** Today `trust_level` is `None`→`undefined`→falsy→no badge. After the change a real integer `0` (NEW) must STILL render no badge; only levels `>= 1` show a label pill. (This is the falsy-0 transition — test it explicitly.)
- **Do not touch the auth `User` trust_level enum** (`web/src/types/auth.ts`'s `'new' | 'basic' | 'trusted' | 'veteran' | 'expert'`, `authService.test.ts`, or `createMockUser`'s `trust_level`). That is a different, unrelated field.
- **Web conventions:** `.ts`/`.tsx` only; import router from `react-router-dom`; avoid `any`; `npm run type-check` must pass with zero errors.
- **Delivery:** this branch is `forum-wave2-slice1-author-display` off fresh `main`; kimi-review commit gate applies; never push to `main` directly (PR only).

## Rationale to carry into the PR description

**Backend-alone would regress the live UI.** Today the deployed web forum shows no trust badge (value is `None`→`undefined`→falsy). Shipping the backend integer without the web fix flips that to a literal **"2"** badge in production. The web change is therefore not scope creep — it unmasks a pre-existing latent mismatch that the backend change activates. This is why "serializer-only" (spec wording, meaning "no Wave 4 models/avatars/profile-pages") still requires the small web reconciliation.

---

## File Structure

| File | Responsibility | Task |
|------|----------------|------|
| `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py` | `PostAuthorSerializer` reads the joined `ForumProfile` | 1 |
| `backend/packages/wagtail_forum/wagtail_forum/api/views.py` | `PostListView` queryset joins `author__wagtail_forum_profile` | 1 |
| `backend/packages/wagtail_forum/wagtail_forum/api/notifications.py` | `NotificationListView` queryset joins `actor__wagtail_forum_profile` | 1 |
| `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py` | author payload + N+1 + profile-less tests | 1 |
| `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py` | actor payload + N+1 tests | 1 |
| `web/src/services/forumMappers.ts` | `BackendPostAuthor.trust_level: number \| null` | 2 |
| `web/src/types/forum.ts` | forum author `trust_level?: number` | 2 |
| `web/src/components/forum/PostCard.tsx` | integer → label map + `>= 1` render guard | 2 |
| `web/src/components/forum/PostCard.test.tsx` | integer fixtures + label assertions + NEW-hidden test | 2 |
| `web/src/services/forumMappers.test.ts` | integer `trust_level` at the backend boundary | 2 |
| `web/src/tests/forumUtils.ts` | `createMockPost` author fixture uses integer | 2 |
| `todos/273-in_progress-p1-forum-wave2-app-loop-primitives.md` | Wave 2 epic todo (traceability) | 3 |
| `docs/audits/2026-07-11-forum-modernization.md` | Finding Status: L14 → todo 273 | 3 |

---

## Task 1: Backend — real author `trust_level` + `display_name` with N+1-safe joins

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:255-265` (PostAuthorSerializer)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py:440` (PostListView.get_queryset)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/notifications.py:75-77` (NotificationListView.get_queryset)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py`

**Interfaces:**

- Consumes: `ForumProfile` (reverse OneToOne accessor `user.wagtail_forum_profile`, `related_name="wagtail_forum_profile"`), fields `trust_level` (int 0–4, `TrustLevel` IntegerChoices) and `display_name` (str, blank default `""`).
- Produces: `PostAuthorSerializer` output `{"username": str, "display_name": str, "trust_level": int | None}` — the shape `AUTHOR_SCHEMA` already declares. Consumed by web Task 2 as `BackendPostAuthor`.

**Context:** `PostAuthorSerializer` receives the author `User`. `get_trust_level` currently returns hardcoded `None`. `select_related` does NOT dedupe author instances across queryset rows, so accessing `obj.wagtail_forum_profile` per post/notification would be one query PER ROW (N+1) — which is exactly what the existing `CaptureQueriesContext` pins catch. Extending the `select_related` to include the profile folds it into the same SELECT.

- [ ] **Step 1: Write the failing tests (post-list author payload, N+1, profile-less)**

Add to the top import in `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py` (line 7):

```python
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic, TrustLevel
```

Append these three tests to `test_post_list.py`:

```python
@pytest.mark.django_db
def test_post_list_author_carries_trust_level_and_display_name():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    # Set profile fields AFTER the post exists so the post-save trust signal
    # (which recomputes trust_level from post_count) has already run and won't
    # clobber these values. REGULAR (3) is unreachable from 1 post, proving the
    # serializer reads the stored profile, not a recomputed level.
    profile = ForumProfile.for_user(author)
    profile.trust_level = TrustLevel.REGULAR  # 3
    profile.display_name = "Ada L."
    profile.save(update_fields=["trust_level", "display_name"])

    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    got = resp.data["results"][0]["author"]
    assert got["username"] == "ada"
    assert got["display_name"] == "Ada L."
    assert got["trust_level"] == 3


@pytest.mark.django_db
def test_post_list_author_profiles_add_no_per_post_queries():
    # 20 posts by 20 DISTINCT authors, each with their own ForumProfile — the
    # worst case for an author-profile N+1. select_related folds every profile
    # into the single posts SELECT, so the count stays the pinned 3.
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    starter = User.objects.create_user(username="starter")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=starter, live=True
    )
    for i in range(20):
        u = User.objects.create_user(username=f"u{i}")
        Post.objects.create(
            topic=topic,
            author=u,
            is_opening_post=(i == 0),
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )
    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20
    # Pinned EXACTLY (docs/rules/testing.md): Q1 visibility prefetch, Q2 topic
    # lookup, Q3 posts page (author + author profile + topic all select_related).
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_post_list_author_without_profile_still_renders():
    # A reverse OneToOne select_related is a LEFT OUTER JOIN, so a post whose
    # author has no ForumProfile row must NOT be dropped from the results.
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ghost")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    ForumProfile.objects.filter(user=author).delete()  # purge any signal-created row

    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    results = resp.data["results"]
    assert len(results) == 1  # row not dropped
    assert results[0]["author"]["username"] == "ghost"
    assert results[0]["author"]["trust_level"] is None
    assert results[0]["author"]["display_name"] == "ghost"  # username fallback
```

- [ ] **Step 2: Run the post-list tests to verify they fail**

Run:

```bash
cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py -v
```

Expected: the three new tests FAIL — `test_post_list_author_carries_trust_level_and_display_name` gets `trust_level == None` (not 3), and the two N+1/profile tests fail on the still-hardcoded `None` path (payload) — while the existing pins still pass. (If `..._add_no_per_post_queries` currently reports 3, that is because the hardcoded `None` never touches the profile; it will jump to 23 in Step 3 BEFORE the queryset fix, which is what proves the join is needed.)

- [ ] **Step 3: Write the failing notification tests**

Add to the top import in `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py` (the `from wagtail_forum.models import (...)` block, lines 8-15):

```python
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Notification,
    NotificationVerb,
    Post,
    Topic,
    TrustLevel,
)
```

Append to `test_notifications_api.py`:

```python
@pytest.mark.django_db
def test_notification_actor_carries_trust_level_and_display_name():
    recipient = User.objects.create_user(username="r")
    actor = User.objects.create_user(username="a")
    board = _board("gen-actor")
    topic, post = _topic_and_post(board, recipient, actor)
    _notify(recipient, actor, topic, post)
    profile = ForumProfile.for_user(actor)
    profile.trust_level = TrustLevel.LEADER  # 4
    profile.display_name = "Ann"
    profile.save(update_fields=["trust_level", "display_name"])

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.get("/forum/notifications/")
    assert resp.status_code == 200
    got = resp.data["results"][0]["actor"]
    assert got["username"] == "a"
    assert got["display_name"] == "Ann"
    assert got["trust_level"] == 4


@pytest.mark.django_db
def test_notification_list_actor_profiles_add_no_per_row_queries():
    recipient = User.objects.create_user(username="r2")
    board = _board("gen-nplus1")
    for i in range(5):
        actor = User.objects.create_user(username=f"act{i}")
        topic, post = _topic_and_post(board, recipient, actor, slug=f"t{i}")
        _notify(recipient, actor, topic, post)

    client = APIClient()
    client.force_authenticate(recipient)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/notifications/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 5
    # Pinned EXACTLY: the notification fetch + one .public() PageViewRestriction
    # lookup. actor + actor profile + topic + board all select_related, so 5
    # distinct actors add no per-row queries.
    assert len(ctx.captured_queries) == 2
```

- [ ] **Step 4: Run the notification tests to verify they fail**

Run:

```bash
cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py -v
```

Expected: `test_notification_actor_carries_trust_level_and_display_name` FAILS on `trust_level == None` (not 4).

- [ ] **Step 5: Implement — join the profile in `PostAuthorSerializer`**

In `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`, replace the current `PostAuthorSerializer` body (lines 255-265):

```python
class PostAuthorSerializer(serializers.Serializer):
    username = serializers.CharField(source="get_username")
    display_name = serializers.SerializerMethodField()
    trust_level = serializers.SerializerMethodField()

    @staticmethod
    def _profile(obj):
        # Reverse OneToOne accessor (ForumProfile.user, related_name
        # "wagtail_forum_profile"). Its RelatedObjectDoesNotExist subclasses
        # AttributeError, so getattr(..., None) yields None for an author with
        # no ForumProfile row instead of raising — and issues no query when the
        # caller select_related-joined the profile.
        return getattr(obj, "wagtail_forum_profile", None)

    def get_display_name(self, obj):
        profile = self._profile(obj)
        if profile and profile.display_name:
            return profile.display_name
        full = obj.get_full_name()
        return full or obj.get_username()

    def get_trust_level(self, obj):
        profile = self._profile(obj)
        return profile.trust_level if profile else None
```

- [ ] **Step 6: Implement — extend the two list querysets**

In `backend/packages/wagtail_forum/wagtail_forum/api/views.py`, change the `PostListView.get_queryset` return (line 440) from:

```python
        return topic.posts.filter(live=True).select_related("author", "topic")
```

to:

```python
        return topic.posts.filter(live=True).select_related(
            "author", "author__wagtail_forum_profile", "topic"
        )
```

In `backend/packages/wagtail_forum/wagtail_forum/api/notifications.py`, change the `NotificationListView.get_queryset` return (lines 75-77) from:

```python
        return _visible_notifications(self.request.user).select_related(
            "actor", "topic__board"
        )
```

to:

```python
        return _visible_notifications(self.request.user).select_related(
            "actor", "actor__wagtail_forum_profile", "topic__board"
        )
```

- [ ] **Step 7: Run both test files to verify all pass (including the unchanged pins)**

Run:

```bash
cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py -v
```

Expected: PASS — new tests green; the pre-existing pins (`test_post_list_is_cursor_paginated_with_bounded_queries` == 3, `test_post_list_affordances_add_no_per_post_queries` == 3, `test_notification_list_query_count_pinned` == 2) STILL green (the join adds no query).

- [ ] **Step 8: Run the wider forum suite to catch any serializer-shape regression**

Run:

```bash
cd backend && source venv/bin/activate && python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/ -q
```

Expected: PASS. (`test_schema.py` validates the OpenAPI schema; `AUTHOR_SCHEMA` is unchanged so it stays green.)

- [ ] **Step 9: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/serializers.py \
        backend/packages/wagtail_forum/wagtail_forum/api/views.py \
        backend/packages/wagtail_forum/wagtail_forum/api/notifications.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_list.py \
        backend/packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py
git commit -m "forum: serve real author trust_level + display_name (wave 2 slice 1)"
```

---

## Task 2: Web — consume integer `trust_level`, render as a label, hide NEW

**Files:**

- Modify: `web/src/services/forumMappers.ts:56` (BackendPostAuthor type)
- Modify: `web/src/types/forum.ts:51-55` (forum author trust_level type)
- Modify: `web/src/components/forum/PostCard.tsx` (label map + render guard, replacing lines 118-122)
- Test: `web/src/components/forum/PostCard.test.tsx`
- Test: `web/src/services/forumMappers.test.ts`
- Modify: `web/src/tests/forumUtils.ts:98` (mock author fixture)

**Interfaces:**

- Consumes: Task 1's `PostAuthorSerializer` payload `{username, display_name, trust_level: int | null}`.
- Produces: forum author `trust_level?: number`; PostCard renders the label from `TRUST_LEVEL_LABELS`.

**Context:** `PostCard.tsx:118-122` renders `{post.author.trust_level && (<span …>{post.author.trust_level}</span>)}` — the raw value. `NotificationBell.tsx` uses only `display_name`/`username` (no trust badge), so no notification-render change is needed.

- [ ] **Step 1: Update the failing PostCard tests to expect labels and hide NEW**

In `web/src/components/forum/PostCard.test.tsx`:

Change line 29 `trust_level: 'member',` → `trust_level: 2,` and the assertion at line 36 `expect(screen.getByText('member')).toBeInTheDocument();` → `expect(screen.getByText('Member')).toBeInTheDocument();`.

Change line 46 `trust_level: 'basic',` → `trust_level: 1,`.

Change line 248 `trust_level: 'regular',` → `trust_level: 3,`.

Change line 265 `trust_level: 'basic',` → `trust_level: 1,`.

Add a new test (place it right after the `renders post author information` test, ~line 37):

```tsx
  it('hides the trust badge for a NEW (level 0) author', () => {
    const post = createMockPost({
      author: {
        id: 1,
        email: 'newbie@example.com',
        username: 'newbie',
        display_name: 'New Person',
        trust_level: 0,
      },
    });

    renderPostCard(post);

    // Level 0 (New) is intentionally un-badged (preserves the prior falsy-0
    // hidden behaviour); only levels >= 1 get a label pill.
    expect(screen.queryByText('New')).not.toBeInTheDocument();
    expect(screen.getByText('New Person')).toBeInTheDocument(); // author still renders
  });
```

- [ ] **Step 2: Run PostCard tests to verify they fail**

Run:

```bash
cd web && npx vitest run src/components/forum/PostCard.test.tsx
```

Expected: FAIL — `getByText('Member')` finds nothing (component still renders the raw integer `2`), and the NEW test may pass-by-accident (raw `0` is falsy) — that is acceptable; it locks the behaviour once the label map lands.

- [ ] **Step 3: Implement — label map + render guard in PostCard**

In `web/src/components/forum/PostCard.tsx`, add this constant at module scope (just below the imports, above the component):

```tsx
// Forum trust levels mirror the backend ForumProfile.TrustLevel enum (0–4).
const TRUST_LEVEL_LABELS: Record<number, string> = {
  0: 'New',
  1: 'Basic',
  2: 'Member',
  3: 'Regular',
  4: 'Leader',
};
```

Replace the badge block (lines 118-122):

```tsx
              {post.author.trust_level && (
                <span className="px-2 py-0.5 bg-sky/10 text-ink text-xs rounded">
                  {post.author.trust_level}
                </span>
              )}
```

with:

```tsx
              {typeof post.author.trust_level === 'number' &&
                post.author.trust_level >= 1 && (
                  <span className="px-2 py-0.5 bg-sky/10 text-ink text-xs rounded">
                    {TRUST_LEVEL_LABELS[post.author.trust_level] ??
                      `Level ${post.author.trust_level}`}
                  </span>
                )}
```

- [ ] **Step 4: Run PostCard tests to verify they pass**

Run:

```bash
cd web && npx vitest run src/components/forum/PostCard.test.tsx
```

Expected: PASS — `Member` renders for level 2, the NEW-hidden test passes, avatar/username tests unaffected.

- [ ] **Step 5: Fix the types (mapper source + forum author)**

In `web/src/services/forumMappers.ts`, change line 56 from:

```typescript
  trust_level: string | null;
```

to:

```typescript
  trust_level: number | null;
```

(Line 119 `trust_level: a.trust_level ?? undefined` needs no change — nullish-coalescing preserves `0` and maps `null`→`undefined`.)

In `web/src/types/forum.ts`, replace lines 51-55:

```typescript
  // Forum posts carry a free-form trust label distinct from the auth User
  // enum, so override (not intersect) trust_level to a plain string.
  author: Omit<User, 'trust_level'> & {
    trust_level?: string;
  };
```

with:

```typescript
  // Forum posts carry the backend ForumProfile trust level as an integer enum
  // (0=New … 4=Leader), distinct from the auth User's string trust_level enum,
  // so override (not intersect) trust_level to a number.
  author: Omit<User, 'trust_level'> & {
    trust_level?: number;
  };
```

- [ ] **Step 6: Update the mapper + fixture tests to integer boundaries**

In `web/src/services/forumMappers.test.ts`, change line 202 `trust_level: 'member'` → `trust_level: 2`, and add an assertion after line 227 (`expect(p.author?.display_name).toBe('Jane Doe');`):

```typescript
    expect(p.author?.trust_level).toBe(2);
```

Lines 237 and 258 (`trust_level: null`) stay unchanged — `null` is valid for `number | null`.

In `web/src/tests/forumUtils.ts`, change the `createMockPost` author override at line 98 from:

```typescript
      trust_level: 'basic',
```

to:

```typescript
      trust_level: 1,
```

(Leave `createMockUser`'s `trust_level: 'basic'` at line 49 — that is the auth `User` enum, not the forum author.)

- [ ] **Step 7: Run the affected web tests + type-check**

Run:

```bash
cd web && npx vitest run src/components/forum/PostCard.test.tsx src/services/forumMappers.test.ts && npm run type-check
```

Expected: PASS with zero type errors.

- [ ] **Step 8: Run the full web unit suite to catch fixture fallout**

Run:

```bash
cd web && npx vitest run
```

Expected: PASS. (`createMockPost` feeds many forum tests; the integer override must not break any that read `post.author.trust_level`.)

- [ ] **Step 9: Commit**

```bash
git add web/src/services/forumMappers.ts web/src/types/forum.ts \
        web/src/components/forum/PostCard.tsx \
        web/src/components/forum/PostCard.test.tsx \
        web/src/services/forumMappers.test.ts web/src/tests/forumUtils.ts
git commit -m "forum web: render integer trust_level as a label, hide NEW (wave 2 slice 1)"
```

---

## Task 3: Wave 2 epic todo + finding traceability

**Files:**

- Create: `todos/273-in_progress-p1-forum-wave2-app-loop-primitives.md`
- Modify: `docs/audits/2026-07-11-forum-modernization.md` (Finding Status: L14 → todo 273)

**Context:** The roadmap's "Todo bookkeeping" requires a new Wave 2 epic todo with `source_review` pointing at the 2026-07-11 audit. This slice creates it as the home for all four Wave 2 slices; each later slice retargets the audit findings it actually closes in its own PR. This slice retargets only **L14** (`trust_level` renders as raw unstyled text) — the finding it fixes. `#H7` (public identity) stays at todo 257 because profiles remain a Wave 4 deliverable; 273 references the serializer subset without claiming H7.

- [ ] **Step 1: Create the Wave 2 epic todo**

Create `todos/273-in_progress-p1-forum-wave2-app-loop-primitives.md`:

```markdown
---
status: in_progress
priority: p1
issue_id: "273"
tags: [forum, api, drf, web]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H6, H7, L14, M6, M35, M36, M37, M39"
---

# Forum epic: Wave 2 — app-loop backend primitives (+ minimal web UI)

Wave 2 of `docs/superpowers/specs/2026-07-17-forum-app-loop-roadmap-design.md`.
Delivered as per-slice PRs off fresh `main`.

## Slices

- [x] **Slice 1 — Author display fix** (this PR): `PostAuthorSerializer` serves
  real integer `trust_level` + `display_name` from the joined `ForumProfile`
  (N+1-safe); web renders the integer as a label and hides NEW.
  Plan: `docs/superpowers/plans/2026-07-17-forum-wave2-slice1-author-display.md`.
  Closes L14; serves the serializer subset of H7 (public profiles stay Wave 4 / todo 257).
- [ ] **Slice 2 — Solved answers** (H6, moved from todo 256): `Topic.solved_post`
  FK + `solved_at`, `POST/DELETE /topics/{id}/solution/`, Solved badge +
  accepted-post highlight, accepted-answer notification, clear-on-unpublish rule.
- [ ] **Slice 3 — Identification embed** (M6, moved from todo 263):
  `ForumIdentificationAttachment` snapshot model, compose-time photo copy through
  the forum image upload pipeline, card above the opening post, "Ask the
  community" web entry point.
- [ ] **Slice 4 — Mobile-gating API hardening** (M35, M36, M37, M39 subset of
  todo 258): idempotency for `PATCH /posts/{id}/` + image upload (and the new
  solution endpoint), OpenAPI response-code completeness, error-envelope
  consistency across mobile-bound endpoints.

## Notes

Solved answers moved out of 256; the identification embed moved out of 263; the
mobile-gating subset split out of 258 — the remainder of each stays put. See the
roadmap's "Todo bookkeeping" section.
```

- [ ] **Step 2: Retarget the L14 finding in the audit**

In `docs/audits/2026-07-11-forum-modernization.md`, find the `## Finding Status` line for `#L14` (grep for `#L14`). Retarget it to todo 273, preserving the `(moved from …)` convention. For example, if it reads:

```markdown
- [ ] #L14 trust-level-raw-render → todo 257
```

change it to:

```markdown
- [ ] #L14 trust-level-raw-render → todo 273 (moved from 257)
```

(Use the finding's actual short-description slug as written in the file; only the `→ todo …` target and the `(moved from …)` note change.)

- [ ] **Step 3: Commit**

```bash
git add todos/273-in_progress-p1-forum-wave2-app-loop-primitives.md \
        docs/audits/2026-07-11-forum-modernization.md
git commit -m "docs: open Wave 2 epic todo 273 + retarget L14 finding (wave 2 slice 1)"
```

---

## Self-Review

**1. Spec coverage** (roadmap "Author display fix (pulled forward from Wave 4)"):

- "returns the real `trust_level` (currently hardcoded `None`)" → Task 1, Steps 5-6 (serializer + joins) + tests.
- "and `display_name`" → Task 1 `get_display_name` prefers `ForumProfile.display_name`.
- "Serializer-only; profiles, avatars, and profile pages stay in Wave 4" → no models/migrations/endpoints; web change is presentation-only (label render), justified by the regression argument.
- "the mobile client should not launch with faceless authors, and solved-answer badges are hollow without visible reputation" → rationale captured; the integer contract is honoured so mobile (Wave 3) reads the same field.
- Roadmap "Todo bookkeeping" (new Wave 2 epic todo with `source_review`) → Task 3.

**2. Placeholder scan:** every code step shows complete code; every test step shows the full test and the exact run command + expected result. Task 3 Step 2 leaves the L14 slug/target to a grep because the exact current line is in a large file the implementer opens — the transformation is fully specified.

**3. Type consistency:** backend returns `trust_level: int | None` (matches `AUTHOR_SCHEMA`); web `BackendPostAuthor.trust_level: number | null` → forum author `trust_level?: number` → `TRUST_LEVEL_LABELS: Record<number, string>` render. `createMockPost` author override is `number`; `createMockUser` (auth `User`) stays a string enum — deliberately distinct.

**Minor for final review:** single-object responses (reply-create, edit) do one extra `ForumProfile` query each (no `select_related` on those in-memory/`_get_visible_post` paths); this is not N+1 (single object) and no `CaptureQueriesContext` pin exists on those endpoints, so it is intentionally left out of scope for this slice.
