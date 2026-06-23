---
status: in_progress
priority: p1
issue_id: "231"
tags: [forum, api, web, spec-2]
dependencies: []
source_review: "docs/audits/2026-06-10-forum.md"
source_finding: "H4"
---

# Forum Spec 2: read API (topic detail/posts) + migrate the web client off the machina dialect

## Problem

The React forum client (`web/src/services/forumService.ts`) still calls the
retired machina API (`/api/v1/forum/categories/`, `GET /topics/<id>/`,
`/posts/...`). The new `wagtail_forum` API mounted at `api/v1/forum/` serves
`boards/` and has **no read endpoints for topic detail or posts** — every web
forum page 404s against the live (deployed) API today. The design spec
explicitly deferred client migration + post-detail to "Spec 2", but nothing
tracked it; this todo is that tracker.

## Findings

- 2026-06-10 forum audit, finding H4 (api-design agent; verified by grep):
  `web/src/services/forumService.ts:34-261` calls `categories/`, `topics/<id>/`
  (GET), `posts/?topic=`, `posts/<id>/` PATCH, `posts/<id>/delete/`,
  `posts/<id>/reactions/` GET, `posts/<id>/images/` — none exist in
  `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`.
- Design spec (`docs/superpowers/specs/2026-06-06-wagtail-native-forum-package-design.md`
  line 77): client updates are "Spec 2". Spec table (line 247) already sketches
  `GET /topics/{id}/` and post list endpoints.
- Plan 1C line 1089: image-rendition serialization "arrives with post-detail …
  in Spec 2"; body serialization MUST go through `expand_db_html()`
  (`blocks.py:18-21` SECURITY comment).
- Audit L10 (deferred here): verb-style create routes (`…/topics/create/`)
  and mixed slug/id identifiers should be rationalized when the final Spec 2
  surface is defined — no consumer exists yet, so the rename is free until then.
- kimi-review note (2026-06-10): `/sync/` `next_since` + `gte` boundary can
  livelock if >200 live topics share one `updated_at` (e.g. bulk import).
  Spec 2 should move to a compound `(updated_at, id)` cursor.

- Phase 6 review LOWs folded in (2026-06-10): sync `board` param silently
  empty on typo/ambiguous slug (should 404/409 like `_get_board`); ancestor
  (ForumIndex) liveness not part of `_visible_boards()`; user-deletion cascade
  of Reactions never recounts `post.reaction_counts`; OpenAPI response-code
  gaps (429 on throttled host wrappers, 422/400/409 branches); idempotency
  endpoint-scope isolation test.

## Recommended Action

1. Write Spec 2 (brainstorm + plan per superpowers workflow): read endpoints —
   topic detail (with `expand_db_html()` body serialization + image renditions),
   cursor-paginated post list, reaction state per post (`reacted_by_me`).
2. Rationalize write routes (POST-to-collection) while no consumer depends on
   them; keep host rate-limit wrappers + parity test in sync.
3. Replace `forumService.ts` with a client for the new contract; delete the
   machina-era types; update React forum pages.
4. Compound sync cursor `(updated_at, id)`.
5. Decide image story (upload path + collection validation) — chooser blocks
   are currently rejected on the API path (`api/sanitize.py`, audit L5).

## Technical Details

- Backend package: `backend/packages/wagtail_forum/wagtail_forum/api/`
- Host wrappers: `backend/apps/forum_host/api.py` + `api_urls.py` (route-parity
  test in `apps/forum_host/tests/test_ratelimits.py` will fail on any new
  package route until the host mounts it — by design).
- Web: `web/src/services/forumService.ts`, forum pages under `web/src/`.

## Acceptance Criteria

- [x] Topic detail + post list read endpoints exist, schema-annotated, with
      `expand_db_html()` body serialization and query-count-pinned tests.
      (read endpoints + `expand_db_html` + query pins landed Phase 1; PR-1
      2026-06-23 added `@extend_schema` + `swagger_fake_view` guards to
      `TopicDetailView`/`PostListView`. `tests/api/test_schema.py` green;
      `manage.py spectacular` exits 0 with both forum read ops documented.)
