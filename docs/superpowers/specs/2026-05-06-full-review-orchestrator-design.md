# Full-Repo Code Review Orchestrator — Design

**Status:** Draft, pending implementation
**Author:** brainstorming session 2026-05-06
**Related agents:** `code-review-orchestrator` (incremental, existing), all domain reviewers, `pattern-codifier`

## Problem

The existing `code-review-orchestrator` reviews only files changed against `HEAD` (or `HEAD~1`). It is excellent for "review what I just did," but offers no way to ask "what's the current state of the whole codebase?" — which is what we need for periodic audits, onboarding new contributors, and pre-release sweeps.

## Goal

Add a sibling agent, `full-review-orchestrator`, that:

1. Reviews **every active source file** in the repo (not just changed files).
2. Reuses the existing fleet of domain reviewers without forking them.
3. Produces a **detailed, persistent report** (markdown + JSON) under `docs/reviews/`.
4. Supports a **filter-driven repair phase** that dispatches the same domain reviewers in repair mode.
5. Coexists with the existing incremental orchestrator — neither replaces the other.

## Non-goals

- Not a replacement for the incremental orchestrator. The two complement each other.
- Not a CI/CD pipeline. This is human-triggered.
- Not pattern-codifier-by-default. Codifier on a 300-finding review is a separate (expensive) decision.
- Not a security scanner replacement (Bandit, Snyk, etc. still have their place).

## Decisions captured during brainstorm

| # | Decision |
|---|---|
| Q1 | New agent (B-class), keeps incremental orchestrator unchanged |
| Q2 | Scope: all active source files. Skip `existing_implementation/`, `docs/archive/`, `**/migrations/`, vendor dirs (`node_modules/`, `.venv/`, `dist/`, `build/`, `__pycache__/`), generated artifacts (`*.g.dart`, `*.freezed.dart`, `*_pb2.py`, `*.pb.go`, `coverage/`, `.next/`, `.dart_tool/`) |
| Q3 | Per-app / per-feature-folder batching (5–15 files per invocation) |
| Q4 | Persistent markdown report **+** machine-readable JSON **+** running history in `INDEX.md` |
| Q5 | Filter-expression repair selection (S2) + per-file dispatch (D2) |
| Q6 | New separate agent (A) + wave-based parallelism (P1), default wave size 8 |
| §4 | Per-review artifacts gitignored, `INDEX.md` committed |

## Architecture

### Agent layout

```
.claude/agents/
├── code-review-orchestrator.md       # existing, unchanged
├── full-review-orchestrator.md       # new
├── django-drf-reviewer.md            # existing, contract update
├── wagtail-reviewer.md               # existing, contract update
├── ...                                # all other reviewers, contract update
└── pattern-codifier.md               # existing, unchanged
```

### Mental model

| Orchestrator | Question it answers | Trigger |
|---|---|---|
| `code-review-orchestrator` | "Is what I just changed good?" | After a coding session |
| `full-review-orchestrator` | "What's the current state of the codebase?" | Audits, onboarding, pre-release |

### Frontmatter for the new agent

```yaml
---
name: full-review-orchestrator
description: Orchestrates a full-repository code review by enumerating every active source file, batching by app/feature, dispatching all domain reviewers in waves, producing a persistent report, and driving an optional repair phase via filter expressions.
model: haiku
color: purple
tools: Bash, Read, Glob, Grep, Write
---
```

The orchestrator holds zero pattern knowledge. All quality logic lives in the domain reviewers.

## Phase flow

Six phases. Phases 1, 4, 5, 6 are the orchestrator's turns; Phases 2, 3 are Main Claude doing dispatch / edit application.

### Phase 0 — Confirm scope

The orchestrator prints a summary and gates the work:

```
Full review starting:
  Roots: backend/apps, web/src, plant_community_mobile/lib, firebase, functions
  Excluded: existing_implementation/, docs/archive/, **/migrations/, vendor (node_modules, .venv, dist, build, __pycache__), generated (*.g.dart, *.freezed.dart, *_pb2.py, .next/, coverage/)
  Estimated batches: 34 across 11 reviewers (≈ 5 waves of 8)
Proceed? (yes / no / edit-roots)
```

If estimated invocation count exceeds 100, an extra cost-guardrail prompt is required:
```
This is a large review (137 invocations across 18 waves). Proceed? (yes / scope-down / cancel)
```

### Phase 1 — Plan

The orchestrator enumerates files via `git ls-files --cached --others --exclude-standard` (tracked + untracked, respects `.gitignore`, excludes ignored files), filters by routing rules, groups into batches, builds the wave plan. Returns:

