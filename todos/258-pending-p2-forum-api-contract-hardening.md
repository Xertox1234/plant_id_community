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

- [ ] Retried PATCH with the same Idempotency-Key: one revision, one signal,
      one push (end-to-end test)
- [ ] Retried image upload with the same key: one Image row, one stored file
- [ ] One documented error-envelope contract, pinned by a test asserting a
      single shape
- [ ] `manage.py spectacular` clean with complete response codes on the named
      endpoints; 201s carry `Location`
- [ ] No `as unknown as` casts in forum mappers; no dead exported forum types;
      reaction types single-sourced
- [ ] L18 profiling results recorded in this todo's work log

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 11 open findings per the manifest's Phase 4 grouping table.

## Notes

p2. M35's duplicate-push trace makes it the sharpest item here — a mobile
client on flaky networks (todo 260) will hit it in practice, so land M35/M36
before the mobile write path ships.
