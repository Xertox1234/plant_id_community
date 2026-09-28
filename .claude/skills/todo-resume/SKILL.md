---
name: todo-resume
description: Resume, restart, or discard an interrupted todo run from its checkpoint file. Use when the user says "/todo-resume", "resume todos", "continue todo run", or "pick up where I left off".
---

# Todo Resume

1. `ls -1t todos/.sweep-run-*.json 2>/dev/null | head -1` → RUN. If none but a v1
   `todos/.completing-todos-run-*.json` exists: explain it's from the retired v1 skill and offer
   **discard** only. Old `in_progress` todos are picked up by the next scan as stranded.
2. `python3 scripts/todos/state.py show $RUN` shows the todos per stage, and
   `python3 scripts/todos/state.py worktrees $RUN` shows where their staged work is. Ask: resume / restart / discard.
3. **resume**: re-enter `completing-todos` at the earliest stage anything is in:
   - `scanned` → Stage A (triage) for those todos
   - `triaged` → Decide
   - `ready` with no group → `state.py group`; with a group → Stage B for its wave
   - `executing` → the execute workflow was lost. In the same session, `Workflow({scriptPath, resumeFromRunId})`
     if you have its run id. Otherwise `state.py set $RUN <id> failed --field reason="execute workflow lost"`
     then retry it once.
   - `verified` → Stage D (Land)
   - `pr_open` → Stage C, at round `review_round + 1`. First run `ensure-worktree` (sandbox off) and
     `/usr/bin/git -C $WT diff --cached --quiet`. If it exits non-zero, a round-1 repair is staged but was
     never pushed (`ingest-review` already set `review_round=1`). Finish Stage C's `repair-staged` commit,
     `ensure-worktree` and push before any round runs; otherwise round 2 reviews the unrepaired PR.
   - `reviewed` / `merged` → merge confirmation and cleanup
   - `blocked` → report each reason. One whose blocker has since cleared is reopened as in Stage B step 5.
4. **restart**: list `state.py worktrees $RUN` in your reply, delete RUN (confirm first), then re-run the original selector.
5. **discard**: list `state.py worktrees $RUN` in your reply, delete RUN (confirm first). No todo file on `main`
   changes: v2 never leaves a todo `in_progress` on `main`, so there's nothing to reset.
