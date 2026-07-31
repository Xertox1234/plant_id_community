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
  Addresses L14's `trust_level`-renders-as-raw-text item (the emoji-`aria-hidden`
  and reactions-`flex-wrap` items in that cluster remain at todo 257); serves the
  serializer subset of H7 (public profiles stay Wave 4 / todo 257).
- [x] **Slice 2 — Solved answers** (H6, moved from todo 256): `Topic.solved_post`
  FK + `solved_at`, `POST/DELETE /topics/{id}/solution/`, Solved badge +
  accepted-post highlight, accepted-answer notification, clear-on-unpublish rule.
- [ ] **Slice 3 — Identification embed** (M6, moved from todo 263):
  `ForumIdentificationAttachment` snapshot model, compose-time photo copy through
  the forum image upload pipeline, card above the opening post, "Ask the
  community" web entry point.
- [x] **Slice 4 — Mobile-gating API hardening** (M35, M36, M37, M39 subset of
  todo 258): idempotency for `PATCH /posts/{id}/` + image upload (and the new
  solution endpoint), OpenAPI response-code completeness, error-envelope
  consistency across mobile-bound endpoints.
  **Shipped under todo 258 / PR #494 (2026-07-24), not as a separate 273 PR** —
  258 batched the whole contract-hardening set and landed this subset with it.
  Verified 2026-07-31: `docs/audits/2026-07-11-forum-modernization.md` Finding
  Status has all four as `- [x] … (completed 2026-07-24, PR #494)`, and
  `api/views.py` wires `idempotency_cache_key` on topic-create, reply-create,
  post-edit, image-upload, reaction-toggle and post-report. The parenthetical
  "and the new solution endpoint" could not be covered then — that endpoint did
  not exist yet — so it is carried into slice 2 below, which wires the same
  contract on `POST /topics/{id}/solution/`.

## Notes

Solved answers moved out of 256; the identification embed moved out of 263; the
mobile-gating subset split out of 258 — the remainder of each stays put. See the
roadmap's "Todo bookkeeping" section.

## Work Log

### 2026-07-31 - Picked up by completing-todos skill (run 2026-07-31-1455)

