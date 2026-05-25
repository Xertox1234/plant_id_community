# Forum Modernization & Hardening (Web) — Design

- **Date:** 2026-05-25
- **Status:** Approved (brainstorming) — ready for implementation planning
- **Scope:** Web forum only. The Flutter mobile app is explicitly out of scope.
- **Author:** Brainstorming session (William + Claude)

## Background

The repo's web forum is a half-finished revival sitting on a working backend. A
prior Discourse install was fully removed (no remnants in the codebase). What
"works with Django" today is a **django-machina**–based forum, exposed through a
custom DRF API and consumed (incompletely) by a React frontend.

Three layers exist:

1. **Backend data layer — django-machina** (installed via `ENABLE_FORUM=True` in
   `backend/plant_community_backend/settings.py`). Provides categories, topics,
   posts, permissions, trust levels, moderation, search, tracking, polls.
2. **API shim — `backend/apps/forum_integration/`** (DRF). Wraps machina behind
   `/api/v1/forum/*` (wired in `backend/plant_community_backend/urls.py`). Adds
   rich posts, image attachments (max 6/post), reactions, search, AI-assist,
   plant mentions, and a moderation queue. This is the **active** forum app.
3. **Frontend — React 19 + TS** in `web/src/pages/forum/` and
   `web/src/components/forum/`. Modern (TipTap editor, image upload widget) but
   **abandoned half-built and currently broken**: it calls `/threads/` endpoints
   while the API serves `/topics/`, so it cannot fetch anything.

Two dead/legacy artifacts also exist and should be removed:

- `backend/apps/forum/` — gutted stub (only a `.backup` test file), not in
  `INSTALLED_APPS`.
- Server-rendered Django templates (`forum_integration/templates/.../*_simple.html`)
  and their views, which **bypass permission checks "temporarily for debugging."**
  Already commented out of `urls.py`, so not exposed — but dead risky code.

## Goal

Take the abandoned React forum to a state that is:

1. **Working** end-to-end against the live django-machina + DRF backend.
2. **Secure** to a "safe to put online" bar — the user's explicit bar is "stable
   and won't get hacked the minute I put it online."
3. **Mobile-responsive** — usable on phone/tablet browsers.

New forum features are **deferred** (see Out of Scope).

## Non-Goals / Out of Scope

- **New features:** notifications, @-mentions, unread tracking, subscriptions /
  bookmarks, mark-as-solved / best-answer, reporting / flagging, polls, topic
  tags. (Several are machina-backed and cheap later — captured for a follow-up.)
- **API resource renaming** (`/topics/` → `/threads/`). Cosmetic; not worth the
  backend churn under this scope.
- **Flutter mobile app.**
- **Building new registration defenses** — signup is already IP-rate-limited
  (see Preconditions). We verify, we don't rebuild.

## Architecture — What Stays vs. Changes

| Layer | Decision |
|-------|----------|
| django-machina data layer | **Unchanged** — source of truth for forum data |
| DRF API (`forum_integration`) | **Hardened + contract kept**, not redesigned |
| Auth (`apps/users`, JWT/Firebase) | **Unchanged** — public read, authenticated write |
| React forum (`web/.../forum`) | **Finished, secured, made responsive** |
| `backend/apps/forum` (gutted) | **Deleted** |
| Server-rendered `*_simple.html` views/templates | **Deleted** (dead permission-bypass code) |

### Decided trade-offs

- **API contract fix direction: change React, not the API.** Fewer files, no
  backward-compat shim, and **no DB migration for the contract realignment**
  (this guarantee is scoped to the React/endpoint changes — it is *not* a
  claim that all of Phase 2 is migration-free). The React `forumService.ts` +
  types + pages are realigned to the real endpoints. "Threads" naming is
  cosmetic and out of scope.
- **Server-side sanitizer: `nh3`** (maintained, Rust-based ammonia bindings).
  `bleach==6.3.0` is already installed, but Mozilla **archived/deprecated bleach
  in 2023** — building new authoritative security logic on an unmaintained
  dependency is a poor bet. We add `nh3` (small, ships prebuilt wheels) as the
  primary sanitizer and keep the already-present `bleach` as a fallback if `nh3`
  wheels are problematic on the deploy target. Verified: `nh3` is **not**
  currently installed, so this adds one dependency. The backend allowlist
  mirrors the existing React `SANITIZE_PRESETS.FORUM` config
  (`web/src/utils/sanitize.ts`).

