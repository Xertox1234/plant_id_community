---
status: pending
priority: p3
issue_id: "722"
tags: [web, dependencies, owner]
dependencies: ["712"]
triage: ready
triaged: 2026-11-22
owner_decision: "needs-research: a planner checks npm for a typescript-eslint release accepting TS 7 and bumps if one exists; the Sentry event criterion stays owner-gated (owner 2026-11-22)"
---

# Web: TypeScript 7 and the deployed Sentry event check (from todo 712)

## Problem

Todo 712 shipped Vitest 5, jest-dom 7, Sentry 11 and jsdom 31. TypeScript 7 waits for typescript-eslint, and the Sentry check needs a deployed site.

## Findings

- `.github/dependabot.yml` ignores the TypeScript major until typescript-eslint accepts TypeScript 7.
- The Sentry 11 bump is merged; no event from the deployed site has been checked in the dashboard yet.

## Recommended Action

When typescript-eslint supports TS 7, bump `typescript` and run the web checks. Separately, send one test event from the deployed site and find it in Sentry.

## Technical Details

- `web/package.json` `typescript`; `@typescript-eslint/*`; `.github/dependabot.yml` TS ignore entry.

## Acceptance Criteria

- [ ] The TypeScript 7 row is bumped in a merged PR or declined on its Dependabot PR, with the
      PR number and reason in the Work Log (moved from 712 on 2026-11-21).
- [ ] After Sentry 11: one test event from the deployed site appears in Sentry (date and event
      id recorded here; moved from 712 on 2026-11-21).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision of 2026-11-21: these criteria were
  re-pointed here because they can only be checked after the parent's PR merges, or need the owner.
