---
status: pending
priority: p4
issue_id: "494"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: harden owner re-points and the verify-only reopen

## Problem

PR #885 (todo 492) added `state.py repoint` and `set … ready --reverify`. Its reviews fixed the
blocking findings, and round 2 narrowed re-verify to one-todo attempts. The non-blocking findings are
collected here.

## Findings

1. **The re-point rule is enforced only in the verifier's prompt.** Verifier step 4 accepts a criterion
   whose only change is a marker listed on the `REPOINTS:` line. Nothing in code checks it. The archive
   tripwire (`scripts/check_archived_todo_status.py`) accepts any re-point marker on an unchecked box,
   whether or not it was authorized. `state.py` already has `todofile.ac_lines` and each entry's
   `repoints`. It could compare the merge-base and current criteria in `ingest_execute` and in the review
   ingest, allowing only the listed markers.
2. **Stale re-points reach a fresh attempt.** `transition` moves failed → ready without moving
   `repoints`, so a fresh worker's brief lists a re-point whose target file existed only in the
   abandoned worktree. Move `repoints` to `previous` on that edge, or list re-points only in a re-verify
   brief and the review of its PR.
3. **`repoint` accepts any `ready` todo,** including a failed → ready retry that still has its old
   worktree recorded. It then stages the marker in that dead worktree. Require `blocked`, or `ready`
   with `reverify`.
4. **`--date` goes into the marker unvalidated.** A quote, `;` or newline would break the `REPOINTS:`
   line. Only the main session sets it, so this is hardening. Validate `YYYY-MM-DD`, and quote the
   marker with `JSON.stringify` in both workflows.
5. **Re-running `repoint` on another day is refused** as "re-pointed elsewhere", because the marker
   contains the date. Compare only `→ todo NNN`.
6. **Verifier step 4 wording.** Say that `#<index>` is 0-based (the same `index` as AC_FILE), and that
   exactly one occurrence of the marker is removed; a second occurrence is an edit.
7. **`--reverify` accepts a todo blocked at Land,** not only one a worker blocked. A step-3 block
   ("criteria not verified") leaves flipped boxes unstaged, and a step-7 block (a rebase conflict)
   comes after the commit. The re-verify then fails closed and uses up the retry. Record who blocked it
   (for example `blocked_by: worker` from `ingest_execute`) and allow only a worker block.
8. **The `todo-execute` pipeline stage is synchronous on the re-verify path**
   (`b.reverify ? reverifyWorker(b) : agent(…)`). Make it `async`, so a runtime that chains with `.then`
   still gets the record.
9. **Tests.**
   - Nothing checks the record `reverifyWorker` builds against the WORKER schema. A missing `branch`
     would make `ingest_execute` raise a KeyError.
   - The non-numeric target check (`to="../8"`) would pass without the `isdigit` guard, because the
     glob refuses it too. Use a target like `8a` with a staged `8a-*.md` file.
   - The "missing WORK_FIELDS" refusal in `reopen_reverify` is never exercised.
   - No test calls `repoint` on a `ready` todo, so narrowing its stage check (finding 3) is unpinned
     either way.

## Acceptance Criteria

- [ ] Findings 1–8 are fixed, or each has a line in this todo saying why not.
- [ ] Each gap in finding 9 has a test that fails when the guard it names is removed.

## Work Log

### 2026-09-28 - Filed from PR #885 review rounds 1 and 2
