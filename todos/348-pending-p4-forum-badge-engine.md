---
status: pending
priority: p4
issue_id: "348"
tags: [forum, gamification, package]
dependencies: []
---

# Badge engine — generalize past the single hardcoded Botanist badge

## Problem

Gamification today is: one badge ("Botanist", threshold on
`identifications_shared`) + a day-streak counter
(`wagtail_forum/models/activity.py:1-99`, `MeStatsView`). Trust levels
exist but grant no visible ladder beyond autopublish. Discourse's badge
engine (grants for firsts, thresholds, streaks, moderation service) is a
major retention/governance surface; ours is a stub.

## Findings

- Botanist: hardcoded name + `BADGE_BOTANIST_THRESHOLD` in
  `ForumSettings`/`conf.py` (host-overridable already).
- `ForumActivityDate` gives streak primitives usable by other badge types.
- Trust thresholds are post-count-only (`TRUST_THRESHOLDS = {1:1, 2:5,
  3:50, 4:200}`, `conf.py:10`) — badges are the natural companion signal.

## Recommended Action

Keep the scope to an engine, not a catalog:

1. **Package (`wagtail_forum`):** `Badge` snippet (name, slug, icon,
   description) + `BadgeRule` (metric + threshold, from a finite enum:
   posts, solutions, identifications_shared, streak_days,
   flags_actioned_against?) + `UserBadge`. Wagtail-native: register via
   the existing snippet viewset pattern so hosts curate badges in the CMS —
   no code to add a badge.
2. Award via the existing signal pipeline (publish/accept/streak
   recomputation sites in `wagtail_forum/signals.py:126-177`), inside
   `transaction.on_commit`, idempotent per `(user, badge)`.
3. **Seeded defaults at package level:** first post, first solution,
   identifications milestone (the current Botanist, migrated onto the
   engine), 7/30-day streaks. Data migration converts existing implied
   Botanist holders so `MeStatsView` progress doesn't regress.
4. **Web:** extend `SeasonStatsGrid.tsx` badge-progress display to list
   earned badges; profile page shows them.
5. Out of scope: badge-granted permissions (trust-level coupling) — that's
   governance, needs its own design.

## Technical Details

- Snippet registration + settings precedent:
  `wagtail_forum/wagtail_hooks.py:1-332`, `apps/forum_host/models.py:140-246`.
- Idempotency conventions: `wagtail_forum/api/idempotency.py:1-62`.
- Package must ship with zero required badges — engine inert until host
  seeds (fits reusable-package constraint).

## Acceptance Criteria

- [ ] `Badge`/`BadgeRule`/`UserBadge` models in package; a CMS-defined
      badge can be created and awarded without code changes
- [ ] Existing Botanist behavior preserved: current holders keep it;
      `MeStatsView` progress unchanged
- [ ] Award idempotent (no dupes under repeated signals; test-pinned)
- [ ] Web displays earned badges on profile

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment: "Behind
  Discourse's badge engine + trust-graded privileges."
