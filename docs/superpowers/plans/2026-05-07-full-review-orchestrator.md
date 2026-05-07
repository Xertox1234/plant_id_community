# Full-Repo Code Review Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `full-review-orchestrator` agent that performs whole-codebase reviews, produces persistent reports under `docs/reviews/`, and drives a filter-based repair phase using the existing domain reviewer fleet.

**Architecture:** A new `.claude/agents/full-review-orchestrator.md` agent enumerates active source files, batches by app/feature folder, dispatches all 11 domain reviewers in waves, aggregates JSON findings, writes a markdown + JSON report, and drives an opt-in repair phase. The 11 existing reviewer agent files get a one-time JSON-output contract update; the existing incremental `code-review-orchestrator` is updated to consume the same JSON shape so both orchestrators share the reviewer fleet.

**Tech Stack:** Markdown-based Claude Code agents. No code, no test framework — verification is live agent invocation. Bash + Git for file enumeration. Reports are markdown + JSON files. The orchestrator is a `model: haiku` glue agent; reviewers stay on their existing models.

**Spec:** `docs/superpowers/specs/2026-05-06-full-review-orchestrator-design.md`

---

## File Structure

### Files to create
| Path | Responsibility |
|---|---|
| `.claude/agents/full-review-orchestrator.md` | New orchestrator agent — Phases 0-5, routing table, filter parser spec |
| `docs/reviews/INDEX.md` | Running history of full reviews (committed) |

### Files to modify
| Path | Change |
|---|---|
| `.claude/agents/django-drf-reviewer.md` | Add JSON output format to Review Mode; extend Repair Mode to multi-edit |
| `.claude/agents/wagtail-reviewer.md` | Same |
| `.claude/agents/react-typescript-reviewer.md` | Same |
| `.claude/agents/flutter-dart-reviewer.md` | Same |
| `.claude/agents/flutter-firebase-reviewer.md` | Same |
| `.claude/agents/firebase-cloudfunction-reviewer.md` | Same |
| `.claude/agents/celery-async-reviewer.md` | Same |
| `.claude/agents/api-design-reviewer.md` | Same |
| `.claude/agents/security-reviewer.md` | Same |
| `.claude/agents/performance-reviewer.md` | Same |
| `.claude/agents/test-quality-reviewer.md` | Same |
| `.claude/agents/code-review-orchestrator.md` | Phase 2 dedupe consumes new JSON shape |
| `.gitignore` | Exclude per-review artifacts; keep `INDEX.md` |

### Verification approach (no traditional tests)

For each task that changes a reviewer or orchestrator prompt, verification is **dispatching the agent on a sample input via the Task tool and reading the returned message** to confirm:
1. The output is valid JSON (no surrounding prose).
2. The output matches the schema specified in the spec.
3. For orchestrator phases, the returned data drives the next phase correctly.

A small, real subdirectory (`backend/apps/users/`) is used as the smoke-test target throughout.

---

## Task 1: Add JSON output contract to all 11 review-mode reviewers

**Files:**
- Modify: `.claude/agents/django-drf-reviewer.md` (insert after `## Review Mode — Checklist` section, before `## Pattern References`)
- Modify: `.claude/agents/wagtail-reviewer.md` (same insertion point)
- Modify: `.claude/agents/react-typescript-reviewer.md` (same)
- Modify: `.claude/agents/flutter-dart-reviewer.md` (same)
- Modify: `.claude/agents/flutter-firebase-reviewer.md` (same)
- Modify: `.claude/agents/firebase-cloudfunction-reviewer.md` (same)
- Modify: `.claude/agents/celery-async-reviewer.md` (same)
- Modify: `.claude/agents/api-design-reviewer.md` (same)
- Modify: `.claude/agents/security-reviewer.md` (same)
- Modify: `.claude/agents/performance-reviewer.md` (same)
- Modify: `.claude/agents/test-quality-reviewer.md` (same)

**Insertion template (apply to every reviewer file, adjusting the `agent` value):**

```markdown
## Output Format (Review Mode)

Return ONLY this JSON structure (no surrounding prose, no markdown fences in the actual response — the example fences below show the schema):

```json
{
  "agent": "<REVIEWER-ID>",
  "batch_label": "<batch label received in input>",
  "findings": [
    {
      "severity": "critical|high|medium|low|info",
      "file": "<relative path from repo root>",
      "line": 42,
      "description": "<one sentence — what is wrong>",
      "rule": "<optional: issue # or pattern doc citation>",
      "suggested_fix": "<optional: one-liner hint, not the actual edit>"
    }
  ]
}
```

Severity rules:
- `critical`: security hole, data loss risk, or production-breaking bug
- `high`: real bug or pattern violation that will cause issues
- `medium`: maintainability or correctness concern
- `low`: nit, stylistic, or minor improvement
- `info`: notable but not actionable

If you find no issues, return `{"agent": "<REVIEWER-ID>", "batch_label": "...", "findings": []}`.

If a checklist item does not apply to any file in the batch, do not emit a finding for it.
```

The `<REVIEWER-ID>` value for each file:

| File | Value to substitute |
|---|---|
| `django-drf-reviewer.md` | `django-drf-reviewer` |
| `wagtail-reviewer.md` | `wagtail-reviewer` |
| `react-typescript-reviewer.md` | `react-typescript-reviewer` |
| `flutter-dart-reviewer.md` | `flutter-dart-reviewer` |
| `flutter-firebase-reviewer.md` | `flutter-firebase-reviewer` |
| `firebase-cloudfunction-reviewer.md` | `firebase-cloudfunction-reviewer` |
| `celery-async-reviewer.md` | `celery-async-reviewer` |
| `api-design-reviewer.md` | `api-design-reviewer` |
| `security-reviewer.md` | `security-reviewer` |
| `performance-reviewer.md` | `performance-reviewer` |
| `test-quality-reviewer.md` | `test-quality-reviewer` |

- [ ] **Step 1: Apply insertion to `django-drf-reviewer.md`**

Use Edit. Locate the line `## Pattern References` and insert the template above (with `<REVIEWER-ID>` replaced by `django-drf-reviewer`) directly before it, separated by a blank line.

- [ ] **Step 2: Apply insertion to the remaining 10 reviewer files**

Apply the same insertion to each of:
- `wagtail-reviewer.md`
- `react-typescript-reviewer.md`
- `flutter-dart-reviewer.md`
- `flutter-firebase-reviewer.md`
- `firebase-cloudfunction-reviewer.md`
- `celery-async-reviewer.md`
- `api-design-reviewer.md`
- `security-reviewer.md`
- `performance-reviewer.md`
- `test-quality-reviewer.md`

