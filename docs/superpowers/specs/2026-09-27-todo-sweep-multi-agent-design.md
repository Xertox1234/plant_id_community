# Todo Sweep v2 — Multi-Agent, Workflow-Driven Design

**Date:** 2026-09-27
**Status:** Draft — awaiting owner review
**Replaces:** the single-context loop in `.claude/skills/completing-todos/` and
its wrappers `todo-sweep`, `todo-batch`, `todo-next`, `todo-resume`

## 1. Why

`completing-todos` was written for older models: one agent walks every pending
todo sequentially, in one context window, and `--parallel` was "reserved for
future work". In practice that design fails in nine recorded ways:

1. The single context window fills after a few todos.
2. Many todos are gated (owner decision, prod access, credentials, device,
   design call); the sweep finds this out late, after spending effort.
3. Parallel agents in worktrees broke each other — moving the controller with
   `EnterWorktree` revoked a sibling's Bash access
   (memory: `project_worktree_parallel_dispatch_conflict`).
4. Backend pytest shares one test DB; concurrent runs produce fake failures.
5. Sandboxed subagents cannot commit (kimi gate false "STALE" via `/dev/fd`;
   `gh` TLS failure) — the working split became "agents stage, orchestrator
   commits".
6. Hot files (`settings.py`, `.secrets.baseline`) conflict across parallel PRs.
7. The real delivery unit is one **merged PR** per todo/slice (review r1 →
   repair → r2), not an uncommitted tree — the skill's "never commit" rail is
   already superseded in practice (memory: `feedback_todo_slice_means_merged_pr`).
8. Todos left `in_progress` are invisible to every future sweep (discovery greps
   `^status: pending`); 8 were stranded on 2026-09-13.
9. Agents check boxes without evidence; verification must be independent.

## 2. Goals and non-goals

**Goals**

- The main session's context stays roughly flat per todo: it holds compact
  records, never worker transcripts or raw tool output.
- Gated todos are identified before any implementation, and every owner question
  for a run is asked **once, in one batch**.
- Up to 3 todos/groups are implemented concurrently without file, worktree,
  test-DB or Redis collisions.
- Every completed todo ends as a merged PR that also archives the todo file.
- No todo can be stranded in a status no sweep sees.
- A completion claim is accepted only when a different agent re-ran the evidence.

**Non-goals**

- Parallel commits/pushes. One committer (the main session) is a design choice,
  not only a sandbox workaround.
- Automating owner-gated work (prod reads, vendor dashboards, device checks).
  Those are classified and handed off, never attempted.
- Cheap-worker (Kimi) delegation inside the engine — user rule: explicit request only.

## 3. Decisions taken in brainstorming (2026-09-27)

| Decision | Choice |
|---|---|
| Scope | **Shared engine.** `completing-todos` becomes the engine; `todo-sweep` / `todo-batch` / `todo-next` are selectors; `todo-resume` resumes from the run file. |
| Triage data | **Split.** Durable facts in todo frontmatter (landed by a triage PR); per-run progress in a gitignored run file. |
| Land | **Arm auto-merge** after the main session reviews the PR diff and round 2 is clean. |
| Parallelism | **3 workers** by default (`--workers N`), after a 2-worker pilot passes. |
| Orchestration | **Approach A:** stage workflows (Triage, Execute, Review) + serial Land in the main session. |
| Agents | Four role-based agents: `todo-triager`, `todo-worker`, `todo-verifier`, and the existing reviewers. |

Rejected: B (main session + background `Agent` calls — prompt-driven loop,
context grows per result, not deterministically resumable); C (one end-to-end
workflow — workflow agents are sandboxed subagents and cannot commit or run `gh`
today).

## 4. Architecture

```text
 main session (lean; the only committer)
 ├─ Stage 0  Scan      scripts/todos/scan.py              → run file
 ├─ Stage A  Triage    Workflow todo-triage   (N × todo-triager)
 │           Group     scripts/todos/group.py             → lanes, waves
 │           Decide    AskUserQuestion batch  → owner_decision
 │           Triage PR frontmatter facts → merged before Execute
 ├─ Stage B  Execute   Workflow todo-execute  (per wave ≤ 3 groups)
 │                     [planner?] → todo-worker (worktree) → todo-verifier
 ├─ Stage C  Review    Workflow todo-review   (per wave, round 1 and round 2)
 │                     reviewers → repair worker → verifier
 └─ Stage D  Land      main session, serial per group:
                       evidence → AC boxes → archive → commit → push → PR
                       → r1 → repair commit → r2 → auto-merge
```

