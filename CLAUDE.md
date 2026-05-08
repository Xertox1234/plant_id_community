# Plant ID Community

Multi-platform plant identification app. Backend (Django + Wagtail) at port 8000, React web at port 5174, Flutter mobile as primary platform.

## Quick Reference

- **Port 8000** — Django backend + Wagtail CMS (admin at `/cms/`, NOT `/admin/`)
- **Port 5174** — React web frontend (Vite)
- **Port 6379** — Redis (required — `brew services start redis`)
- **Active backend**: `/backend/` — `/existing_implementation/` is archived, do not edit it

## Project Structure

| Directory | Role |
|-----------|------|
| `backend/apps/plant_identification/` | Dual-provider plant ID API (Plant.id v3 + PlantNet) |
| `backend/apps/blog/` | Wagtail CMS blog with AI content generation |
| `backend/apps/forum/` | Community forum — trust levels, spam detection, moderation |
| `backend/apps/garden_calendar/` | Garden beds, plants, care tasks, harvests |
| `backend/apps/users/` | JWT auth + Firebase token exchange |
| `web/` | React 19 + TypeScript frontend (blog, forum, auth) |
| `plant_community_mobile/` | Flutter app (primary — plant ID, offline, garden tracking) |
| `docs/archive/` | Historical docs — read-only reference |
| `existing_implementation/` | Archived reference — do not edit |

See platform-specific `CLAUDE.md` files in `backend/`, `web/`, and `plant_community_mobile/` for commands and conventions.

## Critical Gotchas

Six non-obvious bugs that have already caused real failures:

**1. ViewSet `get_permissions()` must call `super()` for `@action` endpoints**
If you override `get_permissions()` without calling `super().get_permissions()` for custom actions, action-level `permission_classes` are silently ignored — a security hole. See `backend/docs/patterns/architecture/viewsets.md`.

**2. React Router: import from `react-router-dom`, not `react-router`**
`import { useNavigate } from 'react-router'` causes a silent runtime failure (`Cannot read properties of undefined`). Always use `react-router-dom`. Hit 15+ files during TypeScript migration.

**3. Raw SQL in migrations: never use f-strings for table/column names**
Use `psycopg2.sql.Identifier()` + a whitelist. F-strings concatenate directly into SQL with no escaping. See `backend/docs/patterns/security/input-validation.md`.

**4. `django-ratelimit` raises `PermissionDenied` (returns 403, not 429)**
`Ratelimited` inherits from `PermissionDenied`, so DRF returns 403 by default. A custom exception handler that checks `isinstance(exc, Ratelimited)` before DRF processing is required for RFC-compliant 429. See `backend/docs/patterns/architecture/rate-limiting.md`.

**5. Debounce timers in React: `useRef`, not `useState`**
`useState` for a timer ID triggers a re-render on every update, recreates the callback, and leaks the timer on unmount. Use `useRef` — it holds the ID without causing re-renders.

**6. Test DB stale after migration changes**
If the test DB predates a migration change, Django raises `FieldError`. Fix: pass `--noinput` to force a fresh rebuild: `python manage.py test apps.foo --noinput`.

## Pattern Library

The pattern library is the primary reference for implementation decisions. Read the relevant pattern doc before writing new code in that area.

### Backend (`backend/docs/patterns/`)

| File | Covers |
|------|--------|
| [`README.md`](backend/docs/patterns/README.md) | Index — start here |
| `security/authentication.md` | JWT tokens, account lockout, OAuth |
| `security/csrf-protection.md` | Django + React CSRF integration |
| `security/file-upload.md` | 4-layer validation (extension, MIME, size, PIL) |
| `security/input-validation.md` | SQL wildcard escaping, XSS prevention |
| `security/secret-management.md` | API keys, SECRET_KEY validation, rotation |
| `architecture/caching.md` | Redis strategies, cache invalidation |
| `architecture/rate-limiting.md` | django-ratelimit, 429 vs 403, Retry-After |
| `architecture/services.md` | Service layer, circuit breakers, distributed locks |
| `architecture/viewsets.md` | DRF ViewSet patterns, get_permissions() |
| `performance/query-optimization.md` | N+1 elimination, GIN indexes, strict test assertions |
| `domain/plant-identification.md` | Plant.id v3 + PlantNet integration |
| `domain/diagnosis.md` | UUID lookups in DRF |
| `domain/forum.md` | Trust levels, spam detection, moderation |
| `domain/blog.md` | Wagtail AI integration, caching |
| `domain/wagtail.md` | Wagtail page models, StreamField, signals |
| `domain/celery.md` | Celery tasks, retry config |

### Web (`web/docs/patterns/`)

| File | Covers |
|------|--------|
| `react-typescript.md` | Component patterns, type safety |
| `tailwind.md` | Tailwind CSS 4 conventions |
| `testing.md` | Vitest + Playwright patterns |

### Mobile (`plant_community_mobile/docs/patterns/`)

| File | Covers |
|------|--------|
| `flutter-patterns.md` | Material 3, dark mode, null safety |
| `firebase-auth.md` | Firebase → Django JWT exchange, GDPR email redaction |
| `riverpod.md` | Riverpod 3.x state management |

### Firebase (`firebase/docs/patterns/`)

| File | Covers |
|------|--------|
| `cloud-functions.md` | Functions architecture, idempotency, cold starts |
| `firestore-rules.md` | Security rules |
| `iam.md` | IAM configuration |

