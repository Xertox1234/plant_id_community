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

### [2026-07-12] `SummaryItem` is a `Component` on Wagtail 7.4.2 — the positional-args constructor doesn't exist (audit H16, todo 254 Slice 2)

**Mistake**: built a homepage "N awaiting moderation" panel using
`SummaryItem(label, count, url_label, url, icon_name=..., order=...)` —
copied verbatim from `apps/blog/wagtail_hooks.py`'s existing "Pending
Comments" panel, which uses the same call shape. Both raise `TypeError:
SummaryItem.__init__() got an unexpected keyword argument 'icon_name'` on
every `/cms/` load: on Wagtail 7.4.2, `SummaryItem` is a `Component`
subclass whose `__init__(self, request)` takes only the request, and
rendering is template-driven (`get_context_data` + `template_name`), not
constructor args. The blog's version is invisible because its whole hook
body is `except Exception: pass` — it has been silently broken with no
test ever hitting `/cms/` to catch it (see todo 264).
**Fix**: subclass `SummaryItem`, set `template_name`, override
`get_context_data(self, parent_context)` to return the template context,
and add a small template. See `wagtail.images.wagtail_hooks.ImagesSummaryItem`
plus its `site_summary_images.html` for the upstream precedent, or
`backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py`'s
`ForumModerationSummaryItem` for the in-repo one this fix produced.
**Rule**: Before wiring a new `construct_homepage_summary_items` hook, check
the installed Wagtail version's actual `SummaryItem.__init__` signature —
don't copy an existing in-repo call site on faith, it may already be stale
against the pinned Wagtail version.
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

### [2026-06-21] Rendering a structured error object showed the literal "[object Object]" (PR #381)

**Mistake**: `LoginPage`/`SignupPage` passed the whole structured `AuthError` (`{message, code, details}`) to `setServerError(String(sanitizeError(result.error)))`. `sanitizeError()` returns non-strings UNCHANGED (`if (typeof error !== 'string') return error`), so it neither sanitized nor coerced — and `String({...})` rendered the literal `[object Object]` to the user on every server-side auth failure (e.g. "email already exists", bad credentials). The bug was duplicated across both auth pages.
**Fix**: Render `result.error?.message` — `authService` already builds a readable string there (signup even flattens DRF field errors into it). Added `LoginPage.test.tsx` / `SignupPage.test.tsx` to guard it.
**Rule**: Display `error.message` (a string) for any structured error, never the error object. A `sanitize*`/transform helper that returns non-strings unchanged is a no-op on objects — coerce to the string field BEFORE passing it in.
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

### [2026-05-08] `subosito/flutter-action@v2`: never combine `flutter-version` and `channel`

**Mistake**: `security-scan.yml` Flutter setup specified both `flutter-version: '3.38.x'` and `channel: 'stable'`. The action attempts to satisfy both simultaneously, which causes ambiguous resolution — the pinned version may not match the latest stable, leading to either a failed lookup or divergence between the security-scan workflow and the mobile-ci workflow (which used `channel: stable` alone).
**Fix**: Drop the `flutter-version` pin entirely; use `channel: stable` to always track the latest stable release. If a hard pin is ever needed for a specific reason, use `flutter-version` alone (no `channel`), and document why.
**Rule**: In `subosito/flutter-action@v2`, choose exactly one resolution strategy: `channel: stable` (floating latest) OR `flutter-version: 'X.Y.Z'` (exact pin). Combining both is unsupported and produces silently ambiguous behaviour. Keep all jobs in a repo using the same strategy so Flutter versions stay in sync across workflows.
**Agent**: flutter-dart-reviewer

### [2026-05-07] Full-review orchestrator at full-repo scale: rate-limit risk + main-context overflow

**Mistake**: First end-to-end run of `full-review-orchestrator` over the entire repo (63 invocations across 8 waves of 8). Two operational failures emerged. (1) The 8th and final wave hit Anthropic per-account rate limits — all 7 sub-agents in that wave returned `You've hit your limit`, losing every web/* invocation. (2) Reviewer agents in waves 2-8 are dispatched via `subagent_type=general-purpose` (project-local agents in `.claude/agents/` are not auto-discovered as subagent types in this environment), and the original orchestrator template asked each agent to return findings as JSON in its message body — main Claude's context filled with ~700 KB of finding text after wave 1, threatening compaction.
**Fix**: (a) Switched waves 2-8 dispatch prompt to a "disk-write" pattern: agent uses its own `Write` tool to save findings JSON to `/tmp/wave_results/<wave>__<agent>__<batch>.json`, then returns only a one-line summary (`Wrote ...json — N findings (X critical, ...)`) so main Claude never holds the full payload. Aggregation reads those files at Phase 3. (b) Recorded the 7 lost wave-8 invocations in `failed_invocations` so the resume flow can re-dispatch only those — the orchestrator's existing `.<review_id>-partial.json` checkpoint already supports this.
**Rule**: For any orchestrator that dispatches > ~30 sub-agents in a single session, use the disk-write + summary-only return pattern; do not let agents return large JSON inline. Plan for rate-limit pauses at the 50-60 invocation mark per Anthropic account; the orchestrator's resume design (partial checkpoint + completed_waves array) handles this if every wave's results land on disk before the next wave starts. When a project-local reviewer agent isn't accepted as `subagent_type`, fall back to `general-purpose` and instruct it to read `.claude/agents/<name>.md` itself for persona — works equivalently.
**Agent**: full-review-orchestrator

---

## Security (2026-05-07 additions)

### [2026-05-07] Firebase verify_id_token() does NOT enforce email_verified — backend must gate explicitly

**Mistake**: `apps/users/firebase_auth_views.py` accepted any successfully-verified Firebase ID token and looked up / created the matching Django user purely on `email`. An attacker could sign up with Firebase email/password using a victim's email address, never click the verify link, and still log in as that user once a Django account with the same email existed (account takeover).
**Fix**: After `decoded_token = firebase_auth.verify_id_token(...)`, explicitly check `decoded_token.get('email_verified')` and `decoded_token.get('firebase', {}).get('sign_in_provider')`. Reject with HTTP 403 unless the email is verified OR the provider is in a TRUSTED_PROVIDERS allowlist (`google.com`, `apple.com` self-verify emails). Confirmed via Context7 docs (`/websites/firebase_google_auth_admin`) that the SDK does not implicitly enforce verification — it returns the claim and leaves the policy to the caller.
**Rule**: Any backend that exchanges a Firebase ID token for a session/JWT and matches users by email MUST gate on `email_verified == True` (or a federated-provider allowlist). `verify_id_token` only validates signature/expiry/audience — verification status of the email is the integrator's responsibility. See `backend/docs/patterns/security/authentication.md` for the full pattern.

---

## Tooling / Agents (2026-05-08 additions)

### [2026-05-08] Name-gated pre-commit hooks break files that have both a tracked and a local form

**Mistake**: A `block-claude-md` hook used `grep -E "CLAUDE\.md"` against staged filenames to prevent `CLAUDE.md` from ever being committed. The intent was to stop developers accidentally committing local personalisation notes. Instead it blocked the *team-shared* `CLAUDE.md` (project conventions, delegation rules, critical gotchas) which is intentionally tracked. The hook had no way to distinguish the two forms.
**Fix**: Removed `block-claude-md`. The two concerns are already handled separately: `.gitignore` with a `CLAUDE.md` entry prevents accidental commits of a purely-local file; `scan-api-keys` catches real credentials regardless of filename. The team-shared `CLAUDE.md` is committed normally.
**Rule**: Name-gating ("block this filename") is only appropriate for files that must *never* appear in git history (e.g. `.env`, `*.pem`). For files that have a legitimate tracked form alongside a private local form, use `.gitignore` to guard the private form and rely on content-scanning hooks (detect-secrets, scan-api-keys) to catch actual secrets. Combining both in one hook conflates two distinct problems and will eventually block a legitimate commit.

---

## Performance (2026-05-08 additions)

### [2026-05-08] Reverse OneToOne accessed in three separate SerializerMethodFields — 3× N+1 per row

**Mistake**: `PostSerializer` in `forum_integration/serializers.py` accessed `obj.rich_content` (a reverse OneToOne to `RichPost`) independently in `get_rich_content`, `get_content_format`, and `get_ai_assisted`. Each try/except is a separate DB query when `select_related` is absent — tripling the query cost per serialized Post.
**Fix**: Add `select_related('rich_content')` to the ViewSet queryset and consolidate all three field reads into a shared `_get_rich_post()` helper that caches on the instance, reducing per-post DB hits from 3 to 1.
**Rule**: Any reverse OneToOne relation accessed in more than one `SerializerMethodField` must be in `select_related()` and read from a single consolidated access point. See `backend/docs/patterns/performance/query-optimization.md` Pattern 26.
**Agent**: performance-reviewer

### [2026-05-08] Instance-level cache on model instance inside serializer risks stale data after create()

**Mistake**: Caching a reverse relation as `obj._rich_post_cache` directly on the Post instance inside a serializer method. If the same instance is mutated (e.g. `RichPost.objects.create()`) then re-serialized in the same request, the cached `None` is returned instead of the freshly-created object.
**Fix**: Cache on the serializer instance (dict keyed by pk) or eliminate caching entirely via `select_related()`.
**Rule**: Never attach cache attributes to a model instance inside a serializer. See `backend/docs/patterns/performance/query-optimization.md` Pattern 27.
**Agent**: performance-reviewer

---

## Django/DRF (2026-05-08 additions)

### [2026-05-08] Identical helper method duplicated across two serializer classes

**Mistake**: `_normalize_rich_content` was defined verbatim in both `CreateTopicSerializer` and `CreatePostSerializer`. A future change to one copy will not propagate to the other, causing silent divergence in plant_mention normalisation logic.
**Fix**: Extract into a `RichContentMixin` and have both serializers inherit from it (todo 066).
**Rule**: Any serializer helper method appearing identically in two or more classes must be extracted to a mixin before merging. See `backend/docs/patterns/performance/query-optimization.md` Pattern 28.
**Agent**: django-drf-reviewer

---

## Testing (2026-05-08 additions)

### [2026-05-08] Machina dynamic class loader raises AppNotFoundError at import time — all forum_integration tests unreachable

**Mistake**: `apps.forum_integration` tests all failed at import with `machina.core.loading.AppNotFoundError: No app found matching 'forum_conversation.managers'` because Machina's dynamic loader requires its full `machina.apps.*` subtree in `INSTALLED_APPS`. The error fires before any test's `setUp`, making the entire suite unreachable and masking regressions (todo 065).
**Fix**: Ensure all required `machina.apps.*` entries are present in `INSTALLED_APPS` in the test settings.
**Rule**: Any test module importing from django-machina must verify the full app subtree is in `INSTALLED_APPS` — a missing entry causes an import-time failure, not a test-time assertion failure, so the problem is invisible until the suite is run.
**Agent**: test-quality-reviewer
**Agent**: security-reviewer

---

## Audit 2026-05-17 (full audit additions)

### [2026-05-17] A stub `tests.py` next to a `tests/` package aborts ALL Django test discovery

**Mistake**: Six apps (`blog`, `core`, `forum`, `garden`, `plant_identification`, `users`) each kept the Django default 3-line stub `apps/<app>/tests.py` *and* had a real `apps/<app>/tests/` package. `unittest`'s discovery imports a module named `tests` and a package named `tests` from the same directory, raising `ImportError: 'tests' module incorrectly imported` — and it aborts the **entire** `manage.py test` run, not just that app. The backend test suite was completely unrunnable and nobody noticed because CI ran apps explicitly.
**Fix**: Delete the stub `tests.py` files (audit C1). Tests live in the `tests/` package.
**Rule**: An app must have **either** `tests.py` **or** a `tests/` package — never both. When you add a `tests/` package, delete the stub `tests.py` in the same commit.
**Agent**: baseline (audit Phase 1)

