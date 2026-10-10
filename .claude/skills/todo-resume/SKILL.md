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
   - `pr_open` → Stage C, at round `review_round + 1`. When `review_round` is 1, a round-1 repair may not
     have reached the PR yet. When `review_round` is 2 with `hand_round: 3` (todo 542), the same holds for
     the owner's round-3 repair. The reviewers read the local worktree, but auto-merge ships the remote
     branch. So before round 2 (or round 3), run `ensure-worktree` (sandbox off), then:
     - if `/usr/bin/git -C $WT diff --cached --quiet` exits non-zero, the repair is still staged. Finish Stage C's
       `repair-staged` commit, `ensure-worktree` and push.
     - if `/usr/bin/git -C $WT rev-parse HEAD` differs from the SHA in `/usr/bin/git -C $WT ls-remote origin <branch>`,
       the repair was committed but never pushed. Run `ensure-worktree`, then push.

     When `review_round` is 0 and the round-1 output was never ingested, run `ingest-review --round 1`
     on it first, if its task output file still exists; otherwise rerun round 1.
     A group with `review_residue` ended its last round on `residue`: follow `completing-todos` Stage C step 5
     before rerunning that round.
   - `reviewed` / `merged` → merge confirmation and cleanup
   - `blocked` → report each reason. One whose reason starts `held for the owner` is a PR held for a
     dismissed critical: only the owner clears it, with `state.py clear-hold $RUN G --decision "…"`. A round-2
     hold then goes to `reviewed`: arm it (Stage C step 2). A round-1 hold (`(round 1)` in the reason) goes back
     to `pr_open` with round 1 done: resume it as `pr_open` above. A group round 2 blocked on blocking findings
     (`blocked_by: review round 2`) gets a round 3 only when the owner approves one: `state.py hand-round`
     (`completing-todos` Stage C step 2). Any other blocked group whose blocker has
     since cleared is reopened as in Stage B step 5.
4. **restart**: list `state.py worktrees $RUN` in your reply, delete RUN (confirm first), then re-run the original selector.
5. **discard**: list `state.py worktrees $RUN` in your reply, delete RUN (confirm first). No todo file on `main`
   changes: v2 never leaves a todo `in_progress` on `main`, so there's nothing to reset.