### Incidents (`docs/LEARNINGS.md`)

Append-only log of bugs, incidents, and hard-won patterns. Read before starting a new feature area.

## Review Doc Tracking

When a finding from a review doc is converted to an individual todo file, link them so completion is visible.

### Convention

**1. Add `source_review` fields to the todo frontmatter:**

```yaml
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "42"
```

**2. Add/update a `## Finding Status` section in the review doc** (create if absent, append if present):

```markdown
## Finding Status
- [ ] #42 short-description → todo 064
- [ ] #43 another-description → todo 065
```

One line per converted finding, in finding-number order.

**3. The `completing-todos` skill handles the rest automatically** on archive:

- Checks off `- [ ] #42` → `- [x] #42 (completed YYYY-MM-DD)`
- When **all** `## Finding Status` lines are `- [x]`, renames the review doc to `…-COMPLETED.md` via `git mv`

### Why

Previously, findings were converted to todos and completed without any trace in the source review doc, making it impossible to tell at a glance which findings were still open. This broke down in the May 6 review — 7 items looked open but were already done as todos 057–063.

## Code Review Agents

Trigger a review: ask Claude to invoke `.claude/agents/code-review-orchestrator.md`. It reads `git diff`, dispatches only the agents relevant to changed files in parallel, deduplicates findings, and returns results by severity.

| Agent | Covers |
|-------|--------|
| `django-drf-reviewer.md` | Django, DRF viewsets, permissions, migrations |
| `wagtail-reviewer.md` | Wagtail page models, StreamField, API v2 |
| `react-typescript-reviewer.md` | React 19, TypeScript, Tailwind, Vitest, Playwright |
| `flutter-dart-reviewer.md` | Flutter, Riverpod, go_router, Material 3 |
| `flutter-firebase-reviewer.md` | Firebase Auth, JWT exchange, secure storage, GDPR |
| `security-reviewer.md` | File upload, CSRF, secrets, XSS, SQL injection |
| `performance-reviewer.md` | N+1 queries, Redis caching, query count assertions |
| `api-design-reviewer.md` | Serializers, versioning, OpenAPI, error shapes |
| `test-quality-reviewer.md` | No DB mocks, strict assertions, coverage |
| `celery-async-reviewer.md` | Celery tasks, retry config, beat schedules |
| `firebase-cloudfunction-reviewer.md` | Cloud Functions architecture, idempotency, cold starts |
| `pattern-codifier.md` | Extracts new patterns after each review |

Non-review agents (invoke directly for implementation tasks):

- `wagtail-cms-orchestrator.md` — CMS content, API integration, data flow tracing
- `frontend-developer.md` — React UI/UX implementation

## Environment Variables

| Variable | File | Controls |
|----------|------|----------|
| `SECRET_KEY` | `backend/.env` | Django secret (min 50 chars, no `django-insecure`) |
| `DEBUG` | `backend/.env` | `True` = anonymous plant ID allowed; `False` = auth required |
| `DATABASE_URL` | `backend/.env` | PostgreSQL connection string |
| `REDIS_URL` | `backend/.env` | Redis (required for caching + distributed locks) |
| `PLANT_ID_API_KEY` | `backend/.env` | Plant.id API v3 |
| `PLANTNET_API_KEY` | `backend/.env` | PlantNet fallback API |
| `CORS_ALLOWED_ORIGINS` | `backend/.env` | Set to `http://localhost:5174` in dev |
| `GOOGLE_APPLICATION_CREDENTIALS` | `backend/.env` | Path to Firebase service account JSON |
| `VITE_API_URL` | `web/.env` | Backend URL for React app |

## Cheap-Worker Delegation (Kimi K2.6)

Three CLI tools delegate bulk I/O to a cheap worker model (Kimi K2.6 via OpenRouter).
Claude handles reasoning and architecture; the worker handles token-heavy reading/writing.

### ask-kimi — bulk file reading

Use when reading 3+ files for context, or any single file >400 lines when the goal is
understanding (not editing):

```bash
ask-kimi --paths <file1> <file2>... --question "<specific question>"
```

Returns structured bullets. Read the summary instead of the raw files.
Only use Read directly when you need exact line numbers for editing.

### kimi-write — boilerplate generation

Use for pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers —
anything that follows an existing pattern:

```bash
kimi-write --spec "<what to write>" --context <existing-similar-file> --target <output-path>
```

Then review the output and edit only what needs fixing.

### extract-chat — session transcript extraction

Converts Claude Code JSONL session logs to readable text (no API call, stdlib only):

```bash
extract-chat <session.jsonl> -o /tmp/chat.txt
```

Use before post-session doc updates: extract → ask-kimi to suggest changes → apply with Edit.

### Delegation rules

**AUTO-delegate (no prompt needed):**

- Reading 3+ files for exploration or context
- Single file >400 lines when goal is understanding (not editing)
- Boilerplate: pytest tests, DRF viewsets/serializers, Flutter widgets, Riverpod providers
- Post-session documentation updates

**NEVER delegate:**

- Architecture decisions, refactoring plans, feature design
- Debugging (requires reasoning about error state)
- Security-sensitive code: auth, permissions, input validation, migrations
- Tasks requiring exact line numbers for editing — use Read directly
- Tasks under ~2000 tokens (overhead not worth it)

**Ask first (ambiguous):**

- "Summarize what changed in this PR"
- Anything touching auth or permissions even if it seems mechanical
