# Todo sweep v2 — pilot results (Task 14)

Run on 2026-09-28 from `../plant_id_community-pilot`, a checkout of `origin/main`
(`90e239f1`, PR #861) on branch `pilot/todo-sweep-v2`, with `backend/.env` and
`web/.env` copied in. Plan: `docs/superpowers/plans/2026-09-27-todo-sweep-v2.md`
Task 14. Spec: `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`.

## Result

| Check | Result | Evidence (sections below) |
|---|---|---|
| P0 worker ran pytest + Vitest | PASS | g2 `tests_run`: `slot_env 2 pytest apps/users/tests/test_dashboard_stats.py --create-db: 9 passed`, `vitest run ProfileStats.test.tsx profileService.test.ts ProfilePage.test.tsx: 32 passed` (worker copied `backend/.env` by hand, sandbox off) |
| P1 `isolation: worktree` includes `.claude/` | PASS | `git -C <WT> ls-files .claude` → `.claude/agents/celery-async-reviewer.md` …; `ls <WT>/.claude/agents` lists the agents |
| P2 two slots run pytest concurrently | **FAIL** in the harness, PASS by hand | only g2's worker ran pytest; the plan's post-run `psql` check can't work (DBs dropped at session end). Polled by hand: `…_w1,…_w2` both present at 04:03:11, both runs green |
| P3 verifier ran in the worker's worktree | PASS | g2 VERDICT `commands_rerun: 1`, `tree_id_before == tree_id_after == fcc86f63…` |
| P4 hook blocks worker commits; main session can land | PASS | denial quoted below; main session committed in `.claude/worktrees/…` for #863 and #865 (`c0088909`), guard silent (sandbox off) |
| P5 `.worktreeinclude` delivered `backend/.env` | **FAIL** | neither harness worktree had it; mitigated by #864 (`slot_env` falls back to the main checkout's `.env`), which let 432's tests run in its worktree: `37 passed`. `web/.env` still not delivered |
| P6 records read from output files; context growth | PASS | `record-triage`/`ingest-execute`/`ingest-review` read the task output files; ~12 k main-session tokens across wave 0 |
| P7 PRs merged with todos archived in the same PR | PASS | #863 `MERGED` (439 archived in it); #865 (432 archived in it, landed by hand) |
| P8 review workflow | PASS, flagged | `checklist_skipped: false`, no blocking; both rounds fell back to an inline review ("no Agent tool available") — `skill:code-review` never ran |
| P9 tree-hash detection | PASS, check defective | `write-tree` = recorded `tree_id`; an unstaged edit shows up as `M` in porcelain's second (worktree) column and clears on restore. Porcelain is never empty on a staged tree; `write-tree` can't see unstaged edits |
| P10 restricted-tools agents return records | PASS | first triage run: 2 records, `"missing":[]` |

**Gate.** P1 and P3 pass, so no spec §12 fallback. P2 and P5 failed; per Step 5 each was fixed
at its owner and re-checked: P5 by #864 (tests in `test_slot_env.py`) and a real run of 432's
suite in its harness worktree; P2 by the polled concurrent run. **Proceed to Part B**, with
todo 469 (engine and plan gaps: no retry out of `blocked`, workers' pytest depends on a
per-call sandbox-off decision, workflow worktrees leave the sandbox allowlist, P2/P9 check
wording) folded into Tasks 15–17. Follow-ups filed: 469, 470 (#863 stale JSDoc), 471 (#865
review notes).

## Step 0 — settings check (spec §11, applied by the owner 2026-09-28)

User settings read back from `~/.claude/settings.json`:

```
sandbox: {"enableWeakerNetworkIsolation": true,
          "network": {"allowedDomains": ["openrouter.ai", "api.github.com", "github.com"]}}
workflowSizeGuideline = large
```

| Check | Result | Evidence |
|---|---|---|
| `gh pr list --limit 1` sandboxed | PASS | `854 refactor: delete the users care-reminder system; archive todo 410 (slice B) feat/410b-remove-users-care-reminders OPEN` |
| kimi commit gate runs | PASS | throwaway commit on `scratch/kimi-gate-probe` (worktree in `$TMPDIR`): `kimi-review staged-diff gate (CRITICAL blocks)....Passed` / `duration: 24.58s` / `[kimi: 1179 in (0 cached) / 455 out \| finish: stop]` / `No findings in requested tiers: CRITICAL, WARNING`. Branch deleted, worktree removed. |
| `command -v timeout` | PASS | `/opt/homebrew/bin/timeout` |
| `gh auth status` | PASS | `✓ Logged in to github.com account Xertox1234 (keyring)`, scopes `gist, read:org, repo, workflow` |
| `git worktree list` | PASS | 17 peer worktrees under the main checkout's `.claude/worktrees/`; `scan.py` excluded the two in flight (`428`, `410`). Neither pilot todo is held. |

Observations:

- `git worktree remove <path>` prints `error: could not lock config file …/.git/config`
  and exits 1 under the sandbox, **but the worktree is removed** (`git worktree list`
  no longer shows it). Never chain it with `&&`; confirm with `git worktree list`.
- **The sandbox blocks local TCP to Postgres and Redis**, even with them in
  `allowed_domains`: `pg_isready -h localhost` → `no response`;
  `redis-cli -h 127.0.0.1 ping` → `Operation not permitted`. Unsandboxed, both
  answer (`accepting connections`, `PONG`). So every backend pytest a worker or
  verifier runs needs the sandbox off. Spec §7.3 does not mention this.
- The pilot checkout has no `backend/venv` or `web/node_modules`. Execute runs
  with `--main-root ~/projects/plant_id_community` (spec §7.4 toolchain). Its venv
  predates the web-push pins on `origin/main` (`requirements.txt` +10 lines vs
  `6b782055`), but `import pywebpush, aiohttp` succeeds in it, so the venv is current.

## Evidence log (filled in as the run proceeds)

Run id `2026-09-28-0839`: `scan.py --selector batch --ids 432,439 --workers 2`.
A = **432** (`backend/packages/wagtail_forum/`, backend only — pytest).
B = **439** (`backend/apps/users/`, `web/src/`, `backend/docs/` — pytest + Vitest).
Different subtrees with no shared file, no dependency edge. P2 needs both workers to
run pytest, so two backend todos were required; "different top-level directories"
is read as "disjoint files".

### P4 (part 1) — the hook denies a worker commit

`Agent(subagent_type: "todo-worker")` asked to run
`/usr/bin/git -C $SCRATCH/p4-repo commit --allow-empty -m probe`. Tool result, verbatim:

```
PreToolUse:Bash hook error: todo sweep: git commit is reserved for the main session; workers stage and stop (allowed: add, diff, fetch, log, mv, rev-parse, rm, show, status, write-tree)
```

### Stage A — triage (workflow `w5c1n07nq`, 2 agents, 29.7 s, 75,401 subagent tokens)

Workflow result: `"records":[{"id":"432","class":"ready",…},{"id":"439","class":"ready",…,"owner_question":"Should the Posts card count replies only, relabeled \"Replies\", …?"}],"missing":[]`

```
$ state.py record-triage $RUN --output …/tasks/w5c1n07nq.output
{"without_record": []}
$ state.py accept-ready $RUN
{"ready": ["432"]}
$ state.py questions $RUN      → one question (439, Posts card)
$ state.py decide $RUN 439 ready --decision "Posts card counts replies only, relabeled \"Replies\" (2026-09-28)"
```

Owner answered "Replies only" via AskUserQuestion. Triage PR **#862** (`apply-triage`: 5 frontmatter
lines in `todos/` only; kimi gate `Passed`, 6.17 s) merged as `c478ea8d`.
`git push -u` pushed the branch but printed `could not lock config file` for the upstream write — the
sandbox denies `.git/config`. Push without `-u`.

