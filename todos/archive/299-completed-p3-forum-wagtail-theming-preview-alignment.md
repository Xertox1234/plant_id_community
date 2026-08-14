---
status: completed
priority: p3
issue_id: "299"
tags: [forum, wagtail, theming, templates]
dependencies: []
---

# Forum Wagtail theming + preview alignment

## Problem

The forum's server-rendered surface diverges from Wagtail conventions in two
deliberate-but-unrevisited ways: the two fallback page templates are bare
standalone documents (no `{% extends %}`, no shared base, and `forum_board.html`
loads no Wagtail tag library at all), and forum post preview uses server-rendered
`PreviewableMixin` while the blog uses `HeadlessPreviewMixin` — two preview
conventions in one repo. Each needs a decision: theme/align, or affirm and pin
the current posture.

## Findings

- `backend/packages/wagtail_forum/templates/wagtail_forum/forum_index.html:1` —
  standalone `<!DOCTYPE html>`, no `{% extends %}`; does load `wagtailcore_tags`
  and renders `{{ page.intro|richtext }}`. Header comment records this as the
  deliberate minimal fallback (audit 2026-07-11 H17): the SPA is the real UI.
- `backend/packages/wagtail_forum/templates/wagtail_forum/forum_board.html:1` —
  standalone document, loads **no** Wagtail tag library; renders
  `{{ page.description }}` plain and topic titles as unlinked `<li>` text (the
  package cannot know the host SPA's URL scheme).
- Neither front-end fallback includes `{% wagtailuserbar %}` — an editor landing
  on "View live" gets no edit affordance. (The admin-side
  `admin/post_preview.html` *does* include it.)
- `backend/packages/wagtail_forum/wagtail_forum/models/posts.py:115-121` —
  `Post.get_preview_template()` → `wagtail_forum/admin/post_preview.html` via
  Wagtail's `PreviewableMixin`.
- `apps/blog/models.py` uses `HeadlessPreviewMixin`; `wagtail_headless_preview`
  is installed (`plant_community_backend/settings.py:156`) with
  `HEADLESS_PREVIEW_CLIENT_URLS` configured (`settings.py:434-440`).
- Web SPA has `web/src/pages/BlogPreview.tsx` but no forum preview route.
- Discovery source: Wagtail-compliance survey session 2026-08-13 (Explore agent
  sweep of `packages/wagtail_forum/` + verification against settings and web).

## Proposed Solutions

### Option 1: Minimal theming + pin the posture (Recommended)

- **Implementation:** Add a tiny package base template
  (`wagtail_forum/base.html`) with title/content blocks and
  `{% wagtailuserbar %}`; make both fallback templates extend it;
  load `wagtailcore_tags` in `forum_board.html`. Keep the pages minimal,
  unstyled, and host-overridable. Keep `PreviewableMixin` for `Post`
  (server preview works for moderators with zero SPA work) and document the
  divergence from the blog's headless preview as deliberate in the package
  README.
- **Pros:** Small; keeps the package host-agnostic; restores the editor userbar;
  no web work.
- **Cons:** Preview-convention divergence remains (documented rather than
  removed).
- **Effort:** 1–2 hours
- **Risk:** Low — fallback pages are crawler/admin-only surfaces.

### Option 2: Full headless alignment

- **Implementation:** Switch `Post` preview to `HeadlessPreviewMixin`; add a
  forum preview route to the web SPA (mirroring `BlogPreview.tsx`) rendering
  draft content through the existing forum components; theme the fallback pages
  as in Option 1 (they must stay — H17).
- **Pros:** One preview convention repo-wide; moderators preview in the real UI.
- **Cons:** Cross-stack (backend + web route + token handling); the package
  would grow a `wagtail_headless_preview` dependency or need a host hook;
  `wagtail_headless_preview` targets Pages — its snippet support needs
  verification before committing.
- **Effort:** 1–2 days
- **Risk:** Medium — headless preview of a *snippet* is not the library's
  documented core case.

## Recommended Action

1. Create `packages/wagtail_forum/templates/wagtail_forum/base.html`: minimal
   skeleton, `{% load wagtailuserbar %}`, blocks for title and content,
   `{% wagtailuserbar %}` before `</body>`.
2. Convert `forum_index.html` and `forum_board.html` to extend it; add
   `{% load wagtailcore_tags %}` to the board template.
3. Extend `packages/wagtail_forum/wagtail_forum/tests/test_page_serving.py`:
   both pages still 200, and the userbar renders for a logged-in editor.
4. Add a short "Previews" note to the package README recording the
   `PreviewableMixin`-not-headless decision (or, if Option 2 is chosen, do the
   alignment instead).
5. Run the full forum package suite.

## Technical Details

- Templates: `backend/packages/wagtail_forum/templates/wagtail_forum/`
- Preview: `models/posts.py:115-121`, `templates/wagtail_forum/admin/post_preview.html`
- Headless preview config: `plant_community_backend/settings.py:156,434-440`
- Constraint: `ForumBoard.description` stays plain text by design — see the
  field comment in `models/boards.py` (added 2026-08-13); do not "fix" it to
  rich text while theming the board template.
- Patterns: `backend/docs/patterns/domain/wagtail.md`, `domain/forum.md`

## Acceptance Criteria

- [x] Decision recorded (Option 1 or 2) in this todo and the package README
- [x] Both fallback templates extend a shared package base and load every tag
      library they use
- [x] `{% wagtailuserbar %}` renders on both fallback pages for an
      authenticated editor (test-pinned)
- [x] Preview convention decided and documented; if Option 2, the SPA preview
      route exists and a moderator can preview a draft post end to end
- [x] `test_page_serving.py` and the full forum package suite green

## Work Log

### 2026-08-14 - Completed by completing-todos skill (run 2026-08-14-0021)

- Verification: all 5 acceptance criteria passed (page-serving suite 6 passed;
  full forum package suite 478 passed on a clean run).
- Review: 5 findings total, 1 blocking — addressed via repair (base.html
  staged, assertion strengthened, parametrize ids); 2 lows accepted as known
  issues, recorded above.

### 2026-08-14 - Started by completing-todos skill (run 2026-08-14-0021)

- Picked up by automated workflow. User selected **Option 1** (minimal theming
  + pin the posture). Note: implementation of the branch-independent files
  (templates, tests) began while PR #533 — which introduced this todo file —
  finished CI; the in-progress rename happened right after its merge, so the
  skill's step order was inverted for mechanical reasons only.

### 2026-08-14 - Implemented (Option 1)

- New `templates/wagtail_forum/base.html`: shared skeleton (head, `<main>`,
  `<h1>`), `{% load wagtailuserbar %}` + `{% wagtailuserbar %}` before
  `</body>`, H17 rationale comment. `forum_index.html` and `forum_board.html`
  now `{% extends %}` it and keep only their `{% block content %}` bodies;
  index still loads `wagtailcore_tags` for `|richtext`, board needs no tag
  library (its content block uses none).
- Wagtail 7.4's userbar tag returns `""` when the request lacks a `.user` or
  the user lacks `wagtailadmin.access_admin` (verified in
  `venv/.../wagtail/admin/templatetags/wagtailuserbar.py`), so the two
  pre-existing bare-`RequestFactory` serve tests keep passing unchanged.
- `test_page_serving.py`: +4 tests — userbar present for a superuser and
  absent for `AnonymousUser`, parametrized over both page types; asserts the
  stable `wagtail-userbar` markup id.
- README: "Creating the page tree" now describes the shared base + userbar +
  override points; new "Previews" section (in TOC) pins the
  `PreviewableMixin`-not-headless decision and its three reasons.
- Verification: `pytest packages/wagtail_forum/wagtail_forum/tests/test_page_serving.py --create-db -q`
  → `6 passed`. (An earlier full-suite run reported `478 passed` but is
  discounted — a stash/branch switch mutated the working tree mid-run; clean
  re-run recorded below.)
- Full-suite verification (clean re-run on the settled `todo/299-…` branch):
  `pytest packages/wagtail_forum --create-db -q` → `478 passed`, exit 0.

### 2026-08-14 - Code review (wagtail-reviewer + cross-cutting-reviewer)

- 5 findings: 1 critical, 1 medium, 3 low. Repaired:
  - [critical] `base.html` was still untracked while both page templates
    already `{% extends %}` it (a merge without it = TemplateDoesNotExist,
    the exact H17 regression) → `git add`ed; `git status` shows `A`.
  - [medium] userbar assertion pinned only the wrapper shell, which renders
    even when the page can't be resolved → now also asserts
    `reverse("wagtailadmin_pages:edit", args=[page.pk])` in the HTML.
  - [low] opaque parametrize ids → `ids=["index", "board"]`.
  - Re-verified after repair: `pytest …/test_page_serving.py --create-db -q`
    → `6 passed`.
- Known issues (accepted, low, not acted on):
  - `_tree()` parents pages under `Page.objects.get(id=1)` (treebeard root,
    unroutable) — pre-existing fixture style shared across the package's
    direct-`serve()` tests; fine while nothing exercises URL routing.
    The reviewer's proposed write-time trigger was deliberately NOT captured:
    it would fire on the package's own established, deliberate test pattern.
  - `test_userbar_absent_for_anonymous_user` is satisfied by Wagtail's own
    permission gate; it counts only as the paired negative case — the
    admin-presence test is the one pinning this diff's change.

### 2026-08-13 - Filed

- Filed from the Wagtail-compliance survey. The same session shipped the quick
  wins separately (README `modelcluster` correction, Wagtail API v2 posture
  note, `ForumBoard.description` plain-text-by-design comment); these two
  items were out of that PR's scope.

## Notes

- p3: no user-facing bug — the fallback pages exist only so "View live",
  sitemaps, and crawlers don't 500; members use the React SPA.
- Related rejected change: converting `ForumBoard.description` to
  `RichTextField` (contract churn across web + Flutter for a card blurb;
  revisit only with a real product need).
