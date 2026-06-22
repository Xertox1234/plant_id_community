# Audit: Maintainability Audit (2026-06-09)

> **Date:** 2026-06-09
> **Trigger:** User-invoked `/audit maintainability` (all three stacks, discovery-first).
> **Domains (maintainability lens):** django-drf, wagtail, react-typescript, flutter, testing — cross-cutting maintainability (complexity, duplication, dead code, oversized modules/functions, inconsistent patterns, type-safety escapes, debt markers, coupling).
> **Baseline (static checks; full test-suite baselines deferred to fix phase per discovery-first mode):** backend `manage.py check` clean (0 issues, Redis-fallback config warning only) · web `tsc --noEmit` 0 errors / eslint clean (1 ignorable `coverage/block-navigation.js` warning) · flutter `analyze` clean (0 issues)

## Context

- This is a **maintainability-lens** audit. Prior audits ([2026-05-17](2026-05-17-full.md), [2026-06-02](2026-06-02-full-COMPLETED.md)) focused on security/performance/correctness bugs — dedup risk against them is low, but findings are cross-checked against their (mostly archived) deferred todos.
- Discovery-first: Phases 1–2.5 only. No worktree, no fixes, no PR until the user picks findings to fix.

### Quantitative signal (Phase 1 metrics)

**Largest backend modules (non-test, non-migration):** `plant_identification/models.py` 2815 · `garden_calendar/api/views.py` 1862 · `plant_identification/views.py` 1665 · `users/views.py` 1617 · `garden_calendar/models.py` 1357 · `users/models.py` 1350 · `blog/models.py` 1030.

**Longest backend functions:** `ai_care_service._create_enhanced_care_prompt` 231 · `plant_id_service.identify_plant` 190 · `garden_calendar upload_image` 180 · `views._generate_care_instructions` 174 · `plantnet_service.identify_plant` 171 · `core/exceptions.custom_exception_handler` 171 · `blog viewsets.get_queryset` 164 · `firebase_token_exchange` 155.

**Largest web modules:** `DiagnosisDetailPage.tsx` 669 · `StreamFieldEditor.tsx` 569 · `ReminderManager.tsx` 520 · `forum/SearchPage.tsx` 519 · `ImageUploadWidget.tsx` 508.

**Largest mobile modules:** `profile_screen.dart` 612 · `api_service.dart` 524 · `auth_service.dart` 450 · `firestore_service.dart` 349.

**Debt/escape markers:** backend 42 TODO/FIXME (mostly tests), 199 broad `except Exception`, 2 bare `except:` · web 14 TODO, 19 `as unknown`/`as any`, 10 `eslint-disable` · mobile 13 TODO, 46 `dynamic`, 1 `// ignore:`.

## Findings

Each finding has a lifecycle: `open` → `fixing` → `verified` or `deferred` or `false-positive`.

**Status key:** `open` · `fixing` · `verified` · `deferred` (link todo) · `false-positive`

**Research key** (Phase 2.5): `confirmed` · `better-fix` · `contradicted ⚠` · `—` (n/a)

> **Severity calibration:** maintainability is almost all Medium/Low. **High** is reserved for dead code that is dangerous-if-revived, duplication that has **already** diverged, or a test giving materially false confidence on a security path. Two agent-proposed Highs were **calibrated down to Medium** (M17 `route_transitions.dart` — dead but not-yet-divergent animation code; M20 anon-limits empty test — covers unimplemented behavior, hides no regression).
>
> **Research (Phase 2.5):** every finding is internal-code (dead code / duplication / naming / contract-vs-code) — none hinges on external library behavior, so all are `—` (not-applicable). No `docs-researcher`/Context7 calls were warranted; per the audit skill, a domain with zero library-dependent findings is skipped.

### Critical

_None._ (Critical is N/A for a maintainability lens.)

### High