```json
{
  "review_id": "2026-05-06-1430",
  "started_at": "2026-05-06T14:30:00Z",
  "scope": {
    "roots": ["backend/apps", "web/src", "plant_community_mobile/lib", "firebase", "functions"],
    "excluded": ["existing_implementation/", "docs/archive/", "**/migrations/", "**/__pycache__/"]
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

Then stops. Main Claude takes over.

### Phase 2 — Dispatch waves (Main Claude)

For each wave, Main Claude dispatches all invocations in parallel via the Task tool. The dispatch prompt for a reviewer:

```
Review these files. Report findings only for the files listed.

Batch label: apps/forum (django-drf-reviewer)
Files:
  - backend/apps/forum/viewsets/post_viewset.py
  - backend/apps/forum/serializers.py

Return findings in this JSON shape:
{
  "agent": "django-drf-reviewer",
  "batch_label": "apps/forum",
  "findings": [
    {
      "severity": "critical|high|medium|low|info",
      "file": "backend/apps/forum/viewsets/post_viewset.py",
      "line": 42,
      "description": "...",
      "rule": "Issue #131",
      "suggested_fix": "..."
    }
  ]
}
```

After every wave, Main Claude appends collected findings to `docs/reviews/.<review_id>-partial.json` (gitignored checkpoint) and prints a one-liner:

```
Wave 3/5 complete — 47 new findings (12 critical, 18 high, 14 medium, 3 low)
```

### Phase 3 — Aggregate and write artifacts

Main Claude re-invokes the orchestrator with the full collected findings list. The orchestrator:

1. Deduplicates by `(file, line, finding_hash)`. When multiple agents report the same finding, the `agents` array keeps both; `primary_agent` is computed once via the routing table.
2. Sorts by severity (critical → info), then by file, then by line.
3. Writes `docs/reviews/<review_id>-full-review.md` (human-readable).
4. Writes `docs/reviews/<review_id>-full-review.json` (machine-readable, schema below).
5. Prepends a row to `docs/reviews/INDEX.md`.
6. Returns to Main Claude a summary block: counts by severity, link, top 10 critical findings.

### Phase 4 — Repair (orchestrator drives, Main Claude applies)

The orchestrator prompts:

```
Repair selection (filter expression):
  examples: "all critical+high", "agent:security-reviewer",
            "file:apps/forum/**", "ids:1,4,7-12", "all", "none"
>
```

The orchestrator parses the filter, prints matched count + per-file breakdown, asks confirmation:

```
Filter: critical+agent:security-reviewer
Matched: 8 findings across 5 files
  - backend/apps/forum/upload_views.py (3)
  - backend/apps/users/auth_service.py (2)
  - ...

Dispatch repairs? (yes / no / refilter)
```

On yes, the orchestrator groups matched findings **by file** (per-file dispatch — D2). For each file, the `primary_agent` is the sole repair owner; all findings for that file (regardless of which agent flagged them) go in a single repair invocation.

Repair invocations dispatch in waves (same wave size as Phase 2). Each invocation returns:

```json
{
  "file": "backend/apps/forum/upload_views.py",
  "edits": [
    {"old_string": "...", "new_string": "..."},
    {"old_string": "...", "new_string": "..."}
  ]
}
```

Main Claude applies edits. After each wave, the orchestrator confirms applied repairs and updates the JSON (`repaired: true`, `repaired_at: <ISO timestamp>`).

After the full repair pass:

```
Repaired 8/8 findings.
JSON updated: docs/reviews/2026-05-06-1430-full-review.json
Run another repair pass? (filter / done)
```

### Phase 5 — Codifier (optional)

```
Run pattern-codifier on all findings? (y/n)
  Note: this can be expensive on a large review (304 findings). Recommended only when the review surfaces a recurring pattern.
```

On yes, dispatch the codifier with the full findings list. Codifier output (JSON instructions) is applied by Main Claude, same as the existing flow.

## Sub-agent contract (review mode)

Domain reviewers must return findings as **JSON**, not prose. This is a one-time, mechanical update across all 11 reviewer agent files. The incremental orchestrator benefits — its dedupe logic gets simpler.

### Review-mode input

```
Review these files. Report findings only for the files listed.

Batch label: <batch_label>
Files:
  - <relative path>
  - <relative path>
