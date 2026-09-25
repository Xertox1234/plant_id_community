---
status: pending
priority: p3
issue_id: "412"
tags: [backend, web, mobile, users]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire up onboarding (`me/onboarding/*`) and fix the broken demo-data seeder

## Problem

`me/onboarding/*` (4 routes, about 190 LOC) has no client. The owner decided
(todo 405) to wire it up. The adversarial verifier (todo 405, 2026-09-23)
proved the demo-data half is broken three ways:

- `POST me/onboarding/create-demo-data/` returns 500:
  `_create_demo_identifications` imports `apps.common.models` and
  `IdentificationResult`, and neither exists.
- Even with the imports fixed, it would fail again: `is_demo_data` and
  `image_1_url` are not fields (the request model has `image_1`).
- `DELETE me/onboarding/demo-data/` returns 500 on its own, because
  `DemoData.objects.filter(user=…)` uses a field that does not exist (the
  field is `created_by`).

`OnboardingProgress` is created by a live signal (`users/signals.py:56`).

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Decide what onboarding is for in Houseplant MD: steps, and whether demo
   data belongs at all.
2. Rebuild the demo seeder against the real models, or delete it. Fix the
   delete view.
3. Build the onboarding UI on the chosen client(s).

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] Both demo-data endpoints return 2xx or are removed. Tests pin them.
- [ ] A client shows onboarding progress.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-24 - Owner decision: checklist onboarding, no demo data (gate removed)

Decided by the owner: onboarding is a **progress checklist** (e.g. first plant
ID, first forum post, profile filled in) on the existing `OnboardingProgress`
model, shown by a client. **Delete** the demo-data seeder and both demo-data
endpoints (`POST me/onboarding/create-demo-data/`, `DELETE me/onboarding/demo-data/`)
instead of rebuilding them — that satisfies AC 1's "or are removed" branch.
Ready for a sweep.
