# CLAUDE.md Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 1,308-line stale root `CLAUDE.md` with four lean, accurate files — one project-wide root and one per platform — so each Claude session only loads what's relevant.

**Architecture:** Write four files fresh (root + backend + web + mobile), then delete the old root file. No content is migrated verbatim — everything is rewritten from current state. Each file covers only what Claude cannot discover by reading code.

**Tech Stack:** Markdown only. No code changes. Verification via `wc -l` and `ls` to confirm line counts and referenced paths exist.

---

## File Map

| Action | Path | Lines |
|--------|------|-------|
| Replace | `/CLAUDE.md` | ≤150 |
| Create | `/backend/CLAUDE.md` | ≤55 |
| Create | `/web/CLAUDE.md` | ≤55 |
| Create | `/plant_community_mobile/CLAUDE.md` | ≤55 |

---

### Task 1: Write the root `/CLAUDE.md`

**Files:**
- Replace: `/CLAUDE.md`

- [ ] **Step 1: Write the file**

Write `/CLAUDE.md` with exactly this content:

```markdown
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
```

- [ ] **Step 2: Verify line count**

```bash
wc -l CLAUDE.md
```

Expected: ≤150 lines. If over, find the longest section and trim prose — do not remove sections.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: replace root CLAUDE.md with lean 4-file split"
```

---

### Task 2: Write `/backend/CLAUDE.md`

**Files:**
- Create: `/backend/CLAUDE.md`

- [ ] **Step 1: Write the file**

Write `/backend/CLAUDE.md` with exactly this content:

```markdown
# Backend — Django / DRF / Wagtail

## Commands

```bash
# Setup
cd backend
source venv/bin/activate

# Development
python manage.py runserver           # http://localhost:8000
python simple_server.py              # runserver + Redis health check

# Database
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser

# Testing
# --keepdb skips teardown (faster); --noinput forces fresh rebuild after migration changes
python manage.py test apps.plant_identification --keepdb
python manage.py test apps.blog --keepdb
python manage.py test apps.forum --keepdb
python manage.py test apps.garden_calendar --keepdb
python manage.py test apps.users --keepdb

# Cache warming (run after deploy to eliminate cold start penalty)
python manage.py warm_moderation_cache
python manage.py warm_moderation_cache --force

# Redis
brew services start redis
redis-cli ping   # should return PONG
```

## Conventions

- **No magic numbers** — all config (timeouts, limits, cache keys, thresholds) in the app's `constants.py`. Every app has one at `apps/<app>/constants.py`. Import from there; never hardcode.
- **Bracketed log prefixes** — use `[CACHE]`, `[PERF]`, `[ERROR]`, `[CIRCUIT]`, `[SECURITY]` so logs are greppable by category.
- **Type hints on all service methods** — `def identify(self, file) -> Optional[Dict[str, Any]]:`. No bare `def`.
- **Escape search wildcards** — before any `icontains` filter, escape `%` and `_`: `query.replace('%', r'\%').replace('_', r'\_')`. See `docs/patterns/security/input-validation.md`.
- **Wagtail admin** — at `/cms/`, not `/admin/`.

## Gotcha: stale test DB after migration changes

If a test raises `FieldError` after you changed a migration, the test DB predates the change. Fix:

```bash
python manage.py test apps.<app> --noinput   # drops and rebuilds the test DB
```
```

- [ ] **Step 2: Verify line count**

```bash
wc -l backend/CLAUDE.md
```

Expected: ≤55 lines.

- [ ] **Step 3: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs: add backend/CLAUDE.md with commands and conventions"
```

---

### Task 3: Write `/web/CLAUDE.md`

**Files:**
- Create: `/web/CLAUDE.md`

- [ ] **Step 1: Write the file**

Write `/web/CLAUDE.md` with exactly this content:

```markdown
# Web — React 19 / TypeScript / Tailwind CSS 4

## Commands

```bash
cd web

npm run dev           # http://localhost:5174
npm run build         # production build (runs type-check first — must pass)
npm run type-check    # TypeScript compilation check (zero errors required)
npm run lint          # ESLint
npm run test          # Vitest (unit + component)
npm run test:watch    # watch mode for development
npm run test:e2e      # Playwright E2E (auto-starts dev servers)
npm run test:e2e:ui   # Playwright UI — best for debugging E2E failures
```

## Conventions

- **All source files** must be `.ts` or `.tsx`. No `.js` files in `src/`.
- **React Router** — always import from `react-router-dom`, never `react-router`. The latter causes silent runtime failure.
- **TypeScript strictness** — `strict: false` for now. Avoid `any`; use `unknown` for truly unknown types. New types go in `src/types/`.
- **User-generated HTML** — always sanitize with `DOMPurify` before rendering. Never set `dangerouslySetInnerHTML` with raw user input.
- **CSRF** — include `X-CSRFToken` header and `credentials: 'include'` on all mutating requests to the backend.

## Gotcha: debounce timers

Use `useRef` — not `useState` — for debounce/interval timer IDs. `useState` triggers a re-render on every update, causes the callback to be recreated, and leaks the timer on unmount:

```typescript
const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(() => { /* search */ }, 500);
}, []);  // stable — no dependencies

useEffect(() => () => {
  if (timerRef.current) clearTimeout(timerRef.current);
}, []);
```
```

- [ ] **Step 2: Verify line count**

```bash
wc -l web/CLAUDE.md
```

Expected: ≤55 lines.

- [ ] **Step 3: Commit**

```bash
git add web/CLAUDE.md
git commit -m "docs: add web/CLAUDE.md with commands and conventions"
```

---

### Task 4: Write `/plant_community_mobile/CLAUDE.md`

**Files:**
- Create: `/plant_community_mobile/CLAUDE.md`

