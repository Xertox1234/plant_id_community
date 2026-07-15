---
status: pending
priority: p2
issue_id: "269"
tags: [backend, database, search, blog, plant_identification]
dependencies: []
---

# Search queries double-escape SQL wildcards, silently dropping real matches

## Problem

`apps/core/utils/query_sanitization.py::escape_search_query()` is called
before an `__icontains`/`__istartswith` filter at 13 production call sites
across 6 files. Django's ORM already auto-escapes `%`/`_`/`\` for these
lookups — calling `escape_search_query()` first double-escapes, so any
search containing a literal `%`, `_`, or `\` character silently returns
fewer results than it should (worst case: zero), with no error anywhere.

Found while codifying todo 253 slice 4's review findings (2026-07-14) — the
project's own documented convention (`backend/CLAUDE.md`, `docs/rules/security.md`,
`backend/docs/patterns/security/input-validation.md`) told engineers to do
exactly this, and has now been corrected. This todo is the follow-up: audit
and fix the call sites the corrected docs didn't touch.

## Findings

Verified via Django 6.0.7 source (`django.db.models.lookups.PatternLookup.
process_rhs()` calls `connection.ops.prep_for_like_query()` unconditionally
on the raw filter value; confirmed PostgreSQL does not override
`prep_for_like_query`) and reproduced via a failing test in the originating
session (`test_search_escapes_sql_wildcards`: searching `"dave_"` matched
nothing instead of the real username `"dave_1"`).

Mechanism: `escape_search_query("dave_")` → `"dave\_"` (one added
backslash). Django's own auto-escaping then escapes that string AGAIN:
`\` → `\\`, `_`... wait, order matters — the ORM escapes the escaper's
output, producing a LIKE pattern that requires a literal backslash in the
matched text. The real column value (`"dave_1"`, no backslash) no longer
matches. Silent — an empty/reduced result set, not an exception.

All 13 call sites (confirmed via direct read, each one feeds into
`icontains`, none are used for a lookup that bypasses `PatternLookup`):

- `apps/blog/admin_views.py:82` — comment search (content/author/post title)
- `apps/blog/admin_views.py:282` — admin blog search (title/description/intro)
- `apps/blog/api_views.py:140` — plant-name autocomplete suggestions
- `apps/blog/views.py:115` — tag filter (`tags__name__icontains`)
- `apps/blog/views.py:521` — public blog search (title/intro/content/tags)
- `apps/blog/api/viewsets.py:478` — blog title-suggestion autocomplete
- `apps/plant_identification/views.py:87` — plant search (scientific/common/family name)
- `apps/plant_identification/views.py:97` — family filter
- `apps/plant_identification/views.py:1022` — disease name search
- `apps/plant_identification/views.py:1192` — local plant-database search endpoint
- `apps/plant_identification/views.py:1251` — local disease-database search endpoint
- `apps/plant_identification/api/endpoints.py:89` — family filter
- `apps/plant_identification/api/endpoints.py:336` — nested family filter

Some call sites carry a comment claiming the escaping is "to prevent
query-cost abuse" (`apps/blog/api_views.py:139`, `apps/blog/views.py:520`)
— this rationale doesn't hold either: Django's own auto-escaping already
turns a `%`/`_` in the search term into a literal character to match, not
an active wildcard, regardless of whether `escape_search_query()` runs
first.

## Recommended Action

1. For each of the 13 call sites, remove the `escape_search_query()` call
   and pass the (stripped) raw query directly to the `icontains`/
   `istartswith` filter.
2. Add or extend a test per affected view/endpoint asserting a query
   containing a literal `%`, `_`, or `\` still matches the real row it's
   searching for (mirroring `wagtail_forum/tests/api/test_user_search.py::
   test_search_escapes_sql_wildcards`'s fixture shape — a decoy row that
   would only match if double-escaping were still happening).
3. Re-run each affected app's test suite (`apps.blog`, `apps.plant_identification`)
   after the fix — some existing tests may currently pass by accident (never
   exercising a query with a literal wildcard character) and would need a
   new fixture to actually pin the fix.
4. Once no call site remains, decide whether `escape_search_query()`/
   `escape_search_query_optional()` should stay in
   `apps/core/utils/query_sanitization.py` for the genuinely-still-valid
   case (a lookup that bypasses `PatternLookup` — raw SQL, `.extra()`, a
   custom `Lookup`) or be removed if no such caller exists anywhere in the
   codebase.

## Technical Details

- Root utility: `apps/core/utils/query_sanitization.py::escape_search_query()`.
- Django mechanism: `django.db.models.lookups.PatternLookup.process_rhs()` →
  `django.db.backends.base.operations.BaseDatabaseOperations.
  prep_for_like_query()` (escapes `\`, then `%`, then `_`, in that order).
- Corrected documentation (already fixed, 2026-07-14): `backend/CLAUDE.md`,
  `docs/rules/security.md`, `backend/docs/patterns/security/input-validation.md`
  (Pitfall 1, Pitfall 6, "Pattern: Forum Thread Search with Multiple Fields",
  "Pattern: Backend Search Query Sanitization", the Security Checklist).
- Write-time trigger `escape-search-query-before-orm-wildcard-lookup`
  (`docs/rules/triggers.json`) now warns on any NEW `escape_search_query(`
  call, so this class shouldn't grow further while this todo is open.
- Precedent for the test pattern:
  `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_user_search.py::
  test_search_escapes_sql_wildcards`.

## Acceptance Criteria

- [ ] All 13 listed call sites no longer call `escape_search_query()` ahead
      of an `icontains`/`istartswith` lookup
- [ ] Each affected view/endpoint has a test proving a literal `%`/`_`/`\`
      in the query still matches the real target row
- [ ] `apps.blog` and `apps.plant_identification` test suites pass
- [ ] Decision recorded on whether `escape_search_query()`/
      `escape_search_query_optional()` are still needed anywhere, or should
      be removed

## Work Log

### 2026-07-14 - Filed from todo 253 slice 4 codification pass

- Discovered while correcting the SQL-wildcard-escaping documentation that
  the codebase's OWN documented convention was actively wrong for Django's
  auto-escaping `PatternLookup` lookups (verified against Django 6.0.7
  source, reproduced via a failing test in `wagtail_forum/tests/api/
  test_user_search.py`). The corrected docs and a new write-time trigger
  ship in the same commit that files this todo; the 13 existing call sites
  themselves are intentionally NOT touched here — a code-fix task, not a
  documentation correction, and larger than the docs-only commit it was
  found alongside.

## Notes

p2: no active security hole (this is a correctness/UX bug — reduced or
missing search results — not data exposure or injection), no live
user-reported incident, but it IS already affecting real production
searches today (any query containing `%`, `_`, or `\`), unlike a purely
latent risk. Related: todo 253 (forum notifications epic) is the origin
context — the forum's OWN new `mention_user_search` endpoint (todo 253
slice 4) was written correctly (no double-escaping) specifically because
this bug was caught by its own test before shipping; this todo covers the
13 PRE-EXISTING call sites outside the forum that predate that fix.
