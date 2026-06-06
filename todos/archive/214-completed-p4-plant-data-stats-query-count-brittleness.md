---
status: completed
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

- [x] The test still fails if `plant_data_stats` regresses to per-metric counts.
- [x] The query-count assertion is either decoupled from auth/session overhead
      (option 1) or its composition is documented (option 2) — or the todo is
      closed with an explicit accept-as-is rationale (option 3).

## Work Log

### 2026-06-05 - Filed

- Surfaced in the PR #341 (`/review`) pass as a 🟢 minor nit. Non-blocking; the
  test is correct and green today.

### 2026-06-05 - Started by completing-todos skill (run 2026-06-05-2256)

- Picked up by automated workflow.

### 2026-06-05 - Implemented (option 1 — CaptureQueriesContext)

- Replaced `assertNumQueries(7)` in
  `test_query_count_does_not_scale_with_species` with a
  `CaptureQueriesContext` capture filtered to the two data tables
  (`PlantSpecies._meta.db_table`, `PlantIdentificationRequest._meta.db_table`),
  asserting exactly **2** data queries. Auth/session/savepoint queries are now
  excluded, so a Django/middleware upgrade can't break a test that guards the
  L13 aggregate. Used `_meta.db_table` rather than hardcoded names so a future
  `db_table` rename also can't silently mis-filter. Matches the existing
  table-substring convention in `apps/blog/tests/test_n_plus_1.py:355`.

**Verification — criterion 2 (decoupled, green):**

```
$ python manage.py test apps.blog.tests.test_plant_data_stats --keepdb
Ran 2 tests in 0.249s
OK
```

**Verification — criterion 1 (catches regression):** temporarily reverted the
production aggregate in `api_views.py` to four separate `.count()` calls, ran the
test, then restored:

```
AssertionError: 5 != 2 : plant_data_stats must hit each data table exactly once;
per-metric expansion would add queries. Captured:
Ran 1 test in 0.153s
FAILED (failures=1)
```

5 = 4 species `.count()` + 1 request `.count()`, exactly as predicted. Production
`api_views.py` restored to the single `aggregate()` (verified: 0 diff, aggregate
present) and the suite is green again. No production code changed by this todo.

### 2026-06-05 - Code review + hardening

- Reviewed via test-quality-reviewer (code-review-orchestrator routing: test-only
  diff). 1 finding, **low** severity — non-blocking under the skill's policy.
- Finding (applied anyway, since test robustness is this todo's whole point): the
  bare-substring table filter `table in q["sql"]` had a latent false-positive —
  `plant_identification_plantspecies` is a prefix of the Wagtail
  `plant_identification_plantspeciespage` table, so a future query against the
  page table would be miscounted as a data query and could mask a regression.
  Fixed by matching the quoted identifier Django emits (`f'"{table}"'`); the
  trailing `"` stops the over-match. Portable across Postgres (CI) and SQLite.
- Re-verified after the fix: pass check `Ran 2 tests ... OK`; regression check
  (temp per-metric revert) `AssertionError: 5 != 2 ... FAILED`; restored —
  aggregate present, suite green.

### 2026-06-05 - Completed by completing-todos skill (run 2026-06-05-2256)

- Verification: both acceptance criteria passed (regression-caught + decoupled
  from auth/session overhead via option 1).
- Review: 1 finding total, 0 blocking (1 low) — the low finding was repaired
  (quoted-identifier filter) and re-verified rather than deferred.

## Notes

p4 — pure test-robustness hardening, zero runtime impact. Bundle into the next
touch of the blog test suite if not done standalone.
