---
name: completing-todos
description: The todo engine. Drives selected todos through scan, triage, one batch of owner decisions, parallel implementation in worktrees, independent verification, a two-round review, and a merged PR that archives each todo. Invoked by todo-sweep, todo-batch and todo-next, or directly — "finish todo NNN", "complete the pending todos", /completing-todos.
---

# Completing Todos — the engine (todo sweep v2)

**Announce:** "I'm using the completing-todos engine (todo sweep v2)."

Design: `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`. Pilot evidence:
`docs/superpowers/specs/2026-09-27-todo-sweep-pilot-results.md`. This file is the main-session
runbook. `scripts/todos/*.py` own every state change and file edit. The named workflows
`todo-triage`, `todo-execute` and `todo-review` own the fan-out. Running them is sanctioned: the user invoked a
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
`TRIAGE_WT` = `$SCRATCH/triage-$RUN_ID`. Run scripts from REPO with absolute paths. Use `/usr/bin/git`
(rtk hides pre-commit failures).

## Sandbox

The spec §11 settings are applied: `gh`, `git push` and the kimi gate run sandboxed. Never `push -u`:
the upstream write to `.git/config` is denied. Workers' pytest reaches Postgres and Redis over the Unix
sockets in `sandbox.network.allowUnixSockets` through `slot_env.py` (spec §7.3), so no worker or verifier
needs the sandbox off. A worker that blocks on "no database" means a socket is missing:
`ls /tmp/.s.PGSQL.5432 /tmp/redis.sock`.

**Sandbox-off steps** (pilot, 2026-09-28). `todo-execute` creates each group's worktree under
`REPO/.claude/worktrees/`. The sandbox allows writes there only while that workflow runs. Once it
finishes, run these steps with the sandbox off, and no others:

- Stage D steps 1–6 and 8, and a Stage C repair commit: `ensure-worktree`, `land.py`, `git add`,
  `git branch -m`, `git commit` and a rebase in `$WT`.
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
4. `python3 scripts/todos/state.py record-triage $RUN --output <task output file>`
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
| `stale` | "Supersede" / "Keep" | Supersede: re-point each open criterion (`→ todo NNN (re-pointed $TODAY)`) and archive the todo as `superseded` inside the triage PR, then `skipped --decision "superseded: …"`. Keep: `blocked --decision …` |
| stranded (`in_progress`, nothing in flight) | "Reset to pending" / "Leave it" | `ready --reset-stranded` / `blocked --decision …` |
| `needs-research` | none needed | `ready` (a planner runs first) |

## Triage PR (skip for selector `next`)

1. `python3 scripts/todos/state.py apply-triage $RUN --repo $TRIAGE_WT --today $TODAY`.
   Only **after** this, do the `stale` → supersede edits and moves from Decide. `apply-triage` writes to each
   todo's current path, so a todo moved first makes it fail.
2. `/usr/bin/git -C $TRIAGE_WT add todos` → `git diff --cached --stat` must list only `todos/`
   → commit `chore(todos): triage run $RUN_ID` → `git push origin chore/todo-triage-$RUN_ID`
   → `gh pr create` → `gh pr merge --auto --squash --delete-branch`.
3. Execute does not start until `gh pr view <n> --json state` says `MERGED`. Then `git -C REPO fetch origin main`
   and `git -C REPO worktree remove $TRIAGE_WT`.

For `next`: remove the detached `$TRIAGE_WT` once Decide is done. Run step 1 with `--repo <the worker's worktree>`
during Land, before `land.py`, and commit it with the todo.

## Group

`python3 scripts/todos/state.py group $RUN` → waves and unschedulable todos (blocked with reasons).
With `--limit N`, execute only the first ⌈N / workers⌉ waves and list the deferred groups in the summary.

## Stage B — Execute (per wave W, in order)

1. `python3 scripts/todos/state.py execute-args $RUN --wave W --main-root REPO` → `{run_id, briefs}`.
   It refuses while wave W−1 is still executing or wave W−2 is not merged. Then Land those first.
   An empty wave (`[]`) means wait for wave W−2 to merge, then move on.
2. `Workflow({name: "todo-execute", args: <that object>})` runs in the background. Meanwhile, land wave W−1.
3. On the notification: `python3 scripts/todos/state.py ingest-execute $RUN --output <task output file>`.
4. `failed` todos: retry once in a later wave with `state.py set $RUN <id> ready`, then `state.py group $RUN`
   (it appends new groups and waves). A second failure: `state.py set $RUN <id> blocked --field reason="…"`.
5. `blocked` todos: report the blocker to the owner. When it is cleared (a fix merged, a decision made),
   reopen the todo: `state.py set $RUN <id> ready --field reason="<what cleared it>"`, then
   `state.py group $RUN`. This does not spend the retry. It is refused for a todo with a PR; fix that
   PR instead. Reopen any todo that execute-args blocked as `dependency <id> blocked` the same way.
   The blocked attempt's worktree stays under `previous` in RUN; `state.py worktrees $RUN` lists it.

## Stage D — Land (per `verified` group G of wave W, one at a time)

Steps 1–6 and 8 run with the sandbox off (see **Sandbox**).

1. `WT=$(python3 scripts/todos/state.py ensure-worktree $RUN G --scratch $SCRATCH/worktrees)`
2. `/usr/bin/git -C $WT diff --cached --stat` — the only view of the change you take.
3. For each todo id in G: `python3 scripts/todos/land.py flip-acs --run $RUN --id <id> --repo $WT --date $TODAY`.
   If `remaining` has a criterion that is not a re-point, stop this group:
   `state.py set-group $RUN G blocked --field reason="criteria not verified: …"`.