- [ ] **Step 1: Write the file**

Write `/plant_community_mobile/CLAUDE.md` with exactly this content:

```markdown
# Mobile — Flutter / Firebase / Riverpod

## Commands

```bash
cd plant_community_mobile

flutter run -d ios       # iOS simulator
flutter run -d android   # Android emulator
flutter run -d macos     # macOS desktop

flutter test             # unit + widget tests
flutter test --coverage  # with coverage report

# Regenerate Riverpod providers + go_router routes after any annotation change
flutter pub run build_runner build --delete-conflicting-outputs

# Security scan (run before commits)
cd ..
source backend/venv/bin/activate
python scripts/check_flutter_security.py
```

## Conventions

- **Riverpod 3.x** — use `Notifier` class with `@riverpod` annotation. Do not use `StateNotifier`.
- **go_router** — set `debugLogDiagnostics: kDebugMode`, not `true` (would log in production).
- **Material 3** — use `CardThemeData` (not `CardTheme`), `.withValues(alpha:)` (not `.withOpacity()`).
- **Token storage** — always `flutter_secure_storage`. Never `SharedPreferences` (not encrypted).
- **Dark mode** — check `Theme.of(context).brightness == Brightness.dark` for conditional styling.

## Gotcha: StreamSubscription memory leaks

Any `StreamSubscription` opened in a Riverpod provider **must** be cancelled in `ref.onDispose()`:

```dart
StreamSubscription<User?>? _authSub;

@override
AuthState build() {
  _authSub = _firebaseAuth.authStateChanges().listen((user) async {
    if (user != null) await _exchangeToken(user);
  });
  ref.onDispose(() => _authSub?.cancel());
  return AuthState(firebaseUser: _firebaseAuth.currentUser);
}
```

See `docs/patterns/firebase-auth.md` for the full Firebase → Django JWT exchange pattern.
```

- [ ] **Step 2: Verify line count**

```bash
wc -l plant_community_mobile/CLAUDE.md
```

Expected: ≤55 lines.

- [ ] **Step 3: Commit**

```bash
git add plant_community_mobile/CLAUDE.md
git commit -m "docs: add plant_community_mobile/CLAUDE.md with commands and conventions"
```

---

### Task 5: Verify all referenced paths exist and finalize

**Files:**
- No new files

- [ ] **Step 1: Verify all pattern doc paths referenced in root CLAUDE.md**

```bash
# Backend patterns
ls backend/docs/patterns/README.md
ls backend/docs/patterns/security/authentication.md
ls backend/docs/patterns/security/csrf-protection.md
ls backend/docs/patterns/security/file-upload.md
ls backend/docs/patterns/security/input-validation.md
ls backend/docs/patterns/security/secret-management.md
ls backend/docs/patterns/architecture/caching.md
ls backend/docs/patterns/architecture/rate-limiting.md
ls backend/docs/patterns/architecture/services.md
ls backend/docs/patterns/architecture/viewsets.md
ls backend/docs/patterns/performance/query-optimization.md
ls backend/docs/patterns/domain/plant-identification.md
ls backend/docs/patterns/domain/diagnosis.md
ls backend/docs/patterns/domain/forum.md
ls backend/docs/patterns/domain/blog.md
ls backend/docs/patterns/domain/wagtail.md
ls backend/docs/patterns/domain/celery.md

# Web patterns
ls web/docs/patterns/react-typescript.md
ls web/docs/patterns/tailwind.md
ls web/docs/patterns/testing.md

# Mobile patterns
ls plant_community_mobile/docs/patterns/flutter-patterns.md
ls plant_community_mobile/docs/patterns/firebase-auth.md
ls plant_community_mobile/docs/patterns/riverpod.md

# Firebase patterns
ls firebase/docs/patterns/cloud-functions.md
ls firebase/docs/patterns/firestore-rules.md
ls firebase/docs/patterns/iam.md

# Agents
ls .claude/agents/code-review-orchestrator.md
ls .claude/agents/django-drf-reviewer.md
ls .claude/agents/wagtail-reviewer.md
ls .claude/agents/react-typescript-reviewer.md
ls .claude/agents/flutter-dart-reviewer.md
ls .claude/agents/flutter-firebase-reviewer.md
ls .claude/agents/security-reviewer.md
ls .claude/agents/performance-reviewer.md
ls .claude/agents/api-design-reviewer.md
ls .claude/agents/test-quality-reviewer.md
ls .claude/agents/celery-async-reviewer.md
ls .claude/agents/pattern-codifier.md
```

Expected: all paths exist. If any `ls` fails, remove that row from the root CLAUDE.md table before proceeding.

- [ ] **Step 2: Check all four file line counts together**

```bash
wc -l CLAUDE.md backend/CLAUDE.md web/CLAUDE.md plant_community_mobile/CLAUDE.md
```

Expected:
- `CLAUDE.md` ≤ 150
- `backend/CLAUDE.md` ≤ 55
- `web/CLAUDE.md` ≤ 55
- `plant_community_mobile/CLAUDE.md` ≤ 55

- [ ] **Step 3: Spot-check for stale content**

Search for common stale markers:

```bash
grep -n "PR #\|Issue #\|✅\|🚧\|📋\|passing\|Grade A\|Nov 2025\|Nov 6\|Nov 8\|Nov 13\|Nov 15" CLAUDE.md backend/CLAUDE.md web/CLAUDE.md plant_community_mobile/CLAUDE.md
```

Expected: no matches. If any are found, remove the line containing them.

- [ ] **Step 4: Final commit**

```bash
git add CLAUDE.md backend/CLAUDE.md web/CLAUDE.md plant_community_mobile/CLAUDE.md
git commit -m "docs: finalize CLAUDE.md split — 4 lean platform-specific files"
```
