# Completing Todos Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a project-local skill that drives `status: pending` todo files in `todos/` through implementation → verification → code review → archival, plus a frozen template that future audits use to create new todos.

**Architecture:** One markdown skill at `.claude/skills/completing-todos/SKILL.md` orchestrates the workflow and reuses the existing `code-review-orchestrator` agent. A `todos/TEMPLATE.md` codifies the frontmatter + section structure so future todos stay consistent. Checkpoint files for resumability are git-ignored.

**Tech Stack:** Markdown (skill prose, template, README), bash + grep + git for discovery and verification, Claude Code Skill tool for invocation, existing `.claude/agents/code-review-orchestrator.md` for the review step.

**Spec:** [docs/superpowers/specs/2026-05-07-completing-todos-skill-design.md](../specs/2026-05-07-completing-todos-skill-design.md)

---

## Important Context (read before starting)

**1. `.claude/*` is gitignored.** The repo has `.claude/*` in `.gitignore` (line 175) with an exception only for `.claude/agents/`. The new skill at `.claude/skills/…` will NOT be tracked unless you add `!.claude/skills/`. Task 1 handles this; do not skip it.

**2. This skill is markdown prose, not code.** "Tests" are not unit tests — they are:

- Reading the file back to confirm structure (grep, head, wc)
- Running the discovery commands the skill embeds (`grep -l "^status: pending" todos/*.md`)
- Invoking the skill via the Skill tool with `--dry-run` to confirm prompts/gates fire
- A final live-run on one small todo to validate end-to-end

**3. Filename convention** (from existing todos): `NNN-<status>-pX-<slug>.md` where `NNN` is zero-padded, `pX` is `p1|p2|p3|p4`, and the status segment must match the YAML frontmatter `status:` value.

**4. Existing agents to reuse, not rewrite:**

- [.claude/agents/code-review-orchestrator.md](../../../.claude/agents/code-review-orchestrator.md) — invoked at step 4 of Phase 1
- Specialist agents (`Explore`, `frontend-developer`, `wagtail-cms-orchestrator`, `general-purpose`) — invoked from step 2 of Phase 1 when the todo's work needs them

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `.gitignore` | Modify | Carve out `!.claude/skills/` exception; ignore `todos/.completing-todos-run-*.json` |
| `todos/TEMPLATE.md` | Create | Frozen template — YAML frontmatter + every required section, with a "do not edit in place" header comment |
| `todos/README.md` | Modify | Add "Creating a New Todo" section pointing at the template |
| `.claude/skills/completing-todos/SKILL.md` | Create | The skill itself: frontmatter + Phase 0 + Phase 1 + Phase 2 + Resumability + Safety Rails |

---

## Task 1: Carve out `.claude/skills/` and ignore checkpoint files

**Files:**

- Modify: `.gitignore` (lines 174–176 for the skills exception; lines 203–207 area for checkpoint pattern)

- [ ] **Step 1: Inspect the current `.claude` exception block**

Run: `sed -n '174,177p' .gitignore`
Expected output:

```
# Claude Code configuration and tools (ignore contents, not dir itself, so agents/ exception works)
.claude/*
!.claude/agents/

```

- [ ] **Step 2: Add `!.claude/skills/` exception**

Edit `.gitignore`. Find this exact block:

```
# Claude Code configuration and tools (ignore contents, not dir itself, so agents/ exception works)
.claude/*
!.claude/agents/
```

Replace with:

```
# Claude Code configuration and tools (ignore contents, not dir itself, so agents/ and skills/ exceptions work)
.claude/*
!.claude/agents/
!.claude/skills/
```

- [ ] **Step 3: Add the checkpoint-file ignore pattern**

Edit `.gitignore`. Find this exact block (near line 203):

```
# Full-review per-review artifacts (date-stamped, noisy). Index history committed.
docs/reviews/*-full-review.md
docs/reviews/*-full-review.json
docs/reviews/.*-partial.json
!docs/reviews/INDEX.md
```

