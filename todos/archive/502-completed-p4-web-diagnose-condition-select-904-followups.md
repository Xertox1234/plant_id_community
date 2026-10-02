---
status: completed
priority: p4
issue_id: "502"
tags: [web, frontend]
dependencies: []
triage: ready
triaged: 2026-10-01
---

# Web diagnose condition select: non-blocking findings from PR #904 (todo 459)

## Problem

PR #904 (todo 459) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`web/src/pages/diagnosis/DiseaseDiagnosePage.tsx:13`** (low, round 1, round 2). The PlantCondition union (types/diagnosis.ts) and the PLANT\_CONDITIONS array are kept in sync by hand. TypeScript checks that each array value is in the union, but nothing fails if a union key is left out of the array, and nothing ties either list to the backend choices.
   Suggested: Optional. Declare the keys once as a `const` tuple in types/diagnosis.ts, derive `PlantCondition` from it, and build the array from that tuple. Or add a test that compares the array's keys with the union.
   Also reported: PLANT\_CONDITIONS is typed ReadonlyArray\<{value: PlantCondition}>, which does not enforce that all five union members are listed, and nothing ties the union to the backend choices. If the model's choices drift, the select and the type drift silently. Keys and labels match models.py:853-861 and mobile today.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #904 review rounds 1-2.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-02-0118)

- Finding 1 (union vs array drift): the keys are now declared once, as the `PLANT_CONDITIONS` `as const` tuple in `web/src/types/diagnosis.ts`, and `PlantCondition` is derived from it, so a key can no longer be in the union but missing from the list.
- The labels moved to `PLANT_CONDITION_LABELS: Record<PlantCondition, string>` in `DiseaseDiagnosePage.tsx`, so a condition without a label is a `tsc` error; the select's options are built from the tuple, in the model's order.
- Backend tie (the "also reported" half): new test `offers exactly the plant_condition choices declared on the backend model` reads `backend/apps/plant_identification/models.py`, extracts the `plant_condition` choices and asserts the rendered `[value, label]` pairs and the tuple equal them. Mutation-checked: adding a sixth choice to the model fails it.
- The mobile copy of the list is not tied by this test; it was out of this finding's scope (the finding names the web array, the union and the backend).

### 2026-10-01 - Verified by the todo sweep (run 2026-10-02-0118)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_867e27f5-a58-1/web && ./node_modules/.bin/vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx && npm run type-check` — evidence `.sweep-evidence/g1/502-ac0.txt`, last lines:

  ```text
     Duration  1.35s (transform 77ms, setup 127ms, import 255ms, tests 320ms, environment 563ms)


  > web@0.0.0 type-check
  > tsc --noEmit
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-02-0118)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
