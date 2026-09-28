---
status: pending
priority: p3
issue_id: "468"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep v2 Part A: follow-ups from the final branch review

## Problem

The final whole-branch review of the todo sweep v2 engine (Part A) fixed its
Critical, Important and cheap Minor findings in one wave. Fifteen smaller
items were ruled follow-up, not fixed, and the re-review of that wave added
eight more, and PR #861 round 1 three more. None is reachable on today's backlog or in the first pilot, but
each is a real gap in a later sweep.

## Findings

Source: the final review of `feat/todo-sweep-v2-engine` (2026-09-27), and
the controller rulings on it. Line numbers are at the residual fix commit.

- **apply_triage is not transactional.** A mid-batch failure leaves earlier
  todos renamed, and the reset-stranded `git mv` is not idempotent on re-run
  (`scripts/todos/state.py:220`). Concrete repro (PR #861 round 1): the first
  run saves `entry["path"]` as the pending path but leaves `reset_stranded`
  set, so a rerun computes the same pending name and runs `git mv` onto
  itself, which git refuses.
- **ingest_review does not validate stage or round order.** A re-ingest of a
  stale round-1 output can overwrite `tree_id` and `verified_ac` on a group
  that is already reviewed (`scripts/todos/state.py:504`).
- **The review doc is not a single-lane resource.** Two groups sourced from
  one `docs/reviews/*.md` can both check it off and race the `-COMPLETED`
  rename (`scripts/todos/group.py:18`, `scripts/todos/land.py:396`).
- **The triager reads the local checkout.** `triage_args` passes no root, so
  the triager reads the main checkout, which can be behind origin/main
  (`scripts/todos/state.py:133`, `.claude/workflows/todo-triage.js:33`). The
  Task 15 runbook must run triage from a fresh origin/main tree.
- **`.worktreeinclude` delivery is unverified.** Nothing has shown that
  `backend/.env` and `web/.env` reach an `isolation: worktree` checkout
  (`.worktreeinclude:5-6`). This is pilot check P5.
- **A failed tree check leaves the re-added worktree on disk.** It is
  non-destructive, and the message names the path
  (`scripts/todos/state.py:632-637`).
- **The workflow harness does not schema-validate its fixtures.** The triage
  stub `{ id: 'WRONG', class: 'ready' }` is not a valid TRIAGE record
  (`scripts/todos/test_workflows.js:78`).
- **`source_review` dangles after a COMPLETED rename.** Only the archiving
  todo's own `source_review` follows the rename. Other archived todos that
  name the same review doc keep the old path (`scripts/todos/land.py:408`).
- **m1: `needs-design` and `stale` todos are re-asked every sweep.** Scan
  skips only `triage: blocked-*` (`scripts/todos/scan.py:141`), and
  apply-triage writes the triager's class verbatim
  (`scripts/todos/state.py:229`).
- **m6: worktree re-add has no `origin/<branch>` fallback.** When the local
  branch is gone, recovery fails even though the branch is pushed
  (`scripts/todos/state.py:622-626`).
- **m7: the guard allows `git -C <MAIN> add/mv/rm`.** A worker that confuses
  MAIN with WT can stage into the owner's main checkout
  (`scripts/todos/worker_git_guard.py:31`).
- **m8: review-stage reviewers are prompt-bound only.** The `general-purpose`
  and `code-review-orchestrator` reviewers are not guarded
  (`.claude/workflows/todo-review.js:157-160`,
  `scripts/todos/worker_git_guard.py:30`). Consider a guarded
  `todo-reviewer` agent type.
- **m12: three Part B carry-forwards are missing from the Task 15 text**
  (`docs/superpowers/plans/2026-09-27-todo-sweep-v2.md:3862`): triage from
  an origin/main tree; spec §7.2's "rebase on origin/main before push, and a
  non-mechanical conflict stops the group"; and pilot P1 recording that the
  isolation worktree's HEAD equals origin/main.
- **The verifier gets ids and the claimed tree id only in prose.** No
  verifier step consumes `CLAIMED_TREE`; the main session compares tree ids
  (`.claude/agents/todo-verifier.md:18`,
  `.claude/workflows/todo-execute.js:90`).
- **Retry fires only on an explicit `fail`.** A null verdict goes to
  `failed`, and the runbook retries it in a fresh worktree instead of the
  same one (`.claude/workflows/todo-execute.js:123`).

Added from the fix-wave re-review (N2, N3, the m5, m3 and F5 residuals, and
the spec):

- **N2: `_continues` ends a criterion early at a wrapped `#42` or `10.`
  line.** It treats the first as a heading and the second as a bullet, so the
  joined text differs from what a model copies and Land refuses (fails
  closed) (`scripts/todos/todofile.py:111-112`). A stricter heading test
  (`^\s*#{1,6}(\s|$)`) would close it.
- **N3: the fence stop in `_continues` is unpinned.** No test fails when the
  `FENCE_RE` clause is removed (`scripts/todos/todofile.py:112`).
- **m5 residual: `parse_dotenv` keeps an inline `# comment` in the value.**
  A secret written `KEY=value # note` masks `value # note`, and the bare
  value leaks (`scripts/todos/slot_env.py:34`).
- **m5 residual: a component printed alone is not masked.** The password
  inside `DATABASE_URL`, printed by itself, matches no whole `.env` value
  (`scripts/todos/land.py:106-116`).
- **m5 residual: a DB name that is not a prefix of the slot name is not
  masked.** `slot_env` rewrites the path to `/plant_community_w<N>`, so a
  local DB name that is not a prefix of it breaks the substring match, and
  the slotted `DATABASE_URL` with its password is quoted whole
  (`scripts/todos/land.py:106-116`, `scripts/todos/slot_env.py:47`).
- **m3 residual: `fix/todo412` shapes are no longer matched.** An id with no
  delimiter before it is missed, which fails open (the todo can be selected
  while in flight). No local ref has this shape today
  (`scripts/todos/scan.py:32`).
- **F5 residual: recorded worktrees are lost at `finish`.** `finish` deletes
  the run file once every todo is terminal (`scripts/todos/state.py:714-716`),
  so Part B must list every non-staged todo's recorded worktree at wrap-up,
  before `finish`.
- **`lanes_forbidden` omits the previous wave's lanes while it still runs.**
  It lists only the lanes of other groups in the same wave
  (`scripts/todos/state.py:386`). Wave N-1 is still executing or in review
  when wave N starts, so a file a worker edits that triage did not predict
  can collide with a PR in that wave (PR #861 round 1).
- **The m5 longest-first masking order is not pinned by a test.** Reversing
  the sort (`scripts/todos/land.py:116`) passes every test, because no
  fixture has one secret value inside another (PR #861 round 1).
- **harness-ci's `push` path filter lacks `.claude/agents/**`.**
  `test_land.py` reads `.claude/agents/todo-worker.md` (the m9 check), but
  an agent-file change pushed to main/develop does not run the job
  (`.github/workflows/harness-ci.yml:48-60`); pull requests are unfiltered
  (PR #861 round 1).
- **Spec §5.2 says `status --porcelain` is empty after staging.** Staged
  entries are listed by porcelain, so the sentence is wrong; the engine's
  clean check reads the worktree column only
  (`docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md:208`).

- **PR #861 round 2: a worker can unignore `.env` and then stage it.**
  Deleting the `.env` rule from the worktree's `.gitignore` lets a plain
  `git add -A` stage `backend/.env`. Both the guard and the
  `ensure_worktree` backstop read the edited rules
  (`scripts/todos/state.py:593-604`). Check the `.worktreeinclude` paths
  directly, or read the rules from `origin/main:.gitignore`.
- **PR #861 round 2: nothing calls `ensure-worktree` yet.** The
  force-staged-path backstop protects nothing until the Part B Land
  procedure runs `state.py ensure-worktree` before every commit and push.
  Today it appears only in the plan (`scripts/todos/state.py:638-642`).
- **PR #861 round 2: the backstop refuses a `git mv` of a tracked file that
  matches an ignore rule.** For example, a `CLAUDE.md` file. Its message
  also says "force-staged", which is wrong for that case
  (`scripts/todos/state.py:593-604`). Reword the message and keep counting
  renames as adds.
- **PR #861 round 2: two older gaps.**
  - A member blocked through `decide()` rather than the gate stays in its
    group, and its in-group dependent still runs (`scripts/todos/state.py:360-372`).
  - Todos that share a file can still form a group cycle from acyclic
    dependencies (`scripts/todos/group.py:78-86`).

## Recommended Action

1. Make `apply_triage` skip the `git mv` when the pending path already exists
   and the old one is gone, and add a re-run test.
2. Guard `ingest_review` on `stage == pr_open` and
   `review_round == round - 1`.
3. Add a `review:<path>` lane before the first `docs/reviews`-sourced batch,
   and rewrite sibling `source_review` values on a COMPLETED rename.
4. Add a `root` field to `triage_args` and a `ROOT:` line to the triage
   prompt, pointing at a scratch origin/main worktree. Add the three m12
   items to the Task 15 runbook text.
5. Record the pilot results for P1 and P5 in the pilot log.
6. Remove a re-added worktree when its tree check fails, or name it in the
   wrap-up.
7. Add a tiny fixture validator to `test_workflows.js` once pilot P6 shows
   real record shapes.
8. Skip `needs-design` and `stale` todos that have an `owner_decision` and no
   change since, or write `blocked-owner` when Decide blocks them.
9. Fall back to
   `git worktree add --no-track -b <branch> <target> origin/<branch>`.
10. Deny an allowed write subcommand whose `-C` target is outside the
    agent's worktree, and add a guarded `todo-reviewer` agent type.
11. Decide whether the verifier should compare `CLAIMED_TREE` itself, and
    whether a null verdict should retry in the same worktree.

## Technical Details

- Engine: `scripts/todos/state.py`, `scan.py`, `group.py`, `land.py`,
  `worker_git_guard.py`.
- Agents: `.claude/agents/todo-worker.md`, `todo-verifier.md`,
  `todo-triager.md`.
- Workflows: `.claude/workflows/todo-execute.js`, `todo-review.js`,
  `todo-triage.js`.
- Spec: `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`
  (§4.1, §5.2, §7.2).
- Tests: `python3 scripts/todos/test_<module>.py`,
  `node scripts/todos/test_workflows.js`,
  `bash .claude/hooks/test-guard-todo-worker-git.sh`.

## Acceptance Criteria

- [x] Re-running `apply-triage` after a mid-batch failure succeeds, with a test.
- [x] `ingest-review` refuses an output whose round does not follow the
      group's `review_round`, with a test.
- [x] Two groups sourced from one review doc never share or neighbour a wave,
      with a test.
- [x] Triage reads todos from an origin/main tree, and the Task 15 runbook
      says so.
- [x] Pilot P5 records whether `backend/.env` and `web/.env` reach a worker
      worktree.
- [ ] A failed tree check in `ensure-worktree` leaves no new worktree behind,
      or the wrap-up lists it.
- [ ] `test_workflows.js` rejects a fixture that does not match its schema.
- [ ] Archiving the last finding of a review doc updates every archived
      todo's `source_review` that named it.
- [x] A `needs-design` or `stale` todo the owner already answered is not
      re-asked by the next sweep, with a test.
- [ ] `ensure-worktree` recovers from `origin/<branch>` when the local branch
      is gone, with a test.
- [ ] The guard denies `git -C <MAIN> add`, `mv` and `rm` for guarded agents,
      with a test.
- [ ] Review-stage reviewers run as a guarded agent type, or the decision
      not to is recorded here.
- [x] The Task 15 runbook text carries the three m12 carry-forwards.
- [ ] The verifier either consumes `CLAIMED_TREE` or the prompt drops it,
      and the decision is recorded here.
- [ ] The retry-on-null-verdict decision is recorded here.
- [ ] A wrapped continuation line starting with `#42` or `10.` stays part
      of its criterion, with a test.
- [ ] A test fails when the fence stop in `_continues` is removed.
- [ ] `parse_dotenv` strips an inline `# comment` from unquoted values, with
      a test.
- [ ] A `DATABASE_URL` password printed on its own is masked in a quoted
      evidence tail, with a test.
- [ ] A slotted `DATABASE_URL` is masked whatever the local DB name, with a
      test.
- [x] `fix/todo412`-style branch names count as in flight, or the decision
      not to is recorded here.
- [x] The Part B wrap-up lists every non-staged todo's recorded worktree
      before `state.py finish`.
- [x] Spec §5.2 no longer says `status --porcelain` is empty after staging.
- [x] `lanes_forbidden` includes the lanes of the previous wave while that
      wave is not merged, with a test.
- [ ] A test with overlapping `.env` values fails when the masking sort is
      reversed.
- [x] harness-ci's `push` paths include `.claude/agents/**`.
- [ ] A worker cannot stage a `.worktreeinclude` path, even after it has
  edited `.gitignore`.
- [x] The Part B Land procedure runs `state.py ensure-worktree` before
  every commit and push.
- [ ] The backstop's message names the real cause, and a `git mv` of a
  tracked ignored-pattern file is handled deliberately.
- [x] A `decide()`-blocked member leaves its group and blocks its in-group
  dependents. Shared-file groups cannot form cycles from acyclic
  dependencies.

## Work Log

### 2026-09-27 - Filed from the final branch review

- The final review of todo sweep v2 Part A ruled these fifteen items
  follow-up. The fix wave on `feat/todo-sweep-v2-engine` fixed C1, I2-I5
  and m2-m5, m9-m11.

### 2026-09-27 - Residuals added from the fix-wave re-review

- Added N2, N3, three m5 leak paths, the m3 delimiter-less shape, the F5
  wrap-up step and the spec §5.2 correction. N1, N4 and the m5 command leak
  were fixed in the same commit that added these.

### 2026-09-27 - PR #861 round 1 non-blocking findings added

- Added the `lanes_forbidden`, masking-order and harness-ci path items, and
  the apply-triage self-`git mv` repro to the existing idempotency item.
  B-1 to B-3 were fixed in the same commit.

## Notes

p3: none of these is reachable on today's backlog or in the first pilot.
m12 and the triage-root item should land before Part B's first real sweep.

### 2026-09-28 - Six criteria closed by Part B (branch feat/todo-sweep-v2-skills)

- **Triage root.** `state.py triage-args --root <tree>` adds an absolute root,
  `todo-triage.js` passes it as a `root:` line, and `todo-triager.md` reads the
  todo and code under it. Checked by `test_state.py` and `test_workflows.js`
  (`triage: a root reaches every triager prompt (todo 468)`). Stage A of the
  runbook creates the origin/main tree before triage and passes `--root`.
- **P5.** The pilot results table records both: "neither harness worktree had it …
  `web/.env` still not delivered". The open part moves to todo 472.
- **m12.** The runbook's Stage A triages an origin/main tree. Stage D step 7
  rebases on origin/main before a push, stops the group on a non-mechanical
  conflict, and re-records `tree_id` after a clean rebase so `ensure-worktree`
  doesn't read it as lost work. The third item is a pilot record, not a runbook
  step: the results doc's Stage B section has
  `git -C <WT> merge-base HEAD origin/main` → `c478ea8d` (= origin/main).
- **F5.** New `state.py worktrees RUN` lists every unarchived todo's recorded
  worktree, including a reopened todo's earlier attempts. The wrap-up runs it before
  `finish`, and `todo-resume` runs it before restart or discard.
- **Spec §5.2** now says porcelain shows nothing in the worktree column; staged
  entries are still listed.
- **ensure-worktree.** Stage D step 1 runs it before the commit and step 8 before
  the push (after any rebase); a Stage C repair runs it before its commit and again before its push.

### 2026-09-28 - Slice A: planning and ingest correctness (branch fix/todo-468-engine-state)

- **apply-triage rerun.** The run file is saved only on success, so a rerun after a
  mid-batch failure still had the in_progress path. The rename is skipped when the
  pending file already exists, the Work Log line is not repeated, and `reset_stranded`
  is cleared once done (`test_state.py`, three `468:` checks, red against main first).
- **ingest-review order.** Every group must be `pr_open` at `review_round == round - 1`,
  checked before anything is written (`test_state_flow.py`). The R4 fixture that
  re-ingested round 1 now resets `review_round`, as a fresh round 1 would.
- **Review-doc lane.** `scan` loads `source_review`, the run entry keeps it, and
  `group.review_lane` adds `review:<doc>`, so two groups from one doc are never in
  the same or a neighbouring wave. `group.lane_doc` describes it in the brief
  (`test_group.py`, `test_state_flow.py`).
- **needs-design / stale.** An owner who blocks one has answered it: `apply-triage`
  writes `triage: blocked-owner` with the answer as `blocked_on`, which scan already
  skips until the file changes. A todo skipped for this run keeps its class and is
  asked again (`test_state.py`, through `scan.select`).
- **`fix/todo412`.** Decision: count it. `ID_RE` also accepts an id right after
  `/todo`; `todos412` still does not match (`test_scan.py`).
- **Previous wave's lanes.** `execute_args` forbids the lanes of every wave N-1 group
  with a todo not yet merged (`test_state_flow.py`, both directions).
- **harness-ci** push paths include `.claude/agents/**`.
- **Owner-blocked member and cycles.** A member blocked or skipped after grouping
  leaves its group like a gate-blocked one, and its in-group dependents block with
  it. `group.plan` refuses a cycle among the todos themselves, then merges every
  group on a group-level cycle into one group (`test_group.py`, `test_state_flow.py`).
- All nine engine suites pass.

### 2026-09-28 - PR #869 round 1

- Three blocking findings fixed. The review lane now applies only to a
  `docs/reviews/*.md` source_review; real todos share archived-todo paths there,
  which Land never touches. A retried member blocked after regrouping leaves its
  group; it still carried its first attempt's `wave`. `apply_grouping` seeds the
  planner with the lanes of the run's last unmerged wave, and `execute_args` refuses
  a group that holds a lane the previous wave still holds. Before, it dropped that
  lane from `lanes_forbidden`.
- One cheap non-blocking fix: `blocked-owner` is written only when the owner's own
  decide blocked the todo, not after a worker block that followed a "ready" answer.
- The other four non-blocking findings went to todo 474.
