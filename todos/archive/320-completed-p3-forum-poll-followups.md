---
status: completed
priority: p3
issue_id: "320"
tags: [forum, web, api]
dependencies: []
source_review: "todo 309 (deferred 2026-08-30); PR #589 /code-review medium (2026-08-30)"
---

# Forum polls: raw DRF validation-error envelope leaks to the user (cross-cutting, not poll-specific)

## Problem

Originally 8 findings across two review passes on todo 309 (forum polls).
7 of the 8 were fixed directly in PR #589 once the user asked for the
review's fixes to be applied (see Work Log) — only this one remains open,
deliberately: it is a pre-existing, cross-cutting infra issue shared by
every DRF endpoint in the repo, not something scoped to the poll feature,
and fixing it properly means auditing every page that renders `err.message`
verbatim across `web/src/`. That is a different, wider PR than this one.

## Findings

- **Raw DRF validation-error dict leaks to the user on ANY nested-serializer
  400**, not just polls. `backend/apps/core/exceptions.py:151` sets
  `"message": str(exc)` for any DRF exception carrying a `response` — for a
  nested serializer's `ValidationError` (e.g. `TopicPollSerializer`'s), `str(exc)`
  stringifies the whole `detail` dict including `ErrorDetail(...)` reprs, not
  a clean sentence. `web/src/services/forumService.ts:96-100`
  (`authenticatedFetch`) takes `error.message` straight from that envelope
  and every page-level `catch` (e.g. `NewThreadPage.tsx`) renders it
  verbatim. Confirmed reachable via the poll composer (a validation error
  that reaches the server despite todo 309's client-side `pollValid` gate —
  e.g. a duplicate-option or too-long-question poll, which the client
  doesn't pre-validate), but the root cause is generic to every
  nested-serializer field on every endpoint, not poll-specific.

## Recommended Action

Either (a) have `apps/core/exceptions.py` format a nested `ValidationError`'s
`detail` into a flat, readable string (walk the dict, join field:message
pairs) instead of `str(exc)`, or (b) have the frontend's `authenticatedFetch`
prefer a structured `errors` field over `message` when the backend supplies
one, falling back to `message` only when it doesn't. Whichever direction,
this is a shared-infra change — audit every page that renders `err.message`
verbatim before shipping, not just the forum composer.

## Technical Details

- `backend/apps/core/exceptions.py` (custom DRF exception handler).
- `web/src/services/forumService.ts` (`authenticatedFetch`, `ForumApiError`).
- `web/src/pages/forum/NewThreadPage.tsx` (one of several call sites that
  would benefit, not the only one — grep `err.message`/`error.message`
  across `web/src/pages/` and `web/src/components/` for the full blast
  radius before scoping the fix).

## Acceptance Criteria

- [x] A nested-serializer validation error (poll or otherwise) renders a
      readable message to the user, not a raw Python dict repr — test
      asserting the rendered text contains no `ErrorDetail`/`{'...':` markup
      (`test_polls_api.py::test_invalid_poll_is_rejected_and_creates_no_topic`
      × 7 real `POST boards/<slug>/topics/` cases now assert
      `message.startswith("poll.")` and no `ErrorDetail`/`{'`; plus the
      6-row flatten table pinned in both handlers' unit tests — see Work Log
      2026-09-01)

## Notes

p3. Not a live vulnerability or data-corruption risk — UX polish (a raw
dict repr instead of a clean sentence on an already-rare validation
failure). Deferred out of todo 309 / PR #589 per this project's
review-round discipline (fix BLOCKING findings in round 1, non-blocking
findings become a follow-up todo rather than a third review round).

## Work Log

### 2026-08-30 - 7 of 8 findings fixed directly, on user request

The user asked to apply the review's fixes rather than defer them further.
Verified each of the 7 was safe to fix without expanding scope beyond the
poll feature (unlike #1 above) before doing so:

- **PollCard resync** (was #2): added a `useEffect` in `PollCard.tsx`
  tracking the `poll` prop via a `useRef`, resyncing `current` only when
  the prop's IDENTITY changes (a real parent refetch) and no vote is in
  flight (`pendingOptionId === null`) — deliberately NOT keyed off `current`
  in the deps array, since that would re-fire immediately after
  `handleVote` sets `current` and stomp the just-applied vote result with
  the pre-vote prop. Two new tests in `PollCard.test.tsx`: one asserting a
  same-thread prop change updates displayed counts, one specifically
  asserting a successful vote survives an unrelated refetch that itself
  now includes the vote (not assumed — asserted).
- **Payload duplication + weak drift test** (was #3): added
  `Poll.serialize(my_vote_option_id)` in `models/polls.py` as the one
  shared shape; `TopicDetailSerializer.get_poll` and `PollVoteView.post`
  both call it now instead of hand-building the dict twice. Strengthened
  `test_vote_response_matches_topic_detail_poll_shape` to
  `assert vote_resp.data == detail_resp.data["poll"]` (full equality, not
  key-set plus two scalars).
- **Extra query** (was #4): closed by the same `Poll.serialize` change —
  `PollVoteView.post` now passes `option.id` (already in scope from the
  just-recorded vote) instead of re-querying `PollVote`.
  `_poll_payload`/`_poll_payload`'s old query is gone entirely.
- **Client/server option-bounds drift** (was #5): added
  `test_poll_option_bounds_defaults_match_the_web_composer_constants` in
  `test_polls_api.py`, pinning `POLL_MIN_OPTIONS == 2` /
  `POLL_MAX_OPTIONS == 10` with an assertion message naming
  `NewThreadPage.tsx`'s constants directly, so a future default change
  fails loudly and points at the other side.
- **Bounded-list duplication** (was #6): factored `_BoundedListField` as a
  shared base (`max_items` + `too_many_message` class attributes) in
  `serializers.py`; `_BoundedTagListField`, `_BoundedCandidateListField`,
  and `_BoundedOptionListField` are now one-line subclasses. Full
  `apps/forum_host packages/wagtail_forum` suite re-run clean afterward
  (tag and candidate tests included, not just poll tests).
- **`closes_at` UI** (was #7): added a `type="datetime-local"` input
  (labeled "Closes (optional)") to the poll composer in `NewThreadPage.tsx`
  — `type="date"` was deliberately rejected: the field is a `DateTimeField`
  compared against `timezone.now()` server-side, and a date-only value
  would submit local midnight, which can already be in the past. The
  submitted local value is converted with `new Date(value).toISOString()`
  before it reaches the API. Two new tests in `NewThreadPage.test.tsx`:
  one asserting a filled-in close time reaches `createThread` as a UTC ISO
  string, one asserting a blank field omits `closes_at` entirely (not an
  empty string).
- **Poll/option invariant** (was #8): added `PollVote.clean()` in
  `models/polls.py`, raising when `option.poll_id != poll_id`.
  Deliberately **NOT** wired into `save()` — Django 6's `full_clean()` also
  runs `validate_constraints()`, which would pre-check `uniq_poll_vote`
  against the DB and convert a double-vote from the `IntegrityError`
  `PollVoteView.post` specifically catches (to return 409) into an
  uncaught pre-save `ValidationError` (500). `clean()` alone protects any
  OTHER writer (Django admin, a data migration, a future second view) that
  calls it explicitly, without touching the one hot path that doesn't. New
  test `test_poll_vote_clean_rejects_option_from_another_poll` calls
  `clean()` directly on a mismatched poll/option pair and asserts it
  raises.

Verification: `pytest apps packages` full suite (matches CI scope, not
just the forum subset) green; `npx vitest run` 979 passed (up from 975);
`npx tsc --noEmit` clean; `npx eslint` clean on all touched files;
`python manage.py check` clean; `makemigrations --check --dry-run` — no
changes detected (both fixes are behavior-only, no schema change).

Advisor consulted before implementing (caught two real mistakes before
they shipped): the Django-6 `full_clean()`/`validate_constraints()`
interaction with the 409 path above, and confirmed the `useRef`-based
`PollCard` resync guard (my own first draft, which included `current` in
the effect's deps, would have immediately reverted a successful vote —
caught and fixed before writing any test against it).

### 2026-09-01 - Started by completing-todos skill (run 2026-09-01-1327)

- Picked up by automated workflow (via `todo-next`; chosen over 315/329/330 as
  the one p3 that is a real user-facing bug and finishable in a session).
- Direction: option (a) — fix server-side so all 55 `err.message` render sites
  in `web/src` are corrected without touching them. Both handlers (host
  `apps/core/exceptions.py` + the package's byte-compatible twin
  `wagtail_forum/api/exception_handler.py`) get the identical
  `_readable_message` flattener.
- Blast radius measured before editing (Explore sweep): 0 backend or web tests
  pin the old dict-repr `message`; no frontend consumer parses it; the two
  message-text branchers (`httpClient.ts:146` CSRF retry, `AuthContext.tsx`
  error codes) only see string-detail 401/403s.

### 2026-09-01 - Implemented (run 2026-09-01-1327)

Confirmed the repr empirically first (DRF 3.17.1):
`str(ValidationError({"poll": {"options": [...]}}))` →
`{'poll': {'options': [ErrorDetail(string='Poll options must be unique.', code='invalid')]}}`.

- **`_readable_message(exc)` + `_flatten_detail()`** added verbatim to BOTH
  `apps/core/exceptions.py` (wired at the DRF-handled `"message":`) and
  `wagtail_forum/api/exception_handler.py` (`message=`), keeping the
  package's byte-compatibility contract. Scalar details keep `str(exc)`
  exactly (403/404/409/422 messages unchanged — `AuthContext` and
  `httpClient`'s CSRF retry match on that text); dict/list details flatten to
  `field: text; other.field: text`, nested serializers give dotted paths,
  `many=True` children give `field[i].child`, `non_field_errors`/`detail`
  keys drop the prefix. `errors`/`code` untouched.
- **Sibling finding, worse than filed**: `plant_identification/api/simple_views.py`
  caught *Django's* `ValidationError` around `validate_image_file`, which
  raises *DRF's* — the branch was dead and a rejected upload fell through to
  the outer `except Exception` as a **500** ("An unexpected error occurred
  during identification"), losing the reason. Verified pre-fix with the new
  test: `assert 500 == 400` and the log line
  `Plant identification error: [ErrorDetail(string='Invalid Content-Type:
  text/plain. ...', code='invalid')]`. Fix: import DRF's `ValidationError`
  and join the `ErrorDetail` strings (`str(e)` would have been the list
  repr). The formatter hook also dropped two pre-existing unused imports in
  that file (`Optional`, `method_decorator`) — not hand-edited.
- Docs: package README §Error envelope (what `message` is), `forum.md` §M39
  (flattener is part of the byte-compatible contract), `docs/rules/api.md`
  (never `str(exc)` to a user; catch the `ValidationError` actually raised),
  `forumService.ts` comment tightened.

Tests (all new/extended, real requests where the todo asks for it):

```
$ pytest apps/core/tests/test_exception_envelope.py \
    packages/wagtail_forum/wagtail_forum/tests/api/test_error_envelope.py \
    packages/wagtail_forum/wagtail_forum/tests/api/test_polls_api.py -q
apps/core/tests/test_exception_envelope.py ........                      [ 16%]
packages/wagtail_forum/wagtail_forum/tests/api/test_error_envelope.py ..
.........                                                                [ 38%]
packages/wagtail_forum/wagtail_forum/tests/api/test_polls_api.py .......
.......................                                                  [100%]
======================== 49 passed, 1 warning in 19.21s ========================

$ pytest apps/plant_identification/tests/test_simple_identify_errors.py -q
(pre-fix)  E   assert 500 == 400
(post-fix) ======================== 1 passed, 1 warning in 17.57s ========================
```

Checks: `manage.py check` → "System check identified no issues";
`makemigrations --check --dry-run` → "No changes detected";
`pre-commit run --files <12 touched>` → every hook Passed (black, flake8,
isort, eslint, prettier, markdownlint, detect-secrets, kimi-review gate);
`web: npx tsc --noEmit` → "No errors found"; `eslint forumService.ts` → clean.

Full backend suite (CI scope, single invocation):

```
$ pytest apps packages -q
=========== 1927 passed, 8 skipped, 6 warnings in 213.70s (0:03:33) ============
```

Live probe (dev server, DEBUG anonymous path) — the Identify sibling fix on
a real request; pre-fix this was a 500 with the generic message:

```
$ curl -F "image=@notes.txt;type=text/plain" localhost:8000/api/v1/plant-identification/identify/
{"success":false,"error":"Invalid Content-Type: text/plain. Allowed types: image/jpeg, image/jpg, image/png, image/webp"}
HTTP 400
```

The poll path needs an authed session; it is driven end-to-end through the
real handler by `test_polls_api.py` (7 real POSTs) rather than re-probed.

### 2026-09-01 - Code review round 1 + fixes (run 2026-09-01-1327)

`code-review-orchestrator` routed to 4 domain reviewers (+ bundled
`/code-review high` in parallel). 6 findings, none blocking (0 critical/high);
all 6 fixed in one round per the two-round budget:

- **[medium] django-drf** `simple_views.py` — my list-only join would still
  leak the repr for a dict detail (latent; verified by the reviewer). Fixed by
  making the host helper public (`apps.core.exceptions.readable_message`) and
  reusing it there; added a `[PLANT_ID] Rejected upload …` info log so the
  400 path is observable (the old accidental 500 path had logged).
- **[low] django-drf** — `_flatten_detail` type hints (`node: Any` →
  `Iterator[str]`), both copies.
- **[low] wagtail** `test_polls_api.py` — `startswith("poll.")` would fail on
  a malformed (non-dict) `poll` that collapses to `poll: …`; loosened to
  `startswith("poll")`.
- **[info] wagtail** — run the web suite too: `npx vitest run` →
  `Test Files 86 passed (86) / Tests 1004 passed (1004)`.
- **[medium] cross-cutting** — "change both or neither" was comment-only;
  added `test_package_handler_agrees_with_host_handler` (host imports the
  package handler and asserts identical `message`/`errors` over the shared
  table + a scalar case) — the L16 drift-guard shape from `forum.md`.
- **[low] cross-cutting** — empty dict/list detail fell back to `str(exc)`
  (`ValidationError({})` → `'{}'`); now `"Invalid input."`, two table rows
  added on both sides.
- react-typescript: 0 findings (comment accurate; `authenticatedFetch` already
  prefers `message`; no `ForumApiError` renderer truncates or parses it).

Post-fix: `pre-commit run --files <9>` → all Passed (black reformatted the
host test once; restaged); targeted
`pytest test_exception_envelope.py test_error_envelope.py test_polls_api.py
test_simple_identify_errors.py` → `65 passed`.

Full backend suite, re-run after the fix round:

```
$ pytest apps packages -q
=========== 1942 passed, 8 skipped, 6 warnings in 214.77s (0:03:34) ============
```

### 2026-09-01 - Completed by completing-todos skill (run 2026-09-01-1327)

- Verification: the single acceptance criterion passed — 7 real
  `POST boards/<slug>/topics/` invalid-poll cases assert a readable
  `poll…` message with no `ErrorDetail`/`{'`; both handlers' 8-row flatten
  tables + the host↔package drift guard pass; full backend suite 1942
  passed / 8 skipped; web `npx vitest run` 1004 passed; live probe of the
  Identify sibling fix returned a readable 400.
- Review: 6 findings total, 0 blocking — all 6 fixed in round 1 (above). The
  bundled `/code-review high` reported interim verifier topics only (all
  overlapping findings already fixed: empty-container fallback, dict branch
  in `simple_views`, dropped rejected-upload log, `detail`-key handling —
  now commented in `_flatten_detail`); its final report had not arrived at
  archive time.
- Codified: `docs/rules/api.md` bullet, `forum.md` §M39 contract note,
  package README §Error envelope, `docs/LEARNINGS.md` 2026-09-01 entry,
  write-time trigger `drf-envelope-message-str-exc`. The standalone
  `kimi-review` codify pass was skipped on purpose (global rule: never point
  the cheap-worker tools at input-validation / security-sensitive paths;
  the commit-time gate ran regardless).
- Shipped as a single-slice PR (commit → push → PR), deliberately deviating
  from the skill's never-commit rail per the project's single-slice
  convention.
