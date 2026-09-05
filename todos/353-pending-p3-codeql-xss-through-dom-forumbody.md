---
status: pending
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

- [ ] Alert #116 is either dismissed with a written false-positive rationale
      or fixed with a regression test
- [ ] The next PR touching `forumBody.ts` does not re-raise it as "new"

## Work Log

### 2026-09-05 - Filed during the P4 todo sweep

- Surfaced by the CodeQL check on PR #637; confirmed pre-existing on `main`.
