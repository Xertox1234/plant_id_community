---
status: pending
priority: p3
issue_id: "319"
tags: [forum, trust-and-safety, drf, web]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M10"
---

# Forum: private messaging (M10)

## Problem

No private messaging exists between forum members. Originally filed together
with M9 (block/mute) as todo 284, with a hard ordering constraint: **shipping
DMs before block/mute would hand every member an unfilterable private channel
to every other member.** M9 has now shipped (backend PR #577, web UI PR #578,
both merged 2026-08-29), so that gate is satisfied and this finding is
promoted into its own standalone todo per todo 284's own Notes ("ship M9,
leave M10 unstarted").

## Findings

State verified against `main` at 2026-08-29 (todo 284's Work Log): no DM
model, endpoint, or UI exists anywhere in the repo. `UserBlock`
(`backend/packages/wagtail_forum/wagtail_forum/models/user_blocks.py`) now
does exist and is fully wired through every content read path plus
notification fan-out — a future DM feature has a real, tested block primitive
to enforce against at send time (see Recommended Action below).

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

## Recommended Action

Per todo 284's original Phase 2 plan, this needs at minimum:

1. A conversation/message model — decide 1:1 vs. group at design time; the
   audit's framing (and this repo's existing forum surface) only motivates
   1:1.
2. Per-message rate limiting, following this repo's `_throttled()` +
   `DEFAULT_FORUM_RATELIMITS` convention (`apps/forum_host/api.py`,
   `constants.py`).
3. The existing spam backend applied to DM bodies
   (`WAGTAILFORUM_SPAM_BACKEND` — see todo 280; currently unset/dormant in
   prod, an ops decision independent of this todo).
4. **Block enforcement at send time** — a blocked sender must not be able to
   reach the blocked recipient. Decide and document: does the send call
   return a success-shaped response with silent non-delivery, or an explicit
   403? `UserBlock.can_block`/`UserBlock.objects.filter(...)` (both
   directions — mirror `_drop_blocked_pairs` in
   `apps/forum_host/notifications.py`) is the primitive to check against;
   don't re-derive block-pair logic independently.
5. Report-a-DM support, reusing the existing `Report` model/flow
   (`W/models/reports.py`) rather than a parallel one.
6. A retention/tombstone story matching the forum's existing tombstone-prune
   cron (todo 261) — decide whether DMs are covered by the same cron or need
   their own retention policy, and record the choice.

## Technical Details

- Package purity: no `apps.*` imports in `backend/packages/wagtail_forum/`
  (`test_reusability.py`).
- Reuse `UserBlock`'s existing bidirectional-check shape
  (`_should_filter_blocks`/`_exclude_blocked_authors` in
  `W/api/views.py`, `_drop_blocked_pairs` in `apps/forum_host/notifications.py`)
  rather than writing new block-pair logic for DMs — todo 284 already solved
  the "check both directions, moderator bypass, NULL-safety" problems once.
- Patterns: `backend/docs/patterns/domain/forum.md` (trust levels,
  moderation), `backend/docs/patterns/architecture/rate-limiting.md`,
  `backend/docs/patterns/security/input-validation.md`.

## Acceptance Criteria

- [ ] A blocked sender cannot deliver a DM to the user who blocked them —
      test, both directions (blocker→blocked and blocked→blocker)
- [ ] Conversation/message model with per-message rate limiting — test
- [ ] Report-a-DM reuses the existing `Report` model — test
- [ ] Retention/tombstone decision recorded in the Work Log (covered by the
      existing cron, or a new one — either is acceptable, silence is not)
- [ ] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-08-29 - Promoted out of todo 284 (M9 shipped)

- M9 (block/mute) shipped: backend PR #577 (merge commit
  0abc21425399ffd069972f4c8c52bd5a44ea4d78) + web UI PR #578, both merged.
  Todo 284's hard gate ("no private-messaging code may merge until block/mute
  is merged") is now satisfied.
- Finding re-verified absent on `main` — no DM model/endpoint/UI anywhere in
  the repo.
- Source review's Finding Status line for #M10 re-pointed from todo 284 to
  this todo (319), per this project's re-pointing convention (a promoted
  finding is re-pointed, never checked off, until it actually ships).

## Notes

p3 — no current demand signal for this feature; todo 284's Notes were
explicit that M9 alone was the recommended shippable outcome and M10 should
stay unstarted absent a concrete need. This todo exists so the finding stays
tracked, not as a signal to prioritize it.
