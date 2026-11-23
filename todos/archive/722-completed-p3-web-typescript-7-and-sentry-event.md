---
status: completed
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

- [x] The TypeScript 7 row is bumped in a merged PR or declined on its Dependabot PR, with the
      PR number and reason in the Work Log (moved from 712 on 2026-11-21).
- [x] After Sentry 11: one test event from the deployed site appears in Sentry (date and event
      id recorded here; moved from 712 on 2026-11-21).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision of 2026-11-21: these criteria were
  re-pointed here because they can only be checked after the parent's PR merges, or need the owner.

### 2026-11-23 - Sentry criterion tried with the owner: no event, web Sentry was never configured

- The owner threw a test error on the deployed site (2026-11-23, about 21:15Z). Nothing reached
  Sentry: the organisation had no web project and the deployed bundle holds no DSN, so
  `initSentry()` returned at its `VITE_SENTRY_DSN` check. Sentry 11 itself was never exercised in
  production.
- The owner created the project `houseplant-md-web` and added `VITE_SENTRY_DSN` to the Cloudflare
  Worker's build variables. The test is repeated after the next production build; the event id
  goes here.

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- npm checked on 2026-11-23: `typescript-eslint` 8.74.0 (latest), its canary 8.74.1-alpha.0 and
  `@typescript-eslint/parser` 8.74.0 all require `typescript >=4.8.4 <6.1.0`; TypeScript latest
  is 7.0.2. No release accepts TypeScript 7, so `web/package.json` is unchanged and the
  `typescript` major ignore in `.github/dependabot.yml` stays (its comment now names 8.74.0).
- TypeScript 7 criterion, confirmed by the owner (2026-11-23): declined on the owner's decision of
  2026-11-22 because no typescript-eslint release accepts it. Dependabot PR #1330 (closed
  2026-11-16) carries the reason as a comment posted 2026-11-23.
- Sentry criterion, confirmed by the owner (2026-11-23): after Sentry 11 and the new
  `VITE_SENTRY_DSN` build variable, a test error on the deployed site appeared in Sentry project
  `houseplant-md-web` as event 735c9351 (issue HOUSEPLANT-MD-WEB-3), 2026-11-23T22:25:36Z,
  mechanism `auto.browser.browserapierrors.setTimeout`.
- The PR comment and the Sentry event are the owner's confirmations; this run did not re-check them.

### 2026-11-23 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-22-1957)

- AC 1: confirmed by the owner on 2026-11-23: "Owner decision 2026-11-22: TypeScript 7 is declined because no typescript-eslint release accepts it. Dependabot PR #1330 (closed 2026-11-16) carries the reason as a comment posted 2026-11-23." (`state.py confirm`; no command or evidence)
- AC 2: confirmed by the owner on 2026-11-23: "Owner 2026-11-23: after Sentry 11 and the new VITE_SENTRY_DSN build variable, a test error on the deployed site appeared in Sentry project houseplant-md-web as event 735c9351 (issue HOUSEPLANT-MD-WEB-3), 2026-11-23T22:25:36Z, mechanism auto.browser.browserapierrors.setTimeout." (`state.py confirm`; no command or evidence)

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; review is on the PR.

### 2026-11-23 - Review round 1: non-blocking findings

- **Fixed: the Dependabot ignore comment pointed at this todo, which is now archived (low, two
  reviewers).** The comment no longer relies on an open todo: it says the entry was declined
  here and names the re-check that removes it.
- **Fixed: the comment read as if #1330 failed against typescript-eslint 8.74.0 (low, two
  reviewers).** #1330 failed on 2026-11-16; 8.74.0 is the version re-checked on 2026-11-23. The
  comment now gives both dates.
