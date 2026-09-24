---
status: pending
priority: p3
issue_id: "411"
tags: [backend, web, users]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire `me/dashboard-stats/` into the profile page

## Problem

`GET /api/v1/auth/me/dashboard-stats/` (about 150 LOC; 3 tests in
`test_dashboard_stats.py`) returns plant-ID and forum aggregates, but no screen
shows them. The owner decided (todo 405) to wire it up.

The web `/profile` page became editable in PR #798 and is the natural home.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Check the payload against what the profile page should show. Some
   aggregates read `PlantIdentificationResult`, which nothing writes (todo
   405). Drop or replace those fields.
2. Render a stats section on `/profile`, with tests.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] The profile page shows the stats and has tests.
- [ ] No field depends on a table nothing writes.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.