Waves are pipelined across stages: while wave N is in Review/Land, wave N+1 may
Execute **if** it has no dependency on wave N and shares no single-lane resource
with it (§7).

### 4.1 Components

**New**

| Path | Role |
|---|---|
| `.claude/agents/todo-triager.md` | Read-only classifier. `tools: Read, Grep, Glob`. Returns one TRIAGE record (§6.1). |
| `.claude/agents/todo-worker.md` | Sole writer for its group. Full tools. Plans, implements, tests, writes evidence, stages, **stops at staged**. Isolation is passed per call (`isolation: 'worktree'` in Execute; omitted for repair, which must work in the PR's existing worktree) — **not** set in frontmatter, where it would force a fresh worktree on every call. |
| `.claude/agents/todo-verifier.md` | Independent evidence checker. `disallowedTools: Edit, Write, NotebookEdit`. Re-runs every AC command in the worker's worktree. Bash can still write, so its read-only-ness is **enforced by the tree-hash check in §5.2**, not by its tool list. |
| `.claude/workflows/todo-triage.js` | Named workflow: `pipeline(todos, triager)`; returns records. |
| `.claude/workflows/todo-execute.js` | Named workflow: `pipeline(groups, [planner], worker, verifier)`; returns WORKER + VERDICT records. |
| `.claude/workflows/todo-review.js` | Named workflow: `pipeline(prs, reviewers, [repair worker], [verifier])`; `args.round` = 1 or 2 (round 2 never repairs). |
| `scripts/todos/scan.py` | Stage 0 discovery (§5.0). |
| `scripts/todos/group.py` | Deterministic lanes + waves from triage records (§7). |
| `scripts/todos/state.py` | The only writer of the run file; enforces the stage transition table (§8). |
| `scripts/todos/todofile.py`, `slot_env.py`, `land.py`, `worker_git_guard.py` | Byte-preserving todo edits; per-slot env; Land's AC flip + archive; the hook's decision logic (added by the implementation plan). |
| `scripts/todos/test_*.py`, `test_workflows.js` | Tests next to the code (repo convention); the workflow tests run each script with stubbed `agent()`. |
| `.claude/hooks/guard-todo-worker-git.sh` + `test-guard-todo-worker-git.sh` | `PreToolUse` on Bash: when `agent_type` is `todo-worker` or `todo-verifier`, allow only the git subcommands `add`, `mv`, `rm`, `diff`, `status`, `log`, `show`, `fetch`, `write-tree`, `rev-parse`, and deny every other `git` subcommand (commit, push, switch, checkout, stash, rebase, reset, clean, …) and all `gh`. An allowlist, because a denylist misses branch-moving commands. |
| `.worktreeinclude` | `backend/.env`, `web/.env` — gitignored env files copied into worker worktrees. |

**Changed**

| Path | Change |
|---|---|
| `.claude/skills/completing-todos/SKILL.md` | Rewritten as the engine: Stages 0–D, the per-todo contract (AC gospel, re-points, external-verification evidence, source-review check-off, filename/frontmatter status match). Retires "never auto-commit" and "`--parallel` reserved" **on the record**, citing this spec. |
| `.claude/skills/todo-sweep/SKILL.md` | Selector: all eligible todos → engine. |
| `.claude/skills/todo-batch/SKILL.md` | Selector: `--priority/--ids/--tag/--exclude-ids` → engine. |
| `.claude/skills/todo-next/SKILL.md` | Selector: top eligible todo → engine with `--workers 1` (one wave, one group). **No separate triage PR**: a single-todo run writes its triage fields in the todo's own PR, so the daily driver does not pay an extra CI cycle. |
| `.claude/skills/todo-resume/SKILL.md` | Reads `todos/.sweep-run-*.json`; offers resume / restart / discard. Legacy `.completing-todos-run-*.json` → offer discard only. |
| `todos/TEMPLATE.md` | Documents the new optional frontmatter fields (§6.4). |
| `.claude/settings.json` | Registers the new hook. |
| `.gitignore` | `todos/.sweep-run-*.json`, `.sweep-evidence/`. |
| `scripts/check-kimi-engine.sh:16` | Replace `diff <(…) <(…)` with temp files — removes the sandbox false "STALE" (prerequisite, §11). |

**Boundaries (invariants)**

- Workflows never commit, push, or call `gh`. (Enforced by the hook for worker
  and verifier; triager has no Bash.)
- The main session never edits product code for a todo — it edits only the todo
  file, the source review doc, and state, and it commits.
- Only `state.py` writes the run file. Only a todo's own PR or the triage PR
  changes that todo's `status:` on `main`.

## 5. Data flow, stage by stage

### 5.0 Stage 0 — Scan (main session, no agents)

`scan.py --selector <sweep|batch …|next> --run-id <id>`:

- Reads the todos **at `origin/main`** (after `git fetch`), never the working
  tree. The main checkout was 45 commits behind on 2026-09-27, and reading it
  re-selected five already-archived todos. Enumerates `todos/*.md` **with a
  frontmatter block**, excluding `README.md` and `TEMPLATE.md`. Includes every non-archived status (`pending`,
  `in_progress`, `blocked`) — never a `^status: pending` grep.
- Flags **stranded** todos: `in_progress` with no live branch/worktree/open PR →
  offered back to `pending`. The rename (`git mv`) plus frontmatter edit and a
  Work Log note land in the triage PR.
- Legacy `status: blocked` (e.g. todo 387) stays valid, as `TEMPLATE.md`
  allows it. Scan includes it and triage records a `triage: blocked-*` class
  alongside it without changing `status:` or the filename. Sweeps read the gate
  from `triage:`; `status:` is never used to express a triage class.
- Excludes todos that already have an in-flight branch, worktree
  (`git worktree list`), or open PR matching the issue id — they belong to a
  peer session or a prior run. Lists them in the plan.
- Skips todos whose frontmatter says `triage: blocked-*`, unless `--retriage`
  is passed or the file has a commit dated **after** its `triaged:` date. The
  triage PR itself is the commit that writes `triaged:`, so comparing
  `triaged:` with the last commit would never fire.
- `--dry-run`: Stage 0 only, then print the plan (selected, excluded and why,
  stranded, cleanup candidates). No workflows, no file changes.
- Lists worktrees whose branch is merged into `origin/main` as cleanup
  candidates (report only; removal is an owner-confirmed step).
- Writes the run file with every selected todo at stage `scanned`.

### 5.1 Stage A — Triage

**Workflow `todo-triage`** (`args: [{id, path}]`): one `todo-triager` per todo,
pipelined, `effort: medium`. Each returns a TRIAGE record (§6.1). The triager
reads the todo and its Work Log, greps the codebase for evidence the fix
already exists, and predicts touched files from Technical Details. It has no
Bash, so it cannot change anything.

**Group** (`group.py`, main session): reads the records from the run file and
produces lanes and waves (§7). Deterministic and unit-tested — grouping is not
a model call.

**Decide** (main session): all `owner_question`s for the run are asked together
via `AskUserQuestion` (≤ 4 per call, looped). Answers are recorded verbatim as
`owner_decision`. A todo whose answer unblocks it becomes `ready`.

**Triage PR** (costs one CI cycle per run): `state.py apply-triage` writes `triage`, `blocked_on`,
`owner_decision`, `triaged` into each todo's frontmatter; the main session
commits, opens the PR, arms auto-merge, and **Execute does not start until it
merges** — worker worktrees are cut from `origin/main`, and a worker PR that
archives a todo would otherwise conflict with the triage PR on the same file.

### 5.2 Stage B — Execute

**Workflow `todo-execute`** (`args: {run_id, wave: [GroupBrief]}`), per group:

1. **Planner** (only if `triage: needs-research`): `agentType: 'todo-triager'`
   (read-only tools) with a planning prompt; returns the plan as a schema field
   (`plan`, ≤ 4000 chars) that is embedded in the worker's brief — no plan file.
   Research finding: split plan/implement only when the plan is a complete
   handoff; otherwise one worker owns plan + implement + test.
2. **Worker** — `agentType: 'todo-worker'`, `isolation: 'worktree'`, brief per
   §6.2. Implements, runs tests with its slot's resources (§7.3), writes
   `.sweep-evidence/<id>/` (command outputs + `ac.json`), updates the todo's
   Work Log, `git add`s, returns a WORKER record. It does **not** flip AC
   boxes, archive, or change `status:`.
3. **Verifier** — `agentType: 'todo-verifier'`, no isolation, told the worker's
   worktree path. Re-runs every AC command, compares with the worker's
   evidence, diffs test files vs `origin/main` and flags edited or deleted
   existing tests, returns a VERDICT record.

**Tree-hash check (enforces an independent verifier).** The worker's last step
stages everything, so `git -C <wt> status --porcelain` shows nothing in the
worktree (second) column (staged entries are still listed; evidence lives in the
gitignored `.sweep-evidence/`), and records `git -C <wt> write-tree`. The
verifier records both values as its first and last steps. Before Land, the main
session checks that all three tree ids match and that the working tree is still
clean (`status --porcelain --untracked-files=no`: untracked test artifacts don't
count, because Land commits only the index and stages exactly the paths `land.py`
reports). The staged-tree id alone would miss an unstaged `sed -i`, which is why the
clean check is also required. Any difference **voids the
verdict** (the todo goes to `failed`), because a verifier that changed the tree
has "fixed its way" to passing. This is the mechanism behind pain point 9; the
schema alone does not deliver it.

`verdict: fail` → one retry: a new worker in the same worktree with the
verifier's notes, then a new verifier. A second fail → stage `blocked`, reason
recorded; the todo returns to `pending` with a Work Log entry.

### 5.3 Stage C — Review, and Stage D — Land

Land runs in the main session, one group at a time, in wave order:

1. Read `git -C <wt> diff --staged --stat` and the VERDICT. Flip each AC box
   **only** where the verifier set `verified: true`, quoting the evidence file
   in the Work Log. Unverifiable external criteria follow Safety Rail 5 (date +
   observed result) or become re-points.
2. Archive in the same commit: frontmatter `status: completed`, `git mv` to
   `todos/archive/<id>-completed-…`, fix any `.secrets.baseline` path entry by
   filename-only edit, check off `source_review` findings (and rename the
   review doc to `-COMPLETED` when all are checked).
3. Commit (hooks run, including the kimi gate), push, `gh pr create`.

   **Worktree liveness.** The harness's periodic sweep may remove a worktree
   that has no uncommitted files and no unpushed commits, which is exactly the
   PR's worktree after step 3. Before every repair, round, or verifier retry,
   Land checks that the worktree exists. If it is gone, Land re-adds it from
   the pushed branch under the scratchpad directory
   (`git worktree add <scratchpad>/<id> <branch>`, proven to work in the
   sandbox on 2026-09-27) and updates the run file.

4. **Round 1** — `todo-review` workflow with `round: 1` for every PR landed so
   far in the wave. Pilot P8 showed that no workflow agent can spawn subagents
   ("no Agent tool available"), so neither the bundled code-review skill nor
   the orchestrator's dispatch can run inside one. Every fan-out is therefore an
   `agent()` call in the workflow script (todo 472), for **every** size:
   - **Bug lenses:** three read-only `todo-reviewer` finders over the whole diff,
     each primed on one lens (correctness; security and data; contracts, state
     and tests).
   - **Checklist lane:** `review-args` computes the PR's changed files from the
     worktree diff (never from an LLM). The workflow applies the path rules of the
     orchestrator's routing table to that list (`ROUTES`, kept in step with the table
     by a test) and always dispatches those reviewers, each with only its own files.
     `code-review-orchestrator` runs Phase 1 only and can add reviewers that paths
     can't decide, such as a wagtail import found by grep. It never removes one
     (todo 478).
   - **Refute:** each critical/high finding, deduplicated, goes to two
     `todo-reviewer` skeptics and stops blocking only if both refute it.
   - Any dead reviewer makes the round `rerun`, never a partial pass.

   Every reviewer prompt names the worktree path and the diff range explicitly
   (`git -C <wt> diff origin/main...HEAD`), because a no-isolation workflow
   agent's cwd is the main checkout. Otherwise `code-review-orchestrator`
   reads the wrong `git diff`, and the domain reviewers read the main checkout's
   files. Blocking findings → repair worker in the PR's worktree → verifier.
   Main session commits the repair.
