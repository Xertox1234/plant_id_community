---
status: pending
priority: p2
issue_id: "624"
tags: [backend, web, mobile, notifications, preferences, product]
dependencies: []
---

# Add important-event email and quiet hours for forum notifications

## Problem

Split from todo 620 at triage (run 2026-10-12-1616, owner decision 2026-10-12): 620 ships the policy matrix and web/mobile parity; this todo owns the optional important-event email channel and quiet-hour/frequency behavior that 620's AC4 and AC5 required.

## Findings

- `backend/packages/wagtail_forum/wagtail_forum/preferences.py:33-38` offers email only for replies; mention, quote and accepted-answer events are push-only, so members without push get no immediate signal.
- `backend/apps/forum_host/notifications.py:212-225,264-301` excludes mentioned/quoted members from reply-email recipients.
- No quiet-hour, timezone or coalescing logic exists in the forum dispatch/task paths; each reply sends immediately.

## Recommended Action

1. Build on 620's recorded policy matrix. Get owner defaults for quiet hours (window, timezone source), coalescing window and read-before-send suppression before implementing them.
2. Add optional mention/quote/accepted-answer email, deduplicated with reply email so a mentioned subscriber gets one appropriate message.
3. Implement quiet hours/coalescing with security mail exempt and the in-app inbox unaffected.

## Acceptance Criteria

- [ ] Mention/quote/accepted-answer email and mentioned-subscriber behavior are explicitly decided; approved channels are implemented and tested for missing push registration, deduplication and unsubscribe. Any declined channel has a dated reason, not an untracked deferral.
- [ ] Approved quiet-hour/frequency behavior is implemented and tested across timezones/DST, rapid replies, read-before-send, preference changes while waiting, and security-mail exemptions. Any declined option has a dated owner decision.
- [ ] Web and mobile settings expose the new choices consistently with 620's matrix; relevant backend preference/unsubscribe tests, web settings tests and type-check, and mobile preference tests/analyze pass.

## Work Log

### 2026-10-12 - Split from 620 at triage

- Criteria 620 AC4 and AC5 re-pointed here by owner decision; wording carried over unchanged.

## Notes

Depends in practice on 620's policy matrix landing first. Care reminders stay FCM-only (archived 410).
