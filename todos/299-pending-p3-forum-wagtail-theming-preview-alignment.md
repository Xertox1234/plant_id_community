---
status: pending
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

- [ ] Decision recorded (Option 1 or 2) in this todo and the package README
- [ ] Both fallback templates extend a shared package base and load every tag
      library they use
- [ ] `{% wagtailuserbar %}` renders on both fallback pages for an
      authenticated editor (test-pinned)
- [ ] Preview convention decided and documented; if Option 2, the SPA preview
      route exists and a moderator can preview a draft post end to end
- [ ] `test_page_serving.py` and the full forum package suite green

## Work Log

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
