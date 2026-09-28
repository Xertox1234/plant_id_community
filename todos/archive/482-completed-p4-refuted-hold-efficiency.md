---
status: completed
priority: p4
issue_id: "482"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-28
owner_decision: "finish refuses to delete the run file while a held group exists (2026-09-28)"
---

# Todo sweep: hold at round 1, and dedupe refuted findings by file:line

## Problem

Two non-blocking findings from PR #874's round-1 review, about the critical hold (todo 478):

1. **The hold waits for round 2.** A critical dismissed by refuters in round 1 guarantees a
   `held` outcome at round 2. Round 1 still returns `clean` or `repair-staged`, so the engine
   pays for the repair, the verifier, a commit and push, and a full round 2 before holding.
   This costs agents only: the PR is still never armed.
2. **`refuted` dedupes on the whole line.** Each line carries its `| also: …` phrasings,
   so the same file:line dismissed in both rounds with slightly different wording is stored
   twice. The hold reason then says "2 critical finding(s)" for one bug, and the PR comment
   repeats it.

3. **`finish` can drop a held group's record.** `is_complete` treats `blocked` as terminal,
   so the wrap-up's `finish` deletes the run file while a PR is still held. Then
   `clear-hold` has nothing to act on, and the owner must merge by hand. This fails safe,
   because nothing arms. Found in PR #874's round-2 check.

## Recommended Action

1. In a round-1 ingest, if any dismissed critical exists, return `held` right away. Block the
   group with the hold reason and leave any staged repair uncommitted, for the owner.
2. Key `refuted` on severity plus file:line, and merge the phrasings into one line.

## Acceptance Criteria

- [x] A critical dismissed in round 1 returns `held` from the round-1 ingest, with a test.
- [x] The same file:line dismissed in both rounds is one `refuted` line with the phrasings
      merged, with a test.
- [x] `finish` refuses, or warns and lists, while any group is held for the owner, with a test.

## Work Log

### 2026-09-28 - Filed from PR #874 review round 1

- Non-blocking; filed under the two-round review budget.

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- A critical dismissed by the refuters in round 1 now returns `held` from the round-1 ingest: the group is
  blocked with the hold reason (`(round 1)`, and a note when a verified repair waits staged, uncommitted), so
  no commit, push or round 2 is paid for. A failed round-1 repair still blocks, naming the critical too.
- `clear-hold` on a round-1 hold returns the group to `pr_open` with round 1 done, and records the cleared
  lines in `hold_cleared`, so round 2 does not hold again for them; a new critical in round 2 still holds.
- `refuted` is keyed on severity plus file:line: a later round's new phrasings join the existing line, so one
  bug counts once in the hold reason and the PR comment.
- Owner decision applied: `state.py finish` refuses (exit 1, naming the groups) while any group is held for
  the owner, and keeps the run file. Tests in `test_state_flow.py`; one existing check changed its
  expectation (round 1 now returns `held`, not `clean`), as this todo asks.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/482-ac0.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

- AC 2: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/482-ac1.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

- AC 3: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/482-ac2.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