4. For each todo id: `python3 scripts/todos/land.py archive --run $RUN --id <id> --repo $WT --date $TODAY`
   → stage exactly its `paths`: `/usr/bin/git -C $WT add <paths…>` (after `git mv`, re-add the new path).
5. Rename the branch to the repo convention: `/usr/bin/git -C $WT branch -m <type>/<id>-<slug>`, then
   `state.py annotate $RUN G --field branch=<new>`.
6. Commit the index only (never `-a`): `/usr/bin/git -C $WT commit -m "<type>(<scope>): <summary> (todo <id>)" -m "<2–4 bullets from the WORKER summary>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
   If the kimi gate prints `timed out; skipping gate`, record `kimi: skipped` (never "passed").
7. Re-run step 1 (`ensure-worktree` before every push, too).
8. Rebase when origin/main moved (spec §7.2): `/usr/bin/git -C $WT fetch origin main`; if
   `/usr/bin/git -C $WT merge-base --is-ancestor origin/main HEAD` fails, `/usr/bin/git -C $WT rebase origin/main`.
   A conflict outside `todos/` and append-only docs (`docs/LEARNINGS.md`, `docs/rules/*.md`) is not
   mechanical: `git rebase --abort`, then `state.py set-group $RUN G blocked --field reason="rebase conflict: <paths>"`.
   After a clean rebase, record the new tree, or the next `ensure-worktree` reads it as lost work:
   `state.py annotate $RUN G --field tree_id=$(/usr/bin/git -C $WT write-tree)`.
9. `/usr/bin/git -C $WT push origin <branch>` (no `-u`) → `gh pr create --head <branch> --title … --body …`. The body gives
   the todo ids, the WORKER summary, verification counts, flagged test edits, the `kimi:` status and the Claude Code footer.
   Then `state.py set-group $RUN G pr_open --field pr=<n>`.

## Stage C — Review (per wave, after its PRs are open)

1. `python3 scripts/todos/state.py review-args $RUN --round 1 --wave W` → `Workflow({name: "todo-review", args})`
   → `python3 scripts/todos/state.py ingest-review $RUN --output <file> --round 1`.
   - `clean` → round 2.
   - `repair-staged` → `ensure-worktree`, `git -C $WT diff --cached --stat`, commit `fix: address review round 1 (todo <id>)`,
     `ensure-worktree` again, push, then round 2.
   - `rerun` → run round 1 again once. A second `rerun`: `set-group … blocked`.
   - `blocked` → report it.
2. Round 2: `review-args --round 2` → workflow → `ingest-review --round 2`. `clean` →
   `gh pr merge <n> --auto --squash --delete-branch`. The round-2 reviewers read the full diff in fresh
   contexts; that is the "review before arming" step. You read `--stat` and their verdicts only.
   `blocked` → stop that PR and report it. When a group has `checklist_skipped`, add a PR comment saying the
   checklist review could not run (`gh pr comment <n> --body …`), and list it in the wrap-up.
3. Read each round's `ranges`. When one says `inline review` or `no Agent tool available`, the deep
   `/code-review` pass did not run inside the workflow (pilot P8). The verdict still stands, but list the PR
   in the wrap-up as "deep review fell back inline".
4. Follow-ups: todos with `followups` get one follow-up todo file per PR (next free id, `p4`, the PR number
   in its Findings), all committed together in a closing `chore(todos): follow-ups from run $RUN_ID` PR.

## Merge confirmation and cleanup

For each `reviewed` group: `gh pr view <n> --json state` → `MERGED` → `state.py set-group $RUN G merged`
→ `/usr/bin/git -C REPO worktree remove $WT` (pushed and merged, so nothing is lost) → `state.py set-group $RUN G archived`.
Both git steps run with the sandbox off. Finish with `/usr/bin/git -C REPO worktree prune`: in the sandbox,
`worktree remove` deletes the directory but not `.git/worktrees/<name>`.

## Wrap-up

1. `python3 scripts/todos/state.py worktrees $RUN` lists every unarchived todo's recorded worktree,
   earlier blocked attempts included. Put each in the summary. `finish` deletes RUN, and with it the only
   record of where that staged work is.
2. `python3 scripts/todos/state.py finish $RUN` removes the run file only when every todo is terminal.

The summary lists: merged PRs, blocked todos with reasons, skipped todos, the worktrees from step 1,
owner hand-offs (prod, device and vendor steps are never attempted), the `kimi: skipped` count,
PRs whose deep review fell back inline, deferred groups (`--limit`), and the follow-ups PR.

## Safety rails

1. **Acceptance criteria are gospel.** A box flips only through `land.py flip-acs` (worker pass + verifier
   agreement + evidence file). The only exception is a re-point naming a numbered target
   (`→ todo NNN (re-pointed DATE)`). `scripts/check_archived_todo_status.py` enforces this in CI.
2. **External verification leaves evidence in the file:** the date and the observed result, quoted.
   "Verified" alone is not evidence.
3. **No destructive recovery.** Never reset, force-push, delete or `git checkout --` to recover. Stop and report.
4. **Two review rounds.** Round 2 never repairs; non-blocking findings become follow-up todos.
5. **One committer.** Workflows never commit, push or call `gh`; `guard-todo-worker-git.sh` enforces it for
   workers and verifiers.
6. **Never read production.** A todo needing prod data is `blocked-prod` and an owner hand-off.
7. **Only `state.py` writes the run file; stage names never go in `status:`.**
8. **The sandbox goes off only for the steps listed under Sandbox.**
