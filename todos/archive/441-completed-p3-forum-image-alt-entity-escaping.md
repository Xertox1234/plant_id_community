---
status: completed
priority: p3
issue_id: "441"
tags: [web, forum, accessibility, images]
dependencies: []
source_review: "PR #823"
---

# Editing a post rewrites image alt text that contains HTML entities

## Problem

`web/src/utils/forumBody.ts` `bodyBlocksToHtml` builds the editor HTML for an
image block with `alt.replace(/"/g, '&quot;')` and interpolates it into an
HTML string that TipTap parses. `&` is not escaped (nor is the `url`), so a
stored alt of `Tom &amp; Jerry` or `leaf &copy 2026` rehydrates as
`Tom & Jerry` / `leaf © 2026`, and re-saving the post PATCHes a DIFFERENT
`alt_text` for an image the author never touched.

Found by the bundled `/code-review` of PR #823 (todo 368): the new
browser round-trip test uses a plain ASCII alt, so it can't see this.

## Findings

- Also noted there: `forum-image-upload.spec.js` now repeats its
  request-counting listener 4x and the one-pixel-JPEG `setInputFiles` block
  5x; a shared helper would give one definition.

## Recommended Action

Escape `&`, `<`, `>` and `"` (and the URL) when building the HTML, or build
the node with the DOM / TipTap JSON instead of a string. Pin it with a
unit round-trip test (`bodyBlocksToHtml` → `htmlToBodyBlocks`) over alts
containing `&amp;`, `&copy`, `<`, `"`, and extend the e2e round trip with one
such alt.

## Acceptance Criteria

- [x] Alt text with `&`, `<`, `>`, `"` and entity-like sequences survives
      rehydrate → re-save byte-for-byte (unit + e2e), failing first.

## Work Log

### 2026-09-24 - Filed from PR #823 review round 1

### 2026-09-24 - Done: escape every string attribute in bodyBlocksToHtml
- `web/src/utils/forumBody.ts`: new `escapeAttr` (= `escapeHtml` + `"`) for
  values inside a double-quoted attribute; the image branch now escapes
  BOTH `alt` and `src` (the url had no escaping at all, so a `"` in it could
  break out). The embed branch's inline `safe.replace(/"/g, ...)` now uses
  the same helper (same bytes). `'` deliberately not escaped: every
  attribute is double-quoted, and ordinary values stay byte-identical
  (pinned by a test). `id`/`post_id`/`postId` are numbers — `post_id` is
  already `isSafeInteger`-guarded and htmlToBodyBlocks drops a non-digit id.
- Unit (`forumBody.test.ts`, new describe "todo 441"): `it.each` over
  `Tom &amp; Jerry`, `leaf &copy 2026`, `a < b > c`, `say "hi"`, `it's`,
  plain ASCII and decorative `""`, each through BOTH
  `htmlToBodyBlocks(bodyBlocksToHtml())` and a real TipTap Editor
  `getHTML()`; plus a src test (`&amp;`, `&copy=`, `" onerror=`) and a
  byte-identity pin. Pre-fix: 5 red (the two entity alts x both paths + the
  src test); the `<`/`"`/`'`/plain/decorative cases were already green —
  inside a double-quoted attribute they parse literally, so they are
  regression pins, not red-first cases.
- Mutations (restored via `cp` backup, grep-verified): drop `&` from
  escapeAttr -> same 5 red; leave `url` unescaped -> src test red.
- E2E: `forum-image-upload.spec.js` gains a third `imageRoundTrip` with alt
  `Tom &amp; Jerry <3`. Ran against Django + Vite from the worktree:
  chromium-authenticated 8/8 passed. With escapeAttr mutated back to
  quote-only, the new test FAILS at the rehydrated node
  (`Received: "Tom & Jerry <3"`).
- Verify: type-check 0, lint 0, `vitest run src/utils src/components/forum`
  29 files / 518 tests passed, check:classes 0.
- Not done (from Findings): the spec's repeated request-counting listener /
  `setInputFiles` block helper extraction — cosmetic, out of this todo's AC.
