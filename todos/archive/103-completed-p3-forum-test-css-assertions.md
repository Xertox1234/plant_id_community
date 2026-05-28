---
status: completed
priority: p3
issue_id: "103"
tags: [forum, testing, quality]
dependencies: []
---

# Replace CSS class assertions with behaviour assertions in forum tests

## Problem

Several tests in `ThreadDetailPage.test.tsx` and related forum test files assert on
specific Tailwind class names (e.g., `expect(el).toHaveClass('bg-green-500')`). These
tests break whenever a class is renamed for styling reasons and never caught bugs caused
by logic changes — they test CSS output, not behaviour.

## Recommended Action

Replace class-based assertions with behaviour-based ones:

- Visible/hidden state → `toBeVisible()` / not `toBeInTheDocument()`
- Disabled state → `toBeDisabled()`
- Active/selected state → `aria-selected`, `aria-current`, or role queries

## Acceptance Criteria

- [x] No forum test file asserts on a Tailwind class name directly.
- [x] Each replaced assertion verifies observable user-facing behaviour instead.

## Work Log

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-1516)

- Replaced 3 CSS class assertions across 2 files with behaviour assertions:
  - CategoryCard: `toHaveClass('hover:shadow-lg')` → `within(link).getByRole('heading')` verifying heading is inside the clickable link.
  - ImageUploadWidget: 2 drag-highlight tests deleted — code review confirmed they passed trivially (plain Event objects bypass React synthetic handlers; `aria-disabled` never changes). The "uploads image when dropped" test at line 409 already covers the real behavioral contract.
- Verification: `npm run type-check` clean, 148/148 tests pass (2 deleted trivially-passing tests).
- Code review: 2 high findings repaired (trivially-passing drag tests, duplicate CategoryCard assertion).
