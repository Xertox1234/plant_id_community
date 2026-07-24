---
status: pending
priority: p2
issue_id: "258"
tags: [forum, api, drf, openapi]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M28, M35, M36, M37, M38, M39, M40, L16, L18, L19, L20"
---

# Forum epic: API contract hardening

## Problem

The forum API's write-path idempotency has real gaps (a retried PATCH creates a
duplicate revision AND a duplicate push notification; a retried image upload
creates duplicate rows/files), the OpenAPI schema has holes, one API ships four
different list envelope shapes, and the web client suppresses a real type
mismatch with `as unknown as` casts. p2 epic from the 2026-07-11
forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `H` = `backend/apps/forum_host`, `web` = `web/src`.

- **M35** — PATCH `/posts/{id}/` lacks Idempotency-Key support unlike all
  sibling writes; a retried edit re-runs `submit_edit_for_moderation` →
  duplicate revision row + duplicate `moderation_decided` signal → traced to an
  unconditional duplicate FCM push (no dedup at any layer)
  (`W/api/views.py:444-475`, `W/workflow.py:174,211`, `H/notifications.py:51-65`).
- **M36** — POST `/forum/images/` lacks Idempotency-Key — the most retry-prone
  request shape (multipart; the docstring's own mobile use case) creates
  duplicate Image rows + stored files (`W/api/views.py:516-557`;
  `docs/rules/api.md:31-35` names the package's own `idempotency.py` as the
  reference contract).
- **M37** — OpenAPI response-code gaps: topic/reply create declare 201/409/422
  but not the provable 400; ReactionToggle omits 409/422 despite the same
  idempotency contract; list GETs document 404 in prose only; zero `examples=`
  anywhere (`W/api/views.py:140-146,167-177,302-308,345-353,564-571`).
- **M38** — `MeProfileView` has zero `@extend_schema` (no description, no 400
  for bio/fcm_token length failures) (`W/api/views.py:611-620`).
- **M39** — The consistent error envelope is HOST-owned
  (`apps/core/exceptions.py` via the project `EXCEPTION_HANDLER`) — the
  reusable package neither ships nor documents that dependency; another host
  gets bare DRF `{"detail"}` responses; the one envelope test accepts either
  shape so pins neither (`W/tests/api/test_topic_create.py:318`).
- **M40** — Four list envelope shapes in one API (cursor
  `{results,next,previous}` / flat `{results}` / search `{topics,posts}` / sync
  custom); search per-item fields are a poorer subset of the list serializers
  (drop reply_count/view_count/is_pinned/last_post_at). (The raw-HTML excerpt
  half was fixed in audit H24.)
- **M28** — `as unknown as ForumAuthor` ×4 suppresses a real structural
  mismatch (`id: ''` string vs required `User.id: number`); plus 6 dead
  exported legacy types (`web/services/forumMappers.ts:88-109`,
  `web/types/forum.ts:113-207`).
- **L16** — Reaction types hand-duplicated: web `REACTION_TYPES` literal
  mirrors backend `Reaction.REACTION_CHOICES` with no schema link.
- **L18** — PATCH costs 68 pinned SQL queries, DELETE 32 — likely inherent to
  Wagtail's revision/workflow/signal cascade, but a profiling pass is
  warranted on hosted Postgres (`W/tests/api/test_post_edit_delete.py`).
- **L19** — No `Location` header on any 201 (topic/reply/image create).
- **L20** — `versioning_class = None` rationale commented on 1 of 12 views.

## Recommended Action

1. **Idempotency parity first** (M35, M36): wire both endpoints through the
   package's existing `idempotency.py` contract; regression tests proving a
   replayed key is a no-op (no second revision, no second push, no second
   Image row).
2. **M39 envelope decision**: either ship a default exception handler in the
   package or document the host dependency in README + conf; pin exactly one
   shape in the envelope test (coordinate with todo 262's README work).
3. **M40 envelope normalization**: converge on the cursor envelope where
   feasible; enrich search items to the list-serializer field set. Breaking —
   coordinate web mappers + document.
4. **OpenAPI pass** (M37, M38, L19, L20): complete response codes, add
   `examples=`, `Location` on 201s, comment the versioning rationale once at a
   shared base.
5. **Web types cleanup** (M28, L16): fix the author `id` mismatch at its
   source (coordinates with todo 257 H26 — do the shape unification there
   first if both are open), delete dead types, single-source reaction types
   (codegen from the OpenAPI schema or a shared literal derived from it).
6. **L18 profiling**: capture a query breakdown for PATCH/DELETE, decide if
   any cascade step is elidable; record results either way.

## Technical Details

- `W/api/idempotency.py` is the reference implementation; throttle
  drift-guard tests will catch new unthrottled surfaces automatically.
- Query-pin tests carry an "explain the new number" contract — any idempotency
  read adds queries; update pins with comments.
- Envelope changes are versioning-relevant: `versioning_class = None`
  currently — decide whether normalization warrants a documented break
  (pre-deploy window makes this cheap now).

## Acceptance Criteria

- [x] Retried PATCH with the same Idempotency-Key: one revision, one signal,
      one push (end-to-end test) — PR1
- [x] Retried image upload with the same key: one Image row, one stored file — PR1
- [x] One documented error-envelope contract, pinned by a test asserting a
      single shape — PR1
- [x] `manage.py spectacular` clean with complete response codes on the named
      endpoints; 201s carry `Location` — PR1
- [ ] No `as unknown as` casts in forum mappers; no dead exported forum types;
      reaction types single-sourced — PR2 (web)
- [x] L18 profiling results recorded in this todo's work log — PR1

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 11 open findings per the manifest's Phase 4 grouping table.

### 2026-07-24 - Started by completing-todos skill (run 2026-07-24-1946)

- Picked up by automated workflow. Three-agent exploration re-scoped the epic:
  - **M28** already resolved by todo 257 slice A (PR #490) — casts gone, author
    contract unified on `username`. Reduced to verify-no-casts + dead-types delete.
  - **M40** mostly stale — search topics already carry reply_count/view_count/
    last_post_at (PR #473); only `is_pinned` + the post search item still diverge.
    Not an acceptance criterion.
  - **L20** is 17 views (not 12); not an acceptance criterion.
- User decisions: M39 → ship a package reference exception handler + document;
  defer M40 + L20 to follow-up todo 277; L16 → shared literal + drift-check
  (not codegen); deliver as two PRs (backend first, then web).
- Delivery: PR1 = backend (M35/M36/M37/M38/M39/L18/L19); PR2 = web (M28/L16) +
  archival. Branch `fix/forum-258-api-contract-backend`.

### 2026-07-24 - PR1 backend implemented + verified

Changes (`W` = `backend/packages/wagtail_forum/wagtail_forum`, `H` = `backend/apps/forum_host`):

- **M35** — `PostWriteView.patch` now wires the idempotency contract (scope
  `post-edit`): `reserve()` before `submit_edit_for_moderation`, `remember()` on
  the 200. A replay short-circuits before the edit, so no second revision / signal
  / push (`W/api/views.py`).
- **M36** — `PostImageUploadView.post` idempotency (scope `image-upload`),
  fingerprinting a **content hash** (multipart: `request.data` is the file, not
  JSON) with `seek(0)` before hashing and before `.create()`.
- **M37** — provable response codes added to the named endpoints: topic/reply
  create gain **400/401**; ReactionToggle **and** the parallel PostReport gain
  **409/422/401**; list GETs move their prose 404 into `responses`. Representative
  `examples=` added to topic-create (request + 422 envelope).
- **M38** — `MeProfileView` gains `@extend_schema_view` (GET + PATCH: description,
  200, **400**, 401).
- **M39** — new `W/api/exception_handler.py` ships a reference
  `forum_exception_handler` producing the same envelope as the host
  (`{error,message,code,status_code,errors?}`); documented in `W/README.md`
  ("Error envelope" + "Idempotency") and `W/api/exceptions.py`. The either-shape
  envelope test is re-pinned to ONE shape.
- **L19** — 201s carry a `Location` header. Reverse is **namespace-agnostic**
  (`_created_location` resolves within the current request's namespace) — a
  hardcoded `wagtail_forum_api:` prefix 500s under the host's root-mounted
  urlconf (caught by the throttle suite; fixed).
- **L18 profiling (recorded)** — real measured query counts via
  `CaptureQueriesContext` (pin tests PASS): **PATCH = 71 queries, DELETE = 33**.
  The idempotency wiring adds **0 SQL** (cache get/add/set are LocMemCache, and
  are no-ops entirely when no `Idempotency-Key` header is sent — so the pins are
  unchanged). The bulk is inherent Wagtail machinery: `save_revision` → workflow
  finish → publish → the denormalized counter-recount signal cascade
  (reply_count/last_post_at/board/profile), plus the unified author-profile SELECT
  (257 H26) and one reacted lookup (257 M23). **Judgment: not elidable** without
  bypassing the workflow/publish path, which would forfeit moderation correctness,
  audit-log attribution, and counter accuracy. No cheap win; counts are stable and
  pinned with per-delta comments in `test_post_edit_delete.py`.

Tests added/updated: `test_post_edit_delete.py` (PATCH idempotency ×3 + fixture),
`test_post_image_upload.py` (image idempotency ×2 + Location + fixture),
`test_error_envelope.py` (new — package handler unit tests), `test_schema.py`
(exact response-code assertions on named operations), `test_topic_create.py`
(single-shape envelope + Location), `H/tests/test_idempotency_push.py` (new —
M35 end-to-end: one revision + one push through the real host URL).

Verification (all `--create-db`):

- `pytest apps/forum_host packages/wagtail_forum` → **506 passed**.
- `test_edit_query_count_is_pinned` (71) + `test_delete_query_count_is_pinned`
  (33) → PASSED.
- `manage.py spectacular --file /dev/null` → exit 0; generated schema shows the
  new codes on every named operation (`test_write_endpoints_declare_provable_error_codes`).

**Deferred (NOT acceptance criteria; re-pointed in the audit, not checked off):**
M40 (envelope-shape normalization — breaking, needs web coordination; already
partly stale) and L20 (versioning comment across 17 views) → follow-up todo 277.

### 2026-07-24 - PR1 code review + repair

Reviewed via `code-review-orchestrator` → django-drf-reviewer + wagtail-reviewer +
cross-cutting-reviewer (all three, staged diff). Findings (0 critical/high):

- **[MEDIUM ×2, confirmed] Idempotent replay dropped the `Location` header** —
  a same-key retry of a create returned 201 without `Location`. **Repaired**:
  `remember()` now stores optional `headers`, and `_replay_or_none` re-applies
  them, so replays are response-faithful. New replay-Location assertions in
  `test_topic_create.py`, `test_replies_reactions.py`, `test_post_image_upload.py`.
- **[MEDIUM/LOW/INFO] Location coverage gaps** — no reply-create assertion; no
  exact-value test under the real *namespaced* host mount. **Repaired**: added
  reply-create Location assertion + a host test
  (`test_topic_create_location_header_under_namespaced_host_mount`) pinning
  `http://testserver/api/v1/forum/topics/{id}/` and replay fidelity under the
  nested `v1:wagtail_forum_api` namespace.
- **[LOW] exception_handler Http404/PermissionDenied branches unreachable** —
  DRF converts those upstream, so a 404 gets `code:"error"`. **Not changed by
  design**: this is byte-identical to the host handler; "fixing" it in the
  package alone would diverge the envelope from the host and break M39's
  interchangeability. Clarifying comment added.

Re-verified: `pytest apps/forum_host packages/wagtail_forum` → **507 passed**;
flake8 clean; `spectacular` exit 0.

## Notes

p2. M35's duplicate-push trace makes it the sharpest item here — a mobile
client on flaky networks (todo 260) will hit it in practice, so land M35/M36
before the mobile write path ships.