5. **Round 2** — `todo-review` with `round: 2` (no repair). Clean → the main session
   runs `gh pr merge --auto --squash --delete-branch`. The "review the diff
   before arming" rule is met by the round-2 reviewers, which read the full PR
   diff in fresh contexts. The main session reads only `--stat` and their
   compact verdicts, never the full diff, because reading ~18 full diffs is the
   context fill this design removes. Still blocking → stop that PR
   and report. Non-blocking findings from either round → a follow-up todo file
   (CLAUDE.md review-loop budget: two rounds, never three).
6. After merge is confirmed, remove the worktree (work is pushed and merged, so
   nothing is lost) and set the stage to `archived`.

Because workflow results arrive only when a workflow finishes, the unit of
pipelining is the wave: the main session lands wave N while wave N+1 executes in
the background.

## 6. Contracts

All workflow agents return through a JSON `schema`, so the main session receives
validated objects. Free-text fields have `maxLength` to enforce compact
results (research: 1–2K tokens per result is typical; the cap must be in the
schema, because the parent receives the whole final message).

### 6.1 TRIAGE record

```json
{
  "id": "412",
  "class": "ready | blocked-owner | blocked-prod | blocked-device | blocked-external | needs-design | needs-research | already-done | stale",
  "evidence": "≤ 400 chars: what was grepped/read and what it showed",
  "blocked_on": "≤ 200 chars, or empty",
  "owner_question": "≤ 300 chars, one question, or empty",
  "predicted_files": ["backend/apps/…/views.py"],
  "size": "xs | s | m | l",
  "needs_e2e": false,
  "notes_for_siblings": "≤ 200 chars"
}
```

