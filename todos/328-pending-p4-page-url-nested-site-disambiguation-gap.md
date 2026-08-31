---
status: pending
priority: p4
issue_id: "328"
tags: [backend, wagtail, api]
dependencies: []
---

# `_absolute_page_url()` skips Wagtail's multi-Site disambiguation for a nested-Site topology this project doesn't use today

## Problem

`_absolute_page_url()` (in `apps/blog/api/serializers.py` and
`apps/plant_identification/api/serializers.py`, introduced by todo 308)
calls `page.get_url_parts(request=request)` to get a page's site-relative
path. If a page ever belongs to more than one Wagtail `Site` (e.g. one
site's root page nested under another's), Wagtail disambiguates which
site's root path to slice against via `Site.find_for_request(request)` —
but only inside a branch gated on `isinstance(request, HttpRequest)`
(`wagtail/models/pages.py`, `get_url_parts`). DRF's `Request` wrapper
(what `self.context["request"]` actually is in every call site) does not
subclass `HttpRequest`, so that check silently fails and the branch never
runs — Wagtail falls back to an arbitrary candidate site's root, which can
slice `page_path` against the wrong root for an ambiguous (nested-Site)
page.

**This does not affect this project's production behavior today**: there
is exactly one Wagtail `Site` row configured (or, in the one test that
creates a second, both rows share the *same* `root_page`, which sidesteps
the gap entirely — see Findings). It only matters for a genuinely nested
Wagtail `Site` topology, which this project has never used.

## Findings

- Confirmed via direct read of the installed Wagtail source
  (`wagtail/models/pages.py:1343-1414`, `get_url_parts`): the
  `isinstance(request, HttpRequest)` branch only matters when
  `len(unique_site_ids) > 1` for the SAME page — i.e. the page's
  `url_path` falls under more than one Site's `root_path` simultaneously,
  which requires one Site's root to be a proper ancestor/descendant of
  another's, not merely a second Site sharing the identical root page.
- `python3 -c "from rest_framework.request import Request; from django.http import HttpRequest; issubclass(Request, HttpRequest)"` → `False`, confirmed empirically.
- The underlying raw `HttpRequest` is reachable via DRF's own documented
  `Request._request` attribute (confirmed:
  `venv/.../rest_framework/request.py:160`, `self._request = request`).
- **A fix was attempted and reverted**: unwrapping `request` to `request._request`
  before calling `get_url_parts()` makes the isinstance check pass and
  Wagtail's disambiguation reachable — but this was empirically tested
  (`python manage.py test apps.blog --noinput`, 7 full-suite runs with the
  unwrap vs. 5 without) and found to correlate with a rare, unreproduced
  `Site.DoesNotExist` failure in an unrelated Wagtail-admin-dashboard test
  (`apps/blog/tests/test_admin_render_smoke.py`) on 1 of 7 runs with the
  unwrap, 0 of 5 without. A targeted 2-file reproduction (5/5 runs) could
  not reproduce it in isolation, and the exact causal mechanism (suspected:
  `Site.get_site_root_paths()`'s Django-cache entry, long-TTL and
  process-wide, populated during a `TestCase`-rolled-back Site row, read
  by an unrelated later test) was not conclusively traced. Given the
  narrow, currently-unused topology this fix targets, the risk wasn't
  judged worth it — reverted, documented in the helper's own docstring,
  filed here instead.

## Recommended Action

Only worth pursuing if/when this project adopts a genuinely nested
Wagtail `Site` topology (one Site's root page a descendant of another's).
At that point:

1. Re-attempt the `request._request` unwrap in both `_absolute_page_url()`
   helpers.
2. This time, root-cause the `test_admin_render_smoke.py` flake *before*
   accepting the change — bisect by adding `cache.clear()` at strategic
   points, or use Django's `--debug-sql`/cache instrumentation to see
   exactly which cache read returns the stale `Site` id. Suspect:
   `Site.get_site_root_paths()`'s `SITE_ROOT_PATHS_CACHE_KEY` (Django's
   low-level cache, 3600s TTL, process-wide, not transaction-aware) getting
   populated with a temporary `Site` row's data during a `TestCase` that
   later rolls back — the cached entry would outlive the transaction.
3. Alternatively, sidestep Wagtail's own disambiguation entirely: since
   `_absolute_page_url()` never uses `get_url_parts()`'s `root_url`/`site_id`
   (only `page_path`), it may be possible to determine the *actually
   correct* site for a nested topology by calling
   `Site.find_for_request(request)` directly (this doesn't have the
   isinstance gate — duck-types on request attributes) and passing that
   site's `root_path` explicitly, rather than relying on
   `get_url_parts()`'s internal, gated disambiguation.

## Technical Details

- `apps/blog/api/serializers.py`'s `_absolute_page_url()` — docstring
  documents this gap in place.
- `apps/plant_identification/api/serializers.py`'s `_absolute_page_url()` —
  same.
- `venv/lib/python3.13/site-packages/wagtail/models/pages.py:1343-1414`
- `apps/blog/tests/test_admin_render_smoke.py` — the test that flaked
  during the reverted fix attempt.

## Acceptance Criteria

- [ ] Not actionable until this project has a nested-Site use case —
      revisit then. No AC until scoped against a real requirement.

## Work Log

### 2026-08-31 - Filed

- Surfaced by a `/code-review` pass on todo 308's PR (fix/wagtail-api-absolute-urls),
  which correctly identified the `isinstance(request, HttpRequest)` gate
  as a real gap in the new `_absolute_page_url()` helper. Attempted the
  fix, found it introduced test flakiness under empirical stress-testing,
  reverted it, and filed this todo instead of shipping unresolved risk for
  a topology this project doesn't use.
