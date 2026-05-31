---
name: enforce-or-drop-web-coverage-thresholds
status: completed
priority: p3
created: 2026-05-30
tags: [harness, ci, web, testing, coverage]
source_review: "PR #307 review (web-ci.yml)"
---

# Enforce web coverage thresholds in CI, or document them as dev-only

## Problem

`web/vitest.config.ts` declares coverage thresholds (lines/functions/branches/
statements = 80%), but nothing enforces them. Vitest only evaluates
`coverage.thresholds` when coverage is actually collected (`--coverage`). The new
`web-ci.yml` (todo 126) runs `npm run test -- --run` — i.e. `vitest --run` with
**no** `--coverage` — so the 80% threshold is configured but never checked. It
reads as a real gate while being a no-op.

Surfaced in the PR #307 self-review as a low-severity finding.

## Acceptance criteria

- [x] Make a deliberate decision and record it:
  - **Option A — enforce:** add a coverage step to `web-ci.yml` (e.g.
    `npm run test:coverage -- --run`) so the 80% threshold actually gates PRs.
    First confirm current coverage is ≥80% (run `npm run test:coverage` in `web/`)
    — if it isn't, either raise tests or lower the threshold to a true floor, so
    the gate is honest from day one.
  - **Option B — dev-only:** keep CI on the fast no-coverage run and add a comment
    in `vitest.config.ts` noting the thresholds are advisory/local-only, so the
    config doesn't imply enforcement it doesn't have.
  Decision: **Option B**. Coverage measured at Stmts 79.44% / Branches 76.84% /
  Functions 75.38% / Lines 80.89% — three metrics below 80%, so enforcing now
  would immediately break CI. Comment added to `web/vitest.config.ts`.
- [x] Whichever option: no config that claims a threshold the pipeline doesn't apply.
  `vitest.config.ts` now documents thresholds as advisory/local-only.

## Notes

Workflow + config files are not under `.claude/` — editable directly. If choosing
Option A, watch CI runtime (coverage instrumentation is slower than a bare run).
Relates to todo 126 (the web-ci workflow this refines) and todo 127 (harness/CI
gating).

## Work Log

### 2026-05-31 - Started by completing-todos skill (run 2026-05-31-1516)

- Picked up by automated workflow.
- Ran `npm run test:coverage -- --run` in `web/`. Results:
  Statements 79.44%, Branches 76.84%, Functions 75.38%, Lines 80.89%.
  Three of four metrics are below the 80% threshold, so Option A as-is would
  immediately break CI. Presented findings to user.
- **Decision: Option B** — keep CI on the fast bare run; add a comment to
  `vitest.config.ts` marking thresholds as advisory/local-only.

### 2026-05-31 - Completed by completing-todos skill (run 2026-05-31-1516)

- Verification: both acceptance criteria passed — decision recorded, comment added.
- Review: 0 findings — comment-only change, no logic.
