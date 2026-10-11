---
status: completed
priority: p4
issue_id: "577"
tags: [todo-sweep, scripts, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Fix all seven findings, #3 (cross-file merged duplicates) and #5 (worker-edit guard vs the brief) included; declining is not allowed (2026-10-11)"
---

# Follow-ups from PR #1016 (todo 551, the sweep engine)

## Problem

Todo-sweep run 2026-10-11-0401 merged PR #1016. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and checked each one against main, and a refuter
tried to refute every one; anything dropped is listed with its reason. Line numbers are as of the PR head,
so re-check each against main before acting on it.

## Findings

PR #1016 (todo sweep run 2026-10-11-0401, group g5, todos 551); follow-ups: verified.

1. **medium** `scripts/todos/todofile.py:191` The checker now matches fences by character and length, but todofile.ac_lines (used by land.flip_acs and state.py) still uses the old FENCE_RE toggle. A ```python line inside a```markdown block in an AC section hides real boxes from land, which archives with them unticked, and the CI tripwire then fails.
2. **medium** `scripts/todos/state.py:1470` The kept-side `phrased` set is still global across files while the dropped side is now file-scoped. A kept 'missing test' in a.py still hides an identical stored 'missing test' in b.py from `uncovered`. The same fix applies, and no test pins it.
3. **low** `scripts/todos/state.py:371` The dropped-phrasing coverage is scoped by file but not by line. A stored line in the same file with an identical summary far away (for example two separate `missing test` findings in a.py), which the curator never merged, is still swallowed by an unrelated drop. | also: dropped_phrased is keyed by the drop's file. The curator may merge the same problem from another file ("in other words"), and the refuter prompt says `also` may be at another location. A refuted cross-file duplicate now comes back as an uncovered follow-up, which breaks the 546 rule that merged duplicates stay refuted. | A dropped phrasing now covers stored lines only in the drop's own file. The curator may merge same-problem items across files ('in other words'), so a refuted `also` phrasing that came from another file returns as an uncovered kept follow-up. Kept-item coverage (`phrased`) is still cross-file, so the two paths disagree.
4. **low** `.claude/workflows/todo-followups.js:90` When the summary is refuted and an `also` phrasing survives, the kept item takes the merged item's file:line and its max severity. A low `nit` merged in from a.py:2 comes back as a medium at a.py:9.
5. **low** `scripts/todos/worker_edit_guard.py:94` A worker whose cwd is the main checkout (or a session worktree) can now edit any `wf_*` or `agent-*` worktree, not only its group's recorded one. That includes another workflow's or agent's isolated worktree and any human worktree named `wf_*`. | also: From the main checkout or a session worktree, a worker may now edit any wf_*/agent-* worktree, not just its group's recorded one (the hook cannot read the brief). No test covers a worker targeting a different group's wf_* worktree from the main checkout.
6. **low** `scripts/todos/test_workflows.js:474` A leftover `r = await run(... refuted: true, also_refuted: [] ...)` call is overwritten by the next run before anything asserts on it. After the 546 #993-6 rewrite, this call checks nothing. | also: After the 546 #993-6 rewrite, a `run('todo-followups', ... also_refuted: [] ...)` call is left whose result is overwritten by the next call without any check. It is dead test code. The other edits to existing tests (adding the required `also_refuted` and the expectation change ordered by the owner) are justified.
7. **low** `.claude/workflows/todo-followups.js:93` When on_main is 'fixed' and the refuter refutes only an `also` phrasing, the drop reason still reads 'fixed on main: `<note>`; the refuter agreed', attributing the item-level fixed claim to a phrasing that was judged separately.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: scripts/check_archived_todo_status.py:186 `(?<=/)-(?:Users|home)-` no longer flags a bare TMPDIR or project-dir spelling that does not follow a slash, such as `-Users-NAME-projects-x` in backticks or at the start of a line, so a username in a Work Log can pass silently. (fixed on main: origin/main HOME_PATH_RE uses `(?<![\w-])-(?:Users|home)-[^-/\s'"`<>]+-`, which matches after a backtick, quote, space or line start. The comment says a bare`-Users-NAME-projects-x` is caught (review of PR #1016).; the refuter agreed: origin/main HOME_PATH_RE (check_archived_todo_status.py:230) is `(?<![\w-])-(?:Users|home)-[^-/\s'"`<>]+-`. That matches after a backtick, quote, space or line start, so `-Users-alice-projects-x` is flagged again. work_log_home_paths uses it.)
- low: scripts/check_archived_todo_status.py:172 FENCE_RE has no callers now that parse() and work_log_home_paths() both use fenced_lines(). It remains as dead code alongside _FENCE_OPEN_RE. (fixed on main: FENCE_RE is not dead on origin/main: todofile.py imports it (lines 18, 178, 195) and land.py:372 uses it. The also claim about an unclosed opener is still there: fenced_lines deliberately treats one as plain text, as its docstring says.; the refuter agreed: FENCE_RE is not dead on origin/main: todofile.py imports it (18) and uses it at 178/195, and land.py:372 uses check_archived_todo_status.FENCE_RE. The unclosed-opener behavior is deliberate, as fenced_lines' docstring says.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- #1: `todofile.ac_lines` uses `fenced_lines` (character and length, as the tripwire) instead of the `FENCE_RE` toggle; tested in `scripts/todos/test_todofile.py`. #2/#3: `state.ingest_followups` pools every returned phrasing with a count, and each covers one stored line wherever it is, after the lines returned at their own location take theirs. So a cross-file merged duplicate stays covered (kept or refuted), while an identical, unmerged summary elsewhere, in the same file or another, is kept as stored. Tested in `scripts/todos/test_state_flow.py`.
- #4: in `.claude/workflows/todo-followups.js`, when the summary is refuted the surviving merged phrasing leads the item at its own stored file:line and severity (looked up in the group's stored follow-ups); a reworded phrasing keeps the item's place. #7: the "fixed on main" wording names only the summary's own drop; a refuted `also` phrasing reads `refuted:`, as its own drop when both are refuted.
- #5: `scripts/todos/worker_edit_guard.py` allows a `wf_*`/`agent-*` worktree from the main checkout (or a session worktree) only when a sweep run file (`todos/.sweep-run-*.json` in the main checkout or the cwd's checkout) records it as a todo's worktree. That closes another workflow's or agent's isolated worktree and a human's `wf_*` one. It does not tell the worker's own group from another recorded group: a PreToolUse event carries `agent_id`/`agent_type` but not the prompt or a transcript, so the hook cannot read the brief. Tests in `.claude/hooks/test-guard-todo-worker-edit.sh`; its 551 #2 fixture now writes the run file its "recorded" cases name.
- #6: removed the overwritten `run(...)` call in `scripts/todos/test_workflows.js` (it repeated the 551 #3 case that asserts). The 551 #3 expectation changed with #4: the surviving `nit` now comes back at `low: a.py:2`. New JS cases pin #4 and #7.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `python3 scripts/todos/test_todofile.py && python3 scripts/todos/test_state_flow.py && node scripts/todos/test_workflows.js && bash .claude/hooks/test-guard-todo-worker-edit.sh` — evidence `.sweep-evidence/g11/577-ac0.txt` (not committed), last lines:

  ```text
  PASS: a todo-verifier is not this hook's business
  PASS: a cwd in no git checkout fails open
  PASS: malformed JSON fails open

  Results: 31 passed, 0 failed
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
