# Audit: Full Codebase Audit (2026-06-02)

> **Date:** 2026-06-02
> **Trigger:** User-invoked `/audit` (full scope) — first full audit since 2026-05-17.
> **Domains:** security, performance, django-drf, api-design, wagtail, react-typescript, flutter, firebase, celery, testing
> **Baseline (all green):** backend `manage.py check` clean (0 issues) · backend 687 tests OK (11 skipped) · web 689 vitest pass / tsc 0 errors / eslint 1 warning (generated `coverage/` file, ignore) · flutter 171 pass, 3 skipped / analyze clean

## Context

- Last full audit: [2026-05-17-full.md](2026-05-17-full.md) — 124 findings, 110 deferred to todos 079–085 (still tracked). Dedupe new findings against those.
- Largest change since: Green Thumb design-system web migration (#323/#324, ~130 files, 12k insertions) + backend PyJWT 2.12.1→2.13.0 (#326).

## Findings

Each finding has a lifecycle: `open` → `fixing` → `verified` or `deferred` or `false-positive`.

**Status key:** `open` · `fixing` · `verified` · `deferred` (link todo) · `false-positive`

**Research key** (Phase 2.5): `confirmed` · `better-fix` · `contradicted ⚠` · `—` (n/a)

### Critical

_None._

### High

| ID  | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | ------- | ------ | ----- | ------- | -------- | ------ | ------------ |
| H1 | Celery autoretry is dead code — generic `except Exception` catches the `autoretry_for` exceptions, sets `status="failed"` & re-raises; on retry the line-48 idempotency guard sees `!= pending` and no-ops. First transient API blip → permanent failure; all 5 retries wasted. | celery | celery | `apps/plant_identification/tasks.py:102-111` (guard `:48`) | confirmed | deferred | **REVERTED** (Phase 6) — task-only fix was inert: the service swallows every exception (`identification_service.py:226`, no re-raise), so autoretry/`on_failure` never fire. Real fix = service re-raise + `on_failure` together → [todo 208](../../todos/208-pending-p2-audit-celery-autoretry-service-reraise.md) |
| H2 | `get_ai_text` import doesn't exist in installed wagtail-ai 3.1.0 → live `api/ai-content/` endpoint always returns 503; `BlogAIIntegration.generate_content` fails every call. AI content generation is non-functional via API. | wagtail | wagtail | `apps/blog/api_views.py:218,274`; `apps/blog/ai_integration.py:371,373` | better-fix | deferred | runtime ImportError confirmed; FIX: wagtail-ai 3.x `from wagtail_ai.agents import get_llm_service` → `get_llm_service().completion(messages=[{"role":"user","content":prompt}]).choices[0].message.content` |
| H3 | AI rate limiting wired into no live path — v3 monkey-patch installs wrapper with `user=None` (limiter branch unreachable); API path has no limiter. Admin AI-panel generation is unthrottled (staff-only surface). | wagtail | wagtail | `apps/blog/wagtail_ai_v3_integration.py:354-358`; `apps/blog/api_views.py:198` | confirmed | deferred | agent-verified; NOTE: wagtail-ai 3.x exposes no user-aware hook — enforce rate-limit at the **view layer** before `get_llm_service()`, not via monkey-patch (depends on H2 fix) |
| H4 | Blog comment create/delete/approve never invalidates cached blog responses — no `BlogComment` signal exists. Cached detail/list embed `comment_count`; stale up to 24h TTL. | performance | performance | `apps/blog/signals.py` | — | verified | added `BlogComment` post_save/delete receiver → invalidate post+lists+popular. **Behavioral tests** (`test_blog_signals.py`): real comment write → cached post/list key is cleared (fails if the receiver's silent `except` swallowed a bug) |
| H5 | Firestore update rules don't pin `request.resource.data.user_id` → an owner can rewrite `user_id` to another uid, moving their record into a victim's namespace. **Latent: collections unused by any client today.** | firebase | firebase-cf | `firebase/firestore.rules:27,37,46` | confirmed | verified | all 3 update rules now pin `request.resource.data.user_id == resource.data.user_id`; re-read, syntax valid |
| H6 | N+1: `ForumTopicsListView` omits `select_related("forum")`; `TopicSerializer.get_forum` reads `obj.forum.*` per topic on a public unbounded list (sibling `all_topics_list` does it right). | django-drf | django-drf | `apps/forum_integration/api_views.py:88-92` | — | verified | added `select_related("forum")`; forum_integration tests pass |
| H7 | N+1: `SeasonalTemplateViewSet` omits `select_related("created_by")`; serializer nests `created_by=EventOrganizerSerializer` over FK on a public list. | django-drf | django-drf | `apps/garden_calendar/api/views.py:373` | — | verified | added `.select_related("created_by")` to class queryset; garden_calendar 150 tests pass |

### Medium

| ID  | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | ------- | ------ | ----- | ------- | -------- | ------ | ------------ |
| M1 | `CareLogSerializer.activity_type_display` declared as `CharField(source="get_activity_type_display")` but `CareLog.activity_type` has no `choices=` → DRF `SkipField` silently omits the key; drf-spectacular still advertises it (schema/runtime mismatch). | api-design | api-design | `apps/garden_calendar/api/serializers.py:685-686` | better-fix | deferred | runtime-verified (DRF `SkipField`); FIX: add `choices=` to `CareLog.activity_type` model field (makes `get_FOO_display` exist + drf-spectacular emits enum) — or drop the field if free-form |
| M2 | `service_status` error branch returns `Response({"error":...})` with no `status=` kwarg → HTTP **200** on a server error. | api-design | api-design | `apps/plant_identification/urls.py:67-68` | — | verified | `status=http_status.HTTP_503_SERVICE_UNAVAILABLE` (aliased import avoids shadowing local `status`) |
| M3 | `CreateTopicSerializer.create` writes Topic+Post(+RichPost)+save with no `transaction.atomic()` (ATOMIC_REQUESTS off) → half-formed topic on mid-failure. | django-drf | django-drf | `apps/forum_integration/serializers.py:385-438` | — | deferred | agent-verified |
| M4 | `CreatePostSerializer.create` multi-row write without `transaction.atomic()` (same pattern). | django-drf | django-drf | `apps/forum_integration/serializers.py:473-506` | — | deferred | agent-verified |
| M5 | Rate-limit `Retry-After` wrapper (todo 115) adopted forum-only; these modules still `import django_ratelimit.decorators.ratelimit` → `Ratelimited` has no `.rate`, handler falls back to `Retry-After: 3600` for sub-hour windows. | api | django-drf | `apps/plant_identification/views.py:22` (+ `oauth_views.py:25` → todo 206) | — | verified | `views.py` swapped to `apps.core.ratelimit` wrapper (691 tests pass). `oauth_views.py` portion deferred → todo 206: it carries pre-existing F401 tech-debt that the pre-commit flake8 gate flags, and it's an auth module needing hand cleanup — out of the fix-now scope |
| M6 | No rate limiting on `firebase_token_exchange` (AllowAny; runs Firebase crypto verify + DB user creation per call). Every sibling auth entry point has `@ratelimit`. | security | flutter-fb | `apps/users/firebase_auth_views.py:89-91` | — | deferred | agent-verified |
| M7 | `forum_stats` runs 3 uncached COUNT queries on every public (AllowAny) request — no Redis layer (analogous to fixed M8 `blog_stats`). | performance | performance | `apps/forum_integration/api_views.py:302-318` | — | deferred | agent-verified |
| M8 | `BlogCategory` rename/update leaves stale cached blog responses — category-invalidation receiver is commented out. | performance | performance | `apps/blog/signals.py:135-147` | — | verified | activated `BlogCategory` post_save/delete receiver (category+lists invalidation). **Behavioral test** (`test_blog_signals.py`): real category write → cached list key cleared |
| M9 | Garden bed `analytics`: health tally via Python `for` loop + two separate `.count()` (collapsible to one conditional aggregate). | performance | performance | `apps/garden_calendar/api/views.py:794-811` | — | verified | loop→grouped `values().annotate(Count("pk"))` + one `Count("pk", filter=Q())` aggregate. **New endpoint test** asserts 200 + breakdown + `assertNumQueries(3)` (`test_audit_aggregates.py`) |
| M10 | Harvest `statistics`: 4 sequential `Sum()` aggregates in a per-unit loop (collapsible to one `Q`-filtered aggregate). | performance | performance | `apps/garden_calendar/api/views.py:1744-1751` | — | verified | 6 queries → 1 `Q`-filtered aggregate. **New endpoint test** asserts 200 + totals + `assertNumQueries(2)`. (Pre-existing unit-key mismatch `"lbs"/"bunches"` vs model `"lb"/"bunch"` preserved — noted in Phase 6) |
| M11 | `user_plants` public-read branch (`is_public==true`) has no `isAuthenticated()` guard → any unauthenticated caller reads the whole doc incl. `user_id`. **Latent** (collection unused). | firebase | firebase-cf | `firebase/firestore.rules:33-34` | confirmed | verified | public-read branch now `(isAuthenticated() && is_public)`; **behavior change** (no anon read) noted for PR |
| M12 | Rate-limit retry exhaustion: `self.retry()` raises `MaxRetriesExceededError` from a sibling `except`, not caught by `except Exception` → request stuck `pending` forever. | celery | celery | `apps/plant_identification/tasks.py:101` | confirmed | deferred | reverted with H1 (shares root: service swallow) → [todo 208](../../todos/208-pending-p2-audit-celery-autoretry-service-reraise.md) |
| M13 | No `acks_late`/`reject_on_worker_lost` on a 120s external-I/O task — worker kill mid-task loses the message (task is idempotent, so low-risk to enable). | celery | celery | `apps/plant_identification/tasks.py:18-31` | confirmed | deferred | agent-verified; FIX: `acks_late=True` + `task_reject_on_worker_lost=True` (safe given idempotency guard; Celery FAQ) |

### Low

| ID  | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | ------- | ------ | ----- | ------- | -------- | ------ | ------------ |
| L1 | PyJWT pinned `2.10.1` in `requirements-dev.txt` while prod is `2.13.0`; CI `pip-audit` only scans `requirements.txt` (un-gated drift). Known residual from PR #326. | security | security | `backend/requirements-dev.txt:124` | — | deferred | self-verified earlier |
| L2 | Inline prop type literals instead of an interface (sibling `ClayButton` does it right). | react-typescript | react-ts | `web/src/components/ui/Eyebrow.tsx:5-10`; `GrainOverlay.tsx:7` | — | deferred | agent-verified |
| L3 | `data as unknown as CategoriesResponse` double-cast defeats the type system (runtime guard follows, so benign). | react-typescript | react-ts | `web/src/pages/forum/SearchPage.tsx:96` | — | deferred | agent-verified |
| L4 | `get_can_rsvp` uses `obj.attendees.get(...)` bypassing prefetch (detail serializer; +1 query/request). | performance | django-drf | `apps/garden_calendar/api/serializers.py:178` | — | deferred | agent-verified |
| L5 | `_retry_after_seconds` only handles `/Nm`/`/Ns` suffixes; `"5/15m"` → 3600 fallback (latent — no wrapper user has such a window). | api | django-drf | `apps/core/exceptions.py:37-46` | — | deferred | agent-verified |
| L6 | Forum `TopicDetailView` nested-posts pagination shape `{results,count,current_page,...}` diverges from DRF-standard `{count,next,previous,results}`. | api-design | api-design | `apps/forum_integration/api_views.py:207-218` | — | deferred | agent-verified |
| L7 | Identified-badge text/icon uses `colorScheme.onSurface` over light `ext.leaf` bg → light-on-light in dark mode. | flutter | flutter-dart | `lib/features/results/results_screen.dart:93,98`; `lib/features/collection/collection_screen.dart:149` | — | deferred | agent-verified |
| L8 | Disabled `ClayButton` bg (`surfaceContainerHighest` → falls back to `surface` = scaffold bg) makes the disabled state nearly invisible. | flutter | flutter-dart | `lib/shared/widgets/clay_button.dart:41,47` | — | deferred | agent-verified |
| L9 | Invalid-email path raises `ValueError(f"...{firebase_email}")` → logged unredacted at `:233` (every other email log site redacts). | firebase | flutter-fb | `apps/users/firebase_auth_views.py:276` (→ `:233`) | — | deferred | agent-verified |
| L10 | Stale docstring still documents client-supplied `email`/`display_name` request params (C8 re-introduction risk; code correctly ignores them). | firebase | flutter-fb | `apps/users/firebase_auth_views.py:99-104` | — | deferred | agent-verified |
| L11 | `email` field has no DB `unique=True`; `User.objects.get(email=...)` catches only `DoesNotExist` → latent `MultipleObjectsReturned` → 500 (app-layer reg uniqueness mitigates). | django-drf | flutter-fb | `apps/users/firebase_auth_views.py:294`; `apps/users/models.py` | — | deferred | agent-verified |
| L12 | `_get_rich_post()` sets `obj._rich_post_cache` on the model instance inside a serializer — the exact anti-pattern in LEARNINGS.md:222; latent (no live stale-read path today). | performance | performance | `apps/forum_integration/serializers.py:167-174` | — | deferred | agent-verified |
| L13 | `plant_data_stats` runs 5 uncached COUNT/aggregate queries (staff-only dashboard, low traffic). | performance | performance | `apps/blog/api_views.py:306-332` | — | deferred | agent-verified |
| L14 | `HomePage.test.tsx` "renders a ClayButton CTA (clay)" only asserts unconditional `rounded-pill`, never `bg-clay` — under-verifies the variant it names. | testing | test-quality | `web/src/pages/HomePage.test.tsx:23` | — | deferred | agent-verified |
| L15 | Dead v2 module: `AIRateLimiter.USER_LIMITS` (no such attr → `AttributeError` if reached) + hardcoded `from django.contrib.auth.models import User`. Module's install fn is never called. | wagtail | wagtail | `apps/blog/wagtail_ai_integration.py:71,18` | — | deferred | agent-verified |
| L16 | Storage `avatars` uses `allow read: if true` (likely intentional public avatars; the literal anti-pattern in the pattern doc). | firebase | firebase-cf | `firebase/storage.rules:51` | — | deferred | agent-verified |

> **Dedup note (not new findings):** the Wagtail agent flagged that two items marked resolved in the 2026-05-17 audit are still present in code — **M23** AI cache TTL `2_592_000` (30 days) at `apps/blog/services/ai_cache_service.py:43` vs the 24h pattern doc, and **M25** the `retrieve` `Prefetch(...[:3])` slice at `apps/blog/api/viewsets.py:234`. These were deferred to todos 079–085 (now archived completed); the code/todo bookkeeping may have drifted. Surfaced for the user to reconcile, not re-audited here.

## Phase 6 Discoveries (code review)

The Phase 6 code review of the fix diff caught two `Count(<wrong-pk>)` bugs that
no test covered (the `analytics`/`statistics` endpoints had zero coverage). Both
are now fixed and locked by `apps/garden_calendar/tests/test_audit_aggregates.py`.

| ID | Finding | File | Status |
| -- | ------- | ---- | ------ |
| C1 | **Regression introduced by M9 fix:** used `Count("id")` in `analytics`, but `Plant`/`CareTask` have a `uuid` PK (no `id`) → `FieldError` → 500. The 150-test suite missed it (endpoint untested). | `apps/garden_calendar/api/views.py:800,807` | verified (→ `Count("pk")`, +endpoint test) |
| C2 | **Pre-existing (not from this audit):** `statistics` used `Count("uuid")` on `Harvest`, whose PK is `id` → `FieldError` → the endpoint already 500'd on `main`. Fixed opportunistically since the same method was being edited. | `apps/garden_calendar/api/views.py:1749` (new) + `by_plant` (pre-existing) | verified (→ `Count("pk")`, +endpoint test) |
| C3 | **Pre-existing data bug:** `statistics` aggregates per-unit on keys `"lbs"/"bunches"` but the model's `HARVEST_UNITS` are `"lb"/"bunch"` — so lb/bunch harvests never appear in `total_quantity_by_unit`. Out of M10's behavior-preserving scope (the refactor preserved it). | `apps/garden_calendar/api/views.py` `statistics` | deferred → [todo 206](../../todos/206-pending-p3-audit-backend-low-cleanup.md) |

**Celery (H1/M12):** the Phase 6 review also established that the initial
task-only fix was inert (the service swallows all exceptions), so it was reverted
and the findings re-classified `deferred` → todo 208 (service re-raise + on_failure
together). See the H1/M12 rows above.

## Deferred Items

| ID(s) | Todo | Rationale |
| ----- | ---- | --------- |
| H1, M12 | [todo 208](../../todos/208-pending-p2-audit-celery-autoretry-service-reraise.md) | Celery autoretry inert — needs the service to re-raise retryable exceptions paired with `on_failure`; task-only fix reverted in Phase 6 |
| H2, H3, L15 | [todo 204](../../todos/204-pending-p2-audit-wagtail-ai-v3-migration.md) | wagtail-ai 3.x migration + view-layer rate-limit — larger scope than the fix-now set; feature appears dormant |
| M1, M3, M4, M6, M7, M13 | [todo 205](../../todos/205-pending-p2-audit-backend-medium-hardening.md) | risk-sensitive / migration-bearing medium hardening (auth rate-limit, atomic writes, choices migration, caching, acks_late) |
| L1, L4, L5, L6, L9, L10, L11, L12, L13 | [todo 206](../../todos/206-pending-p3-audit-backend-low-cleanup.md) | backend low-severity cleanup — none exploitable/user-facing today |
| L2, L3, L7, L8, L14, L16 | [todo 207](../../todos/207-pending-p3-audit-web-flutter-firebase-low.md) | web/flutter/firebase low-severity polish (cosmetic/quality) |

## Finding Status

Deferred findings tracked as todos — checked off when the linked todo is archived
(the `completing-todos` skill renames this manifest to `…-COMPLETED.md` once all
are `[x]`).

- [x] #H1 Celery autoretry inert (service swallows) → todo 208 (completed 2026-06-03)
- [x] #M12 rate-limit retry exhaustion stuck pending → todo 208 (completed 2026-06-03)
- [x] #H2 wagtail-ai get_ai_text broken → todo 204 (completed 2026-06-02)
- [x] #H3 AI rate-limit wired to no live path → todo 204 (completed 2026-06-02)
- [x] #L15 dead v2 AI module → todo 204 (completed 2026-06-02)
- [x] #M1 CareLog activity_type_display dropped → todo 205 (completed 2026-06-02)
- [x] #M3 CreateTopic non-atomic → todo 205 (completed 2026-06-02)
- [x] #M4 CreatePost non-atomic → todo 205 (completed 2026-06-02)
- [x] #M6 firebase_token_exchange no rate-limit → todo 205 (completed 2026-06-02)
- [x] #M7 forum_stats uncached → todo 205 (completed 2026-06-02)
- [x] #M13 celery acks_late missing → todo 205 (completed 2026-06-02)
- [x] #L1 pyjwt dev-pin drift → todo 206 (completed 2026-06-05)
- [x] #L4 get_can_rsvp bypasses prefetch → todo 206 (completed 2026-06-05)
- [x] #L5 _retry_after_seconds window parse → todo 206 (completed 2026-06-05)
- [x] #L6 forum pagination shape diverges → todo 206 (completed 2026-06-05, accepted with rationale)
- [x] #L9 raw email in log → todo 206 (completed 2026-06-05)
- [x] #L10 stale docstring re-advertises identity fields → todo 206 (completed 2026-06-05)
- [x] #L11 email not DB-unique → todo 206 (completed 2026-06-05)
- [x] #L12 model-instance cache attr in serializer → todo 206 (completed 2026-06-05)
- [x] #L13 plant_data_stats uncached → todo 206 (completed 2026-06-05)
- [x] #L2 inline prop type literals → todo 207 (completed 2026-06-05)
- [x] #L3 double cast through unknown → todo 207 (completed 2026-06-05)
- [x] #L7 dark-mode badge contrast → todo 207 (completed 2026-06-05, on-device visual confirmation deferred to reviewer)
- [x] #L8 invisible disabled ClayButton → todo 207 (completed 2026-06-05, on-device visual confirmation deferred to reviewer)
- [x] #L14 HomePage test under-asserts → todo 207 (completed 2026-06-05)
- [x] #L16 open avatar storage read → todo 207 (completed 2026-06-05)

## Summary

| Severity  | Found | Verified | Deferred | False-positive | Open  |
| --------- | ----- | -------- | -------- | -------------- | ----- |
| Critical  | 0     | 0        | 0        | 0              | 0     |
| High      | 7     | 4        | 3        | 0              | 0     |
| Medium    | 13    | 6        | 7        | 0              | 0     |
| Low       | 16    | 0        | 16       | 0              | 0     |
| **Total** | 36    | 10       | 26       | 0              | **0** |

> Plus 2 Phase-6 code-review fixes not in the 36-finding count: **C1** (regression
> introduced & fixed within this audit) and **C2** (pre-existing `statistics` 500,
> fixed opportunistically) — both verified by `test_audit_aggregates.py`.

## Fix Commits

| Commit | Description |
| ------ | ----------- |
| `cc488b6` | fix: resolve full-audit findings (10 verified, 26 deferred) — 8 code files + new `test_audit_aggregates.py` + manifest/changelog/todos 204–208 |
| `7779fa9` | docs: codify patterns and learnings from full audit |

Branch `chore/full-audit-2026-06-02` (PR pending).

## Codification (Phase 8)

| Finding | Destination | Note |
| ------- | ----------- | ---- |
| C1/C2 (Phase 6) | `docs/rules/database.md` | binding rule: aggregate on `Count("pk")`, never `Count("id")`/`Count("uuid")` |
| C1/C2 + verification gap | `docs/LEARNINGS.md` | untested endpoint hid a `Count(id)` 500 behind a green suite (hollow verification) |
| H1/M12 (Celery) | `docs/LEARNINGS.md` | `autoretry_for` is inert when the called service swallows exceptions; don't mock the whole service in the retry test |
