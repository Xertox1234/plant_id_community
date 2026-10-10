---
status: completed
priority: p3
issue_id: "542"
tags: [todo-sweep, engine]
dependencies: []
---

# Todo sweep: give an owner-approved review round 3 a real path through the run file

## Problem

When round 2 sustains a blocking finding, `ingest-review --round 2` blocks the group. The owner has
approved a hand-run round 3 three times now: #880 (run 2018, g8), #886 (todo 423) and #982 (run
2026-10-10-1537, g1). Each time, the engine had no path for it:

- `ALLOWED["blocked"] = {"ready"}` (`scripts/todos/state.py:48`). Reopening to `ready` discards the PR
  and starts a fresh worker, which is wrong for a PR that is one fix away from mergeable.
- `clear_hold` resumes at review, but only for a refuter **hold** (`reason` starts with `HELD`), not for
  a sustained blocking finding.
- So the round is run by hand. The repair is committed in the PR worktree, then `annotate tree_id`, and
  `review_args` is run on an **unsaved deepcopy** of the run with the group set to `pr_open` /
  `review_round 1` and `review_baseline` popped. That returns a bare list, which is wrapped as
  `{"round": 2, …}` and launched. The deepcopy has no saved path, so the args carry
  `state.py residue '' g1`. The round-3 result is never ingested, so its non-blocking findings never reach
  the run file, and the follow-up todo has to be written by hand (todo 541).
- After the merge, the group stays `blocked` with an annotated `merged_pr`. `set-group … reviewed` and
  `… merged` are refused, and `state.py worktrees` keeps listing the removed worktree as if it were live.
  `finish` accepts it only because `blocked` counts as terminal.

The procedure lives only in session memory, and it bypasses every guard the engine applies to the first
two rounds: residue baseline, ingest and follow-up capture.

## Proposed fix

1. `state.py hand-round $RUN G --decision "<owner's words, dated>"`. It accepts only a group blocked by
   `ingest-review --round 2` for blocking findings (not a hold, not a worker/verifier/Land block). It
   records the decision and moves the group back to `pr_open` with `review_round: 2` and a
   `hand_round: 3` marker. It refuses a second time (the cap is three rounds).
2. The owner's repair is committed in the PR worktree, followed by `annotate tree_id`, as today. Then
   `review-args --round 3` builds round-2-mode args (no repair) with a real run path and a fresh residue
   baseline, and `ingest-review --round 3` records it: `clean` → `reviewed`, blocking → `blocked` for
   good (owner hand-off). Its follow-ups and refuted findings are stored like any round's.
3. The runbook (`completing-todos` SKILL.md, Stage C) gets a step for it, replacing the memory-only
   procedure. Note there that `.claude/skills/` is write-denied in the main checkout's sandbox, so the
   worker edits it in its worktree.

## Acceptance Criteria

- [x] `state.py hand-round` moves a group blocked by round-2 blocking findings back to `pr_open` with the
      owner's dated decision, and refuses a held group, a group blocked for any other reason, and a second
      call on the same group (tests, each with a guard-removed mutant).
- [x] `review-args --round 3` and `ingest-review --round 3` work on the saved run file: a clean round 3
      ends at `reviewed`, so `set-group merged` / `archived` then succeed. A blocking round 3 ends
      `blocked`, and the engine runs no round 4 (tests).
- [x] Round 3's non-blocking and refuted findings are stored with the group, as rounds 1–2 are (test).
- [x] The completing-todos runbook documents the step, and no deepcopy or hand-built args remain in it.

## Work Log

- 2026-10-10: Filed from run 2026-10-10-1537 at the owner's request, after the third hand-run round 3
  (#982). See `docs/LEARNINGS.md` 2026-10-10 and the run's codify PR #985.
- 2026-10-10: Done. `state.py hand-round` (accepts only a round-2 `blocked_by`, never a hold or any other
  block, and only once), round 3 in `review-args` / `ingest-review` (needs `hand_round: 3`; no round 4), a
  round-3 hold clears to `reviewed` with round 3 done, and the Stage C runbook step. Evidence:
  `python3 scripts/todos/test_state_flow.py` (`hand_round_542_tests`: four guard-removed mutants, and round 3
  run on a saved run file against a real git worktree), `python3 scripts/todos/test_state.py`, and
  `node scripts/todos/test_workflows.js` (round 3 never repairs).
