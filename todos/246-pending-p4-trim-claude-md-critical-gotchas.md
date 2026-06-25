---
status: pending
priority: p4
issue_id: "246"
tags: [harness, docs, housekeeping, claude-md]
dependencies: []
---

# Decide whether to trim CLAUDE.md Critical Gotchas that are now trigger-enforced

## Problem

Two of the seven Critical Gotchas in the root `CLAUDE.md` are now also enforced
automatically as write-time triggers in `docs/rules/triggers.json`. The original
housekeeping sweep (todo 230, Recommended Action #4) proposed shrinking these to
one-line pointers, but that half was left undone because the prose is also useful
read-time orientation. This todo exists to make that call deliberately rather than
let it sit as an unresolved "optional" item.

## Findings

- `CLAUDE.md:47-70` — the `## Critical Gotchas` section (7 numbered gotchas).
- **Gotcha #1** (`CLAUDE.md:51`, ViewSet `get_permissions()` must call `super()`
  for `@action`) is enforced by a trigger in `docs/rules/triggers.json` (the
  `content_present: "def get_permissions\\b"` + `content_absent:
  "super\\(\\)\\.get_permissions"` rule, ~line 50-52). Long-form detail lives in
  `backend/docs/patterns/architecture/viewsets.md`.
- **Gotcha #3** (`CLAUDE.md:57`, raw SQL in migrations: no f-strings for
  table/column names) is enforced by the `migration-fstring-sql` trigger in
  `docs/rules/triggers.json` (~line 22-32). Long-form detail lives in
  `backend/docs/patterns/security/input-validation.md`.
- The other five gotchas (#2 react-router-dom, #4 ratelimit 403/429, #5 useRef
  debounce, #6 stale test DB, #7 LSP position) are NOT trigger-enforced and stay
  as prose regardless.
- Discovery source: todo 230 Recommended Action #4 (2026-06-10 harness audit);
  trigger enforcement re-verified 2026-06-24 against `docs/rules/triggers.json`.

## Proposed Solutions

### Option 1: Measured trim (Recommended)

- **Implementation:** For gotchas #1 and #3 only, keep the one-line bold headline
  (scannable read-time orientation) but replace the explanatory paragraph with a
  one-line pointer, e.g. `→ enforced write-time by docs/rules/triggers.json; full
  detail in backend/docs/patterns/architecture/viewsets.md`. Leave gotchas
  #2/#4/#5/#6/#7 untouched.
- **Pros:** Removes the prose that now duplicates trigger + pattern-doc content;
  keeps the list scannable; the "why" still reachable one click away.
- **Cons:** A reader scanning only CLAUDE.md loses the inline explanation for two
  items; relies on the pattern docs staying accurate.
- **Effort:** ~15 minutes.
- **Risk:** Low — doc-only.

### Option 2: Close as wontfix

- **Implementation:** Leave the Critical Gotchas section as-is; document that the
  prose is intentionally retained as read-time orientation even though enforcement
  is automated (triggers fire at write-time; the gotchas orient at read-time —
  different purpose, not pure duplication).
- **Pros:** Zero risk of losing useful context; acknowledges triggers and gotchas
  serve different moments.
- **Cons:** A small, known overlap between CLAUDE.md and triggers.json persists.
- **Effort:** ~2 minutes (close the todo).
- **Risk:** None.

## Recommended Action

1. Decide Option 1 vs Option 2 (repo owner's call — both are defensible).
2. If Option 1: trim gotchas #1 and #3 in `CLAUDE.md` to headline + pointer; leave
   the other five intact. Verify each pointer's pattern-doc path exists.
3. If Option 2: record the rationale and close.

## Technical Details

- Editing root `CLAUDE.md` (agent-startup config) can trip the auto-mode self-mod
  classifier — have Auto Mode disabled for that step (same constraint as todo 230).
- Doc-only change → feature branch + PR (branch protection on `main`).
- No `source_review` frontmatter; no review-doc Finding Status to update.

## Acceptance Criteria

- [ ] A decision (Option 1 or Option 2) is recorded in this todo's Work Log.
- [ ] If Option 1: gotchas #1 and #3 in `CLAUDE.md` are headline + one-line pointer
      to `docs/rules/triggers.json` and their pattern docs; gotchas #2/#4/#5/#6/#7
      are unchanged; both referenced pattern-doc paths verified to exist.
- [ ] If Option 2: the keep-as-is rationale is documented and the todo is closed.

## Work Log

### 2026-06-24 - Created

- Filed as the deferred half of todo 230 Recommended Action #4. Todo 230's other
  three parts (todos/ reference-doc cleanup, forum pattern doc rewrite, memory
  prune) and AC #4 (global/project CLAUDE.md delegation dedup, PR #404) are done;
  this gotcha-trim was the only piece the sweep deliberately left as an open
  judgment call. Trigger enforcement of gotchas #1/#3 re-verified against
  `docs/rules/triggers.json`.

## Notes

- Priority p4: purely cosmetic doc hygiene with no functional impact, and Option 2
  (close as wontfix) is a legitimate outcome — so this is genuinely low-stakes.
- Related: todo 230 (parent, archived 2026-06-24 as
  `todos/archive/230-completed-p3-harness-housekeeping-sweep.md`).
