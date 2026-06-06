---
status: completed
priority: p2
issue_id: "208"
tags: [celery, plant-identification, backend, audit]
dependencies: []
source_review: "docs/audits/2026-06-02-full.md"
source_finding: "H1, M12"
---

# Make plant-ID autoretry actually work (service must re-raise; task uses on_failure)

## Problem

`run_identification`'s `autoretry_for` / `retry_backoff` / `max_retries=5` config
is **completely inert**: the service it calls swallows every exception, so no
exception ever escapes to the task and Celery never retries. Two coupled defects:

1. **Service swallows exceptions** — `identify_plant_from_request`
   (`apps/plant_identification/services/identification_service.py:226-235`)
   catches `except Exception`, sets `request.status = "failed"`, saves, and
   **returns without re-raising**. The retryable exceptions (`ExternalAPIError`,
   `APIUnavailable`, `requests.exceptions.RequestException`, `RateLimitExceeded`)
   never reach the task body, so `autoretry_for` and the body's
   `except RateLimitExceeded` never fire.
2. **Task body writes terminal status mid-flight** — `apps/plant_identification/
   tasks.py:102-111`: the `except Exception` sets `status="failed"` then
   re-raises. *If* the service ever did re-raise, this would trip the
   `status != "pending"` idempotency guard (line 48) on the retried run, turning
   every autoretry into a no-op (the originally-reported H1). M12: the
   `RateLimitExceeded` exhaustion path raises `MaxRetriesExceededError` from a
   sibling `except`, leaving the request stuck `pending`.

The audit's initial task-only fix (move the terminal write to `on_failure`) was
**reverted** because it is inert while the service swallows — and a unit test for
it asserted a `pending` state that cannot occur in production (the service writes
`processing` first). The two defects must be fixed **together**.

## Findings

- Service swallow: `identification_service.py:76` (`status="processing"`), `:226-235`
  (catch-all → `failed` → return, no re-raise).
- Task: `tasks.py:48` (guard), `:88-101` (RateLimit retry), `:102-111` (terminal
  write + re-raise).
- Status choices: `pending, processing, identified, needs_help, failed`
  (`models.py:379-388`). Terminal-success = `identified`/`needs_help`.

Source: audit 2026-06-02 (H1/M12 verified at code level; Phase-6 code review
found the service-swallow root cause; Celery docs via Context7 confirm the
`on_failure` pattern).

## Recommended Action

1. **Service:** in `identify_plant_from_request`, classify exceptions — re-raise
   the retryable ones (`ExternalAPIError`, `APIUnavailable`, `RequestException`,
   `RateLimitExceeded`) instead of swallowing; only swallow + mark `failed` for
   genuinely permanent errors. Preserve the websocket `emit("error")` / progress
   callbacks.
2. **Task:** remove the body's `status="failed"` write; add an
   `IdentificationTask(Task)` base with `on_failure(...)` that marks the request
   `failed` **unless** it already reached a terminal-success status
   (`identified`/`needs_help`) — i.e. `exclude(status__in=["identified",
   "needs_help", "failed"]).update(status="failed")`. This also resolves the
   `processing`-stuck edge and M12's `MaxRetriesExceededError` exhaustion.
3. **Tests (must actually exercise the path):** a test where the *real* service
   raises `ExternalAPIError` (mock only the external API client, not the whole
   service) and assert the task retries / ends `failed` after exhaustion; a test
   that `on_failure` does not clobber a `identified` request.

## Acceptance Criteria

- [x] A transient `ExternalAPIError` from the external API triggers a Celery
      retry (assert via `self.request.retries` or a retry spy), not an immediate
      permanent `failed`.
- [x] After `max_retries`, the request ends `failed` (not stuck `pending`/`processing`).
- [x] `on_failure` never overwrites `identified`/`needs_help`.
- [x] Tests mock the external API client, not the whole `PlantIdentificationService`.

## Notes

p2: the feature works for the happy path; the gap is resilience under transient
external-API failures. The earlier task-only fix was reverted (commit history on
branch `chore/full-audit-2026-06-02`) precisely because it was inert without the
service change — do them together.

## Work Log

### 2026-06-03 - Started by completing-todos skill (run 2026-06-03-1835)

- Picked up by automated workflow.

### 2026-06-03 - Implementation

**Root cause was deeper than the line refs suggested.** Retryable exceptions
were swallowed at **three** levels, not one: `_identify_with_plantnet` (its own
`except Exception`), the main method's PlantNet wrapper (`except Exception` →
fallback results), and the outer handler (`:226` → `failed`). Fixing only the
outer handler would have left autoretry inert.

Changes:
- `services/identification_service.py`: added module-level `RETRYABLE_EXCEPTIONS`
  = `(ExternalAPIError, APIUnavailable, RateLimitExceeded, RequestException)`.
  Re-raise these at all three catch points; permanent errors still swallowed +
  marked `failed`. The non-error `return None` → fallback path is untouched.
- `tasks.py`: added `IdentificationTask(Task)` base with `on_failure` that does
  `.exclude(status__in=TERMINAL_STATUSES).update(status="failed")` (terminal =
  `identified`/`needs_help`/`failed`); removed the body's mid-flight
  `status="failed"` write (kept `emit("error")` + `raise`); fixed the
  idempotency guard from `!= "pending"` to `in TERMINAL_STATUSES` so an
  autoretry (status=`processing`) re-runs instead of being skipped (H1).
- Tests: new `tests/test_autoretry.py` (mocks only `service.plantnet`, the
  external client); updated `tests/test_celery_idempotency.py` to use real
  statuses (`identified`, not the bogus `completed`) + added a
  `processing → service IS called` lock-in test.

