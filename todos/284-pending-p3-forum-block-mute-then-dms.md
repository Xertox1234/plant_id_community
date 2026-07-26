---
status: pending
priority: p3
issue_id: "284"
tags: [forum, trust-and-safety, drf, web]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M9, M10"
---

# Forum: block/mute, then (only then) private messaging (M9, M10)

## Problem

Members have no way to stop seeing a specific other member (M9), and there is no
private messaging (M10). These are filed together because the ordering is a
safety requirement, not a preference: **direct messaging without block/mute
hands every member an unfilterable private channel to every other member.**
Promoted out of the todo 263 parking epic at the 2026-07-26 roadmap review,
which carried the same hard ordering as an acceptance criterion.

## Findings

State verified against `main` at 2026-07-26 (commit 27ade0c):

- **M9 — no block/mute.** No block/mute model, endpoint, or filter exists in
  `backend/packages/wagtail_forum/` (grep for `BlockedUser`/`block_user`/`mute`
  returns nothing). A member's only recourse against another member today is
  the report/flag path to moderators (`W/models/reports.py`) — which is a
  moderator action, not a personal filter.
- **M10 — no private messaging.** No DM model, endpoint, or UI exists.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

## Recommended Action

### Phase 1 — M9 block/mute (must land first)

1. `UserBlock` model (`blocker`, `blocked`, `created_at`) with a
   `UniqueConstraint` on the pair and a self-block guard. Follow the
   `related_name` conventions documented in `W/models/subscriptions.py:17-21`.
2. `POST`/`DELETE /users/{id}/block/` plus `GET /me/blocks/`.
3. **Apply the filter everywhere content is read**, not just the thread view —
   this is where block features usually leak: topic lists, thread posts, search
   results, mentions/@-typeahead, notifications, and the reactions surface.
   Enumerate the read paths from `W/api/views.py` and cover each.
4. Decide and record: does blocking hide the blocked user's posts entirely, or
   collapse them behind a "blocked — show anyway" affordance? Collapse is the
   safer default (it does not distort thread structure).
5. Moderators must still see everything — the filter is a viewer-side
   preference, never a moderation mechanism.

### Phase 2 — M10 private messaging (gated on Phase 1 shipping)

Do not begin until block/mute is merged and deployed. When promoted, that work
needs at minimum: a conversation/message model, per-message rate limiting, the
existing spam backend applied to DM bodies
(`WAGTAILFORUM_SPAM_BACKEND` — see todo 280), block enforcement at *send* time
(a blocked sender gets a success-shaped response but no delivery, or an explicit
403 — decide and document), report-a-DM support, and a retention/tombstone
story matching the forum's existing tombstone-prune cron (todo 261).

## Technical Details

- Block filtering is a cross-cutting read-path concern. Prefer one queryset
  helper (`exclude_blocked(qs, user)`) reused by every view over per-view
  `.exclude(...)` calls, so a new endpoint cannot silently miss it.
- Query-count risk: naively filtering per-row costs an N+1. Fetch the blocker's
  block-id set once per request (cacheable) and filter against it, mirroring the
  batched approach used for reactions/read-state.
- Package purity: no `apps.*` imports (`test_reusability.py`).
- Patterns: `backend/docs/patterns/domain/forum.md` (trust levels, moderation),
  `backend/docs/patterns/architecture/rate-limiting.md` (DM send limits),
  `backend/docs/patterns/performance/query-optimization.md`.

## Acceptance Criteria

- [ ] **Hard gate — no private-messaging code may merge until block/mute is
      merged.** A DM PR that touches this repo before `UserBlock` exists on
      `main` must be closed or held, and this box may only be checked by
      recording the block/mute merge commit here
- [ ] Blocking a user hides/collapses their content on every read path —
      one test per path: topic list, thread detail, search, mentions typeahead,
      notifications
- [ ] A moderator's view is unaffected by another user's blocks — test
- [ ] Self-block is rejected — test
- [ ] Block filtering adds no per-row query — exact `assertNumQueries` test on
      the thread-detail and topic-list endpoints
- [ ] Hide-vs-collapse decision recorded in the Work Log
- [ ] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Both findings re-verified absent on `main` @ 27ade0c.
- Kept as ONE todo rather than two so the ordering is structural: M10 cannot be
  picked up as an independent unit of work without reading M9's gate. Todo 263's
  AC2 ("M9 lands before or with M10 if DMs are ever promoted") is carried
  forward verbatim as this todo's first acceptance criterion.

## Notes

p3 — but note the asymmetry: M9 alone is a genuine trust-and-safety improvement
worth doing on its own merits, while M10 is a large surface-area addition
(moderation, spam, retention, abuse reporting) that this project has no current
demand signal for. The recommended outcome is **ship M9, leave M10 unstarted**.
