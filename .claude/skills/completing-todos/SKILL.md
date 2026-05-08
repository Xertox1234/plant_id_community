---
name: completing-todos
description: Work through pending todo files in todos/ — one, many, or all. Drives each through implementation → verification → code review → archival. Use when the user says "complete the pending todos", "clear todos", "finish todo NNN", or invokes /completing-todos.
---

# Completing Todos

Drive `status: pending` todo files in `todos/` through implementation, verification, code review, and archival. Reuse `code-review-orchestrator` for the review step; never reimplement its routing.

**Announce at start:** "I'm using the completing-todos skill to work through pending todos."

## Trigger phrases

- `/completing-todos`
- "complete the pending todos"
- "work through the todos"
- "clear all todos"
- "finish todo NNN" (single-todo mode — parse `NNN` and treat as `--ids NNN`)

## Filter flags

Parsed from the user's invocation message:

- `--priority p1` — restrict to one priority (default: all)
- `--ids 050,052,056` — restrict to specific issue_ids
- `--skip 053,054` — exclude specific issue_ids
- `--dry-run` — print the plan and per-todo prompts; touch nothing

Natural-language id references ("finish todo 050", "do 052 and 056") normalize to the equivalent `--ids` flag during Phase 0.

## Workflow

The skill runs in three phases. Phase 0 confirms scope. Phase 1 loops per todo. Phase 2 wraps up.

(Phase sections appear below — populated in subsequent commits.)

## Phases

### Phase 0 — Scope Confirmation

1. **Generate a `run_id`** for this invocation:
   ```bash
   date -u +"%Y-%m-%d-%H%M"
   ```

2. **Check for an interrupted run.** Glob:
   ```bash
   ls -1 todos/.completing-todos-run-*.json 2>/dev/null
   ```
   If one or more matches exist, read the most recent and follow the **Resumability** section below; do NOT continue with steps 3–8.

3. **Discover candidates:**
   ```bash
   grep -l "^status: pending" todos/*.md | sort
   ```

4. **Parse each candidate's frontmatter** (`priority`, `issue_id`, `dependencies`) and title (the first `# ` line of the file).

5. **Apply filter flags** parsed from the user's invocation message:
   - `--priority pX` — keep only matching priority
   - `--ids A,B,C` — keep only matching issue_ids (also accept natural-language: "finish todo 050" → `--ids 050`)
   - `--skip A,B` — exclude matching issue_ids
   - `--dry-run` — set a flag consulted in Phase 1 (no file mutations, no agent dispatches; just print what each step would do)

6. **Order:** sort by priority ascending (p1 first), then dependency-respecting topological sort within each priority. If a dependency cycle is detected, **abort** with the cycle printed; do not silently break it.

7. **Print the plan and prompt for confirmation:**
   ```
   Completing N todos sequentially [DRY-RUN]:
     1. 050 [p1] Make Flutter App Buildable From a Fresh Checkout
     2. 052 [p2] CI toolchain drift
     ...
   Skipped: 053 (--skip), 055 (--priority p2)
   Run id: 2026-05-07-1430
   Proceed? (yes / edit / cancel)
   ```
   On `edit`, accept a refined filter and re-plan from step 5. On `cancel`, exit without touching anything.

8. **Write the initial checkpoint** (skip if `--dry-run`):
   ```json
   {
     "run_id": "<id>",
     "started_at": "<ISO>",
     "plan": ["050", "052", "056"],
     "completed": [],
     "skipped": [],
     "aborted_at": null,
     "filter_flags": ["--skip", "053"]
   }
   ```
   Path: `todos/.completing-todos-run-<run_id>.json`. Use Write.

Proceed to Phase 1.

### Phase 1 — Per-Todo Loop

(populated in Tasks 6–7)

### Phase 2 — Wrap-Up

After the per-todo loop ends (cleanly, by user `abort-run`, or by an unrecoverable error):

1. **Print the run summary:**
   ```
   Run <run_id> finished.
     Completed: 050, 052, 056
     Skipped:   054 (verification failed: flutter analyze)
     Aborted:   none
   Files moved to todos/archive/. No commits made.
   Suggested next step: review `git status`, then commit per todo or as a batch.
   ```

2. **Delete the checkpoint** if every planned id reached a terminal state (in `completed` or `skipped`). Keep it otherwise so the next invocation can resume.
   ```bash
   rm -f todos/.completing-todos-run-<run_id>.json
   ```

3. **Never run `git commit`.** The skill exits here.

## Resumability

A `run_id` (`YYYY-MM-DD-HHMM`) is assigned in Phase 0. The checkpoint file `todos/.completing-todos-run-<run_id>.json` carries plan + progress so a long run can resume.

Checkpoint shape:
```json
{
  "run_id": "2026-05-07-1430",
  "started_at": "2026-05-07T14:30:00Z",
  "plan": ["050", "052", "056", "054"],
  "completed": ["050", "052"],
  "skipped": [],
  "aborted_at": null,
  "filter_flags": ["--skip", "053"]
}
```

When Phase 0 detects an existing checkpoint:

```
Found in-progress run <run_id> (2/4 complete).
Plan: 050 ✓, 052 ✓, 056 (next), 054
Resume? (yes / restart / discard)
```

- `yes` → skip every id in `completed` and `skipped`; resume Phase 1 at the next planned id.
- `restart` → delete the checkpoint, return to Phase 0 step 3.
- `discard` → delete the checkpoint, exit immediately.

Update the checkpoint after every per-todo terminal state (completed or skipped), using Write to overwrite (last writer wins; the checkpoint always reflects cumulative state).

## Safety Rails

(populated in Task 8)