### [2026-05-17] A discovery-blocking collision hides every downstream broken module

**Mistake**: While C1's collision aborted discovery, three unrelated pre-existing breakages were completely invisible: `test_diagnosis_{api,models}.py` import a `DiagnosisCard` model removed in migration 0025 (H37), and `PlantDiseaseDatabaseSerializer` declares a `created_at` field its model lacks, breaking OpenAPI schema generation (H38). They only surfaced once C1 was fixed and discovery ran end-to-end.
**Fix**: Tracked in todo 080.
**Rule**: After fixing anything that blocks test collection/build, expect a wave of newly-visible failures — re-run the full suite and triage them; they are not regressions from your fix.
**Agent**: baseline (audit Phases 3 & 5)

### [2026-05-17] `ENABLE_FORUM=True` *disables* the headless `apps/forum/` app

**Mistake**: `settings.py` appends `apps.forum` to `LOCAL_APPS` only in the `else` branch of `if ENABLE_FORUM:` — when `ENABLE_FORUM=True` the legacy **Machina** forum is installed and the headless DRF `apps/forum/` is NOT. `.env` sets `ENABLE_FORUM=True`, so `apps/forum/` (viewsets, models, 16 test modules) is dead code in the running config, and all its tests error with `RuntimeError: ... isn't in INSTALLED_APPS`. The flag name reads backwards relative to which forum it enables, and the root `CLAUDE.md` describes `apps/forum/` as the active forum — a direct contradiction.
**Fix**: Deferred (todo 084) — the forum-config question (promote `apps/forum/` or delete it) needs an owner decision.
**Rule**: `apps/forum/` and Machina are mutually exclusive and gated by `ENABLE_FORUM`; `apps/forum/` is only live when `ENABLE_FORUM=False`. Do not assume `apps/forum/` code runs in the current dev/prod config.
**Agent**: baseline (audit Phase 1)

---

## Forum todos 104–116 (2026-05-29 additions)

> Note: the active forum API app is `apps/forum_integration/` (Machina-based,
> `ENABLE_FORUM=True`), NOT `apps/forum/` — see the 2026-05-17 entry above.

### [2026-05-29] django-ratelimit's `Ratelimited` is bare — `Retry-After` cannot be derived in the handler

**Mistake**: The 429 exception handler hardcoded `Retry-After: 3600`, so a `30/m` search limit told clients to back off an hour. The obvious fix ("read `exc.rate`") is impossible: in django-ratelimit 4.1.0, `Ratelimited` is `class Ratelimited(PermissionDenied): pass` (no rate), and the `@ratelimit` decorator discards the usage dict — it keeps only `request.limited`. Neither the exception nor the request exposes the rate downstream (todo 115).
**Fix**: A drop-in `ratelimit` wrapper (`apps/core/ratelimit.py`) catches `Ratelimited` and re-raises `RatelimitedWithRate(rate)` — a subclass, so `isinstance(exc, Ratelimited)` still matches — and the handler derives the window from `exc.rate` (`/m`→60, `/h`→3600, …) guarded by `isinstance(rate, str)` (rate may be a callable).
**Rule**: Don't assume `Ratelimited` carries the rate; capture it at the decorator site. `Retry-After` must reflect the real window, not a constant. See `backend/docs/patterns/architecture/rate-limiting.md`.
**Agent**: api-design-reviewer

### [2026-05-29] A relation-reading `SerializerMethodField` N+1s EVERY list endpoint that uses the serializer

**Mistake**: Adding `reaction_counts` (iterates `obj.reactions`) to the shared `PostSerializer` fixed the list endpoint but silently introduced an N+1 on the public community feed (`TopicsFeedView` → `first_post`, a `PostSerializer` subclass) and on `forum_search`. Only the directly-edited `PostListView` got a prefetch; code review caught the other two as a CRITICAL (todo 105).
**Fix**: `prefetch_related("reactions")` on every list queryset feeding the serializer (incl. `TopicsFeedView` via `first_post__reactions`), with a `CaptureQueriesContext` constant-count N+1 guard per path.
**Rule**: When you add a field that reads a relation to a SHARED serializer, audit and prefetch in ALL list views (and nested-serializer parents) that use it — not just the one you came to change. Add a query-count test per path.
**Agent**: performance-reviewer

### [2026-05-29] `(max_order or -1) + 1` collides because 0 is falsy — a post could never hold >1 image

**Mistake**: `ForumPostImage.save()` auto-assigned `upload_order` with `(max_order or -1) + 1`. When the current max was `0`, `0 or -1` evaluates to `-1`, so the 2nd image also got order 0 and collided on `unique_together(post, upload_order)` — no post could ever store more than one image (todo 116). The same guard also re-fired on UPDATE, relocating an order-0 image when its alt_text was edited.
**Fix**: `(max_order if max_order is not None else -1) + 1`, and gate the auto-assign on `self.pk is None` (insert-only) so updates preserve order.
**Rule**: Never use `or` for a numeric default where 0 is valid — use `is None`. Model `save()` auto-assignment must be insert-only (`self.pk is None`), or it mutates rows on every update.
**Agent**: django-drf-reviewer

### [2026-05-29] Catching a DB error inside `transaction.atomic()` without a savepoint poisons the transaction

**Mistake**: Wrapping a per-item insert loop in one `transaction.atomic()` (for an atomic image-cap check) while keeping the existing `try/except` per item: a caught `IntegrityError` left the connection in a failed-transaction state, so the next insert raised `TransactionManagementError` (todo 113).
**Fix**: Wrap each item's insert in a nested `with transaction.atomic():` (savepoint) so a failed item rolls back only its savepoint and the outer transaction stays usable — preserving partial-success semantics.
**Rule**: If you catch exceptions from DB ops inside an outer `atomic()` and continue, each caught op must be in its own nested `atomic()` savepoint.
**Agent**: django-drf-reviewer

### [2026-05-29] Squash-merging a feature branch then continuing on it re-conflicts and resurrects completed todos

**Mistake**: This branch's earlier work was squash-merged to main (#290), but the branch kept going without rebasing. Merging main back in conflicted on `api_views.py` (squashed vs evolved same code) and RE-INTRODUCED todos the branch had already completed — 099–103 reappeared as `pending` alongside their `archive/…-completed` versions. A teammate PR (#291) on the same branch overlapped the same files mid-rebase too.
**Fix**: Verified the branch was a strict superset of the squash (only the squash commit was ahead on main), resolved `api_views.py` to the branch's evolved version, kept the branch's todo states, and removed the resurrected `pending` dupes.
**Rule**: After a feature branch is squash-merged to main, rebase/reconcile before continuing — expect code conflicts (squashed vs evolved) AND resurrected completed-todo files. Before committing such a merge, grep for any `todos/<id>-pending-*` that also has a `todos/archive/<id>-*`.
**Agent**: baseline

### [2026-05-29] Harness: `scripts/kimi-review` is drift-locked; recurring mistakes now flagged at write-time

