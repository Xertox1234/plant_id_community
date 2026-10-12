---
status: pending
priority: p2
issue_id: "626"
tags: [email, templates, accessibility, testing, owner]
dependencies: []
---

# Verify redesigned emails in real Gmail, Apple Mail and Outlook inboxes

## Problem

Split from todo 622 at triage (run 2026-10-12-1637, owner decision 2026-10-12): 622 ships the link fixes, text alternatives and base.html standardization; real inbox rendering can only be checked by the owner with approved test accounts.

## Recommended Action

1. After 622 merges, send each representative live email family (welcome, verification, password reset, forum reply/mention, digest, newsletter confirm/digest) to approved test inboxes only — never to members.
2. Check Gmail (web + mobile), Apple Mail and Outlook in light, dark and narrow-screen views; record date, client/version and observations.

## Acceptance Criteria

- [ ] Approved Gmail, Apple Mail and Outlook checks record date, client/version, light/dark/narrow-screen observations and any accepted limitation. If unavailable, keep this criterion open or explicitly re-point it to a dedicated verification todo; do not claim inbox compatibility from a browser-only render.

## Work Log

### 2026-10-12 - Split from 622 at triage

- 622 AC6 re-pointed here by owner decision; wording carried over unchanged.

## Notes

Owner-only: needs test inbox accounts. Browser screenshots are not inbox evidence.
