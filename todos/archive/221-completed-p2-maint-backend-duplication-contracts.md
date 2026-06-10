---
status: completed
priority: p2
issue_id: "221"
tags: [maintainability, backend, duplication, audit]
dependencies: []
source_review: "docs/audits/2026-06-09-maintainability.md"
source_finding: "M1,M4,M6,M7,M8,M9,M11,L1,L4,L6"
---

# Maintainability: backend drifted duplication & misleading contracts

## Problem

The 2026-06-09 maintainability audit found backend duplication that has already
drifted, misleading docstrings/OpenAPI contracts, and magic numbers diverging
from their orphaned constants. None is a security/correctness bug, but each
carries a concrete maintenance cost (a change must be applied in N places, or a
maintainer trusts a false contract). Deferred from that audit (the fix-now batch
was dead-code + hollow-tests only).

## Findings

Source: `docs/audits/2026-06-09-maintainability.md` (per-finding cost in the manifest).

- **M4** `get_images`/`get_image_thumbnails` duplicated across 4 serializers and **drifted** — one copy returns relative URLs, three absolute; two serialize the *same* model. `apps/plant_identification/serializers.py:108,180,444,672` (model-layer twin: `models.py:432-449,917-934` = L3).
- **M1 / L1** PlantNet `species` parser hand-rolled in 3 places; `get_top_suggestions` (`plantnet_service.py:360`) is test-only and reads `family.scientificNameWithoutAuthor` while the live parsers read `family.scientificName` — already drifted. (`normalize_plantnet_data` already deleted in the audit.) Consolidate `_extract_care_info`/`_merge_suggestions` (`combined_identification_service.py:401-437,478-515`) + `get_top_suggestions` onto one parser, or delete the test-only copy.
- **M7** Drifted signup side-effects across 3 account-creation paths — default "My Plants" collection created in `users/views.py:114` and `oauth_views.py:358` but **absent** from `firebase_auth_views.py:256-400`; 3 different username-collision strategies. Centralize signup side-effects.
- **M6** Misleading OpenAPI schema: `@extend_schema` says "Soft delete … is_active=False" but `destroy` hard-deletes. `apps/garden_calendar/api/views.py:626,937`. Either implement soft-delete or fix the docstrings.
- **M9** `csrf_token_view` docstring says "DEPRECATED … backward compatibility" but it is the live `api/csrf/` endpoint the web SPA depends on. `apps/core/views.py:32-33`. Remove the false deprecation note.
- **M8** Unreachable `Ratelimited` branch + misleading "ordering" comment in `custom_exception_handler` (the early return at `:74`/`:113` makes `:179-183` dead). `apps/core/exceptions.py:178-183`. Remove the dead branch + correct the comment (touches the 429 path — verify with rate-limit tests).
- **M11** Live rate-limit code hardcodes `60`/`30`/`10` while `API_RATE_LIMIT_WINDOW`/`_MAX_REQUESTS`/`SUSPICIOUS_ACTIVITY_THRESHOLD` sit orphaned in `constants.py`. `apps/core/security.py:442,475,482`. Reference the constants (no-magic-numbers rule).
- **L4** frequency→interval mapping reimplemented in 3 styles, already diverging on unknown-frequency handling. `apps/users/models.py:745-754`; `views.py:1487-1504,1584-1601`.
- **L6** Silent broad-except swallow with misleading narrow except-lists (`except (JSONDecodeError, …, Exception)` → `pass`/`None`, no log). `apps/core/security.py` `_post_request_tracking`.

## Recommended Action

1. Extract shared serializer image helpers (M4) + decide one URL shape (relative vs absolute); add a query-count/contract test.
2. Consolidate the PlantNet parser (M1/L1) onto one function; pick the correct family field; cover with a parser test.
3. Centralize signup side-effects behind one hook reused by all 3 account-creation paths (M7).
4. Fix the misleading contracts (M6, M9, M8 comment) — one PR, with rate-limit tests for M8.
5. Replace magic numbers with the orphaned constants (M11); add `Retry-After`-window coverage where relevant.
6. DRY the frequency mapping (L4); log + narrow the swallow (L6).

## Technical Details

Per-finding file:line above. Patterns: `backend/docs/patterns/architecture/services.md`,
`docs/rules/api.md`, `docs/rules/database.md`, `docs/rules/caching.md`.

