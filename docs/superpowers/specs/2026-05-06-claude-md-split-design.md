# CLAUDE.md Split Design

**Date**: 2026-05-06
**Status**: Approved

## Problem

The root `CLAUDE.md` is 1,308 lines / 57KB. It is ~8 months old, based on outdated standards, and gets injected into every Claude session regardless of which platform is being worked on. This wastes tokens, goes stale quickly, and is hard to navigate.

## Goal

Replace the single bloated file with four lean, accurate files — one root file and one per platform — so each session only loads what's relevant.

## Approach: Lean quick-reference with critical gotchas

Content falls into three categories:

1. **Keep in CLAUDE.md**: Things Claude cannot discover by reading code (ports, non-obvious commands, cross-cutting gotchas, pattern library navigation, agents)
2. **Move to platform sub-files**: Platform-specific commands and conventions
3. **Delete entirely**: Status tables, implementation history, detailed code examples, completion notes — all of this lives in pattern docs or git history

## File Structure

### Root `/CLAUDE.md` (~130 lines)

Sections:
1. **Quick Reference** — ports (8000 Django/Wagtail, 5174 React, 6379 Redis), Wagtail admin at `/cms/` not `/admin/`, active backend is `/backend/` not `/existing_implementation/`
2. **Project Structure** — one-liner per app (`plant_identification`, `blog`, `forum`, `garden_calendar`, `users`) and per platform (web, mobile), note that `/existing_implementation/` and `/docs/archive/` are archived
3. **Critical Gotchas** — six non-obvious bugs that have already cost time (see below)
4. **Pattern Library** — navigation table linking to all pattern docs across all platforms; `backend/docs/patterns/README.md` as the index; includes web and mobile patterns
5. **Code Review Agents** — explains the orchestrator + 11 domain specialist system, when to invoke `.claude/agents/code-review-orchestrator.md`
6. **Environment Variables** — key variable names and what they control, no values

#### Critical Gotchas (root)

These are cross-cutting, non-obvious, and have caused real bugs:

1. **ViewSet `get_permissions()`**: Must call `super().get_permissions()` for `@action`-decorated endpoints, otherwise action-level `permission_classes` are silently ignored — a security hole.
2. **React Router imports**: Import from `react-router-dom`, not `react-router`. Found in 15+ files during TypeScript migration; causes silent runtime failure.
3. **Raw SQL in migrations**: Use `psycopg2.sql.Identifier()` and a whitelist, never f-strings. F-strings bypass Django ORM's SQL injection protection.
4. **`django-ratelimit` status codes**: The `Ratelimited` exception inherits from `PermissionDenied`, so DRF returns 403. A custom exception handler checking `isinstance(exc, Ratelimited)` is required to return the correct 429.
5. **Debounce timers in React**: Use `useRef` not `useState` for timer IDs. `useState` triggers re-renders, causes callback recreation, and leads to memory leaks.
6. **Test DB after migration changes**: If the test DB predates a migration change, tests fail with `FieldError`. Fix: `--noinput` to force a fresh rebuild.

---

### `/backend/CLAUDE.md` (~50 lines)

Sections:
- **Commands** — `source venv/bin/activate`, `python manage.py runserver`, `migrate`, test commands per app, `python manage.py warm_moderation_cache`
- **Conventions** — all config in `constants.py` (never magic numbers), bracketed logging prefixes (`[CACHE]`, `[PERF]`, `[ERROR]`, `[CIRCUIT]`), type hints required on all service methods, escape `%` and `_` in `icontains` search queries
- **Gotcha** — `--noinput` for test DB reset (also in root, repeated here for locality)

---

### `/web/CLAUDE.md` (~40 lines)

Sections:
- **Commands** — `npm run dev` (port 5174), `npm run build` (includes type-check), `npm run type-check`, `npm run test`, `npm run test:e2e`
- **Conventions** — all source files in `.ts`/`.tsx` (no `.js` in `src/`), import from `react-router-dom` not `react-router`, `strict: false` during migration (will enable incrementally)
- **Gotcha** — `useRef` for debounce timers; `DOMPurify` required for any user-generated HTML rendering

---

### `/plant_community_mobile/CLAUDE.md` (~40 lines)

Sections:
- **Commands** — `flutter run -d ios/android/macos`, `flutter test`, `flutter pub run build_runner build --delete-conflicting-outputs`, `python scripts/check_flutter_security.py`
- **Conventions** — Riverpod 3.x: use `Notifier` class with `@riverpod` (not `StateNotifier`), `kDebugMode` in go_router (not `true`), `CardThemeData` not `CardTheme`, `.withValues(alpha:)` not `.withOpacity()`
- **Gotcha** — always cancel `StreamSubscription` in `ref.onDispose()`; use `flutter_secure_storage` for tokens (never `SharedPreferences`)

---

## Migration

The existing root `/CLAUDE.md` is replaced entirely — not updated in place. The four new files are written fresh. The old file is deleted after the new files are committed and verified.

## What Gets Deleted

Everything that was in the old CLAUDE.md but does not belong in any of the new files:

- Project status tables ("What Works", "In Progress", "Planned")
- Implementation history and PR references
- Detailed code examples (these live in pattern docs)
- Firebase auth flow walkthrough (lives in `plant_community_mobile/docs/patterns/firebase-auth.md`)
- TypeScript migration history (lives in `web/TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md`)
- Deployment checklists (belong in a runbook, not CLAUDE.md)
- Architecture decision rationale (belongs in ADRs)
- Verbose descriptions of what's implemented

## Success Criteria

- Root CLAUDE.md ≤ 150 lines
- Each platform sub-file ≤ 55 lines
- Zero stale content (no PR references, completion claims, or status tables — framework version references in conventions are fine)
- Pattern Library section links to all pattern docs with one-line descriptions
- Agents section accurately reflects `.claude/agents/` directory contents