- [ ] Web forum pages render against the live API (no machina paths remain;
      `grep -r "categories/" web/src/services/` is empty). *(PR-2/PR-3 — write
      path + images. Note: the literal grep also matches `blogService.ts`'s
      `/api/v2/categories/`; the real gate is no machina forum paths in
      `forumService.ts`.)*
- [x] Sync uses a compound cursor; same-timestamp livelock test added.
      (PR-1 2026-06-23 — `SyncView` filters `Q(updated_at__gt) | Q(updated_at=,
      id__gt)` ordered `(updated_at, id)`, returns `next_since_id`;
      `test_sync_compound_cursor_advances_through_same_timestamp_rows` green.)
- [ ] Route-parity test green with the final URL surface. *(parity green now —
      `test_host_api_routes_match_package` passes — but the "final URL surface"
      arrives with PR-2's route rationalization; keep open until then.)*

## Work Log

### 2026-06-10 - Created

- Filed from forum audit H4 (+ L10, sync-cursor note) during Phase 4 deferral;
  everything else from the audit was fixed in the audit branch.

### 2026-06-21 - Phase 1 (read path) landed — todo still OPEN (Phase 2/3 remain)

Spec + plan: `docs/superpowers/specs/2026-06-20-forum-spec2-read-write-client-design.md`,
`docs/superpowers/plans/2026-06-20-forum-spec2-phase1-read-path.md`. Branch
`feat/forum-spec2-web-client` (subagent-driven execution, 8 tasks, each reviewed).

**Done in Phase 1:**

- Backend read endpoints: `GET /topics/{id}/` (topic-detail) + `GET /topics/{id}/posts/`
  (cursor-paginated) with `expand_db_html()` body serialization and EXACT query-count
  pins. Search extended to topics + posts (full parity) — required adding
  `index.RelatedFields("topic", [live, board_id])` to `Post.search_fields` so the DB
  backend can visibility-filter post hits. `seed_default_forum` idempotent command.
  Route-parity guard green; forum backend suite 114 passed.
- Web read client rewritten to the new contract (boards/topics/posts/search); machina
  read paths gone; post bodies render via `StreamFieldRenderer`. Thread view is
  **read-only for Phase 1** (reply/react/delete controls hidden behind a "coming soon"
  notice — user-approved) since the write endpoints are Phase 2. Web suite green.

**Still open (do NOT close this todo):**

- Phase 2: write path (create/edit/delete post, reactions) + re-enable the write UI;
  `grep categories/ web/src/services/` still hits the un-rewritten `createThread`.
- Phase 3: image upload + rendition serialization (chooser blocks still rejected on the
  API path); add the `image` case back to `StreamFieldRenderer`.
- Compound `(updated_at, id)` sync cursor + same-timestamp livelock test (kimi note).
- Route rationalization (audit L10): verb-style create routes + mixed slug/id identifiers.

**Phase 1 tech-debt follow-ups (small):**

- topic-detail query pin is N=4 and includes a redundant Q4
  (`SELECT id, topic_id FROM post WHERE id=… LIMIT 21`) — a refetch of the opening post
  already found by `get_opening_post_id`. Constant-cost; eliminate when convenient.
- New DRF views are auto-schema'd (spectacular warnings, non-gating). "schema-annotated"
  acceptance wants `@extend_schema`/`@extend_schema_field` + `swagger_fake_view` guards.
- Deploy: confirm `seed_default_forum` runs in the Railway release step (not just
  documented in `backend/CLAUDE.md`) so prod isn't error-free-but-empty.

### 2026-06-23 - PR-1 (backend cleanup) landed — AC1 + AC3 done; todo still OPEN

**PR #394** (open, not auto-merged — owner merges). Branch
`feat/forum-spec2-phase2`; spec open questions resolved + plan written
(`docs/superpowers/plans/2026-06-23-forum-spec2-pr1-backend-cleanup.md`). The
remaining epic is decomposed into 3 PRs (PR-1 backend cleanup, PR-2 write path,
PR-3 images); this is PR-1.

**Done in PR-1 (TDD, two commits):**

- **AC1** — `@extend_schema` + `swagger_fake_view` guards on `TopicDetailView`/
  `PostListView`. The guard is load-bearing: `PostListView.get_queryset` calls
  `get_object_or_404`, which dropped the path during schema generation until
  guarded. New `tests/api/test_schema.py` generates the schema under the REAL
  urlconf (the project's `preprocess_exclude_wagtail` hook keeps only `/api/v1/*`,
  so the bare `/forum/` test urlconf filters to empty) and asserts both read ops
  carry a documented 200. `manage.py spectacular` exits 0.
- **AC3** — `SyncView` compound `(updated_at, id)` cursor: filters
  `Q(updated_at__gt=since) | Q(updated_at=since, id__gt=since_id)`, returns
  `next_since_id`. Fixes the bulk-import livelock (>MAX_TOPICS rows sharing one
  `updated_at`). `since_id` defaults to 0 → first sync keeps the old no-loss
  boundary; `next_since` unchanged → the two existing sync tests still pass.
  Verified no `/sync/` consumer exists in `web/` or `plant_community_mobile/`, so
  the `next_since_id` addition is a free contract change.

Verification: forum package API suite **50 passed**; host route-parity +
rate-limit **5 passed** (`test_host_api_routes_match_package` green — PR-1 changed
no routes). Gotcha hit + fixed: the PostToolUse Python formatter stripped the
`from django.db.models import Q` import while it was momentarily unused (added
before its first use) — re-added after the usage existed.

**Still open (do NOT close):** AC2 (web off machina) + AC4 final URL surface need
PR-2 (write path) and PR-3 (images). Todo archives only after PR-3.

### 2026-06-23 - PR-2b (web write client) landed — todo still OPEN

Branch `feat/forum-spec2-pr2b-web-write` off `main` (web-only; disjoint from the
backend PR-2a). Plan: `docs/superpowers/plans/2026-06-23-forum-spec2-pr2b-web-write.md`.
PR-2a (backend write path, PR #395) is its prerequisite for live integration but
the web suite mocks `fetch`, so PR-2b is fully verifiable without it.

**Done (TDD; commits = plan + reactions + service-writes + NewThread + wiring + this log):**

- **Service** (`forumService.ts`) migrated onto the PR-2a routes:
  `createThread` → `POST /boards/{slug}/topics/` (client slugifies the title;
  returns `{id, slug, status}`); `createPost` → `POST /topics/{id}/posts/`
  (`{id, status}`); `updatePost` → `PATCH /posts/{id}/` (full post +
  `moderation_status`); `deletePost` → `DELETE /posts/{id}/`; `toggleReaction`
  → `{type}` request / `{reaction_counts, reacted}` response. Bodies wrapped as a
  single `paragraph` StreamField block via `toBodyBlocks`. `fetchReactions`
  deleted (no GET on the toggle endpoint).
- **Compose UI**: new `NewThreadPage` + `/forum/new-thread` route (a published
  topic navigates into the thread; a *pending* one is `live=False` and would 404,
  so we notify + return to the board). `ThreadDetailPage` gained the reply
  composer (hidden when locked), inline edit, delete-with-confirm, and reaction
  toggles; the read-only notice is gone. `PostCard` now gates edit/delete on the
  backend `can_edit`/`can_delete` (the client-side author check was dead — the
  mapper sets `author.id=''`).

Verification: full web suite **559 passed** (37 files); `tsc --noEmit` clean;
ESLint 0 errors. Machina write-path sweep of `forumService.ts` is empty
(`topics/create/`, `posts/create/`, `posts/{id}/delete/`, `reaction_type` all
gone); the only legacy paths left are the **image** fns (PR-3).

**Deferred to PR-3 (do NOT close the todo):** inline image upload/render —
`POST /topics/{id}/images/`, `validate_forum_body` relax, the web
`StreamFieldRenderer` `image` case, and migrating the forum image client fns.
Also a UX nicety: the composer toolbar still offers heading/quote/strike/
code-block marks that the server's nh3 allowlist flattens to text (graceful, no
data loss) — trim later. Todo archives after PR-3.
