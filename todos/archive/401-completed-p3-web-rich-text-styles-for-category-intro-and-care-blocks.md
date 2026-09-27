---
status: completed
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

- [x] A category intro with paragraphs, a list and a link renders with
      paragraph spacing, list markers and a visible link style, in both
      `data-mode` themes, checked in a browser at :5174 (2026-09-26, see Work Log)
- [x] `npm run check:classes` passes with the new class in place

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

### 2026-09-26 - Completed (PR #847, P3 sweep)

- Added `.rich-text` to `web/src/index.css`, on the `--gt-*` tokens and
  mirroring `.forum-editor-content`. Applied it to the category intro.
- **Diagnosis care blocks: moot.** `DiagnosisDetailPage.tsx` was deleted in
  #798, and `DiseaseDiagnosePage` renders no HTML, so there is nowhere to
  apply it.
- **Found on the way:** the intro's sanitization tests queried `.prose`,
  which todo 399 removed, so their `toBeNull()` checks had passed vacuously.
  They now query `.rich-text`, with an anchor asserting the container exists.
  Mutation-checked: dropping the class from the component fails
  "sanitizes the CMS welcome copy before rendering it".
- AC 1, browser check (2026-09-26): Playwright against :5174, with local
  Django serving a test intro set in the **local** DB only (restored to `''`
  after). Computed styles with `data-mode="dark"`: `p + p` margin-top 14px;
  `ul` disc, `ol` decimal, both `padding-inline-start: 24px`; `a` underlined,
  `rgb(218, 241, 222)`. With `data-mode="light"`: `a` `rgb(35, 83, 71)`,
  underlined; `ul` disc. Screenshots of both themes showed spacing, bullets,
  numbers and the underlined link.
- AC 2: `npm run check:classes` → "138 files, 5851 class tokens checked
  against 712 built classes". Vitest `CategoryListPage.test.tsx` 32/32.
- Review round 1: bundled `/code-review` found 0 findings.
  code-review-orchestrator found 1 medium and 1 low, neither blocking:
  `StreamFieldRenderer`'s dead `prose` tokens, which the class checker also
  missed, and `.rich-text h4` has no font-size. Both are filed as **todo 450**,
  which found that forum post and blog paragraph lists render with no markers.
