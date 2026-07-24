---
status: pending
priority: p3
issue_id: "277"
tags: [forum, api, drf, openapi]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M40, L20"
---

# Forum: list-envelope normalization + versioning-rationale comment

## Problem

Split out of todo 258 (forum-api-contract-hardening) on 2026-07-24 — both findings
are in 258's Recommended Action but were **not** 258 acceptance criteria, and both
are breaking / broad enough to warrant their own change window.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

- **M40** — The forum API ships four list-envelope shapes: cursor
  `{results,next,previous}` (topic/post/notification lists), flat `{results}`
  (`BoardListView`), search `{topics,posts,topics_has_more,posts_has_more,page}`
  (`SearchView`), and the sync custom shape (`SyncView`). **Partly stale as of
  2026-07-24**: PR #473 already added `reply_count`/`view_count`/`last_post_at`
  to the search *topic* item, so of the four originally-named dropped fields only
  `is_pinned` is still missing there. The genuinely-divergent remainder is the
  **search post item** — an entirely separate lightweight shape vs `PostSerializer`
  (`W/api/views.py` search builders + `W/api/serializers.py`). Normalizing is a
  BREAKING response change — coordinate the web mappers
  (`web/src/services/forumMappers.ts`) and document.
- **L20** — `versioning_class = None` appears on **17** views across
  `W/api/{views,notifications,subscriptions,user_search}.py`, with the opt-out
  rationale commented on exactly one (`BoardListView`). Factor the rationale to a
  shared base/mixin (or a single referenced comment) so it is stated once.

## Recommended Action

1. **M40**: decide the target — converge search/sync onto the cursor envelope
   where feasible, and enrich the search *post* item to the `PostSerializer` field
   set (or explicitly document the lightweight search shape as intentional).
   Breaking: update `web/src/services/forumMappers.ts` + a full-suite grep for the
   old keys, and document the contract. `versioning_class = None` today, so a
   documented break is cheap pre-deploy.
2. **L20**: introduce a shared `versioning_class = None` base/mixin carrying the
   rationale comment once; refactor the 17 views to inherit it (mechanical).

## Acceptance Criteria

- [ ] Either a single documented list-envelope contract (search/sync converged
      onto cursor) OR the divergence explicitly documented as intentional; web
      mappers updated + full web/backend suites green
- [ ] The versioning-opt-out rationale is stated once (shared base/mixin), not
      duplicated or absent across the 17 views

## Notes

p3. Deferred from 258 — see
`todos/archive/258-completed-p2-forum-api-contract-hardening.md`.
