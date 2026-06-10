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
