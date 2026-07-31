---
status: completed
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
- [x] **Slice 3 — Identification embed** (M6, moved from todo 263):
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

### 2026-07-31 - Slice 3 implemented (identification embed, M6)

Branch `forum/wave2-slice3-identification-embed`.

**The spec's premise did not hold, and that reshaped the slice.** The roadmap
says the attachment is "created at compose time from an
`identification_result_id`". There is no such id:

- `POST /api/v1/plant-identification/identify/` is **stateless** — it calls the
  combined service and returns the AI result. It writes no rows.
- `PlantIdentificationResult` has readers everywhere (serializers, auditlog, a
  management command, a read-only ViewSet) and **zero writers**:
  `grep -rnE "PlantIdentificationResult(\(|\.objects\.(create|bulk_create|get_or_create|update_or_create))" apps/ packages/`
  → one hit, the class definition.
- The one apparent writer, `apps/users/services.py:611`, is dead: it imports
  `IdentificationResult` (no such class) and passes `image_1_url`,
  `location_data`, `is_demo_data` — none of which exist on the model.

So the snapshot is **caller-supplied**, and the design says so out loud rather
than implying a verified determination. This also stays true to the spec's own
*rationale* (a snapshot precisely so public forum content never depends on
private history) — only its mechanism changed.

**Backend (package).** New `models/identifications.py`:
`ForumIdentificationAttachment` — `OneToOne(Topic, CASCADE)`, `image`
FK `SET_NULL`, `provider`, `candidates` JSON, `created_at`, plus
`identification_result_id` as a plain non-FK field per the spec's advisor
amendment (documented as having no producer yet). Migration `0019`.
`TopicCreateSerializer` gains an optional nested `identification`;
`TopicDetailSerializer` gains a read-only `identification` object.

**Decisions worth recording.**

- **Detail-only, deliberately.** The card renders above the opening post and
  nowhere else, so `SearchView` and `apps/forum_host/semantic_search._serialize`
  — the other two topic-hit builders that bit slice 2 — are untouched. Pinned by
  `test_the_identification_is_absent_from_the_topic_list_payload`.
- **The write bounds ARE the defence**, since nothing is server-verified:
  ≤3 candidates (host-overridable, read at request time like the tag bounds), a
  raw-list ceiling checked *before* child validation, name length + inner
  whitespace collapse, provider length, and confidence in [0, 1].
- **NaN confidence is rejected explicitly.** Every comparison with NaN is False,
  so `FloatField(min_value=0, max_value=1)` passes it; stored in a JSONField it
  re-serializes as the literal `NaN`, which is not valid JSON. DRF's
  `STRICT_JSON` parser already blocks the literal over HTTP (verified: it is
  `True` in this host), so this is defence in depth for a host that flips it and
  for non-HTTP callers — the test asserts at the serializer for that reason.
- **`image_id` reuses the existing IDOR rule** verbatim from
  `MeProfileSerializer.validate_avatar_id`: the photo must be an image THIS user
  uploaded into the forum collection. No new upload code — "copied into the forum
  image collection through the existing pipeline" is satisfied literally, by
  calling `POST /forum/images/`.
- **The photo is uploaded on the identify page, before navigating.** Only JSON
  crosses into router state, so an upload failure surfaces where the user
  pressed the button rather than at composer submit, and a reload degrades to a
  plain composer instead of a half-broken card. That forced the auth gate:
  `/identify` allows anonymous under DEBUG but `POST /forum/images/` does not,
  so the button routes a signed-out user to login (same pattern as
  `handleSavePlant`).
- **The attachment is created inside the topic-create transaction** — a topic
  whose attachment failed to write would render as an ordinary question,
  silently losing the thing it was asked about. Pinned by patching the create to
  raise and asserting no topic survives.
- **The card never claims the plant IS the top candidate.** It heads "What the
  app suggested", lists every candidate with its confidence, says plainly it is
  not a confirmed identification, and — once solved — links to the accepted
  answer so the machine guess is not the last thing a reader sees.
- **The composer shows the attachment with a Remove control.** It carries the
  user's photo; attaching it silently would be the wrong default.
- **The handoff is NOT persisted into the sessionStorage draft.** The draft
  outlives the uploaded image's relevance, and a stale `image_id` would fail the
  server's ownership check at submit. A saved draft title also always beats the
  suggested one.
- **Idempotency needed no change** — the topic-create fingerprint is already
  `fingerprint({"slug": slug, "body": request.data})`, which covers the nested
  key automatically.

**Verification** (all on this branch):

- `pytest --create-db` (FULL suite, per the slice-2 lesson) → **1431 passed,
  0 failed, 8 skipped** (1403 baseline + 28 new in
  `tests/api/test_identification_attachment.py`).
- `python manage.py check` → "System check identified no issues".
- `python manage.py spectacular --file /dev/null` → exit 0, no new warnings
  naming the new serializers.
- `npx vitest --run` → **799 passed** (775 baseline + 24 new: 8 card, 6
  composer, 3 identify page, 3 thread detail, 2 mappers, 2 service).
- `npx tsc --noEmit` → "No errors found"; `npm run lint` → 0 errors.

**Query cost.** Topic detail with an attachment pins at **6** queries
(`test_topic_detail_query_count_with_an_identification_is_pinned`): the
attachment row and its image ride the detail `select_related`, so the only extra
over a plain topic is one rendition lookup, independent of candidate count. No
existing pin moved — the no-attachment path is unchanged.

**The package README** gained an "Identification attachment" section (the
`test_readme_documents_every_setting` gate caught the three new settings, as
designed).

**Not in this slice, by design:** the Flutter client. Mobile rendering of the
card belongs to the mobile forum todos (291–295); Wave 3's slice 3 covers the
mobile "Ask the community" flow.

**Stated plainly — what was NOT done in-browser:** the authenticated
click-through. "Ask the community" needs a signed-in user, and driving a login
form means typing a password, which I do not do. The read path (card rendering,
no-photo fallback, solved link, absence when there is no snapshot) is covered by
component + page tests; the write path (upload → router state → create →
persisted row → detail payload) is covered end-to-end by the backend endpoint
tests plus the client unit tests, but not by a real browser session. Same gap,
and same reason, as slice 2.

### 2026-07-31 - Completed (epic closed)

- All four slices shipped: slice 1 (#474), slice 2 (#522), slice 3 (this PR),
  slice 4 under todo 258 / #494.
- Verification: full backend suite 1431 passed / 0 failed / 8 skipped; web 796
  passed; `tsc --noEmit` clean; ESLint 0 errors; `spectacular` exit 0.
- Source review `docs/audits/2026-07-11-forum-modernization.md`: #H6 and #M6
  both checked off. The all-findings-resolved rename to `…-COMPLETED.md`
  deliberately did **not** fire — #M2, #M7, #M8, #M9, #M10 and #M13 remain open
  against todos 281/283/284/289.