| ID  | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | ------- | ------ | ----- | ------- | -------- | ------ | ------------ |
| H1 | **Dead `TrustLevelService`** (auth-adjacent, dangerous-if-revived). Zero external callers; only ref is the never-called `update_all_user_trust_levels`. Manipulates Django `Group` membership (a permissions primitive) and silently no-ops on missing groups. Reviving it to gate permissions wires auth onto unmaintained groups. Also uses `print()` not the bracketed logger. | django-drf | gp:users+garden | `apps/users/services.py:32-101` (+ dead `User.update_trust_level` `models.py:291`) | — | open | **ref-count verified** (only internal call at services.py:94) |
| H2 | **Dead 462-line frozen shadow** `_services_deprecated.py` — byte-identical copy of two **live** services (`PlantDataLookupService`, `BlockAutoPopulationService`). Module docstring does NOT say deprecated (only the filename prefix does). Future edits to the live `services/` copies won't propagate; grepping the class name can land a maintainer on the wrong copy. | wagtail | gp:blog+core | `apps/blog/_services_deprecated.py` (whole file) | — | open | **ref-count verified** (zero refs; live imports all point to `services/`) |
| H3 | **Dead 382-line `formatDate.ts`** (8 exports, zero app refs) while date formatting is reimplemented inline in 3 diagnosis files — and the copies have **already drifted** (`month:'short'` vs `'long'` vs relative-day logic). A maintainer edits the misleading "canonical" util that nothing uses, against 3 divergent truths. | react-typescript | gp:web | `web/src/utils/formatDate.ts`; `DiagnosisCard.tsx:37`; `DiagnosisDetailPage.tsx:50`; `ReminderManager.tsx:19` | — | open | **ref-count verified** (zero non-test imports) |
| H4 | **Empty rate-limit security test** — `test_rate_limit_response_includes_retry_after` has **no assertion** (loops to 429 then `pass # optional`). Names the RFC-compliance hazard from CLAUDE.md gotcha #4; a regression dropping `Retry-After` passes green. | testing | gp:testing | `apps/users/tests/test_rate_limiting.py:287` | — | open | **read-verified** (body is `pass`, no assert) |

### Medium

