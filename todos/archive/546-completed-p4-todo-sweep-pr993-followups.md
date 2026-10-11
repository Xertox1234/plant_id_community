---
status: completed
priority: p4
issue_id: "546"
tags: [todo-sweep, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Run in this batch alongside 544/545 (2026-10-10)"
---

# Follow-ups from PR #993 (todos 492, 497, 540, 541, the sweep engine)

## Problem

Todo-sweep run 2026-10-10-2307 merged PR #993. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and confirmed each one is still present on main, and a
refuter dismissed none. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #993 (todo sweep run 2026-10-10-2307, group g4, todos 492, 497, 540, 541); follow-ups: verified.

1. **medium** `scripts/todos/worker_edit_guard.py:66` `own` comes from the agent's cwd. If the engine runs from a session whose cwd is a .claude/worktrees/&lt;x&gt; worktree, subagents inherit that cwd, so own=&lt;x&gt; and every todo-worker Edit/Write into its sweep worktree (.claude/worktrees/sweep-*) is denied. Every group then fails.
2. **medium** `scripts/check_archived_todo_status.py:187` HOME_PATH_RE misses home paths that leak the user name: 'file:///Users/bob/x', '-I/Users/bob/inc', '//Users/bob' and the sandbox TMPDIR form '/private/tmp/claude-501/-Users-bob-projects-...'. Land's refusal and the CI rule both rely on it, and workers write Work Log entries by hand. | also: scripts/check_archived_todo_status.py:185 HOME_PATH_RE, used by both Land's archive refusal and the CI rule, misses spellings that still leak the user name in a public repo. Probed: `/private/tmp/claude-501/-Users-alice-projects-x/...` (the sandbox TMPDIR form), `file:///Users/alice/x` and `//Users/alice` all return no match. | HOME_PATH_RE only matches POSIX /Users and /home. A Windows-style `C:\Users\name` path in a Work Log would not trip the leak rule. Low impact because the dev machine is macOS. | HOME_PATH_RE matches any `/home/<x>` that starts a token, so a URL route in Work Log prose (e.g. 'route /home/feed') counts as a home path. land.archive refuses that todo in phase 1 and CI flags it, though no local path leaks.
3. **medium** `scripts/todos/state.py:274` The add_worktrees recovery text tells the operator to run `worktree remove --force` and `branch -D` where the old text said to move the directory aside. 'Not same' covers a worktree with uncommitted worker changes, so an agent that follows the message deletes that work. This breaks safety rail 3 and the CLAUDE.md destructive-command rule.
4. **medium** `scripts/todos/state.py:998` review_criteria lets a box change at any `confirmed` index, even one the verifier never agreed to. confirm() also accepts a blocked todo that already has a PR, since CONFIRM_STAGES has no PR check. So after `confirm` on a round-2-blocked group, a box ticked by hand in the round-3 repair passes _not_ready's criteria gate.
5. **low** `scripts/todos/state.py:1529` release_incomplete resets review_reruns[round] to 0. With MAX_INCOMPLETE at 2, a released round gets two more incomplete attempts, not the one more try the docstring promises. The SKILL's 'a third incomplete round blocks for good' is also wrong: it blocks only on the fourth.
6. **low** `scripts/todos/state.py:1423` `phrased` is built only from the curator's kept items, which may have survived the refuter. If raw item B was merged into item A (B's phrasing is in A.also) and the refuter refutes A, then B is 'uncovered' and kept as stored, so the refuted finding comes back in the follow-up todo.
7. **low** `.claude/agents/todo-worker.md:124` The worker prompt tells a sub-agent to re-run pre-commit with the sandbox off when a fixer hits `Operation not permitted` on .claude/agents. That runs every configured hook unsandboxed, from an agent whose only edit guard is a mistake guard, not a boundary.
8. **low** `scripts/check_archived_todo_status.py:214` work_log_home_paths ends the Work Log section at any line that starts with '## ', even one inside a fenced output block. A quoted tail containing such a line hides every later home path from both Land and CI.
9. **low** `scripts/todos/worker_edit_guard.py:41` worktree_of accepts any path under .claude/worktrees/&lt;name&gt;. A worker whose cwd is the main checkout can edit any other worktree there, including a human's (such as todo-543-hand-round-guards), and plain files placed directly in .claude/worktrees/. The docstring notes the cross-group case but not human worktrees.

14 more location(s) were dropped by the cap of 10 (the most severe are kept).

### Beyond the cap (round 2 of PR #993, recorded by hand)

The run file stores at most 10 follow-ups per PR. These round-2 findings fell past the cap and are listed here so
they are not lost. Re-check each against main before acting on it.