## Verified Current State (recon, with references)

Confirmed by direct inspection of `backend/apps/forum_integration/api_views.py`,
`serializers.py`, and `web/src/components/forum/PostCard.tsx`:

**Security gaps (the spine of Phase 2):**

1. **No rate limiting anywhere** in the forum API — `grep` for
   `ratelimit/throttle` in `api_views.py`/`api_urls.py` returns nothing. Posts,
   reactions, image uploads, search, and **`forum_ai_assist`** are all
   unthrottled → spam floods, brute force, and real-money LLM cost abuse.
   (`django-ratelimit==4.1.0` is already a dependency, used in `apps/users`,
   `apps/garden`, etc.; the 429 conversion lives in `apps/core/exceptions.py` /
   `apps/core/middleware.py` — the forum just doesn't use it.)
2. **Unbounded pagination** — `page_size = int(request.GET.get("page_size", 25))`
   (`api_views.py:74`) goes straight into `Paginator` with no cap, on `AllowAny`
   endpoints → `?page_size=10000000` is a trivial memory DoS.
3. **Spoofable image upload** — only `uploaded_file.size` (5 MB) and
   client-supplied `uploaded_file.content_type` are checked
   (`api_views.py:689–705`). No magic-byte / PIL verification, no extension
   allowlist, no re-encode. Violates the repo's own 4-layer file-upload pattern.
4. **No server-side HTML sanitization** — raw TipTap HTML is stored in
   `content_raw`; `content_format` is an unconstrained `CharField`
   (`serializers.py:334`). React sanitizes on render
   (`PostCard.tsx:48–49,131` via `sanitizeHtml(..., SANITIZE_PRESETS.FORUM)`,
   with an XSS test) — but that is defense-in-depth, not authoritative. Any other
   consumer (email, the old templates, the mobile app, a future API client)
   renders it raw.
5. **Trust levels not wired** — API hardcodes `"can_attach_files": user.is_staff`
   (`api_views.py:1096`) instead of using machina's trust-level / PermissionHandler.
6. **Dead permission-bypassing views** — `forum_integration/views.py` skips
   permission checks "for debugging"; commented out of `urls.py` but should be
   deleted, not left lying around.

**Functional blocker:** the `/threads/` ↔ `/topics/` mismatch between
`web/src/services/forumService.ts` and `api_urls.py` means the React forum can't
load at all.

**Already fine (do not "fix"):** API `permission_classes` are set explicitly per
view; ownership checks are present (`post.poster != request.user and not
request.user.is_staff`, e.g. `api_views.py:389,419,660`); CSRF is wired; search
escapes SQL wildcards via `escape_search_query()`.

### React forum inventory (Phase 1 starting point)

Everything below **exists** but is **broken at runtime** because `forumService.ts`
targets `/threads/` while the API serves `/topics/`. "Broken" = renders but can't
fetch; "partial" = also has unfinished flows.

| File | Status |
|------|--------|
| `web/src/pages/ForumPage.tsx` | exists — entry/wrapper |
| `web/src/pages/forum/CategoryListPage.tsx` | exists, broken (contract) |
| `web/src/pages/forum/ThreadListPage.tsx` | exists, broken (contract) |
| `web/src/pages/forum/ThreadDetailPage.tsx` | exists, **partial** + broken (reply flow, pagination) |
| `web/src/pages/forum/SearchPage.tsx` | exists, broken (contract) |
| `web/src/components/forum/CategoryCard.tsx` | exists |
| `web/src/components/forum/ThreadCard.tsx` | exists |
| `web/src/components/forum/PostCard.tsx` | exists — read-sanitizes content ✓ |
| `web/src/components/forum/TipTapEditor.tsx` | exists — emits raw HTML via `getHTML()` |
| `web/src/components/forum/ImageUploadWidget.tsx` | exists — needs wiring to real upload endpoint |
| `web/src/services/forumService.ts` | exists, **broken** (wrong endpoints) — primary Phase 1 fix |
| `web/src/types/forum.ts` | exists — needs realignment to API response shapes |

Each has a colocated `*.test.tsx`/`*.test.ts` to realign.

## Preconditions (verify before launch — not built here)

- **Open registration is the dominant day-one attack vector.** Signup in
  `apps/users/views.py` is already IP-rate-limited (multiple `@ratelimit`
  decorators; `apps/users/tests/test_rate_limiting.py` exists). **No CAPTCHA**
  found. Launch gate: confirm **email verification is enforced** before exposing
  the forum publicly. If not, that is a separate task, not this one.
- **Shared-endpoint consumers.** The Flutter app shares the backend but,
  verified, **does not currently consume any forum endpoint** (zero
  forum-API references in `plant_community_mobile/lib`). So the Phase 2 API
  changes (429s, `page_size` caps, stricter upload validation) carry **no mobile
  compatibility risk today**. Forward-looking note only: if a Flutter forum
  client is added later, it must handle 429 responses and the `page_size` cap.

## Phased Plan

### Phase 1 — Make it work (functional)

- **Realign the React API contract to the real endpoints.** Produce an
  endpoint-by-endpoint mapping (React expected → actual API) covering
  `/categories/`, `/categories/{id}/topics/`, `/topics/{id}/`, `/posts/`,
  `/posts/{id}/` (PATCH/DELETE), `/posts/{id}/images/…`, `/posts/{id}/reactions/`,
  `/search/`, `/stats/`. Update `forumService.ts`, `types/forum.ts`, and the
  pages/components accordingly.
- **Finish unfinished pages/flows:** `ThreadDetailPage` reply flow + pagination,
  create-topic and reply, reactions wiring, `ImageUploadWidget` against the real
  upload endpoint.
- **Prove the golden path end-to-end** against the live backend: list categories
  → open category → open topic → reply → react → upload image.
- **Tests:** realign `forumService.test.ts` to actual endpoints; component tests
  for completed pages; one Playwright e2e for the golden path.

### Phase 2 — Make it safe (security — the core)

1. **Audit first.** Run the repo's `security-reviewer` agent over the whole forum
   surface (backend `api_views.py`/`serializers.py` + React forum), triage
   findings by severity. This catches what greps missed; the items below are the
   known floor, not the ceiling.
2. **Harden, using existing repo patterns:**
   - **Rate limiting** (`django-ratelimit`) on create-topic, create-post,
     reactions, image upload, and search. **AI-assist gets a stricter per-user
     daily request cap** (`@ratelimit(key="user", rate="N/d")`) — a request
     count, **not** a token/dollar accounting cap, so it needs no custom spend
     state (django-ratelimit uses the existing Redis cache backend). 429
     responses and their logging are already handled centrally by
     `apps/core/exceptions.py` (it converts `Ratelimited` → 429 and emits
     `logger.warning("429 Rate Limit Exceeded", ...)`), so every endpoint that
     adds the decorator inherits correct status + logging for free.
   - **Pagination caps** — clamp `page_size` (max 100) on every list endpoint
     (closes the `?page_size=10000000` DoS at `api_views.py:74`).
   - **Image upload** — add the project's 4-layer validation (extension
     allowlist + MIME + size + **PIL magic-byte verify / re-encode**); stop
     trusting client `content_type`.
   - **Rich-content XSS (new + legacy)** —
     - *On write:* **sanitize `content_raw` server-side with `nh3`** (allowlist
       mirroring `SANITIZE_PRESETS.FORUM`) as the authoritative layer.
     - *content_format:* enforce an allowed set via a **serializer `ChoiceField`**
       (`plain`/`draftail`/`html`), **not** model-level `choices` — the
       authoritative gate is the API (all writes are API-mediated) and this
       avoids a migration on the `models.py:480` field.
     - *Legacy data:* add a **one-time backfill management command**
       (`sanitize_forum_content`) that re-sanitizes all existing `content_raw`.
       React already read-sanitizes (`PostCard.tsx`), so the React consumer is
       not currently exposed; the backfill closes the gap for every *other*
       consumer (email, RSS, future API clients) authoritatively.
     - *Defense-in-depth:* keep React's read-side sanitize; audit **all** render
       sites (PostCard ✓, thread-list excerpts, search snippets).
   - **Forum-level authorization (security)** — the API currently gates writes
     with plain `IsAuthenticated` and does not consult machina's per-forum
     permissions. `MACHINA_DEFAULT_AUTHENTICATED_USER_FORUM_PERMISSIONS`
     (`settings.py:751`) grants authenticated users full rights *except*
     `can_attach_files`, so this is functionally correct **for default/public
     forums**. **Time-boxed (1 day):** verify whether any forum is configured
     restricted and, if so, enforce machina `PermissionHandler` read/write checks
     in the API. **Fallback if blocked:** keep the current explicit
     `IsAuthenticated` + ownership gates (safe for the all-public model) and file
     a follow-up todo.
   - **Attachment gating** — replace the hardcoded
     `"can_attach_files": user.is_staff` (`api_views.py:1096`) with machina's
     `PermissionHandler.can_attach_files(forum, user)`. Note: `is_staff` is
     already a *safe* (restrictive) default, not a hole — this change makes it
     *correct* (honors configured grants). **Fallback:** keep `is_staff` if the
     PermissionHandler integration proves config-heavy within the time-box.
   - **Delete dead code** — server-rendered `*_simple.html` views/templates and
     the gutted `backend/apps/forum`.
   - **Per-endpoint authz audit** — confirm every `AllowAny` is intentional
     (read-only) and every write is owner/staff-gated.
