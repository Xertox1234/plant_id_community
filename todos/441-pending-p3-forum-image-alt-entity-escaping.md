---
status: pending
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

- [ ] Alt text with `&`, `<`, `>`, `"` and entity-like sequences survives
      rehydrate → re-save byte-for-byte (unit + e2e), failing first.

## Work Log

### 2026-09-24 - Filed from PR #823 review round 1
