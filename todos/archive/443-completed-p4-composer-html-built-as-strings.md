---
status: completed
priority: p4
issue_id: "443"
tags: [web, forum, composer]
dependencies: []
source_review: "PR #826"
triage: needs-research
triaged: 2026-10-02
owner_decision: "Move the composer to TipTap JSON/DOM nodes instead of building HTML strings (2026-09-28); narrowed 2026-10-02: do the server-side CR-to-LF and NUL normalisation in sanitize.py _normalise_image_value plus a test covering CR and NUL; the TipTap JSON content model becomes a separate future todo (2026-10-02)"
blocked_on: "Confirm scope of the TipTap JSON decision (both directions, HTML-string contract replaced) vs the small server-side normalisation the AC also allows."
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

- [x] An alt containing `\r\n` survives rehydrate → re-save unchanged, or
      the backend normalizes it on write (test either way).

## Work Log

### 2026-09-24 - Filed from PR #826 review round 1

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Owner narrowed the decision (2026-10-02) to the server side:
  `_normalise_image_value` in `sanitize.py` now rewrites CRLF and lone CR to LF
  and deletes NUL before the strip/truncate, so the stored alt is the form the
  browser's attribute parser would produce and rehydrate -> re-save is a
  no-op. Docstring point 3 records why.
- Normalisation runs before the length cap on purpose: the cap applies to the
  final form, and `str.strip()` removes CR but not NUL, so an alt of only NULs
  would otherwise pass as authored text.
- Tests in `wagtail_forum/tests/test_blocks.py`:
  `test_alt_line_endings_and_nul_are_normalised_on_write` (CRLF, lone CR,
  NUL), `test_alt_of_only_cr_and_nul_is_blank_and_so_decorative`,
  `test_alt_is_normalised_before_the_length_cap`.
- Checked, not assumed: before this change a NUL alt never reached storage. A
  throwaway probe (deleted, not committed) that saved a `Post` whose body
  carried `alt_text: "a\x00b"` raised `django.db.utils.DataError: unsupported
  Unicode escape sequence — \u0000 cannot be converted to text` from the jsonb
  column, which the API surfaces as a 500. Deleting NUL, rather than storing
  U+FFFD, is therefore the only form that lets the write succeed at all.
- The TipTap JSON/DOM content model from the 2026-09-28 decision is split out
  as todo 526 (`todos/526-pending-p4-composer-tiptap-json-content-model.md`).

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py 2 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_blocks.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/443-ac0.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 29 passed, 2 warnings in 17.75s ========================
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