`already-done` and `stale` carry evidence and go to the owner batch as a
confirm question. The triager never archives. `check_archived_todo_status.py`
fails an archived todo that has any bare unchecked AC, including a `superseded`
one, so:

- **`already-done`, confirmed:** the todo runs through Execute as a
  **verify-only** group. The worker changes no code and gathers evidence for
  each AC, the verifier re-runs it, and Land archives it as usual.
- **`stale`, confirmed:** each open AC is re-pointed to a numbered todo or
  checked with evidence, then archived as `superseded` in the triage PR. If the
  owner can do neither, it stays `pending` with `triage: stale` and the
  `owner_decision` recorded.

### 6.2 GroupBrief (input to a worker)

Self-contained, because a non-fork subagent receives only its prompt string.
It references files by path rather than copying them (workers load CLAUDE.md and
can read the repo):

- `todo_paths`, `owner_decision` (verbatim), optional `plan` text
- `in_scope_files` (predicted), `single_lane_files` it holds this wave, and
  `do_not_touch` (single-lane files held by other groups this wave)
- `slot`: `DATABASE_URL`, `REDIS_URL` (§7.3), `needs_e2e`
- `evidence_dir`: `.sweep-evidence/<id>/`
- `toolchain` (§7.4): absolute interpreter path, `PYTHONPATH`, and how
  web/Flutter dependencies are provided
