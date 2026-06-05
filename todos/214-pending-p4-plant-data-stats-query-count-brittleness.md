---
status: pending
priority: p4
issue_id: "214"
tags: [testing, backend, blog, tech-debt]
dependencies: []
source_review: "PR #341 review (todo-sweep 206-210)"
source_finding: "review nit — exact assertNumQueries brittleness"
---

# Decouple plant_data_stats query-count test from auth overhead

## Problem

`backend/apps/blog/tests/test_plant_data_stats.py::PlantDataStatsQueryTest.
test_query_count_does_not_scale_with_species` pins `assertNumQueries(7)`. Only
**2** of those queries are the code under test (the L13 `PlantSpecies`
conditional `aggregate()` + the `PlantIdentificationRequest` count). The other
~5 are incidental overhead from `self.client.force_login` (session lookup, user
lookup) plus transaction savepoints.

The exact pin is house style and is stable today, but it is the most
environment-coupled assertion added in the sweep: a Django/middleware upgrade
that changes session/auth query counts would break this test with **no
regression** in the L13 aggregate it is meant to guard.

## Recommended Action

Pick one (in order of preference):

1. Assert only the data queries via `django.test.utils.CaptureQueriesContext`,
   filtering captured SQL to the `plantspecies` / `plantidentificationrequest`
   tables — pins exactly the 2 queries the L13 fix is about, immune to auth churn.
2. Keep the exact `assertNumQueries(7)` but add a comment breaking down the
   count (2 data + N auth/session/savepoint) so a future bump is trivial to
   re-baseline.
3. Accept as-is and close — exact counts are the documented house style.

## Technical Details

- File: `backend/apps/blog/tests/test_plant_data_stats.py` (the `7` on the
  `assertNumQueries` line).
- The regression it must keep catching: L13 reverting from one conditional
  `aggregate()` to four separate `.count()` calls (would add 3 queries).

## Acceptance Criteria

- [ ] The test still fails if `plant_data_stats` regresses to per-metric counts.
- [ ] The query-count assertion is either decoupled from auth/session overhead
      (option 1) or its composition is documented (option 2) — or the todo is
      closed with an explicit accept-as-is rationale (option 3).

## Work Log

### 2026-06-05 - Filed

- Surfaced in the PR #341 (`/review`) pass as a 🟢 minor nit. Non-blocking; the
  test is correct and green today.

## Notes

p4 — pure test-robustness hardening, zero runtime impact. Bundle into the next
touch of the blog test suite if not done standalone.
