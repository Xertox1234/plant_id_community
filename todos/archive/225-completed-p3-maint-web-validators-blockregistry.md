---
status: completed
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
- [x] M16 block-type registry single-sourced (renderer driven from one source;
      adding a block is one edit). (done 2026-06-23 — investigation showed the
      diagnosis `StreamFieldEditor.tsx` was **dead code**: never imported in git
      history, no tests, no diagnosis edit page exists — `care_instructions` are
      backend AI-generated and rendered read-only. User chose "delete editor +
      registry-fy renderer". Deleted the 370-line dead editor (3 of 4 dispatch
      spots gone); extracted the live renderer into `streamFieldBlocks.tsx`
      driven by an exhaustive `Record<DiagnosisBlock['type'], …>` registry — TS
      now fails the build until a new block type has a registered renderer
      (adding a block = one edit). The audit's "menu + editor" sources were the
      dead editor, so single-sourcing applies to the one live consumer.)
- [x] `npm run test` + `type-check` + `lint` green. (M16 change: `tsc --noEmit`
      exit 0 — proves no dangling refs to the deleted editor/inlined renderer;
      eslint exit 0; full Vitest suite **571 passed / 38 files** incl. 10 new
      `streamFieldBlocks.test.tsx` cases — one per block type + unknown-type
      fallback.)

## Work Log

### 2026-06-23 - M16 done (delete dead editor + registry-fy renderer) (run 2026-06-23-1511)

- Picked up by `/todo-next 225`. M12 already done; only M16 (block-type
  registry) remained. Already `in_progress`, so no rename needed.
- **Key finding (corrects the audit):** `web/src/components/diagnosis/
  StreamFieldEditor.tsx` (370 lines) was **dead code** — `git log -S` shows it
  was *never* imported in the entire history, it has no test, and there is no
  diagnosis create/edit page. `care_instructions` are produced by the backend
  (AI) and rendered read-only by the inline `StreamFieldBlockComponent` in
  `DiagnosisDetailPage.tsx`. So M16's premise ("dispatch switched in 3 spots,
  add-a-block = 3 edits, drive menu + editor + renderer from one registry") was
  3 dead switches (in the editor) + 1 live switch (the renderer). The unrelated
  `components/StreamFieldRenderer.tsx` is the blog/forum renderer, not this.
- Pressure-tested with `kimi-challenge` (flagged the live renderer being an
  untestable in-page switch as the real concern) and brought the fork to the
  user via AskUserQuestion. **User chose "Delete editor + registry-fy renderer".**
- Implementation:
  - `git rm` the dead `StreamFieldEditor.tsx` (removes 3 of 4 dispatch spots).
  - New `components/diagnosis/streamFieldBlocks.tsx`: one small renderer per
    block type, each typed via `BlockRendererMap[K] = FC<{block: Extract<
    DiagnosisBlock,{type:K}>}>`; exhaustive `BLOCK_RENDERERS: BlockRendererMap`
    registry; exported `StreamFieldBlock` dispatcher that looks up by
    `block.type` and logs+returns null for unknown (preserves old `default`
    behavior). JSX copied verbatim from the old renderer → no visual change.
  - `DiagnosisDetailPage.tsx`: deleted the inline `StreamFieldBlockComponent`,
    imported and used `StreamFieldBlock` (rename-usage → remove-def → add-import
    order to dodge the edit-time import strip).
  - New `streamFieldBlocks.test.tsx`: 10 cases (every block type + frequency-
    absent, image caption/alt fallback, unknown-type warn+null).
- Verification: `tsc --noEmit` exit 0; `eslint` exit 0; `vitest run` **571
  passed / 38 files**.
- Review (code-review-orchestrator → react-typescript-reviewer): 0 critical / 0
  high / 0 medium. Confirmed behavioral parity (JSX moved verbatim), exhaustive
  typing, safe deletion (no remaining `StreamFieldEditor` refs). 1 LOW + 1 INFO
  — both fixed rather than deferred: the image "omits caption" test now asserts
  no `<p>` renders (was hollow per testing rules); added a comment on the
  dispatcher cast/guard so it isn't "simplified" away. Re-ran gate after fix:
  tsc 0, eslint 0, streamFieldBlocks 10/10.

### 2026-06-23 - Completed by completing-todos skill (run 2026-06-23-1511)

- Verification: both open acceptance criteria (M16 + green gate) passed with
  quoted evidence above. M12 was already done (2026-06-21).
- Review: 2 findings total (1 LOW, 1 INFO), 0 blocking — both repaired.
- Checked off #M12 and #M16 in the source review doc. All 21 Finding Status
  lines now `[x]`, so `docs/audits/2026-06-09-maintainability.md` was renamed to
  `docs/audits/2026-06-09-maintainability-COMPLETED.md` — all findings resolved.

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
