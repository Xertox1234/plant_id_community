---
status: completed
priority: p2
issue_id: "352"
tags: [blog, web, forum, api, moderation]
dependencies: []
---

# Blog post comments: wire existing BlogComment to frontend + forum anti-spam services

## Problem

Blog posts allow no reader participation — no way to comment, reply, or
discuss an article. Discussion is a proven engagement/retention driver
(Discourse's core premise, and the reason forum todos 339-350 exist).
The research finding: **`BlogComment` already exists end-to-end in the
backend but the frontend was never wired up**, and it lacks the forum's
spam/trust/rate-limit protections, so enabling the UI as-is would expose
an unprotected comment surface.

This was scoped as "a new Wagtail package reusing forum tech"; research
(summarized below) found that a new package is unnecessary — direct
`Topic`/`Post` reuse is architecturally wrong, third-party packages
(`django-comments-xtd` et al.) would create a parallel system with no
trust-level or auth integration, and the backend model/API/admin
moderation already exist. The work is: frontend UI + wiring forum
anti-abuse services into the existing comment flow.

## Findings

**Existing backend (all in `backend/apps/blog/`):**

- `BlogComment` model — threaded (`parent` self-FK for replies),
  `is_approved`/`is_flagged`/`flag_count`, indexes on
  `(post, created_at)`, `(author, created_at)`, `(is_approved, created_at)`.
  `backend/apps/blog/models.py:893-957`.
- DRF API: `BlogPostPageViewSet.add_comment` (auth-required, respects
  `allow_comments`) + `BlogCommentViewSet` CRUD incl. `flag`;
  non-staff see only approved comments. `backend/apps/blog/views.py:48-225`,
  `366-402`; serializer `backend/apps/blog/serializers.py:159-188`.
- Admin moderation: staff-only approve/reject routes + Wagtail
  homepage "Comments Pending Approval" widget.
  `backend/apps/blog/admin_urls.py:14-25`,
  `backend/apps/blog/admin_views.py:63-141`,
  `backend/apps/blog/wagtail_hooks.py:48-246`.
- `BlogPostPage.allow_comments` (default `True`) published in Wagtail
  API v2 `api_fields`; `comment_count` already computed in both the
  Wagtail API v2 serializer (`api/serializers.py:375-391`) and queryset
  annotations (`api/viewsets.py:191-196, 230-235`) — but the web
  frontend type ignores them.

**Missing today:**

- **No frontend at all.** `web/src/types/blog.ts:218-244` has no
  comment fields; `blogService.ts` only calls Wagtail API v2 (no comment
  endpoints); `BlogDetailPage.tsx` renders no comment section.
  Note: the comment endpoints are on the **DRF v1** API
  (`/api/v1/blog/…`), which the current `blogService` doesn't use —
  service will either add v1 calls or the endpoint surface needs
  deriving from v2 conventions.
- **No anti-abuse protection.** `add_comment` and `flag` have no rate
  limiting, no spam screening, no trust gating — every authenticated
  user's comment auto-approves (`is_approved` default `True`).
- Serializer caps replies at one level deep (`if obj.is_reply: return []`)
  — decide and document the intended thread depth.

**Forum components reusable for blog comments** (service-level, NOT
model-level — `Topic`/`Post` are hard-wired to `ForumBoard` and carry
forum-only semantics; reusing them directly would pollute forum
counters/search/notifications):

- Spam screening: `wagtail_forum/spam/base.py` `SpamBackend.check_text()`
  - host LLM backend `apps/forum_host/spam.py`. Screen flattened
  comment text before deciding `is_approved`.
- Trust gating: `ForumProfile.for_user(user).trust_level` — e.g.
  NEW/BASIC held for moderation, MEMBER+ auto-approved (threshold
  configurable).
- Rate-limit wrapper pattern: `apps/forum_host/api.py`
  `django-ratelimit` decorators — mirror on comment/flag endpoints.
- `UserBlock` — already content-agnostic; suppress replies/notifications
  from blocked authors.
- UI patterns for the frontend: `web/src/pages/forum/ThreadDetailPage.tsx`
  (composer, per-target draft persistence, moderation-pending banner,
  reports) and `web/src/utils/sanitize.ts` (DOMPurify MINIMAL preset).

**Ecosystem check (2026):** Wagtail's built-in `Comment` model is
editorial-only. Only maintained third-party visitor-comment package is
`django-comments-xtd`, which would be a parallel system with its own
moderation UI and no trust/auth integration — rejected in favor of the
existing `BlogComment`.

## Recommended Action

1. **Backend — protect the existing endpoints:**
   - On comment create, call `get_spam_backend()` (forum host wiring,
     heuristic fallback in package) on the comment text; spammy AND/OR
     below trust threshold → create with `is_approved=False`
     ("pending moderation") and surface that state in the API response,
     like the forum's moderation-pending notices.
   - Auto-approve above a trust threshold (`ForumProfile.trust_level >=
     MEMBER`); make the threshold a Django setting.
   - Apply `django-ratelimit` wrappers to `add_comment` and `flag`
     (mirror `apps/forum_host/api.py`); keep gotcha #4 in mind —
     the custom exception handler must map `Ratelimited` → 429.
   - Optionally fire notification events (reply-to-comment, flag) via a
     host-side helper — don't touch `wagtail_forum` internals for this.
2. **Frontend — build the comment section:**
   - Extend `BlogPost` type + `blogService.ts` with `comment_count`,
     `allow_comments`, comment list/create endpoints.
   - New `BlogCommentSection` component under `BlogDetailPage`:
     composer, reply, flag, moderation-pending banner — modeled on
     `ThreadDetailPage` patterns; render with DOMPurify MINIMAL.
   - Honor `allow_comments: false` → no composer.
3. **Tests:**
   - Backend: spam → held; low trust → held; high trust → approved;
     rate limit returns 429; `allow_comments=false` → 403 (exists).
   - Frontend: Vitest for section states (pending banner, disabled
     comments, empty state); Playwright happy path (post + reply).

## Technical Details

- Follow `django-ratelimit` 429-not-403 gotcha:
  `backend/docs/patterns/architecture/rate-limiting.md` (rule 4 in
  root CLAUDE.md).
- Comments are plain `TextField` today — keep plain text (escapes the
  whole rich-text sanitization question); rich-text comments are a
  possible follow-up using `wagtail_forum/api/sanitize.py`.
- Frontend draft persistence/composer patterns:
  `web/src/pages/forum/ThreadDetailPage.tsx`;
  React Router import from `react-router-dom` only (gotcha #2).
- Debounce/submit-timer handling via `useRef`, not `useState` (gotcha #5).
- If a migration is added, test DB rebuild: `python manage.py test
  apps.blog --noinput` (gotcha #6).
- Follow-ups explicitly OUT of scope: notification fan-out for every
  reply thread, comment editing/versioning, converting `BlogComment`
  to a Wagtail snippet + workflow (bigger migration), extracting a
  shared `wagtail_moderation` package (revisit only if a third
  commentable surface appears).

## Acceptance Criteria

- [x] Signed-in user can comment on a blog post from the web UI; reply
      to a comment (documented depth cap)
- [x] New/low-trust users' comments show "pending moderation" and are
      not publicly visible until approved via existing admin queue
- [x] Spam backend screens comment text before auto-approval
- [x] Rate limiting on comment create + flag returns 429 (not 403)
- [x] `allow_comments: false` hides/disables the composer
- [x] `comment_count` renders in the UI (list and/or detail page)
- [x] Backend tests: spam/trust gating, rate limit 429, visibility
      (non-staff see approved only)
- [x] Frontend tests: Vitest section states + Playwright post/reply
      happy path

## Work Log

### 2026-09-04 - Filed

- Research session: "extending forum functionality into blog comments".
  Key discovery: `BlogComment` model + DRF API + admin moderation queue
  predated the question; frontend was never wired and endpoints are
  unprotected. Rejected alternatives: (a) reusing `Topic`/`Post`
  directly (forum-shaped models, would corrupt forum semantics), (b) a
  new `wagtail_comments` package (over-engineering for two surfaces),
  (c) `django-comments-xtd` (parallel system, no trust/auth integration).

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Backend protection implemented (run 2026-09-05-1142)

Decisions:

- **Service-level reuse only** (`apps/blog/comments.py`): the forum spam
  backend (`get_spam_backend().check(adapter)`) and `ForumProfile.trust_level`
  decide `is_approved` on create; staff always approve; anything held waits
  in the existing admin queue. Threshold `BLOG_COMMENT_AUTO_APPROVE_TRUST_LEVEL`
  (default MEMBER = 2); rates `DEFAULT_BLOG_RATELIMITS`
  (`comment_create` 10/h, `comment_flag` 20/h) overridable via
  `BLOG_RATELIMITS`, applied with `apps.core.ratelimit` so the custom
  exception handler maps them to **429 + Retry-After** (gotcha #4).
- **Two holes beyond the todo's list closed:** the generic
  `BlogCommentViewSet` was a `ModelViewSet` — `POST /comments/` created a
  comment on ANY post with no `allow_comments`, spam, trust or rate check,
  and PUT/DELETE were open — now `ReadOnlyModelViewSet` + `flag` (405 test);
  and `parent` was never validated — now it must be an approved, top-level
  comment on the same post. **Thread depth documented: one level.**
- `post` is read-only on the serializer (the view binds it from the URL).
- Own pending comments/replies are returned to their author on the
  `comments` listing (`Q(is_approved) | Q(author=me)` + a prefetched
  `visible_replies`) so "awaiting moderation" survives a reload; the
  public listing hides them; staff see everything on `/comments/`.
- `flag`: per-user cache dedup (24 h), self-flag 400, `F()` increment,
  auto-flag at 5.

Evidence:

```text
$ pytest apps/blog/tests/test_comments_api.py → 12 passed
  (trusted → approved+public; low trust → pending, author-only, staff see; spam → held even for a leader; staff skip gates; threshold is a setting; 429 + Retry-After at 2/h; comments disabled → 403 read+write; anon/empty; depth cap + cross-post + pending-parent 400s; own pending reply visible to author only; generic writes 405; flag dedup/self/429)
```

Full backend suite with the comment protection (alone, `--create-db`):

```text
2184 passed, 8 skipped, 5 warnings in 298.79s (0:04:58)
```

### 2026-09-05 - Review round 1 (backend): cross-cutting + django-drf — all repaired

- **[high, cross-cutting] generic `/comments/` list N+1** (no reply prefetch;
  the serializer fell back to a query per row; `is_reply` also fetched the
  parent per reply) — repaired: `Prefetch("replies", …, to_attr="visible_replies")`
  on both branches of `get_queryset`, `is_reply` reads `parent_id`; pinned
  exactly (per-post route 7 queries with 2 comment queries; generic 3 with
  3) — flat in the number of comments.
- **[medium, django] spam backend called before the trust check** — for a
  low-trust author the outcome is fixed, so a billable LLM backend would be
  paid for nothing. Repaired: staff → trust → spam (mirrors
  `_screen_dm_body`); test counts backend calls (0 below trust, 1 at/above).
- **[medium, django] auto-flag had no observable outcome** (`is_flagged`
  read nowhere) — repaired: at the threshold the comment is also pulled
  from public view (`is_approved=False`) into the existing pending queue;
  test with 5 distinct flaggers.
- **[low, cross-cutting] `parent` was an id oracle** (distinct errors for
  "exists elsewhere" vs "missing") — repaired: `resolve_parent` is scoped to
  what the caller can see on THIS post; cross-post, missing and another
  member's pending id all get the same generic 400; `parent` is read-only
  on the serializer.
- **[medium] tests:** `isinstance` hedge removed (the list IS paginated),
  anonymous → exact 401, unpublished + view-restricted posts 404 for both
  routes, auto-flag threshold, exact query pins; **[low]** 429s documented
  via `@extend_schema` on both actions; type hints on the service module.

```text
$ pytest apps/blog/tests/test_comments_api.py → 15 passed
```

### 2026-09-05 - Web half (implemented by a general-purpose agent against the contract, reviewed below)

- `services/blogCommentService.ts` (`fetchBlogComments`, `addBlogComment`,
  `flagBlogComment`, 2000-char client cap; throws `ForumApiError` with
  `.status`; handles the `{message}` envelope and a plain `{detail}`),
  `components/blog/BlogCommentSection.tsx` mounted last inside
  `BlogDetailPage`'s `<article>`: heading count from `comment_count` then the
  loaded list; closed → note, no composer, no fetch; signed-out → list +
  "Sign in to comment"; composer, one reply composer at a time (approved
  top-level only), Flag on others' approved comments, "Awaiting moderation —
  only you can see this" badge, 429/403/400 messages (the envelope's
  `parent:`/`content:` prefix stripped), one always-mounted live region,
  epoch guard keyed to the post id.
- **Production bug found and fixed while mounting:** `fetchBlogPost` hit the
  LISTING route (`?slug=…&fields=*`), which since todo 306 (2026-08-17) uses
  `BlogPostPageListSerializer` and ignores `fields=*` — live-probed locally
  AND in prod: no `content_blocks`/`introduction`/`related_posts`/
  `allow_comments`, so the web article body has been empty since then. Now
  resolves slug → id (listing, `limit=1`) then `GET /api/v2/blog-posts/<id>/?fields=*`.
  Web-only; flagged in the PR.
- `web/e2e/blog-comments.spec.js` (authenticated projects only, three-place
  scoping): posts a unique comment and replies to the first approved
  top-level comment; the local dev DB was migrated (0027–0033 were pending)
  so the running server matched its code.

```text
$ vitest run (full web) → Test Files 96 passed (96) / Tests 1194 passed (1194)
$ npm run type-check → clean; eslint (12 files) clean; prettier clean
$ playwright test --project=chromium-authenticated e2e/blog-comments.spec.js → 2 passed (6.5s) [comment-state: approved, reply-step: replied]
mutation check: removing the epoch guard fails exactly the race test; MUTANT residue 0
```

Post-repair full backend suite (alone, `--create-db`):

```text
2187 passed, 8 skipped, 5 warnings in 275.77s (0:04:35)
```

### 2026-09-05 - Review round 1 (web): react-typescript reviewer — all repaired

- **[high] a failed initial load shadowed every later write outcome** in the
  live region (`loadError ?? notice`) — repaired: the write outcome wins
  (`notice ?? loadError`); test posts after a failed load and reads the
  moderation notice.
- **[medium] detail-hop 404 miscategorised** (axios's message, not the
  page's `/not found/` branch) — repaired: a 404 on the id-addressed detail
  GET rethrows `Blog post not found` (by STATUS, with `cause`).
- **[medium] retry during an in-flight submit could duplicate the comment
  row** — repaired: appends go through an id `upsert` (top-level and
  replies); test resolves the refresh before the submit's echo → one row.
- **[medium] E2E replied to "the first approved comment" (seeded)** —
  repaired: the spec replies to the comment IT posted; a held comment
  skips the reply step with an annotation. Still depends on a seeded blog
  post with comments enabled, like the forum spec depends on a board.
- **[low] no unmount invalidation** — repaired: the effect cleanup bumps
  the epoch (via a stable callback so the lint's node-ref heuristic is not
  tripped); **[low] prefix stripping only on the first segment** →
  per-segment.

### 2026-09-05 - Acceptance criteria evidence

- Comment + reply from the web UI: `BlogCommentSection` tests (submit
  appends / reply POSTs `parent`) and Playwright `blog-comments.spec.js`
  → 2 passed (comment approved, reply posted). Thread depth documented: one
  level (backend `resolve_parent`, UI offers Reply on top-level only).
- Pending moderation: backend `test_low_trust_comment_is_held_visible_to_its_author_only`
  (public/other members see nothing; author sees it; staff see it in the
  admin route) + UI badge test.
- Spam backend screens before auto-approval: `test_spam_flagged_text_is_held_for_a_trusted_member_and_never_screened_below_trust`.
- Rate limiting 429 (not 403) on create and flag: `test_comment_create_is_rate_limited_with_429_not_403`,
  `test_flag_is_deduped_per_user_rate_limited_and_never_self` (+ `Retry-After`).
- `allow_comments: false` hides the composer: UI test (closed → note, no
  composer, no fetch) + backend 403 on read and write.
- `comment_count` renders: the section heading "Comments (N)" from the v2
  payload, then the loaded list (UI test).
- Backend tests: 15 in `test_comments_api.py` (gating, 429, visibility,
  depth, generic writes 405, flag semantics, query pins); blog app 272
  passed; full backend suite 2187 passed.
- Frontend tests: `BlogCommentSection.test.tsx` 17, `blogCommentService.test.ts`
  11, `BlogDetailPage.test.tsx` +2; full web suite **1197 passed (96 files)**;
  Playwright happy path 2 passed.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 8 acceptance criteria evidenced (backend 2187 passed / web 1197 passed / Playwright post+reply 2 passed).
- Review: cross-cutting + django-drf (backend), react-typescript (web) — 1 round each; every finding repaired (generic list N+1 + prefetch, trust-before-spam, auto-flag hides into the queue, parent id oracle closed, exact pins; live-region shadowing, detail 404, retry dedupe, own-comment E2E reply, unmount epoch, per-segment prefixes).
