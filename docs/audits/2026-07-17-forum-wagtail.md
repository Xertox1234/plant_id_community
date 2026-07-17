# Audit: Forum — Wagtail Integration Correctness

> **Date:** 2026-07-17
> **Trigger:** User-invoked `/audit` after the forum notifications epic work (todo 253
> slices 1–6, PRs #445–#470). Focus: whether the forum package's Wagtail integration
> properly follows current Wagtail documentation (7.4.2). Security explicitly
> out of scope this round (user directive).
> **Domains:** wagtail
> **Baseline:** `manage.py test --noinput`: 689 tests OK (8 skipped) | `manage.py check`: 0 issues
> ⚠ Mid-audit discovery: the authoritative runner is **pytest** (`manage.py test` misses the function-based forum tests, per docs/rules/testing.md); the pre-fix pytest baseline run was invalidated by a concurrent-test-DB collision — close-out relies on the full worktree pytest run below plus the July 11 audit's 906-passed reference.
> **Versions:** Wagtail 7.4.2, Django 6.0.7, DRF 3.17.1
> **Branch at start:** `main` (04bf781)

## Findings

Each finding has a lifecycle: `open` → `fixing` → `verified` or `deferred` or `false-positive`.

**Status key:**

- `open` — Found but not yet addressed
- `fixing` — Work in progress
- `verified` — Fix applied AND confirmed by test/grep/type-check
- `deferred` — Intentionally postponed (must link to todo)
- `false-positive` — Agent was wrong or issue was already fixed

**Research key** (Phase 2.5 verdict, recorded in the `Research` column):

- `confirmed` — current documentation agrees the finding is valid
- `better-fix` — finding is real, but current docs show a cleaner fix (described in the `Verification` column for Phase 3 to use)
- `contradicted ⚠` — current docs say the flagged pattern is fine; may be a false positive — decide at triage
- `—` — research not applicable, or finding predates Phase 2.5

### Critical

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |

### High

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| H1  | `seed_default_forum` attaches ForumIndex under the depth-1 treebeard root (`Page.objects.filter(depth=1)`) instead of the Site's `root_page` (depth 2) — pages land as siblings of Home, outside the routable tree: `page.url`/`full_url` = `None`, `route()` never reaches them, admin "View live"/sitemap broken. Empirically verified against live DB. Wired into `railway.json` preDeployCommand, so fires on first prod deploy. Defeats the July H17 fallback-template fix. | wagtail | wagtail-reviewer (serving/host) | `backend/apps/forum_host/management/commands/seed_default_forum.py:16,21` | confirmed | verified | Site.root_page resolution + mis-parented repair via `Page.move`; tests `test_seed_default_forum_pages_are_routable` + `..._repairs_misparented_index` green (5/5 file); kimi-review clean |

### Medium

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| M1  | Hardcoded `/cms/snippets/wagtail_forum/topic/` admin URL in the forum SearchArea and moderation summary template instead of `reverse()`/`{% url %}` via `SnippetViewSet.get_url_name()` — silently 404s if the admin mount changes or the "reusable" package lands in a host with a different mount. Wagtail's own SearchAreas use `reverse("wagtailimages:index")`. | wagtail | wagtail-reviewer (admin) | `backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py:152`, `templates/wagtail_forum/homepage/site_summary_moderation.html:5` | confirmed | verified | Both sites now `reverse(Topic.snippet_viewset.get_url_name("list"))`; tests pin resolved hrefs (test_admin.py 12/12 green); kimi-review clean |
| M2  | Blog has the same hardcoded-admin-URL anti-pattern M1 was copied from (forum hook docstring says "mirrors the blog's register_blog_search"): 12+ hardcoded `/blog-admin/...` URLs across `apps/blog/wagtail_hooks.py` (SearchArea `/blog-admin/search/`, MenuItem `/blog-admin/settings/`, dashboard buttons, per-page action links). Outside forum scope — found incidentally by Phase 2.5 research. | wagtail | docs-researcher (incidental) | `backend/apps/blog/wagtail_hooks.py:37,128,208-312,348,359` | confirmed | verified | All 11 URLs now `reverse("blog_admin:<name>")` (dead `mark_safe` import dropped, `format_html` with args per rule); new `test_wagtail_hooks_urls.py` renders /cms/ + pages search and pins resolved URLs (2/2 green); kimi-review clean |

### Low

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| L1  | `seed_default_forum` never calls `save_revision().publish()` after `add_child` — pages are `live=True` with zero revisions and `first_published_at=None`; no `page_published` fires. No current receiver depends on it (grep-confirmed), but diverges from the repo's own blog-seed pattern (`create_demo_blog_posts.py:160`). | wagtail | wagtail-reviewer (serving/host) | `backend/apps/forum_host/management/commands/seed_default_forum.py:21,27-33` | confirmed | verified | `save_revision().publish()` after both `add_child` calls; test `test_seed_default_forum_publishes_with_revisions` asserts live + 1 revision + first_published_at; kimi-review clean |
| L2  | `get_forum_image_collection()` docstring claims "idempotently" but is non-atomic check-then-create with no unique constraint on `Collection.name` — two concurrent first callers can create duplicate "Forum Images" collections. Primary seeding moved to deploy-time (todo 247) so the race only remains for hosts that skip the seed command; docstring/behavior mismatch. | wagtail | wagtail-reviewer (admin) | `backend/packages/wagtail_forum/wagtail_forum/collections.py:15-22` | — | verified | Double-checked `select_for_update` on root collection row; deterministic locked-recheck race test `test_get_forum_image_collection_locked_recheck_reuses_existing` (first threaded draft violated the repo's no-`transaction=True` rule — flush wiped migration-seeded root rows in full-suite context; reworked per tests/api/test_topic_detail.py convention); kimi-review clean ×2 |

## Deferred Items

Items marked `deferred` must have a linked todo and rationale.

| ID  | Todo | Rationale |
| --- | ---- | --------- |
| —   | —    | —         |

## Summary

| Severity  | Found | Verified | Deferred | False-positive | Open  |
| --------- | ----- | -------- | -------- | -------------- | ----- |
| Critical  | 0     | 0        | 0        | 0              | 0     |
| High      | 1     | 1        | 0        | 0              | 0     |
| Medium    | 2     | 2        | 0        | 0              | 0     |
| Low       | 2     | 2        | 0        | 0              | 0     |
| **Total** | 5     | 5        | 0        | 0              | **0** |

## Close-out

- Full worktree pytest suite: **1088 passed, 8 skipped, 0 failed** (`manage.py check`: clean).
- Worktree test-run mechanics (for future audits): the venv's `wagtail_forum` is an
  editable install pointing at the MAIN checkout — worktree runs must prepend
  `PYTHONPATH=<worktree>/backend/packages/wagtail_forum` or package edits are
  silently not under test; and never run two pytest sessions concurrently (shared
  `test_plant_community` DB → phantom connection errors).

## Phase 6 — Code Review

`code-review-orchestrator` routed the staged diff to `wagtail-reviewer` +
`cross-cutting-reviewer` (both verified against installed Wagtail 7.4.2 source).
No Critical/High/Medium findings. Deduped results:

- **Low (both reviewers): repair branch skipped revision parity** — a
  pre-audit-seeded forum repaired by `Page.move` kept 0 revisions /
  `first_published_at=None`, inconsistent with the L1 fix's goal. **Fixed:**
  the repair branch now publishes a first revision for the index and any
  pre-existing boards lacking one; repair test asserts revision state for both.
- **Low (cross-cutting): 5 of the converted blog listing-button URL names were
  test-unreachable** (no test rendered the page explorer with a BlogPostPage
  child — a rename would only surface in prod). **Fixed:**
  `test_page_listing_renders_blog_post_buttons_with_resolved_urls` renders the
  explorer with a featured + plain post and asserts all five resolved hrefs.
- **Info (residue, not fixed — outside diff):** `add_blog_stats_panel` still
  hardcodes `/cms/pages/` links (pre-existing; `/cms/` is a documented fixed
  convention in CLAUDE.md, unlike the app-local `/blog-admin/` mount); the
  `Site.DoesNotExist → CommandError` branch has no test (requires deleting the
  migration-seeded default Site).

Both reviewers independently confirmed: `Page.move` + refetch is required-not-
defensive (treebeard leaves the in-memory instance stale), the new
`page_published` emissions from seeding are safe (all repo receivers
isinstance-guard on other types; no workflow assigned to ForumIndex/ForumBoard),
`reverse()` in hooks is lazy-safe (menu/search registries are cached_property,
first accessed at request time), and `snippet_viewset` is set at app-ready via
`SnippetViewSet.on_register()`. kimi-review clean on the Phase 6 repair diff.

## Fix Commits

| Commit | Description |
| ------ | ----------- |
| —      | —           |

## Codification (Phase 8)

Completed after fixes are committed. Each row links to the docs change.

| Finding | Destination | Note |
| ------- | ----------- | ---- |
| —       | `docs/rules/<domain>.md` / `*/docs/patterns/...` / `docs/LEARNINGS.md` / agent | — |
