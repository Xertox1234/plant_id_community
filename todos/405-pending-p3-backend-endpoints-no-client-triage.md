---
status: pending
priority: p3
issue_id: "405"
tags: [backend, dead-code, product, api]
dependencies: []
source_review: "docs/audits/2026-09-23-web-dead-code.md"
source_finding: "L13"
---

# Backend endpoints no client calls: decide to wire up, keep for mobile, or remove

## Problem

The 2026-09-23 web dead-code audit mapped every backend route against both
clients. It found whole API families that **neither** web nor mobile calls. Each
is either an unfinished feature (wire it up) or dead code (remove it, along with
its tests and maintenance cost). That is a product decision per family, not a
mechanical fix.

## Findings

The route walk used `django.urls.resolve()` plus a URLconf walk, not grep.
Mobile-only endpoints were excluded as expected.

- **Forum AI:** `GET forum/topics/<id>/summary/` (premium) and
  `GET forum/topics/similar/` (503 unless `FORUM_VECTOR_SEARCH_ENABLED`).
  Backend-complete, with no UI anywhere.
- **Blog v2:** `blog-posts/featured|recent|by_category|search_suggestions|<pk>/related`,
  `blog-index/*`, `blog-categories/*`, `blog-authors/*`, `series/*`. The web
  uses list, detail, `popular/` and `categories/` only.
- **Blog v1 (DRF):** almost all of it, including `newsletter/*` and `stats/`.
- **Plant CMS v2:** `plant-species/*`, `plant-categories/*`, `care-guides/*`,
  `plants/*`, `plant-index/*`.
- **Plant ID v1:**
  - `species/*` and `results/*` (vote, accept, add_to_collection,
    regenerate-care);
  - `plants/<pk>/` edits;
  - `disease-results/*`, `disease-database/*`;
  - `saved-diagnoses/*`, `saved-care-instructions/*`, `treatment-attempts/*`;
  - `search/*`.
- **Users v1:** `me/searches/*`, `me/dashboard-stats/`,
  `me/push-notifications/*`, `me/care-reminders/*`, `me/onboarding/*`,
  `me/email-preferences/*`.
- **Garden and calendar:** all of `/api/v1/garden/*` and
  `/api/v1/calendar/api/*`. Mobile garden data lives in Firestore.
- **Legacy unversioned `/api/` mount** (`plant_community_backend/urls.py`,
  "TODO: Remove after 2025-07-01"). Its only web user was `diagnosisService`,
  deleted by this audit (H1). Whether other clients or tests use it is a
  hypothesis, not verified.
- **Dead preview mode (L14):** `BlogPostPage.preview_modes` offers
  "Mobile (Flutter)", but wagtail-headless-preview 0.9 calls
  `get_client_root_url(request)` without the mode. So that option opens the web
  preview and the `plantid://` branch is unreachable.

## Recommended Action

For each family above, record one decision in the Work Log, with the reason:

- **wire up:** file a feature todo;
- **mobile roadmap:** keep, and say which planned screen will use it;
- **remove:** delete the routes, views, serializers and tests in a PR.

Start with the legacy `/api/` mount: grep tests, mobile and e2e for `/api/`
paths without `v1`/`v2` before removing it.

## Technical Details

- Route inventory method: `django.urls.get_resolver()` walk, with each web and
  mobile call resolved. The audit manifest has the tables.
- `backend/plant_community_backend/urls.py` (the legacy mount, routers)
- `backend/apps/blog/models.py` (`BlogPostPage.preview_modes`,
  `get_client_root_url`)

## Acceptance Criteria

- [ ] Every family listed above has a recorded decision (wire up, mobile
      roadmap, or remove) with a reason.
- [ ] The legacy unversioned `/api/` mount is removed, or kept with evidence
      of a live caller.
- [ ] The "Mobile (Flutter)" preview mode is either made to work or removed
      from `preview_modes`.

## Work Log

### 2026-09-23 - Filed from the web dead-code audit (L13, L14)

This is a product triage, so it could not be fixed inside a web dead-code PR.
