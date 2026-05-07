# Self-Improving Agent Team Design
**Date**: 2026-05-06  
**Status**: Approved — ready for implementation  
**Project**: plant_id_community

---

## Problem Statement

The existing agent files (`comprehensive-code-reviewer.md`, `code-review-specialist.md`, `django-performance-reviewer.md`) were written months ago against old principles. They embed all patterns inline, making them monolithic, token-expensive, and impossible to keep current. There is no feedback loop — patterns discovered during one session are never recorded for future sessions.

This design replaces them with a self-improving team: 13 focused agents where domain knowledge lives in domain-specific files, reviews run in parallel against changed files only, and every session compounds into better pattern coverage.

---

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Orchestration model | Lightweight dispatch (Approach A) | Orchestrator stays thin forever — routes only, holds no patterns |
| Agents write files | No — main Claude only | Clean permission model, user sees all changes before they land |
| Review scope | Changed files only (`git diff --name-only HEAD`) | Full-repo review exhausts context window |
| Post-review trigger | Codifier fires after every review | Every session compounds into improved checklists |
| Repair capability | Same domain agents re-invoked in repair mode | No duplicate agents needed |
| Todo destination | `todos/YYYY-MM-DD-review.md` | Existing folder, consistent with project convention |

---

## Agent Team — 13 New Agents

### Delete (replaced entirely)
- `.claude/agents/comprehensive-code-reviewer.md`
- `.claude/agents/code-review-specialist.md`
- `.claude/agents/django-performance-reviewer.md`

### Orchestration & Learning

| File | Purpose | Model | Tools |
|---|---|---|---|
| `code-review-orchestrator.md` | Reads diff → selects + dispatches domain agents | haiku | `Bash` |
| `pattern-codifier.md` | Post-review: returns structured update instructions | sonnet | `Read, Glob, Grep` |

### Domain Review Agents

| File | Scope | Model | Tools |
|---|---|---|---|
| `django-drf-reviewer.md` | Django 5.2, DRF viewsets, permissions, migrations, models | sonnet | `Read, Glob, Grep, Bash` |
| `wagtail-reviewer.md` | Wagtail 7.1.2 (dev) / 7.4 (prod), StreamField, page models, signals, API v2 | sonnet | `Read, Glob, Grep, Bash` |
| `react-typescript-reviewer.md` | React 19, TypeScript, Tailwind CSS 4, Vitest, Playwright | sonnet | `Read, Glob, Grep, Bash` |
| `flutter-dart-reviewer.md` | Flutter 3.x, Riverpod, go_router, Dart null safety | sonnet | `Read, Glob, Grep, Bash` |
| `flutter-firebase-reviewer.md` | Firebase Auth, JWT exchange, Firestore listeners, Storage, Function invocation, StreamSubscription cleanup, secure storage | sonnet | `Read, Glob, Grep, Bash` |
| `security-reviewer.md` | File upload validation, CSRF, secrets, XSS, SQL injection, auth bypass, firestore.rules, storage.rules, Firebase IAM | sonnet | `Read, Glob, Grep, Bash` |
| `performance-reviewer.md` | N+1 queries, Redis caching, query count assertions, React render perf, Firestore read costs, Cloud Function cold starts | sonnet | `Read, Glob, Grep, Bash` |
| `api-design-reviewer.md` | DRF serializers, versioning, OpenAPI/Swagger schema correctness, error response shapes | sonnet | `Read, Glob, Grep, Bash` |
| `test-quality-reviewer.md` | No-DB-mocks, strict query count assertions, coverage requirements, test naming conventions | sonnet | `Read, Glob, Grep, Bash` |
| `firebase-cloudfunction-reviewer.md` | Functions architecture, triggers, idempotency, retry logic, cold start mitigation | sonnet | `Read, Glob, Grep, Bash` |
| `celery-async-reviewer.md` | Task definitions, retry logic, beat schedules, idempotency, error handling | sonnet | `Read, Glob, Grep, Bash` |

All domain agents are **read-only**. No `Edit` or `Write` tools assigned to any agent.

---

## Agent File Structure

