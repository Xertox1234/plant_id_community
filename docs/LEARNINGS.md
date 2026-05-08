# Learnings

This file is append-only. New entries are added by main Claude after each code review session, based on `pattern-codifier` output. Never edit existing entries.

## Index
- [Django/DRF](#djangodrf)
- [Wagtail](#wagtail)
- [React/TypeScript](#reacttypescript)
- [Flutter/Firebase](#flutterfirebase)
- [Security](#security)
- [Performance](#performance)
- [Testing](#testing)
- [Celery](#celery)
- [Tooling / Agents](#tooling--agents)

---

## Django/DRF

### [2025-11-06] ViewSet `get_permissions()` silently ignores `@action` permission_classes (Issue #131)
**Mistake**: Custom `get_permissions()` override in a ViewSet returned blanket permission lists for all actions, silently overriding the `permission_classes` specified on individual `@action` decorators. NEW-trust users were able to bypass upload restrictions because the action-level `CanUploadImages` permission was never evaluated.
**Fix**: Custom actions must be explicitly passed through to `super().get_permissions()` so their decorator-level permissions are respected.
**Rule**: In any ViewSet with a custom `get_permissions()`, enumerate all custom `@action` names and delegate them to `super().get_permissions()` — never return a blanket list that covers custom actions.
**Agent**: django-drf-reviewer

---

## Wagtail

### [2026-05-06] Wagtail version mismatch between requirements.txt and requirements-dev.txt
**Mistake**: `requirements.txt` referenced `wagtail==7.4` while `requirements-dev.txt` had `wagtail==7.1.2`, causing inconsistent behaviour between dev and production environments. Agents and pattern docs that referenced a single Wagtail version were silently wrong for one environment.
**Fix**: Audited both files; agents and pattern docs now reference both versions with dev/prod context where behaviour differs.
**Rule**: Any version reference in an agent checklist or pattern doc must specify dev vs. prod if they differ. Format: "dev (`requirements-dev.txt`): 7.1.2 · prod (`requirements.txt`): 7.4".
**Agent**: wagtail-reviewer

### [2025-11-xx] Signal handlers must use `isinstance()` not `hasattr()` for page type checks
**Mistake**: Signal handlers checking for Wagtail page subtypes used `hasattr(instance, 'blogpostpage')`. Multi-table inheritance makes this unreliable — the parent `Page` instance receives the signal, and the child table row may not be accessible at that point.
**Fix**: Replaced all `hasattr` type checks with `isinstance(instance, BlogPostPage)`.
**Rule**: Always use `isinstance()` for Wagtail page type checks in signal handlers. `hasattr()` on multi-table inheritance child attributes is unreliable.
**Agent**: wagtail-reviewer

---

## React/TypeScript

### [2025-11-08] React Router v7 imports must use `react-router-dom` not `react-router` (Issue #134)
**Mistake**: 15+ files imported `useNavigate`, `useParams`, `useLocation` from `'react-router'` instead of `'react-router-dom'`. This caused a silent runtime crash: "Cannot read properties of undefined (reading 'navigate')".
**Fix**: Global search-and-replace of the import source. Zero compilation errors after fix.
**Rule**: All React Router v7 hooks must be imported from `'react-router-dom'`. The bare `'react-router'` package does not export these hooks in v7.
**Agent**: react-typescript-reviewer

### [2025-11-xx] Debounce timers must use `useRef`, not `useState`
**Mistake**: Timer IDs stored in `useState` triggered unnecessary re-renders and created stale closure bugs in the search page debounce handler. The `useCallback` dependency array needed to include the state setter, causing the callback to be recreated on each keystroke and defeating the debounce.
**Fix**: Moved timer to `useRef` with cleanup in `useEffect` return.
**Rule**: All timers (setTimeout, setInterval) in React components must be stored in `useRef`. Never store timer IDs in `useState`.
**Agent**: react-typescript-reviewer

---

## Flutter/Firebase

### [2025-11-15] StreamSubscription memory leaks from Firebase auth state listener (PR #200)
**Mistake**: The auth state `StreamSubscription<User?>` was not cancelled in `ref.onDispose()`. This caused a persistent Firebase connection after the provider was disposed, leading to memory leaks visible across hot restarts.
**Fix**: Added `ref.onDispose(() { _authStateSubscription?.cancel(); })` to the `build()` method.
**Rule**: Every `StreamSubscription` in a Riverpod provider MUST be cancelled in `ref.onDispose()`. This is non-negotiable — Firebase listeners are persistent connections that survive widget disposal.
**Agent**: flutter-firebase-reviewer

### [2025-11-15] GDPR violation — unredacted email in Django backend logs (PR #200)
**Mistake**: Backend Firebase token exchange endpoint logged the full email address from the decoded Firebase token.
**Fix**: Added `redact_email()` helper that masks the local part: `william@example.com` → `wi***@example.com`.
**Rule**: No backend log statement may contain a full email address. Always pass email values through `redact_email()` before logging.
**Agent**: flutter-firebase-reviewer, security-reviewer

---

## Security

### [2025-11-11] F-strings in raw SQL bypass Django ORM injection protection (Issue #012)
**Mistake**: A migration used f-string interpolation to construct `ALTER TABLE` statements with dynamic table names. This bypassed Django ORM's SQL injection protection.
**Fix**: Replaced f-strings with `psycopg2.sql.Identifier()` + a hardcoded whitelist of allowed table names.
**Rule**: Never use f-strings or string concatenation to build raw SQL. Use `psycopg2.sql.Identifier()` for dynamic identifiers and validate against a hardcoded whitelist.
**Agent**: security-reviewer

### [2025-11-xx] `icontains` queries must escape `%` and `_` SQL wildcards
**Mistake**: Search endpoints used `icontains` queries without escaping SQL wildcard characters. A query containing `%` matched unintended records.
**Fix**: Added `escape_search_query()` helper that escapes `%` → `\%` and `_` → `\_`.
**Rule**: All user-supplied strings used in `icontains` (or any Django ORM filter that maps to SQL `LIKE`) must pass through `escape_search_query()` first.
**Agent**: security-reviewer

---

## Performance

### [2025-11-xx] Lenient query count assertions hide N+1 regressions (Issue #117)
**Mistake**: Performance tests used `assertLess(query_count, 10)` which allowed the query count to grow from 1 to 9 without any test failing. An N+1 regression went undetected until production load revealed it.
**Fix**: Changed all performance test assertions to strict equality: `assertEqual(query_count, N)`.
**Rule**: Performance tests must use `assertEqual(query_count, N)` with a docstring explaining why N is the expected count. `assertLess` is only acceptable when the count genuinely varies (document why).
**Agent**: performance-reviewer, test-quality-reviewer

---

## Testing

### [2025-11-xx] Django ORM mock tests passed while production migrations failed
**Mistake**: Unit tests that mocked the Django ORM returned passing results for queries that assumed a schema that didn't match the actual migration state. After deploying a migration, the mocked tests continued to pass while production queries failed.
**Fix**: Removed all ORM mocks; tests now hit a real PostgreSQL test database.
**Rule**: Never mock Django ORM, QuerySets, or database connections in backend tests. Always use the real PostgreSQL test database with `--keepdb`.
**Agent**: test-quality-reviewer

---

## Celery

*(No entries yet — will be populated by pattern-codifier after first review involving Celery files.)*

---

## Security (2026-05-06 additions)

### [2026-05-06] ICS calendar export vulnerable to CRLF injection from user-supplied strings
**Mistake**: `plant_name`, `reminder_type`, and `description` were embedded in ICS f-strings without stripping `\r` or `\n`. An attacker could inject arbitrary ICS fields by including CRLF sequences in a plant name.
**Fix**: Added `_ics_safe = lambda s: str(s).replace('\r', '').replace('\n', ' ')` and applied it to every user-supplied field before embedding in the ICS template.
**Rule**: Every user-supplied string embedded in an ICS (iCalendar) template MUST pass through a CRLF-stripping sanitizer. Strip both `\r` and `\n` — stripping only `\n` is insufficient.
**Agent**: pattern-codifier

### [2026-05-06] Numeric API parameters accepted without `int()` conversion or range check
**Mistake**: `snooze_hours` from `request.data` was passed directly to `mark_snoozed()`. Passing `"abc"` or `"-1"` caused a downstream `TypeError` or silently allowed unreasonable values (e.g., 100,000 hours).
**Fix**: Added `int()` conversion inside `try/except` followed by `1 <= snooze_hours <= 8760` guard, returning HTTP 400 on failure.
**Rule**: All numeric parameters from `request.data` or `query_params` MUST be explicitly converted with `int()` inside a `try/except`, then validated against named min/max constants before passing to service methods.
**Agent**: pattern-codifier

---

## Testing (2026-05-06 additions)

### [2026-05-06] Plant.id v2 mock responses silently pass tests while production uses v3 API
**Mistake**: 3 test files still used v2 mock dicts (`suggestions[].plant_name`). Tests passed because the mock matched the test, but production already parsed v3 (`result.classification.suggestions[].name`).
**Fix**: Updated all 3 mocks to v3 structure. Tests expecting a single API call now expect two (identify + health_assessment).
**Rule**: Search for `"plant_name"` as the v2 canary in Plant.id test mocks. Any mock with a top-level `"suggestions"` key is v2 and must be migrated. See `backend/docs/patterns/domain/plant-identification.md` for the canonical v3 mock structure.
**Agent**: pattern-codifier

### [2026-05-06] `on_commit` lambdas make target-function patches ineffective in tests
**Mistake**: A test patched `BlogPostView.objects.create` to raise an exception, but the call was inside a `transaction.on_commit` lambda. Django tests wrap each test in a transaction that never commits, so the lambda was queued but never executed. The error-handling path was never tested.
**Fix**: Patched `apps.blog.middleware.transaction.on_commit` with `side_effect=lambda fn: fn()` to execute the callback immediately.
**Rule**: When testing code that wraps a call in `transaction.on_commit`, you must either (a) patch `transaction.on_commit` at the call site to execute immediately, or (b) use `self.captureOnCommitCallbacks(execute=True)`. The patch path must match the import in the module under test, not the canonical Django path.
**Agent**: pattern-codifier

---

## Tooling / Agents

### [2026-05-07] Bash `**` glob silently collapses to `*` without `shopt -s globstar`
**Mistake**: The `full-review-orchestrator` `file:` filter spec relied on `**` for recursive path matching (`file:backend/apps/**`). Default Bash treats `**` as `*` — a single-component wildcard — so `backend/apps/**` matched only direct children of `apps/`, not nested files. The bug would have manifested as the repair phase silently skipping findings under nested paths (e.g., `backend/apps/forum/viewsets/foo.py`).
**Fix**: Pinned the implementation recipe in `.claude/agents/full-review-orchestrator.md` to `shopt -s globstar nullglob` before glob expansion, with `find <root> -path '<pattern>'` as the alternative. Called out the default-bash trap explicitly.
**Rule**: Any agent prompt or shell helper that uses `**` for recursive matching MUST set `shopt -s globstar` first, OR use `find -path` instead. Never assume `**` works in bash by default — globstar is an opt-in Bash 4+ feature, off by default. Same applies in zsh's emulated bash mode.
**Agent**: full-review-orchestrator

### [2026-05-07] Full-review orchestrator at full-repo scale: rate-limit risk + main-context overflow
**Mistake**: First end-to-end run of `full-review-orchestrator` over the entire repo (63 invocations across 8 waves of 8). Two operational failures emerged. (1) The 8th and final wave hit Anthropic per-account rate limits — all 7 sub-agents in that wave returned `You've hit your limit`, losing every web/* invocation. (2) Reviewer agents in waves 2-8 are dispatched via `subagent_type=general-purpose` (project-local agents in `.claude/agents/` are not auto-discovered as subagent types in this environment), and the original orchestrator template asked each agent to return findings as JSON in its message body — main Claude's context filled with ~700 KB of finding text after wave 1, threatening compaction.
**Fix**: (a) Switched waves 2-8 dispatch prompt to a "disk-write" pattern: agent uses its own `Write` tool to save findings JSON to `/tmp/wave_results/<wave>__<agent>__<batch>.json`, then returns only a one-line summary (`Wrote ...json — N findings (X critical, ...)`) so main Claude never holds the full payload. Aggregation reads those files at Phase 3. (b) Recorded the 7 lost wave-8 invocations in `failed_invocations` so the resume flow can re-dispatch only those — the orchestrator's existing `.<review_id>-partial.json` checkpoint already supports this.
**Rule**: For any orchestrator that dispatches > ~30 sub-agents in a single session, use the disk-write + summary-only return pattern; do not let agents return large JSON inline. Plan for rate-limit pauses at the 50-60 invocation mark per Anthropic account; the orchestrator's resume design (partial checkpoint + completed_waves array) handles this if every wave's results land on disk before the next wave starts. When a project-local reviewer agent isn't accepted as `subagent_type`, fall back to `general-purpose` and instruct it to read `.claude/agents/<name>.md` itself for persona — works equivalently.
**Agent**: full-review-orchestrator

---

## Security

### [2026-05-07] Firebase verify_id_token() does NOT enforce email_verified — backend must gate explicitly
**Mistake**: `apps/users/firebase_auth_views.py` accepted any successfully-verified Firebase ID token and looked up / created the matching Django user purely on `email`. An attacker could sign up with Firebase email/password using a victim's email address, never click the verify link, and still log in as that user once a Django account with the same email existed (account takeover).
**Fix**: After `decoded_token = firebase_auth.verify_id_token(...)`, explicitly check `decoded_token.get('email_verified')` and `decoded_token.get('firebase', {}).get('sign_in_provider')`. Reject with HTTP 403 unless the email is verified OR the provider is in a TRUSTED_PROVIDERS allowlist (`google.com`, `apple.com` self-verify emails). Confirmed via Context7 docs (`/websites/firebase_google_auth_admin`) that the SDK does not implicitly enforce verification — it returns the claim and leaves the policy to the caller.
**Rule**: Any backend that exchanges a Firebase ID token for a session/JWT and matches users by email MUST gate on `email_verified == True` (or a federated-provider allowlist). `verify_id_token` only validates signature/expiry/audience — verification status of the email is the integrator's responsibility. See `backend/docs/patterns/security/authentication.md` for the full pattern.
**Agent**: security-reviewer