- Shell rules for worktree sessions: use `/usr/bin/git` (not the rtk wrapper),
  one `git` call per Bash command, absolute paths, no shell variables where an
  option could go, and no heredocs that contain `git` (memory:
  `project_worktree_session_gotchas`)
- Rules: no commits/pushes/`gh` (hook-enforced); never edit or delete existing
  tests to make them pass; do not flip AC boxes; report discoveries upward.
- Context and constraints, **not** implementation steps (Cognition: prescriptive
  managers backfire without codebase context).

### 6.3 WORKER and VERDICT records

```json
{ "ids": ["412"], "status": "staged | blocked | failed | no_change",
  "worktree": "…", "branch": "…", "tree_id": "…", "files_changed": ["…"],
  "ac_file": ".sweep-evidence/412/ac.json", "tests_run": ["…"],
  "blockers": "≤ 300", "discoveries": "≤ 300", "summary": "≤ 600" }
```

```json
{ "ids": ["412"], "verdict": "pass | fail",
  "ac": [{ "index": 0, "verified": true, "note": "≤ 200" }],
  "test_edits_flagged": ["path::test_name"], "commands_rerun": 5,
  "tree_id_before": "…", "tree_id_after": "…", "clean_after": true }
```

`ac.json` is the machine-checkable AC ledger (research: JSON is less likely than
Markdown to be inappropriately rewritten): `[{index, text, command,
evidence_path, pass}]`. The worker may set `pass`; only the verifier's VERDICT
allows the main session to flip the Markdown box.

### 6.4 Frontmatter additions (durable, optional)

```yaml
triage: blocked-owner        # one of the TRIAGE classes
blocked_on: "VAPID keys must be set on Railway"
owner_decision: "Use FCM topics, not per-device sends (2026-09-27)"
triaged: 2026-09-27
```

Stage names (`staged`, `pr_open`, …) **never** go in `status:` —
`check_archived_todo_status.py` reports unknown status words, and the run file
is where stages live.

## 7. Grouping, lanes and resources

### 7.1 Groups

`group.py` builds groups by union-find over `predicted_files`: two ready todos
sharing a predicted file join one group (one worker, one PR). Tiny todos
(`size: xs`) in the same top-level module are bundled, at most 3 per group.
Frontmatter `dependencies` order groups; a dependency cycle aborts with the
cycle printed.