### `code-review-orchestrator.md` (~80 lines, never grows)

Contains only:
1. Instruction to run `git diff --name-only HEAD`
2. Routing table mapping file path patterns to agent IDs
3. Deduplication and severity presentation format
4. Repair dispatch instructions (Phase 2)
5. Todo creation instruction (Phase 3)

Holds zero pattern knowledge.

**Routing table (examples):**
```
apps/**/*.py                          → django-drf-reviewer
apps/blog/** or Page subclass         → wagtail-reviewer
web/src/**/*.tsx / *.ts               → react-typescript-reviewer
plant_community_mobile/**/*.dart      → flutter-dart-reviewer
firebase/** or *.rules                → flutter-firebase-reviewer, security-reviewer
functions/**                          → firebase-cloudfunction-reviewer
**/tasks.py or **/celery*.py          → celery-async-reviewer
Any auth/upload/secret-touching file  → always adds security-reviewer
**/tests/**                           → always adds test-quality-reviewer
```

### Domain reviewer `.md` files (~130–160 lines each)

Structure:
```markdown
## Scope
Only review files passed in. Do not read the full repo.

## Review Mode — Checklist
- [ ] [Specific pattern to enforce, with issue # if known]
- [ ] [Grows over time via pattern-codifier]

## Pattern References
[Links to relevant docs/patterns/ files — not loaded automatically]

## Repair Mode
When invoked with a specific finding:
1. Read the affected file
2. Identify the minimal code change
3. Return: { "file": "path", "old": "exact string", "new": "replacement" }
Do not apply changes yourself.
```

### `pattern-codifier.md` (fixed procedure, never grows)

Returns structured JSON:
```json
{
  "agent_updates": [
    { "file": ".claude/agents/django-drf-reviewer.md",
      "append_to_checklist": "- [ ] ..." }
  ],
  "learnings": [
    { "domain": "django", "mistake": "...", "fix": "...", "rule": "...", "agent": "..." }
  ],
  "pattern_docs": [
    { "file": "backend/docs/patterns/domain/wagtail.md", "append": "..." }
  ]
}
```

Main Claude receives this and executes all writes.

---

## Two-Phase Review + Repair Flow

```
Phase 1 — Review
  Orchestrator runs git diff → maps paths → dispatches domain agents in parallel
  Each agent reviews changed files in its domain → returns findings
  Orchestrator deduplicates findings across agents
  Presents to user:

    CRITICAL (n)  HIGH (n)  MEDIUM (n)  LOW/INFO (n)
    [finding list with file:line, description, owning agent]

    "Repair CRITICAL + HIGH + MEDIUM? (yes / no / select)"

Phase 2 — Repair (if user confirms)
  Orchestrator re-dispatches owning domain agent per finding in repair mode
  Agent reads file → returns { file, old_string, new_string }
  Main Claude executes all Edit operations

Phase 3 — Todos
  Main Claude writes LOW/INFO findings to todos/YYYY-MM-DD-review.md
  Format: checkbox list grouped by file

Phase 4 — Compound
  pattern-codifier invoked
  Returns structured update instructions
  Main Claude writes updates to agent checklists + docs/LEARNINGS.md
```

### Severity Definitions

| Level | Meaning | Action |
|---|---|---|
| CRITICAL | Security vulnerability, data loss risk | Offer immediate repair |
| HIGH | Breaking bug, significant performance issue | Offer immediate repair |
| MEDIUM | Pattern violation, maintainability problem | Offer immediate repair |
| LOW | Style, minor improvements, documentation | Written to todos/ |
| INFO | Observation, suggestion, version note | Written to todos/ |

---

## Pattern File Locations

### Existing (keep, extend)
```
backend/docs/patterns/
  README.md                    ← codifier updates index here
  architecture/                caching, viewsets, services, rate-limiting
  security/                    authentication, csrf, file-upload, input-validation, secrets
  performance/                 query-optimization
  domain/
    blog.md
    forum.md
    plant-identification.md
    diagnosis.md
    wagtail.md                 ← new: split from blog.md
    celery.md                  ← new
```

