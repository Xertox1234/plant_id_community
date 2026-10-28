---
status: completed
priority: p2
issue_id: "626"
tags: [email, templates, accessibility, testing, owner]
dependencies: []
triage: ready
triaged: 2026-10-28
owner_decision: "Unblocked: owner ran the real-inbox checks 2026-10-27/28 in Outlook for iOS ('much better' after #1211) and Gmail ('everything looks good in gmail'); Apple Mail split to new todo 664 ('new todo for Apple Mail') (2026-10-28); criterion 0 confirmed by the owner (2026-10-28): Outlook for iOS, owner 2026-10-28 after the #1211 fixes: \"much better\" (version: \"I am using the latest IOS version of outlook\", build number not recorded; iOS version not recorded). Gmail, same inbox: \"everything looks good in gmail\" (web/app not specified). Apple Mail: \"new todo for Apple Mail\", the accepted limitation, carried by new todo 664."
---

# Verify redesigned emails in real Gmail, Apple Mail and Outlook inboxes

## Problem

Split from todo 622 at triage (run 2026-10-12-1637, owner decision 2026-10-12): 622 ships the link fixes, text alternatives and base.html standardization; real inbox rendering can only be checked by the owner with approved test accounts.

## Recommended Action

1. After 622 merges, send each representative live email family (welcome, verification, password reset, forum reply/mention, digest, newsletter confirm/digest) to approved test inboxes only — never to members.
2. Check Gmail (web + mobile), Apple Mail and Outlook in light, dark and narrow-screen views; record date, client/version and observations.

## Acceptance Criteria

- [x] Approved Gmail, Apple Mail and Outlook checks record date, client/version, light/dark/narrow-screen observations and any accepted limitation. If unavailable, keep this criterion open or explicitly re-point it to a dedicated verification todo; do not claim inbox compatibility from a browser-only render.

## Work Log

### 2026-10-12 - Split from 622 at triage

- 622 AC6 re-pointed here by owner decision; wording carried over unchanged.

### 2026-10-28 - Real-inbox checks (owner)

- Tooling: PR #1210 added `backend/apps/core/management/commands/send_inbox_samples.py` (10 email families, `[Inbox check]` subject prefix, at most 5 recipients; signed links point at `SITE_URL/inbox-check/<name>` and carry no real tokens). The owner ran the dry run (10 ok), then the real send from prod at 2026-10-27 23:27 UTC to their own `+inbox` alias (all 10 sent).
- Outlook for iOS (the owner's only daily client), checked in dark mode on a portrait iPhone (portrait counts as the narrow-screen view). Version: "latest" per the owner ("I am using the latest IOS version of outlook"); build number not recorded; iOS version not recorded. Light mode: not separately reported. Observation: Outlook for iOS ignores `color-scheme: light` and inverts colors in dark mode.
- Two issues found in Outlook for iOS: (a) the forum digest's topic dividers rendered as white lines and the underlined topic titles looked heavy; (b) the welcome email's amber/orange Tip box (#fef3c7 / #b45309 / #78350f) clashed with the green palette. Both fixed in PR #1211: digest sections are borderless #f0f7f2 cards, titles not underlined, an "N new" pill and a "Go to the forum" button; the Tip box is now #f0f7f2 background, #2c5f41 border/title, #333333 body. Tests: `test_forum_digest_is_cards_without_topic_dividers` and `test_welcome_tip_uses_the_brand_palette` in `backend/apps/users/tests/test_email_presentation.py`. The owner resent forum_digest + welcome at 2026-10-28 02:46 UTC: "much better".
- Gmail, same inbox (one Gmail address): "everything looks good in gmail". Web vs app not specified.
- Apple Mail: not checked; owner: "new todo for Apple Mail", carried by todo 664 (the accepted limitation for this todo). Also accepted and left unchanged: the password-reset email's amber security notice (`backend/templates/account/email/password_reset_key_message.html`).
- Not recorded: an Outlook for iOS light-mode result, the Gmail client (web or app) and version, and Gmail light/dark/narrow results. The owner confirmed the criterion with these gaps on 2026-10-28; nothing above claims them.

### 2026-10-28 - Implemented by the todo sweep (run 2026-10-28-1052)

- Recorded the owner's real-inbox checks above (Outlook for iOS and Gmail, dates, versions as reported, observations, accepted limitations); no code changed.
- Criterion 0 is owner-confirmed (2026-10-28) per the owner decision in the frontmatter; Apple Mail split to new todo 664 (`todos/664-pending-p3-apple-mail-inbox-check.md`).

### 2026-10-28 - Confirmed by the owner, ticked by the todo sweep (run 2026-10-28-1052)

- AC 1: confirmed by the owner on 2026-10-28: "Outlook for iOS, owner 2026-10-28 after the #1211 fixes: "much better" (version: "I am using the latest IOS version of outlook", build number not recorded; iOS version not recorded). Gmail, same inbox: "everything looks good in gmail" (web/app not specified). Apple Mail: "new todo for Apple Mail", the accepted limitation, carried by new todo 664." (`state.py confirm`; no command or evidence)

### 2026-10-28 - Completed by the todo sweep (run 2026-10-28-1052)

- Archived by `land.py archive`; review is on the PR.
- Review round 1 (PR #1213): no blocking findings. Three lows, all fixed by hand: two asked that the unrecorded views be named (the "Not recorded" line above), and one found that 622's link to this todo was already broken on main (fixed to the archived name).

## Notes

Owner-only: needs test inbox accounts. Browser screenshots are not inbox evidence.
