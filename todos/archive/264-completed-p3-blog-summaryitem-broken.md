---
status: completed
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

- [x] `/cms/` loads with no exception from `add_blog_summary_items` (remove
      or narrow the `except Exception: pass` once fixed, so a future regression
      is loud, not silent)
- [x] "Blog Posts", "Featured Posts" (when any exist), and "Pending Comments"
      (when any exist) all render on the homepage, covered by a test

## Notes

p3: real but low-impact (admin-UX only, fails safe, not user-facing). Found
opportunistically while fixing the equivalent bug for the forum's own panel
in todo 254 Slice 2 — same root cause (Wagtail's `SummaryItem` API changed
out from under both hand-rolled call sites), unrelated otherwise.

## Work Log

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0237)

- Picked up by automated workflow.
- Mirrored the in-repo precedent (`wagtail_forum.wagtail_hooks.ForumModerationSummaryItem`,
  fixed for the equivalent bug) rather than the upstream `ImagesSummaryItem`
  directly, since blog needs 3 panels sharing one shape — wrote a single
  parameterized `BlogSummaryItem(SummaryItem)` class (`label`, `count`,
  `url_label`, `url`, `icon_name`, `order` as constructor kwargs) instead of
  3 near-identical subclasses.
- Added the shared template `apps/blog/templates/wagtailadmin/home/site_summary_blog.html`
  (Django `APP_DIRS: True` confirmed in settings.py so this is auto-discovered).
- Narrowed `except Exception: pass` to wrap ONLY the 3 DB count queries
  (`return` instead of `pass`, matching the forum precedent's "graceful
  degradation if models aren't ready" framing) — the `BlogSummaryItem`
  construction/append calls are now fully unguarded, so a future regression
  in the SummaryItem API will 500 loudly instead of vanishing silently.
- **Key finding while verifying**: the existing `test_admin_render_smoke.py::test_authenticated_admin_dashboard_renders`
  ALREADY hits `/cms/` as an authenticated superuser and asserts only
  `status_code == 200` — this is exactly why the bug went undetected: the
  broad `except Exception: pass` kept the request itself at 200 even while
  silently swallowing the internal `TypeError`. A bare status-code check
  passes identically before and after this fix, so it is not, by itself,
  evidence of a working panel.
- Added `test_blog_posts_summary_item_renders` and
  `test_featured_and_pending_comment_summary_items_render_when_present` to
  the SAME file (extends `WagtailAdminRenderSmokeTests`, matching its
  `TestCase`-based style) — each drives a real post/comment through the ORM,
  hits `/cms/` as a real superuser via Django's test client, and asserts the
  exact rendered panel text ("1 Blog Posts", "1 Featured Posts", "1 Pending
  Comments") appears in the raw response bytes. Traced by hand that these
  would fail against the pre-fix code: the old `SummaryItem(...)` call raises
  `TypeError` inside the `try`, caught by the old broad `except: pass`, so
  `items` never gets the blog entries and none of that text would appear.
  This mirrors the exact pattern already proven for the sibling forum bug
  (`wagtail_forum/tests/test_admin.py::test_moderation_summary_item_counts_spam_rejected_post`).
- Verification:
  - `pytest apps/blog/tests/test_admin_render_smoke.py -v --tb=short` → 4 passed.
  - `pytest apps/blog/ --tb=short -q` → 191 passed, 0 failed, 7 skipped (no regressions).
  - `grep -n "except Exception" apps/blog/wagtail_hooks.py` → confirmed the
    remaining 2 matches are (a) an unrelated earlier hook function, and (b)
    the narrowed count-only guard — the `BlogSummaryItem` construction itself
    has no surrounding except.

### 2026-07-13 - Completed by completing-todos skill (run 2026-07-13-0237)

- Review: code-review-orchestrator (wagtail-reviewer + cross-cutting-reviewer)
  → 1 medium, 1 low. Repaired the medium; recorded the low.
- Advisor flagged a real risk worth checking: a SEPARATE, pre-existing hook
  (`add_blog_stats_panel`, registered on `construct_homepage_panels`, NOT
  `construct_homepage_summary_items`) unconditionally renders the literal
  words "Featured Posts" on the same `/cms/` page via a hand-rolled `Panel`
  subclass — a different, already-working mechanism, unrelated to the
  SummaryItem bug this todo fixes. Verified empirically (not just reasoned
  about) with a direct `format_html()` check: that panel's HTML is
  `<strong>1</strong> Featured Posts` — the `<strong>` tags break the
  contiguous "1 Featured Posts" substring my tests assert on, so the existing
  assertions are NOT vacuous. wagtail-reviewer independently traced Wagtail's
  `fallback_render_method` dispatch and confirmed the stats panel is a
  different, unaffected mechanism.
- Repair (medium): cross-cutting-reviewer found the `if featured_count > 0`/
  `if pending_comments > 0` guards were untested at the zero-count state
  (`test_blog_posts_summary_item_renders` already has that state but only
  asserted presence, never absence) — deleting either guard would still pass
  the full suite. Added `assertNotIn` on the unique `/blog-admin/featured/`
  and `/blog-admin/comments/` hrefs (not the label text — the stats panel
  above always renders "Featured Posts" regardless of count, which would
  false-fail a text-based absence check). Verified the fix is non-vacuous by
  temporarily mutating `if featured_count > 0:` → `if True:`, confirming the
  test FAILS (0 passed, 1 failed), then restoring the original file and
  re-confirming all 4 tests pass again.
- Recorded (low): not applied — see Known Issues below.
- Re-verification: `pytest apps/blog/tests/test_admin_render_smoke.py -v` →
  4 passed. `pytest apps/blog/ -q` → 191 passed, 0 failed, 7 skipped (no
  regressions).

#### Known issues — accepted at completion

- **[low]** `site_summary_blog.html` renders a static plural noun regardless
  of count ("1 Blog Posts", "1 Featured Posts", "1 Pending Comments"),
  unlike its cited sibling precedent
  (`wagtail_forum/.../site_summary_moderation.html`), which uses
  `{{ count|pluralize }}`. Purely cosmetic per wagtail-reviewer, not a
  functional regression, and not required by this todo's acceptance
  criteria. Not applied — fixing it later also touches
  `test_admin_render_smoke.py`'s hardcoded assertions (noted for whoever
  picks this up).
