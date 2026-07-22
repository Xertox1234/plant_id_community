---
status: in_progress
priority: p1
issue_id: "255"
tags: [forum, ai, premium, wagtail-ai]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H12, H13, H14, H15, M12, M13, M14, L6, L7"
---

# Forum epic: AI features & premium entitlement

## Problem

The premium-AI theme (a stated goal of the forum modernization) has zero
substrate: no plan/tier/entitlement primitive exists anywhere in the codebase,
and none of the AI features are built — while the wagtail-ai + django-ai-core
substrate they need already ships in the dependency tree, dormant. p1 epic from
the 2026-07-11 forum-modernization audit.

## Findings

- **H12** — No premium/entitlement primitive anywhere (no plan/tier/Stripe/
  entitlement code; `is_staff` is the only tier proxy, in
  `apps/blog/services/ai_rate_limiter.py`). **Hard prerequisite for every other
  item — sequence first.** Belongs host-side (`apps/users/` + `forum_host`
  decorators), never in the reusable package.
- **H13** — LLM spam/moderation pre-screen unimplemented despite a first-class
  extension point: `WAGTAILFORUM_SPAM_BACKEND` swaps in one setting
  (`W/conf.py:6`, `W/spam/base.py`); a host-side `LLMSpamBackend` can reuse
  `generate_ai_text()` (`apps/blog/wagtail_ai_v3_integration.py:73`) + Redis
  cache. Design cost: the publish-path call is synchronous — needs a timeout +
  heuristic fallback. Premium-agnostic quality win — ranks first among the AI
  features.
- **H14** — AI thread summarization (premium perk): 100% host-side reuse of
  existing substrate (`generate_ai_text`, the Celery task pattern from
  `send_forum_push`, `AICacheService` content-hash caching). Needs H12 first.
- **H15** — Semantic "similar topics" on compose: `django_ai_core.contrib.index`
  (pgvector storage, `rebuild_indexes` command) already ships via wagtail-ai 3.x
  and is dormant; `ModelSource` verified to work on plain models (Topic/Post are
  non-Page). One-time infra: INSTALLED_APPS + pgvector extension (**Railway
  support UNVERIFIED — precheck before building**) + index definition. Product
  call: arguably free-for-all, not premium-gated (dedupe helps community health).
- **M12** — Semantic search upgrade (premium): marginal add once H15 infra
  exists (`VectorIndex.search_sources()` is generic). Baseline corrected by H22
  research: current search is already Postgres FTS with ranking — the value-add
  is synonym/meaning matching, not "any ranking at all".
- **M13** — RAG plant-care answers grounded in the site's plant-ID + blog data:
  highest differentiation, long-horizon big bet; strict superset of H15 infra;
  needs citation UX + hallucination guardrails (plant-care advice has real-world
  consequences). **Do not start before H15.**
- **M14** — AI-assisted composer (draft improvement): wagtail-ai's editor
  machinery is admin-only (verified — panels are `/cms/`-only); only the backend
  `generate_ai_text` substrate applies → bespoke host endpoint + TipTap toolbar
  action. Least favorable cost profile (interactive, uncacheable).
- **L6** — Doc drift: `backend/docs/patterns/domain/blog.md:381-450` documents a
  `TIER_LIMITS`/premium API that does not exist in `ai_rate_limiter.py` —
  overstates premium infra.
- **L7** — `OPENAI_API_KEY` defaults to `""` (`settings.py:771`) — whether
  production AI works depends on a deployed secret unverifiable from the repo;
  ops check before shipping any AI feature.

## Recommended Action

Sequence (dependency-ordered):

1. **H12 entitlement primitive**: `is_premium`/plan on the user (or a small
   Plan model), checkable in DRF permissions and services; migrate
   `AIRateLimiter` off the `is_staff` proxy; fix the L6 doc drift in the same
   pass; run the L7 prod-key check.
2. **H13 LLM spam backend** (premium-agnostic, highest quality-per-effort):
   host-side backend behind `WAGTAILFORUM_SPAM_BACKEND` with hard timeout +
   fallback to the heuristic backend; Redis-cache verdicts by content hash.
3. **H14 thread summarization**: premium-gated endpoint + Celery task +
   content-hash cache.
4. **H15 similar-topics**: pgvector-on-Railway precheck FIRST; then
   INSTALLED_APPS + index definition + compose-time endpoint.
5. **M12 semantic search** (thin layer over H15), **M14 composer assist**
   (bespoke endpoint), **M13 RAG** (explicitly last; own design round).

## Technical Details

- Substrate verified at installed-source level during the audit: wagtail-ai
  3.1.0 requires django-ai-core (0.1.5); `ModelSource` works on plain models;
  wagtail-vector-index (PyPI v0.10.0, June 2024, Wagtail 5 classifier) is stale
  — the django-ai-core path is the right one.
- Never point kimi cheap-worker tools at the entitlement/permission code (user
  policy: permissions are never delegated).
- Package purity: entitlement checks and AI endpoints live host-side;
  `test_reusability.py` forbids `apps.*` imports inside the package.

## Acceptance Criteria

- [x] Entitlement primitive exists, is checkable in DRF, and `AIRateLimiter`
      consumes it (no `is_staff` proxy); `blog.md` drift corrected (L6)
      — slice 1, 2026-07-20
- [x] Production `OPENAI_API_KEY` presence verified/documented before any AI
      feature ships (L7) — slice 1, 2026-07-20: present on Railway service
      `plant_id_community` (164-char `sk-` key)
- [x] LLM spam backend runs behind the one-setting swap with timeout +
      heuristic fallback — publish path never blocks on provider outage (tested)
      — slice 2, 2026-07-21
