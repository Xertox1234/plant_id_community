---
status: pending
priority: p3
issue_id: "664"
tags: [email, templates, testing, owner]
dependencies: []
---

# Check the redesigned emails in Apple Mail

## Problem

Split from todo 626 on 2026-10-28 (owner: "new todo for Apple Mail"). Todo 626 recorded real-inbox checks in Outlook for iOS and Gmail; Apple Mail was not checked.

## Recommended Action

1. The owner runs `python manage.py send_inbox_samples --to <own address> [--family ...]` on prod themselves (via `railway ssh`). It sends each email family with an `[Inbox check]` subject prefix; its signed links carry no real tokens.
2. Check each `[Inbox check]` mail in Apple Mail (iOS and/or macOS) in light, dark and narrow-screen views; record date, client/OS version and observations.
3. Outlook for iOS needed the PR #1211 fixes (it inverts colors in dark mode), so watch dark-mode colors and the forum digest cards.

## Acceptance Criteria

- [ ] Apple Mail check records date, client/OS version, light/dark/narrow-screen observations and any accepted limitation; browser-only renders do not count.

## Work Log

### 2026-10-28 - Split from 626

- Split from todo 626 by owner decision ("new todo for Apple Mail"); Outlook for iOS and Gmail were checked there.

## Notes

Owner-only: needs the owner's own Apple Mail client. Browser screenshots are not inbox evidence.
