# Completing Todos Skill — Design

**Date:** 2026-05-07
**Status:** Approved (Approach A)
**Author:** Brainstormed with Claude Code

## Goal

Provide a repeatable, reviewable workflow for working through `status: pending` todo files in `todos/` and a frozen template that future audits use to create new todos. The workflow drives one or many todos through implementation → verification → code review → archival, reusing the existing `code-review-orchestrator` rather than duplicating its routing logic.

## Non-Goals

- **Auto-creating todos.** New todos are added by audits or humans; the template enforces structure but the skill does not generate todos.
- **Auto-committing.** The skill never runs `git commit`. The user controls commit boundaries (often one PR per todo, sometimes one PR per batch).
- **PR creation.** Out of scope. Use `commit-commands:commit-push-pr` after.
- **Backfill of the existing `archive/`.** Existing archived files are left alone; the template applies going forward.
- **Reimplementing review routing.** All file-pattern → reviewer mapping lives in `code-review-orchestrator`; this skill calls that orchestrator and consumes its findings.

## User-Visible Surface

### Trigger phrases

The skill activates on any of:

- `/completing-todos` (slash invocation)
- "complete the pending todos"
- "work through the todos"
- "clear all todos"
- "finish todo NNN" (single-todo mode — skill parses `NNN` and treats it as `--ids NNN`)

### Filter flags (parsed from the user's invocation message)

- `--priority p1` — restrict to one priority (default: all)
- `--ids 050,052,056` — restrict to specific issue_ids
- `--skip 053,054` — exclude specific issue_ids
- `--dry-run` — print what would be done; touch nothing

Natural-language id references (e.g., "finish todo 050", "do 052 and 056") are normalized to the equivalent `--ids` flag during Phase 0 plan construction.

Defaults: process all `status: pending` todos, sequentially, in priority then dependency order.

## Components

### 1. `todos/TEMPLATE.md` — frozen template

A single template file at the root of `todos/`. Codifies the structure already documented in [todos/README.md](../../../todos/README.md) (lines 164–213) so future authors and AI audits emit consistent files.

**Header comment** (markdown comment at top, removed when copied):