For each file, locate `## Pattern References` and insert the template directly before it. If a reviewer file has no `## Pattern References` section, insert before `## Repair Mode` instead.

- [ ] **Step 3: Verify each file has the new section**

Run:
```bash
grep -l "## Output Format (Review Mode)" .claude/agents/*-reviewer.md | wc -l
```
Expected output: `11`

- [ ] **Step 4: Verify the agent ID is correct in each**

Run:
```bash
for f in .claude/agents/*-reviewer.md; do
  agent_id=$(basename "$f" .md)
  if ! grep -q "\"agent\": \"$agent_id\"" "$f"; then
    echo "MISMATCH in $f"
  fi
done
```
Expected output: empty (no mismatches printed).

- [ ] **Step 5: Smoke test — dispatch one reviewer and verify JSON output**

Dispatch `security-reviewer` via the Task tool with this prompt:
```
Review these files. Report findings only for the files listed.

Batch label: smoke-test (security-reviewer)
Files:
  - backend/apps/users/auth_service.py
```
Expected: response is a JSON object starting with `{"agent": "security-reviewer", "batch_label": "smoke-test"`. The `findings` array may be empty or non-empty — both are valid.

Failure: response is prose, not JSON, or wraps the JSON in markdown fences with extra text.

If failure, re-read the inserted Output Format section in `security-reviewer.md` and refine wording until JSON is returned reliably.

- [ ] **Step 6: Commit**

```bash
git add .claude/agents/*-reviewer.md
git commit -m "$(cat <<'EOF'
feat(agents): add JSON output contract to all review-mode reviewers

Adds a standardized "## Output Format (Review Mode)" section to each of
the 11 domain reviewer agents. Findings are returned as structured JSON
instead of prose, enabling reliable aggregation in both incremental and
full-repo orchestrators.

EOF
)"
```

---

## Task 2: Extend repair-mode contract to multi-edit per file

**Files:**
- Modify: `.claude/agents/django-drf-reviewer.md` (replace `## Repair Mode` body)
- Modify: All 10 other reviewer files (same change)

**Replacement template for `## Repair Mode` body (applies to every reviewer):**

```markdown
## Repair Mode

When invoked with a list of findings to repair in a single file:

1. Read the affected file with the `Read` tool.
2. Compute the minimal edits that fix all listed findings without changing unrelated code.
3. Return ONLY this JSON structure (no surrounding prose):

```json
{
  "file": "<relative path>",
  "edits": [
    {"old_string": "<exact string to replace>", "new_string": "<replacement>"},
    {"old_string": "<exact string to replace>", "new_string": "<replacement>"}
  ]
}
```

Rules:
- Each `old_string` must be unique enough in the file that an exact match replaces only the intended span.
- Do not apply edits yourself — return them; the orchestrator will apply via the Edit tool.
- If a finding cannot be repaired safely (ambiguous, requires architectural change), include it in an extra field `"unrepaired": [{"line": N, "reason": "..."}]`.
- The `edits` array may be empty if all findings land in `unrepaired`.

The single-finding case is just `edits` of length 1.
```

- [ ] **Step 1: Update `django-drf-reviewer.md`**

Use Edit. The current `## Repair Mode` section is:

```markdown
## Repair Mode

When invoked with a specific finding to repair:
1. Read the affected file with the `Read` tool
2. Identify the minimal code change that fixes the issue
3. Return exactly this structure (no prose):
```json
{
  "file": "apps/forum/viewsets/post_viewset.py",
  "old_string": "exact string to replace",
  "new_string": "replacement string"
}
```
Do not apply the change yourself.
```

Replace the entire `## Repair Mode` section (from the heading line through the final "Do not apply the change yourself.") with the replacement template above.

- [ ] **Step 2: Update the remaining 10 reviewer files**

For each of the other 10 reviewer files, replace the `## Repair Mode` section with the same template. The exact pre-existing text varies slightly per file but always starts with `## Repair Mode` and ends with `Do not apply the change yourself.` or similar. Replace the whole section.

- [ ] **Step 3: Verify all 11 files have the new shape**

Run:
```bash
grep -l '"edits":' .claude/agents/*-reviewer.md | wc -l
```
Expected: `11`

Run:
```bash
grep -L '"edits":' .claude/agents/*-reviewer.md
```
Expected: empty (no files missing the new schema).

- [ ] **Step 4: Smoke test — dispatch a reviewer in repair mode**

First, identify a known issue. Open `backend/apps/forum/viewsets/post_viewset.py` (or any backend Python file) and pick a real-looking line for the test. Dispatch `django-drf-reviewer` with this prompt:

```
Repair the following findings in this file:

File: backend/apps/forum/viewsets/post_viewset.py
Findings:
  - line 1: hypothetical missing import for testing repair-mode JSON output shape
```

