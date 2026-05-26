---
status: pending
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

- [ ] All forum pages render correctly in system dark mode (no pure-white backgrounds,
      no illegible text).
- [ ] No new hardcoded hex colors introduced (use Tailwind tokens with `dark:` variants).