`state.py group` → `{"waves": [["g1", "g2"]], "unschedulable": {}}`.

### Stage B — execute wave 0 (workflow `w6a43vml0`, 3 agents, 952 s, 441,369 subagent tokens)

`execute-args --wave 0 --main-root ~/projects/plant_id_community`. Both worktrees were created by
`isolation: worktree` under the **main checkout's** `.claude/worktrees/wf_6b13b590-b1b-{1,2}`, cut from
`origin/main` `c478ea8d` (`git -C <WT> merge-base HEAD origin/main` → `c478ea8d`). While the workflow ran,
the sandbox write allowlist named both paths; after it finished, it no longer did.

- **g1 (432)** → WORKER `status: blocked`, `verdict: null`, `tests_run`:
  `"AC0 pytest node: NOT RUN (slot_env exit 2: no DATABASE_URL; the worktree has no backend/.env)"`,
  `"test_topic_approval.py with CI placeholder env: all errored (sandbox blocks Postgres socket)"`.
  `blockers`: `"… Classifier denied copying it and pytest outside the sandbox. …"`
- **g2 (439)** → WORKER `status: staged`; VERDICT `pass`, `commands_rerun: 1`,
  `tree_id_before == tree_id_after == fcc86f63…`, 4 test edits flagged. Its worker copied
  `backend/.env` from the main checkout by hand and ran pytest and Vitest with the sandbox off. The
  classifier allowed g2 and denied g1: the same action, decided differently.

`ingest-execute` → `{"432": "blocked", "439": "verified"}`.
Main-session context (proxy: `total_tokens` left in system reminders; `/context` is user-only):
14,858,573 before the wave → 14,846,619 after ingest (~12 k).

### Stage C — review round 1, PR #863 (workflow `wea894q6s`, 2 agents, 321 s, 154,839 subagent tokens)

```
"ranges":["git diff origin/main...HEAD",
          "origin/main...HEAD @ 852ab0fc — inline review (routed django-drf, react-typescript, cross-cutting; no Agent tool available)"],
"reviewers_ok":true,"checklist_skipped":false,"blocking":[]
```

Two `low` findings, one issue: stale JSDoc in `web/src/types/auth.ts:50` → follow-up.
`ingest-review --round 1` → `{"g2": "clean"}`.

### Stage C — review round 2, PR #863 (workflow `wy02l7b32`, 2 agents, 311 s, 156,014 subagent tokens)