Expected: response is JSON of shape `{"file": "...", "edits": [...]}` (or with `unrepaired` populated if the agent decides the finding can't be repaired). Either is valid — what matters is the JSON shape.

- [ ] **Step 5: Commit**

```bash
git add .claude/agents/*-reviewer.md
git commit -m "$(cat <<'EOF'
feat(agents): extend reviewer repair mode to multi-edit per file

Repair-mode contract now accepts a list of findings for one file and
returns an "edits" array, enabling per-file repair dispatch in the
full-review-orchestrator. Single-finding cases continue to work as
"edits" of length 1.

EOF
)"
```

---

## Task 3: Update incremental orchestrator (Phase 2 dedupe) to consume JSON findings

**Files:**
- Modify: `.claude/agents/code-review-orchestrator.md` (replace `## Phase 2 — Present Findings` section)

The existing Phase 2 says "deduplicate by (file + line + issue)." Now that reviewers return JSON, the orchestrator should consume that shape.

**Replacement for `## Phase 2 — Present Findings`:**

```markdown
## Phase 2 — Present Findings

After main Claude collects findings JSON from each dispatched reviewer (each result is `{"agent": "...", "batch_label": "...", "findings": [...]}`), merge all `findings` arrays. Deduplicate by `(file, line, normalized_description)` where `normalized_description` is lowercase + whitespace-collapsed. When two findings collapse, keep both agent IDs in an `agents` array on the merged finding.

Sort merged findings by severity (critical → info), then by file, then by line.

Present:

```
## Code Review — YYYY-MM-DD

### 🔴 CRITICAL (n)
1. file:line — description — agents: [list]

### 🟠 HIGH (n)
...

### 🟡 MEDIUM (n)
...

### 🟢 LOW / INFO (n) → will be written to todos/
...

Repair CRITICAL + HIGH + MEDIUM findings? (yes / no / select numbers)
```
```

- [ ] **Step 1: Apply edit to `code-review-orchestrator.md`**

Use Edit. Replace the entire `## Phase 2 — Present Findings` section (from that heading through the closing triple backtick of its presentation template) with the replacement above.

- [ ] **Step 2: Verify the orchestrator now references JSON shape**

Run:
```bash
grep -A2 "Phase 2 — Present Findings" .claude/agents/code-review-orchestrator.md
```
Expected output includes the phrase `findings JSON from each dispatched reviewer`.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/code-review-orchestrator.md
git commit -m "$(cat <<'EOF'
refactor(agents): code-review-orchestrator consumes JSON findings

Phase 2 dedupe now reads the structured JSON returned by reviewers
(rather than prose). Merges agents arrays when two reviewers report
the same (file, line, normalized_description).

EOF
)"
```

---

## Task 4: End-to-end verify the incremental orchestrator still works

This is a verification-only task — no edits. Confirms the JSON contract change didn't break the existing flow before we build on top of it.

- [ ] **Step 1: Make a trivial code change to trigger the orchestrator**

Create a throwaway change. Pick an existing Python file in `backend/apps/users/` and add a no-op blank line. Stage but do not commit:

```bash
echo "" >> backend/apps/users/auth_service.py
git add -N backend/apps/users/auth_service.py
git diff --name-only HEAD
```

Expected output includes `backend/apps/users/auth_service.py`.

- [ ] **Step 2: Invoke the incremental orchestrator**

Use the Task tool to dispatch `code-review-orchestrator` with the description "Run incremental review on staged change." No additional prompt — the agent reads `git diff` itself.

Expected: orchestrator returns Phase 1 JSON listing `agents_to_invoke` (e.g., `django-drf-reviewer`, `performance-reviewer`).

- [ ] **Step 3: Dispatch the listed reviewers**

For each agent in `agents_to_invoke`, dispatch it via the Task tool with the prompt format from Task 1 Step 5 (Batch label + Files). Collect each JSON response.

Expected: every reviewer returns valid JSON of shape `{"agent": "...", "findings": [...]}`. No prose responses, no markdown fences leaking outside JSON.

- [ ] **Step 4: Re-invoke orchestrator with collected findings**

Pass the array of reviewer outputs back to `code-review-orchestrator` for Phase 2 presentation.

Expected: orchestrator returns severity-grouped findings listing with `agents:` arrays correctly merged.

- [ ] **Step 5: Revert the throwaway change**

```bash
git restore --staged backend/apps/users/auth_service.py
git checkout -- backend/apps/users/auth_service.py
```

- [ ] **Step 6: No commit required (verification only)**

If any verification step failed, return to Tasks 1-3 and refine the contract specifications until the smoke test passes.

---

## Task 5: Create `full-review-orchestrator.md` skeleton + Phase 0

**Files:**
- Create: `.claude/agents/full-review-orchestrator.md`

- [ ] **Step 1: Write the skeleton with frontmatter and Phase 0**

Create `.claude/agents/full-review-orchestrator.md` with this content:

```markdown
---
name: full-review-orchestrator
description: Orchestrates a full-repository code review. Enumerates every active source file, batches by app/feature, dispatches all domain reviewers in waves, produces a persistent report under docs/reviews/, and drives an optional repair phase via filter expressions. Coexists with code-review-orchestrator (incremental); neither replaces the other.

<example>
Context: User wants a comprehensive audit of the entire codebase
user: "Run a full review of the codebase"
assistant: "I'll use the full-review-orchestrator to enumerate active source files, dispatch all domain reviewers in waves, and produce a persistent report."
<commentary>
Use this orchestrator when the user wants a whole-codebase audit. For incremental reviews of recent changes, use code-review-orchestrator instead.
</commentary>
</example>

model: haiku
color: purple
tools: Bash, Read, Glob, Grep, Write
---

You are the full-repository code review orchestrator for the plant_id_community project. You enumerate active source files, plan batched review waves, aggregate findings into a persistent report, and drive an optional repair phase. You hold zero pattern knowledge — all quality logic lives in the domain reviewers.

This agent runs in **six phases**. You are re-invoked between phases by Main Claude. Each phase identifies itself in its first line.

## Phase 0 — Confirm Scope

Run on first invocation when there is no existing partial review for today.

1. Enumerate the candidate roots from this list (skip any that do not exist on disk):
   - `backend/apps`
   - `web/src`
   - `plant_community_mobile/lib`
   - `firebase`
   - `functions`

2. Check disk:
```bash
for dir in backend/apps web/src plant_community_mobile/lib firebase functions; do
  [ -d "$dir" ] && echo "$dir"
done
```

3. Estimate batch count by counting top-level subfolders in each present root:
```bash
ls -1d backend/apps/*/ web/src/*/ plant_community_mobile/lib/*/ 2>/dev/null | wc -l
```
Multiply by ~2.5 (the average number of reviewers per batch given cross-cutting agents).

4. Compute reviewers that will be skipped because their gating root is missing:
   - `firebase/` missing → skip `firebase-cloudfunction-reviewer` (functions also lives separately) and the `flutter-firebase-reviewer` rule for `firebase/**`
   - `functions/` missing → skip `firebase-cloudfunction-reviewer`
   - `plant_community_mobile/lib/` missing → skip `flutter-dart-reviewer`, `flutter-firebase-reviewer`
   - `web/src/` missing → skip `react-typescript-reviewer`
   - `backend/apps/` missing → skip `django-drf-reviewer`, `wagtail-reviewer`, `celery-async-reviewer`, `api-design-reviewer`, `performance-reviewer`, `security-reviewer` (when only firing for backend)

5. Print this prompt to Main Claude:

```
Full review starting:
  Roots: <comma-separated list of present roots>
  Excluded: existing_implementation/, docs/archive/, **/migrations/, vendor (node_modules, .venv, dist, build, __pycache__), generated (*.g.dart, *.freezed.dart, *_pb2.py, .next/, coverage/, .dart_tool/)
  Skipped reviewers (no matching root): <comma-separated list, or "none">
  Estimated batches: <N> across <K> reviewers (≈ <waves> waves of 8)
Proceed? (yes / no / edit-roots)
```

6. If estimated batch count exceeds 100, append a second prompt:
```
This is a large review (<N> invocations across <waves> waves). Proceed? (yes / scope-down / cancel)
```

