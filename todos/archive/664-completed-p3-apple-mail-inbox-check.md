---
status: completed
priority: p3
issue_id: "664"
tags: [email, templates, testing, owner]
dependencies: []
triage: ready
triaged: 2026-11-03
owner_decision: "Owner checked Apple Mail: All looked right (light, dark and narrow all rendered correctly on iOS and macOS) (2026-11-03); criterion 0 confirmed by the owner (2026-11-03): All looked right: light, dark and narrow all rendered correctly on iOS and macOS"
---

# Check the redesigned emails in Apple Mail

## Problem

Split from todo 626 on 2026-10-28 (owner: "new todo for Apple Mail"). Todo 626 recorded real-inbox checks in Outlook for iOS and Gmail; Apple Mail was not checked.

## Recommended Action

1. The owner runs `python manage.py send_inbox_samples --to <own address> [--family ...]` on prod themselves (via `railway ssh`). It sends each email family with an `[Inbox check]` subject prefix; its signed links carry no real tokens.
2. Check each `[Inbox check]` mail in Apple Mail (iOS and/or macOS) in light, dark and narrow-screen views; record date, client/OS version and observations.
3. Outlook for iOS needed the PR #1211 fixes (it inverts colors in dark mode), so watch dark-mode colors and the forum digest cards.

## Acceptance Criteria

- [x] Apple Mail check records date, client/OS version, light/dark/narrow-screen observations and any accepted limitation; browser-only renders do not count.

## Work Log

### 2026-10-28 - Split from 626

- Split from todo 626 by owner decision ("new todo for Apple Mail"); Outlook for iOS and Gmail were checked there.

### 2026-11-03 - Implemented by the todo sweep (run 2026-11-03-2214)

- No code change: the only criterion is an owner-only Apple Mail inbox check.
- The owner checked the `[Inbox check]` mails in Apple Mail on 2026-11-03: "All looked right: light, dark and narrow all rendered correctly on iOS and macOS". No limitation was reported.
- Criterion 0 is recorded as owner-confirmed in the sweep evidence; Land ticks it, quoting the owner's words.

### 2026-11-03 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-03-2214)

- AC 1: confirmed by the owner on 2026-11-03: "All looked right: light, dark and narrow all rendered correctly on iOS and macOS" (`state.py confirm`; no command or evidence)

### 2026-11-03 - Completed by the todo sweep (run 2026-11-03-2214)

- Archived by `land.py archive`; review is on the PR.

## Notes

Owner-only: needs the owner's own Apple Mail client. Browser screenshots are not inbox evidence.

### 2026-11-03 - Review round 1: non-blocking findings (PR #1265)

- RECORDED (low, two reports at line 26): the criterion asks for the client/OS version. The owner's answer named only "iOS and macOS"; no iOS, macOS or Apple Mail version was given, so the versions are not recorded. Limitation: version not recorded.
- DECLINED (low, line 38): "Criterion 0" (0-based, as the sweep's `ac.json` counts) and "AC 1" (1-based) name the same single criterion; there is only one.
- DECLINED (low, `todos/archive/626-…md:45`): 626's link to `todos/664-pending-…` is a historical note in an archived todo; todo id 664 still resolves in `todos/archive/`.
