---
status: in_progress
priority: p3
issue_id: "225"
tags: [maintainability, web, react, typescript, security, audit]
dependencies: []
source_review: "docs/audits/2026-06-09-maintainability.md"
source_finding: "M12,M16"
---

# Maintainability: web validators wire-or-remove + diagnosis block-type registry

## Problem

Split out of todo 222 (run 2026-06-10-0251). The other five web findings
(M13/M14/M15/L8/L9) were straightforward dedups and were completed there. These
two were deferred because each needs a deliberate decision/refactor, not a
mechanical dedup:

- **M12** is a security judgment call (do NOT blind-delete tested security
  validators).
- **M16** is a component-extraction refactor (the per-block editor/renderer JSX
  genuinely differ, with per-block theming), not a find-and-replace.

## Findings

Source: `docs/audits/2026-06-09-maintainability.md`.

- **M12** `web/src/utils/validation.ts` has ~9 tested-but-unused security
  validators: `validateSlug/Token/ContentType/Url/Integer/Pagination/CategorySlug/FileType`,
  `sanitizeSearchQuery`. Investigation (2026-06-10): **all have 0 import sites**
  (only `getEmailError` is used); `validation.test.ts` covers them (108 cases);
  `validateFileType` is **redundant** with `ImageUploadWidget`'s MIME-type check
  (`ALLOWED_IMAGE_TYPES.includes(file.type)`, stronger than extension); the rest
  duplicate backend validation. The one genuine wire site is `sanitizeSearchQuery`
  → the forum search input (client-side defense-in-depth). Decide per-validator:
  wire where it applies or remove **with its tests**. Do NOT blind-delete — some
  may close latent client-side validation gaps.
- **M16** Diagnosis StreamField block-type dispatch is switched in 3 spots →
  add-a-block = 3 edits; labels/icons hard-coded in `case` JSX despite
  `BLOCK_TYPES`. `components/diagnosis/StreamFieldEditor.tsx:20-27` (`BLOCK_TYPES`
  menu array), `:58` (editor switch); `pages/diagnosis/DiagnosisDetailPage.tsx`
  (renderer switch, ~`StreamFieldBlockComponent`). Drive editor + renderer + menu
  from one block-type registry (label/icon/editor/renderer per block type).

## Recommended Action

1. M12: per-validator wire-or-remove decision (recommended from the 222 session:
   wire `sanitizeSearchQuery` into the forum search input; remove the other 8 +
   their tests, since `validateFileType` is redundant and the rest have no wire
   site and duplicate backend checks). **Confirm with the user before deleting**
   (security-adjacent).
2. M16: extract a block-type registry (one map of `{label, icon, EditorComponent,
   RendererComponent}` or equivalent) and drive the menu, editor, and renderer
   from it so adding a block is one edit.

## Technical Details

Per-finding file:line above. Patterns: `web/docs/patterns/react-typescript.md`,
`docs/rules/react.md`, `docs/rules/typescript.md`, `security/file-upload.md`.

## Acceptance Criteria

- [x] M12 validators each wired or removed (with tests); no tested-but-unused
      security validators remain. User confirmed any deletions. (done 2026-06-21
      — user approved "wire 1, delete 8": `sanitizeSearchQuery` wired into
      `SearchPage` query derivation; the other 8 removed from `validation.ts` +
      their tests pruned. type-check clean = no dangling refs.)
- [ ] M16 block-type registry single-sourced (menu + editor + renderer driven
      from one source; adding a block is one edit). (DEFERRED 2026-06-21 by user
      — real component refactor of the diagnosis StreamField editor; left for a
      focused session. This todo stays in_progress until M16 lands.)
- [x] `npm run test` + `type-check` + `lint` green. (for the M12 change:
      type-check clean, eslint exit 0, full Vitest suite 546 passed / 34 files.)

## Work Log

### 2026-06-21 - M12 done (user-approved), M16 deferred (run 2026-06-21-1412)

Walk-through with the user. **M12 (user chose "wire 1, delete 8"):**

- Verified the audit's claim against current code (post-PR#374 forum rewrite):
  all 9 security validators have **0 import sites**; internal deps mapped
  (`validateCategorySlug→validateSlug`, `validatePagination→validateInteger`,
  so the 8 delete together cleanly); the kept form validators
  (`validateRequired/Email/Password/PasswordMatch`) are used internally by the
  live `get*Error` helpers, so they stayed.
- Wired `sanitizeSearchQuery` into `SearchPage` at the query derivation
  (`const query = sanitizeSearchQuery(searchParams.get('q') || '')`) — one point
  that covers the typed input AND a direct `?q=...` URL (defense-in-depth;
  backend already sanitizes).
- Deleted the other 8 (`validateSlug/Token/ContentType/Url/Integer/Pagination/
  CategorySlug/FileType`) from `validation.ts` and pruned their tests from
  `validation.test.ts` (removed the now-dead validator `describe`s + the
  deleted-validator assertions in the cross-cutting `security`/`edge` blocks;
  kept the email-XSS-rejection assertion). 77 dead test cases removed.
- Verified: `tsc --noEmit` clean (proves no dangling refs to the deleted
  validators anywhere), `eslint` exit 0, full Vitest suite **546 passed / 34
  files**. Self-reviewed (deletion was provably dead code; wiring is trivial) —
  no multi-agent review (proportionate).

**M16: DEFERRED by the user** — single-sourcing the diagnosis StreamField block
dispatch (menu array + editor switch at `StreamFieldEditor.tsx:20,58,415` +
renderer switch at `DiagnosisDetailPage.tsx:45`) is a real component-extraction
refactor with per-block JSX/theming and regression risk, not a mechanical dedup.
Left for a focused session. **This todo stays `in_progress`** until M16 lands;
the `source_review` finding (M12,M16) is NOT checked off yet (M16 still open).
Consider splitting M16 to its own todo if it stays deferred.

### 2026-06-10 - Created (split from todo 222)

- Deferred from todo 222 during the completing-todos sweep (run 2026-06-10-0251).
  The user chose to defer M12 to its own todo; M16 was added here too because its
  proper fix is a component-extraction refactor, not a mechanical dedup, and was
  not safe to rush at the tail of that session. The other 5 web findings
  (M13/M14/M15/L8/L9) were completed in 222.

## Notes

p3: quality/maintenance, no user-facing bug. M12 is the security judgment call
(don't delete potentially-should-be-wired validators without confirmation).
