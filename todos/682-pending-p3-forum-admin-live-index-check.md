---
status: pending
priority: p3
issue_id: "682"
tags: [forum, forum-categories, owner, prod-check]
dependencies: ["666"]
triage: blocked-prod
triaged: 2026-11-20
blocked_on: "The owner creates a test forum in the live /cms/, sees it listed on the live /forum index within 60 s, and logs the date and what he saw."
owner_decision: "Owner: Claude runs the live /cms/ to /forum check on the Samsung over wireless adb in the remote session (2026-11-20)"
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

- [ ] Created forums appear on the web index without a deploy (owner's manual check on the live site, dated, with the observed result quoted in the Work Log).

## Work Log
