---
status: completed
priority: p3
issue_id: "658"
tags: [todo-sweep, engine, land]
dependencies: []
---

# A verified group can still be refused at Land on the worker's own pass flag

## Problem

The engine has two different rules for "verified", and a group can pass one
and fail the other. A group the engine has already called verified then blocks
at Land, and the only way through is a full rebuild.

In run 2026-10-18-0439 (todo 657), the first worker (group g1) ran out of time
before its full backend suite finished. It recorded that criterion in
`ac.json` as `"pass": false`, with an empty evidence file
(`.sweep-evidence/g1/657-ac2.txt`, 0 bytes). The independent verifier then ran
the same suite itself: 5552 passed, 8 skipped, exit 0. It returned `verdict:
pass` with all 3 criteria `verified: true`, and `ingest-execute` set the todo
to `verified`.

At Land, `land.py flip-acs` refused that criterion, because it ticks a box only
when the worker's `pass` is true, the verifier agreed, and an evidence file
exists (`scripts/todos/land.py`, the check
`entry["pass"] is True and index in agreed and evidence`). It returned
`remaining: [2]`. The runbook then calls for `set-group … blocked`, and
`--reverify` is refused for a block at Land. The only route left is a plain
reopen: a fresh worker and a fresh worktree. That cost a second full execute,
about 21 minutes (PR #1154 came from group g2).

The verifier's own run is never used as evidence. So any worker that runs out
of time on a slow criterion blocks at Land like this, however clean the
verifier's run.

## Findings

- `ingest-execute` accepts a verdict of `pass` even when a criterion's worker
  entry has `pass: false`. The disagreement is first noticed at Land, after
  the worktree has been treated as finished.
- The verifier does not write an evidence file that `flip-acs` could quote.
  Its result is a short note in the verdict (`"my run: … 5552 passed, 8
  skipped, exit 0"`).
- Possible fixes (choose at triage; not prescribed):
  1. `ingest-execute` treats a worker `pass: false` on a verifier-verified
     criterion as a failure. The todo then takes the normal `failed` → retry
     path, with no block at Land.
  2. The verifier writes its own evidence file for each criterion it re-runs,
     and `flip-acs` can tick a box on the verifier's agreement plus that file
     when the worker's run did not finish. This keeps "never on the worker's
     word alone" and adds no hand path.
  3. The worker brief starts long criteria (the full suite) early, in the
     background, so they finish within the worker's budget. This makes the
     problem less likely but does not remove the gap.
- Related, seen in the same run: `flip-acs` quotes the last lines of the
  evidence file. For a full pytest run those lines can be shutdown logging
  (a Sentry/logging traceback), not the `N passed` summary. Round-1 review of
  PR #1154 flagged that the quoted evidence shows no pass. The summary was
  line 481 of 519.

## Acceptance Criteria

- [x] A group whose verifier verified every criterion, while the worker's
      `ac.json` has `pass: false` on one of them, no longer reaches Land and
      blocks there. Either it fails earlier, at `ingest-execute`, into the
      normal retry path, or Land ticks it on verifier-owned evidence. A test in
      `scripts/todos/` drives that case.
- [x] The criterion `flip-acs` ticks is never ticked on the worker's word
      alone. The existing tests for that still pass.
- [x] The completing-todos runbook describes the chosen behaviour.

## Work Log

### 2026-10-18 - Filed

- Filed at the owner's request after run 2026-10-18-0439. Group g1 was
  blocked at Land as described above, then 657 was reopened. Group g2 merged
  as PR #1154.

### 2026-10-24 - Implemented by hand

- Chose fix 1, placed where it saves the re-run: the verifier
  (`.claude/agents/todo-verifier.md` step 3) marks an entry with a command
  and `pass` not true `verified: false`, note `worker run incomplete`, so
  the workflow's in-place retry worker re-runs just that criterion. A
  failure at `ingest-execute` alone would only reach `failed → ready`, a
  fresh worktree, the same ~21 minutes.
- Backstop in code: `state.worker_ac_problem` reads the worker's `ac.json`
  and `ingest_execute(worker_ac=…)` fails the whole group, `worker evidence
  incomplete`, when a criterion with a command lacks the worker's pass. An
  unreadable `ac.json` fails closed. Re-pointed, owner-confirmed and
  external entries (no command, `pass: false`) are exempt.
- Fix 2 declined: it gives the read-only verifier a write path and splits
  evidence between two owners. Fix 3 added to the worker spec (start a
  slow suite early, in the background).
- Related finding fixed: `land._tail` now leads the quoted tail with the
  last pytest summary line when shutdown logging pushed it out.
- AC 1: `python3 scripts/todos/test_state_flow.py` → 549 PASS, 0 FAIL,
  including "658: a verifier-verified criterion the worker did not pass
  fails the group at ingest" and the CLI case, each with a mutation check
  that fails with the guard removed.
- AC 2: `flip_acs` is unchanged (still `entry["pass"] is True and index in
  agreed and evidence`); `python3 scripts/todos/test_land.py` → 302 PASS,
  0 FAIL. The rest of the harness-ci list (todofile, state, scan, group,
  slot_env, `node scripts/todos/test_workflows.js`) passes.
- AC 3: `.claude/skills/completing-todos/SKILL.md` Execute step 3
  describes the ingest refusal and the verifier's retry.

### 2026-10-24 - Completed

- Archived by hand; verification is quoted above.
