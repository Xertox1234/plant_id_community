---
name: completing-todos
description: The todo engine. Drives selected todos through scan, triage, one batch of owner decisions, parallel implementation in worktrees, independent verification, a two-round review, and a merged PR that archives each todo. Invoked by todo-sweep, todo-batch and todo-next, or directly — "finish todo NNN", "complete the pending todos", /completing-todos.
---

# Completing Todos — the engine (todo sweep v2)

**Announce:** "I'm using the completing-todos engine (todo sweep v2)."

Design: `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`. Pilot evidence:
`docs/superpowers/specs/2026-09-27-todo-sweep-pilot-results.md`. This file is the main-session
runbook. `scripts/todos/*.py` own every state change and file edit. The named workflows
`todo-triage`, `todo-execute`, `todo-review` and `todo-followups` own the fan-out. Running them is sanctioned: the user invoked a
skill whose instructions call Workflow.

**Stay lean.** Hold only records and `--stat` output. Never read a worker's diff, evidence files, or
a workflow transcript in full. The scripts read the workflow task output files for you.

**Retired rails** (spec §4.1, 2026-09-27). "Never auto-commit" and "`--parallel` reserved" are replaced
by: one committer (this session), workflows never commit (hook-enforced), and one merged PR per todo group.

## Inputs

From the selector skill: `selector` (sweep | batch | next); filters `--priority`, `--ids`, `--tag`,
`--exclude-ids`; `--workers N` (1–3, default 3; next forces 1); `--limit N` (groups this run);
`--retriage`; `--dry-run`. "finish todo NNN" means `batch --ids NNN --workers 1`.

Names used below: `REPO` = the main checkout root; `RUN_ID` = `date -u +%Y-%m-%d-%H%M`;
`RUN` = `REPO/todos/.sweep-run-$RUN_ID.json`; `SCRATCH` = the session scratchpad; `TODAY` = `date +%Y-%m-%d`;
`TRIAGE_WT` = `$SCRATCH/triage-$RUN_ID`; `GH_REPO` = `gh repo view --json nameWithOwner -q .nameWithOwner`,
run once in REPO. Run scripts from REPO with absolute paths. Use `/usr/bin/git`
(rtk hides pre-commit failures).

**Arming auto-merge** (todo 512): always `gh pr merge <n> --repo $GH_REPO --auto --squash --delete-branch`, run
from REPO, never from inside a PR's worktree. When the checks have already passed, `--auto` merges at once, and
without `--repo` gh then deletes the local branch and tries to remove the worktree that has it checked out. The
sandbox stopped that part-way on PR #904 and left 358 tracked files deleted. With `--repo`, gh leaves local git
alone; it still deletes the remote branch.

## Sandbox

The spec §11 settings are applied: `gh`, `git push` and the kimi gate run sandboxed. Never `push -u`:
the upstream write to `.git/config` is denied. Workers' pytest reaches Postgres and Redis over the Unix
sockets in `sandbox.network.allowUnixSockets` through `slot_env.py` (spec §7.3), so no worker or verifier
needs the sandbox off. A worker that blocks on "no database" means a socket is missing:
`ls /tmp/.s.PGSQL.5432 /tmp/redis.sock`.

**Sandbox-off steps** (pilot, 2026-09-28). Each group's worktree lives under `REPO/.claude/worktrees/`;
`state.py execute-args` creates it there (todo 528), and the sandbox does not allow the main session to write
there. Run these steps with the sandbox off, and no others:

- Stage B step 1, `execute-args` (it runs `git worktree add` and copies the `.worktreeinclude` files).
- Stage D steps 1–8, a Stage C repair commit, and the empty commit that restarts a wedged CI run and the
  `DIRTY` recovery merge (Merge confirmation): `ensure-worktree`, `land.py`, `git add`, `git branch -m`,
  `git commit`, a rebase and a merge of origin/main in `$WT`.
- Cleanup: `git worktree remove $WT`, then `git worktree prune`.

A step that fails for any other reason is not a sandbox problem; stop and report it.

## Stage 0 — Scan

1. `git worktree list` — a peer session may hold todos; scan excludes them, but say so.
2. `python3 scripts/todos/scan.py --selector <s> --run-id $RUN_ID [filters] --workers N [--retriage] --dry-run`
3. Show the plan (Selected / Excluded with reasons / cleanup candidates). If `--dry-run`, stop.
   Otherwise ask once: proceed / cancel.
4. Re-run the same command without `--dry-run` → writes RUN.
   An old `todos/.completing-todos-run-*.json` is from the v1 skill: point the user to `todo-resume`.

## Stage A — Triage

Triage reads a fresh origin/main tree, never REPO: the main checkout can sit on another branch or
behind origin/main (todo 468).

