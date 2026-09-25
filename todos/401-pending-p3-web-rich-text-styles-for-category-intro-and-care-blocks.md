---
status: pending
priority: p3
issue_id: "401"
tags: [web, tailwind, design-system]
dependencies: []
---

# Style the category intro HTML (and diagnosis care blocks): `prose` never compiled

## Problem

Todo 399's class check found `prose prose-sm` on the forum category intro
(`web/src/pages/forum/CategoryListPage.tsx`, the `dangerouslySetInnerHTML` div)
and `prose prose-green` on the diagnosis care instructions
(`web/src/pages/diagnosis/DiagnosisDetailPage.tsx`). Neither was ever styled:
`@tailwindcss/typography` is not installed and `index.css` defines no `.prose`,
so the built CSS has only `.max-w-prose`. The rendered HTML (paragraphs,
lists, links, headings) gets Tailwind's preflight reset: no paragraph spacing
and no list bullets.

Todo 399 removed the dead tokens, which changes nothing on screen. The
styling they were meant to provide is still missing.

## Recommended Action

Decide how rich text is styled across the web app. Either:

- add a small hand-written rich-text class in `index.css` on the `--gt-*`
  tokens, like `.forum-editor-content` (which already styles TipTap output);
- or install `@tailwindcss/typography` and theme it to Canopy.

Then apply it to the category intro. The diagnosis page is unrouted (todo 400
decides whether it lives), so apply it there only if it is kept.

## Acceptance Criteria

- [ ] A category intro with paragraphs, a list and a link renders with
      paragraph spacing, list markers and a visible link style, in both
      `data-mode` themes, checked in a browser at :5174
- [ ] `npm run check:classes` passes with the new class in place

## Work Log

### 2026-09-23 - Filed from todo 399

Found by the new CI class check (review round 1). Not fixed there because
it is a design decision, not a dead-class removal.

### 2026-09-24 - Owner decision: hand-written rich-text class (gate removed)

Decided by the owner: add a small hand-written `.rich-text` class in
`web/src/index.css` on the `--gt-*` tokens, like `.forum-editor-content`
already does. Do NOT install `@tailwindcss/typography`. Apply it to the
category intro (`CategoryListPage.tsx`) and the diagnosis care blocks
(`DiagnosisDetailPage.tsx`). Ready for a sweep.
