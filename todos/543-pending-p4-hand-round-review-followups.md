---
status: pending
priority: p4
issue_id: "543"
tags: [todo-sweep, engine, follow-ups]
dependencies: []
---

# Todo sweep: follow-ups from the `/code-review` of PR #987 (todo 542, hand round 3)

## Problem

A medium-effort `/code-review` of `0b27e92e` (PR #987) found nine issues. The PR filing this todo fixed
four: todo-resume's unpushed-repair check now covers a hand-round group, `--wave` was added to the runbook
command, `hand_round` was added to `ATTEMPT_FIELDS`, and root CLAUDE.md now names the round-3 exception.
One more is refuted: no run file written before #987 exists, so the "no `blocked_by` on old round-2 blocks"
case cannot happen. The four below are real but not blocking.

## Findings

1. **medium** `scripts/todos/state.py:1062`. Neither `review-args --round 3` nor `ingest-review --round 3`
   checks that the owner's repair is committed, recorded in `tree_id` and pushed; only the runbook says so.
   If round 3 reviews the local worktree, comes back clean and is armed while the push was skipped, the PR
   merges without the repair. Round 1's repair-then-push has the same gap. A fix could have `review-args`
   (rounds 2 and 3) refuse when `HEAD` differs from `ls-remote origin <branch>`, and have `hand_round`
   record HEAD and refuse round 3 until it moves. That would close both rounds.
2. **medium** `scripts/todos/state.py:1466`. A round-2 output file ingested with `--round 3` is accepted.
   The stale-output guard reads only group state, and the workflow result carries no round. A wrong
   `--output` would spend the owner's one round 3 on stale round-2 findings. Fix: the todo-review workflow
   echoes `round` in each result, and `ingest_review` refuses a mismatch when it is present.
3. **low** `scripts/todos/state.py:1283`. The owner's round-3 repair never runs the acceptance-criteria
   check (`review_criteria`) or a verifier. A hand repair that edits an AC line merges with round 1's
   `verified_ac`. Consider running `review_criteria` on the annotated tree at `ingest-review --round 3`.
4. **low** `scripts/todos/state.py:1062`. Round 3 is special-cased in three places through
   `hand_round == 3`. A single `max_round` field on the entry (default 2, set to 3 by `hand_round`) would
   keep the cap in one place. Do this only if 1 or 2 touches these lines anyway.

## Acceptance Criteria

- [ ] Each finding above is fixed (with a test, and for a guard a guard-removed mutant), or closed with a
      dated reason.

## Work Log

- 2026-10-10: Filed from the post-merge `/code-review` of PR #987 at the owner's request.
