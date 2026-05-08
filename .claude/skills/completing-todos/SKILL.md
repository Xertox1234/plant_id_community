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

For each todo in the planned order:

#### Step 1 — Mark in-progress

This step is atomic from the user's perspective: any failure leaves the file in `pending` state.

1. Edit the file's frontmatter: `status: pending` → `status: in_progress`.
2. Rename the file with `git mv`:
   ```bash
   git mv todos/050-pending-p1-flutter-fresh-checkout-build.md \
          todos/050-in_progress-p1-flutter-fresh-checkout-build.md
   ```
3. Append a Work Log entry to the renamed file:
   ```markdown
   ### YYYY-MM-DD - Started by completing-todos skill (run <run_id>)

   - Picked up by automated workflow.
   ```
4. If `--dry-run`: print what each of the above would do; do not execute.

#### Step 2 — Implement or verify

1. Read the **Recommended Action** and **Technical Details** sections.
2. **Verify-only path:** if every `- [ ]` in Acceptance Criteria is already `- [x]` AND `git diff --quiet HEAD -- <paths-from-Technical-Details>` returns 0 (no diff), skip implementation and proceed to Step 3 to re-confirm. State this explicitly in the Work Log: `Detected verify-only state — no implementation work needed.`
3. **Implementation path:** otherwise, perform the work described. Use TodoWrite to track sub-steps. Delegate substantial or specialized work to subagents:
   - `Explore` for searching the codebase
   - `frontend-developer` for React UI work
   - `wagtail-cms-orchestrator` for CMS data flow / Wagtail page work
   - `general-purpose` as a fallback for cross-cutting research or multi-step work

   The skill itself owns orchestration; subagents do the actual implementation. Always read the relevant pattern docs under `backend/docs/patterns/`, `web/docs/patterns/`, or `plant_community_mobile/docs/patterns/` before writing new code in those areas.
4. If `--dry-run`: do not invoke any subagent or write any file; print the planned subagent dispatches and pattern docs that would be consulted, then continue to Step 3.

#### Step 3 — Verification gate

Per [verification-before-completion](https://github.com/anthropic-experimental/claude-superpowers): every `- [ ]` in Acceptance Criteria must flip to `- [x]` only when backed by quoted command output captured in the Work Log.

1. For each unchecked item in Acceptance Criteria:
   - Run the exact command implied by the criterion (test command, build command, type-check, etc.).
   - Capture the output.
   - If the output proves the criterion holds, flip `- [ ]` to `- [x]` and quote the relevant lines in the Work Log.
   - If the output does NOT prove the criterion: do not flip the box. Continue to the failure handling below.
2. **Failure handling:** if any criterion cannot be flipped, pause and ask:
   ```
   Acceptance criterion failed for todo NNN:
     <criterion text>
   Last command: <command>
   Output:
     <relevant lines>
   Choose: (retry / skip-todo / abort-run)
   ```
   - `retry` — re-run after the user fixes the underlying issue.
   - `skip-todo` — do NOT mark complete. Add this id to `skipped` in the checkpoint, append a Work Log entry explaining why, leave the file in `in_progress` state with its filename also `in_progress`. Continue to the next todo.
   - `abort-run` — stop the loop, jump to Phase 2.
3. If `--dry-run`: print the commands that would run, do not execute them, do not flip any boxes.

#### Step 4 — Code review

1. Compute the changed file list:
   ```bash
   git diff --name-only HEAD
   ```
2. Dispatch the `code-review-orchestrator` agent via the Task tool with this prompt:
   ```
   Review the following changes for todo NNN: <todo title>.
   Changed files:
     - <path 1>
     - <path 2>
   Return findings in your standard JSON shape.
   ```
3. **Severity policy:**
   - `critical` or `high` — block. Print the findings and ask:
     ```
     Code review surfaced N blocking findings for todo NNN:
       [critical] <file>:<line> — <description>
       [high]     <file>:<line> — <description>
     Choose: (repair / accept-and-continue / abort-run)
     ```
   - `medium` or below — list in the Work Log under a `Known issues` subsection; do not block.
4. **On `repair`:** re-dispatch the *same domain reviewer that surfaced each blocking finding* via the Task tool, one invocation per file, with this prompt:
   ```
   Repair the following findings in this file:
   File: <path>
   Findings:
     - line <N>: <description>  (suggested_fix: <text or "—">)
     - line <M>: <description>
   Return JSON: {"file": "...", "edits": [{"old_string": "...", "new_string": "..."}], "unrepaired": [...]}
   ```
   Apply each returned `edit` via the Edit tool. Re-run Step 3 (verification gate) on the repaired files. After repair completes, **exit the loop** so the user can review the diff before further todos run. Append a Work Log entry naming each finding repaired and any left in `unrepaired`.
5. **On `accept-and-continue`:** record each unaddressed blocking finding in the Work Log under `Known issues — accepted at completion`. Do not silently drop them.
6. **On `abort-run`:** stop the loop, jump to Phase 2.
7. If `--dry-run`: print the orchestrator dispatch prompt and stop; do not actually invoke the orchestrator.

#### Step 5 — Archive

1. Edit the file's frontmatter: `status: in_progress` → `status: completed`.
2. Append a Work Log entry:
   ```markdown
   ### YYYY-MM-DD - Completed by completing-todos skill (run <run_id>)

   - Verification: <one-line summary, e.g., "all 5 acceptance criteria passed">.
   - Review: <N findings total, M blocking — addressed via repair / accepted / none>.
   ```
3. Rename and move with `git mv`:
   ```bash
   git mv todos/050-in_progress-p1-flutter-fresh-checkout-build.md \
          todos/archive/050-completed-p1-flutter-fresh-checkout-build.md
   ```
4. Update the checkpoint: append the issue_id to `completed[]`, write the file back.
5. If `--dry-run`: print the planned frontmatter edit, Work Log entry, and `git mv` command; do not execute any of them.

Proceed to the next todo in the plan, or to Phase 2 if this was the last.

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

These are non-negotiable. They override any in-the-moment judgment to "just push through".

1. **Never auto-commit.** The skill never runs `git commit`. Phase 2 explicitly tells the user to commit.
2. **Sequential by default.** A `--parallel N` flag is reserved for future work; do NOT implement it in v1. Todos can collide on shared files; serialization is the safe default.
3. **One-time confirmation before the first file move.** After Phase 0 confirmation, before the first `git mv` of the run, prompt once:
   ```
   About to rename + move N files via git mv across this run. Working directory: <pwd>. Continue? (yes / cancel)
   ```
   Skip this prompt if `--dry-run`.
4. **Acceptance criteria are gospel.** A todo cannot be marked `completed` unless every `- [ ]` is flipped to `- [x]` with verification evidence quoted in the Work Log. There is no `--force-complete`.
5. **No destructive recovery.** If `git mv` or any other step fails mid-todo, stop the loop and leave state as-is for the user to inspect. Do not roll back, do not delete, do not retry silently.
6. **Stop on review block.** If `code-review-orchestrator` returns `critical`/`high` and the user chooses `repair`, exit the loop after that todo so the user can inspect the diff before the next todo starts.
7. **Checkpoint integrity.** Update the checkpoint after every per-todo terminal state (completed or skipped), not at the end of the run. A killed process must be resumable from the last completed todo.
