---
status: pending
priority: p4
issue_id: "637"
tags: [todo-sweep, docs, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Finding 2: the apply-triage unblock requires an owner_decision; a plain --reset-stranded keeps the triage class and blocked_on (2026-10-12)"
---

# Follow-ups from PR #1082 (todos 614, 616, todo-sweep runbook)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1082 (todos 614, 616, todo-sweep runbook). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1082 (todo sweep run 2026-10-12-0349, group g12, todos 614, 616); follow-ups: verified.

1. **medium** `.claude/skills/completing-todos/SKILL.md:377` DIRTY step 3 uses one `<path>` placeholder for both `show :2:<path>` (needs the conflicted, archived `completed` path) and `show origin/main:<path>` (pre-archive `pending` path), then defines `<path>` as the pending path. `:2:` at the pending path fails and the unguarded `>` leaves an empty .branch copy, losing ticks. | also: Step 3 uses one placeholder `<path>` for two different paths. `show :2:<path>` needs the conflicted (archived `completed`) path, but the closing 'where `<path>` is ... its pre-archive `pending` path' reads as covering both. `:2:` at the pending path fails and leaves an empty `.branch` copy, so the branch's ticks are lost. | Step 3 uses one `<path>` placeholder for both `show :2:<path>` and `show origin/main:<path>`, then redefines `<path>` as the pre-archive pending path. For an archived todo, :2: lives at the completed path, so an operator who reads it literally gets 'path not in index' for the branch copy. | The DIRTY todo rebuild assumes git saw the archive as a rename, so the conflict and stage :2 sit at the completed path. If rename detection misses (a heavy archive edit), it is a modify/delete at the pending path. Then `show :2:<completed path>` fails and the unguarded `>` leaves an empty .branch file. | The branch-side save (`git show :2:<path> > $TMPDIR/<name>.branch`) has no success check. Only the origin/main show is gated. If `:2:` is absent, an empty .branch file is the 'saved copy' that ticks and Work Log entries get re-applied from, so they are silently dropped.
2. **low** `scripts/todos/state.py:505` The unblock fires for any needs-design/blocked-* todo past triage, including one moved to ready only by `decide ready --reset-stranded` with no --decision. The owner answered the stranded question, not the class one, yet blocked_on is dropped and triage is written ready.
3. **low** `.claude/skills/completing-todos/SKILL.md:402` SKIP_KIMI_REVIEW=1 on the DIRTY merge commit also skips kimi for hunks resolved by hand (todos/ rebuilds, .secrets.baseline line numbers); the rationale covers only what origin/main brought in. Owner-approved; detect-secrets and other hooks still run. | also: Step 6 says to 'record `kimi: skipped`' for the recovery merge commit, but the PR body is already written at this point and no state field or wrap-up line is named. The record has no defined home, so the wrap-up's `kimi: skipped` count can miss it.
4. **low** `scripts/todos/state.py:501` New comment says needs-design and blocked-* leave `triaged` only through `decide … ready`, but `state.py set <id> ready` also does so with no owner_decision. The stated invariant is wrong. The 614 #5 test (stage ready with a decision) also passes on the old code, so it is not a regression test.
5. **low** `.claude/skills/completing-todos/SKILL.md:396` DIRTY step 4 stops the group on any gate failure, but `pre-commit run --files` exits 1 whenever a fixer (trailing-whitespace, end-of-file) rewrites a resolved file, so a fixer-only rewrite disarms and aborts the recovery although step 6 has a fixer path.
6. **low** `todos/archive/614-completed-p4-todo-sweep-triage-guard-1061.md:58` The AC command runs `tests && ...; echo exit=$?; ...; sed`, so it always exits 0, and the quoted evidence tail shows no `exit=` line, so the recorded evidence cannot show the suites passed (616's AC command has the same shape).
7. **low** `todos/archive/616-completed-p4-dirty-armed-pr-recovery-1063.md:56` Work Log ordering is inconsistent: the 'Verified' and 'Completed' entries are dated 2026-10-11 but follow the 2026-10-12 'Implemented' entry of the same run 2026-10-12-0349 (614 has the same problem). Land likely used a stale `$TODAY`.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1082 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g12`.
