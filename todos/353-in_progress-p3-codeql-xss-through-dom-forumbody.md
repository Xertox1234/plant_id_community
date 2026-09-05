---
status: in_progress
priority: p3
issue_id: "353"
tags: [web, security, codeql, forum]
dependencies: []
---

# Triage CodeQL alert #116 (js/xss-through-dom) on forumBody.ts's DOMParser round-trip

## Problem

GitHub code scanning has held an open **high** alert since 2026-07-30:
`js/xss-through-dom` — "DOM text is reinterpreted as HTML without escaping
meta-characters" — at the `new DOMParser().parseFromString(html, 'text/html')`
call in `web/src/utils/forumBody.ts` (`htmlToBodyBlocks`). It resurfaced as
"1 new alert" on PR #637 (todo 344) only because the embed block changes
shifted the alert's fingerprint; the flagged code and the flow predate that
PR. CodeQL is not a required check, so it does not block merges, but a
standing high-severity alert on `main` has never been assessed.

## Findings

- Alert: <https://github.com/Xertox1234/plant_id_community/security/code-scanning/116>
  (`most_recent_instance.ref` = `refs/heads/main`, created 2026-07-30).
- The sink is a **detached** document: `parseFromString` never attaches to
  the page, and `htmlToBodyBlocks` only reads text/attributes from it.
- The DOM-text sources are the composer round-trip helpers in the same
  file (`quoteTextOf`, `embedUrlOf`, `node.textContent`) whose output goes
  through `escapeHtml` before `bodyBlocksToHtml` hands HTML back to TipTap —
  a custom sanitizer CodeQL does not model, which is the likely reason for
  the finding.
- The trust boundary that matters is `bodyBlocksToHtml` → TipTap
  `setContent` (live composer DOM), covered by `forumBody.test.ts`'s
  escaping cases and the http(s) href allowlist added in todo 344.

## Recommended Action

1. Trace the CodeQL path (SARIF "path" view on the alert) and confirm every
   source reaches the sink only through `escapeHtml`/`getSafeHref`.
2. If confirmed benign: dismiss the alert as **false positive** with that
   reasoning, and consider a `// codeql[js/xss-through-dom]` suppression
   comment or a CodeQL model pack entry so it does not resurface on every
   fingerprint shift.
3. If any path is unescaped: fix it in `forumBody.ts`, add the failing case
   to `forumBody.test.ts`, and let CodeQL close the alert.

## Acceptance Criteria

- [x] Alert #116 is either dismissed with a written false-positive rationale
      or fixed with a regression test
- [ ] The next PR touching `forumBody.ts` does not re-raise it as "new"

## Work Log

### 2026-09-05 - Filed during the P4 todo sweep

- Surfaced by the CodeQL check on PR #637; confirmed pre-existing on `main`.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Traced, hardened, dismissed (run 2026-09-05-1142)

**The CodeQL path** (SARIF `codeFlows` of the `/language:javascript-typescript`
analysis on `main` @ 78e0dbf, alert #116, rule `js/xss-through-dom`):

```text
 0 forumBody.ts:50   el.textContent                      ← "DOM text": the pasted link's paragraph text in embedUrlOf
 4 forumBody.ts:51   PROVIDER_VIDEO_URL.test(text) ? text : null
 8 forumBody.ts:138  blocks.push({type:'embed', value: embedUrl})   [ArrayElement, value]
11 forumBody.test.ts:146/152  once = htmlToBodyBlocks(body); bodyBlocksToHtml(once)   ← through the TEST file
18 forumBody.ts:198  paragraph branch: return block.value           ← the taint conflates the embed VALUE with paragraph HTML
23 forumBody.test.ts:152  bodyBlocksToHtml(...) → html
25 forumBody.ts:118  parseFromString(html)                          ← sink
```

Why it is a false positive: (1) the only route from DOM text to the sink is
the test's round-trip composition — in production the parser input is
TipTap's own serialisation and the parsed document is detached and only
read; (2) the taint is carried on `[ArrayElement, value]`, so the
regex-validated embed URL "becomes" a paragraph's HTML only in CodeQL's
model — the real paragraph values are server-sanitized HTML and the embed
branch escapes its URL (`escapeHtml` + `&quot;`, todo 344's href guard).

Hardened anyway: `PROVIDER_VIDEO_URL` now uses `[^\s<>"'`]+` instead of
`\S+`, so a pasted "link" carrying HTML meta-characters stays an ordinary
paragraph (TipTap-escaped) instead of becoming an embed value; test
`never turns a link carrying HTML meta-characters into an embed` (mutation:
loosening the youtu.be branch back to `\S+` fails it). A
`// codeql[js/xss-through-dom]` suppression comment with the rationale
sits on the sink line so a fingerprint shift does not re-raise it.

Alert #116 dismissed as **false positive** via the code-scanning API with
the rationale above (the API caps the comment at 280 chars; this entry is
the full text).

Noted, out of scope: the same analysis carries a second `js/xss-through-dom`
result at `TipTapEditor.tsx:438` (`altPrompt.previewUrl`, a
`URL.createObjectURL(file)` blob URL rendered as an `<img src>` preview) —
a blob: URL of a user-chosen file into an image src is benign; it is not
alert #116 and is left for its own triage.

```text
npx vitest run src/utils/forumBody.test.ts → 32 passed
npm run type-check → exit 0; eslint clean
```

### 2026-09-05 - AC1 flipped

- Alert #116 → `dismissed (false positive)` (code-scanning API response), rationale
  in the entry above; regression test `never turns a link carrying HTML
  meta-characters into an embed` in `forumBody.test.ts` (32 passed; mutation
  loosening the regex → 1 failed).

```text
npx vitest run → Test Files 97 passed (97) / Tests 1245 passed (1245)
```
