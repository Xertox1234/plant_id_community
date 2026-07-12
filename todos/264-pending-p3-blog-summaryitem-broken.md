---
status: pending
priority: p3
issue_id: "264"
tags: [blog, wagtail, admin]
dependencies: []
---

# Blog's homepage summary panel silently 500s on every load (broken SummaryItem API)

## Problem

`apps/blog/wagtail_hooks.py::add_blog_summary_items` (the "Blog Posts" /
"Featured Posts" / "Pending Comments" homepage panel) raises
`TypeError: SummaryItem.__init__() got an unexpected keyword argument
'icon_name'` on every `/cms/` load, on Wagtail 7.4.2. The whole function is
wrapped in `except Exception: pass`, so this is completely silent — staff
never see the panel and never see an error. Nobody has noticed because no
test exercises `/cms/` with this hook enabled.

## Findings

- Discovered as a side effect of todo 254 Slice 2 (forum moderation-queue
  homepage panel): copying the same positional-args `SummaryItem(label,
  count, url_label, url, icon_name=..., order=...)` pattern from
  `apps/blog/wagtail_hooks.py:168-204` failed identically for the forum's
  own new panel, caught by a real `/cms/` integration test
  (`backend/packages/wagtail_forum/wagtail_forum/tests/test_admin.py::test_moderation_summary_item_counts_spam_rejected_post`).
- On the installed Wagtail version, `wagtail.admin.site_summary.SummaryItem`
  is a `Component` subclass: `__init__(self, request)` only — no `label`,
  `count`, `url`, or `icon_name` args. Rendering is template-driven
  (`get_context_data` + `template_name`), not constructor args. Confirmed via
  the in-tree precedent `wagtail.images.wagtail_hooks.ImagesSummaryItem`
  (`venv/lib/python3.13/site-packages/wagtail/images/wagtail_hooks.py:125-147`).
- `apps/blog/wagtail_hooks.py:168-204` (`add_blog_summary_items`) still uses
  the old positional form for all 3 of its panels: "Blog Posts", "Featured
  Posts", "Pending Comments". All 3 are currently broken, not just Pending
  Comments.
- Not a data-loss or security bug — purely a missing admin-UI affordance.
  `except Exception: pass` means it fails safe (no 500 to the user), but
  also means it will never surface itself; it needs to be found and fixed
  deliberately.

## Recommended Action

1. Rewrite `add_blog_summary_items` using the `SummaryItem` subclass pattern
   (see `backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py`'s
   `ForumModerationSummaryItem` for the in-repo precedent this todo mirrors,
   and `wagtail.images.wagtail_hooks.ImagesSummaryItem` for the upstream one):
   one subclass per panel (or one parameterized subclass for all 3), each
   with its own `template_name` + `get_context_data`.
2. Add 3 small templates (or 1 shared, parameterized one) under
   `apps/blog/templates/wagtailadmin/home/` or similar, following
   `wagtail/images/templates/wagtailimages/homepage/site_summary_images.html`'s
   shape.
3. Add a `/cms/` integration test asserting all 3 panels actually render —
   this is what would have caught the break originally.

## Technical Details

- `apps/blog/wagtail_hooks.py:161-207` (`add_blog_summary_items`).
- `venv/lib/python3.13/site-packages/wagtail/admin/site_summary.py` — base
  `SummaryItem`/`SiteSummaryPanel` classes.
- `venv/lib/python3.13/site-packages/wagtail/images/wagtail_hooks.py:125-147`
  — `ImagesSummaryItem`, the pattern to copy.

## Acceptance Criteria

- [ ] `/cms/` loads with no exception from `add_blog_summary_items` (remove
      or narrow the `except Exception: pass` once fixed, so a future regression
      is loud, not silent)
- [ ] "Blog Posts", "Featured Posts" (when any exist), and "Pending Comments"
      (when any exist) all render on the homepage, covered by a test

## Notes

p3: real but low-impact (admin-UX only, fails safe, not user-facing). Found
opportunistically while fixing the equivalent bug for the forum's own panel
in todo 254 Slice 2 — same root cause (Wagtail's `SummaryItem` API changed
out from under both hand-rolled call sites), unrelated otherwise.
