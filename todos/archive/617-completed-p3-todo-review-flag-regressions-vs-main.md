---
status: completed
priority: p3
issue_id: "617"
tags: [todo-sweep, tooling, review]
dependencies: []
owner_decision: "Implement as proposed; AC 3: KEEP the manual round-1 medium read in SKILL.md as a fallback for regressions the reviewer did not flag (2026-10-11)"
triage: ready
triaged: 2026-10-16
---

# todo-review: a medium that is a regression against main should hold the PR, not become a follow-up

## Problem

`todo-review.js` treats only `critical`/`high` as blocking (`BLOCKING`). Every `medium` becomes a follow-up,
even when it is a NEW regression that the PR introduces. So round 1 comes back `clean` and the PR heads to
round 2 and auto-merge carrying the regression. Only the main session reading every medium by hand catches it.

It has happened in four runs now:

- Run 2026-10-11-1434: round-1 `clean` hid a new regression (memory note on that batch).
- Run 2026-10-11-0401: guard regressions in round-2 mediums.
- Run 2026-10-11-2219, three of 15 PRs, each needing an owner-approved hand repair before round 2:
  - #1055 lost three detections in the requests exception guard.
  - #1061 let workers edit a recorded `stray_worktree`, the exact tree todo 577 #5 denies.
  - #1063's runbook told the operator to "keep both sides" of a todo-file conflict, which corrupts it.

The signal is already in the reviewers' prose ("flagged on main but quiet here", "regression vs main"). The
schema just has no field for it.

## Proposed Solution

- Add `regression: boolean` to the reviewer FINDINGS schema in `.claude/workflows/todo-review.js`. Prompt the
  reviewer to set it only when the PR head behaves worse than origin/main on the same input, with the probe
  as evidence.
- Treat a `medium` with `regression: true` as blocking in round 1, so the round-1 repair fixes it and the
  refuters judge it like a high.
- In round 2, a regression medium blocks like a high, so the owner sees it through `hand-round`.

## Acceptance Criteria

- [x] The reviewer schema carries `regression` and the prompt says when to set it. A `test_workflows.js` case
      shows a medium regression entering `blocking` in round 1, and a medium without it staying a follow-up.
- [x] Round 2: a medium regression blocks the group (`ingest-review` → blocked), with a `test_state_flow.py`
      or `test_state.py` case.
- [x] `completing-todos` SKILL.md Stage C drops the manual "read round-1 mediums for regressions" step, or
      keeps it as a fallback, and says which.

## Work Log

### 2026-10-11 - Filed from run 2026-10-11-2219 (owner request)

The owner asked for a todo after the run's pattern review.

### 2026-10-11 - Owner decision: keep the manual read as a fallback

Implement the proposed `regression` flag as written. For AC 3, the owner chose to **keep** the manual
"read round-1 mediums for regressions" step in `completing-todos` SKILL.md Stage C, shortened to a fallback:
skim the mediums for wording like "vs main" or "flagged on main but quiet here" that the reviewer did not
flag. A reviewer can fail to set the flag, so the hand read stays as a backstop.

### 2026-10-16 - Implemented by the todo sweep (run 2026-10-16-1135)

- `.claude/workflows/todo-review.js`: the FINDINGS schema gains an optional boolean `regression` (optional so a
  reviewer that omits it is not refused); the shared severity text tells every lens and domain reviewer to set it
  only when the PR head behaves worse than origin/main on the same input, with the probe in the summary.
- `isBlocking` sends a medium with `regression: true` to the refuters (who are told to judge it against main) and,
  in round 1, to the repair, exactly as a high; in rounds 2 and 3 it lands in `blocking`, so `ingest-review` blocks.
- `scripts/todos/state.py`: `is_blocking` mirrors the rule, so a regression medium is never also stored as a follow-up.
- `completing-todos` SKILL.md Stage C KEEPS the manual medium read as a fallback (owner decision 2026-10-11),
  after round 1 and round 2 `clean`. The runbook had no such step before; it is added, not shortened.
- Tests: `scripts/todos/test_workflows.js` and `scripts/todos/test_state_flow.py` (`regression_medium_tests`);
  both mutation-checked by reverting the blocking predicate and the follow-up filter.

### 2026-10-16 - Verified by the todo sweep (run 2026-10-16-1135)

- AC 1: `node scripts/todos/test_workflows.js` — evidence `.sweep-evidence/g2/617-ac0.txt` (not committed), last lines:

  ```text
    PASS  529 item 3: every agentType in todo-followups.js is one the git guard limits to read-only git
    PASS  WORKER schema is identical in execute and review
    PASS  VERDICT schema is identical in execute and review

  All checks passed.
  ```

- AC 2: `python3 scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g2/617-ac1.txt` (not committed), last lines:

  ```text
    PASS  596 #2: ... and so is a phrasing merged twice into one item's `also`
    PASS  546 (beyond the cap): a re-verify brief and its entry get an absolute main_root
    PASS  546 (beyond the cap): both stray worktrees of two attempts are listed

  All checks passed.
  ```

- AC 3: `grep -n -A6 "regression fallback" .claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g2/617-ac2.txt` (not committed), last lines:

  ```text
  276-   round-2 reviewers read the full diff in fresh contexts; that is the "review before arming" step. You read
  277-   `--stat` and their verdicts only.
  278-   `held` → a critical finding was dismissed only by the refuters (in either round). `ingest-review` has
  279-   already blocked the group. Do NOT arm. Report the PR to the owner as held. Only the owner can clear a
  280-   critical. When they do, run `state.py clear-hold $RUN G --decision "<their words, dated>"`, which moves the
  ```

### 2026-10-16 - Completed by the todo sweep (run 2026-10-16-1135)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-16 - Repaired by the todo sweep (run 2026-10-16-1135)

- Round-1 review (two reviewers, same finding): a medium regression that both refuters dismiss is stored in
  the refuted lines as `medium: f:l ...`, and `_holds` in `scripts/todos/state.py` treated every line not
  starting `high: ` as a critical, so the PR was held for the owner instead of going clean.
- `_holds` now holds a labelled `critical: ` line, or a line with no `severity: file:line` label (still fail
  closed for pre-478 lines); a labelled high or medium never holds.
- `scripts/todos/test_state_flow.py` gains cases: a refuted medium regression in round 1 and in round 2 is
  clean with no open criticals, and `_holds` on unlabelled, critical, high and medium lines. Both cases fail
  against the old `_holds` and pass now.