Then stop. Wait for Main Claude to return with the user's response and re-invoke you for Phase 1.
```

- [ ] **Step 2: Verify the file is well-formed**

Run:
```bash
head -20 .claude/agents/full-review-orchestrator.md
```
Expected: shows the frontmatter (`name:`, `description:`, `<example>`, `model:`, `color:`, `tools:`) and start of the body.

- [ ] **Step 3: Smoke test Phase 0**

Dispatch `full-review-orchestrator` via the Task tool with the prompt: `Run Phase 0 — confirm scope.`

Expected: agent emits the "Full review starting:" block listing real roots from the repo, an estimated batch count, and asks "Proceed?".

If output is missing pieces or includes pattern-knowledge not in the agent file, refine the Phase 0 wording.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/full-review-orchestrator.md
git commit -m "$(cat <<'EOF'
feat(agents): add full-review-orchestrator skeleton with Phase 0

New agent for whole-codebase reviews. Phase 0 confirms scope by
enumerating present source roots, estimating batch count, and gating
on cost (extra confirmation when >100 invocations).

EOF
)"
```

---

## Task 6: Add Phase 1 (planning + wave plan JSON) to the new orchestrator

**Files:**
- Modify: `.claude/agents/full-review-orchestrator.md` (append after Phase 0)

- [ ] **Step 1: Append Phase 1 section**

Append to `.claude/agents/full-review-orchestrator.md`:

```markdown

## Phase 1 — Plan

Triggered when Main Claude returns with the user's "yes" response to Phase 0.

1. Generate a `review_id` of the form `YYYY-MM-DD-HHMM` from the current date and time:
```bash
date -u +"%Y-%m-%d-%H%M"
```

2. Enumerate all candidate files via:
```bash
git ls-files --cached --others --exclude-standard
```

3. Filter the file list — keep only paths under one of the confirmed roots, drop any path matching:
   - `existing_implementation/`
   - `docs/archive/`
   - `**/migrations/**`
   - `**/__pycache__/**`
   - `**/node_modules/**`
   - `**/.venv/**`
   - `**/dist/**`
   - `**/build/**`
   - `**/.next/**`
   - `**/coverage/**`
   - `**/.dart_tool/**`
   - `*.g.dart`
   - `*.freezed.dart`
   - `*_pb2.py`

4. Apply the routing table to compute, for each file, its `primary_agent` and the list of `secondary_agents` that also review it.

### Routing Table

| Path pattern | Reviewer | Primary? |
|---|---|---|
| `backend/apps/<app>/**/*.py` not matching wagtail predicate | `django-drf-reviewer` | ✓ |
| `backend/apps/blog/**` OR `.py` matching `import wagtail|from wagtail|class.*Page` | `wagtail-reviewer` | ✓ (overrides django) |
| `backend/apps/<app>/**/tasks.py`, `**/celery*.py`, `**/beat*.py` | `celery-async-reviewer` | secondary |
| `backend/apps/<app>/**/serializers.py`, `**/api/**` | `api-design-reviewer` | secondary |
| `backend/apps/<app>/**/permissions.py`, `**/auth*.py`, `**/upload*.py`, `**/*token*.py`, `**/*secret*.py` | `security-reviewer` | secondary |
| `backend/apps/<app>/**/tests/**`, `**/test_*.py` | `test-quality-reviewer` | ✓ for test files |
| `backend/apps/<app>/**/*.py` (any) | `performance-reviewer` | secondary |
| `web/src/<feature>/**/*.{ts,tsx}` | `react-typescript-reviewer` | ✓ |
| `web/src/**/*.test.{ts,tsx}` | `test-quality-reviewer` | secondary |
| `plant_community_mobile/lib/<feature>/**/*.dart` | `flutter-dart-reviewer` | ✓ |
| `plant_community_mobile/lib/**/firebase*.dart`, `**/auth*.dart` | `flutter-firebase-reviewer` | secondary |
| `firebase/**`, `*.rules` | `flutter-firebase-reviewer` (primary), `security-reviewer` | flutter-firebase ✓ |
| `functions/**/*.{js,ts}` | `firebase-cloudfunction-reviewer` | ✓ |

The wagtail predicate runs as:
```bash
grep -l "import wagtail\|from wagtail\|class.*Page" <candidate-py-files>
```

5. Group files into batches:
   - Backend: one batch per Django app (subdirs of `backend/apps/`)
   - Web: one batch per top-level subfolder of `web/src/`
   - Mobile: one batch per top-level subfolder of `plant_community_mobile/lib/`
   - Firebase: one batch covering all of `firebase/`
   - Functions: one batch per subdirectory of `functions/`

6. For each (batch, reviewer) pair, emit one invocation. A single batch produces multiple invocations (e.g., `apps/forum` → django-drf-reviewer + performance-reviewer + maybe security-reviewer + maybe celery-async-reviewer).

7. Group invocations into waves of `wave_size` (default 8, configurable via the user invocation).

8. Return ONLY this JSON (no prose):

```json
{
  "review_id": "2026-05-07-1430",
  "started_at": "<ISO 8601>",
  "scope": {
    "roots": ["..."],
    "excluded": ["existing_implementation/", "docs/archive/", "**/migrations/", "**/__pycache__/", "**/node_modules/", "**/.venv/", "**/dist/", "**/build/", "**/.next/", "**/coverage/", "**/.dart_tool/", "*.g.dart", "*.freezed.dart", "*_pb2.py"]
  },
  "primary_map": {
    "<file path>": "<primary agent id>"
  },
  "total_invocations": 34,
  "wave_size": 8,
  "waves": [
    {
      "wave": 1,
      "invocations": [
        {
          "agent": "django-drf-reviewer",
          "batch_label": "apps/forum",
          "files": ["backend/apps/forum/viewsets/post_viewset.py", "backend/apps/forum/serializers.py"]
        }
      ]
    }
  ]
}
```

`primary_map` is included so Phase 4 (repair) can compute the primary agent per file without re-running routing.

Then stop. Main Claude dispatches each wave's invocations in parallel via the Task tool, collects JSON results, checkpoints to `docs/reviews/.<review_id>-partial.json` after each wave, and re-invokes you for Phase 3 once all waves complete.
```

- [ ] **Step 2: Smoke test Phase 1 on a small subtree**

Dispatch `full-review-orchestrator` with: `Run Phase 1 — plan. Limit roots to backend/apps/users only for this smoke test.`

Expected: agent returns valid JSON with `waves` array. Each invocation has a real `agent` ID, a real `batch_label` like `apps/users`, and a `files` array of real Python files.