| ID  | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | ------- | ------ | ----- | ------- | -------- | ------ | ------------ |
| M1 | Dead PlantNet normalizers + **drift**: `normalize_plantnet_data` zero refs; `get_top_suggestions` test-only while the live path reimplements the parser inline — and the test-covered copy reads `family.scientificNameWithoutAuthor` vs the live copies' `family.scientificName`. A fix to the tested copy silently doesn't reach production. | django-drf | gp:plant_id | `services/plantnet_service.py:360,398,444`; `combined_identification_service.py:478-515` | — | open | **ref-count verified** (only archived-todo ref) |
| M2 | Dead `_create_care_prompt` (~109L, superseded by `_create_enhanced_care_prompt`); has diverged (lacks the `botanical_data` param) so can't even be swapped back in. Misleads maintainers into editing a stale OpenAI prompt schema. | django-drf | gp:plant_id | `services/ai_care_service.py:119-227` | — | open | agent-verified (zero refs) |
| M3 | Dead geo-routing feature `identify_with_location` + `_get_project_for_location` (zero refs); hardcodes 6 **overlapping** lat/long magic bounding boxes resolved by first-match → silent mis-routing if revived. Violates "no magic numbers". | django-drf | gp:plant_id | `services/plantnet_service.py:547-612` | — | open | **ref-count verified** (only archived-todo ref) |
| M4 | `get_images`/`get_image_thumbnails` duplicated across **4 serializers** and **drifted**: one copy returns relative URLs, three return absolute — and two of them serialize the _same model_ (`PlantIdentificationRequest`), so the same data is returned with inconsistent URL shape depending on endpoint. | django-drf | gp:plant_id | `serializers.py:108,180,444,672` | — | open | agent-verified |
| M5 | Dead method cluster in `users/models.py` (`complete_step`, `enable/disable_demo_mode`, `get_for_onboarding_step`, etc.) — `OnboardingProgress` carries two parallel progress schemes; the method-driven one is entirely dead while the boolean-field one is live. Changes to the dead "canonical" API silently no-op. | django-drf | gp:users+garden | `apps/users/models.py:349,1024,1095,1100,1105,1234,1246` | — | open | agent-verified (zero refs, checked serializers/admin) |
| M6 | Misleading OpenAPI schema: both `@extend_schema` say "Soft delete … is_active=False" but `destroy` hard-deletes (no `perform_destroy` override; `is_active` unused). drf-spectacular ships this false contract to client SDKs; doubled identical wrong text = copy-paste. | django-drf | gp:users+garden | `apps/garden_calendar/api/views.py:626,937` | — | open | agent-verified |
| M7 | Drifted signup side-effects across **3 account-creation paths**: default "My Plants" collection is created in `register` and OAuth `_find_or_create_user` but **absent** from the Firebase path; the 3 also use different username-collision strategies. No single definition of "what happens on signup". | django-drf | gp:users+garden | `apps/users/views.py:114`; `oauth_views.py:358`; `firebase_auth_views.py:256-400` | — | open | agent-verified |
| M8 | Unreachable `Ratelimited` branch + misleading comment: the handler returns at `:113`, so the `elif isinstance(exc, Ratelimited)` at `:179-183` can never run; the `:178` "check before PermissionDenied" comment implies that ordering is load-bearing (it isn't — the real guard is the early return at `:74`). Wastes/misdirects maintainer effort on the 429 path. | django-drf | gp:blog+core | `apps/core/exceptions.py:178-183` | — | open | agent-verified |
| M9 | `csrf_token_view` docstring says **"DEPRECATED … kept for backward compatibility"** but it is the live, routed `api/csrf/` endpoint the entire web SPA fetches (`web/src/utils/csrf.ts:75`). A maintainer trusting the docstring could remove it and break CSRF for the whole web app. | django-drf | gp:blog+core | `apps/core/views.py:32-33` | — | open | agent-verified |
| M10 | Dead `SecurityMonitor` tracking methods (`track_file_upload`, `track_validation_failure`, `get_security_status`) — zero call sites; their paired constants (`UPLOAD_FAILURE_WINDOW`, `VALIDATION_FAILURE_WINDOW`) are orphaned. Reads as a live security-monitoring API but tracks nothing; maintainers may rely on non-existent monitoring. | django-drf | gp:blog+core | `apps/core/security.py:489,541,679` | — | open | agent-verified (sibling methods confirmed live, excluded) |
| M11 | Live rate-limit code hardcodes `60`/`30`/`10` inline while the matching constants (`API_RATE_LIMIT_WINDOW/_MAX_REQUESTS`, `SUSPICIOUS_ACTIVITY_THRESHOLD`) sit orphaned in `constants.py`. Tuning the constants has **no effect**; violates the explicit "no magic numbers — config in constants.py" rule. | django-drf | gp:blog+core | `apps/core/security.py:442,475,482` | — | open | agent-verified |
| M12 | `validation.ts`: 14 of 17 exports dead (entire `validate*` family + `getNameError`), while `SignupPage.tsx:92` reimplements username validation inline (dead-util + local-reimpl, same trap as H3). 350 lines presenting a validation "library" almost entirely unwired. | react-typescript | gp:web | `web/src/utils/validation.ts` | — | open | agent-verified |
| M13 | Case-collision sanitize names: `sanitizeHtml` (live) vs `sanitizeHTML` (`@deprecated`, dead) vs `domSanitizer.sanitizeHTML` (async) — a capitalization typo silently imports the wrong fn. The needless `Promise` wrapper (file's own header admits DOMPurify is sync) forces the `SafeHTML` component to carry `useState`+`useEffect`+`isMounted`+"Loading…" to await a `Promise.resolve()`. | react-typescript | gp:web | `web/src/utils/sanitize.ts:207,286,338`; `domSanitizer.ts`; `StreamFieldRenderer.tsx:16-37` | — | open | agent-verified |
| M14 | `handlePageChange` byte-identical in two forum pages; the pagination render block is copy-pasted and **already diverged** (`variant`, "Page X of Y" vs "Page X", `<=1` vs `===1`) → inconsistent pagination UI, fix needed in 2+ places. | react-typescript | gp:web | `pages/forum/ThreadListPage.tsx:118-128,262-281`; `SearchPage.tsx:240-250,495-514` | — | open | agent-verified |
| M15 | Harmful double-cast at the diagnosis-create API boundary: `cardData` typed `Record<string,unknown>` then `as unknown as CreateDiagnosisCardInput`, fully defeating the compiler — a renamed/added required field ships a malformed body with zero type feedback. | react-typescript | gp:web | `components/diagnosis/SaveDiagnosisModal.tsx:59,83` | — | open | agent-verified |
| M16 | Diagnosis StreamField block-type dispatch is switched in 3 spots (the `BLOCK_TYPES` menu, the editor `BlockEditor` switch, the renderer switch); adding a block type = 3 edits, and labels/icons are hard-coded in `case` JSX despite being declared in `BLOCK_TYPES`. | react-typescript | gp:web | `components/diagnosis/StreamFieldEditor.tsx:20-27,58`; `DiagnosisDetailPage.tsx:62-180` | — | open | agent-verified |
| M17 | Dead 284-line `route_transitions.dart` (`RouteTransitions` 10 builders + `PlatformExtension`, zero refs) while the router hand-rolls its own inline `FadeTransition`. _(Calibrated down from agent's High: copies are equivalent, not yet divergent; animation code, not dangerous-if-revived.)_ | flutter | gp:mobile | `lib/core/routing/route_transitions.dart` (whole file) | — | open | **ref-count verified** (zero refs) |
| M18 | `FirestoreService` (349L) + `plantsStreamProvider` fully built and **test-covered** but zero production call sites (`collection_screen` is a static placeholder). Passing tests reinforce the false impression of a live offline/sync layer; ongoing carry cost. | flutter | gp:mobile | `lib/services/firestore_service.dart` | — | open | agent-verified |
| M19 | `navigation_extensions.dart` (199L "type-safe" nav helpers) bypassed by all production code (raw `context.go/push` used instead); ~23 members unused by prod _and_ tests. Two competing nav conventions; new screens drift further from the advertised one. | flutter | gp:mobile | `lib/core/routing/navigation_extensions.dart` | — | open | agent-verified |
| M20 | Empty stub `test_anonymous_has_stricter_limits` (`pass` + "depends on endpoints") counted as a passing security test. _(Calibrated down from agent's High: covers unimplemented behavior, so hides no regression — but a green empty stub still misleads.)_ | testing | gp:testing | `apps/users/tests/test_rate_limiting.py:323` | — | open | **read-verified** (body is `pass`) |
| M21 | Hollow Sentry test: named for the production breadcrumb path but only asserts the Sentry mock is `toBeDefined()` — never invokes the logger, never asserts Sentry is called. A regression that stops sending breadcrumbs passes green. | testing | gp:testing | `web/src/utils/logger.test.ts:236` | — | open | agent-verified |
| M22 | Tautological config test `has correct timeout value`: declares a local `const TIMEOUT = 30000` and asserts it equals `30000` — never imports the real httpClient config. Changing the real timeout leaves it green. | testing | gp:testing | `web/src/utils/httpClient.test.ts:86` | — | open | agent-verified |

### Low

| ID  | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | ------- | ------ | ----- | ------- | -------- | ------ | ------------ |
| L1 | Third inline reimplementation of the PlantNet `species` parser (`_extract_care_info` + `_merge_suggestions`), compounding M1 — any PlantNet response-shape change requires editing 3 hand-rolled parsers. | django-drf | gp:plant_id | `services/combined_identification_service.py:401-437,478-515` | — | open | agent-verified |
| L2 | Copy-pasted no-op `if hasattr(image_file,"read")` branch where both branches are identical (dead conditional), duplicated verbatim across two `_prepare_image` methods — invites an asymmetric "fix" to a branch that does nothing. | django-drf | gp:plant_id | `services/plantnet_service.py:166-169`; `plant_health_service.py:71-74` | — | open | agent-verified |
| L3 | `images`/`image_thumbnails` model properties byte-identical across two sibling request models — paired helpers of the already-drifted M4 serializer layer. | django-drf | gp:plant_id | `apps/plant_identification/models.py:432-449,917-934` | — | open | agent-verified |
| L4 | frequency→interval mapping reimplemented in 3 places in 3 styles (model dict-with-default vs two view if/elif+break), already diverging on unknown-frequency handling; guarded today by the field's `choices=`. Adding a frequency = 3 edits in 3 styles. | django-drf | gp:users+garden | `apps/users/models.py:745-754`; `views.py:1487-1504,1584-1601` | — | open | agent-verified |
| L5 | Dead `_old_trust_level` branch: the attr is assigned nowhere, so the `if old_trust_level …` block (incl. commented-out upgrade-email) never runs; docstring claims behavior it doesn't perform. Wiring the email there ships a feature that silently never fires. | django-drf | gp:users+garden | `apps/users/signals.py:95-122` | — | open | agent-verified |
| L6 | Silent broad-except swallow with misleading narrow except-lists: `except (JSONDecodeError, …, Exception)` → `pass`/`None` with no log (the `Exception` makes the listed types meaningless). Not the file's normal `[SECURITY]`-logged pattern; hides bugs in the security-event path. | django-drf | gp:blog+core | `apps/core/security.py:759-769` | — | open | agent-verified |
| L7 | `logger.ts` standalone convenience wrappers (`logError`/`logWarning`/`logInfo`/`LOG_LEVELS`) zero refs — all 22 consumers use the `logger` object; unused parallel API invites inconsistent logging. | react-typescript | gp:web | `web/src/utils/logger.ts:47,400,407,414` | — | open | agent-verified |
| L8 | `getSeverityColor` severity→color map duplicated in two files with **drifted** type signatures (`(severity: string)` vs `(severity: SeverityAssessment)`) — the looser copy won't flag an invalid severity; new level = 2 edits. | react-typescript | gp:web | `components/diagnosis/DiagnosisCard.tsx:24`; `DiagnosisDetailPage.tsx:37` | — | open | agent-verified |
| L9 | `Attachment` type carries 5 overlapping URL fields ("Alias for compatibility") forcing `getAttachmentImageUrl` to fall through all 5; the type can't say which the backend populates. | react-typescript | gp:web | `web/src/types/forum.ts:75-79`; `ImageUploadWidget.tsx:29-38` | — | open | agent-verified |
| L10 | Stale TODO claims avatar upload is blocked "when FirebaseStorageService is implemented" — but that service is fully implemented and in use; the false dependency defers real work. | flutter | gp:mobile | `lib/services/user_profile_service.dart:180-181` | — | open | agent-verified |
| L11 | Unused public `getJWT()` accessor (zero callers) diverges from the established `ApiService.setAuthToken()` injection path; invites a second token-handling convention. | flutter | gp:mobile | `lib/services/auth_service.dart:405-407` | — | open | agent-verified |
| L12 | Tautological config test `has correct base URL from environment` recomputes the env expression inline instead of reading the client's real `baseURL`; can't catch a regression. | testing | gp:testing | `web/src/utils/httpClient.test.ts:91` | — | open | agent-verified |
| L13 | Under-asserting spoofed-IP test: name claims tracking rejects the spoofed IP, but the assertion accepts _either_ "Invalid IP" _or_ "Failed login" log strings, so it passes if any warning fires. Partial blind spot (IP validation tested elsewhere). | testing | gp:testing | `apps/users/tests/test_ip_spoofing_protection.py:247` | — | open | agent-verified |

## Phase 3 — Resolution (status authority)

User chose to fix the **dead-code sweep + hollow tests** now; everything else
deferred to todos 221–223. Post-fix suites all green: **backend 628 OK** (`--noinput`),
**web 615 pass**, **flutter 165 pass** (after the M18 restore below); `manage.py check` clean, `tsc`/`flutter analyze` clean.
An orphan re-sweep (grep every deleted symbol across `apps`, no `.py` filter) returned **zero** residual references.

### Verified (fixed + stack tests green)

| ID | Outcome | Verification |
| -- | ------- | ------------ |
| H1 | Deleted `TrustLevelService` (+ `create_trust_level_groups`, `assign_user_to_trust_group`, `update_all_user_trust_levels`); transitively-orphaned `User.update_trust_level` + `log_trust_level_upgrade`; removed orphaned `Group` import | users 102 OK; re-sweep clean |
| H2 | Deleted `apps/blog/_services_deprecated.py` (462-line frozen shadow) | backend 628 OK |
| H3 | Deleted `web/src/utils/formatDate.ts` + its test (residual 3-way inline drift → todo 221-adjacent / left as-is) | web 615 pass |
| H4 | Rewrote empty Retry-After test → asserts `429` **and** positive-int `Retry-After` | users 102 OK |
| M1 | Deleted `normalize_plantnet_data` (fully dead); `get_top_suggestions` drift → **deferred** todo 221 | backend 628 OK |
| M2 | Deleted `_create_care_prompt` (superseded prompt builder) | backend 628 OK |
| M3 | Deleted `identify_with_location` + transitively-orphaned `_get_project_for_location` | backend 628 OK |
| M5 | Deleted 7 dead onboarding/demo methods + transitively-orphaned `_get_next_step` (kept live `completion_percentage`/`remaining_steps`) | users 102 OK |
| M10 | Deleted `track_file_upload`, `track_validation_failure`, `get_security_status` + 4 orphaned constants (`MAX_UPLOAD_FAILURES_PER_HOUR`, `UPLOAD_FAILURE_WINDOW`, `MAX_VALIDATION_FAILURES_PER_HOUR`, `VALIDATION_FAILURE_WINDOW`); kept live `_trigger_security_alert` | backend 628 OK |
| M12 | Deleted clear-dead `getNameError`; tested **security validators** → **deferred** todo 222 | web 615 pass |
| M17 | Deleted `route_transitions.dart` (284-line unused) | flutter 165 |
| M19 | Deleted `navigation_extensions.dart` + its test groups + now-unused splash import (user-approved) | flutter 165 |
| M20 | Deleted empty `AnonymousVsAuthenticatedRateLimitsTestCase` — both `pass` stubs incl. the unflagged sibling `test_authentication_increases_rate_limit` | users 102 OK |
| M21 | Rewrote hollow Sentry test → `vi.stubEnv('DEV', false)` forces prod branch; asserts breadcrumb + `captureMessage` | web 615 pass |
| M22 | Rewrote tautological timeout test → asserts real `httpClient.defaults.timeout` | web 615 pass |
| L5 | Deleted no-op `handle_user_profile_update` receiver + orphaned `post_save` import | users 102 OK |
| L7 | Deleted dead `logError`/`logWarning`/`logInfo`; un-exported internal-only `LOG_LEVELS` | web 615 pass |
| L11 | Deleted unused `getJWT()` | flutter 165 |
| L12 | Rewrote tautological base-URL test → asserts real `httpClient.defaults.baseURL` | web 615 pass |
| L13 | Tightened spoofed-IP test → asserts validated IP `== "192.168.1.100"` (rejects spoofed XFF) | users 102 OK |

**Transitive deletions** (orphaned by a flagged deletion, removed in the same commit after a zero-ref re-sweep): `log_trust_level_upgrade`, `_get_next_step`, `_get_project_for_location`, the 4 `MAX_*`/`*_WINDOW` constants, and the `Group` / `post_save` imports. `_trigger_security_alert` was checked and **kept** (live callers at security.py:240/382/443).

> **Post-review reversal (M18):** `firestore_service.dart` + `.g.dart` + its 2 test
> files were initially deleted (user-approved at triage), then **restored** after the
> owner confirmed offline persistence is a roadmap priority to keep and improve. M18
> is reclassified **deferred → [todo 224](../../todos/224-pending-p2-wire-offline-persistence-firestore.md)** (wire the offline layer into the UI). flutter suite back to **165 pass**. M17/M19 (unrelated to offline persistence) stay deleted.

<!-- -->

> **Severity-downgrade note:** M1 and M12 are recorded `verified` for their dead-code portion only; their drifted/wire-or-remove residuals are deferred (todos 221/222). H3's dead util is deleted; the 3 inline-`formatDate` copies remain (cosmetic, not in the dead-code-removal scope).

## Deferred Items

| ID(s) | Todo | Rationale |
| ----- | ---- | --------- |
| M4, M6, M7, M8, M9, M11, M1(parser), L1, L4, L6 | [todo 221](../../todos/221-pending-p2-maint-backend-duplication-contracts.md) (p2) | Backend drifted duplication & misleading contracts — multi-site edits / false contracts; M8 touches the 429 path |
| M12(validators), M13, M14, M15, M16, L8, L9 | [todo 222](../../todos/222-pending-p3-maint-web-duplication-casts-validators.md) (p3) | Web duplication/casts/coupling + tested security validators needing a wire-or-remove decision (don't blind-delete) |
| L2, L3, L10 | [todo 223](../../todos/223-pending-p3-maint-misc-low-cleanups.md) (p3) | Misc low-severity cleanups (dead conditional branch, dup model props, stale TODO) |
| M18 (keep + wire) | [todo 224](../../todos/224-pending-p2-wire-offline-persistence-firestore.md) (p2) | Initially deleted; **restored** — offline persistence is a roadmap priority. Wire `FirestoreService`/`plantsStreamProvider` into the UI |

## Finding Status

Deferred findings tracked as todos — checked off when the linked todo is archived
(the `completing-todos` skill renames this manifest to `…-COMPLETED.md` once all are `[x]`).

- [x] #M1 PlantNet parser drift/consolidation → todo 221 (completed 2026-06-10)
- [x] #M4 image-URL serializers duplicated + drifted → todo 221 (completed 2026-06-10)
- [x] #M6 misleading soft-delete OpenAPI schema → todo 221 (completed 2026-06-10)
- [x] #M7 drifted signup side-effects across 3 paths → todo 221 (completed 2026-06-10)
- [x] #M8 unreachable Ratelimited branch + misleading comment → todo 221 (completed 2026-06-10)
- [x] #M9 csrf_token_view falsely marked DEPRECATED → todo 221 (completed 2026-06-10)
- [x] #M11 rate-limit magic numbers vs orphaned constants → todo 221 (completed 2026-06-10)
- [x] #L1 third inline PlantNet parser → todo 221 (completed 2026-06-10)
- [x] #L4 frequency→interval mapping in 3 styles → todo 221 (completed 2026-06-10)
- [x] #L6 silent broad-except swallow → todo 221 (completed 2026-06-10)
- [x] #M18 offline `FirestoreService` — keep + wire to UI (restored) → todo 224 (completed 2026-06-22)
- [ ] #M12 unwired security validators (wire-or-remove) → todo 225 (split from 222)
- [x] #M13 sanitize case-collision + needless async → todo 222 (completed 2026-06-10)
- [x] #M14 forum pagination duplicated + drifted → todo 222 (completed 2026-06-10)
- [x] #M15 harmful double-cast at diagnosis-create boundary → todo 222 (completed 2026-06-10)
- [ ] #M16 block-type dispatch edit-in-3-places → todo 225 (split from 222)
- [x] #L8 getSeverityColor duplicated + drifted → todo 222 (completed 2026-06-10)
- [x] #L9 Attachment URL-field sprawl → todo 222 (completed 2026-06-10)
- [x] #L2 no-op hasattr branch ×2 → todo 223 (completed 2026-06-10)
- [x] #L3 duplicated model image properties → todo 223 (completed 2026-06-10)
- [x] #L10 stale FirebaseStorageService TODO → todo 223 (completed 2026-06-10)

## Summary

| Severity  | Found | Verified | Deferred | False-positive | Open  |
| --------- | ----- | -------- | -------- | -------------- | ----- |
| Critical  | 0     | 0        | 0        | 0              | 0     |
| High      | 4     | 4        | 0        | 0              | 0     |
| Medium    | 22    | 11       | 11       | 0              | 0     |
| Low       | 13    | 5        | 8        | 0              | 0     |
| **Total** | 39    | 20       | 19       | 0              | **0** |

> 20 verified (dead-code sweep + hollow tests), 19 deferred to todos 221–224, 0 open.
> M18 (`FirestoreService`) was deleted then **restored** post-review — offline persistence is a roadmap priority — and reclassified deferred → todo 224.

## Coverage & Dedup Notes

- **`forum_integration/` is gone.** Retired in commit `42882be` (django-machina removal, 2026-06-09). The Phase-1 churn/size data flagged `forum_integration/serializers.py` as the hottest backend file, but those were _historical_ commits on now-deleted code. The **live backend forum** (`backend/packages/wagtail_forum/`, `apps/forum_host/`) is new, small (~74-line serializers), and was just reviewed under PRs #361/#362 with tests — it was **not** deep-audited for maintainability here. Low risk, but a deliberate coverage gap if the user wants it covered.
- **Already-tracked, not re-reported:** `BlogAIIntegration.generate_content` dead (todo 204); `wagtail_ai_integration.py` v2 module / `AIRateLimiter` dead (todo 204); `HomePage.test.tsx` clay-CTA under-assert (todo 207 — confirmed already fixed); `SearchPage.tsx:96` double-cast (todo from 2026-06-02); `identification_service.py:226` swallow (todo 208).
- **Agent-caught false positives (excluded):** `validate_plant_types`, `GrowingZoneViewSet.lookup`, 5 garden_calendar "dead" methods, `track_successful_login`/`unlock_account`/`log_security_event`/`ExternalAPIError`/`RateLimitExceeded` — all verified **live** by reference count and excluded. `api_service.dart` and the services-layer `dynamic`/error-handling were verified clean.
- **Low-value stale comment (noted, not filed):** the AI-removal comment at `apps/blog/api_views.py:363-367` points to `apps/blog/panels.py` + panel classes that don't exist — surrounding code is already tracked-dead (todo 204), so folded in rather than filed separately.

## Fix Commits

| Commit | Description |
| ------ | ----------- |
| —      | —           |

## Codification (Phase 8)

| Finding | Destination | Note |
| ------- | ----------- | ---- |
| Mass-deletion method (H1/H2/M1-M5/M10/L5 etc.) | `docs/LEARNINGS.md` | Dead-code removal is verified by whole-repo reference re-sweep + orphaned-import check, NOT a green suite; follow transitive-deadness chains to closure; grep without `.py` filter before deleting model methods (string refs in serializers/panels/templates) |
| M12/M18/M19 (built-but-unwired) | `docs/LEARNINGS.md` | "Zero references" ≠ "delete" — coherent tested features / security utilities get a human delete-vs-wire decision (M19 deleted on approval; **M18 deleted then restored** when the owner flagged offline persistence as roadmap → todo 224; M12 validators + M1 parser deferred). Reinforces the rule: surface coherent-but-unwired features, don't auto-delete. |
| H4/M20/M21/M22/L12/L13 (hollow tests) | `docs/LEARNINGS.md` + `docs/rules/testing.md` | Banned hollow-test shapes (empty `pass`, tautological literal, mock-`toBeDefined`-only); `vi.stubEnv('DEV', false)` to enter dev-gated branches; delete empty placeholder stubs |
| Hollow-test rule | `docs/rules/testing.md` | New "No hollow tests" binding rule (sharpens existing "a test that can't fail isn't a test") |
