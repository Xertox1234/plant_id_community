---
status: pending
priority: p3
issue_id: "300"
tags: [forum, web, backend, gamification]
dependencies: []
---

# Forum day streak + badge progress ("Your season" card)

## Problem

The Canopy artifact's "Your season" section shows a day streak and badge
progress ("16 to your Botanist badge"). PR 2.5 deliberately ships the streak
card as a zero-state ("—" / "Coming soon") and omits progress bars entirely —
no fabricated numbers (spec §9 honesty ledger). The real feature needs
activity tracking that does not exist yet.

## Findings

- Spec §9 (zero-state decision):
  `docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md`
- Zero-state card lives in `web/src/pages/forum/CategoryListPage.tsx`
  (the fourth "Your season" StatCard, `value="—"`, `sublabel="Coming soon"`,
  with a code comment pointing at this todo).
- `StatCard` already supports a `progress` prop
  (`web/src/components/ui/StatCard.tsx`) — deliberately unused until badges
  are real.
- `me/stats/` endpoint (PR 2.5) returns all-time posts / solutions /
  identifications — the natural home for streak/badge fields later.

## Recommended Action

1. Per-user daily-activity tracking: an activity-date table (user, date
   unique-together) written on post publish (Wagtail `published` signal —
   same hook the counters use).
2. Streak computation (consecutive days ending today/yesterday) exposed on
   `me/stats/`.
3. Badge definitions + thresholds + award logic (e.g. Botanist = N accepted
   identifications), with per-badge progress in the payload.
4. Replace the zero-state card with the real streak value and restore
   `StatCard` progress bars for the nearest badge.

## Technical Details

- Counters/trust fire on Wagtail's `published` signal —
  `backend/packages/wagtail_forum/wagtail_forum/signals.py` shows the pattern.
- Keep tunables in `conf.py` `DEFAULTS` (package convention).

## Acceptance Criteria

- [ ] Streak card shows a real number that increments with next-day activity
      and resets after a gap (unit-tested date math).
- [ ] At least one badge exists with visible progress on the landing page.
- [ ] The zero-state code comment in `CategoryListPage.tsx` is removed.

## Work Log

### 2026-08-15 - Filed

- Deferred out of PR 2.5 (canopy forum content) by spec §9: ship honest
  zero-states rather than fabricated streak/badge numbers.