```markdown
<!--
COPY THIS FILE — do not edit in place.
Filename: NNN-pending-pX-short-slug.md
  NNN     = next zero-padded issue id (check `ls todos/*.md | tail -1`)
  pX      = p1 | p2 | p3 | p4
  slug    = lowercase-kebab-case, ≤ 6 words

Status transitions: pending → in_progress → completed (or blocked).
Filename status segment must match frontmatter status.
-->
```

**Body** (the template proper, identical structure to existing todos):

```markdown
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
```

### 2. `todos/README.md` — small addition

Add one section near the top of [todos/README.md](../../../todos/README.md), immediately after the "Quick Reference" header:

```markdown
## Creating a New Todo

1. Copy `TEMPLATE.md` to `NNN-pending-pX-slug.md` (next id, lowercase kebab slug).
2. Fill every section. Empty Optional sections may be deleted, not left blank.
3. Frontmatter `status` must match the filename status segment.
4. Commit the new file before referencing its issue_id from another todo's `dependencies`.
```

The existing "Todo File Structure" section (lines 164–213) stays — it documents the schema. The new section points authors at the template.

### 3. `.claude/skills/completing-todos/SKILL.md` — the workflow skill

Project-local skill (lives in this repo, ships with the codebase).

**Frontmatter:**

```yaml
---
name: completing-todos
description: Work through pending todo files in todos/ — one, many, or all. Drives each through implementation → verification → code review → archival. Use when the user says "complete the pending todos", "clear todos", "finish todo NNN", or invokes /completing-todos.
---
```

**Body sections** (full prose lives in the skill file; this spec describes shape):

#### Section: Phase 0 — Scope Confirmation

1. Discover candidates:

   ```bash
   grep -l "^status: pending" todos/*.md | sort
   ```

2. Parse each candidate's frontmatter (`priority`, `issue_id`, `dependencies`) and title (first `#` line).
3. Apply filter flags from the user's message (`--priority`, `--ids`, `--skip`).
4. Order: **priority asc** (p1 first), then **dependency-respecting topo sort** within priority. If a cycle is detected, abort with the cycle printed; do not silently break it.
5. Print the proposed run plan:

   ```
   Completing 4 todos sequentially:
     1. 050 [p1] Make Flutter App Buildable From a Fresh Checkout
     2. 052 [p2] CI toolchain drift
     3. 056 [p2] Backend Python vulnerabilities
     4. 054 [p3] Update stale documentation
   Skipped: 053 (--skip), 055 (--priority p2)
   Proceed? (yes / edit / cancel)
   ```

6. Wait for user confirmation. On `edit`, accept a refined filter and re-plan. On `cancel`, exit.

#### Section: Phase 1 — Per-Todo Loop

For each todo in order:

1. **Mark in-progress** (atomic):
   - Edit frontmatter `status: pending` → `in_progress`.
   - `git mv` filename `…-pending-…` → `…-in_progress-…`.
   - Append Work Log entry: `YYYY-MM-DD - Started by completing-todos skill`.

2. **Implement / verify**:
   - Read **Recommended Action** and **Technical Details** sections.
   - If acceptance criteria are already all-checked and the file paths in Technical Details show no diff vs. `HEAD` (`git diff --quiet HEAD -- <paths>`), treat as **verify-only**: skip to step 3 to re-confirm the criteria still hold.
   - Otherwise, perform the work. Use TodoWrite to track sub-steps. Delegate large or specialized work to subagents (Explore for searches, frontend-developer for UI, wagtail-cms-orchestrator for CMS data flow). The skill itself owns the orchestration; subagents own the doing.

3. **Verification gate** (per [verification-before-completion](../../../.claude/skills/superpowers/verification-before-completion/SKILL.md)):
   - Run every command implied by the Acceptance Criteria. Capture output.
   - For each `- [ ]` item: confirm with evidence, then flip to `- [x]`. Never flip without command output you can quote.
   - If any criterion fails: pause, print the failure, ask `(retry / skip-todo / abort-run)`. Do not proceed.

4. **Code review**:
   - Dispatch `code-review-orchestrator` via the Task tool with the changed file list.
   - Severity policy:
     - `critical` or `high` → block. Print the findings, ask `(repair / accept-and-continue / abort-run)`.
     - `medium` or below → list in the Work Log entry, do not block.
   - On `repair`: the skill re-dispatches the *same domain reviewer that surfaced the finding* via the Task tool with a repair prompt (file path + finding description + suggested_fix). It then applies the reviewer's returned edits via Edit, re-runs the verification gate, and exits the loop after this todo so the user can inspect the diff before continuing. (Repair does NOT use `full-review-orchestrator`'s Phase 4 machinery — that's a different surface; this skill keeps repair scoped to a single file.)
   - On `accept-and-continue`: record the unaddressed finding in the Work Log under a `Known issues` subsection so it is not silently lost.

5. **Archive**:
   - Edit frontmatter `status: in_progress` → `completed`.
   - Append Work Log entry: `YYYY-MM-DD - Completed by completing-todos skill. Verification: <one-line summary>. Review: <N findings, N blocking>.`
   - `git mv` `…-in_progress-…` → `…-completed-…` AND move into `todos/archive/`.

6. **Checkpoint**:
   - Append the completed `issue_id` to `todos/.completing-todos-run-<run_id>.json` (see Resumability below).

7. **Continue** to the next todo.

#### Section: Phase 2 — Wrap-Up

After the loop (or after `abort-run`):

1. Print the run summary:

   ```
   Run <run_id> finished.
     Completed: 050, 052, 056
     Skipped:   054 (verification failed: flutter analyze)
     Aborted:   none
   Files moved to todos/archive/. No commits made.
   Suggested next step: review `git status`, then commit per todo or as a batch.
   ```

2. Delete the checkpoint file if all planned todos reached a terminal state (completed or skipped). Keep it if the run was aborted, so a re-invocation can resume.

#### Section: Resumability

A `run_id` is generated at Phase 0 (`date -u +"%Y-%m-%d-%H%M"`).

The checkpoint file `todos/.completing-todos-run-<run_id>.json` shape:

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

On re-invocation, if any `todos/.completing-todos-run-*.json` exists:

- Phase 0 detects it, prints `Found in-progress run <run_id> (2/4 complete). Resume? (yes / restart / discard)`.
- `yes` → skip everything in `completed`/`skipped`; resume at the next planned id.
- `restart` → delete the checkpoint, re-plan from scratch.
- `discard` → delete the checkpoint, exit.

#### Section: Safety Rails

- **Never auto-commit.** Phase 2 explicitly tells the user to commit.
- **Sequential by default.** A `--parallel N` flag is reserved but not implemented in v1; document it as future work in the skill body.
- **Confirmation before the first file move.** Once per run, the skill prompts `About to rename + move 4 files via git mv. Continue? (yes / cancel)` so a misclick or wrong working directory bails out cheaply.
- **Acceptance criteria are gospel.** The skill cannot mark a todo complete unless every `- [ ]` has been flipped to `- [x]` with verification evidence captured in the Work Log.
- **No destructive recovery.** If the workflow fails mid-todo (e.g., `git mv` fails), the skill stops and leaves state as-is for the user to inspect. It does not roll back.
- **Stop on review block.** If `code-review-orchestrator` returns critical/high findings and the user picks `repair`, the skill exits the loop after repair so the user can review the diff before any further todos run.

### 4. Reuse, not rebuild

- **Routing:** `code-review-orchestrator` already maps changed files to domain reviewers. This skill calls it; it does not maintain its own routing table.
- **Verification rigor:** [verification-before-completion](../../../.claude/skills/superpowers/verification-before-completion/SKILL.md) defines what "verified" means. This skill cites and follows it; it does not redefine.
- **Subagents:** For implementation work, the skill dispatches existing agents (`Explore`, `frontend-developer`, `wagtail-cms-orchestrator`, `general-purpose`) chosen by what the todo touches.

## Out of Scope (explicit)

- Generating todos from review findings (separate workflow).
- Synchronizing todos with GitHub Issues (covered by existing `GITHUB_ISSUE_*.md` docs in `todos/`).
- Time tracking or effort-estimate reconciliation.
- Stale-todo detection / cleanup.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Skill marks a todo complete with un-met acceptance criteria | Hard rule: every `- [ ]` must flip to `- [x]` with quoted command output in the Work Log. Skill code path has no "force complete". |
| Sequential runs are slow for many small todos | v1 ships sequential only. Document `--parallel` as future work; do not implement until shared-file collision detection exists. |
| `git mv` fails mid-rename leaves orphan | Skill stops on first error; does not attempt recovery. User inspects `git status` and resolves. |
| User runs skill in wrong directory | One-time confirmation prompt before the first file move. |
| Review orchestrator returns findings the user disagrees with | Skill offers `repair / accept-and-continue / abort-run` — user is in the loop, never overridden. |
| Checkpoint file leaks if process is killed | Checkpoint lives under `todos/.completing-todos-run-*.json`; pattern is git-ignored (add to `.gitignore` as part of implementation). Stale ones can be inspected and deleted by hand. |

## Acceptance Criteria for the Skill Itself

- [ ] `todos/TEMPLATE.md` exists, contains the documented structure, and includes the "do not edit in place" header comment.
- [ ] `todos/README.md` has a "Creating a New Todo" section pointing at the template.
- [ ] `todos/.gitignore` (or root `.gitignore` entry) excludes `todos/.completing-todos-run-*.json`.
- [ ] `.claude/skills/completing-todos/SKILL.md` exists with frontmatter triggering on the documented phrases and `/completing-todos`.
- [ ] Skill body covers all four phases (Scope, Per-Todo Loop, Wrap-Up, Resumability) and the Safety Rails section.
- [ ] Skill explicitly delegates code review to `code-review-orchestrator` via the Task tool — no domain-routing logic in the skill itself.
- [ ] Skill cites `verification-before-completion` as the standard for marking acceptance criteria done.
- [ ] Dry-run a single completed todo from the existing archive (e.g., 046) end-to-end and confirm the prompts and gates fire as designed (no actual file changes — `--dry-run` flag).

## Implementation Order (preview for writing-plans)

1. Write `todos/TEMPLATE.md` and the README addition. Cheapest, smallest blast radius.
2. Add the `todos/.completing-todos-run-*.json` exclusion to `.gitignore`.
3. Write `.claude/skills/completing-todos/SKILL.md` — Phase 0 + Phase 2 + Resumability first (the wrapper), then Phase 1 (the loop body). This lets the skill be invoked end-to-end with `--dry-run` before the loop is fully fleshed out.
4. Dry-run against the current 7 pending todos. Refine prompts based on real output.
5. Live-run on one truly small pending todo (a P3 or P4) to validate the full path including `git mv` and the review dispatch.

`writing-plans` will turn these into a numbered, dependency-aware implementation plan.