- **low** `scripts/todos/state.py` `ingest_followups`: an item the curator returns at a known location but with a
  changed severity goes to `dropped`, and its key counts as returned, so the stored line leaves `curated`
  (against the 'kept as stored, never lost' rule of PR #982 finding 1). An item rejected for a bad location also
  feeds `phrased`.
- **low** `scripts/todos/state.py` `add_worktrees`: `main_root` is made absolute only for non-reverify briefs, so a
  reverify brief and its entry can keep a relative `--main-root`.
- **low** `scripts/todos/state.py` `stray_worktree` is a single field; a second mismatch on a retry overwrites the
  first, so `state.py worktrees` stops listing the earlier stray worktree.
- **low** `scripts/todos/worker_edit_guard.py`: paths are compared with `startswith` after `realpath`, which does
  not fold case on APFS, so a differently-cased path into the main checkout is allowed. A mistake guard, so
  documenting the gap is enough.
- **low** `scripts/check_archived_todo_status.py`: the home-path rule scans only the `## Work Log` section of an
  archived todo; a home path elsewhere in the file is not checked. A token-start `/home/x` URL route in prose is a
  false positive.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0149)

- Fixed with tests, findings 1 and 9 (`scripts/todos/worker_edit_guard.py`, `.claude/hooks/test-guard-todo-worker-edit.sh`): a cwd counts as the worker's own worktree only when it is a worker's (`sweep-*` or harness `agent-*`); from the main checkout or an inherited session worktree a worker may edit only a `sweep-*` worktree, so a human's worktree, the session's own worktree and a plain file directly in `.claude/worktrees/` are denied. The APFS case-folding gap (beyond the cap) is documented in the docstring, as the finding asked.
- Fixed with tests, findings 2 and 8 (`scripts/check_archived_todo_status.py`, `scripts/test_check_archived_todo_status.py`): `HOME_PATH_RE` now matches `file:///Users/<name>`, `-I/Users/<name>`, `//Users/<name>`, `//home/<name>`, the sandbox TMPDIR spelling `-Users-<name>-` and `C:\Users\<name>`, while a `<name>` placeholder and `home/` inside a longer path still pass (all 38 grandfathered files unchanged, no new violation); `work_log_home_paths` ignores a `##` line inside a fence. Declined: the false positive on a URL route under `/home/` in prose (it cannot be told from a home directory without knowing user names; it fails safe and `grandfathered_home_paths` excuses a file) and scanning beyond the Work Log (8 more archived files would trip on review findings quoted in their Problem text, which Land never writes).
- Fixed with tests in `scripts/todos/state.py` / `scripts/todos/test_state_flow.py`: finding 3, the `add_worktrees` recovery now moves the worktree (`git worktree move`) and renames its branch (`branch -m`), deleting nothing; finding 4, `confirm` refuses a todo that has a PR (closing the hole there, so `review_criteria` keeps accepting confirmed indexes); finding 5, `release_incomplete` sets the count to `MAX_INCOMPLETE - 1`, so the release is exactly one more try and the docstring and `.claude/skills/completing-todos/SKILL.md` now read true; finding 6, `.claude/workflows/todo-followups.js` drops a refuted item with its `also` phrasings and `ingest_followups` counts the workflow's drops as covering them (test in `scripts/todos/test_workflows.js` too).
- Fixed with tests, beyond the cap: an item `ingest_followups` rejects (bad location or severity) no longer counts as returned or feeds `phrased`, so the stored line stays; a re-verify brief and its entry get an absolute `main_root`. Checked and declined: `stray_worktree` is not overwritten on a retry, because failed -> ready moves it to `previous` with the other attempt fields; a new test pins that both stray worktrees are listed.
- Finding 7 (`.claude/agents/todo-worker.md`): the worker no longer re-runs pre-commit with the sandbox off; it fixes a `.claude/agents/` file by hand and names it for the commit-time run. Two existing checks changed with the behaviour: 541 #982-7 (recovery text) and 497 F4 (the released count, and one more incomplete review now blocks).

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0149)

- AC 1: `bash -c 'python3 scripts/todos/test_state_flow.py && python3 scripts/todos/test_state.py && python3 scripts/todos/test_land.py && python3 scripts/todos/test_scan.py && python3 scripts/test_check_archived_todo_status.py && node scripts/todos/test_workflows.js && bash .claude/hooks/test-guard-todo-worker-edit.sh'` — evidence `.sweep-evidence/g3/546-ac0.txt` (not committed), last lines:

  ```text
  PASS: a todo-verifier is not this hook's business
  PASS: a cwd in no git checkout fails open
  PASS: malformed JSON fails open

  Results: 19 passed, 0 failed
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0149)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
