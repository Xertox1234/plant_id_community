---
status: pending
priority: p4
issue_id: "526"
tags: [web, forum, composer]
dependencies: []
source_review: "PR #826"
triage: needs-design
triaged: 2026-10-10
blocked_on: "Owner choice between a TipTap JSON content contract and DOM-built nodes still passed as an HTML string"
owner_decision: "Option A: switch the editor content/onChange contract to TipTap JSON (getJSON; paragraph HTML via generateJSON), touching TipTapEditor and ThreadDetailPage (2026-10-10)"
---

# Composer: build body HTML from TipTap JSON/DOM nodes instead of strings

## Problem

`web/src/utils/forumBody.ts` `bodyBlocksToHtml` still assembles the composer's
HTML with template strings and hand escaping (`escapeAttr`, todo 441), and
`htmlToBodyBlocks` parses it back. Escaping cannot stop the HTML parser
normalising attribute values on the way in (CR/CRLF to LF, NUL to U+FFFD), so
the rehydrate -> re-save round trip is exact today only because the server
normalises those characters on write (todo 443). The owner's 2026-09-28
decision on todo 443 was to move the composer to TipTap JSON/DOM nodes; on
2026-10-02 it was narrowed to the server-side normalisation, with the content
model change split out here.

## Findings

- `web/src/utils/forumBody.ts` `bodyBlocksToHtml` (the `image` branch and
  `linkParagraphHtml` for `embed` / `link_preview`) interpolate persisted
  values into markup; `escapeAttr` covers `&`, `<`, `>` and `"`, but the
  parser's attribute-value normalisation is not an escaping problem.
- `docs/rules/react.md` "HTML built as a string escapes `&` too" already says
  to prefer building nodes via the DOM or TipTap JSON when adding a branch
  (PR #826 review).
- todo 443's Work Log (2026-10-02, run 2026-10-02-0335) records the narrowing
  and the server-side fix that this todo keeps as defence in depth.

## Recommended Action

Replace the string-built branches with TipTap JSON (the editor's `content`
accepts a JSON document) or DOM nodes built with `document.createElement` +
`setAttribute`, in BOTH directions (`bodyBlocksToHtml` and `htmlToBodyBlocks`),
so no persisted value passes through an HTML string. Keep the server-side
normalisation from todo 443.

## Technical Details

- Scope: `web/src/utils/forumBody.ts`, `web/src/utils/forumBody.test.ts`,
  `web/src/components/forum/TipTapEditor.tsx` (the `content` prop contract and
  its `data-image-id` / `data-decorative` / `data-post-id` round-trip markers).
- `escapeAttr` and `linkParagraphHtml` become dead once no branch builds a
  string; remove them with their last caller, and the `javascript:` scheme
  guard they carry must survive the move (a TipTap/DOM `href` is still a URL).
- Read the installed TipTap source before trusting hosted docs
  (`docs/rules/react.md`).

## Acceptance Criteria

- [ ] No branch of `bodyBlocksToHtml` interpolates a persisted value into an
      HTML string: image, embed and link-card nodes are built as TipTap JSON
      or DOM nodes, with a test per branch.
- [ ] A round-trip test shows every stored block shape rehydrates and
      re-serialises unchanged, so re-saving an untouched post sends no PATCH.

## Work Log

### 2026-10-02 - Filed by the todo sweep (run 2026-10-02-0335)

- Split out of todo 443 when its owner decision was narrowed to the
  server-side CR/CRLF/NUL normalisation in `sanitize.py`.
