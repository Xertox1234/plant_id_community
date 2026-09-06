---
status: pending
priority: p2
issue_id: "363"
tags: [dependencies, wagtail, django]
dependencies: []
---

# Assess and execute Wagtail 7.4.3 → 8.0

## Problem

PR #695 put the backend on Django 6.1.1 while leaving Wagtail at 7.4.3. Wagtail
7.4.3 declares `Django>=5.2` with **no upper bound**, so it installs and runs — but
its trove classifiers stop at `Framework :: Django :: 6.0`. The pairing is therefore
untested upstream. Wagtail 8.0 is the first release classifying Django 6.1.

## Findings

- `wagtail==7.4.3` (`backend/requirements.txt:197`); Wagtail 8.0 classifies 5.2, 6.0
  **and 6.1** (PyPI `requires_dist`/classifiers, checked 2026-09-06).
- The full suite is green on the 7.4.3 × 6.1.1 pairing (2273 passed, 8 skipped),
  including the forum package's 36-migration surface, and CI is 17/17.
- The only Django-6.1-induced behaviour change found was a query-count *reduction*
  in our own serializer path (a redundant PK refetch in `get_opening_post_id`) —
  nothing inside Wagtail internals broke.
- A page-EDIT render smoke test was added in #695
  (`apps/blog/tests/test_admin_render_smoke.py::test_page_edit_view_renders_the_form`)
  specifically to cover the admin form surface for this pairing. It passes.

## Recommended Action

1. Read the Wagtail 8.0 release notes' upgrade considerations in full.
2. Bump `wagtail` to 8.0 and run the full suite plus `manage.py check`.
3. Work through the 6.4–7.3 deprecation removals that 8.0 enforces, in particular
   the ones this codebase plausibly uses:
   - `construct_wagtail_userbar` hook now takes a third `page` argument
   - telepath moves `wagtail.telepath` → `wagtail.admin.telepath`
   - `WAGTAILSEARCH_BACKENDS` `INDEX` option → `INDEX_PREFIX`
   - custom listing views must supply a `breadcrumbs_items` context variable
   - custom viewset permission policies must register via `register_permission_policy()`
   - `SnippetChooserViewSet.widget_class` returns a class, not an instance
   - `Page._get_site_root_paths()` parameter renamed `request` → `cache_object`
   - AVIF/WebP no longer auto-convert to PNG — configure conversions explicitly
4. Expect three **new** dependencies: `django-ninja`, `pydantic`, `swapper`.
5. Re-run the R2 rendition path (`USE_R2`) given the AVIF/WebP conversion change.

## Technical Details

- `backend/packages/wagtail_forum/` is the highest-risk consumer: 36 migrations,
  custom admin views (`admin_views.py`), custom viewsets, custom permission policies.
- `django-treebeard` must stay `<6.0` — both Wagtail 7.4.3 and 8.0 cap it there, so
  do **not** take `django-treebeard` 7.0.1 as part of this.
- `djangorestframework` is already at 3.18.0 (#695), which is Wagtail 8.0's floor.

## Acceptance Criteria

- [ ] `wagtail==8.0` in `backend/requirements.txt`, `pip check` clean
- [ ] Full backend suite green, CI green
- [ ] `/cms/` login, dashboard, explorer listing and page-edit smoke tests all pass
- [ ] Forum admin views and the `USE_R2` rendition path manually exercised once
- [ ] Any new deprecation warnings triaged, not merely observed

## Work Log

### 2026-09-06 - Filed

- Deferred deliberately from PR #695 (Django 6.1.1 upgrade) so the Django bump could
  land on a green, reviewable diff. Raised by the #695 code review as the one
  remaining untested-upstream pairing.

## Notes

p2, not p1: the pairing is empirically green and prod is unaffected today. But it
is the last unsupported-by-classifier dependency in the stack, and Django 6.2 LTS
(April 2027) will need Wagtail 8.x regardless — so this is on the critical path to
the next LTS, not optional.