### 7.2 Single-lane resources

A lane is a resource at most one in-flight group may hold at a time (from
Execute until merge):

- `backend/plant_community_backend/settings.py`
- `.secrets.baseline`
- `e2e` — any group with `needs_e2e: true` (Playwright reuses whatever is on
  :5174/:8000; memory: `project_e2e_run_from_worktree`)
- `deps` — any group predicted to change a dependency manifest (§7.4)

The lane list is configuration in `group.py`, and grows when a new hot file is
observed. Prediction can miss, so conflicts are also caught after the fact: Land
rebases on `origin/main` before pushing, and a non-mechanical conflict stops that
group (reported, returned to `pending`) instead of being resolved by guess.

### 7.3 Per-slot resources

Worker slot `N` gets the following. Slots come in two banks, `(wave % 2) × workers + position`, because
wave N is still in review while wave N+1 executes, so the two waves need disjoint slots. Slots
run 1–6, which caps `--workers` at 3:

- `DATABASE_URL=postgres://localhost/plant_community_w<N>` → pytest creates
  `test_plant_community_w<N>` (`settings.py` parses `DATABASE_URL` under pytest;
  `pytest.ini` does not pin `--reuse-db`). Page suites keep `--create-db`.
- `REDIS_URL=redis://127.0.0.1:6379/<9+N>`, DBs 10–15 (dev uses 1 and 3).
- **Over Unix sockets when they exist** (todo 469). The sandbox blocks loopback
  TCP (`allowLocalBinding` covers listening, not connecting), and whether a
  worker may run pytest with the sandbox off is a per-call classifier call — the
  pilot's two workers got opposite answers. A socket listed in
  `sandbox.network.allowUnixSockets` is reachable from inside the sandbox, so
  for a local host `slot_env.py` uses `/tmp/.s.PGSQL.<port>`
  (`postgresql://%2Ftmp/plant_community_w<N>`) and `/tmp/redis.sock`
  (`unix:///tmp/redis.sock?db=<9+N>`, plus `CELERY_BROKER_URL=redis+socket://…?virtual_host=<9+N>`,
  because kombu does not read `unix://`). No socket file, or a remote host → TCP.
- Both are applied by `scripts/todos/slot_env.py <N> -- <command>`, never typed into prompts.
- File caches and `MEDIA_ROOT` are `BASE_DIR`-relative, so already per-worktree.
- Vitest and scripts are safe in parallel; Playwright is the `e2e` lane.
- Slot values are set as **process environment** on the worker's commands,
  never written into `.env`. `.worktreeinclude` copies `backend/.env` in, and
  python-decouple lets environment variables override `.env`, which is what
  makes the override work.

### 7.4 Toolchain in a fresh worktree

`backend/venv`, `web/node_modules` and Flutter `.dart_tool` are gitignored and
are **not** copied: they are too large for `.worktreeinclude`. Each worker's
brief states:

- **Python:** the main checkout's interpreter by absolute path
  (`<main>/backend/venv/bin/python`), with
  `PYTHONPATH=<worktree>/backend/packages/wagtail_forum`. `wagtail_forum` is
  installed editable from the main checkout, and without the prefix pytest
  collects it twice and reports import-file-mismatch errors.
- **Web:** `ln -sfn <main>/web/node_modules <worktree>/web/node_modules` (a
  symlink in a gitignored path is never committed).
- **Flutter:** `flutter pub get` in the worktree (served from the shared pub
  cache).
- **Dependency changes:** a todo that changes `backend/requirements*.txt`,
  `web/package*.json` or `pubspec.*` cannot use the shared venv or
  `node_modules`. It takes the single-lane resource `deps` (§7.2) and installs
  into a worktree-local environment (`python -m venv`, `npm ci`).

## 8. State model (run file)

`todos/.sweep-run-<run_id>.json`, written only by `state.py`:

```json
{ "run_id": "2026-09-27-1830", "selector": "sweep", "workers": 3,
  "todos": { "412": { "stage": "pr_open", "group": "g3", "wave": 1, "slot": 2,
                      "worktree": "…", "branch": "…", "pr": 861,
                      "evidence_dir": "…", "attempts": 1, "reason": "" } },
  "groups": { "g3": ["412"] }, "waves": [["g1","g2","g3"], ["g4"]],
  "lanes": { "settings.py": "g1" } }
```

Allowed transitions (`state.py` refuses others):