**Mistake/Context**: Building review-time trigger capture (#298–302) surfaced a harness trap: `scripts/kimi-review` is a *vendored* copy of a canonical engine, and `scripts/check-kimi-engine.sh` runs in pre-commit and blocks the commit if the vendored copy drifts — so editing `scripts/kimi-review` directly breaks the commit gate.
**Fix/Pattern**: To change the review engine, edit the canonical copy and run `scripts/sync-kimi-engine.sh`; never edit the vendored `scripts/kimi-review`. Separately, recurring mistakes are now flagged at write-time from `docs/rules/triggers.json` (matcher `scripts/inject/match_triggers.py`, injected by `.claude/hooks/inject-patterns.sh`); add one via `scripts/inject/capture_trigger.py`, or auto-capture from review via the code-review orchestrator's Phase 2.5 → `scripts/inject/capture_from_review.py`. Design: `docs/superpowers/specs/2026-05-29-jit-mistake-injection-design.md`.
**Rule**: Never edit `scripts/kimi-review` directly (drift-checked vendored engine) — sync via `scripts/sync-kimi-engine.sh`. A recurring, signature-able mistake belongs in `triggers.json`, not only in a prose rule.
**Agent**: —

### [2026-06-02] `Count("id")` on a UUID-PK model 500s — and an untested endpoint hid it behind a green suite

**Mistake**: A full-audit perf fix rewrote `GardenBed.analytics` to aggregate with `Count("id")`. `Plant`/`CareTask` use a UUID primary key (no `id` field), so `Count("id")` raises `FieldError` → 500 on every call. The 687-test backend suite passed because the `analytics` (and sibling `harvests/statistics`) endpoints had ZERO test coverage — the manifest was even marked "verified, 150 tests pass." Phase 6 code review (not the suite) caught it, and also surfaced a pre-existing `Count("uuid")` 500 in `statistics` (`Harvest` has an `id` PK, no `uuid`).
**Fix**: Use `Count("pk")` (resolves to the real primary key regardless of its field name) everywhere. Added `test_audit_aggregates.py` that hits both endpoints and pins `assertNumQueries`, so the FieldError class can never regress unnoticed.
**Rule**: Aggregate on `Count("pk")`, never `Count("id")`/`Count("uuid")`. And "N tests pass" is hollow verification unless those tests actually execute the changed code path — when you rewrite an endpoint's queries, add an endpoint test that exercises it.
**Agent**: performance-reviewer, django-drf-reviewer

### [2026-06-02] Celery `autoretry_for` is inert if the called service swallows the exception

**Mistake**: An audit finding flagged that `run_identification`'s task body set `status="failed"` before re-raising, tripping the idempotency guard so retries no-op'd — and a fix (move the write to `on_failure`) was written + "verified" with a unit test. But the test mocked the WHOLE `PlantIdentificationService`, hiding that the real service (`identification_service.py:226`) catches every exception, sets `failed`, and returns WITHOUT re-raising. So no exception ever escapes the task, `autoretry_for` never fires, and the `on_failure` fix is unreachable — the test asserted a `pending` state that can't occur in production.
**Fix**: Reverted the inert task-only change; filed todo 208 to fix the root cause (service re-raises retryable exceptions) together with the `on_failure` terminal-status write. A task-level retry finding is only real if exceptions actually propagate OUT of the task — verify the called service's except clauses re-raise, and don't mock the whole service in the test that's supposed to prove the retry path.
**Rule**: `autoretry_for` only works on exceptions that escape the task body. Before "fixing" a retry/`on_failure` bug, confirm the service the task calls actually re-raises (doesn't catch-and-return). Mock the external client, not the whole service, or the test proves nothing.
**Agent**: celery-async-reviewer

### [2026-06-02] Celery `task_`-prefixed option names are silently ignored in the task decorator

**Mistake (near-miss)**: Todo 205 (M13) instructed adding `acks_late=True` + `task_reject_on_worker_lost=True` to `run_identification`'s `@shared_task(...)`. The `task_`-prefixed form is the *global* Celery config setting name (`task_reject_on_worker_lost`, `task_acks_late`), NOT the per-task decorator option. Passed as a decorator kwarg it is silently accepted as an inert attribute and does nothing — the durability the finding wanted would never have taken effect, and no error would have flagged it. Caught at write-time by checking Context7 Celery docs before shipping.
**Fix**: Used the unprefixed per-task option `reject_on_worker_lost=True` (and `acks_late=True`). Added a test asserting `run_identification.acks_late is True` and `.reject_on_worker_lost is True` so a silent regression to the wrong name fails the suite. Verify durability scope too: `acks_late` only redelivers within the window BEFORE the task/service commits a non-`pending` status — once `status="processing"` is committed (here `identification_service.py:76`, before the 120s I/O), the idempotency guard short-circuits any redelivery.
**Rule**: Per-task options in the `@shared_task`/`@app.task` decorator are unprefixed (`acks_late`, `reject_on_worker_lost`); the `task_*` names are global config settings and are inert (no error) as decorator kwargs. Assert the task attribute in a test.
**Agent**: celery-async-reviewer

### [2026-06-02] Adding `choices=` to an existing writable serializer field silently breaks the write API

**Mistake (avoided)**: Todo 205 (M1) called for adding `choices` to `CareLog.activity_type` so `get_activity_type_display()` exists and drf-spectacular emits an enum. The field is writable through `CareLogSerializer` (NOT in `read_only_fields`), so a model `choices` turns DRF's auto-generated field into a `ChoiceField` that rejects any out-of-enum value on write with a 400 — a breaking change for clients sending free-form values. Risk closed by grepping every client: Flutter sends zero `activity_type`, web sends `watering`/`fertilizing`, tests send `watering`/`fertilizing`/`pruning`/`treatment` — all folded into the enum (+ `other`). The two out-of-enum strings found in the tree (`account_created`, `trust_level_upgrade`) write to a DIFFERENT model (`ActivityLog` in the `users` app), not `CareLog`.
**Fix**: Built `ACTIVITY_TYPE_CHOICES` as a deliberate superset of all client-sent values plus an `other` escape hatch. The migration is state-only (`choices` is not a DB constraint), so existing out-of-enum rows still read fine — `get_FOO_display()` returns the raw value when unmapped.
**Rule**: Before adding `choices=` to a writable field, enumerate every value real clients send (mobile + web + tests) and make the enum a superset. `blank=True` covers empty/omitted; an `other` member covers the long tail. State-only migration; no data risk.
**Agent**: django-drf-reviewer, api-design-reviewer

### [2026-06-06] Bare `format_html()` (no interpolation args) 500s the entire Wagtail admin on Django 6.0

**Mistake**: `apps/blog/wagtail_hooks.py` and `apps/forum_integration/wagtail_hooks.py` registered `insert_global_admin_css`/`insert_global_admin_js` hooks that called `format_html('<link ...>')` with a single literal string and NO interpolation args. On Django ≤5.x this was a silent deprecation warning; on Django 6.0 (the production version) it became a hard `TypeError: args or kwargs must be provided.`. Wagtail renders every `insert_global_admin_*` hook on EVERY admin page (`[fn() for fn in hooks.get_hooks(name)]`), so one bad hook 500'd all of `/cms/` — including the login page — in production. It stayed invisible locally because no test ever rendered an admin page, and `requirements-dev.txt` still pinned Django 5.2.7 while prod/CI ran 6.0.x (dev-pin reconciliation tracked in todo 217).
**Fix**: For hooks whose static assets exist, switched to `format_html('<link href="{}">', static('...'))` (a real format arg, also yielding hashed URLs). Deleted hooks that referenced files which never existed (a `static()` call there would have 500'd again under the strict manifest). Used `mark_safe(...)` for a no-interpolation literal (a stats-panel button). Added a regression test that calls every project global-admin hook the way Wagtail does.
**Rule**: Never call `format_html()` with no interpolation args — it raises `TypeError` on Django 6.0. For trusted static HTML use `mark_safe()`; when you need a URL/value, pass it as a format arg (`format_html('{}', static(...))`). Especially dangerous in `insert_global_admin_*` hooks, which render on every admin page, so a crash there takes down the whole CMS.
**Agent**: django-drf-reviewer, wagtail-reviewer

### [2026-06-06] `django` logger without `propagate=False` double-logs through root

**Mistake**: `settings.LOGGING` attaches the same handlers (`console`/`console_prod`) to the `django`, `apps`, and `plant_community_backend` loggers AND to `root`. `apps` and `plant_community_backend` set `propagate=False`, but `django` did not — so every `django.*` record (request/server/security/db) was handled once by the `django` logger and again by `root`, emitting twice in dev and prod. The `console`/`console_prod` pair is NOT the cause of duplication — their `require_debug_true`/`require_debug_false` filters make them mutually exclusive (the dev-vs-prod formatter split); collapsing them would have broken that and not fixed the real bug.
**Fix**: Added `propagate=False` to the `django` logger, matching its siblings. Regression test in `apps/blog/tests/` (a CI-collected, always-installed location — `apps/forum_integration/tests` is `--ignore`d by pytest) asserts all three project loggers set `propagate=False`.
**Rule**: A logger that defines its own `handlers` must also set `propagate=False` when `root` carries the same handlers, or every record double-emits. Don't diagnose double logging as "two console handlers" when those handlers have mutually-exclusive `require_debug_true/false` filters.
**Agent**: django-drf-reviewer

---

## Tooling / Agents (2026-06-06 additions)

### [2026-06-06] A path-filtered workflow cannot be a required status check — it deadlocks unrelated PRs

**Mistake**: `mobile-ci.yml` (the Flutter `analyze`/`test`/build job) is path-filtered to `plant_community_mobile/**`, and is NOT in `main`'s required status checks — so a Flutter-only PR can merge with a failing `flutter test` (it's gated only by backend/web/harness checks). The obvious fix — "just add it to required checks" — is itself a trap: GitHub treats a required check with **no reported status** as pending forever, and a path-filtered workflow reports nothing on PRs whose diff doesn't match its `paths:`. So requiring it would permanently BLOCK every non-mobile PR (docs, backend, web). `harness-ci.yml:4-8` documents this exact trap and deliberately runs its required job on every PR (justified there because the harness tests are fast; Flutter's ~6.5 min run is not).
**Fix**: Tracked in todo 219. Recommended pattern: a lightweight **always-run gate job** (no path filter) that detects whether mobile files changed, conditionally runs/awaits the heavy Flutter job, and **always reports a status** — make the gate the required check. Avoids both the deadlock and paying Flutter CI cost on every PR.
**Rule**: A required status check MUST report a status on 100% of PRs to `main`. Never mark a path-filtered (`on.pull_request.paths:`) workflow as required — gate via an always-run job that emits success for out-of-scope PRs instead.

### [2026-06-06] Squash-merged branches are invisible to `git branch -d` and pile up; detect via PR state, not diffs

**Mistake**: A local branch list had grown to 37, ~92% of which were dead. Squash-merging a PR collapses the branch's commits into one new commit on `main` with a different SHA, so `git branch -d` (and `git branch --merged`) never recognize the original branch as merged — it lingers indefinitely. Worse, `git diff main..<branch>` is actively misleading for a branch that's many commits behind `main`: the diff is dominated by `main`'s *newer* work appearing as "deletions," which reads as huge unmerged value when the branch is actually superseded (one branch showed −1722 lines but its PR was already merged).
**Fix**: Detect superseded branches by **PR state + landed artifacts**, not by diffing: `gh pr list --state all --head <branch>` (merged/closed?), and confirm the deliverables (e.g. archived todos, the squash commit) are in `main`. For squash detection without a PR, collapse the branch to a single tree-commit on its merge-base and `git cherry main <commit>` (a `-` means patch-present in `main`). Pruned 37 → relevant branches this way.
**Rule**: Don't trust `git branch -d`/`--merged` or 2-dot diffs to decide if a branch is safe to delete in a squash-merge repo. Confirm the PR merged/closed and its content landed in `main`, then `git branch -D`. Periodically prune, or enable auto-delete-on-merge, so squash debris doesn't accumulate.

---

## Audit method (2026-06-09 maintainability audit)

### [2026-06-09] Dead-code deletion: tests cannot catch under-deletion — re-sweep references instead

**Mistake**: When removing dead code, the instinct is "delete it, run the suite, green = safe." But dead code has *no test exercising it* — so leaving a freshly-orphaned helper behind (e.g. deleting a method whose only callee `_get_next_step`/`log_trust_level_upgrade`/`_get_project_for_location` is now unreferenced) never moves a single test. "Suite green" is structurally blind to under-deletion. The symmetric trap is over-deletion: a model method referenced only by **string** (a serializer `fields=[...]`/`source=`, a Wagtail panel, a template, a URL route, settings) won't be caught by a `--glob '*.py'` grep, and the test that would catch it is often the untested path.

**Fix**: Three-part discipline, used across this 24-file / −4,317-line deletion with zero regressions: (1) **before** deleting a model method, grep the WHOLE repo with no `.py` filter to catch string references; (2) follow transitive-deadness chains to closure — after removing a parent, re-grep each callee and delete it only if now at zero refs, stopping at the first still-referenced symbol (kept `_trigger_security_alert`, which had live callers); (3) **after** all deletions, re-sweep every deleted symbol across the tree to prove zero residual references, and run `pyflakes` on touched files to catch newly-orphaned imports (`Group`, `post_save` were removed this way). Tests are the backstop, not the primary instrument.

**Rule**: Dead-code removal is verified by reference re-sweep (whole-repo, non-`.py`) + orphaned-import check, NOT by a green suite. Follow transitive chains to closure in the same commit. Before deleting a model method, grep without the `.py` filter (string refs in serializers/panels/templates/URLs).

### [2026-06-09] "Built but unwired" ≠ "dead code" — surface coherent unused features, don't auto-delete

**Mistake**: A maintainability sweep flags zero-reference code as "dead." But some zero-reference code is a *coherent, tested feature built ahead of its UI* (a Flutter `FirestoreService` offline-sync layer + tests with no screen consuming it; a 199-line type-safe nav helper layer prod bypasses) or a *tested security utility that arguably should be wired up* (`validation.ts` `validateFileType`/`sanitizeSearchQuery` — unused, but their absence at the upload widget / search box is a latent gap, not a reason to delete). Blind-deleting these removes intended-roadmap work or forecloses closing a real gap.

**Fix**: Split "dead code" into (a) **superseded/orphaned** (a live replacement exists, or it's truly incoherent) → safe delete, and (b) **coherent-but-unwired feature** → surface to the human for a delete-vs-wire decision before touching it. In this audit, the nav helpers were deleted after user approval; the tested security validators + a drifted PlantNet parser were *deferred* for a wire-or-remove decision. The offline-sync `FirestoreService` was deleted **with** triage approval — then **restored** post-PR when the owner clarified offline persistence is a roadmap priority. Lesson reinforced: even an approved deletion of a coherent feature can be the wrong call until the owner confirms it's not roadmap; prefer *deferring* coherent-but-unwired features over deleting, and make the reversal cheap (it was one `git checkout main -- <files>`).

**Rule**: Zero references is necessary but not sufficient for deletion. If the code is a coherent, tested feature (or a security utility that plausibly *should* be called), surface it for a human delete-vs-wire decision — and prefer deferring over deleting, since "unwired" often means "roadmap," not "dead."

### [2026-06-09] Hollow tests give false green on security paths — empty `pass`, tautologies, and dev-gated branches

**Mistake**: Three recurring shapes of a test that *cannot fail*, all found this audit (6 instances): (1) an empty body that loops to a side effect then `pass` ("optional" header check on a 429 — named for the RFC `Retry-After` gotcha, asserted nothing); (2) a tautology that re-declares the value it checks (`const TIMEOUT = 30000; expect(TIMEOUT).toBe(30000)` instead of reading `httpClient.defaults.timeout`); (3) a test for production-only behavior that never enters the production branch (Sentry calls gated behind `import.meta.env.DEV === false`, so the test only asserted the mock `toBeDefined()`).

**Fix**: (1) assert the real effect (`status == 429` AND `int(response["Retry-After"]) > 0`); (2) import the real subject and assert *its* config; (3) force the gated branch with `vi.stubEnv('DEV', false)` and assert the real call (`Sentry.captureMessage`) plus that the dev path was NOT taken (`consoleSpy.log` not called). Empty stubs for unimplemented behavior were deleted, not faked.

**Rule**: A test named for behavior X must assert X and fail if X regresses — never `pass`, never assert a locally-declared literal, never assert only that a mock exists. For env/dev-gated code, stub the env to enter the real branch (`vi.stubEnv`). An empty placeholder test for an unbuilt feature is noise — delete it (or build the feature + test together), don't leave a green stub.
**Agent**: test-quality-reviewer

### [2026-06-09] Editing a `@riverpod` source without regenerating fails CI's codegen gate — `flutter analyze`/`test` won't catch it

**Mistake**: During PR #364 (the maintainability audit) I deleted the unused `getJWT()` method from `auth_service.dart`. `AuthService` is a `@riverpod` Notifier, and Riverpod's generated `auth_service.g.dart` embeds a **source-content hash** (`_$authServiceHash = r'5a072f4f…'`). Deleting *any* code from the source changes that hash, but I never ran `build_runner`, so the committed `.g.dart` carried the stale hash. Local `flutter analyze` (clean) and `flutter test` (165 pass) both passed — they don't regenerate — so the gap was invisible until the CI job's `Ensure generated code is committed` step (`build_runner build` + `git diff --exit-code -- lib test`) failed the PR. This recurred a previously-noted gotcha; it had not been codified into `docs/rules/flutter.md`, so the inject hook never warned at write-time.

**Fix**: `cd plant_community_mobile && flutter pub run build_runner build --delete-conflicting-outputs`, then commit the updated `.g.dart` (only the hash line changed). Codified as a binding rule in `docs/rules/flutter.md` + a JIT trigger (`flutter-codegen-regen`) so editing any `@riverpod`/`@freezed`/`part '*.g.dart'` source now warns at write-time.

**Rule**: After editing ANY codegen-backed Dart source (`@riverpod`, `@freezed`, or one with `part '*.g.dart'`), regenerate with `build_runner` and commit the `.g.dart` in the same change. Local analyze/test cannot detect a stale `.g.dart`; CI's codegen gate will block the merge.
**Agent**: flutter-dart-reviewer

## Security sweep (2026-06-10 additions)

### [2026-06-10] A data migration that `call_command()`s a seed command minted a superuser with a hardcoded password on every deploy

**Mistake**: Blog migration `0004_auto_20250819_1922` used `RunPython` → `call_command("migrate_care_guides_to_blog")`. That command, when the author user was missing, silently created superuser `plant_care_admin` / `temp_password_change_immediately`. Because Railway's start command runs `manage.py migrate --noinput` on **every deploy**, this was a standing account-creation path in production for ~10 months — gated only by the accident that prod had zero `PlantCareGuide` rows (the command early-returns at count 0). Three more known-credential creators shipped alongside: `create_sample_blog_posts.py` (superuser `admin`/`admin123`), `create_test_user` (`e2e@test.com`, known password), `create_demo_blog_posts` (staff `plant_blogger`, known password) — all runnable in prod with one `railway run`. A second trap: `migrations/RunPython` calling a management command executes the command's *current* code on every fresh `migrate` (CI test DBs, new environments), not a snapshot of what it did in Aug 2025.

**Fix**: Migration 0004 forward is now a documented no-op (its destructive reverse — deleting blog posts — became `RunPython.noop` too); the command raises `CommandError` instead of creating an author; all three seed commands are DEBUG-gated; demo author gets `set_unusable_password()`; `create_sample_blog_posts.py` and a stray git-tracked `web/backend/` duplicate were deleted. Regression tests assert each guard AND that the dangerous accounts are never created. Verified prod via `railway ssh` shell query: 1 user total, none of the suspect accounts.

**Rule**: Never create accounts or set passwords in a migration or any deploy-time path. Data migrations never `call_command()` — inline with `apps.get_model()`, and no-op them once served. Seed/demo/E2E commands must raise `CommandError` when `settings.DEBUG` is False.
**Agent**: security-reviewer

## Forum audit (2026-06-10 additions)

### [2026-06-10] An unsendered `@receiver(post_delete)` silently disabled Django fast-delete for the whole project

**Mistake**: The forum audit's own Round-1 fix wired counter reconciliation with `@receiver(post_delete)` and an `isinstance()` check inside the handler. Without `sender=`, the receiver registers for EVERY model — `Collector.can_fast_delete()` consults `post_delete.has_listeners(model)` and starts returning False project-wide, so every bulk/cascade delete (sessions, revisions, JWT blacklist, anything) fetches rows into memory and deletes one-by-one with per-instance signal dispatch. No forum test could catch it; only the Phase-6 orchestrated review of the fix diff did.

**Fix**: Two receivers with lazy string senders (`sender="wagtail_forum.Topic"` / `"wagtail_forum.Post"`), plus a thread-local pre_delete marker so a topic's cascade doesn't recount the board once per deleted post.

**Rule**: Model-signal receivers always pass `sender=`; `isinstance()` filtering inside the handler does not undo the registration-time damage.
**Agent**: django-drf-reviewer

### [2026-06-10] "Deferred to the next plan" work silently evaporated between plans (forum rate limiting)

**Mistake**: The forum design spec required `django-ratelimit → 429` throttling. Plan 1C explicitly deferred it to Plan 1D ("host-level throttling configured there"); Plan 1D never mentioned throttling. Result: the forum shipped to production with zero rate limiting on any endpoint, combined with automatic trust promotion at 5 posts → unlimited unscreened autopublish. Found only by a 4-agent-convergent audit finding.

**Fix**: Host-side throttled view wrappers (`forum_host/api.py`/`api_urls.py`) with a route-parity test so new package endpoints can't ship unmounted; rates runtime-resolvable via `FORUM_RATELIMITS`.

**Rule**: When plan N defers an item to plan N+1, the deferral is not done until plan N+1's task list contains it — verify the handoff landed, in the same review that approves plan N+1.
**Agent**: (process — audit Phase 1 checks plan-deferral handoffs)

### [2026-06-10] StreamField API writes: `to_python()` neither rejects unknown blocks nor type-checks values

**Mistake**: The API's body validation relied on a `to_python()` dry-run to reject malformed StreamField JSON. Execution-proven gaps: unknown block types are silently DROPPED (client content vanishes with a 201), an int `paragraph` value passes and then 500s in `nh3.clean()` (TypeError), an int `heading` persists silently, and ChooserBlock PKs are stored unresolved (nonexistent or restricted-collection IDs accepted). A test named `test_body_block_rejects_unknown_block_type` asserted only block configuration, masking the gap.

**Fix**: Explicit pre-checks in `validate_forum_body`: unknown type → 400, str (or dict-of-str for StructBlock) value enforcement → 400, chooser blocks rejected on the API path until an upload story exists.

**Rule**: Never treat `StreamBlock.to_python()` as validation for API-submitted bodies; validate type-membership and value types yourself.
**Agent**: wagtail-reviewer

## Forum Spec 2 Phase 1 (2026-06-21 additions)

### [2026-06-21] Wagtail DB search rejects relation-field filters without `index.RelatedFields`

**Mistake**: Extending forum search to post bodies required visibility-filtering the searched queryset (`Post.objects.filter(live=True, topic__live=True, topic__board__in=_visible_boards())`). The Wagtail database search backend raised `FilterFieldError: Cannot filter search results with field "board_id"` at query-compile — `Post.search_fields` only declared `FilterField("live")`, so the related `topic__live`/`topic__board_id` filters were undeclared. The plan's listed files didn't include the model, so the task got BLOCKED mid-implementation.

**Fix**: Added `index.RelatedFields("topic", [index.FilterField("live"), index.FilterField("board_id")])` to `Post.search_fields`. No migration/reindex (`search_fields` is not schema on the DB backend). Dropping the filters to silence the error would have leaked hidden-board / draft-topic posts into search — the wrong fix.

**Rule**: To filter a Wagtail search queryset on a related model's field, declare `index.RelatedFields(rel, [FilterField(...)])` on the searched model — never drop the filter to silence `FilterFieldError`.
**Agent**: wagtail-reviewer

### [2026-06-21] A response-shape rename broke security tests in a file the diff never touched

**Mistake**: Forum search changed from `{"results": [...]}` (topics only) to `{"topics": [...], "posts": [...]}`. The task updated the assertions in `test_search_sync.py`, and BOTH the per-task review and the independent kimi-review (both diff-scoped) passed clean. But two pre-existing SECURITY visibility tests in `test_visibility.py` — not in the diff — still asserted `resp.data["results"]` and `KeyError`'d. Only the whole-app suite run (final verification) caught it. The negative post-search assertions were also vacuous (the hidden content's body never contained the search term, so `posts == []` passed without exercising the visibility filter).

**Fix**: Updated the two tests to the new shape AND strengthened them to assert exclusion from both `topics` and `posts`, with the search term present in the hidden content's post body so the filter is genuinely exercised.

**Rule**: A response-key rename is a cross-file contract change — grep the WHOLE suite for old-shape consumers and run the full app suite, not just touched files. Diff-scoped review (human or kimi) structurally cannot see out-of-diff consumers.
**Agent**: (process — full-suite run before "done")

## Dependency security bumps (todo 235, 2026-06-22)

### [2026-06-22] `pytest --reuse-db` against a foreign/partial test DB → 81 phantom failures

**Mistake**: Verifying the 235 dependency bumps, ran the forum backend tests with `pytest --reuse-db` against a test DB an earlier run had built for a *different* app subset (users+blog). 81 of 114 forum tests "failed" — workflow routing, bootstrap, ratelimits, seed, signals — and the failures looked like they could be the bumps. The reused DB simply lacked the forum app's migrations + `post_migrate` bootstrap (default workflow/board/permissions). Earlier, `manage.py test apps.forum_host wagtail_forum` had reported "Ran 0 tests" (a false pass) because the project runs tests via pytest, not the Django test runner.

**Fix**: Re-ran with `pytest --create-db` (fresh DB applies all migrations + post_migrate) → 114 passed. The bumps were innocent; the full suite then ran 774 passed / 8 skipped.

**Rule**: Backend tests run via **pytest** (`pytest.ini`), not `manage.py test`. When running a different/wider app subset than the cached test DB was built for, use `pytest --create-db` before attributing failures to the diff — `--reuse-db` against a foreign or partial test DB yields phantom failures. (Echoes the "small verification batches" lesson: nearly mis-attributed 81 fake failures.)
**Agent**: (process — test-running gotcha; not diff-reviewable)

### [2026-06-22] pip-audit's empty "Fix Versions" column does NOT mean unfixable

**Mistake**: todo 235 planned to add a justified pip-audit `--ignore-vuln` for `bleach GHSA-g75f-g53v-794x` because the baseline scan showed an empty "Fix Versions" column ("no fix yet"). Treating empty-fix as unfixable would have added a needless permanent suppression to `security-scan.yml`.

**Fix**: Bumped `bleach` 6.3.0→6.4.0 anyway; pip-audit then reported the advisory gone — 6.4.0 is outside its affected range (pip-audit just hadn't populated a fixed-version for that advisory). No suppression added; the existing 6-entry ignore set stayed unchanged.

**Rule**: Before adding a pip-audit `--ignore-vuln` line for a "no fix listed" advisory, try bumping the package — the empty "Fix Versions" column ≠ unfixable. Suppress only when no bump clears it, with a dated one-line justification. Run `npm audit fix` WITHOUT `--force` (force pulls breaking majors).
**Agent**: security-reviewer

## OAuth verified-email invariant (PR #400, 2026-06-24)

### [2026-06-24] A cross-provider security invariant is shared *policy*, not shared *code* — don't consolidate the guards

**Context**: Review finding #2 flagged the "trust only a provider-verified email" rule as scattered across four auth paths (Google web, GitHub web, allauth, Firebase mobile) and prescribed the usual altitude fix: "generalize the mechanism instead of repeating special cases." Applied literally, that would mean one `email_verified(...)` helper the four paths call.

**Why that was the wrong altitude**: the four guards are not the same predicate over a shared shape. They read verification from genuinely different structures — a Google profile dict (`verified_email`/`email_verified`), a GitHub emails list (`primary AND verified`), allauth `EmailAddress` rows (`.verified`), a Firebase JWT claim (`email_verified` + a trusted-provider allowlist) — and enforce failure four different ways (strip email / set-if-verified / raise `ImmediateHttpResponse` / 403+`ValueError`). There is no shared chokepoint to push a gate down to (web → `_find_or_create_user`, Firebase → `get_or_create_user_from_firebase`, different modules). A single provider-switch helper would have *been* the special-cases-on-shared-infra smell, and would have misrepresented each provider's signal (e.g. implying Firebase honors `verified_email`, which it never sends).

**Fix**: single-source the **policy**, not the code. Wrote the canonical rule once in `backend/docs/patterns/security/authentication.md` ("Trust only provider-verified emails": invariant + fail-closed rationale + per-provider table) and had each enforcement site cite it with a one-line comment. Policy at one altitude; per-provider mechanisms stay local.

**Hidden contract worth pinning** (surfaced as a review WARNING — not a bug, but a real fragile coupling): the Google-web guard enforces the invariant by *stripping* `email` from the profile, which only fails closed because `_find_or_create_user` treats a missing email as a hard stop (`email = user_data.get("email"); if not email: return None`). If a future edit adds an email fallback there, the strip-based guard silently breaks. Pinned by `test_stripped_email_does_not_match_existing_account`.

**Rule**: When the same security rule appears across N integrations that read it from different shapes and enforce it differently, single-source the *policy* in the pattern library and cross-reference each guard — don't force a shared helper. A "strip the input → downstream fails closed" guard depends on the downstream hard-stopping on the missing input; assert that coupling in a test.
**Agent**: security-reviewer

### [2026-06-24] detect-secrets baseline churn → commit-abort loop when a doc edit shifts a baselined example token

**Mistake**: Editing `authentication.md` (which contains example tokens already recorded in `.secrets.baseline`) shifted those tokens' line numbers. The `detect-secrets` pre-commit hook rewrites `.secrets.baseline` in place on every run — updating both the moved `line_number`s and a fresh `generated_at` timestamp. That rewrite is an unstaged change *created during the commit*, so pre-commit's stash-then-restore conflicts with the hook's edits and aborts the commit. Re-staging just re-triggers the rewrite: a loop. (markdownlint's whole-file blank-line normalization compounded it by shifting lines again.)

**Fix**: Stage the hook-regenerated baseline, confirm the diff is **only** `line_number`/`generated_at` churn with no new `hashed_secret` block (i.e. no actual new secret — the scan had already passed clean on prior attempts), then commit once with `SKIP=detect-secrets` so the hook doesn't re-timestamp the baseline mid-write.

**Rule**: When a docs/pattern edit moves a line that holds an example token already in `.secrets.baseline`, expect the detect-secrets hook to churn the baseline and loop the commit. Break it by staging the regenerated baseline, verifying the diff is purely `line_number`/`generated_at` (grep for any added `hashed_secret`), and committing with `SKIP=detect-secrets` for that one write. Never `SKIP` it without first confirming no new secret block was added.
**Agent**: (process — commit-hook gotcha; not diff-reviewable)

## Plant collection architecture (todo 237, 2026-06-24)

### [2026-06-24] Verify the write actually happens before building "reconcile two stores" work

**Context**: Todo 237 was filed to "reconcile the Firestore plant collection with the Django backend on reconnect," on the stated premise that an identified plant is written to **two** stores — the backend "during the identify API call" and Firestore — and the two can drift. Picking it up, the premise turned out to be false: `POST /api/v1/plant-identification/identify/` (`backend/apps/plant_identification/api/simple_views.py::identify_plant` → `CombinedPlantIdentificationService.identify_plant`) is **stateless**. It calls Plant.id/PlantNet and returns JSON; the `user=` arg threaded into the service is accepted but never used to `.create`/`.save` anything. No backend record is written on identify, so there is no second store to drift against and nothing to reconcile.

**The real architecture** (recorded so it isn't re-discovered): the plant collection is **bifurcated and intentionally separate**. Mobile writes only to **Firestore** (`camera_screen.dart::_persistPlantOffline` → `firestoreServiceProvider.savePlant`), read back by `CollectionScreen` via `plantsStreamProvider` (todo 224) — this is the mobile source of truth. The backend `UserPlant` collection is written **only by the web app** ("Save to My Collection" → `web/src/services/plantIdService.ts::saveToCollection` → `POST …/plant-identification/plants/`) and has **no read surface found in the current code** — no web "My Plants" list page, no GET of `…/plants/` in `web/src/`, and mobile never touches it. So it is effectively a write-only sink (tracked separately in todo 243). Cross-platform unification of the two collections is **not** a current goal; if it ever is, it's a multi-day epic, not a reconcile patch.

**Rule**: Before scoping work to "sync / reconcile store A with store B," confirm by reading the code that **both** writes actually occur. A `user`/owner argument passed into a service is not evidence of persistence — follow it to a concrete `.objects.create`/`.save`. And a write to a store **no client reads back** is a dead-end to remove, not a store to keep in sync. Here, both checks killed the premise: the backend "write" never happened, and the one backend collection that does get written has no reader.
**Agent**: (process — premise-validation; surfaced via advisor + owner decision)

## Forum Spec 2 — inline images (todo 231 PR-3, 2026-06-25)

### [2026-06-25] Iterating a Wagtail StreamValue is a hidden per-post N+1 for ChooserBlocks

**Mistake**: A forum post-body serializer resolved image blocks to renditions by looping `for bound in stream_value` and reading each block. The post-list endpoint's exact `assertNumQueries` pin still passed for text-only posts, so it looked fine — but with image blocks the query count grew with the number of posts (N=1 → 6 queries, N=4 → 9). A batched `Image.objects.filter(id__in=…).prefetch_renditions(...)` up front did NOT prevent it.

**Root cause**: `StreamValue.__getitem__` (hit by iteration) calls `_prefetch_blocks(type)`, which calls `child_block.bulk_to_python(...)`; for an `ImageChooserBlock` that is `Image.objects.in_bulk(values)` — issued **once per post's StreamValue** (each post is a separate value), and it runs even if you never touch `bound.value`, purely from iterating. The image ids live inside the StreamField JSON, not a relation, so `prefetch_renditions` on the *post* queryset can't reach them and the prefetched map is bypassed by Wagtail's own lazy resolution.

**Fix**: Serialize from `stream_value.raw_data` (the unresolved JSON list), not the resolved StreamValue. Collect chooser ids from raw data, batch-fetch once into an `{id: obj}` map at the view level, pass it via serializer context, and read the map while iterating raw data — never `bound.value` for the chooser block. RichText raw value IS the stored HTML source, so `expand_db_html(raw["value"])` is equivalent to `bound.value.source`. Result: flat 5 queries, verified N=1 ≡ N=4. Diagnosed by wrapping the DB cursor to dump a stack on the offending `wagtailimages_image` query (the stack pointed straight at `_prefetch_blocks`).
**Agent**: performance-reviewer / wagtail-reviewer (codified as a check)

### [2026-06-25] kimi-review WARNINGs on the merged PR-3 backend (deferred, not blocking)

**Findings** (kimi-review, post-merge codify pass): (1) `get_forum_image_collection()` (`wagtail_forum/collections.py`) does query-then-`add_child`, not atomic — two truly-concurrent *first-ever* image uses could create two "Forum Images" collections, after which membership checks against `.first()` reject images uploaded into the other. One-time startup race only. (2) `validate_image_upload` sets PIL's global `PILImage.MAX_IMAGE_PIXELS` per request — technically not thread-safe, but benign here because every request sets it to the *same* constant (`get_setting("IMAGE_MAX_PIXELS")`), so concurrent writes can't vary it.

**Fix/decision**: Both are low-risk and were merged as-is. The clean fix for (1) is to create the collection at deploy time in `seed_default_forum` (single-threaded release step) so request-time get-or-create always finds it — filed as follow-up todo 247, not hot-patched. (2) is the canonical 4-layer pattern (`garden_calendar` does the same) and is benign because every caller assigns the *same* constant, so concurrent writes can't vary the threshold; left as-is. If a per-request limit is ever needed, drop the global and compare `width * height > limit` explicitly. Recorded so neither is "rediscovered" as a new bug.
**Agent**: security-reviewer / performance-reviewer

## OpenAPI schema endpoints publicly exposed (todo 248, 2026-06-27)

### [2026-06-27] drf-spectacular schema/docs/redoc were anonymous-readable in production

**Mistake**: `api/schema/`, `api/docs/`, and `api/redoc/` were registered in `urls.py` with no `permission_classes` and no `DEBUG` guard, so the full generated OpenAPI schema (every endpoint path, parameter, and the documented `jwtCookieAuth` security scheme) plus the interactive Swagger/Redoc UIs were reachable by anonymous users in prod. Pre-dated todo 238 (which only made it more visible by adding the auth scheme); split out and fixed in 248.

**Root cause**: drf-spectacular's `SpectacularAPIView`/`SpectacularSwaggerView`/`SpectacularRedocView` all default `permission_classes = spectacular_settings.SERVE_PERMISSIONS`, whose package default is `['rest_framework.permissions.AllowAny']`. `SERVE_INCLUDE_SCHEMA=False` (which the project already set) does NOT add auth — it only stops the schema from listing its own path. So registering the views verbatim from the docs leaves them wide open.

**Fix**: Set `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]` — one knob gates all three views (and any future spectacular view), preferable to per-path `.as_view(permission_classes=…)`. Left `SERVE_AUTHENTICATION=None` so the project's `DEFAULT_AUTHENTICATION_CLASSES` apply. Also flipped `SWAGGER_UI_SETTINGS.persistAuthorization` to `False`. Verified live in prod after the Railway auto-deploy: anonymous `GET` now → 401 on all three (was 200). Two non-obvious test facts emerged: (a) `permission_classes` binds at **import time**, so `@override_settings(SPECTACULAR_SETTINGS=…)` can't exercise the gate — test the real configured behavior; (b) `IsAdminUser` returns **401** to anonymous (JWT authenticator supplies `WWW-Authenticate`) but **403** to an authenticated non-staff user.
**Agent**: security-reviewer (codified as a check + a write-time trigger)

## Cross-site OAuth state ride a session cookie blocked by SameSite=Strict (todo 242, 2026-06-27)

### [2026-06-27] Web Google sign-in's session-cookie OAuth `state` is silently dropped cross-site in prod

**Mistake**: The web Google-OAuth UI (todo 242) is correct front-end code — `GET
/api/auth/oauth/google/login/` with `credentials: 'include'`, then
`window.location.assign(oauth_url)` — but it will fail **every** prod login with
`?error=invalid_state` and **no client-side error**, because the backend stores
the OAuth `state` CSRF guard in `request.session`. The frontend
(`houseplant-md.com`) and backend (Railway) are different sites, so the
`sessionid` the login endpoint sets is a **third-party cookie**; with Django's prod
default `SESSION_COOKIE_SAMESITE = "Strict"` (settings.py:1010) the browser never
stores it, so it isn't present at the callback and `secrets.compare_digest(...)`
fails.

**Root cause**: SameSite=`Strict`/`Lax` suppresses a cookie on cross-site requests.
The OAuth-state handshake here is inherently cross-site (SPA origin ≠ API origin),
so the session cookie carrying `state` must be `SameSite=None; Secure` to be stored
and replayed. This is a separate knob from the JWT-cookie SameSite already
configured for authenticated API calls.

**Fix**: Set `SESSION_COOKIE_SAMESITE=None` (with `SESSION_COOKIE_SECURE=True`,
already `not DEBUG`) in Railway. **Necessary but maybe NOT sufficient**: Safari ITP
blocks third-party cookies outright and Chrome is deprecating them, so a cross-site
session-cookie OAuth handshake can fail even when SameSite is correct. The durable
fix is to stop relying on a third-party cookie for `state` — carry it in a signed
query param (e.g. `itsdangerous`/JWT round-tripped through the provider) instead.
Tracked as the prod-verification half under todo 240; the 242 UI ships
fail-closed (a missing/invalid session → readable error + link back to `/login`).
**Agent**: security-reviewer (deployment precondition; no code change in 242)

## Forum edit-moderation failure cluster (todo 250, 2026-07-03)

### [2026-07-03] `save_revision()` runs `full_clean()`, so a `null=True` FK without `blank=True` breaks re-saving a SET_NULL row

**Symptom**: A moderator editing an account-deleted author's forum post
(`Post.author` is `on_delete=SET_NULL`, so `author=None`) got
`ValidationError: {'author': ['This field cannot be blank.']}`, and the redaction
was silently lost (the view swallowed it into a fake 200 "pending").

**Root cause**: `RevisionMixin.save_revision()` calls `self.full_clean()`. A
`ForeignKey(null=True, on_delete=SET_NULL)` with `blank` unset defaults to
`blank=False`, so full_clean REJECTS the NULL that SET_NULL legitimately writes on
related-object deletion. The DB allows the NULL; the model's own validation does
not — an inconsistency that only surfaces when the row is re-saved through a
revision/full_clean path (create never hits it because author is always set).

**Fix**: Add `blank=True` to any `null=True` FK whose column is populated with NULL
by SET_NULL AND whose model is revisable (RevisionMixin) or otherwise re-saved via
full_clean. State-only migration (no SQL — `null=True` already exists).
**Agent**: wagtail-reviewer.

### [2026-07-03] Re-moderating an edit: the persistence + race + connection-poisoning contract

Three interacting hazards in one `submit_edit_for_moderation`-shaped path (save a
revision, then publish-or-screen it without taking approved content dark):

1. **Fake "pending"** — a blanket `except Exception -> "pending"` is only truthful
   when a row was persisted BEFORE the try (the create path saves the Post first).
   On an edit, a failure before/inside `save_revision` persists nothing, so
   reporting "pending" lies to the client. Fix: run `save_revision` OUTSIDE the try
   so a pre-persist failure propagates (an explicit error, not a fake success);
   wrap ONLY the publish/workflow step (there a revision exists, so "pending" is
   true).
2. **Connection poisoning** — catching a DB error INSIDE a `transaction.atomic()`
   block poisons the connection (`TransactionManagementError` on the next query).
   Put the `except` AROUND (outside) the `atomic()` so the savepoint has already
   rolled back and the connection is clean for the follow-up `refresh_from_db()`.
   Shape: `save_revision()` (autocommits) → `try: with atomic(): lock+publish` →
   `except: log` → refresh → report.
3. **Publish resurrects a deleted post** — `revision.publish()` unconditionally
   forces `live=True`, so a PATCH (edit) racing a soft-delete (`unpublish()`) can
   republish the just-deleted post. Fix: inside the narrow `atomic()`, take a
   `select_for_update()` row lock and RE-READ liveness; skip publish if the row is
   no longer live. The lock serializes the two writers; the re-read refuses to
   resurrect. Mutate the LOCKED instance (`locked.unpublish()`), never the earlier
   unlocked read whose fields may be stale (a repair the code review caught).

**Follow-up (PR #435 review)**: the `select_for_update().get(pk=…)` re-fetch could
raise `DoesNotExist` if the row is HARD-deleted (topic CASCADE, admin-only — no API
path hard-deletes) between the first fetch and the lock → previously a 500. **Fixed**
in PR #435: the helper lets `Post.DoesNotExist` propagate (not swallowed by the broad
`except`) and both `PostWriteView.patch`/`delete` map it to 404. Two edges remain
**deferred, low-severity → todo 256**: (a) `acting_as_moderator` is computed before
the `atomic()` (a permission revocation racing the request — a non-issue, request-time
perm state is standard); (b) the Post row lock is held while the counter signals write
Topic/Board/Profile, so a concurrent admin topic-hard-delete (Topic→Post) could
deadlock (PG auto-aborts one txn).
**Triaged 2026-07-04 (todo 256): both WON'T-FIX.** (a) Re-checking perm inside the
atomic does not close the window (revocation can land 1ns later) and the only effect of
a stale `True` is a moderator's account-deleted-author redaction going live — request-time
perm state is the standard contract, so no code change. (b) Re-confirmed the reachability
gate still holds — the ONLY `.delete()` in the forum API is on `Reaction`; Post/Topic are
soft-deleted via `unpublish()`, so the CASCADE deadlock is admin-only. PG's deadlock
detector aborts one txn (500 + retry → 404, never a hang or corruption); a retry/lock-order
mitigation is disproportionate complexity for a self-healing, admin-only, microsecond race.
**Agent**: django-drf-reviewer / wagtail-reviewer.

### [2026-07-03] Deleting a RevisionMixin row cascades its revisions, so a later `save_revision()` on the stale instance fails full_clean — not DoesNotExist

**Symptom**: Writing a test for the "row hard-deleted mid-edit" race, I deleted the
Post row up front then called `submit_edit_for_moderation(post, …)`, expecting the
`select_for_update().get()` to raise `Post.DoesNotExist`. Instead `save_revision()`
(which runs first) raised
`ValidationError: {'latest_revision': ['revision instance with id 1 is not a valid
choice.'], 'live_revision': [...]}`.

**Root cause**: `Post.objects.filter(pk=…).delete()` CASCADEs the model's
`revisions`/`workflow_states` GenericRelations, deleting the revision rows too. The
stale in-memory instance still carries `latest_revision_id`/`live_revision_id`
pointing at the now-deleted revision, and `save_revision()` → `full_clean()`
validates those FKs → rejects the dangling reference. The failure surfaces at
`save_revision`, before the lock re-fetch is ever reached.

**Fix / testing rule**: to simulate a row vanishing *mid-operation*, delete it AFTER
the operation's own `save_revision` (e.g. monkeypatch `save_revision` to run the
real one then delete the row), not before — otherwise you test a different failure
(full_clean on a dangling revision FK) than the one you intend (the lock re-fetch's
`DoesNotExist`). **Agent**: wagtail-reviewer.

## Railway Dockerfile-builder migration (todo 241, 2026-07-01)

### [2026-07-01] Nixpacks baked secrets into image layers; the DOCKERFILE rebuild took four prod-only fixes to go live

**Mistake**: The legacy `NIXPACKS` builder generates a Dockerfile with `ARG`+`ENV`
lines for EVERY service variable, so all 9 secret-named vars (SECRET_KEY, API
keys, …) were baked into image layers (BuildKit's `SecretsUsedInArgOrEnv` lint;
Railway docs confirm sealed variables still inject into Nixpacks builds).
Switching to a hand-written Dockerfile (zero `ARG`s; `COPY . .` before
`pip install` so the editable `wagtail_forum` package resolves) fixed the leak
but surfaced four failures observable ONLY in prod, each caught by a guarded
deploy:

1. **No healthcheck = blind traffic swap.** Railway marks a deploy SUCCESS when
   the container *starts*, not when it serves. `healthcheckPath` in
   `railway.json` makes Railway hold traffic until a 200 (old deploy keeps
   serving on timeout) — every later fix was diagnosed through it.
2. **`collectstatic` at container start**: on the `python:3.13-slim` runtime
   filesystem ~3 s/file × 262 files ≈ 13 min — ate the 300 s healthcheck window
   so gunicorn never started. Baked into the Docker build (build infra: ~1.5 s).
   It can't go in `preDeployCommand` either — that container's filesystem is
   separate from the serving one. (Same debugging confirmed Django 6 IGNORES the
   deprecated `STATICFILES_STORAGE` setting — removed in 5.1, superseded by
   `STORAGES` — so settings.py:388 is vestigial and collectstatic emits no
   manifest.)
3. **`$PORT` unexpanded**: a DOCKERFILE `startCommand` is exec'd with NO shell,
   so gunicorn received the literal string `$PORT`. Fix: wrap in `sh -c '…'`.
   (The Nixpacks-era command only worked because `collectstatic && gunicorn`
   forced a shell via `&&`.)
4. **Healthcheck host/scheme rejected**: Railway probes with
   `Host: healthcheck.railway.app` over plain HTTP → Django 400 `DisallowedHost`,
   then `SECURE_SSL_REDIRECT` 301'd the probe. settings.py now appends that host
   to `ALLOWED_HOSTS` and lists the health path in `SECURE_REDIRECT_EXEMPT`.

**Rule**: On Railway always set `healthcheckPath` (SUCCESS ≠ serving). Migrations
belong in `preDeployCommand` (failure = old deploy stays live); `collectstatic`
belongs in the image build (never the start path, never pre-deploy — separate
filesystem); `sh -c`-wrap any `startCommand` that references `$VARS`; keep
`healthcheck.railway.app` + the SSL-exempt health path in settings. Deploys
auto-trigger from `main` (no staging) — merging IS deploying. Operational detail:
`backend/docs/deployment/railway.md` + `backend/Dockerfile` header comments.
**Agent**: (process/deployment — codified in railway.md; no diff-reviewable signature)

## Worktree pytest imports the MAIN checkout via the editable install (audit 2026-07-11)

### [2026-07-11] "import file mismatch" / stale-code test runs inside git worktrees

**Mistake**: `wagtail_forum` is pip-installed editable; its `.pth` finder resolves
the package from the MAIN checkout's absolute path. Inside a worktree, bare
`pytest` therefore executes the MAIN checkout's package code — worktree edits are
invisible to the tests (or collection dies with "import file mismatch"). **Fix**:
prefix worktree runs with the repo-relative package dir, from `backend/`:
`PYTHONPATH=packages/wagtail_forum python -m pytest …` — `sys.path` (PathFinder)
precedes the appended editable finder, so the worktree copy wins. Verify with
`python -c "import wagtail_forum; print(wagtail_forum.__file__)"`.
**Agent**: (process/testing — no diff-reviewable signature; lives here + in the
audit manifest)

## Client ?ordering= overrode forum cursor ordering and 500'd unauthenticated (audit 2026-07-11 Phase 6)

### [2026-07-11] Host-global OrderingFilter reaches into reusable-package generics views

**Mistake**: the forum package's DRF generics views inherited the host's
`DEFAULT_FILTER_BACKENDS` (includes `OrderingFilter`).
`CursorPagination.get_ordering()` PREFERS an ordering filter when the view has
one, so a client `?ordering=-title` replaced the pinned-first cursor tuple —
silently defeating the same-day H5 fix — and `OrderingFilter` derives orderable
fields from the SERIALIZER, so `?ordering=author__get_username` (a dotted
`source`, not a DB column) compiled into `FieldError` → unauthenticated 500 on a
public endpoint. Surfaced by the wagtail reviewer's source analysis in Phase 6
review; escalated to HIGH after both halves reproduced empirically. **Fix**:
`filter_backends = []` on all 5 package generics views + regression tests
(ordering param inert; dotted source returns 200). **Rule**: `docs/rules/api.md`.
**Pattern**: `backend/docs/patterns/architecture/viewsets.md`. **Trigger**:
`drf-package-views-pin-filter-backends`.
**Agent**: django-drf-reviewer — package generics views must pin `filter_backends`.

## Django/DRF (2026-07-12 additions)

### [2026-07-12] `field__in={..., None}` silently matches nothing for the None member (todo 254 slice 5, audit L21)

**Mistake**: closing a cross-user image-reuse IDOR (audit L21) required an
`allowed_uploader_ids` set that legitimately includes `None` (an
account-deleted author's images grandfather in, since Wagtail's
`Image.uploaded_by_user` and `Post.author` both go `SET_NULL` together on
account deletion). The first implementation filtered directly with
`uploaded_by_user_id__in=allowed_uploader_ids`. A dedicated test for the
`None`-grandfather case failed: SQL's `IN (NULL)` evaluates to unknown, not
true, for ANY row — including one whose value actually is `NULL`. Django's
ORM passes `None` through to the `IN (...)` list literally; it does not
special-case it the way `field=None` (which Django DOES rewrite to
`IS NULL`) does.
**Fix**: split the set — `Q(field__in=non_null_values) | Q(field__isnull=True)`,
OR'd in only when `None` is actually a member. See
`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py::validate_forum_body`.
**Rule**: `docs/rules/database.md`. **Pattern**:
`backend/docs/patterns/domain/forum.md` → "Image blocks are scoped to an
allowed-uploader set".
**Agent**: django-drf-reviewer — flag `__in=` filters where the RHS set/list
may contain `None`.

## Tooling / Agents (2026-07-12 additions)

### [2026-07-12] Edit-time import strip recurs when an import lands before its first usage

**Mistake**: added `from django.db.models import Q` to `sanitize.py` in one
Edit call, then used `Q(...)` in a *later* Edit call. The PostToolUse
formatter hook runs between edits and reformats/lints the file as it stands
at that moment — with no usage yet, it silently removed the "unused" import.
The next edit then referenced `Q` without it being defined, surfacing as
`NameError: name 'Q' is not defined` only when tests ran. This is the same
class of bug already logged for Dart/Flutter (`project_dart_edittime_import_
strip` memory, hit 2026-06-23) — confirmed here to also apply on the Python
side within a single session, not just across sessions.
**Fix**: re-added the import in the SAME Edit call as its first usage; the
formatter had nothing to strip once the usage was already present.
**Rule**: added to `docs/rules/_discipline.md` (auto-injected before every
edit): add a new import in the same edit as its first usage, never a prior
one.
**Trigger**: none registered — the actual failure mode (an import added
ahead of a *future* edit that hasn't happened yet) has no textual signature
capturable from a single edit's diff; a trigger matching "any new import" on
every Python/Dart file would be pure noise. Left as prose in
`docs/rules/_discipline.md` + this entry.
**Agent**: (process — no diff-reviewable signature; same as the worktree
PYTHONPATH entry above).

## Security (2026-07-13 additions)

### [2026-07-13] `claude-code-security-review`'s own step outputs can't be trusted for a real merge-gate (todo 249)

**Mistake**: assumed, per the action's naming, that its `results-file` and
`findings-count` step outputs were live values a downstream gate step could
read directly. Reading the action's actual source at our pinned SHA
(`0c6a49f1fa56a1d472575da86a94dbc1edb78eda`, via `gh api
repos/anthropics/claude-code-security-review/contents/<path>?ref=<sha>`)
showed both are unreliable: `results-file` is hardcoded near the top of the
composite step to a literal relative-path string that is never updated to
reflect where the file actually lands relative to a downstream step's
`github.workspace`; and the script's own internally-computed HIGH-severity
exit code is captured into a shell variable
(`|| CLAUDECODE_EXIT_CODE=$?`) and only ever surfaced as an `::warning::`
annotation, never re-raised — so the job exits success regardless of
findings, by design.
**Fix**: read `${{ github.workspace }}/claudecode-results.json` directly —
the action unconditionally copies its results there regardless of outcome —
and parse `.findings[].severity` yourself via `jq`. Confirmed enum (from
`claudecode/prompts.py`'s REQUIRED OUTPUT FORMAT) is `HIGH|MEDIUM|LOW`
only; `CRITICAL` is never emitted despite some docs implying a 4-tier scale.
Implemented as a non-blocking (`continue-on-error: true`) observation step
in `.github/workflows/security-review.yml` — see the todo for why a true
blocking gate is still deferred.
**Rule**: `docs/rules/security.md`. Don't trust a third-party GitHub
Action's documented/named outputs without reading its actual source at the
exact pinned SHA in use — a name like `results-file` implies "the current
results file," not "a hardcoded stale string."
**Agent**: n/a — CI/workflow finding, not a reviewable application-code
pattern.

## Security (2026-07-14 additions)

### [2026-07-14] Promoting a soft-fail CI gate to blocking requires auditing every "can't verify" branch, not just the one that prompted the promotion (todo 249)

**Mistake**: when writing the original non-blocking severity-gate step
(2026-07-13 entry above), a missing `claudecode-results.json` was made to
fail closed (`exit 1`), but a results file present with no `findings` key —
e.g. an `{"error": ...}` shape from an errored scan — fell through the jq
filter's `.findings // []` default to an empty array and passed (`exit 0`).
That inconsistency was invisible while `continue-on-error: true` made the
whole step incapable of failing the job either way. It only became a real
bug the moment `continue-on-error` was removed to make the gate blocking —
a scan that errored out would now silently pass a required merge check.
**Fix**: added an explicit `jq -e 'has("findings")'` check before computing
severity, so both "file missing" and "file present but unverifiable" exit 1.
Caught during execution planning by a second reviewing pass, not by the
original implementation — a hint that "promote observer to blocking" diffs
need an explicit checklist item, not just a mechanical `continue-on-error`
deletion.
**Rule**: `docs/rules/security.md`. When promoting any soft-fail/observation
CI step to a real blocking gate, enumerate every branch that currently
exits 0 because "there's nothing to check" and re-verify each one fails
closed under the new blocking semantics — a soft-fail gate's fail-open
branches are invisible by construction (they can't fail the job either way),
so they never get exercised by whatever validated the original trip
condition.
**Trigger**: none registered — the failure mode is a structural/design
omission across an edit (removing `continue-on-error` from step X without
re-auditing step X's other exit-0 branches), not a single-fragment textual
signature `capture_trigger.py` can match.
**Agent**: n/a — CI/workflow finding, not a reviewable application-code
pattern (same limitation as the 2026-07-13 entry above).

### [2026-07-14] `PATCH .../branches/{branch}/protection` silently resets every unspecified field — use the narrow sub-resource endpoints instead (todo 249)

**Mistake**: nearly reached for a full `PATCH
repos/{owner}/{repo}/branches/{branch}/protection` to add a single new
required status check. GitHub's branch-protection PATCH endpoint is not a
merge-patch — omitted fields are treated as "set to their default/absent,"
not "leave unchanged." A naive PATCH carrying only the intended
`required_status_checks.contexts` change would have silently reset
`enforce_admins` to `false`, dropped `required_pull_request_reviews`, and
discarded the other pre-existing required contexts in the same call — a
security regression (admin-bypassable branch protection) delivered by the
very change meant to strengthen it.
**Fix**: used the narrow, additive sub-resource endpoint instead — `POST
.../branches/{branch}/protection/required_status_checks/contexts` with a
bare JSON array body (`["Claude Code Security Review"]`) — which only adds
to the existing `contexts` list and touches nothing else. Verified via a
`GET` immediately after that `enforce_admins`, `required_pull_request_reviews`,
`allow_force_pushes`, and `allow_deletions` all matched their pre-change
values.
**Rule**: `docs/rules/security.md`. Never `PATCH` GitHub's branch-protection
endpoint with a partial payload. Use the dedicated sub-resource endpoints
(`.../required_status_checks/contexts`, `.../required_pull_request_reviews`,
etc.) for additive/single-field changes, and always `GET` the full
protection object before AND after any protection change to diff the
before/after state.
**Trigger**: none registered — this is a Bash-invoked `gh api` action, not a
file edit; the write-time trigger system only observes Edit/Write tool
calls against repo files, so it has no mechanism to see this action at all.
**Agent**: n/a — a repo-settings action, not a reviewable diff (branch
protection isn't expressed as a file in the repository).

## Tooling / Agents (2026-07-14 additions)

### [2026-07-14] `git mv` of a file with unstaged edits stages the rename using the pre-edit content, not the current working tree

**Mistake**: edited a todo markdown file in place (frontmatter, acceptance
criteria, work log), then ran `git mv oldpath newpath` to archive it,
without an intervening `git add`. `git diff --cached --stat` immediately
after showed "1 file changed, 0 insertions(+), 0 deletions(-)" — a 100%
"similarity index" pure rename — even though the working-tree file at the
new path plainly had ~90 lines of new content (confirmed via `wc -l` and
`grep`). `git status` showed the rename staged AND the same file separately
listed as "modified" (unstaged): `git mv` had staged the rename using the
old path's last-committed/indexed content, while the actual edits sat
correctly on disk but uncaptured by the index.
**Fix**: `git add <newpath>` again after the `git mv`, which pulled the
current working-tree content into the index; `git diff --cached --stat`
then correctly showed the real diff (86 insertions, 11 deletions). Caught
only because the near-zero diff size looked implausible for the amount of
editing done — a smaller, more plausible-looking bare-rename could pass
unnoticed.
**Rule**: `docs/rules/_discipline.md`. Before committing a `git mv` of a
file you just edited, always re-`git add` the new path and re-check `git
diff --cached --stat` for a diff size that matches what you actually
changed. A rename that should carry real content changes but shows
0 insertions/deletions is the tell.
**Trigger**: none registered — a Bash-invoked `git mv`/`git add` sequence,
not a file edit; outside the write-time trigger system's reach (same
limitation as the branch-protection entry above).
**Agent**: n/a — process/tooling mechanic, not an application-code pattern.

## Forum notifications slice 1 (2026-07-14 additions)

### [2026-07-14] `transaction.on_commit()` registered unconditionally after a guarded write, delivering a side-effect even when the write silently failed

**Mistake**: an earlier code-review fix wrapped
`create_notifications(...)` in `apps/forum_host/notifications.py`'s
`reply_added` branch with `try: / with transaction.atomic(): ... / except
Exception: logger.exception(...)`, to scope a DB failure to a savepoint
instead of poisoning the ambient Wagtail publish transaction. But the
existing `transaction.on_commit(_enqueue_push)` call stayed positioned
AFTER that whole `try/except`, unconditionally — an `except` block only
stops the exception from propagating, it does not skip the code that
follows the `try/except` itself. So a DB error inside
`create_notifications()` was caught and logged correctly, but execution
still fell through to register the push-enqueue callback: a user could
receive an FCM push saying "X replied to your topic" with no
`Notification` row ever persisted for them to see in the bell. Four
domain-reviewer agents (django-drf, wagtail, react-typescript,
cross-cutting) all reviewed this file and missed it, because their pass
ran against the version of the file that had just introduced the
try/except — the bug is specifically about the try/except's *relationship*
to a nearby statement, not the try/except in isolation. It was caught by
`kimi-review`'s pre-commit gate on the first commit attempt for todo 253
slice 1.
**Fix**: moved `transaction.on_commit(_enqueue_push)` to be the last
statement INSIDE the `try` block, right after `create_notifications(...)`
succeeds, so a raised exception skips straight to `except` and never
reaches the registration. Added
`test_reply_added_skips_push_when_notification_write_fails`
(`apps/forum_host/tests/test_signals.py`), which mocks
`create_notifications` to raise and asserts `send_forum_push.delay` is
never called.
**Rule**: `docs/rules/forum.md` (one-line bullet) and
`backend/docs/patterns/architecture/services.md` (new pattern section,
"Gate `on_commit` Registration on the Preceding Write's Success").
**Trigger**: none registered — the buggy shape depends on whether the
`on_commit(...)` call sits at an indentation INSIDE the `try` block or
OUTSIDE it after the `except`, a distinction plain-text regex can't
reliably make (it isn't indentation-aware); a naive signature would false
positive on correctly-ordered code reformatted differently. Left as prose
in the rule, the pattern doc, and the reviewer checklist instead.
**Agent**: `.claude/agents/django-drf-reviewer.md` — added a checklist
item under "Forum notifications slice 1 additions (2026-07-14)" for this
exact code shape, so a future review checks whether the on_commit
registration sits inside or outside the guarded block.

## Forum notifications slice 4 (2026-07-14 additions)

### [2026-07-14] @mention resolution reused a spam-heuristics text walker, resolving invisible mentions from code blocks and link attributes

**Mistake**: the initial implementation of `resolve_mentioned_users()`
(`wagtail_forum/mentions.py`, todo 253 slice 4, H4) scanned a post's text
for `@username` tokens via `spam/base.py`'s `extract_text()` — a walker
built for spam heuristics, which need to see a post's links and code AS
WRITTEN (raw HTML, unstripped) to detect spam patterns like link floods.
Mention scanning has the opposite requirement: only text a *reader* can
see should be able to trigger a mention. Reusing the spam walker meant (1)
a code block's raw source (e.g. a Python `@property` decorator) resolved
as a mention nobody could see as one, and (2) an `<a href="…/@victim"
title="@victim">` tag's *attribute* text resolved as a mention — both
attributes survive the write-path sanitizer's `nh3` allowlist
(`api/sanitize.py` permits `href`/`title` on `<a>`), even though only the
link's visible label ("click here") is ever rendered. Neither leak was
caught by the initial test suite (all fixtures used plain paragraph text);
both were found and reproduced during code review (Altitude angle for the
code-block leak, Angle A for the href leak), then independently confirmed
by directly constructing a real saved Post and calling `.findall()` on
the extracted text.
**Fix**: wrote a dedicated `_mention_scan_text()` in `mentions.py`,
walking `post.body.raw_data` and calling `django.utils.html.strip_tags()`
on string block values (paragraph HTML) — `strip_tags()` drops attribute
VALUES along with the tag markup that carries them, since they were never
a text node, only tag syntax (verified:
`strip_tags('<a href="x/@victim" title="@evil">click</a>')` returns
`'click'`, no attributes survive; a real link label like
`'<a href="…">@alice</a>'` still yields `'@alice'` — no false negative).
Code/image blocks (dict/int values) are skipped entirely — not prose a
mention could plausibly appear in. `spam/base.py`'s `extract_text()` was
left untouched — it correctly needs the raw values for its own purpose;
the two consumers' requirements are genuinely different, not a
duplication to consolidate.
**Rule**: `backend/docs/patterns/security/input-validation.md` → new
Pitfall 7, "Reusing a Rendering-Oriented HTML Walker for a Second,
Security-Sensitive Parser".
**Trigger**: none registered — the bug is an *omission* (missing
`strip_tags()`/block-type filtering in a new text-extraction function),
not a matchable bad-code-shape; a regex trigger broad enough to catch a
missing safeguard would false-positive on `extract_text()` itself
(which deliberately doesn't strip tags, for a different, valid reason).
Left as prose in the pattern doc.
**Agent**: n/a — no existing reviewer checklist item fits this specific
StreamField-block-type nuance narrowly enough to add without overfitting
to this one case; the Altitude/Angle-A angles that caught it are already
part of the bundled `/code-review` skill's general-purpose finder set.

### [2026-07-14] Documented SQL-wildcard-escaping convention was actively wrong for Django's own auto-escaping lookups

**Mistake**: `backend/CLAUDE.md`, `docs/rules/security.md`, and
`backend/docs/patterns/security/input-validation.md` all documented
"escape `%`/`_` with `escape_search_query()` before any `icontains` filter"
as the correct, required pattern — copied into a new `user_search.py`
view (todo 253 slice 4, H4) during initial implementation, following the
documented convention exactly. The view's own test
(`test_search_escapes_sql_wildcards`) failed:
`assert set() == {'dave_1'}` — searching for the literal username prefix
`"dave_"` matched nothing. Root cause, found via `manage.py shell` `.query`
introspection: Django's `PatternLookup.process_rhs()` (the shared base for
`contains`/`icontains`/`startswith`/`istartswith`/`endswith`/`iendswith`)
already calls `prep_for_like_query()` on the raw filter value, auto-escaping
`%`/`_`/`\` — confirmed this project's PostgreSQL backend does not override
it. `escape_search_query("dave_")` produces `"dave\_"`; the ORM then
auto-escapes THAT again into a pattern requiring a literal backslash in the
matched text, which the real value `"dave_1"` doesn't have — zero matches,
silently, no error. This is not new/version-specific behavior worth
hedging on — it's `PatternLookup`'s literal implementation, applicable
everywhere it's the lookup type in this codebase (confirmed at least 8
other production call sites follow the same now-known-wrong pattern:
`apps/blog/{admin_views,api_views,views}.py`,
`apps/blog/api/viewsets.py`, `apps/plant_identification/views.py`,
`apps/plant_identification/api/endpoints.py` — NOT audited/fixed as part
of this slice; flagged for a follow-up todo).
**Fix**: removed the manual escaping from `user_search.py`, filtering
directly with the raw (stripped) query. Corrected all three documentation
sources (CLAUDE.md convention line, the rules bullet, and the pattern doc
— including its "Pitfall 1"/"Pitfall 6" worked examples, which had
demonstrated the double-escaping pattern as the "✅ GOOD"/"✅ CORRECT"
answer) to state the verified behavior and reserve `escape_search_query()`
for lookups that bypass `PatternLookup` (raw SQL, `.extra()`, a custom
`Lookup`).
**Rule**: `docs/rules/security.md`, `backend/CLAUDE.md`,
`backend/docs/patterns/security/input-validation.md` (all corrected
2026-07-14 as part of this entry, not left for a future pass).
**Trigger**: `escape-search-query-before-orm-wildcard-lookup` (severity
`warn`) — fires on a new `escape_search_query(` call, prompting a check of
whether it's paired with an auto-escaping lookup before assuming it's needed.
**Agent**: n/a — a documented-convention correction, not a reviewer
checklist gap (the reviewers were following the same now-corrected
convention, not missing a check).

## Forum notifications slice 4 (2026-07-15 additions)

### [2026-07-14] A host-agnostic package can still break its contract via a User INSTANCE attribute, even with the FK type done right (todo 253 slice 4, "most significant single finding")

**Mistake**: `wagtail_forum/api/user_search.py`'s new `mention_user_search`
endpoint (todo 253 slice 4) read `u.display_name` on each matched user to
build the response payload. `display_name` is a property that exists only on
THIS host's custom User model — not part of Django's `AbstractBaseUser`/
`AbstractUser` contract — so the reusable `wagtail_forum` package would
break for any other host whose User model lacks it. The package's existing
convention (`settings.AUTH_USER_MODEL`, never a concrete user model) covers
the FK *type* but doesn't by itself prevent this: the FK was declared
correctly, and the bug was purely in which *attribute* got read off the
resolved instance.
**Fix**: replaced with `u.get_full_name() or u.get_username()` — both are
part of the base contract, so they work for any host's User model. Mirrors
the existing in-repo precedent, `PostAuthorSerializer.get_display_name`
(`wagtail_forum/api/serializers.py`), which this endpoint should have
matched from the start.
**Rule**: `docs/rules/forum.md` — new bullet distinguishing "FK type is
host-agnostic" from "instance attributes read off that FK must also be
host-agnostic," with the explicit caveat that a package-OWNED model (e.g.
`models/profiles.py`'s `Profile.display_name`) is a different, legitimate
case — the check is about the *User* instance specifically, not the string
"display_name."
**Agent**: `.claude/agents/wagtail-reviewer.md` — added under "Forum slice 4
additions (2026-07-15)": when reviewing `backend/packages/wagtail_forum/` (or
any host-agnostic package), check that `User` instance attribute reads use
only base-contract methods, not a host-specific property.

## Tooling / Agents (2026-07-15 additions)

### [2026-07-15] A blocking CI gate can silently stop verifying anything after a PR's first commit (todo 266, follow-up to todo 249)

**Mistake**: todo 249 promoted the Claude Code security-review severity gate
to blocking + fail-closed-on-unverifiable-results, without accounting for the
vendored `claude-code-security-review` action's own per-PR dedup cache: a
cache marker restored via a PR-scoped key prefix (not an exact commit SHA)
disables the actual scan on every push after a PR's first, by upstream design
(to save API cost). Once the gate went fail-closed, every commit after the
first hit a missing `claudecode-results.json` and failed the required check
unconditionally — merge blocked with no real finding behind it. Live-hit on
PR #462's second commit within a day of the promotion landing.
**Fix**: set `run-every-commit: true` on the action (`with:` block in
`.github/workflows/security-review.yml`), forcing a genuine scan on every
push instead of relying on the action's own cache-based dedup.
**Rule**: when promoting any advisory CI check to a blocking, fail-closed gate,
audit whether the underlying tool has its own internal dedup/caching that
skips real work on a subset of runs — a fail-closed gate turns a silent skip
into a hard, unconditional block. "The check ran" does not imply "the check's
actual work ran."
**Trigger**: none registered — a design-review question about a vendored
action's caching behavior, not a detectable code shape.
**Agent**: n/a — CI/workflow-config mechanic, not an application-code pattern.

## Repo Hygiene (2026-07-16 additions)

### [2026-07-16] A lowercase-only .gitignore rule can silently swallow a differently-cased TRACKED directory on macOS (case-insensitive filesystem)

**Mistake**: `.gitignore` had a `planning/` rule (per its "Development
planning and reference" comment block, apparently meant for some lowercase
scratch/reference directory — no such directory was ever found in git
history, unreachable/dangling commits, or the working tree). Because
macOS/APFS is case-insensitive by default and this repo has
`core.ignorecase=true`, the rule collaterally matched the actually-tracked
`PLANNING/` docs directory. It did not untrack the 23 files already
committed there (git doesn't retroactively untrack), but it silently
ignored any *new* file dropped into `PLANNING/` going forward —
`git status` / `git add .` never surfaced it. `PLANNING/20_FORUM_MOBILE_ROADMAP.md`
(473 lines) sat on disk with zero git history for an unknown period,
invisible to normal workflows, and would have been permanently deleted by
a `git clean -dfx` with no recovery path.
**Fix**: removed the `planning/` line from `.gitignore` and force-added
(`git add -f`) the orphaned file (PR #467). Verified no real lowercase
`planning/` target exists anywhere before deleting the rule outright rather
than "fixing" it by anchoring — anchoring (`/planning/`) would not have
helped, since the bug is case-insensitivity, not unanchored-path matching.
Code review of the recovered file then found 6 more issues baked into its
content: wrong file paths (`components/forum/` vs the real `pages/forum/`),
a wrong line number, a dead todo reference, and two feature sections (Phase
5.1 @mentions, 5.2 topic-watch) describing already-shipped work (todo 253
slices 3-4) as still unbuilt. A doc invisible to git for months never went
through normal review/update cycles — its concrete claims needed the same
live-repo verification as any other stale-doc recovery, not just the
mechanical git fix.
**Rule**: when adding a `.gitignore` rule, check it against existing tracked
directory names case-insensitively, not just case-sensitively — a rule that
looks scoped to an unrelated lowercase path can still hit a real, tracked,
differently-cased directory on any contributor's or CI's case-insensitive
filesystem (macOS default; also possible on Windows). Prefer deleting a rule
with no verifiable target over leaving it "just in case" — a dormant rule
that later collides with a newly-created tracked directory of similar name
is a worse failure mode (silent, delayed, easy to miss) than the small cost
of re-adding the rule if a real target ever appears.
**Trigger**: none registered — the failure mode depends on cross-referencing
live git-tracked directory names against `.gitignore` patterns
case-insensitively, which isn't expressible as a static regex over a new
edit fragment (no decorator/import/function-call signature to match).
**Agent**: n/a — general repo-hygiene/git-config gotcha, not an
application-code review checklist item; none of the existing review agents
are scoped to `.gitignore` correctness.