3. **Verify the registration precondition** (above); document the launch gate.
4. **Tests — security regression suite:** 429 on each rate-limited endpoint
   (incl. AI-assist daily cap); oversized `page_size` clamped/rejected;
   spoofed-MIME / non-image upload rejected; stored-XSS payload sanitized
   server-side on write; `content_format` outside the allowed set rejected by the
   serializer; the backfill command neutralizes a pre-existing malicious
   `content_raw` row; non-owner edit/delete forbidden.

### Phase 3 — Make it fit (responsive)

- Mobile overhaul of forum pages/components per
  `web/RESPONSIVE_LAYOUT_PATTERNS.md` and `web/docs/patterns/tailwind.md`:
  category grid → stacked, denser thread lists, readable post width, compact /
  sticky reply editor (TipTap toolbar on small screens), touch-friendly image
  upload + lightbox, nav / breadcrumbs.
- **Verify in a real mobile-width browser** (not just tests), plus Playwright
  viewport tests at mobile / tablet / desktop.

## Testing Strategy (overall)

- **Backend:** pytest against a **real DB (no mocks**, per repo rule); strict
  query-count assertions where relevant (forum list/detail serialization).
- **Web:** Vitest component + service tests; Playwright e2e for the golden path
  and responsive viewports.
- **Security regression suite** as enumerated in Phase 2.4.