If the JSON is malformed or `primary_map` is missing keys for files in `waves[].invocations[].files`, refine the Phase 1 wording.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/full-review-orchestrator.md
git commit -m "$(cat <<'EOF'
feat(agents): full-review-orchestrator Phase 1 — wave planning

Phase 1 enumerates files (git ls-files --cached --others
--exclude-standard), filters by exclusion patterns, assigns
primary/secondary agents via the routing table, batches by
app/feature folder, and emits a wave plan JSON with primary_map
included so the repair phase can dispatch per-file without
re-routing.

EOF
)"
```

---

## Task 7: Document Phase 2 dispatch instructions for Main Claude

Phase 2 is Main Claude's responsibility — the orchestrator doesn't run during it — but the orchestrator file must include instructions so any caller knows what to do between Phase 1 and Phase 3.

**Files:**
- Modify: `.claude/agents/full-review-orchestrator.md` (append Phase 2 section)

- [ ] **Step 1: Append Phase 2 section**

Append to `.claude/agents/full-review-orchestrator.md`:

```markdown

## Phase 2 — Dispatch Waves (Main Claude responsibility)

This phase does not invoke this agent. Main Claude executes it directly using the wave plan from Phase 1.

For each wave in `waves`, in order:

1. Dispatch every invocation in that wave **in parallel** via the Task tool. The dispatch prompt for each invocation:

```
Review these files. Report findings only for the files listed.

Batch label: <invocation.batch_label> (<invocation.agent>)
Files:
  - <invocation.files[0]>
  - <invocation.files[1]>
  ...
```

2. Collect each reviewer's JSON response. Validate that each response is valid JSON matching `{"agent": "...", "batch_label": "...", "findings": [...]}`. If a response is invalid:
   - Record `{"agent": "<id>", "batch_label": "<label>", "status": "failed", "error": "<reason>"}` in a `failed_invocations` list.
   - Continue with the rest of the wave; do not block.

3. After all invocations in the wave finish, append the collected findings + failed_invocations to a checkpoint file:
```
docs/reviews/.<review_id>-partial.json
```

   The checkpoint file shape (carries forward Phase 1 state so Phase 3 has everything it needs):
```json
{
  "review_id": "<id>",
  "started_at": "<ISO from Phase 1>",
  "scope": { "roots": ["..."], "excluded": ["..."] },
  "primary_map": { "<file>": "<agent>" },
  "wave_size": 8,
  "total_invocations": 34,
  "completed_waves": [1, 2, 3],
  "findings": [/* flat list of all findings collected so far */],
  "failed_invocations": [/* list of failed invocation records */]
}
```

   Use the Write tool to overwrite the checkpoint after each wave (last writer wins; the checkpoint always contains the cumulative state). The first wave's checkpoint copies `review_id`, `started_at`, `scope`, `primary_map`, `wave_size`, `total_invocations` from the Phase 1 plan output and initializes `findings` and `failed_invocations` as accumulating arrays.

4. Print a one-line progress update to the user:
```
Wave 3/5 complete — 47 new findings (12 critical, 18 high, 14 medium, 3 low)
```

5. Continue to the next wave.

After the final wave, re-invoke `full-review-orchestrator` for Phase 3 with the path to the checkpoint file (`docs/reviews/.<review_id>-partial.json`) — Phase 3 reads it directly and has all the carried-forward state.

### Resume after interruption

If the user re-invokes the orchestrator and a `.<review_id>-partial.json` file already exists:
- The orchestrator (during a re-run of Phase 0) detects the partial and prompts: `Found partial review from <review_id> (waves <X> of <Y> complete). Resume? (y/n/restart)`.
- On `y`, skip waves already in `completed_waves`, dispatch only the remaining waves.
- On `restart`, delete the partial and re-plan from Phase 0.
```

- [ ] **Step 2: Smoke test the documented dispatch flow**

Using the wave plan JSON returned from Task 6 Step 2, manually execute Phase 2 on the small smoke-test subtree:
- Dispatch each invocation in wave 1 in parallel via the Task tool.
- Validate each response is JSON of the expected shape.
- Write the checkpoint file `docs/reviews/.<review_id>-partial.json`.

Expected: every reviewer returns valid JSON; checkpoint file exists with the expected shape; counts in the progress line match reality.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/full-review-orchestrator.md
git commit -m "$(cat <<'EOF'
feat(agents): full-review-orchestrator Phase 2 — dispatch + checkpoint

Documents the Main Claude responsibility between Phase 1 (planning)
and Phase 3 (aggregation): parallel wave dispatch, JSON validation,
incremental checkpointing to .<review_id>-partial.json, progress
reporting, and resume-after-interruption.

EOF
)"
```

---

## Task 8: Add Phase 3 (aggregate + write artifacts)

**Files:**
- Modify: `.claude/agents/full-review-orchestrator.md` (append Phase 3 section)
- Create: `docs/reviews/INDEX.md` (initial empty index)

- [ ] **Step 1: Create the initial INDEX.md**

Run:
```bash
mkdir -p docs/reviews
```

Use Write to create `docs/reviews/INDEX.md`:

```markdown
# Full Review History

| Date | Review ID | Files | Critical | High | Medium | Low | Report |
|---|---|---|---|---|---|---|---|
```

- [ ] **Step 2: Append Phase 3 section to the orchestrator**

Append to `.claude/agents/full-review-orchestrator.md`:

