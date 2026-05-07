# Copilot Instructions — Plant ID Community

Multi-platform plant identification app. Three platforms in this monorepo:
- **Backend** (`backend/`) — Django 5 + DRF + Wagtail CMS, Python 3.13, PostgreSQL, Redis. Wagtail admin lives at `/cms/` (not `/admin/`).
- **Web** (`web/`) — React 19 + TypeScript + Vite + Tailwind CSS 4 + Vitest + Playwright.
- **Mobile** (`plant_community_mobile/`) — Flutter, Riverpod 3.x, go_router, Material 3, drift (sqlite). Primary platform.

`existing_implementation/` is archived — never edit or reference it.

## Critical gotchas — flag these in review

These have all caused real production failures. If a PR reintroduces any of them, **block the PR**.

1. **DRF `get_permissions()` override without `super()` for `@action` endpoints.** Action-level `permission_classes` are silently ignored — a security hole. The override must call `super().get_permissions()` for custom actions.
2. **`import { ... } from 'react-router'` instead of `react-router-dom`.** Causes silent runtime failure (`Cannot read properties of undefined`). Always import from `react-router-dom`.
3. **Raw SQL in migrations using f-strings for table/column names.** Use `psycopg2.sql.Identifier()` + a whitelist. F-strings concatenate directly into SQL with no escaping.
4. **`django-ratelimit` returning 403 instead of 429.** `Ratelimited` inherits from `PermissionDenied`; a custom exception handler checking `isinstance(exc, Ratelimited)` *before* DRF processing is required for RFC-compliant 429.
5. **Debounce timers in React using `useState` instead of `useRef`.** `useState` re-renders on every update, recreates the callback, and leaks the timer on unmount. Always `useRef`.
6. **Tests that mock the database.** Forbidden — past mocked tests masked broken migrations in production. Tests must hit a real DB. Strict count assertions on N+1 queries are required.

## Conventions

### Backend (Django/DRF/Wagtail)
- ViewSets over function-based views. Pattern docs in `backend/docs/patterns/`.
- N+1 queries are blocking — use `select_related` / `prefetch_related` and assert query count in tests.
- Cache invalidation lives in Wagtail signals (e.g., `apps/blog/signals.py`); use `isinstance(instance, BlogPostPage)`, never `hasattr`.
- Rate limiting via `django-ratelimit`; 429s require the custom exception handler (see gotcha #4).
- File uploads need 4-layer validation: extension, MIME, size, PIL re-decode (`backend/docs/patterns/security/file-upload.md`).
- Service layer (`apps/<app>/services.py`) wraps external APIs with circuit breakers and distributed locks. View code should not call external APIs directly.
- Tests: `python manage.py test apps.foo --noinput` (the `--noinput` is required after migration changes).

### Web (React 19 + TS)
- Always import router APIs from `react-router-dom`.
- Tailwind CSS 4 (`@tailwindcss/vite`), not v3.
- Strict TypeScript — no implicit `any`, no `// @ts-ignore` without justification.
- Component tests with Vitest, E2E with Playwright.
- API URL via `VITE_API_URL`; never hardcode `localhost:8000`.

### Mobile (Flutter)
- Riverpod 3.x for state (no Provider, no setState beyond ephemeral).
- Material 3, dark mode required.
- Firebase Auth → Django JWT exchange flow (`plant_community_mobile/docs/patterns/firebase-auth.md`); never store Firebase tokens for API auth — exchange them.
- GDPR: redact email in logs.
- Null safety strict; no `!` without a comment justifying invariant.

## What to flag in reviews

- Any new code in `existing_implementation/`.
- Direct DB mocks in tests.
- Missing `select_related` / `prefetch_related` on querysets that are iterated.
- New Wagtail StreamField blocks without a corresponding `StreamFieldRenderer.jsx` case.
- Hardcoded secrets, API keys, or `localhost` URLs.
- New endpoints without rate limiting, or with the wrong exception handler.
- Use of `useState` for refs/timers/DOM nodes in React.
- Use of `flutter_bloc`, `Provider`, or non-Riverpod state management in mobile.
- Missing migrations after model changes.
- New workflows in `.github/workflows/` without an explicit `permissions:` block.

## What NOT to flag

- Style nits already enforced by ruff / eslint / dart analyze — the linters handle those.
- Comments — the project policy is "no comments unless the WHY is non-obvious"; don't push for docstrings on every function.
- "Add error handling for X" when X is an internal call between trusted layers — only require validation at system boundaries.
- "Consider splitting into multiple PRs" — small bundled PRs are preferred here.

## Pattern library

Authoritative implementation guides — read these before suggesting alternatives:
- `backend/docs/patterns/` (security, architecture, performance, domain)
- `web/docs/patterns/` (react-typescript, tailwind, testing)
- `plant_community_mobile/docs/patterns/` (flutter, firebase-auth, riverpod)
- `firebase/docs/patterns/` (cloud-functions, firestore-rules, iam)

Incident log (read for context on existing decisions): `docs/LEARNINGS.md`.

## Environment variables

Backend (`backend/.env`): `SECRET_KEY` (≥50 chars, no `django-insecure` prefix), `DEBUG`, `DATABASE_URL`, `REDIS_URL`, `PLANT_ID_API_KEY`, `PLANTNET_API_KEY`, `CORS_ALLOWED_ORIGINS`, `GOOGLE_APPLICATION_CREDENTIALS`.

Web (`web/.env`): `VITE_API_URL`.