```
"ranges":["git diff origin/main...HEAD",
          "origin/main...HEAD @ wf_6b13b590-b1b-2 (inline pass: django-drf-reviewer, react-typescript-reviewer, cross-cutting-reviewer)"],
"reviewers_ok":true,"checklist_skipped":false,"blocking":[]
```

`ingest-review --round 2` → `{"g2": "clean"}`. `gh pr merge 863 --auto --squash --delete-branch`
merged at once (CI was already green). `gh pr view 863 --json state,files` → `MERGED`, files include
`todos/439-pending-…` (deleted) and `todos/archive/439-completed-…` (added). `set-group g2 merged` →
`git worktree remove` (sandbox off: the path is under the main checkout) → `set-group g2 archived`.

Plan defect in P2's check: after the runs,
`psql -d postgres -Atc "select datname from pg_database where datname like 'test_plant_community_w%'"`
returns only `test_plant_community_wt413` (a peer session's). pytest-django drops the test database at
session end (`--create-db`, no `--reuse-db`), so `_w1`/`_w2` exist only **while** a run is in flight.
The check has to poll during the run.

### Session break, then #864

The session was lost after round 2 of #863. In between, the P5 failure was fixed on its own
branch: **#864** (`c1d3c25e`, merged) makes `slot_env.py` fall back to the main checkout's
`backend/.env` (located through `git rev-parse --git-common-dir`) when the worktree has none.
The pilot branch was fast-forwarded to it.

### Stage D for 432 — by hand (the engine has no path)

`blocked` is in `state.TERMINAL`, and `ALLOWED` has no move out of it, so `execute-args` will
never brief g1 again and the gate's "re-run the failed check only" has no engine route. The
owner chose to finish 432 by hand from its existing worktree
(`…/.claude/worktrees/wf_6b13b590-b1b-1`), without editing the run file.

1. **Verify.** `slot_env.py` locates the worktree from `__file__` (`parents[2]`), so a copy
   run from `$TMPDIR` can't work. #864's `slot_env.py` was copied over the worktree's
   (unstaged) copy for the run and restored with `git checkout --` afterwards:
   `test_topic_approval.py` + `workflow/test_edit_moderation.py` + `api/test_post_revisions.py`
   → `37 passed, 3 warnings in 21.63s`. `write-tree` before and after:
   `917946192ba313484cf1091cf1340274e940b9d1` (= the recorded `tree_id`).
2. **Flip + archive.** The AC box was ticked by hand with the evidence in a Work Log entry
   ("Verified by the main session"), because `land.py flip-acs` needs a verifier's
   `verified: true` and g1 has none. `land.py archive` then ran as designed:
   `{"archived": "todos/archive/432-completed-…", "baseline_updated": false, "review": {"note": "source_review 'PR #815' is set but source_finding is missing"}}`.
3. **Commit from the main session inside `.claude/worktrees/…`.** The branch was renamed
   `fix/432-opening-post-pending-edit`; `/usr/bin/git -C <WT> commit` → every pre-commit
   hook `Passed`, `kimi-review staged-diff gate (CRITICAL blocks)....Passed` (27.68 s,
   `No findings in requested tiers`), commit `c0088909`. Sandbox off: the sandbox write
   allowlist names the workflow's worktrees only while the workflow runs.
4. **PR #865**, pushed and opened from the sandbox (`git push` without `-u`, `gh pr create`).

### P2 — by hand, polling while both run

Slot 1 ran 432's worktree (`test_topic_approval.py` + `workflow/test_edit_moderation.py`),
slot 2 ran the pilot checkout (`apps/users/tests`), in parallel, with
`psql -d postgres -Atc "select string_agg(datname, ',' …) … like 'test_plant_community_w%'"`
every 2 s:

```
04:03:07 test_plant_community_wt413
04:03:09 test_plant_community_w1,test_plant_community_wt413
04:03:11 test_plant_community_w1,test_plant_community_w2,test_plant_community_wt413
04:03:32 test_plant_community_w2,test_plant_community_wt413
slot 1: 22 passed, 3 warnings in 22.20s   (exit 0)
slot 2: 331 passed, 3 warnings in 59.13s  (exit 0)
```

### P9 — tree hash on the real worktree

`write-tree` = recorded `tree_id` (`91794619…`). Appending a byte to an **unstaged** tracked
file (`backend/packages/wagtail_forum/README.md`) adds a line with `M` in the second (worktree) column,
`<space>M backend/packages/wagtail_forum/README.md`, to `status --porcelain --untracked-files=no`; `cp` back removes it, and `write-tree` is still
`91794619…`. Two defects in the check as written:

- A staged worktree's porcelain is **never empty** (`M  …signals.py` etc. are always listed).
  "Confirm the porcelain output is empty again" has to be "equals the baseline".
- `write-tree` hashes the **index**, so it cannot see an unstaged edit at all; only the
  porcelain second column (`M`) does. Detection must use both.
- The sandbox denies writes under the main checkout's `.claude/worktrees/` once the workflow
  has finished (`operation not permitted`), so the check needs the sandbox off.