```markdown

## Phase 3 — Aggregate and Write Artifacts

Triggered when Main Claude re-invokes you with the path to `docs/reviews/.<review_id>-partial.json` from Phase 2.

Read the partial checkpoint with the Read tool. It contains: `review_id`, `started_at`, `scope`, `primary_map`, `findings`, `failed_invocations`. All the state Phase 3 needs is in this file.

1. **Deduplicate findings** by `(file, line, normalized_description)` where `normalized_description` is the description lowercased with whitespace collapsed. When two findings collapse, merge their `agent` fields into an `agents` array (preserving both).

2. **Assign IDs**: after dedupe + sort, assign each finding a 1-indexed integer `id`. IDs are stable for this review and are what the repair filter language (`ids:1,4,7-12`) selects against.

3. **Compute primary_agent per finding** using the `primary_map` from the checkpoint. If a file is missing from `primary_map` (shouldn't happen, but defensive), re-derive by re-running the routing table for that file.

4. **Sort** by severity (critical → high → medium → low → info), then by file (lexicographic), then by line (ascending).

5. **Apply severity coercion**:
   - `blocker` → `critical`
   - any other non-canonical value → `info`, and log a warning entry in the report's footer.

6. **Compute stats**:
   - `files_reviewed`: count of distinct files appearing across all invocations (the union of `invocation.files`)
   - `reviewers_invoked`: count of distinct `agent` IDs across all invocations (failed or successful)
   - `total_findings`: length of deduped findings list
   - `by_severity`: counts per canonical severity

7. **Write `docs/reviews/<review_id>-full-review.json`** using Write:

```json
{
  "review_id": "<id>",
  "started_at": "<ISO from Phase 1>",
  "completed_at": "<ISO now>",
  "scope": { "roots": [...], "excluded": [...] },
  "stats": { "files_reviewed": N, "reviewers_invoked": M, "total_findings": K, "by_severity": {...} },
  "findings": [
    {
      "id": 1,
      "severity": "critical",
      "file": "<path>",
      "line": 42,
      "description": "...",
      "rule": "<optional>",
      "suggested_fix": "<optional>",
      "agents": ["django-drf-reviewer", "security-reviewer"],
      "primary_agent": "django-drf-reviewer",
      "repaired": false,
      "repaired_at": null,
      "repair_error": null
    }
  ],
  "failed_invocations": [...]
}
```

8. **Write `docs/reviews/<review_id>-full-review.md`** using Write. Format:

```markdown
# Full Code Review — <human-readable date>

**Scope:** <comma-separated roots>
**Files reviewed:** <stats.files_reviewed>
**Reviewers invoked:** <stats.reviewers_invoked>
**Total findings:** <stats.total_findings> (<by_severity rendered as comma list>)

---

## 🔴 Critical (<count>)

<for each critical finding, grouped by file>
### <file>:<line>
**Finding:** <description>
**Reviewer:** <agents joined with ' · '>
**Rule:** <rule or "—">
**Suggested fix:** <suggested_fix or "—">

---

## 🟠 High (<count>)
<same shape as critical>

## 🟡 Medium (<count>)
<same shape>

## 🟢 Low / Info (<count>)
<abbreviated: file:line — description>

## ⚠️ Failed Invocations (<count>)
<only if non-zero. Format: agent · batch_label — error>
```

9. **Prepend a row to `docs/reviews/INDEX.md`**: read the existing file with Read, insert the new row directly after the table header line (the `|---|...` separator), and write back with Write.

   New row format:
```
| <YYYY-MM-DD HH:MM> | <review_id> | <files_reviewed> | <critical> | <high> | <medium> | <low> | [md](<review_id>-full-review.md) · [json](<review_id>-full-review.json) |
```

10. **Delete the partial checkpoint** file `docs/reviews/.<review_id>-partial.json`:
```bash
rm -f docs/reviews/.<review_id>-partial.json
```

11. **Return a summary block** to Main Claude:

```
Review <review_id> complete.
  Files reviewed: <N>
  Total findings: <K> (<by_severity>)
  Failed invocations: <count>
  Report: docs/reviews/<review_id>-full-review.md
  JSON: docs/reviews/<review_id>-full-review.json

Top 10 critical findings:
1. [file:line] description (agents)
2. ...

Run Phase 4 (repair)? (yes / no)
```

Then stop. Main Claude waits for user input and re-invokes you for Phase 4 if requested.
```

- [ ] **Step 3: Add the .gitignore entries early so test artifacts aren't accidentally committed**

Read the current `.gitignore` and append:

```
# Full-review per-review artifacts (date-stamped, noisy). Index history committed.
docs/reviews/*-full-review.md
docs/reviews/*-full-review.json
docs/reviews/.*-partial.json
!docs/reviews/INDEX.md
```

- [ ] **Step 4: Smoke test Phase 3 with manufactured input**

Manually create a checkpoint file `docs/reviews/.test-2026-05-07-partial.json` with two synthetic findings:

```json
{
  "review_id": "test-2026-05-07",
  "started_at": "2026-05-07T10:00:00Z",
  "scope": {
    "roots": ["backend/apps"],
    "excluded": ["**/migrations/**"]
  },
  "primary_map": {
    "backend/apps/users/auth_service.py": "django-drf-reviewer",
    "backend/apps/users/views.py": "django-drf-reviewer"
  },
  "wave_size": 8,
  "total_invocations": 2,
  "completed_waves": [1],
  "findings": [
    {
      "agent": "django-drf-reviewer",
      "batch_label": "apps/users",
      "severity": "critical",
      "file": "backend/apps/users/auth_service.py",
      "line": 1,
      "description": "Synthetic critical finding for Phase 3 smoke test",
      "rule": "smoke-test"
    },
    {
      "agent": "performance-reviewer",
      "batch_label": "apps/users",
      "severity": "medium",
      "file": "backend/apps/users/views.py",
      "line": 1,
      "description": "Synthetic medium finding for Phase 3 smoke test",
      "rule": "smoke-test"
    }
  ],
  "failed_invocations": []
}
```

Then dispatch the orchestrator with: `Run Phase 3 reading docs/reviews/.test-2026-05-07-partial.json`.

Expected:
- `docs/reviews/test-2026-05-07-full-review.md` exists and is well-formed.
- `docs/reviews/test-2026-05-07-full-review.json` exists, parses as JSON, and contains exactly the two findings with assigned `id` 1 and 2.
- `docs/reviews/INDEX.md` has a new row prepended.

Run:
```bash
python3 -c "import json; print(json.load(open('docs/reviews/test-2026-05-07-full-review.json'))['stats'])"
```
Expected: prints stats dict with 2 total findings.

- [ ] **Step 5: Clean up smoke-test artifacts before commit**

```bash
rm -f docs/reviews/test-2026-05-07-full-review.md docs/reviews/test-2026-05-07-full-review.json
```

Then read `docs/reviews/INDEX.md` and remove the test row using Edit (keep only the header).

- [ ] **Step 6: Commit**

```bash
git add .claude/agents/full-review-orchestrator.md docs/reviews/INDEX.md .gitignore
git commit -m "$(cat <<'EOF'
feat(agents): full-review-orchestrator Phase 3 — aggregate + persist

Phase 3 dedupes findings by (file, line, normalized_description),
sorts by severity/file/line, assigns stable 1-indexed IDs, writes
per-review markdown + JSON artifacts under docs/reviews/, and
prepends a row to docs/reviews/INDEX.md (committed history).
Per-review artifacts are gitignored.

EOF
)"
```

---

## Task 9: Add Phase 4 (filter parser + per-file repair dispatch)

**Files:**
- Modify: `.claude/agents/full-review-orchestrator.md` (append Phase 4 section)

- [ ] **Step 1: Append Phase 4 section**