## Risks

- **machina permission/attachment wiring** may surface config gaps. Time-boxed
  to 1 day; fall back to the current explicit `IsAuthenticated` + `is_staff`
  gates (safe for the all-public model) with a documented follow-up if blocked.
- **Legacy `content_raw` data** is unsanitized until the backfill command runs.
  Mitigation: the backfill is part of Phase 2 and the React consumer already
  read-sanitizes, so exposure is bounded to non-React consumers in the window
  before backfill. Run the backfill before any non-React consumer ships.
- **`nh3` adds a dependency.** It ships prebuilt wheels for common platforms; if
  the deploy target lacks a wheel, fall back to the already-installed `bleach`.
- **Contract realignment surface** — the React forum may expect response shapes
  the API doesn't return (e.g., slugs vs. ids). The Phase 1 mapping step exists
  to surface these before coding; some serializer additions may be needed.
- **Audit scope creep** — `security-reviewer` may surface findings beyond the
  known gaps. Triage by severity; only CRITICAL/HIGH are in-scope for this
  project, the rest become deferred todos.

## Open Questions for Implementation Planning

- Should AI-assist be locked to trusted users (not just rate-limited) given it is
  a direct cost vector? (Default assumption: per-user daily request cap is enough
  for now; revisit if abuse is observed.)
- Exact per-endpoint rate-limit values (the `page_size` cap is set at 100; rate
  values default to `apps/users` conventions, finalized in the plan).
