---
name: enforce-or-drop-web-coverage-thresholds
status: pending
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

- [ ] Make a deliberate decision and record it:
  - **Option A — enforce:** add a coverage step to `web-ci.yml` (e.g.
    `npm run test:coverage -- --run`) so the 80% threshold actually gates PRs.
    First confirm current coverage is ≥80% (run `npm run test:coverage` in `web/`)
    — if it isn't, either raise tests or lower the threshold to a true floor, so
    the gate is honest from day one.
  - **Option B — dev-only:** keep CI on the fast no-coverage run and add a comment
    in `vitest.config.ts` noting the thresholds are advisory/local-only, so the
    config doesn't imply enforcement it doesn't have.
- [ ] Whichever option: no config that claims a threshold the pipeline doesn't apply.

## Notes

Workflow + config files are not under `.claude/` — editable directly. If choosing
Option A, watch CI runtime (coverage instrumentation is slower than a bare run).
Relates to todo 126 (the web-ci workflow this refines) and todo 127 (harness/CI
gating).
