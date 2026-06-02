---
status: pending
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

- [ ] A transient `ExternalAPIError` from the external API triggers a Celery
      retry (assert via `self.request.retries` or a retry spy), not an immediate
      permanent `failed`.
- [ ] After `max_retries`, the request ends `failed` (not stuck `pending`/`processing`).
- [ ] `on_failure` never overwrites `identified`/`needs_help`.
- [ ] Tests mock the external API client, not the whole `PlantIdentificationService`.

## Notes

p2: the feature works for the happy path; the gap is resilience under transient
external-API failures. The earlier task-only fix was reverted (commit history on
branch `chore/full-audit-2026-06-02`) precisely because it was inert without the
service change — do them together.