- The file had no Work Log section at all; created here.
- Audited what actually remained across the four slices:
  - Slice 1 — shipped (PR #474, commit 3f38157).
  - Slice 4 — shipped under todo 258 / PR #494; checked off above with evidence.
    No implementation work; bookkeeping only.
  - Slice 2 (H6 solved answers) and slice 3 (M6 identification embed) — no code
    anywhere. `grep -rn "solved_post\|solved_at\|is_solved"` and
    `grep -rn "ForumIdentificationAttachment"` over `backend/`, `web/src/` and
    `plant_community_mobile/lib/` return **zero** production hits; the newest
    forum migration is `0017_topic_tags`.
- API-contract check before designing slice 2: the Flutter client (Wave 3,
  todo 260, PR #498) shipped WITHOUT any solved fields — `grep -rn "solved"
  plant_community_mobile/lib/` → 0 matches. So no live client pins the field
  names and the contract is free to be designed here. Mobile rendering of
  `is_solved` therefore belongs to the mobile forum todos (291–295), not to
  this slice.
- Scope decision: slice 2 ships as its own PR off fresh `main` per the epic's
  delivery convention (spec line 172). **273 stays open for slice 3** — the
  identification embed is a separate model + upload-pipeline + compose-flow
  change and must not ride along on this branch.

### 2026-07-31 - Slice 2 implemented (solved answers, H6)

Branch `forum/wave2-slice2-solved-answers`.

**Backend (package).** `Topic.solved_post` (FK → Post, `SET_NULL`,
`editable=False`) + `solved_at`, migration `0018`. `Topic.solution_block` /
`can_mark_solution_by` single-source the policy (topic author **or**
`wagtail_forum.change_post`) the same way `Post.edit_block` does, so the API
guard and the serializer affordance cannot diverge. New
`api/solutions.py::TopicSolutionView` serves `POST/DELETE
/topics/{id}/solution/`, wired through the package's own idempotency contract
under scope `topic-solution` — closing the one gap slice 4 could not cover.
`NotificationVerb.SOLUTION` and a `solution_marked` host-facing signal added;
serializers expose `is_solved` + `solved_post_id` (list and detail) plus
`solved_at` + `can_mark_solution` (detail).

**Decisions worth recording.**

- **Clearing rule = explicit state clear, not a liveness check at serialize.**
  Keeps `is_solved` a plain column read, so no per-row join and the topic-list
  pins stay flat. Two paths, both pinned: the `unpublished` receiver (unpublish
  leaves the row alive, so `SET_NULL` never fires) and a `pre_delete` receiver
  (`SET_NULL` alone would null `solved_post` but strand `solved_at`).
- **Not gated on closed/locked**, unlike `Post.edit_block` — closing a solved
  question is the normal end of its life, so a moderator must still be able to
  mark which reply answered it. Accepting writes metadata, not content.
- **Opening post rejected (422)** — a Solved badge pointing at the question
  tells a reader nothing.
- **`save(update_fields=[...])`** so accepting writes no Topic revision and does
  not move `last_published_at`; pinned by
  `test_accepting_an_answer_writes_no_revision_and_does_not_republish`.
- **Web mark is NOT optimistic** (unlike the subscription toggle): solved state
  is shared and the server can legitimately refuse, so the badge moves only on
  confirmation.
- **Re-accepting the same post is silent** — `create_notifications` dedupes the
  bell on (recipient, verb, post) but FCM has no such backstop, so the view
  short-circuits the signal.

**Verification** (all run on this branch):

- `pytest apps/forum_host packages/wagtail_forum --create-db` → **674 passed**
  (23 new in `tests/api/test_solutions.py`, 6 new in
  `apps/forum_host/tests/test_solution_notifications.py`).
- `python manage.py check` → "System check identified no issues".
- `python manage.py spectacular --file /dev/null` (the CI gate command) →
  exit 0, no new warnings mentioning the endpoint.
- `npm run type-check` → clean; `npx vitest --run` → **774 passed**;
  `npm run lint` → 0 errors.

**Two query pins moved, both deliberate and re-commented in place:**

- `test_topic_detail_is_subscribed_for_authenticated_user` 6 → 8: an
  authenticated NON-author now pays the two permission-table reads behind
  `can_mark_solution`. Constant (Django caches the perm set per user instance),
  not per-row; the topic author and anonymous readers pay nothing because
  `solution_block` short-circuits first. The anonymous pin (5) is unchanged.
- `test_delete_query_count_is_pinned` 33 → 34: the `unpublished` receiver's
  clearing UPDATE, on the moderation path only, against the indexed FK column.

**Not in this slice, by design:** the Flutter client. Wave 3 shipped without any
solved fields (`grep -rn "solved" plant_community_mobile/lib/` → 0), so no live
client pins this contract; mobile rendering belongs to todos 291–295.

### 2026-07-31 - Out-of-diff consumer found by the FULL backend suite

Running only `apps/forum_host packages/wagtail_forum` was not enough. The full
`pytest --create-db` caught that `is_solved` reached `TopicListSerializer` but
NOT the two hand-built topic-hit dicts:

- `SearchView` builds its own topic dict (audit M40 territory). Its own comment
  notes the web SearchPage renders the shared `ThreadCard` — and the web mapper
  defaults a missing `is_solved` to `false`, so every search hit would have
  rendered unsolved rather than failing loudly.
- `apps/forum_host/semantic_search.py::_serialize` must match that dict
  key-for-key; `test_premium_semantic_hits_use_the_same_shape_as_fts_topic_hits`
  is what caught it, its hardcoded field-set pin earning its keep.

Both fixed, with tests on each path. `SyncView` deliberately unchanged — it is
a thin delta signal (id/slug/title/updated_at) and the clearing helper's
`updated_at` bump is what makes it notice. No topic queryset uses
`.only()`/`.defer()`, so `is_solved` cannot trigger a deferred-field fetch.

Final: backend **1403 passed, 0 failed, 8 skipped** (full suite); web **775
passed**; type-check and lint clean.

### 2026-07-31 - End-to-end verification in the running app

The spec's Wave 2 acceptance is "exercised end-to-end from the web UI", and
every layer had until now only been verified in isolation
(`ThreadDetailPage.test.tsx` mocks `forumService` wholesale, so no test had
sent a real request). Ran the real stack — Django on :8000, Vite on :5174,
against Postgres + Redis — and drove the real React client in Chrome:

- Thread page before marking: both posts render, **no** accepted-answer label.
- After setting the solved state, the same page renders "✓ Accepted answer" on
  the **reply**, with the highlight border — not on the opening post.
- Board topic list renders the "✓ Solved" badge.
- `/forum/search?q=monstera` renders the "✓ Solved" badge too — confirming the
  `SearchView` fix above through the real mapper and shared `ThreadCard`,
  which is the path a unit test could not have proven end-to-end.
- Clearing rule live: unpublishing the accepted post cleared `solved_post_id`
  AND `solved_at`, and the badge disappeared from the board list on reload.

**Stated plainly — what was NOT done in-browser:** the authenticated
click-through of "Mark as answer". Driving a login form means typing a password,
which I do not do. So the write seam (`Number(post.id)` out,
`solved_post_id` back, the `/api/v1/forum/` mount) is covered by the endpoint
tests through the host mount
(`test_solution_notifications.py::test_the_endpoint_is_reachable_through_the_host_mount`)
and the client-side unit tests, not by a real browser click. The READ seam is
fully verified in-app as above. If an in-app authed click-through is wanted
before merge, it needs a human to sign in — or a Playwright E2E case, which
this project keeps out of CI.

Seed fixtures (2 users, 1 board, 1 topic) were removed from the dev DB
afterwards; both dev servers stopped.
