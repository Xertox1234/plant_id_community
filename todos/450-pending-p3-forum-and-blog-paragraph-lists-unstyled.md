---
status: pending
priority: p3
issue_id: "450"
tags: [web, tailwind, design-system, forum, blog]
dependencies: []
source_review: "todos/archive/401-completed-p3-web-rich-text-styles-for-category-intro-and-care-blocks.md"
triage: ready
triaged: 2026-09-28
owner_decision: "AC2 means only the typography-plugin tokens (prose, prose-*); max-w-prose is fine (2026-09-28)"
---

# Forum post and blog paragraphs render lists with no markers; StreamFieldRenderer keeps dead `prose` tokens

## Problem

Found by the todo 401 review (code-review-orchestrator, round 1, rated
medium). `web/src/components/StreamFieldRenderer.tsx` wraps the `inline`
variant (forum posts, edit history) in `prose prose-lg max-w-none`. Those
classes were never compiled, because `@tailwindcss/typography` is not
installed. So:

- a `paragraph` block's HTML, rendered by `SafeHTML` with only
  `mb-4 leading-relaxed text-ink-2`, gets Tailwind's preflight reset. A
  bulleted or numbered list typed in the TipTap composer shows markers
  while it is being written, and **none** once it is posted. Blog article
  paragraphs (`variant="article"`) have the same gap;
- `npm run check:classes` did not flag the tokens. It appears to skip
  string literals inside a ternary. That is a checker gap, not a pass.

## Recommended Action

1. Apply the `.rich-text` class from todo 401 (`web/src/index.css`) to the
   paragraph `SafeHTML` in `StreamFieldRenderer`. Check that it does not
   fight the mention highlight, quote, and article `text-body-lg` sizing.
2. Remove the dead `prose prose-lg max-w-none` wrapper tokens.
3. Make `scripts/check-tailwind-classes.mjs` check both string branches of a
   conditional, and add a fixture that fails on
   `cond ? 'real' : 'never-compiled'`.
4. Optional, raised in the same review as low: `.rich-text h4` has no
   `font-size`.

## Acceptance Criteria

- [ ] A forum post and a blog paragraph containing a bulleted and a numbered
      list render their markers, checked in a browser at :5174 in both
      `data-mode` themes
- [ ] No `prose` token remains in `web/src`, and `npm run check:classes`
      fails on a planted never-compiled class inside a ternary

## Work Log

### 2026-09-26 - Filed from the todo 401 review (PR #847)
