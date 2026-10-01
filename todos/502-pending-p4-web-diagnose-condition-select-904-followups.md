---
status: pending
priority: p4
issue_id: "502"
tags: [web, frontend]
dependencies: []
---

# Web diagnose condition select: non-blocking findings from PR #904 (todo 459)

## Problem

PR #904 (todo 459) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`web/src/pages/diagnosis/DiseaseDiagnosePage.tsx:13`** (low, round 1, round 2). The PlantCondition union (types/diagnosis.ts) and the PLANT\_CONDITIONS array are kept in sync by hand. TypeScript checks that each array value is in the union, but nothing fails if a union key is left out of the array, and nothing ties either list to the backend choices.
   Suggested: Optional. Declare the keys once as a `const` tuple in types/diagnosis.ts, derive `PlantCondition` from it, and build the array from that tuple. Or add a test that compares the array's keys with the union.
   Also reported: PLANT\_CONDITIONS is typed ReadonlyArray\<{value: PlantCondition}>, which does not enforce that all five union members are listed, and nothing ties the union to the backend choices. If the model's choices drift, the select and the type drift silently. Keys and labels match models.py:853-861 and mobile today.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #904 review rounds 1-2.