## Acceptance Criteria

- [x] M4 image helpers extracted; one URL shape; contract test added.
      (done 2026-06-10 — `serialize_image_urls` helper in `serializers.py`
      replaces 4 drifted copies; absolute-when-request, relative fallback.
      Behavior-preserving: the only relative serializer
      (`PlantIdentificationRequestSerializer`) is served by `search_detail`
      WITHOUT request context → fallback keeps it relative; disease viewsets pass
      request → absolute, unchanged. Contract test in `test_serializers.py`.)
- [x] PlantNet parser single-sourced (M1/L1) with a parser test.
      (done 2026-06-10 — `parse_plantnet_species()` used by `_extract_care_info`,
      `_merge_suggestions`, and `get_top_suggestions`; the latter's drifted
      `scientificNameWithoutAuthor` family/genus reads fixed to `scientificName`.
      `ParsePlantNetSpeciesTest` in `test_services.py`.)
- [x] Signup side-effects centralized across all 3 paths (M7).
      (done 2026-06-10 — `apps/users/signup.py::create_default_plant_collection`
      called by register, OAuth, and Firebase; Firebase now GAINS the default
      "My Plants" collection it lacked. Username-collision deliberately NOT
      unified — Firebase's UUID-suffix format is pinned by
      `test_username_collision_handling`; registration uses a user-chosen name.
      Tests: `test_signup.py` (hook + register endpoint) +
      `test_new_user_gets_default_plant_collection` (Firebase).)
- [x] M6/M9/M8 contracts corrected; M8 covered by rate-limit tests.
      (done 2026-06-10 — M6: garden destroy OpenAPI now says hard-delete (verified
      both `destroy` overrides call `super().destroy()`); M9: false DEPRECATED note
      removed from the live `csrf_token_view` (web falls back to `/api/csrf/`);
      M8: unreachable `Ratelimited` branch + misleading comment removed —
      `test_retry_after.py` + `test_rate_limiting.py` green (11 passed).)
- [x] M11 magic numbers replaced by constants.
      (done 2026-06-10 — `security.py` now sources `SUSPICIOUS_ACTIVITY_THRESHOLD`,
      `API_RATE_LIMIT_WINDOW`, `API_RATE_LIMIT_MAX_REQUESTS` from `constants.py`;
      values unchanged 10/60/30.)
- [x] L4/L6 addressed; full backend suite green.
      (done 2026-06-10 — L4: `CareReminder.get_interval()` single-sources the
      frequency→interval map across the model + the ICS and calendar generators;
      L6: misleading narrow-list-plus-`Exception` swallows in
      `_post_request_tracking` made honest `except Exception` + debug log. Full
      suite: **695 passed, 8 skipped**.)

## Work Log

### 2026-06-10 - Completed by completing-todos skill (run 2026-06-10-0251)

- Verification: all 6 acceptance criteria passed; targeted suites green
  (retry_after/rate_limiting 11, serializers 4, services 17, users 107) and the
  **full backend suite 695 passed / 8 skipped**.
- Key judgment calls (advisor-reviewed): M4 is behavior-preserving (helper's
  request-aware fallback matches each call site's current output — the relative
  serializer is served without request context); M7 centralizes only the
  collection side-effect, NOT username collision (Firebase UUID format is
  test-pinned); M1 keeps `get_top_suggestions` (test-only) but routes it through
  the shared parser rather than deleting it.
- Review: deferred to the run's end-of-sweep code-review-orchestrator pass
  (security + api-design reviewers included — M7/M8/M4 touch auth, the 429 path,
  and API contracts).

### 2026-06-10 - Started by completing-todos skill (run 2026-06-10-0251)

- Picked up by automated workflow. Security-adjacent findings (M7 signup, M8
  429 path, M11/L6 in `core/security.py`) handled directly, not delegated.

### 2026-06-09 - Created

- Deferred from the 2026-06-09 maintainability audit (fix-now batch was
  dead-code + hollow-tests). Grouped backend duplication/contracts findings.

## Notes

p2: no exploitable/user-facing bug, but high maintenance cost (multi-site edits,
false contracts the web SPA / client SDKs rely on). M8 touches the 429 path —
treat as the most delicate item.