```text
scanned → triaged → ready | blocked | skipped
ready → executing → staged → verified → pr_open → reviewed → merged → archived
executing | staged | verified → failed → ready (retry, attempts+1) | blocked
any non-terminal → blocked   (with reason)
```

Terminal: `archived`, `blocked`, `skipped`. The run file is deleted only when
every todo is terminal. Cross-session resume is from this file plus git and
`gh pr list`; same-session resume can additionally use
`Workflow({resumeFromRunId})`.

## 9. Failure handling

| Failure | Response |
|---|---|
| Workflow agent returns `null` (died/skipped) | Stage → `failed`; offered for retry in the next wave. |
| PR worktree removed by the harness sweep | Re-added from the pushed branch under the scratchpad (§5.3 step 3, worktree liveness). |
| Staged tree changed between worker and verifier | Verdict void; stage → `failed` (§5.2). |
| Verifier `fail` twice | `blocked` with reason; todo back to `pending`, Work Log entry. |
| Worker `blocked` (new gate discovered) | Recorded as a new owner question for the next Decide batch. |
| Commit hook `[CRITICAL]` | Treated as a blocking review finding → round-1 repair path. |
| CI failure after push | That PR stops and is reported; other groups continue. |
| Non-mechanical rebase conflict | That group stops, is reported, and returns to `pending`. |
| Kimi gate timeout | The gate self-caps at 150 s and then **skips itself**. A skipped gate is not a passed gate: record `kimi: skipped` in the PR body and the run summary. Round-1/2 review still runs. |
| Owner-gated step inside a todo (prod read, dashboard) | Never attempted; becomes an owner hand-off in the summary. |
| Session ends mid-run | `todo-resume` reads the run file; every stage is idempotent because the source of truth is git + PR state. |

No destructive recovery: nothing is reset, force-pushed, or deleted to "clean
up" a failure.

## 10. Cost and scale

Per group, roughly: 1 triager, 0–1 planner, 1 worker and 1 verifier; per review
round 3 bug lenses, 1 router, 1–4 domain reviewers and 2 refuters per blocking
finding; then 0–1 repair and 0–1 verifier. That is ≈ 14–24 agents per group
(todo 472: review depth is never traded for cost). A full 36-todo sweep with
about half the todos gated is on the order of 300–450 agents across several
workflow runs. Hence:

- `--limit N` caps groups per run; the plan logs what was deferred (no silent caps).
- Review runs at full depth for every size (§5.3). The old `m`+ gate on the
  checklist lane made small PRs shallower than the pre-v2 engine, so it was removed
  (owner, 2026-09-28).
- Tiny todos are bundled (§7.1).
- The kimi commit gate is on Land's serial critical path: up to 150 s per
  commit, and a PR usually has two commits (initial + repair), so ~5 min per
  group in the worst case (observed 2026-09-27: 150 s, then timed out).
- Branch protection on `main` has `strict: false` (checked 2026-09-27), so an
  auto-merge does not force later PRs to rebase and re-run CI one after
  another. Throughput is bounded by Land and review, not by a merge queue. If
  `strict` is ever turned on, the 3-worker estimate no longer holds.
- Model tiering is **not** decided (no surviving evidence); agents inherit the
  session model, and the pilot measures triage accuracy before any downgrade.

## 11. Prerequisites

**In this work (PRs):**

1. `scripts/check-kimi-engine.sh:16` — temp files instead of `diff <(…)`.
2. `.worktreeinclude` for `backend/.env`, `web/.env`.
3. `guard-todo-worker-git.sh` hook + its test.