Append after it (with one blank line of separation):

```

# Completing-todos run checkpoints (per-run, transient)
todos/.completing-todos-run-*.json
```

- [ ] **Step 4: Verify both ignore rules work**

Run:

```bash
mkdir -p .claude/skills/_probe && touch .claude/skills/_probe/x.md && \
  touch todos/.completing-todos-run-2026-05-07-1200.json && \
  git check-ignore -v .claude/skills/_probe/x.md todos/.completing-todos-run-2026-05-07-1200.json && \
  echo OK_NOT_IGNORED || echo OK_IGNORED
```

Expected output: the skills probe path prints with `!.claude/skills/` as the matching rule (meaning it is NOT ignored), and the checkpoint path prints with the new `todos/.completing-todos-run-*.json` rule (meaning it IS ignored). The `git check-ignore` exit code will be mixed; what matters is each path's rule reference in the output.

Then clean up:

```bash
rm -rf .claude/skills/_probe todos/.completing-todos-run-2026-05-07-1200.json
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore(gitignore): allow .claude/skills/ and ignore completing-todos checkpoints"
```

---

## Task 2: Create `todos/TEMPLATE.md`

**Files:**

- Create: `todos/TEMPLATE.md`

- [ ] **Step 1: Write the template file**

Create `todos/TEMPLATE.md` with exactly this content:

````markdown
<!--
COPY THIS FILE — do not edit in place.

Filename: NNN-pending-pX-short-slug.md
  NNN     = next zero-padded issue id (check `ls todos/*.md | tail -1`)
  pX      = p1 | p2 | p3 | p4
  slug    = lowercase-kebab-case, ≤ 6 words

Status transitions: pending → in_progress → completed (or blocked).
The filename status segment MUST match the frontmatter status value.

Required sections: Problem, Findings, Recommended Action, Technical Details,
Acceptance Criteria, Work Log. Optional sections (Proposed Solutions, Notes)
may be deleted entirely if not used — never leave them blank.
-->

---
status: pending
priority: pX
issue_id: "NNN"
tags: []
dependencies: []
---

# <Concise Issue Title>

## Problem

<1–3 sentences. What's broken or missing, and why it matters.>

## Findings

<Bullet list. Each bullet anchored to a file path, line number, command output,
or commit. State the discovery source (audit run, agent, human).>

## Proposed Solutions

### Option 1: <Recommended>
- **Implementation:** <how>
- **Pros:** <list>
- **Cons:** <list>
- **Effort:** <minutes / hours>
- **Risk:** <low / medium / high, with reason>

### Option 2: <Alternative>
<Same shape. Drop entire section if there is genuinely only one viable option.>

## Recommended Action

<Numbered list of concrete steps. Include code snippets, commands, file paths.>

## Technical Details

<File paths, line numbers, configuration examples, links to relevant patterns
under backend/docs/patterns/, web/docs/patterns/, etc.>

## Acceptance Criteria

- [ ] <Verifiable criterion — passes a test, produces a build, etc.>
- [ ] <Each criterion must be objectively checkable.>

## Work Log

### YYYY-MM-DD - <Event>

- <What happened, by whom, with what outcome.>

## Notes

<Priority rationale, related issue ids, trade-offs, deferred decisions.>
````

- [ ] **Step 2: Verify required sections are present**

Run:

```bash
grep -E '^## ' todos/TEMPLATE.md
```

Expected output (in this order):

```
## Problem
## Findings
## Proposed Solutions
## Recommended Action
## Technical Details
## Acceptance Criteria
## Work Log
## Notes
```

- [ ] **Step 3: Verify frontmatter parses (matches existing todos)**

Run:

```bash
sed -n '/^---$/,/^---$/p' todos/TEMPLATE.md | head -10
```

