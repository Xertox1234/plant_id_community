---
status: completed
priority: p2
issue_id: "204"
tags: [wagtail, blog, ai, audit]
dependencies: []
source_review: "docs/audits/2026-06-02-full.md"
source_finding: "H2, H3, L15"
---

# Migrate blog AI generation to the wagtail-ai 3.x API

## Problem

The blog AI content-generation feature is non-functional: it imports
`wagtail_ai.utils.get_ai_text`, which was removed in the installed wagtail-ai
3.1.0. The live `api/ai-content/` endpoint always returns HTTP 503, and any
rate-limiting that exists is wired into no live code path. Two stale/dead modules
remain from the 2.x era.

## Findings

- **H2 (High):** `from wagtail_ai.utils import get_ai_text` raises `ImportError`
  in wagtail-ai 3.1.0 (confirmed at runtime). Call sites:
  `backend/apps/blog/api_views.py:218,274` and
  `backend/apps/blog/ai_integration.py:371,373`. The API endpoint's
  `try/except ImportError` masks it as a 503.
- **H3 (High):** AI rate limiting is unreachable — the v3 monkey-patch installs
  the `CachedLLMService` wrapper with `user=None`
  (`backend/apps/blog/wagtail_ai_v3_integration.py:354-358`), and the API path
  (`api_views.py:198`) has no limiter at all. wagtail-ai 3.x exposes **no
  user-aware hook**, so the per-user limiter branch can never fire.
- **L15 (Low):** dead v2 module `backend/apps/blog/wagtail_ai_integration.py`
  references `AIRateLimiter.USER_LIMITS` (no such attribute → `AttributeError`
  if reached, line 71) and hardcodes `from django.contrib.auth.models import
  User` (line 18). Its `install_*` function is never called.

Source: audit 2026-06-02 (Phase 2.5 doc-research confirmed via Context7).

## Recommended Action

1. Replace `get_ai_text(prompt)` with the wagtail-ai 3.x service API:

   ```python
   from wagtail_ai.agents import get_llm_service

   result = get_llm_service().completion(
       messages=[{"role": "user", "content": prompt}]
   )
   text = result.choices[0].message.content
   ```

   Update both `api_views.py` and `ai_integration.py`. Confirm the project's
   `WAGTAIL_AI` settings use the 3.x `PROVIDERS` style (not 2.x `BACKENDS`).
2. **H3:** because 3.x has no per-user hook, enforce rate-limiting at the **view
   layer** — apply the existing `AIRateLimiter` (or `@ratelimit`) in
   `generate_ai_content` *before* calling `get_llm_service()`. Drop the
   `user=None` monkey-patch limiter branch (keep the caching wrapper if still
   desired).
3. **L15:** delete the dead v2 module `wagtail_ai_integration.py` (resolves the
   M24 "two divergent implementations" tail noted in the 2026-05-17 audit).
4. Add a test that `generate_ai_content` returns 200 with generated text (mock
   the LLM service) and that the rate limit returns 429 past the threshold.

## Technical Details

- Pattern docs: `backend/docs/patterns/domain/blog.md` (AI rate limiting by tier),
  `backend/docs/patterns/domain/wagtail.md` (AI section / version mismatch).
- Verify whether the AI feature is actually used in production before investing
  heavily — it has been silently 503-ing, suggesting low usage.

## Acceptance Criteria

- [x] `python -c "from wagtail_ai.agents import get_llm_service"` works and the
      `get_ai_text` import is gone from the codebase.
- [x] `api/ai-content/` returns 200 with generated content (mocked LLM) instead
      of 503.
- [x] AI generation is rate-limited at the view layer; a test asserts 429 past
      the threshold.
- [x] Dead module `wagtail_ai_integration.py` removed; full blog suite green.

## Work Log

### 2026-06-02 - Deferred from full audit

- Filed from audit `docs/audits/2026-06-02-full.md` (findings H2, H3, L15).
  Deferred per user triage (AI v3 migration is larger scope than the audit's
  fix-now set).

### 2026-06-02 - Completed

- **H2:** Added `generate_ai_text(prompt)` helper in
  `wagtail_ai_v3_integration.py` wrapping the wagtail-ai 3.x service
  (`get_llm_service(alias).completion(messages=[…]).choices[0].message.content`).
  Verified the audit's recommended API against the installed 3.1.0 source — it
  matches what wagtail-ai's own `BasicPromptAgent` uses. Replaced both
  `get_ai_text` call sites (`api_views.py`, `ai_integration.py`); dropped the
  vestigial `try/except ImportError → 503` block (import now always succeeds —
  genuine LLM/config errors map to the existing 500 path). Helper resolves
  `get_llm_service` off the module at call time so the installed caching wrapper
  applies and tests can patch it.
- **H3:** Applied the existing `@ai_rate_limit` decorator (view layer, innermost
  — after staff/method checks so only real staff POSTs consume quota → 429 +
  `Retry-After`) to `generate_ai_content`. Removed the unreachable `user=None`
  limiter branch (plus `user` param / `AnonymousUser` / `AIRateLimiter` imports)
  from `CachedLLMService`; the wrapper now does caching only. Note:
  `BlogAIIntegration.generate_content` is referenced only from tests (no live
  path) — its existing service-layer limiter is unchanged.
- **L15:** Deleted dead v2 module `wagtail_ai_integration.py` (`install_*` never
  called) and fixed the stale comment in `api_views.py` that referenced it.
- Bonus hygiene: bumped `requirements-dev.txt` `wagtail-ai` 3.0.0 → 3.1.0 to
  match `requirements.txt` (CI installs `requirements.txt`, so this was untested
  drift, not a CI gate).
- Tests: added helper unit test (mocks `get_llm_service`, asserts the v3
  messages payload + extraction), view 200 test (mocks helper), view 429
  rate-limit test (50× 200 then 429 + `Retry-After: 3600`), and a
  `BlogAIIntegration` success test. Full blog suite green: **186 passed,
  7 pre-existing skips**.

## Notes

p2 because the feature is fully broken (High severity) but appears dormant
(no one reported the 503). Confirm usage before prioritizing.