```

### Review-mode output

```json
{
  "agent": "<reviewer-id>",
  "batch_label": "<batch_label>",
  "findings": [
    {
      "severity": "critical|high|medium|low|info",
      "file": "<relative path>",
      "line": <int>,
      "description": "<one sentence>",
      "rule": "<optional citation: issue #, pattern doc>",
      "suggested_fix": "<optional one-liner>"
    }
  ]
}
```

### Severity coercion

If a reviewer returns a non-canonical severity:
- `blocker` → `critical`
- anything else → `info` + a warning logged in the report

This protects the report shape without losing findings.

## Sub-agent contract (repair mode)

The current per-finding repair contract (input `{file, line, finding}` → output `{file, old_string, new_string}`) is extended additively to support **multiple findings per file**:

### Repair-mode input

```
Repair the following findings in this file:

File: <relative path>
Findings:
  - line 42: <description>
  - line 78: <description>
```

### Repair-mode output

```json
{
  "file": "<relative path>",
  "edits": [
    {"old_string": "...", "new_string": "..."},
    {"old_string": "...", "new_string": "..."}
  ]
}
```

The single-finding form continues to work: `edits` array of length 1.

## Routing & primary-agent resolution

Lives in the orchestrator agent file as a routing table (same shape as the incremental one, evaluated per batch).

| Path pattern | Batch unit | Reviewer(s) | Primary? |
|---|---|---|---|
| `backend/apps/<app>/**/*.py` (excluding blog, wagtail-using) | one batch per app | `django-drf-reviewer` | primary for `.py` |
| `backend/apps/blog/**` OR `.py` matching `grep -l "import wagtail\|from wagtail\|class.*Page"` | one batch per app | `wagtail-reviewer` | overrides django for these files |
| `backend/apps/<app>/**/tasks.py`, `**/celery*.py`, `**/beat*.py` | one batch per app | `celery-async-reviewer` | secondary |
| `backend/apps/<app>/**/serializers.py`, `**/api/**` | one batch per app | `api-design-reviewer` | secondary |
| `backend/apps/<app>/**/permissions.py`, `**/auth*.py`, `**/upload*.py`, `**/*token*.py`, `**/*secret*.py` | one batch per app | `security-reviewer` | secondary |
| `backend/apps/<app>/**/tests/**`, `**/test_*.py` | one batch per app | `test-quality-reviewer` | primary for test files |
| `backend/apps/<app>/**/*.py` (any) | one batch per app | `performance-reviewer` | secondary |
| `web/src/<feature>/**/*.{ts,tsx}` | one batch per top-level subfolder of `web/src/` | `react-typescript-reviewer` | primary for `.ts/.tsx` |
| `web/src/**/*.test.{ts,tsx}` | rolled into the feature batch | `test-quality-reviewer` | secondary |
| `plant_community_mobile/lib/<feature>/**/*.dart` | one batch per top-level `lib/` subfolder | `flutter-dart-reviewer` | primary for `.dart` |
| `plant_community_mobile/lib/**/firebase*.dart`, `**/auth*.dart` | rolled into feature batch | `flutter-firebase-reviewer` | secondary |
| `firebase/**`, `*.rules` | one batch | `flutter-firebase-reviewer`, `security-reviewer` | flutter-firebase primary |
| `functions/**/*.{js,ts}` | one batch per function dir | `firebase-cloudfunction-reviewer` | primary |

### Primary-agent rule

Every file has exactly one primary agent. In repair phase, the primary owns the repair regardless of which reviewer flagged each finding. This eliminates edit conflicts when multiple reviewers flag the same file.

### Cross-cutting reviewers

`security-reviewer`, `performance-reviewer`, `api-design-reviewer`, `celery-async-reviewer`, `test-quality-reviewer` are **never primary** for backend Python code (except `test-quality-reviewer` on test files). They run alongside the primary domain reviewer; their findings flow through the primary in repair phase.

### Wagtail override

The same `.py` file can match both `django-drf-reviewer` and `wagtail-reviewer`. Wagtail wins as primary when its grep predicate matches. The orchestrator runs the grep during Phase 1 to assign primaries.

## Filter language for repair

```
filter      = clause ("," clause)*           # comma = OR
clause      = predicate ("+" predicate)*     # plus = AND
predicate   = severity | agent | file | ids | "all" | "none"
severity    = "critical" | "high" | "medium" | "low" | "info"
agent       = "agent:" agent-id
file        = "file:" glob                   # fnmatch semantics, ** supported
ids         = "ids:" id-list                 # 1,4,7-12,18
```

### Examples

| Filter | Meaning |
|---|---|
| `all` | every finding |
| `critical` | all critical findings |
| `critical,high` | critical OR high |
| `critical+agent:security-reviewer` | critical AND owned by security-reviewer |
| `file:apps/forum/**` | findings in forum app |
| `file:apps/forum/**+high` | high findings in forum |
| `ids:1-12,47,89-95` | specific finding IDs |
| `none` | no-op, exits repair phase |

### Parser behavior

- Whitespace ignored *around* operators and predicates (`critical , high` ≡ `critical,high`), but never inside a predicate (`critical high` is an error, not `criticalhigh`).
- Unknown predicates → error message, re-prompt (do not crash).
- Glob matching uses Python `fnmatch` semantics (`**` works like in `git`).
- Empty match set → "0 findings matched, refine filter or type 'none'".
- `ids:` ranges are inclusive.
- `repaired: true` findings are filtered out automatically — no need to write `+not-repaired`.

## Output artifacts

All artifacts live under `docs/reviews/`.

### `<review_id>-full-review.md` (human-readable, gitignored)

```markdown
# Full Code Review — 2026-05-06 14:30

**Scope:** backend/apps, web/src, plant_community_mobile/lib, firebase, functions
**Files reviewed:** 287
**Reviewers invoked:** 11
**Total findings:** 304 (12 critical, 47 high, 89 medium, 156 low)

---

## 🔴 Critical (12)

### backend/apps/forum/viewsets/post_viewset.py:42
**Finding:** ViewSet.get_permissions() does not call super() — @action permission_classes silently ignored
**Reviewer:** django-drf-reviewer · security-reviewer
**Rule:** Issue #131
**Suggested fix:** Add `permissions = super().get_permissions()` then extend

` ``python
# current
def get_permissions(self):
    return [IsAuthenticated()]
` ``

---

## 🟠 High (47)
[same shape, grouped by file within severity]

## 🟡 Medium (89)
[same]

## 🟢 Low / Info (156)
[abbreviated — file:line — description, no excerpts]

## ⚠️ Failed Invocations (0)
[only present when reviewers failed]
```

### `<review_id>-full-review.json` (machine-readable, source of truth, gitignored)

```json
{
  "review_id": "2026-05-06-1430",
  "started_at": "2026-05-06T14:30:00Z",
  "completed_at": "2026-05-06T14:47:12Z",
  "scope": {
    "roots": ["backend/apps", "web/src", "plant_community_mobile/lib", "firebase", "functions"],
    "excluded": ["existing_implementation/", "docs/archive/", "**/migrations/", "**/__pycache__/"]
  },
  "stats": {
    "files_reviewed": 287,
    "reviewers_invoked": 11,
    "total_findings": 304,
    "by_severity": {"critical": 12, "high": 47, "medium": 89, "low": 156}
  },
  "findings": [
    {
      "id": 1,
      "severity": "critical",
      "file": "backend/apps/forum/viewsets/post_viewset.py",
      "line": 42,
      "description": "ViewSet.get_permissions() does not call super()...",
      "rule": "Issue #131",
      "suggested_fix": "Add `permissions = super().get_permissions()` then extend",
      "agents": ["django-drf-reviewer", "security-reviewer"],
      "primary_agent": "django-drf-reviewer",
      "repaired": false,
      "repaired_at": null,
      "repair_error": null
    }
  ],
  "failed_invocations": []
}
```

`id` is 1-indexed and stable for this review — the value the `ids:1,4,7-12` filter selects against.

### `INDEX.md` (committed running history, prepend new entries)

```markdown
# Full Review History