Expected output (between the `---` markers): five YAML keys — `status`, `priority`, `issue_id`, `tags`, `dependencies` — matching the schema documented in [todos/README.md](../../../todos/README.md#L168-L175).

- [ ] **Step 4: Commit**

```bash
git add todos/TEMPLATE.md
git commit -m "docs(todos): add TEMPLATE.md for new todo files"
```

---

## Task 3: Add "Creating a New Todo" section to `todos/README.md`

**Files:**

- Modify: `todos/README.md` (insert after the "Quick Reference" header, before the existing "Current Stabilization Sweep" subsection)

- [ ] **Step 1: Locate the insertion point**

Run: `grep -n '^## Quick Reference' todos/README.md`
Expected output: `9:## Quick Reference`

Run: `sed -n '9,13p' todos/README.md`
Expected output:

```
## Quick Reference

### Current Stabilization Sweep (May 1, 2026)

These todos were created after a fresh codebase assessment to make the repository safe to resume before new feature work:
```

- [ ] **Step 2: Insert the new section**

Use Edit. Find this exact block:

```
## Quick Reference

### Current Stabilization Sweep (May 1, 2026)
```

Replace with:

```
## Creating a New Todo

1. Copy `TEMPLATE.md` to `NNN-pending-pX-slug.md` (next zero-padded id, lowercase kebab slug, ≤ 6 words).
2. Fill every required section. Optional sections (Proposed Solutions, Notes) may be deleted, never left blank.
3. Frontmatter `status:` must match the filename's status segment at all times.
4. Commit the new file before referencing its `issue_id` from another todo's `dependencies`.

To work through pending todos, invoke the `completing-todos` skill (`/completing-todos` or "complete the pending todos").

## Quick Reference

### Current Stabilization Sweep (May 1, 2026)
```

- [ ] **Step 3: Verify the section landed**

Run: `grep -n '^## Creating a New Todo' todos/README.md`
Expected output: `9:## Creating a New Todo`

Run: `grep -n '^## Quick Reference' todos/README.md`
Expected output: a line number greater than 9 (the section moved down).

- [ ] **Step 4: Commit**

```bash
git add todos/README.md
git commit -m "docs(todos): document template usage and completing-todos entry point"
```

---

## Task 4: Scaffold the skill — frontmatter + overview only

This task creates the file with just enough structure that the Skill tool can load it. Subsequent tasks fill in each phase.

**Files:**

- Create: `.claude/skills/completing-todos/SKILL.md`

- [ ] **Step 1: Create the directory**

Run:

```bash
mkdir -p .claude/skills/completing-todos
```

- [ ] **Step 2: Verify the directory is tracked (not git-ignored)**

Run:

```bash
touch .claude/skills/completing-todos/.gitkeep && \
  git check-ignore -v .claude/skills/completing-todos/.gitkeep; \
  echo "exit=$?"
```

Expected: the path is NOT ignored. `git check-ignore` should print nothing and exit with code 1 (meaning "not ignored"), or print the `!.claude/skills/` exception rule if your git version reports the matching negative rule. Either way, `exit=1` confirms not-ignored.

Then clean up: `rm .claude/skills/completing-todos/.gitkeep`

- [ ] **Step 3: Write the SKILL.md scaffold**

Create `.claude/skills/completing-todos/SKILL.md` with this content:

````markdown
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

(populated in Task 5)

### Phase 1 — Per-Todo Loop

(populated in Tasks 6–7)

### Phase 2 — Wrap-Up

(populated in Task 5)

## Resumability

(populated in Task 5)

## Safety Rails

(populated in Task 8)
````

- [ ] **Step 4: Verify the skill loads (frontmatter is valid)**

Run:

```bash
head -5 .claude/skills/completing-todos/SKILL.md
```

Expected output: opens with `---`, then `name: completing-todos`, then `description: Work through pending todo files…`, then `---`, then a blank line.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/completing-todos/SKILL.md
git commit -m "feat(skill): scaffold completing-todos skill"
```

---

## Task 5: Phase 0 (Scope Confirmation), Phase 2 (Wrap-Up), Resumability

After this task, `--dry-run` is fully functional end-to-end (it never enters Phase 1).

**Files:**

- Modify: `.claude/skills/completing-todos/SKILL.md`

- [ ] **Step 1: Replace Phase 0 placeholder**

Use Edit. Find:

```
### Phase 0 — Scope Confirmation

(populated in Task 5)
```

Replace with:

````
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
````

- [ ] **Step 2: Replace Phase 2 placeholder**

Use Edit. Find:

```
### Phase 2 — Wrap-Up

(populated in Task 5)
```

Replace with:

````
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
````

- [ ] **Step 3: Replace Resumability placeholder**

Use Edit. Find:

```
## Resumability

(populated in Task 5)
```

Replace with:

````
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
````

- [ ] **Step 4: Verify all placeholders are replaced**

Run:

```bash
grep -n '(populated in Task' .claude/skills/completing-todos/SKILL.md
```

Expected output: only Phase 1 placeholders remain (Tasks 6–7). Phase 0, Phase 2, and Resumability placeholders should be gone.

- [ ] **Step 5: Smoke-test the discovery command**

Run the exact command from Phase 0 step 3:

```bash
grep -l "^status: pending" todos/*.md | sort
```

Expected output: the 7 currently pending files (`050-…` through `056-…`).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/completing-todos/SKILL.md
git commit -m "feat(skill): add Phase 0, Phase 2, and resumability to completing-todos"
```

---

## Task 6: Phase 1 — mark in-progress + verify-only fast path

**Files:**

- Modify: `.claude/skills/completing-todos/SKILL.md`

- [ ] **Step 1: Replace Phase 1 placeholder with the loop scaffold + steps 1–2**

Use Edit. Find:

```
### Phase 1 — Per-Todo Loop

(populated in Tasks 6–7)
```

Replace with:

````
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

(Steps 3–5 below — populated in Task 7.)
````

- [ ] **Step 2: Verify the new scaffold landed and Phase 1 outline is complete through Step 2**

Run:

```bash
grep -nE '^#### Step [0-9]' .claude/skills/completing-todos/SKILL.md
```

Expected output:

```
<line>:#### Step 1 — Mark in-progress
<line>:#### Step 2 — Implement or verify
```

- [ ] **Step 3: Sanity-check the rename example**

Run (this is a dry simulation — do not actually rename):

```bash
ls todos/050-pending-p1-flutter-fresh-checkout-build.md
```

Expected output: the file exists. (Confirms the example path in the skill matches reality.)

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/completing-todos/SKILL.md
git commit -m "feat(skill): add Phase 1 steps 1-2 (mark in-progress, implement/verify) to completing-todos"
```

---

## Task 7: Phase 1 — verification gate, code review, archive

**Files:**

- Modify: `.claude/skills/completing-todos/SKILL.md`

- [ ] **Step 1: Replace the Phase 1 trailing placeholder**

Use Edit. Find:

```
(Steps 3–5 below — populated in Task 7.)
```

Replace with:

````
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
````

- [ ] **Step 2: Verify all five steps of Phase 1 are present**

Run:

```bash
grep -nE '^#### Step [0-9]' .claude/skills/completing-todos/SKILL.md
```

Expected output:

```
<line>:#### Step 1 — Mark in-progress
<line>:#### Step 2 — Implement or verify
<line>:#### Step 3 — Verification gate
<line>:#### Step 4 — Code review
<line>:#### Step 5 — Archive
```

- [ ] **Step 3: Verify there are no remaining placeholders**

Run:

```bash
grep -n '(populated in Task' .claude/skills/completing-todos/SKILL.md || echo "NO_PLACEHOLDERS_REMAIN"
```

Expected output: `NO_PLACEHOLDERS_REMAIN`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/completing-todos/SKILL.md
git commit -m "feat(skill): add Phase 1 steps 3-5 (verify, review, archive) to completing-todos"
```

---

## Task 8: Add Safety Rails section

**Files:**

- Modify: `.claude/skills/completing-todos/SKILL.md`

- [ ] **Step 1: Replace the Safety Rails placeholder**

Use Edit. Find:

```
## Safety Rails

(populated in Task 8)
```

Replace with:

````
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
````

- [ ] **Step 2: Confirm no placeholders remain anywhere**

Run:

```bash
grep -nE '\(populated in Task|TBD|TODO:|FIXME' .claude/skills/completing-todos/SKILL.md || echo "CLEAN"
```

Expected output: `CLEAN`

- [ ] **Step 3: Confirm the skill renders top-to-bottom**

Run:

```bash
wc -l .claude/skills/completing-todos/SKILL.md && \
  grep -cE '^## ' .claude/skills/completing-todos/SKILL.md
```

Expected: a non-trivial line count (~250+) and at least 7 top-level `##` headings (`# Completing Todos`, then `Trigger phrases`, `Filter flags`, `Workflow`, `Phases`, `Resumability`, `Safety Rails`).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/completing-todos/SKILL.md
git commit -m "feat(skill): add safety rails to completing-todos"
```

---

## Task 9: Dry-run validation against current pending todos

**Files:** none modified.

- [ ] **Step 1: Invoke the skill in dry-run mode**

In a Claude Code session in this repo, run:

```
/completing-todos --dry-run
```

Or use natural language: "Dry-run completing-todos against all pending todos."

- [ ] **Step 2: Confirm Phase 0 prints the expected plan**

Expected: the skill prints a numbered plan with the 7 current pending todos, ordered p1 → p2 → p3:

- 050 (p1) before 051, 052, 056 (all p2) before 053, 054 (p3) and 055 (p4).
- Topological order within priority based on each file's `dependencies:` field.
- A generated `run_id` of the form `YYYY-MM-DD-HHMM`.
- `[DRY-RUN]` banner present.
- A `Proceed? (yes / edit / cancel)` prompt.

- [ ] **Step 3: Confirm Phase 1 walks each todo without mutating files**

Respond `yes`. Expected: for each planned todo, the skill prints what it WOULD do at each of the five Phase 1 steps (mark in-progress, implement/verify, verify, review, archive) — but no `git mv` runs, no frontmatter edits land, no agents are dispatched.

Verify after the run:

```bash
git status
```

Expected output: `nothing to commit, working tree clean` (or only changes you had before — none from the dry-run).

```bash
ls todos/.completing-todos-run-*.json 2>/dev/null || echo "NO_CHECKPOINT"
```

Expected: `NO_CHECKPOINT` (Phase 0 step 8 explicitly skips checkpoint write under `--dry-run`).

- [ ] **Step 4: Fix any issues found**

If the dry-run produces unexpected ordering, missing prompts, or written files, fix the SKILL.md prose and re-run from Step 1. Commit any fixes:

```bash
git add .claude/skills/completing-todos/SKILL.md
git commit -m "fix(skill): <specific fix> in completing-todos"
```

---

## Task 10: Live-run on one small pending todo

Pick the smallest, lowest-risk pending todo to validate the full path including `git mv` and orchestrator dispatch. Today (2026-05-07) the candidates are:

- `054-pending-p3-update-stale-documentation.md` — docs only, lowest blast radius. **Recommended.**
- `053-pending-p3-repository-hygiene-generated-artifacts.md` — repo hygiene, also low risk.

Avoid 050/051/052/056 for the live-run — those touch real code paths and deserve focused attention.

- [ ] **Step 1: Confirm working tree is clean**

Run:

```bash
git status --short
```

Expected: empty output (clean tree).

- [ ] **Step 2: Invoke the skill scoped to the chosen todo**

In a Claude Code session, run:

```
/completing-todos --ids 054
```

- [ ] **Step 3: Walk through Phase 0**

Confirm the plan shows just todo 054, accept with `yes`, and accept the one-time file-move confirmation when it appears.

- [ ] **Step 4: Walk through Phase 1**

For Step 2 (Implement or verify), perform the actual documentation updates as the skill orchestrates. For Step 3 (verification), run any commands the acceptance criteria imply. For Step 4 (code review), let the `code-review-orchestrator` dispatch and resolve any findings per the severity policy.

- [ ] **Step 5: Verify the file landed in archive**

Run:

```bash
ls todos/archive/054-completed-p3-update-stale-documentation.md && \
  ls todos/054-pending-p3-update-stale-documentation.md 2>/dev/null || echo "ORIGINAL_GONE"
```

Expected: the archived file exists, and `ORIGINAL_GONE` confirms the original is no longer in `todos/`.

Run:

```bash
sed -n '1,8p' todos/archive/054-completed-p3-update-stale-documentation.md
```

Expected: frontmatter shows `status: completed`, plus the unchanged `priority`, `issue_id`, `tags`, `dependencies`.

- [ ] **Step 6: Verify the checkpoint cleaned up**

Run:

```bash
ls todos/.completing-todos-run-*.json 2>/dev/null || echo "CHECKPOINT_CLEAN"
```

Expected: `CHECKPOINT_CLEAN` (Phase 2 step 2 deletes the checkpoint when every planned id reached terminal state).

- [ ] **Step 7: Inspect the diff and commit**

Run:

```bash
git status
git diff --stat HEAD
```

Expected: documentation file changes from the actual implementation, plus the moved + edited todo file.

Commit per the user's preference (one commit for the todo + its implementation, or split). Suggested:

```bash
git add todos/archive/054-completed-p3-update-stale-documentation.md \
        <files-implementation-touched>
git commit -m "docs: update stale documentation (closes todo 054)"
```

- [ ] **Step 8: Note any rough edges**

If the live-run surfaced friction (confusing prompts, missing edge case, off-by-one in ordering), file a tiny follow-up todo using `todos/TEMPLATE.md` to track the polish. The skill is now real and used; further refinement happens in subsequent commits.

---

## Self-Review (post-write)

The plan was checked against the spec for:

- **Spec coverage:** every section in the spec maps to a task.
  - `todos/TEMPLATE.md` → Task 2
  - README addition → Task 3
  - `.gitignore` for checkpoint files → Task 1
  - `.claude/*` exception (gotcha caught during file structure pass) → Task 1
  - SKILL.md frontmatter + Phase 0 → Tasks 4–5
  - Phase 1 (5 steps) → Tasks 6–7
  - Phase 2 + Resumability → Task 5
  - Safety Rails → Task 8
  - Dry-run acceptance criterion → Task 9
  - Live-run acceptance criterion → Task 10
- **Placeholders:** none (`grep -n '(populated in Task'` is run inside Tasks 7 and 8 to enforce this).
- **Type/identifier consistency:** trigger phrases, flag names (`--priority`, `--ids`, `--skip`, `--dry-run`), and the checkpoint JSON shape are identical across Task 5 (definition) and later tasks (consumption).

---

## Implementation Notes

- **Commit cadence:** 8 commits across the 10 tasks (Tasks 9 and 10 only commit on demand if fixes are needed). This matches the spec's "frequent commits" guidance.
- **Order rationale:** `.gitignore` first because the skill file is invisible to git without it. Template + README before the skill so the skill can reference them. Skill frontmatter before any phase content so the Skill tool can load it incrementally during development. Phase 0 / 2 / Resumability before Phase 1 so `--dry-run` is testable end-to-end before the loop body exists. Safety rails last because they apply to a fully-built workflow. Dry-run before live-run because dry-run cannot mutate state.
