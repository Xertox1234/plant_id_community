---
status: completed
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

- [x] No branch of `bodyBlocksToHtml` interpolates a persisted value into an
      HTML string: image, embed and link-card nodes are built as TipTap JSON
      or DOM nodes, with a test per branch.
- [x] A round-trip test shows every stored block shape rehydrates and
      re-serialises unchanged, so re-saving an untouched post sends no PATCH.

## Work Log

### 2026-10-02 - Filed by the todo sweep (run 2026-10-02-0335)

- Split out of todo 443 when its owner decision was narrowed to the
  server-side CR/CRLF/NUL normalisation in `sanitize.py`.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-0234)

- Owner option A: the composer's `content`/`onChange` contract is TipTap
  JSON (`getJSON()`). `forumBody` now converts `bodyBlocksToDoc` /
  `docToBodyBlocks`; image, embed, link-card and quote values travel as node
  attributes and text nodes, so no persisted value is interpolated into an
  HTML string. `bodyBlocksToHtml`, `htmlToBodyBlocks`, `escapeAttr`,
  `linkParagraphHtml` and `postQuoteHtml` are gone; the `^https?://` guard
  moved into `linkParagraph`. Paragraph blocks (HTML by contract) are parsed
  and printed with the live editor's schema, now shared in
  `components/forum/forumEditorSchema.ts`.
- Services take the write blocks (`body: ForumBodyWriteBlock[]`), so
  `forumService` no longer pulls TipTap into its import graph. NewThreadPage
  moved with ThreadDetailPage; drafts are stored as JSON and pre-526 HTML
  drafts still restore (`draftToDoc` / `toComposerDoc`).
- Re-saving an untouched post now sends no PATCH (`isUnchangedBody`); the
  same comparison replaces the reference-equality dirty check (M27).
- Tests: the `htmlToBodyBlocks` edge cases were ported to the JSON API, and
  new real-editor round trips cover every stored block shape, including CR,
  CRLF and NUL in alt text. The server-side normalisation from todo 443 stays.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-0234)

- AC 1: `cd web && ! grep -nE 'escapeAttr|linkParagraphHtml|bodyBlocksToHtml|htmlToBodyBlocks|postQuoteHtml' src/utils/forumBody.ts && echo 'no string builders remain in forumBody.ts' && npx vitest run src/utils/forumBody.test.ts --reporter=verbose` — evidence `.sweep-evidence/g2/526-ac0.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  89 passed (89)
     Start at  21:13:14
     Duration  1.02s (transform 75ms, setup 109ms, import 229ms, tests 128ms, environment 475ms)
  ```

- AC 2: `cd web && npx vitest run src/utils/forumBody.test.ts src/pages/forum/ThreadDetailPage.test.tsx -t 'every stored block shape|image attributes survive rehydrate|untouched post' --reporter=verbose` — evidence `.sweep-evidence/g2/526-ac1.txt` (not committed), last lines:

  ```text

   Test Files  2 passed (2)
        Tests  28 passed | 146 skipped (174)
     Start at  21:13:15
     Duration  1.60s (transform 371ms, setup 119ms, import 1.26s, tests 233ms, environment 559ms)
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-0234)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