1. `/usr/bin/git -C REPO fetch origin main`, then
   `/usr/bin/git -C REPO worktree add --no-track -b chore/todo-triage-$RUN_ID $TRIAGE_WT origin/main`.
   For selector `next`, use `--detach` instead of `--no-track -b …`; there is no triage PR.
   (`--no-track`: without it git writes upstream config to `.git/config`, which the sandbox denies.)
2. `python3 scripts/todos/state.py triage-args $RUN --root $TRIAGE_WT` → `{"todos": […], "root": …}`.
3. `Workflow({name: "todo-triage", args: <that object>})`. Wait for the notification.
4. `python3 scripts/todos/state.py record-triage $RUN --output <task output file> --root $TRIAGE_WT`
   (`--root` turns a triager's absolute `$TRIAGE_WT/…` paths back into repo-relative ones, which the lanes need)
5. `python3 scripts/todos/state.py accept-ready $RUN`
6. `python3 scripts/todos/state.py questions $RUN`

## Decide — one batch of owner questions

Ask every question from step 6 in as few AskUserQuestion calls as possible (≤ 4 per call). Never
answer one yourself. Record each answer with `python3 scripts/todos/state.py decide $RUN <id> <outcome> [flags]`:

| Class / situation | Options to offer | Record |
|---|---|---|
| `ready` with a question | the question's options | `ready --decision "<answer> ($TODAY)"` |
| `blocked-*`, `needs-design` | "Unblocked: …" / "Still blocked" / "Skip this run" | `ready --decision …` / `blocked --decision "<why>"` / `skipped` |
| `already-done` | "Archive as done (verify only)" / "Not done" | `ready --verify-only` / `ready` |
| `stale` | "Supersede" / "Keep" | Supersede: re-point each open criterion (`→ todo NNN (re-pointed $TODAY)`; put the marker at the end of the criterion's checkbox line, or of its last wrapped line, since both parsers read a wrapped criterion as one unit, todo 572) and archive the todo as `superseded` inside the triage PR, then `skipped --decision "superseded: …"`. Keep: `blocked --decision …` |
| stranded (`in_progress`, nothing in flight) | "Reset to pending" / "Leave it" | `ready --reset-stranded` / `blocked --decision …` |
| `needs-research` | none needed | `ready` (a planner runs first) |

## Triage PR (skip for selector `next`)

1. `python3 scripts/todos/state.py apply-triage $RUN --repo $TRIAGE_WT --today $TODAY`.
   Only **after** this, do the `stale` → supersede edits and moves from Decide. `apply-triage` writes to each
   todo's current path, so a todo moved first makes it fail.
2. `/usr/bin/git -C $TRIAGE_WT add todos` → `git diff --cached --stat` must list only `todos/`
   → commit `chore(todos): triage run $RUN_ID` → `git push origin chore/todo-triage-$RUN_ID`
   → `gh pr create` → arm it (see **Arming auto-merge**).
3. Execute does not start until `gh pr view <n> --json state` says `MERGED`. Then `git -C REPO fetch origin main`
   and `git -C REPO worktree remove $TRIAGE_WT`.

For `next`: remove the detached `$TRIAGE_WT` once Decide is done. Run step 1 with `--repo <the worker's worktree>`
during Land, before `land.py`, and commit it with the todo.

## Group

`python3 scripts/todos/state.py group $RUN` → waves and unschedulable todos (blocked with reasons).
With `--limit N`, execute only the first ⌈N / workers⌉ waves and list the deferred groups in the summary.

## Stage B — Execute (per wave W, in order)

1. `/usr/bin/git -C REPO fetch origin main`, then, with the sandbox off,
   `python3 scripts/todos/state.py execute-args $RUN --wave W --main-root REPO` → `{run_id, briefs}`.
   Waves start at 0: a fresh run's first call is `--wave 0`.
   It cuts each worker group's worktree from origin/main (`REPO/.claude/worktrees/sweep-$RUN_ID-<group>`, branch
   `worktree-sweep-$RUN_ID-<group>`, `--no-track`) and records it on the brief and on each todo before any agent
   runs (todo 528), so a worker that dies still leaves its worktree in RUN for `state.py worktrees`. A rerun
   reuses a worktree it already made; anything else at that path is refused.
   It refuses while wave W−1 is still executing or wave W−2 is not merged. Then Land those first.
   An empty wave (`[]`) means wait for wave W−2 to merge, then move on.
2. `Workflow({name: "todo-execute", args: <that object>})` runs in the background. Meanwhile, land wave W−1.
3. On the notification: `python3 scripts/todos/state.py ingest-execute $RUN --output <task output file>`.
   It also compares each staged todo's Acceptance Criteria with the merge-base ones (todo 494): any change but a
   re-point the run recorded fails the todo, `acceptance criteria were edited`. A worker that reports a worktree
   other than the one it was given fails too.
4. `failed` todos: retry once in a later wave with `state.py set $RUN <id> ready`, then `state.py group $RUN`
   (it appends new groups and waves). The failed attempt's worktree, tree, evidence and re-points move to
   `previous` (todo 494): the retry gets a fresh worktree, and a retried todo is never re-verified in place.
   A second failure: `state.py set $RUN <id> blocked --field reason="…"`.
5. `blocked` todos: report the blocker to the owner. When it is cleared (a fix merged, a decision made),
   reopen the todo with `state.py set $RUN <id> ready --field reason="<what cleared it>"`, and also every
   todo that execute-args blocked as `dependency <id> blocked`, transitively: in a chain A→B→C, C's reason
   names B, not A. Then run `state.py group $RUN` **once**, after
   all of them are reopened. A dependent that is grouped while its dependency is still blocked gets blocked again.
   Reopening doesn't spend the retry. It is refused for a todo with a PR; fix that PR instead.
   The blocked attempt's worktree stays under `previous` in RUN, and `state.py worktrees $RUN` lists it.

   **A worker blocked only on an owner-only criterion** (todo 492) leaves finished, staged work and no
   verdict. A plain reopen gives the todo a fresh worker in a new worktree. When the owner moves that
   criterion to another todo instead, keep the work:
   - Create the target todo (`todos/<NNN>-pending-…md`) in the blocked worktree and `git add` it.
   - `state.py repoint $RUN <id> --index <i> --to <NNN> --decision "<owner's words> ($TODAY)" --date $TODAY`
     (`<i>` is 0-based, as in `ac.json`; the target must be the new todo from the step above).
     It adds the marker to the criterion, stages it, fixes `ac.json`, and records the re-point. The
     verifier accepts only re-points the brief lists, so never re-point one by hand.
   - `state.py set $RUN <id> ready --reverify --field reason="…"`, then `group` and `execute-args` as
     above. Only a one-todo attempt its first worker blocked qualifies: Land commits the worktree's whole
     index, and a tree a verifier already judged is never judged again. So `--reverify` is refused for
     a multi-todo attempt, a worktree any other todo ever recorded, and a block from a retry worker, a
     verifier, Land or the owner. Reopen those the plain way. `group` gives each re-verified todo its own
     group and its own wave, before the planned ones; a dependent reopened with it waits in
     `execute-args` until it merges. The workflow skips the planner and the worker and
     verifies the worktree as it is. Don't touch the worktree after `execute-args`: it records the tree
     the verdict must match. `execute-args` refuses a re-verify whose worktree is gone, or whose index
     changed since the block outside the todo file and each re-point's new target todo (todo 494); block
     the todo and reopen it the plain way.
   - `repoint` takes only a blocked todo or one reopened with `--reverify`, a real `--date YYYY-MM-DD`, and a
     target number no other todo in RUN already re-points to. Rerun on a later day, it keeps the marker
     already on the line.
   - **Runs written before PR #885** have no `blocked_by`, so `--reverify` refuses a todo whose first worker
     did block it (todo 423 in run 2026-09-28-2018). Backfill it once, only when the todo has `attempts: 0`,
     no verdict, and a `reason` that is the worker's blockers:
     `state.py annotate $RUN <group> --field blocked_by=worker`. Never for any other block.
   - **A dead verifier strands a re-verify** (todo 494 F14, owner decision 2026-10-02): two null verdicts
     make the todo `failed` with `no verdict`. No verifier judged that tree, but `--reverify` stays refused
     (it needs a block by the first worker). Retry it the usual way (`set … ready`, a fresh worker); the
     re-pointed work is in `previous` for the owner to compare. There is no other path.
   - **An owner-only criterion the owner confirmed** (todo 492, owner decision 2026-10-10) — a prod email
     arrived, a header is present — is ticked at Land, not hand-closed. After Decide (Decide writes
     `owner_decision` over) and before `execute-args`, run `state.py confirm $RUN <id> --index <i> --decision
     "<the owner's words>" --date $TODAY` for each such criterion: a ready todo, or a blocked one before its
     reopen (`--reverify` when its first worker blocked only on that criterion). The brief carries it, the worker
     records it `owner-confirmed`, the verifier accepts only listed ones, and `flip-acs` ticks the box and quotes
     the owner's words in the Work Log. Never tick one by hand.
   - A wave the run deferred (`--limit`) blocks every later wave. Block its todos with the reason
     `deferred by --limit` first, and list them in the wrap-up.

## Stage D — Land (per `verified` group G of wave W, one at a time)

Steps 1–8 run with the sandbox off (see **Sandbox**).

1. `WT=$(python3 scripts/todos/state.py ensure-worktree $RUN G --scratch REPO/.claude/worktrees)`
   (`--scratch` is where a lost worktree is re-added. Keep it under `.claude/worktrees/`: the worker git guard
   denies a repair worker's `git add` anywhere else, todo 618.)
2. `/usr/bin/git -C $WT diff --cached --stat` — the only view of the change you take.
3. For each todo id in G: `python3 scripts/todos/land.py flip-acs --run $RUN --id <id> --repo $WT --date $TODAY`.
   If `remaining` has a criterion that is not a re-point, stop this group:
   `state.py set-group $RUN G blocked --field reason="criteria not verified: …"`.
4. For each todo id: `python3 scripts/todos/land.py archive --run $RUN --id <id> --repo $WT --date $TODAY`
   (it refuses a todo whose Work Log names a home path, `/Users/<name>` or `/home/<name>`, as CI's tripwire
   does: make those lines repo-relative by hand, `git add`, and archive again; todo 492)
   → stage exactly its `paths`: `/usr/bin/git -C $WT add <paths…>` (after `git mv`, re-add the new path).
5. Rename the branch to the repo convention: `/usr/bin/git -C $WT branch -m <type>/<id>-<slug>`, then
   `state.py annotate $RUN G --field branch=<new>`. A reopened todo (todo 473) may find that name taken: an
   earlier attempt already renamed its branch, and that attempt's worktree (under `previous`) still has it
   checked out, so `branch -m` fails. Never delete or force-move it. If `/usr/bin/git -C $WT rev-parse
   --abbrev-ref HEAD` already prints the name, skip the rename. Otherwise, when
   `/usr/bin/git -C REPO rev-parse --verify --quiet refs/heads/<type>/<id>-<slug>` succeeds, rename to
   `<type>/<id>-<slug>-<n>` instead, with `<n>` = the todo's attempts so far + 1 (the first free one), and name
   the old branch and its worktree in the wrap-up.
6. Commit the index only (never `-a`): `/usr/bin/git -C $WT commit -m "<type>(<scope>): <summary> (todo <id>)" -m "<2–4 bullets from the WORKER summary>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
   If the kimi gate prints `timed out; skipping gate`, record `kimi: skipped` (never "passed"). The pre-commit
   gate (`scripts/kimi-precommit.sh`) may take up to 300 s, so give this Bash call `timeout: 600000`. The
   PreToolUse kimi hook is capped at 300 s too, but it matches only a command that starts `git commit`, so it
   does not run on this `/usr/bin/git -C` commit.
   If a pre-commit fixer rewrote files, the commit aborted and the rewrites sit unstaged, so `ensure-worktree`
   refuses them. Stage exactly the paths it rewrote, NUL-separated so git never C-quotes a path (todo 514):
   `/usr/bin/git -C $WT diff --name-only -z | xargs -0 /usr/bin/git -C $WT add --`, then re-run step 1 and
   commit again. Step 1 accepts only `trailing-whitespace` and `end-of-file-fixer` rewrites: a path passes when its new
   contents are exactly those two fixers' output on the verified ones, on a file they treat as text (todo 513).
   A refusal means the diff is a real change, or another configured fixer rewrote the file (black, isort,
   prettier, dart-format, `markdownlint --fix`, `mixed-line-ending`). Either way, stop the group. Since todo 540
   the worker runs `pre-commit run --files <staged>` before it writes its tree, so a Black or detect-secrets stop
   here is rare; it means that step was skipped, and the owner decided `ensure-worktree` stays strict.
7. Rebase when origin/main moved (spec §7.2): `/usr/bin/git -C $WT fetch origin main`; if
   `/usr/bin/git -C $WT merge-base --is-ancestor origin/main HEAD` fails, `/usr/bin/git -C $WT rebase origin/main`.
   A conflict outside `todos/` and append-only docs (`docs/LEARNINGS.md`, `docs/rules/*.md`) is not
   mechanical: `git rebase --abort`, then `state.py set-group $RUN G blocked --field reason="rebase conflict: <paths>"`.
   After a clean rebase, record the new tree, or the next `ensure-worktree` reads it as lost work:
   `state.py annotate $RUN G --field tree_id=$(/usr/bin/git -C $WT write-tree)`.
8. Re-run step 1 right before the push: `ensure-worktree` runs before every commit and every push.
9. `/usr/bin/git -C $WT push origin <branch>` (no `-u`) → `gh pr create --head <branch> --title … --body …`. The body gives
   the todo ids, the WORKER summary, verification counts, flagged test edits, the `kimi:` status and the Claude Code footer.
   Then `state.py set-group $RUN G pr_open --field pr=<n>`.

## Stage C — Review (per wave, after its PRs are open)

0. Before `review-args` in every round, run `ensure-worktree` (Stage D step 1) for each group in the wave.
   `review-args` runs `git diff` in each PR worktree to compute `changed_files`, so a worktree the harness
   swept away makes it exit 2 for the whole wave.
1. `python3 scripts/todos/state.py review-args $RUN --round 1 --wave W` → `Workflow({name: "todo-review", args})`
   → `python3 scripts/todos/state.py ingest-review $RUN --output <file> --round 1`.
   Read `review-args`' `residue` key first (todo 484): a group listed there still holds what an earlier attempt
   at this round left, so it was left out of `prs` and gets no review. Handle each one per step 5.
   - `clean` → round 2.
   - `repair-staged` → `ensure-worktree`, `git -C $WT diff --cached --stat`, commit `fix: address review round 1 (todo <id>)`,
     `ensure-worktree` again, push, then round 2.
   - `rerun` → run round 1 again once. The run file counts it (`review_reruns`, todo 478), so a second
     incomplete round (`rerun` or `residue`) comes back `blocked` from `ingest-review` itself. Re-ingesting the
     same output file never counts twice (todo 497). A group blocked `review round N was incomplete twice` has
     a PR, so a reopen and `clear-hold` both refuse it. When the owner approves one more try, run
     `state.py release-incomplete $RUN G --decision "<their words, dated>"`: it goes back to `pr_open` with
     round N-1 done and that round's count one short of the limit, so the next incomplete review of that round
     (the third) blocks it again (todo 546). Once per round: then it stays blocked.
   - `residue` → see step 5. Nothing was repaired.
   - `held` (todo 482) → a critical was dismissed only by the refuters, so the PR would be held at round 2 anyway;
     `ingest-review` has already blocked the group. Do not commit, push or run round 2. Report it as in step 2's
     `held`. If the reason says a verified repair waits staged, it stays uncommitted for the owner. When the
     owner clears it, `clear-hold` moves the group back to `pr_open` with round 1 done: commit and push a staged
     repair as for `repair-staged`, then round 2. The cleared lines do not hold again; a new critical does.
   - `blocked` → report it.
2. Round 2: `review-args --round 2` → workflow → `ingest-review --round 2`. Read `review-args`' `residue` key
   first, as in step 1, and handle each group in it per step 5. Then read its `not_ready` key (todo 543). A group
   listed there was left out of `prs` because its PR is not ready for review: HEAD is not pushed (its
   `refs/remotes/origin/<branch>` differs). For a round 3, it may also be that HEAD has not moved since
   `hand-round`, or that the repair edited acceptance criteria. Do what its reason says, then run `review-args`
   again; that does not count as a rerun. For every outcome except
   `rerun` and `residue`, first post the refuter-dismissed findings: run `state.py refuted-comment $RUN G --out
   $SCRATCH/refuted-G.md`. If it prints a path, run `gh pr comment <n> --body-file <that path>`. Never
   build `--body` from the findings: they are LLM text, and this step runs with the sandbox off.
   `clean` → then arm it (see **Arming auto-merge**). The round-2 reviewers read the full
   diff in fresh contexts; that is the "review before arming" step. You read `--stat` and their verdicts
   only.
   `held` → a critical finding was dismissed only by the refuters (in either round). `ingest-review` has
   already blocked the group. Do NOT arm. Report the PR to the owner as held. Only the owner can clear a
   critical. When they do, run `state.py clear-hold $RUN G --decision "<their words, dated>"`, which moves the
   group to `reviewed`, then arm.
   `rerun` → run round 2 again once. A second incomplete round 2 comes back `blocked`; report it.
   `residue` → do NOT arm; see step 5.
   `blocked` → stop that PR and report it. Its reason also names any dismissed critical the owner must clear.
   **Owner-approved round 3** (todo 542). When the owner approves one more round for a PR that round 2 blocked
   on blocking findings, run `state.py hand-round $RUN G --decision "<their words, dated>"`. It refuses a held
   group, any other block, and a second call. It moves the group back to `pr_open` with round 2 done. Then
   commit the owner's repair in the PR worktree, run `/usr/bin/git -C $WT rev-parse HEAD^{tree}` on its own, then
   `state.py annotate $RUN G --field tree_id=<that tree>`. Run `ensure-worktree`, push, and run `review-args $RUN --round 3 --wave W` → workflow →
   `ingest-review --round 3`. `review-args` enforces that order (todo 543). It leaves the group out of `prs`,
   listed under `not_ready`, until HEAD has moved since `hand-round` and been pushed, and while the repair edits
   an acceptance criterion. `ingest-review` refuses an output file whose results name another round. Round 3
   runs as round 2 does: there is no repair, it takes its own residue
   baseline, and it stores follow-ups and refuted lines. Its outcomes are the same as round 2's: post the
   refuted comment, then `clean` → arm, `held` → `clear-hold` → `reviewed`, `blocked` → the owner's hand-off
   for good. There is no round 4. Never run a round on a copy of the run file, and never build its args by hand.
   `.claude/skills/` is write-denied in the main checkout's sandbox, so edit this runbook in a worktree.
3. What a round runs, for every size: three `todo-reviewer` bug lenses, plus the checklist lane.
   `review-args` computes each PR's `changed_files` from its worktree's diff. The workflow applies the
   orchestrator table's path rules to that list and always dispatches those reviewers, each with its own
   files. `code-review-orchestrator` (Phase 1 only) can add reviewers, never remove them; `floor_added`
   names the ones it missed. A dead router (todo 481) still leaves the path-routed reviewers to run
   (`routing_failed: true`); the round counts as complete only when no changed `.py` outside `apps/blog/` could
   need wagtail-reviewer by content. The router greps through `git -C WT grep` over a pathspec, so no changed
   file's name reaches a shell. No subagent can spawn subagents (pilot P8), so all fan-out is in the workflow
   script. Each critical/high file:line then faces two refuters and stops blocking only if both refute every
   phrasing reported there. A dead reviewer makes the round `rerun`, never a partial pass. The run file keeps each
   todo's `refuted` findings whole (`<severity>: file:line summary | also: …`, never capped, one line per severity
   and file:line across both rounds). List them in the wrap-up, so the owner can see what the refuters dismissed.
4. Follow-ups: `ingest-review` stores a group's non-blocking findings once per group (todo 529), as
   `<severity>: file:line summary | also: …`, one line per file:line with every phrasing, the most severe
   first, capped at 10 with `followups_dropped` counting what the cap left out. Once the wave's PRs have
   merged (Merge confirmation and cleanup, below, moves each group to `merged`):
   - `/usr/bin/git -C REPO fetch origin main` first: the curator and the refuter read origin/main, and a PR
     whose code is not on it would read every item it added as `fixed`. `followups-args` takes only `merged`
     or `archived` groups (a `reviewed` one waits for its merge), and the curator checks that the PR's
     `(#<pr>)` squash commit is on origin/main; when it is not, the group stays `uncurated` with nothing dropped.
   - `state.py followups-args $RUN --main-root REPO` → `Workflow({name: "todo-followups", args})` →
     `state.py ingest-followups $RUN --output <task output file>`. Per PR, one curator merges duplicates and
     checks each item on origin/main, then one refuter tries to refute every item, with the curator's `fixed` claim
     where it made one; an item drops out only when the refuter refutes it (todo 541), and `followups-md` lists
     what dropped. An item the curator left out is kept as stored. A dead curator leaves the stored list, marked
     `uncurated`, and `followups-args` offers an uncurated group again on the next run. The `refuted` lines never go
     through it.
   - For each group, `state.py followups-md $RUN G --out $SCRATCH/followups-G.md` writes its Findings: each
     item with its severity, the cap's dropped count, and the refuted lines under their own heading so the
     owner can re-judge them.
   - One follow-up todo file per PR with follow-ups or `refuted` lines (a group with only refuted lines gets
     no curation but still gets one, from `followups-md`): next free id, `p4`, the PR number and that Findings text, all
     committed together in a closing `chore(todos): follow-ups from run $RUN_ID` PR. A group still held or
     blocked is an owner hand-off in the wrap-up, not a p4 follow-up. Its dismissed criticals are already on
     the PR and in its block reason.
5. `residue` (todo 480): an agent of the review changed the PR worktree, so the reviewers did not all read what
   ships, and a round-1 repair's `git add -A` would have committed it. `review-args` records a baseline per
   round (HEAD, plus every path `git add -A` would take, with its content hash). The workflow checks it before
   a round-1 repair, and `ingest-review` checks it in code whenever no repair ran. Nothing from the round is
   kept. `state.py residue $RUN G` lists the paths that still differ (the run file keeps what was found under
   each todo's `review_residue`). Show them to the owner, and ask before removing or restoring any of them.
   When `residue` prints `{"changed": []}`, rerun the round; that counts as its one rerun. A rerun keeps the
   round's baseline, so until the worktree matches it again, `review-args` leaves the group out of `prs` and
   lists it with its paths under `residue`. The wave's other groups carry on.
   Files that were already untracked when the round started (a worker's artifact; Land commits only the index)
   are in the baseline, so they are not residue. The round-1 repair stages only the paths it changed and leaves
   them alone (todo 483): `review-args` lists them as `untracked_before`, the repair and its verifier are told
   about them, and `ingest-review` blocks a repair that staged one.

## Merge confirmation and cleanup

For each `reviewed` group: `gh pr view <n> --json state` → `MERGED` → `state.py set-group $RUN G merged`
→ `/usr/bin/git -C REPO worktree remove $WT` (pushed and merged, so nothing is lost) → `state.py set-group $RUN G archived`.
Both git steps run with the sandbox off. Finish with `/usr/bin/git -C REPO worktree prune`: in the sandbox,
`worktree remove` deletes the directory but not `.git/worktrees/<name>`.

**A wedged CI job** (todo 512) can hold an armed PR open indefinitely. On PR #906 a Web CI run stayed
`in_progress` for over 80 minutes, and `gh run cancel`, the API's `force-cancel` and `gh run rerun` each
refused it. When a required check has shown `in_progress` far past its usual time and those refuse, start a fresh run
with an empty commit, sandbox off: `ensure-worktree` (Stage D step 1) →
`/usr/bin/git -C $WT diff --cached --quiet HEAD` must succeed (todo 513: `ensure-worktree` compares the index
with the recorded tree, not with HEAD, so it lets a staged `todos/`, `docs/reviews/`, `.secrets.baseline` or
fixer-only edit through, and the commit would push it unreviewed; if it fails, stop and look at what is staged) →
`/usr/bin/git -C $WT commit --allow-empty -m "ci: restart a wedged check run (todo <id>)"` → check that
`/usr/bin/git -C $WT rev-parse HEAD^{tree}` and `/usr/bin/git -C $WT rev-parse HEAD~1^{tree}` print the same
tree → `ensure-worktree` again → `/usr/bin/git -C $WT push origin <branch>`. The tree is unchanged, so
`ensure-worktree` accepts it exactly as before and the reviews still hold; both kimi gates skip an empty diff. Then check that auto-merge
is still armed (`gh pr view <n> --repo $GH_REPO --json autoMergeRequest`) and arm it again if not.

**Waiting on an armed PR** (todo 601). A merge conflict is not a check: when a peer PR merges first and
leaves a conflict, GitHub reports it only as `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING`, and every
check can stay green while auto-merge never fires (PRs #1035 and #1040, `docs/LEARNINGS.md` 2026-10-11 "An
armed PR stalled on a conflict no check reported"). So a poll or loop that waits on an armed PR reads
`gh pr view <n> --repo $GH_REPO --json state,mergeStateStatus,mergeable,statusCheckRollup`, not the checks
alone, and stops on any of: `MERGED`, `CLOSED`, a failed required check, or `mergeStateStatus` `DIRTY`.
Treat `DIRTY` as a stop, never as "still waiting", and recover it as below.

**An armed PR that goes `DIRTY`** (todo 601). Recover it with the sandbox off, in this order:

1. `ensure-worktree` (Stage D step 1), then `/usr/bin/git -C $WT fetch origin main`.
2. `/usr/bin/git -C $WT merge --no-commit --no-ff origin/main` — a merge commit,
   never a rebase plus force-push: the branch is already pushed and reviewed, and a force-push rewrites what
   the reviewers read. `--no-commit` stops even a clean merge here, so steps 4–6 run before the commit
   exists.
3. Resolve the conflicts. Only these are mechanical:
   - `todos/` files — rebuild from origin/main, never concatenate both sides (that leaves duplicate `status:`
     keys and doubled criteria and Work Log lines). In this merge "ours" is the branch and "theirs" is
     origin/main. Two paths are in play, and they differ when this branch archived the todo: `<branch path>`
     is the todo's path on this branch (the archived `completed` name), `<main path>` its path on origin/main
     (the pre-archive `pending` name, which is the only one origin/main has). First save the branch's side, so
     a tick or Work Log entry missed below is never lost, and check the save before going on:
     `/usr/bin/git -C $WT show HEAD:<branch path> > $TMPDIR/<name>.branch` must exit 0, and
     `test -s $TMPDIR/<name>.branch` must pass. Read it from `HEAD`, not stage `:2:`: HEAD is the branch side
     either way, while `:2:` is at the `completed` name only when git saw the archive as a rename (a heavy
     archive edit makes it a modify/delete at the `pending` name instead), and a failed `show` still leaves an
     empty file behind the `>` (todo 637). Then write origin/main's version to a scratch file, and only once
     that `show` succeeded copy it over the conflicted file:
     `/usr/bin/git -C $WT show origin/main:<main path> > $TMPDIR/<name>.main`.
     Then re-apply this branch's own changes from the saved copy by hand — its criteria ticks, its Work Log
     entries, its archive move;
   - append-only docs (`docs/LEARNINGS.md`, `docs/rules/*.md`) — keep both entries, origin/main's first;
   - `.secrets.baseline` — only its `generated_at` and the `line_number` values: take origin/main's
     `generated_at`, and fix each line number against the merged file. The baseline is hand-maintained;
     never regenerate it with a scan.

   Any other conflict stops the group for the owner. Disarm first, so nothing merges it before the owner
   resolves it: `gh pr merge <n> --repo $GH_REPO --disable-auto` (from REPO). Then
   `/usr/bin/git -C $WT merge --abort`, then
   `state.py set-group $RUN G blocked --field reason="merge conflict with origin/main: <paths>"`, and report
   the PR in the wrap-up as blocked with auto-merge disarmed. Never resolve a source conflict by hand.
4. Re-run the group's gates on the merged tree: the non-empty `command` of every criterion in its `ac.json`
   (a criterion does not name the files it covers, so run them all), and `pre-commit run --files <resolved
   paths>` (`SKIP=kimi-review`). `pre-commit` also exits 1 when a fixer (`trailing-whitespace`,
   `end-of-file-fixer`) only rewrote a resolved file, which is not a failure: stage the paths it rewrote
   (`/usr/bin/git -C $WT add -- <rewritten paths>`) and run it again. It fails only when a hook still fails on
   that second run with nothing left to rewrite (todo 637). If any gate fails, the merge broke the group: never
   commit or push it, since auto-merge is still armed and would merge it with no one looking. Stop the group as
   for a non-mechanical conflict above (disarm, `merge --abort`, `set-group $RUN G blocked`), with the failing
   command in `reason`.
5. `/usr/bin/git -C $WT add -- <resolved paths>`, then record the merged tree before anything checks it:
   `state.py annotate $RUN G --field tree_id=$(/usr/bin/git -C $WT write-tree)`.
6. Commit the merge with the kimi gate skipped, and record it: `state.py annotate $RUN G --field
   kimi_recovery=skipped` (no other value is accepted), which `finish` reports once per group for the wrap-up's
   `kimi: skipped` total (todo 647), since the PR body is already
   written (owner decision 2026-10-11, todo 616): mid-merge the staged diff is everything origin/main brought
   in, already reviewed in its own PRs, so a CRITICAL or a timeout there would block the recovery on code this
   PR never wrote. The skip also covers the hunks resolved by hand in step 3 (the `todos/` rebuilds, the
   `.secrets.baseline` line numbers, todo 637): those follow the fixed rules of step 3, and detect-secrets and
   the other hooks still run on them.
   `SKIP_KIMI_REVIEW=1 /usr/bin/git -C $WT commit --no-edit` (`timeout: 600000`, as in Stage D step 6). The
   other pre-commit hooks still run. If a fixer rewrote files, the commit aborted: stage exactly the paths it
   rewrote (as in Stage D step 6), re-run the gates (step 4) and record the tree again (step 5), then commit
   again. A hook failure no fixer resolves stops the group as in step 4.
7. `ensure-worktree` again, then `/usr/bin/git -C $WT push origin <branch>` (no `-u`, no `--force`).
8. Confirm auto-merge is still armed (`gh pr view <n> --repo $GH_REPO --json autoMergeRequest,mergeStateStatus`)
   and arm it again if not (see **Arming auto-merge**). Then go back to waiting.

## Wrap-up

1. `python3 scripts/todos/state.py worktrees $RUN` lists every unarchived todo's recorded worktree,
   earlier blocked attempts included, and a landed todo's earlier blocked attempts too (todo 473: cleanup
   removes only the worktree that landed; the others are left for the owner). Put each in the summary.
   `finish` deletes RUN, and with it the only record of where that staged work is.
2. `python3 scripts/todos/state.py finish $RUN` first prints `kimi_recovery=skipped: N group(s): …`, each group
   annotated `kimi_recovery=skipped` once (todo 647; `state.py kimi-skipped $RUN` prints the same list as JSON
   without finishing). It then removes the run file only when every todo is terminal, and
   refuses (exit 1, naming them) while any group is held for the owner (todo 482): `clear-hold` needs the run
   file. Leave it in place and report the held PRs.

The summary lists: merged PRs, blocked todos with reasons, skipped todos, the worktrees from step 1,
owner hand-offs (prod, device and vendor steps are never attempted), the `kimi: skipped` count (Stage D
step 6 timeouts plus the N groups annotated `kimi_recovery=skipped` by a DIRTY recovery, as `finish` printed them),
findings the refuters dismissed (per PR), deferred groups (`--limit`), and the follow-ups PR.

## Safety rails

1. **Acceptance criteria are gospel.** A box flips only through `land.py flip-acs` (worker pass + verifier
   agreement + evidence file), or, for an owner-only criterion, the owner's dated `state.py confirm` record plus
   verifier agreement (todo 492). The only exception is a re-point naming a numbered target
   (`→ todo NNN (re-pointed DATE)`). `scripts/check_archived_todo_status.py` enforces this in CI.
2. **External verification leaves evidence in the file:** the date and the observed result, quoted.
   "Verified" alone is not evidence.
3. **No destructive recovery.** Never reset, force-push, delete or `git checkout --` to recover. Stop and report.
4. **Two review rounds.** Round 2 never repairs; non-blocking findings become follow-up todos.
5. **One committer.** Workflows never commit, push or call `gh`; `guard-todo-worker-git.sh` enforces it for
   workers and verifiers. `guard-todo-worker-edit.sh` keeps a worker's edits inside a worktree (todo 541).
6. **Never read production.** A todo needing prod data is `blocked-prod` and an owner hand-off.
7. **Only `state.py` writes the run file; stage names never go in `status:`.**
8. **The sandbox goes off only for the steps listed under Sandbox.**
