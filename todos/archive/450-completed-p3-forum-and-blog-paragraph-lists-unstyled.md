---
status: completed
priority: p3
issue_id: "450"
tags: [web, tailwind, design-system, forum, blog]
dependencies: []
source_review: "todos/archive/401-completed-p3-web-rich-text-styles-for-category-intro-and-care-blocks.md"
triage: ready
triaged: 2026-10-10
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

- [x] A forum post and a blog paragraph containing a bulleted and a numbered
      list render their markers, checked in a browser at :5174 in both
      `data-mode` themes
- [x] No `prose` token remains in `web/src`, and `npm run check:classes`
      fails on a planted never-compiled class inside a ternary

## Work Log

### 2026-09-26 - Filed from the todo 401 review (PR #847)

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- `StreamFieldRenderer` paragraph blocks (forum posts and blog articles) now carry `.rich-text`, which restores list markers, paragraph spacing and link styling; the dead `prose prose-lg max-w-none` inline wrapper is gone (the inline variant has no wrapper class).
- `.rich-text` already sets the ink-2 colour and relaxed leading and no font size, so the article `text-body-lg` still applies; the mention span (`text-primary`) is not a link and is untouched; quote blocks are rendered separately. Added `.rich-text h4 { font-size: 1rem }` (optional item 4).
- `scripts/check-tailwind-classes.mjs` checks the branches of one conditional / `||` / `??` together: when one branch is a class list (all built classes, one utility-shaped), every branch's tokens are checked as classes. Run against main's `StreamFieldRenderer`, it now flags `prose`, `prose-lg` and `max-w-none`.
- Fixtures added in `src/tests/checkTailwindClasses.test.ts` (ternary in a constant fails; plain-word conditionals stay prose) and `StreamFieldRenderer.test.tsx` (both variants wrap lists in `.rich-text`, no `prose*` class).

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `node .sweep-evidence/g2/browser-lists.mjs` — evidence `.sweep-evidence/g2/450-ac0.txt` (not committed), last lines:

  ```text
  PASS forum post [data-mode=light] {"dataMode":"light","ul":{"listStyleType":"disc","paddingLeft":"24px","liDisplay":"list-item"},"ol":{"listStyleType":"decimal","paddingLeft":"24px","liDisplay":"list-item"},"liColor":"rgb(53, 89, 75)","proseClasses":[]} screenshot=450-forum-post-light.png
  PASS blog paragraph [data-mode=light] {"dataMode":"light","ul":{"listStyleType":"disc","paddingLeft":"24px","liDisplay":"list-item"},"ol":{"listStyleType":"decimal","paddingLeft":"24px","liDisplay":"list-item"},"liColor":"rgb(53, 89, 75)","proseClasses":[]} screenshot=450-blog-paragraph-light.png
  PASS forum post [data-mode=dark] {"dataMode":"dark","ul":{"listStyleType":"disc","paddingLeft":"24px","liDisplay":"list-item"},"ol":{"listStyleType":"decimal","paddingLeft":"24px","liDisplay":"list-item"},"liColor":"oklab(0.768945 -0.0492783 0.0232459)","proseClasses":[]} screenshot=450-forum-post-dark.png
  PASS blog paragraph [data-mode=dark] {"dataMode":"dark","ul":{"listStyleType":"disc","paddingLeft":"24px","liDisplay":"list-item"},"ol":{"listStyleType":"decimal","paddingLeft":"24px","liDisplay":"list-item"},"liColor":"oklab(0.768945 -0.0492783 0.0232459)","proseClasses":[]} screenshot=450-blog-paragraph-dark.png
  ALL PASS: markers render in both themes
  ```

- AC 2: `sh .sweep-evidence/g2/ac2-prose-and-ternary.sh` — evidence `.sweep-evidence/g2/450-ac1.txt` (not committed), last lines:

  ```text
    src/Planted450.ts:2  prose-lg
    src/Planted450.ts:2  never-compiled-450
  exit=1

  AC PASS
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
