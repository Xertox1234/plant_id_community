---
status: pending
priority: p3
issue_id: "084"
tags: [forum, config, audit-2026-05-17]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "H14,H15,H35,M6,M9,M11,M13,L5,L6,L31"
---

# apps/forum/ audit findings — gated on forum-config decision

## Problem

The 2026-05-17 audit found that `settings.py:199-204` installs the headless DRF
forum (`apps/forum/`) only when `ENABLE_FORUM=False`; `.env` sets
`ENABLE_FORUM=True`, so the Machina forum is active and `apps/forum/` is NOT
installed (this is why 72 backend tests error). At audit triage the user confirmed
**Machina is authoritative** and `apps/forum/` is treated as an unfinished branch.

These findings are therefore deferred — they are only worth fixing if/when
`apps/forum/` is promoted to the active forum. Until then they are dead-branch code.

## Findings

All in `apps/forum/` (see `docs/audits/2026-05-17-full.md` for detail):

- **H14** — `get_permissions()` doesn't call `super()` for the `toggle` action
  (`viewsets/reaction_viewset.py:97`).
- **H15** — `get_permissions()` doesn't call `super()` for the `tree` action
  (`viewsets/category_viewset.py:107`).
- **H35** — detail-view query count uses `assertLessEqual` not `assertEqual`
  (`tests/test_post_performance.py:321`).
- **M6** — missing `select_related('parent')` on `CategoryViewSet`.
- **M9** — manual 429 missing `Retry-After` on `flag_post`/`flag_thread`.
- **M11** — bare `except Exception` turns a 400 into a 500 in `review_flag`.
- **M13** — redundant manual permission check duplicating an action permission class.
- **L5** — unbounded querysets in some list actions if pagination disabled.
- **L6** — `Exists()` wrapped in `Q()` inside `filter()`.
- **L31** — `@skip`ped rate-limit-reset test left unverified.

## Recommended Action

1. First resolve the forum-config question: is `apps/forum/` ever going to be the
   active forum? If never, **delete `apps/forum/` and its 16 test modules** instead
   of fixing these findings (and remove the `tests.py`-collision risk entirely).
2. If `apps/forum/` is to be promoted: fix the findings above, then correct the
   `ENABLE_FORUM` flag logic in `settings.py`.

## Acceptance Criteria

- [ ] Forum-config decision recorded (promote `apps/forum/` or delete it).
- [ ] If promoted: each finding fixed and forum tests run clean.
- [ ] If deleted: `apps/forum/` removed; no dangling imports.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4). User confirmed Machina is the
  authoritative forum.
