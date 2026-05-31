---
status: pending
priority: p2
issue_id: "137"
tags: [testing, frontend, ci]
dependencies: []
estimated_effort: "2-4 hours"
---

# Fix diagnosisService.test.ts failures in web CI

## Problem

The `Type-check, lint, and unit/component tests` CI job is failing on every PR
due to test failures in `web/src/services/diagnosisService.test.ts`. This is a
pre-existing failure — it also fails on `main`.

Discovered: 2026-05-31 via `gh run view` on PR #312.

## Findings

Failing tests (all in `diagnosisService.test.ts`):

- `fetchDiagnosisCards > should fetch diagnosis cards with default options`
- `createDiagnosisCard > should create a new diagnosis card`
- `createDiagnosisCard > should handle validation errors`
- `updateDiagnosisCard > should update a diagnosis card`
- `deleteDiagnosisCard > should delete a diagnosis card`
- `deleteDiagnosisCard > should handle delete errors`
- `toggleFavorite > should toggle favorite status`
- `createReminder > should create a new reminder`
- `snoozeReminder > should snooze a reminder with default/custom hours`
- `cancelReminder > should cancel a reminder`
- `acknowledgeReminder > should acknowledge a sent reminder`
- `deleteReminder > should delete / handle errors`

Root cause unknown — needs investigation. Likely a mismatch between the service's
API shape and the test's mock expectations (e.g. URL, response structure, auth
headers) introduced when `diagnosisService` was last modified.

## Recommended Action

1. Run `cd web && npx vitest run src/services/diagnosisService.test.ts` locally
   and capture the full failure output.
2. Compare the service's actual request shape against the test mocks.
3. Fix either the service (if it regressed) or the tests (if they drifted from
   the current API contract).

## Acceptance Criteria

- [ ] `npx vitest run src/services/diagnosisService.test.ts` exits 0 locally.
- [ ] `Type-check, lint, and unit/component tests` CI job passes on a new PR.

## Work Log

### 2026-05-31 - Created

Surfaced while investigating CI failures blocking auto-merge of PR #312.