| Date | Review ID | Files | Critical | High | Medium | Low | Info | Report |
|---|---|---|---|---|---|---|---|---|
| 2026-05-06 14:30 | 2026-05-06-1430 | 287 | 12 | 47 | 89 | 156 | 23 | [md](2026-05-06-1430-full-review.md) · [json](2026-05-06-1430-full-review.json) |
```

### `.gitignore` additions

```
# Per-review artifacts (date-stamped, noisy). Index history committed.
docs/reviews/*-full-review.md
docs/reviews/*-full-review.json
docs/reviews/.*-partial.json
!docs/reviews/INDEX.md
```

### Checkpoint file: `.<review_id>-partial.json`

Hidden, gitignored, written incrementally after each wave. Used for resume-after-interruption (Phase 2 resilience).

## Error handling and edge cases

### Sub-agent invocation failures

A reviewer might timeout, return malformed JSON, or hit a model error. Strategy:

- Main Claude validates each invocation result. Invalid → mark as `status: "failed"` in the running list with the captured error.
- Failed invocations do not block subsequent waves.
- Phase 3 report includes `## ⚠️ Failed Invocations` section with `{agent, batch_label, error}`.
- Orchestrator prompts: `3 invocations failed. Retry just the failed ones? (y/n)`. On yes, retry as a new wave.

### Partial completion / interruption

If the user interrupts mid-review (Ctrl-C, session ends):
- Each wave's findings are checkpointed to `docs/reviews/.<review_id>-partial.json`.
- On re-invocation with a matching `review_id`, the orchestrator detects the partial: `Found partial review from 2026-05-06-1430 (waves 1-3 of 5 complete). Resume? (y/n/restart)`.
- On resume, the orchestrator skips already-completed waves and continues at the next pending wave.

### Empty batches

If a routing rule matches no files (e.g., no `firebase/` directory), the rule is silently dropped from the wave plan. Logged in Phase 0 summary as `Skipped: firebase-cloudfunction-reviewer (no matching files)`.

### Repair edit conflicts

If a repair edit's `old_string` no longer matches (file modified since review):
- Main Claude attempts the Edit tool; on failure, marks the finding `repaired: false, repair_error: "old_string no longer matches"`.
- Orchestrator reports: `5 of 8 repairs applied. 3 failed (file drift).` and lists drift findings.
- Drifted findings stay in JSON; user can re-run review or repair manually.

### Wave plan stability

If files are edited during review, the orchestrator does not re-plan. Findings reference line numbers as captured at review time. The repair phase handles drift via the edit-conflict path.

### Concurrent reviews

Different `review_id` values cannot collide (timestamp includes minute). Same minute is unlikely; if it happens, second invocation sees the existing partial and prompts to resume or pick a different review_id.

## Implementation order

To minimize risk, implement in this order. The reviewer JSON contract change touches every reviewer and the existing incremental orchestrator — verify it works before building anything new.

1. **Update reviewer JSON contract** (review mode + repair mode) across all 11 reviewer files. Mechanical change.
2. **Verify incremental orchestrator** still works end-to-end against a small change. The existing orchestrator's Phase 2 dedupe logic also needs to be updated to consume the new JSON shape.
3. **Build `full-review-orchestrator.md`** with Phase 0, Phase 1 (planning + JSON output), and Phase 3 (aggregation + artifact writing).
4. **Implement Phase 2 dispatch glue** (Main Claude side — instructions in the orchestrator's prompt).
5. **Implement Phase 4 repair** (filter parser, per-file dispatch, JSON updates).
6. **Implement Phase 5 codifier** (optional, opt-in only).
7. **Add `.gitignore` entries** and create empty `docs/reviews/INDEX.md` with table header.
8. **Smoke test** on a small subtree (`/full-review backend/apps/forum`).
9. **Full repo test.**

## Open questions

None at design time. Resolutions:
- Gitignore: per-review artifacts ignored, `INDEX.md` committed (decided in §4).
- Codifier default: off (opt-in per review, decided in Phase 5).
- Wave size: configurable via `--wave-size N`, default 8 (decided in §5).

## Risks

| Risk | Mitigation |
|---|---|
| Reviewer JSON contract breaks incremental orchestrator | Verify incremental orchestrator end-to-end as step 2 of implementation |
| Reviewers produce unstable line numbers across runs | Acceptable; review_id timestamps each snapshot, repair handles drift |
| Large reviews (>100 invocations) burn cost | Phase 0 cost-guardrail prompt; user can scope-down |
| Partial state checkpoints leak sensitive content | Hidden file (`.<review_id>-partial.json`), gitignored, lives only under `docs/reviews/` |
| `pattern-codifier` blowup on 300+ findings | Default off; explicit opt-in with cost warning in Phase 5 |
| Multiple reviewers double-report the same issue | Phase 3 dedupe by `(file, line, finding_hash)`; primary_agent owns repair |

## Success criteria

The agent is done when:

1. Running it on a clean repo produces a valid `INDEX.md` row, a populated `<review_id>-full-review.md`, and a parseable `<review_id>-full-review.json`.
2. The repair phase, given filter `critical+agent:security-reviewer`, applies edits to disk and updates `repaired: true` in the JSON.
3. Interrupting mid-review and re-invoking offers a resume prompt and skips completed waves.
4. The incremental `code-review-orchestrator` continues to work unchanged after the reviewer JSON contract update.
5. All 11 domain reviewers respond correctly to the new review-mode JSON-output requirement and the multi-finding repair-mode input.