- [ ] Premium thread-summary endpoint: Celery-generated, content-hash cached,
      entitlement-gated
- [ ] pgvector-on-Railway precheck result recorded; similar-topics endpoint
      shipped if viable (or descoped with rationale)
- [ ] M13 RAG remains unstarted until H15 infra lands (explicit gate)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 9 open findings per the manifest's Phase 4 grouping table
  (user-approved: AI & premium selected as a p1 theme). H12-first sequencing and
  the pgvector precheck are recorded in the manifest's Phase 4 notes.

### 2026-07-20 - Slice 1: entitlement primitive (H12 + L6 + L7) DONE

Branch `todo-255-slice1-entitlement-primitive`. User-confirmed scope: slice 1
only; field shape: boolean `is_premium` (not a tier CharField or Plan model).

- **H12** — `User.is_premium` BooleanField (migration `users.0010_user_is_premium`)
  - `User.has_premium_access()` (mirrors `can_upload_images()`:
  `is_premium or is_staff or is_superuser`). New DRF `IsPremiumUser` permission
  (`apps/users/permissions.py`). `AIRateLimiter` migrated off the `is_staff`
  proxy: constant `STAFF_LIMIT`→`PREMIUM_LIMIT`, param `is_staff`→`has_premium`;
  decorators + `ai_integration.py` call sites now pass `has_premium_access()`.
  **Trap avoided:** the only live decorator caller (`generate_ai_content`) is
  `@staff_member_required`, so a naive swap would drop non-premium staff 50→10;
  staff get premium-equivalent access *inside the helper*, preserving the limit.
  Regression test added (`test_staff_user_gets_premium_limit_through_decorator`).
- **L6** — rewrote `backend/docs/patterns/domain/blog.md` §"Rate Limiting"
  to the real API (removed fictional `TIER_LIMITS` / `check_and_increment` /
  `user.profile.subscription_tier`).
- **L7** — production `OPENAI_API_KEY` verified present on Railway service
  `plant_id_community` via `railway variables -s plant_id_community --kv`
  (164-char `sk-` key; value not logged). Prod AI is wired.
- Verified: `manage.py check` clean, `makemigrations --check` no changes,
  `spectacular` OK, `pytest apps/users apps/blog --create-db` → 329 passed.
- **Deferred (todo stays in_progress):** H13 spam backend (independent of H12;
  hard timeout + heuristic fallback on the synchronous publish path), H14
  summary endpoint (gate via `IsPremiumUser`), H15 similar-topics (entry
  condition: Railway pgvector precheck — `pgvector` not yet installed / not in
  INSTALLED_APPS), M12/M14, M13 RAG (last).

### 2026-07-21 - Slice 2: LLM spam backend (H13) DONE

Branch `todo-255-slice2-llm-spam-backend` (off `main`, independent of slice 1).
Spec: `docs/superpowers/specs/2026-07-21-forum-llm-spam-backend-design.md`.

- **H13** — host-side `LLMSpamBackend` (`apps/forum_host/spam.py`) behind the
  existing `WAGTAILFORUM_SPAM_BACKEND` swap; **ships dormant** (default stays
  `HeuristicSpamBackend`). Heuristic-first composite: obvious spam rejected with
  no LLM call; the LLM screens only what the heuristic passes, via
  `generate_ai_text()`. Hard wall-clock timeout (`ThreadPoolExecutor`,
  `SPAM_LLM_TIMEOUT_SECONDS=3`, lazy-init pool) because `check()` runs inside
  the workflow's `@transaction.atomic` publish path. Redis-cached verdicts by
  content hash; global-budget spend cap (`check_global_limit()`).
  - **Ratified postures:** provider failure → **fail closed** (reject →
    pending draft via a normal `reject`, not a raise — matches `workflow.py`);
    budget cap → **degrade to heuristic** (publish; cost decision, not outage).
- Verified: `manage.py check` clean, `spectacular` OK, `makemigrations --check`
  no changes, `apps.forum_host` + package `test_spam` suites pass.
- **Post-review hardening (folded in before PR):** CLEAN verdict now requires an
  exact one-word match (a `CLEANLY …` lookalike fails closed — the one unsafe
  parse direction); the whole post-heuristic screening block (Redis cache read,
  budget check, provider call, cache write) fails closed via a returned reject on
  ANY fault incl. a Redis outage, never a raise into the atomic path; timeout logs
  at warning (no per-post traceback); verdict-cache-write failures no longer
  discard a computed verdict. +3 tests (14 total).
- **H13 follow-up before the setting is ever ENABLED (not blocking the dormant
  merge):** a *sustained* LLM outage burns the shared global AI budget via failed
  attempts, because `AIRateLimiter.check_global_limit()` check-and-increments
  BEFORE the call. After ~`GLOBAL_LIMIT` failures the posture flips fail-closed
  (hold) → degrade-to-heuristic (publish LLM-unscreened), and the flip is *sticky*
  (every increment resets the 1h TTL; forum + blog share `ai_rate_limit:global`).
  Fix before enabling: don't count failed attempts against the budget, and
  consider a forum-specific budget key decoupled from the blog AI counter.
- **Deferred (todo stays in_progress):** H14 summary endpoint (gate via
  `IsPremiumUser` from slice 1), H15 similar-topics (Railway pgvector precheck),
  M12/M14, M13 RAG (last).

## Notes

p1 by user triage decision. All research verdicts for H13/H14/H15/M12/M14 were
`confirmed` against current docs at audit time (Context7 + installed-source
verification).