**Verification** — `python manage.py test apps.plant_identification`:
```
Ran 121 tests in 55.737s
OK
```
Acceptance criteria evidence (subset, `tests.test_autoretry`/`test_celery_idempotency`, 16 tests OK):
- AC1 (retry, not immediate failed): `test_external_api_error_propagates` (status stays
  `processing`, 0 fallback rows), `test_retryable_exceptions_in_autoretry_for`,
  `test_task_body_reraises_transient_error`.
- AC2 (ends failed after exhaustion): `test_processing_marked_failed_on_exhaustion`,
  `test_pending_marked_failed_on_exhaustion`.
- AC3 (no clobber): `test_does_not_clobber_identified`, `test_does_not_clobber_needs_help`.
- AC4 (mock the client): `ServiceReRaisesTransientErrorsTest` mocks `service.plantnet`.

**Known issue (accepted, non-blocking):** widening the guard to skip-only-terminal
means a `processing` request now re-runs. For the ExternalAPIError path this is
safe (the error is raised at the API call, before any `PlantIdentificationResult`
rows are created). A worker-lost-after-partial-results requeue could theoretically
duplicate result rows (previously it stayed stuck `processing`); not introduced by
this change's primary path and out of scope for H1/M12. Noted per advisor review.

**Out of scope:** flake8 reports 4 pre-existing violations in
`identification_service.py` (unused `Tuple`/`Union`/`ContentFile` imports, 2 long
lines — orig :605/:674, now :635/:704 after my additions shifted them) — all in
untouched code; left alone per surgical principle.

### 2026-06-03 - Code review (code-review-orchestrator)

Verdict: **SHIP**. 0 CRITICAL, 0 HIGH.

Known issues (MEDIUM and below — non-blocking):
- MEDIUM — widened guard re-runs `processing` requests; a worker-lost-after-
  partial-results requeue could duplicate `PlantIdentificationResult` rows. The
  PRIMARY ExternalAPIError path is safe (error raised at the API call before any
  rows are created; `test_external_api_error_propagates` asserts `count() == 0`).
  Accepted/out-of-scope for H1/M12. Optional future hardening: delete existing
  results at the top of a re-run.
- LOW — fixed: reworded the `RETRYABLE_EXCEPTIONS` comment to state it's a
  superset of `autoretry_for` (RateLimitExceeded handled by the task's explicit
  branch, caught upstream by Trefle), not "in sync".
- LOW — `RateLimitExceeded` in `RETRYABLE_EXCEPTIONS` is dormant (Trefle catches
  it upstream; PlantNet raises `ExternalAPIError`/`QuotaExceeded`, not it). Kept
  per the todo's explicit recommended-action list; documented in the comment.
- LOW — no eager-mode retry→exhaustion e2e test; intentional decomposition
  (config-assert + body-reraise + direct `on_failure`), stated in the test
  module docstring.

Reviewer confirmed the 5 scrutiny items: `on_failure` arg parsing + dispatch
correct (bind=True → `args[0]` is the UUID; resolves to the base override; atomic
UPDATE); the two `RateLimitExceeded` classes are not confused (both use the
`apps.plant_identification.exceptions` version); Trefle graceful degradation
intact; tests mock only the external client with strict assertions.

### 2026-06-03 - Blast-radius fix (post-review advisor catch)

Advisor flagged a regression the diff-only review structurally couldn't see:
`identify_plant_from_request` is **shared** — besides the Celery task it has
SYNCHRONOUS callers in `views.py` (`perform_create` :195, the enqueue-fallback
:189, and `process_now` :273). Worse: `CELERY_ENABLED` is **never defined in
settings**, so `getattr(settings, "CELERY_ENABLED", False)` is always False →
**the create endpoint always runs synchronously and the Celery task is dormant**
(only enqueued inside `if use_celery:`). My unconditional service re-raise would
make a transient PlantNet error on the live sync path return 503 + leave the
request stuck `processing` (no on_failure in sync mode), where it previously
degraded to fallback results + 201. The full suite passed locally only because
PlantNet is unconfigured here (the API-error branch never executed) — a classic
green-but-wrong blind spot.

**Decision (user-chosen, Option A — zero regression):** gate the re-raise behind
`identify_plant_from_request(..., reraise_transient: bool = False)`. The Celery
task passes `reraise_transient=True` (→ propagate → autoretry); synchronous view
callers use the default `False` (→ swallow → fallback results → 201), preserving
exact pre-todo behavior. The three catch points branch on the flag; the inner
`_identify_with_plantnet` always propagates to the decision point.

Added test `test_sync_mode_swallows_transient_and_falls_back` (default flag →
fallback, no propagation) as a zero-regression guard, and an assertion that the
task calls the service with `reraise_transient=True`.

NOTE for future work (user opted NOT to file a follow-up todo): Celery is
effectively disabled (`CELERY_ENABLED` unset). The autoretry/on_failure fixes
here are correct and dormant until Celery is enabled; the live sync path still
has no retry and still returns fake fallback results on API failure.

### 2026-06-03 - Completed by completing-todos skill (run 2026-06-03-1835)

- Verification: all 4 acceptance criteria passed; `apps.plant_identification`
  full suite after the Option-A refactor: `Ran 122 tests in 49.564s OK`
  (was 121 + new sync-mode zero-regression test). flake8 clean on new code.
- Review: code-review-orchestrator → SHIP, 0 blocking (0 CRITICAL/HIGH); 1 MEDIUM
  + 3 LOW recorded above, one LOW (comment accuracy) fixed. Post-review advisor
  catch (shared-service blast radius) resolved via the user-chosen opt-in flag.
