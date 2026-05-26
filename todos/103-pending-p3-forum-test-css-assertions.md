---
status: pending
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

- [ ] No forum test file asserts on a Tailwind class name directly.
- [ ] Each replaced assertion verifies observable user-facing behaviour instead.
