---
status: completed
priority: p3
issue_id: "102"
tags: [forum, frontend, ui]
dependencies: []
---

# Add dark mode support to forum components

## Problem

Forum components (`ThreadCard`, `PostCard`, `ImageUploadWidget`, `ThreadListPage`,
`ThreadDetailPage`, etc.) use hardcoded light-mode Tailwind classes (white backgrounds,
gray text) without `dark:` variants. The rest of the app supports dark mode; the forum
is the only section that doesn't.

## Recommended Action

Audit every forum component for light-only classes and add `dark:` counterparts following
the project's Tailwind 4 conventions. Start with the most visible components:
`ThreadCard`, `PostCard`, `CategoryCard`, form inputs.

## Acceptance Criteria

- [x] All forum pages render correctly in system dark mode (no pure-white backgrounds,
      no illegible text).
- [x] No new hardcoded hex colors introduced (use Tailwind tokens with `dark:` variants).

## Work Log

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-1516)

- Added `dark:` Tailwind variants to 9 forum components: ThreadCard, PostCard, CategoryCard, ImageUploadWidget, TipTapEditor, ThreadListPage, ThreadDetailPage, CategoryListPage, SearchPage.
- Key fixes: `bg-white dark:bg-gray-800`, semantic color pairs for text/border/bg states, `dark:prose-invert` on prose regions.
- Code review surfaced 2 critical (missing `dark:prose-invert` on PostCard body + TipTapEditor), 1 high (missing heading color in ThreadDetailPage), 1 medium (hover backgrounds in PostCard) — all repaired before archive.
- Verification: `npm run type-check` clean (0 errors), `npm run test` 150/150 passed; no hardcoded hex colors introduced.