Append to `.claude/agents/full-review-orchestrator.md`:

```markdown

## Phase 4 — Repair (optional, filter-driven)

Triggered when Main Claude re-invokes you with the user's "yes" response to the Phase 3 repair prompt, plus the `review_id`.

### Step 4a: Prompt for filter

Print:
```
Repair selection (filter expression):
  examples: "all critical+high", "agent:security-reviewer",
            "file:apps/forum/**", "ids:1,4,7-12", "all", "none"
>
```

Stop. Main Claude collects the user's filter string and re-invokes you with it.

### Step 4b: Parse and match

Filter language:
```
filter      = clause ("," clause)*           # comma = OR
clause      = predicate ("+" predicate)*     # plus = AND
predicate   = severity | agent | file | ids | "all" | "none"
severity    = "critical" | "high" | "medium" | "low" | "info"
agent       = "agent:" agent-id
file        = "file:" glob                   # fnmatch semantics
ids         = "ids:" id-list                 # 1,4,7-12,18
```

Parser rules:
- Whitespace ignored *around* operators and predicates (`critical , high` ≡ `critical,high`), but never inside a predicate (`critical high` is an error).
- `none` → return immediately with "No repairs requested."
- `all` → match every finding where `repaired == false`.
- Unknown predicate → return error message and re-prompt: `"Unknown predicate: <token>. Examples: ..."`.
- Glob in `file:` uses Python `fnmatch` semantics; `**` is supported.
- `ids:` ranges are inclusive (`1-3` → 1,2,3).
- Already-repaired findings (`repaired == true`) are filtered out automatically; do not require user to add `+not-repaired`.

Load the JSON report from `docs/reviews/<review_id>-full-review.json`. Apply the filter to the `findings` array.

### Step 4c: Confirm matches

Print:
```
Filter: <user filter>
Matched: <N> findings across <M> files
  - <file 1> (<count>)
  - <file 2> (<count>)
  ...

Dispatch repairs? (yes / no / refilter)
```

Stop. Wait for response.

### Step 4d: Group + dispatch

If user responds `yes`:

1. Group matched findings by `file`. For each file:
   - The owning agent for the repair invocation is `findings[0].primary_agent` (consistent across the file — primary is per-file).
   - Build a single repair invocation:

```
Repair the following findings in this file:

File: <relative path>
Findings:
  - line <N>: <description>
  - line <M>: <description>
```

2. Group repair invocations into waves of `wave_size` (same default 8 as Phase 1).

3. Return JSON to Main Claude:

```json
{
  "phase": "4d",
  "review_id": "<id>",
  "repair_waves": [
    {
      "wave": 1,
      "invocations": [
        {
          "agent": "django-drf-reviewer",
          "file": "backend/apps/forum/upload_views.py",
          "finding_ids": [3, 7, 12],
          "prompt": "Repair the following findings in this file:\n\nFile: ...\nFindings:\n  - line 3: ...\n  - line 7: ...\n  - line 12: ..."
        }
      ]
    }
  ]
}
```

Then stop. Main Claude dispatches each wave in parallel, collects each invocation's `{"file": "...", "edits": [...], "unrepaired": [...]}` response, and applies edits via the Edit tool.

### Step 4e: Apply edits + update JSON (Main Claude responsibility)

For each invocation result:
- For each `edit` in `edits`, call the Edit tool with `file_path = <invocation.file>`, `old_string = edit.old_string`, `new_string = edit.new_string`. If Edit fails (no exact match), capture the error.
- Build a per-finding outcome map: each `finding_id` is repaired if all its edits applied (best-effort: if the agent returned multiple edits without binding them to specific findings, mark all listed `finding_ids` as repaired iff every edit succeeded). Findings listed in `unrepaired` are marked `repaired: false, repair_error: <reason>`.

Re-invoke `full-review-orchestrator` for Phase 4f with the outcome map.

### Step 4f: Persist repair outcomes

Triggered when Main Claude re-invokes you with the outcome map after applying edits.

1. Read `docs/reviews/<review_id>-full-review.json`.
2. For each affected finding by ID, set `repaired: true` and `repaired_at: <ISO now>` if the outcome is success; set `repaired: false, repair_error: <reason>` otherwise.
3. Write the updated JSON back.
4. Print:
```
Repaired <X>/<Y> findings.
  Successes: <X>
  Edit conflicts (file drift): <Z>
  Other failures: <W>
JSON updated: docs/reviews/<review_id>-full-review.json

Run another repair pass? (filter / done)
```

If user responds with another filter, return to Step 4b. If `done`, proceed to Phase 5 prompt.
```

- [ ] **Step 2: Smoke test Phase 4 filter parser**

Dispatch the orchestrator with: `Run Phase 4b with review_id=<smoke-test review id from earlier task> and filter="critical,high"`.

Expected: returns matched findings count and the per-file breakdown.

Try edge cases — verify each:
- `none` → returns "No repairs requested."
- `all` → matches every unrepaired finding.
- `agent:security-reviewer+critical` → only critical findings owned by security-reviewer.
- `file:backend/apps/forum/**` → only findings in forum app.
- `ids:1-3,5` → exactly findings with IDs 1, 2, 3, 5.
- `notarealpredicate` → returns error and re-prompts.
- `critical high` (space, no `+`) → returns error.

- [ ] **Step 3: Smoke test Phase 4 end-to-end on a tiny finding**

Use a JSON report containing one repairable finding (e.g., a missing `select_related()` you can manually verify). Filter `all`, confirm `yes`, observe Edit application, observe Phase 4f update of `repaired: true`.

Verify with:
```bash
python3 -c "import json; r = json.load(open('docs/reviews/<id>-full-review.json')); print([(f['id'], f['repaired']) for f in r['findings']])"
```
Expected: the targeted finding shows `repaired=True`.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/full-review-orchestrator.md
git commit -m "$(cat <<'EOF'
feat(agents): full-review-orchestrator Phase 4 — filter-driven repair

Phase 4 implements filter-expression repair selection (severity, agent,
file glob, ids), per-file dispatch with the file's primary_agent owning
all that file's repairs, wave-based parallel application, edit-conflict
handling for file drift, and JSON persistence of repair outcomes.

EOF
)"
```

---

## Task 10: Add Phase 5 (optional pattern-codifier)

**Files:**
- Modify: `.claude/agents/full-review-orchestrator.md` (append Phase 5 section)

- [ ] **Step 1: Append Phase 5 section**

Append to `.claude/agents/full-review-orchestrator.md`:

```markdown

## Phase 5 — Codifier (optional, opt-in)

