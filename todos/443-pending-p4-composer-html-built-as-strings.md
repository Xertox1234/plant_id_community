---
status: pending
priority: p4
issue_id: "443"
tags: [web, forum, composer]
dependencies: []
source_review: "PR #826"
---

# Composer HTML is built as strings: parser normalization still alters some alts

## Problem

`web/src/utils/forumBody.ts` `bodyBlocksToHtml` builds composer HTML with
template strings and hand escaping (todo 441 added `escapeAttr`). Escaping
cannot stop the HTML parser normalizing attribute values: CR and CRLF become
LF, NUL becomes U+FFFD. An alt stored with `\r\n` (possible via a direct
API write; the backend only trims the ends) still comes back different on
rehydrate, and re-saving an untouched post PATCHes a changed `alt_text`.

## Recommended Action

Build the image/embed nodes with `document.createElement` + `setAttribute`
(or pass TipTap JSON) instead of strings, which removes manual escaping and
parser normalization for those branches; or normalize such alts server-side
on write and document it.

## Acceptance Criteria

- [ ] An alt containing `\r\n` survives rehydrate → re-save unchanged, or
      the backend normalizes it on write (test either way).

## Work Log

### 2026-09-24 - Filed from PR #826 review round 1