**Owner-applied settings (user settings; sandbox won't let Claude write them):**

| Setting | Why |
|---|---|
| `sandbox.enableWeakerNetworkIsolation: true` | `gh` TLS inside the sandbox on macOS (documented for exactly this) |
| `sandbox.network.allowedDomains: ["openrouter.ai","api.github.com","github.com"]` | kimi gate + `gh` without per-command prompts |
| `workflowSizeGuideline: "large"` | a 36-todo triage run is ~37 agents; default `medium` advises < 10 |
| `sandbox.network.allowUnixSockets: ["/tmp/.s.PGSQL.5432", "/private/tmp/.s.PGSQL.5432", "/tmp/redis.sock", "/private/tmp/redis.sock"]` | workers' and verifiers' pytest reaches Postgres and Redis inside the sandbox (§7.3); both spellings because `/tmp` is a symlink. Needs `unixsocket /tmp/redis.sock` + `unixsocketperm 700` in `/opt/homebrew/etc/redis.conf` |
| `autoMode.environment` (user settings only) | trusted context: sweeps commit to feature branches, push, open PRs, arm auto-merge; never read production |

## 12. Testing and rollout

1. **Unit tests** — `scripts/todos/test_*.py` and `test_workflows.js`: scan (status coverage, stranded
   detection, in-flight exclusion, README/TEMPLATE exclusion), group
   (union-find, xs bundling, lanes, dependency cycle abort), state (every
   allowed and refused transition).
2. **Hook test** — `test-guard-todo-worker-git.sh`: denies for
   `todo-worker`/`todo-verifier`, allows for the main session and other agents.
3. **Pilot (2 workers, 2 disjoint low-risk todos).** Must pass, each with
   recorded evidence:
   - P0 a worker in a fresh worktree runs one backend test and one Vitest
     file using the §7.4 toolchain. Without this, P2 and P7 can fail for
     reasons unrelated to the design.
   - P1 `isolation: worktree` creates a working checkout under the sandbox,
     including `.claude/` files (a manual `git worktree add` under
     `.claude/worktrees/` failed on 2026-09-27 with "unable to create file
     .claude/agents/…: Operation not permitted").
   - P2 two slots run backend pytest concurrently with no cross-talk.
   - P3 the verifier (no isolation) can run commands in the worker's worktree.
   - P4 the hook blocks worker commits; the main session can commit in the
     worker's worktree with `git -C`, **and** can Edit/Write todo files inside a
     worktree under `.claude/worktrees/`: neither `guard-main-branch-edit.sh`
     (if the main checkout sits on `main`) nor the native cross-worktree block
     fires. Unpinned Write into a *scratchpad* worktree is proven; under
     `.claude/worktrees/` it is not.
   - P5 `.worktreeinclude` delivers `backend/.env`.
   - P6 every returned record is within its schema caps; record main-context
     growth per group.
   - P7 end to end: both PRs merged with todos archived in the same PR.
   - P8 a `todo-review` agent can run the bundled code-review skill against an
     explicit worktree and diff range. Otherwise use the `general-purpose`
     fallback. *(Result: it cannot, and the fallback was shallower than before
     v2. The fan-out moved into the workflow script, §5.3, todo 472.)*
   - P9 the tree-hash check detects a deliberate one-byte change made after
     the worker returns (mutation test of the §5.2 guard).
4. **3-worker run** on a p3/p4 batch; measure predicted vs actual touched files
   (the grouping accuracy question).
5. **Full sweep.**

A pilot failure on P1 or P3 changes the design (fallback: Execute agents run
without isolation, and `state.py` creates worktrees under the scratchpad
directory via `git worktree add`), so the skills are rewritten only after the pilot.

## 13. Evidence base

From the 2026-09-27 deep-research run (21 sources, 25 claims verified 3-vote):

| Design element | Source | Confidence |
|---|---|---|
| Workflow script for the outer loop | Claude Code docs: Agent SDK subagents, workflows | medium (single doc page) |
| Compact results; state in files, not context | Anthropic multi-agent research system; context engineering; SDK docs | high |
| State file + git as the source of truth; compaction drops specifics | Anthropic long-running harnesses; context-engineering cookbook | high |
| Self-contained structured briefs; not prescriptive | Anthropic research system; SDK docs; Cognition (Apr 2026) | high |
| `isolation: worktree`, fresh from default branch | Claude Code docs: sub-agents, worktrees | high (docs), untested here |
| One writer per unit; extra agents add intelligence | Cognition (Apr 2026) | medium |
| JSON pass/fail ledger; no test edits | Anthropic long-running harnesses | medium |
| Don't split tightly coupled phases | Claude Code sub-agents docs | high |
| Triage taxonomy, grouping, lanes, per-slot DB | Repo experience only | **low** — validated by the pilot |

Refuted in verification and **not** relied on: "fresh-context reviewer finds ~2
bugs/PR" (0–3); "lead agent + specialized subagents" as a recommended
architecture (1–2); "one feature per session was critical" (1–2).

## 14. Open questions

1. Model tiering for the triager (cheaper model?) — decide after pilot accuracy.
2. Is predicted-files grouping accurate enough, or should lanes rely mostly on
   rebase-time detection? Measured in rollout step 4.
3. ~~Should `code-review-orchestrator` run on every PR or only `m`+?~~ Every
   PR (owner, 2026-09-28: reviews can't be shallower than before v2; todo 472).
