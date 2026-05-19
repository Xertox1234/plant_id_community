---
name: todo-sweep
description: Batch through all pending todos in priority order. Use when you want to clear the backlog — when the user says "/todo-sweep", "sweep todos", "clear all pending todos", or "batch complete todos".
---

# Todo Sweep — Backlog Clearer

Run the `completing-todos` skill across **all** pending todos, sequentially, in priority order.

## Steps

1. **Pre-flight — Working directory check**

   ```bash
   git status --short
   ```

   - If dirty, warn and offer: `stash / cancel / continue-anyway`
   - On `stash`: `git stash push -m "todo-sweep pre-flight"`
   - On `cancel`: exit.
   - On `continue-anyway`: proceed but remind user to review diff before committing.

2. **Smoke test — Quick repo health check**

   Run a 30-second smoke test appropriate to the codebase. Choose the fastest relevant check:

   ```bash
   # If backend Django tests are fast:
   cd backend && python -m pytest apps/blog/tests/test_smoke.py -x --tb=short 2>/dev/null || true

   # Or if a lint/type-check is faster:
   # cd web && npm run type-check 2>/dev/null || true
   ```

   This is informational only; do not block on failure.

3. **Discover and scope**

   Count pending todos by priority:

   ```bash
   for p in p1 p2 p3 p4; do
     count=$(grep -l "^priority: $p" todos/*.md 2>/dev/null | wc -l | tr -d ' ')
     echo "$p: $count"
   done
   ```

   Also run:

   ```bash
   grep -l "^status: pending" todos/*.md | grep -v -E '/(TEMPLATE|README|GITHUB|IMPLEMENTATION|QUICK_REFERENCE|RESEARCH)\.md$' | wc -l
   ```

4. **Confirm batch scope**

   Present to user:

   ```text
   Todo Sweep Plan
   ===============
   Pending todos: <N total>
     P1: <n>  P2: <n>  P3: <n>  P4: <n>
   Order: priority ascending, then dependency-respecting topo-sort.
   Mode: SEQUENTIAL (one at a time, safe for colliding files).
   Dry-run available.

   Proceed? (yes / dry-run / cancel)
   ```

   - On `dry-run`: invoke `completing-todos` with `--dry-run`. Print the plan and stop.
   - On `cancel`: exit.

5. **Invoke `completing-todos` skill** with no filter flags (all pending).

   Announce: "I'm using the completing-todos skill to sweep through all pending todos."

6. **Per-todo safety pause**

   After each todo is archived (Phase 1 Step 5 completes), briefly summarize:

   ```text
   Completed <issue_id>. <N> of <total> done.
   Changed files this todo: <list from git diff --name-only HEAD~1..HEAD or git diff --stat>
   ```

   If `completing-todos` returns `skipped` for a todo, note it and continue to the next.

7. **Post-flight — Run summary & commit strategy**

   After Phase 2 wrap-up:

   ```bash
   git diff --stat HEAD
   ```

   Suggest commit options:

   ```text
   Sweep complete.
     Completed: <list>
     Skipped:   <list or "none">

   Commit strategies:
     A) One commit per todo (safest, verbose history):
        for each todo: git add <its-files> && git commit -m "<id>: <title>"
     B) Single batch commit (concise):
        git commit -m "todo-sweep: resolve <N> pending issues" -m "<bullet list of ids>"
     C) Review interactively: git add -p
   ```

   If a stash exists from step 1, remind: `Run git stash pop when ready.`

## Safety Notes

- This workflow is intentionally **sequential**; no `--parallel` flag is exposed.
- If the user chooses `repair` during code review (Phase 1 Step 4), `completing-todos` exits the loop after that todo. The workflow then presents the option to `continue-sweep` (resume the remaining plan) or `stop-here`.
- Never auto-commit.