Triggered when Main Claude re-invokes you after Phase 4 completion (or after Phase 3 if user skipped repair).

Print:
```
Run pattern-codifier on all findings? (y/n)
  Note: this can be expensive on a large review (<total_findings> findings).
        Recommended only when the review surfaces a recurring pattern not yet captured.
```

Stop. Wait for response.

If user responds `y`:

1. Read the JSON report `docs/reviews/<review_id>-full-review.json`.
2. Format findings into the codifier's expected input format:
```
[<severity>] <file>:<line> — <description> — agent: <primary_agent>
```
3. Return to Main Claude an instruction to dispatch `pattern-codifier` with the formatted findings list.

Main Claude dispatches `pattern-codifier`, receives the codifier's JSON output (`agent_updates`, `pattern_doc_updates`, `learnings`), and applies the updates per the existing codifier flow.

If user responds `n`, print "Skipping codifier. Review complete." and stop.
```

- [ ] **Step 2: Smoke test Phase 5 prompt**

Dispatch orchestrator with: `Run Phase 5 with review_id=<test id>`.

Expected: prints the "Run pattern-codifier?" prompt with the correct total_findings count from the JSON report.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/full-review-orchestrator.md
git commit -m "$(cat <<'EOF'
feat(agents): full-review-orchestrator Phase 5 — opt-in codifier

Phase 5 adds an opt-in dispatch of pattern-codifier with cost warning.
Default is off (large reviews would blow up the codifier). Reuses the
existing codifier contract — orchestrator just formats findings and
hands them off.

EOF
)"
```

---

## Task 11: End-to-end smoke test on a small subtree

This is a verification-only task — no edits. Confirms all phases work together.

- [ ] **Step 1: Invoke the orchestrator scoped to a small subtree**

Dispatch `full-review-orchestrator` with: `Run a full review limited to roots: backend/apps/users only.`

Expected sequence:
1. Phase 0 prints scope summary, asks proceed.
2. On `yes`, Phase 1 returns a wave plan (likely 1-2 waves, ~3-5 invocations).
3. Phase 2 (Main Claude) dispatches reviewers, validates JSON responses, checkpoints.
4. Phase 3 produces `docs/reviews/<review_id>-full-review.md` and `.json`, prepends INDEX.md row, returns top-10 critical summary.
5. Phase 4 prompt offered. Respond `yes`, then filter `critical+high`. Verify count, dispatch repairs.
6. Phase 5 prompt offered. Respond `n` for the smoke test.

- [ ] **Step 2: Verify artifacts**

Run:
```bash
ls -la docs/reviews/
```
Expected: `INDEX.md`, `<review_id>-full-review.md`, `<review_id>-full-review.json`. The partial `.<review_id>-partial.json` should NOT exist (deleted in Phase 3).

Run:
```bash
cat docs/reviews/INDEX.md
```
Expected: header + one row for the smoke-test review.

Run:
```bash
python3 -c "
import json
r = json.load(open('docs/reviews/<review_id>-full-review.json'))
print('stats:', r['stats'])
print('finding ids:', [f['id'] for f in r['findings']])
print('any repaired:', any(f['repaired'] for f in r['findings']))
"
```
Expected: stats dict with non-zero `files_reviewed`, `reviewers_invoked`. Finding IDs are 1-indexed contiguous integers. If repair was actually applied, `any repaired` is `True`.

- [ ] **Step 3: Clean up smoke-test artifacts and INDEX row**

```bash
rm -f docs/reviews/<review_id>-full-review.md docs/reviews/<review_id>-full-review.json
```

Edit `docs/reviews/INDEX.md` to remove the smoke-test row.

If real edits were applied to `backend/apps/users/` files in Step 1's repair phase, decide whether to keep them (legitimate fixes) or revert via `git restore`. Document this decision before committing.

- [ ] **Step 4: No commit (verification only); revert any unwanted changes**

If verification surfaces issues with any phase, return to the relevant task and refine. Do not proceed to Task 12 until end-to-end works on the small subtree.

---

## Task 12: Full-repo dry run (cost confirmation, no repair)

- [ ] **Step 1: Invoke a no-repair full review**

Dispatch `full-review-orchestrator` with no scope restriction. The agent's Phase 0 will print the full estimated batch count.

Expected: estimated batch count is large (likely 30-60). If it exceeds 100, the cost-guardrail second prompt fires.

- [ ] **Step 2: Confirm and run all phases except repair**

Respond `yes` to Phase 0, observe Phase 1 wave plan covering the whole repo, observe Phase 2 wave-by-wave progress lines, observe Phase 3 producing the full report.

Respond `no` to Phase 4 (skip repair).

Respond `n` to Phase 5 (skip codifier).

- [ ] **Step 3: Examine the full report**

Run:
```bash
wc -l docs/reviews/<review_id>-full-review.md
python3 -c "import json; r = json.load(open('docs/reviews/<review_id>-full-review.json')); print(r['stats'])"
```

Expected: human-readable report has hundreds of lines; JSON stats show `files_reviewed` matching the count from Phase 0's estimate; `total_findings` is non-zero.

Skim the markdown report for:
- Severity sections render correctly (🔴, 🟠, 🟡, 🟢).
- Findings are grouped by file within each severity.
- `## ⚠️ Failed Invocations` either absent (no failures) or accurately listed.

- [ ] **Step 4: Decide whether to keep or delete the report**

The first real full review surfaces real findings. Decide with the user whether:
- Delete (this was a smoke test only — files gitignored anyway).
- Keep as the first committed `INDEX.md` entry; per-review artifacts stay gitignored locally.

Default: delete the per-review artifacts; keep the INDEX row.

- [ ] **Step 5: Final commit if any cleanup edits to INDEX.md or .gitignore**

```bash
git add docs/reviews/INDEX.md .gitignore
git commit -m "$(cat <<'EOF'
chore(reviews): record first full-repo review in INDEX

EOF
)" 2>/dev/null || echo "no changes to commit"
```

(The `2>/dev/null || echo` allows the step to succeed if there are no changes to commit.)

---

## Done

All tasks complete when:
- All 11 reviewer files have JSON-output review-mode and multi-edit repair-mode contracts.
- `code-review-orchestrator` Phase 2 consumes the new JSON shape.
- `full-review-orchestrator.md` contains all six phases (0-5).
- `docs/reviews/INDEX.md` exists with the table header.
- `.gitignore` excludes per-review artifacts but keeps INDEX.md.
- A scoped smoke test (Task 11) and a full-repo dry run (Task 12) both complete end-to-end without manual intervention beyond user prompts.
