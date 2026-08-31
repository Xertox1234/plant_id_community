---
status: pending
priority: p4
issue_id: "327"
tags: [backend, wagtail, api]
dependencies: []
---

# Wagtail's stock `meta.html_url`/`meta.detail_url` fields still resolve via the Site record, not the request

## Problem

Every page/image API response in this project includes a `meta` object with
`detail_url` and (for pages) `html_url`, via Wagtail's own stock
`DetailUrlField`/`PageHtmlUrlField` (`wagtail/api/v2/serializers.py`) —
these are framework-level fields, not code this project wrote, and todo
308's fix doesn't touch them. `PageHtmlUrlField.to_representation` returns
`page.full_url` — `Page.get_full_url()` called via a model **property**
(`full_url = property(get_full_url)`), which can't accept a `request`
argument at all, so it *always* resolves via `get_url_parts(request=None)` →
Wagtail's `Site.get_site_root_paths()` → the same "no Site row configured
for the real domain → falls back to localhost:80" mechanism todo 308 fixed
everywhere else.

## Findings

- `wagtail/api/v2/serializers.py:56-67` — `PageHtmlUrlField.to_representation`
  returns `page.full_url`.
- `wagtail/models/pages.py` — `full_url = property(get_full_url)`; `get_full_url`
  (distinct from the `get_url`/`get_url_parts` this project's own code
  builds on) always calls `get_url_parts(request=None)` and prepends
  `root_url` unconditionally (never resolves to a plain relative path,
  unlike `get_url()`).
- `DetailUrlField` (`serializers.py:29-50`) — resolves via
  `get_object_detail_url(router, request, model, pk)` → `get_full_url(request, url_path)`
  (`wagtail.api.v2.utils`), the exact mechanism todo 308 replaced
  project-wide — but this one is invoked by Wagtail's OWN router
  internals, not this project's serializer code, so todo 308's fix
  (swapping call sites in `apps/blog/api/serializers.py` and
  `apps/plant_identification/api/serializers.py`) never touched it.
- **Currently inert in the web client**: `web/src/types/blog.ts:224-225`
  types `detail_url`/`html_url` as part of `meta`, but grepped the whole
  `web/src` tree for any actual read of either field beyond the type
  declaration and a test fixture (`web/src/tests/utils.tsx:54-55`) —
  none found. No component renders or relies on them today.
- Discovered by the `/code-review` pass on todo 308's PR, which flagged
  that this file's own docstring/commit-message claims ("every URL in this
  API now uses request-derived resolution") are an overclaim while these
  two stock fields remain unfixed.

## Recommended Action

Given `detail_url`/`html_url` are currently unused by any client, this is
p4 (low urgency) — but worth fixing eventually since it's the same
class of production bug as todo 308, just via Wagtail's own field classes
rather than this project's serializers. Two options:

1. **Override at the base-serializer level**: define a shared mixin (or
   subclass `PageSerializer`/`BaseSerializer` project-wide) that overrides
   `html_url`/`detail_url` to build from `request.build_absolute_uri()`
   instead of the stock fields. Fixes it everywhere in one place, but is a
   broader, more invasive change than a per-call-site swap.
2. **Leave it, documented**: since nothing consumes these fields today, the
   risk is latent, not live. Revisit if/when a client starts reading
   `meta.html_url`/`meta.detail_url`.

Given the field is inert today, recommend confirming with product/frontend
whether either field is actually needed before investing in option 1.

## Technical Details

- `venv/lib/python3.13/site-packages/wagtail/api/v2/serializers.py:29-67`
- `venv/lib/python3.13/site-packages/wagtail/models/pages.py` (`get_full_url`,
  `full_url` property)
- `web/src/types/blog.ts:224-225`, `web/src/tests/utils.tsx:54-55`

## Acceptance Criteria

- [ ] Confirmed with a live probe whether `meta.html_url`/`meta.detail_url`
      resolve to the real domain or `localhost` in production today.
- [ ] Decision recorded: fix via shared mixin, or defer as documented/inert.
- [ ] If fixed: no regression in `apps.blog`/`apps.plant_identification`
      test suites, and web types/consumers (if any exist by then) updated.

## Work Log

### 2026-08-31 - Filed

- Surfaced by a `/code-review` pass on todo 308's PR (fix/wagtail-api-absolute-urls).
  Verified via direct read of the installed Wagtail package source and a
  repo-wide grep confirming zero live consumers of either field today.
  Out of scope for todo 308 — filed separately, p4 given zero current
  client impact.