### New directories
```
web/docs/patterns/
  react-typescript.md
  tailwind.md
  testing.md

plant_community_mobile/docs/patterns/
  flutter-patterns.md
  firebase-auth.md
  riverpod.md

firebase/docs/patterns/
  cloud-functions.md
  firestore-rules.md
  iam.md
```

### Codifier routing table

| Finding source | Write to |
|---|---|
| `django-drf-reviewer` | `backend/docs/patterns/` (appropriate subdir) |
| `wagtail-reviewer` | `backend/docs/patterns/domain/wagtail.md` |
| `celery-async-reviewer` | `backend/docs/patterns/domain/celery.md` |
| `react-typescript-reviewer` | `web/docs/patterns/` |
| `flutter-dart-reviewer` | `plant_community_mobile/docs/patterns/flutter-patterns.md` |
| `flutter-firebase-reviewer` | `plant_community_mobile/docs/patterns/firebase-auth.md` |
| `firebase-cloudfunction-reviewer` | `firebase/docs/patterns/cloud-functions.md` |
| `security-reviewer` | `backend/docs/patterns/security/` |
| `performance-reviewer` | `backend/docs/patterns/performance/` |
| `api-design-reviewer` | `backend/docs/patterns/architecture/` |
| `test-quality-reviewer` | platform-specific `testing.md` |
| Any agent | `docs/LEARNINGS.md` (always) |

---

## LEARNINGS.md Format

Location: `docs/LEARNINGS.md`  
Written by: main Claude (based on codifier output)  
Access: append-only — never edited, only appended

```markdown
# Learnings

## Index
- [Django/DRF](#djangodrf)
- [Wagtail](#wagtail)
- [React/TypeScript](#reacttypescript)
- [Flutter/Firebase](#flutterfirebase)
- [Security](#security)
- [Performance](#performance)

---

## Django/DRF

### [2026-05-06] Wagtail version mismatch between requirements.txt and requirements-dev.txt
**Mistake**: requirements.txt referenced wagtail==7.4 while requirements-dev.txt had 7.1.2, causing inconsistent behaviour between dev and production environments.
**Fix**: Audited both files; agents now reference both versions with dev/prod context.
**Rule**: Any version reference in an agent or pattern doc must specify dev vs prod if they differ.
**Agent**: wagtail-reviewer
```

---

## Implementation Scope

### Files to create
- `.claude/agents/code-review-orchestrator.md`
- `.claude/agents/pattern-codifier.md`
- `.claude/agents/django-drf-reviewer.md`
- `.claude/agents/wagtail-reviewer.md`
- `.claude/agents/react-typescript-reviewer.md`
- `.claude/agents/flutter-dart-reviewer.md`
- `.claude/agents/flutter-firebase-reviewer.md`
- `.claude/agents/security-reviewer.md`
- `.claude/agents/performance-reviewer.md`
- `.claude/agents/api-design-reviewer.md`
- `.claude/agents/test-quality-reviewer.md`
- `.claude/agents/firebase-cloudfunction-reviewer.md`
- `.claude/agents/celery-async-reviewer.md`
- `docs/LEARNINGS.md`
- `backend/docs/patterns/domain/wagtail.md`
- `backend/docs/patterns/domain/celery.md`
- `web/docs/patterns/react-typescript.md`
- `web/docs/patterns/tailwind.md`
- `web/docs/patterns/testing.md`
- `plant_community_mobile/docs/patterns/flutter-patterns.md`
- `plant_community_mobile/docs/patterns/firebase-auth.md`
- `plant_community_mobile/docs/patterns/riverpod.md`
- `firebase/docs/patterns/cloud-functions.md`
- `firebase/docs/patterns/firestore-rules.md`
- `firebase/docs/patterns/iam.md`

### Files to delete
- `.claude/agents/comprehensive-code-reviewer.md`
- `.claude/agents/code-review-specialist.md`
- `.claude/agents/django-performance-reviewer.md`

### Files to update
- `CLAUDE.md` — update agent references section
- `backend/docs/patterns/README.md` — add new domain files to index
