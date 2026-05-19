---
name: todo-resume
description: Resume, restart, or discard an interrupted todo run from its checkpoint file. Use when the user says "/todo-resume", "resume todos", "continue todo run", or "pick up where I left off".
---

# Todo Resume — Interrupted Run Recovery

Detect and recover from a previous `todo-sweep`, `todo-batch`, or `todo-next` that was interrupted (killed process, IDE restart, user abort).

## Steps

1. **Scan for checkpoints**

   ```bash
   ls -1t todos/.completing-todos-run-*.json 2>/dev/null
   ```

   - If **no files found**: report "No interrupted runs found. Start fresh with `/todo-next` or `/todo-sweep`." Exit.

2. **Read the most recent checkpoint**

   Parse the JSON. Extract:
   - `run_id`
   - `started_at`
   - `plan` (array of issue_ids)
   - `completed` (array)
   - `skipped` (array)
   - `aborted_at` (ISO timestamp or null)
   - `filter_flags` (array of strings, e.g., `["--priority", "p3"]`)

3. **Compute progress**

   ```text
   total = len(plan)
   done = len(completed) + len(skipped)
   remaining = [id for id in plan if id not in completed and id not in skipped]
   next_up = remaining[0] if remaining else none
   ```

4. **Present status**

   ```text
   Interrupted Run Found
   =======================
   Run ID: <run_id>
   Started: <started_at>
   Status: <done>/<total> complete, <len(remaining)> remaining

   Completed: <list or "none">
   Skipped:   <list or "none">
   Remaining: <list>

   Next up: <next_up> [<priority>] <title>
   Original filter: <filter_flags or "none">
   ```

5. **Prompt for action**

   ```text
   Choose: (resume / restart / discard / inspect)
   ```

   - **`resume`** → skip all ids in `completed` and `skipped`; invoke `completing-todos` starting at `next_up` with the same `filter_flags`.
   - **`restart`** → delete the checkpoint file (`rm todos/.completing-todos-run-<run_id>.json`), then behave as if the user invoked the **original workflow** (`todo-sweep`, `todo-batch`, or `todo-next`) with the same filter_flags. Re-run from Phase 0 (full re-discovery and confirmation).
   - **`discard`** → delete the checkpoint file. Ask: "Also reset any `in_progress` todos to `pending`? (yes / no)". On `yes`, for each file matching `todos/*-in_progress-*.md`, rename it back to `*-pending-*` and flip frontmatter `status: in_progress` → `status: pending`.
   - **`inspect`** → read the checkpoint JSON in full, show the Work Log entries of the most recently completed todo, then return to step 5.

6. **On `resume` — Delegate to `completing-todos` skill**

   Construct the invocation: include `filter_flags` plus a mechanism to start at `next_up`. If the skill does not natively support resume-from-id, present the plan for the remaining todos and let the user confirm a normal `--ids` invocation on the remaining set.

   Announce: "Resuming run <run_id> from todo <next_up>."

7. **On `restart` — Clean start**

   Delete checkpoint, then:
   - If `filter_flags` was empty → invoke `todo-sweep` workflow.
   - If `filter_flags` contained `--priority`, `--tag`, or `--ids` → invoke `todo-batch` workflow with those flags.
   - If `filter_flags` contained `--ids` with exactly one id → invoke `todo-next` workflow.

8. **Post-flight — Clean up checkpoint**

   After the resumed/restarted run reaches Phase 2 (all remaining todos in terminal state):

   ```bash
   rm -f todos/.completing-todos-run-<run_id>.json
   ```

   Confirm: "Checkpoint cleaned up. Run fully resolved."

## Edge Cases

- **Multiple checkpoints**: Always use the most recently modified (`ls -1t`). If the user wants an older one, they must rename or delete newer ones manually.
- **All todos completed but checkpoint remains**: On detection, report "Run <run_id> appears fully complete but checkpoint was not cleaned up." Offer to delete the stale checkpoint.
- **`in_progress` todo not in checkpoint plan**: This means a todo was started outside the skill. Warn: "Todo `<id>` is in_progress but not tracked by any checkpoint. Manual intervention recommended."

## Safety Notes

- `discard` with reset is **destructive to state** (renames files, flips frontmatter). Always confirm before executing.
- Never delete or move archived todos during recovery.
- If a `git mv` step from a previous run left the repo in an odd state (e.g., staged rename without commit), warn the user to `git status` before proceeding.
