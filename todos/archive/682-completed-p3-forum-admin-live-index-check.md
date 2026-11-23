---
status: completed
priority: p3
issue_id: "682"
tags: [forum, forum-categories, owner, prod-check]
dependencies: ["666"]
triage: blocked-prod
triaged: 2026-11-22
blocked_on: "Someone signed in as a staff user on the live /cms/ creates a test forum, confirms it shows on live /forum within 60 s, then hides it."
owner_decision: "Owner delegated the live check to a Claude session driving Chrome (2026-11-22); run by hand outside the sweep"
---

# Forum categories: owner check that a forum created in /cms/ shows on the live web index

## Problem

Todo 666 added the *Categories & forums* screens to the Wagtail Forum menu. Its manual criterion, that a created forum appears on the web index without a deploy, needs the live site, so the owner moved it here (2026-10-28).

## Findings

- Re-pointed from todo 666 (owner decision 2026-10-28: "Move to new todo").
- The web index reads `GET /forum/categories/`; the CDN may serve a cached copy for up to 60 s (`s-maxage=60`).

## Recommended Action

After 666 is merged and deployed, create a test forum under a category in `/cms/` on the live site, open `/forum` on the web app, and confirm it is listed (allow up to 60 s for the CDN). Hide or rename the test forum afterwards.

## Acceptance Criteria

- [x] Created forums appear on the web index without a deploy (owner's manual check on the live site, dated, with the observed result quoted in the Work Log).

## Work Log

### 2026-11-22 - Live check run by Claude in desktop Chrome (owner-delegated 2026-11-22)

- Signed in to the live `/cms/` as plantadmin, created forum "Test forum 682 (admin check)"
  under General (id 18) at about 20:24:59Z.
- Observed: the signed-in web `/forum` listed it at 20:25:10Z ("Test forum 682 (admin check)
  0 THREADS · 0 POSTS · NO ACTIVITY YET"). An anonymous `GET /api/v1/forum/categories/` at
  20:25:30Z (`cache-control: public, s-maxage=60, max-age=0`, `cf-cache-status: DYNAMIC`)
  included it. About 31 s after creation, inside the 60 s window, with no deploy.
- Cleanup: owner chose delete; the empty test forum was deleted in `/cms/` ("Forum 'Test
  forum 682 (admin check)' deleted."). The tree is back to its five forums.
- The criterion is met; the next triage can archive this todo after verifying it.

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- No code change: the only criterion is a manual check on the live site, which no command
  in the repo can prove, so the sweep ran nothing for it.
- The owner confirmed the criterion on 2026-11-23 ("Confirmed, archive both"), accepting the
  2026-11-22 live check above: forum created in `/cms/` at 20:24:59Z, on the web index by
  20:25:30Z, no deploy.
- Recorded in `.sweep-evidence/g13/ac.json` as owner-confirmed, with no command and no
  evidence file.

### 2026-11-23 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-22-1957)

- AC 1: confirmed by the owner on 2026-11-23: "Owner 2026-11-23: "Confirmed, archive both", accepting the 2026-11-22 live check in the Work Log (forum created in /cms/ at 20:24:59Z, on the web index by 20:25:30Z, no deploy)." (`state.py confirm`; no command or evidence)

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; review is on the PR.
