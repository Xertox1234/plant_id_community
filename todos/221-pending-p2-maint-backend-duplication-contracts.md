---
status: pending
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

- [ ] M4 image helpers extracted; one URL shape; contract test added.
- [ ] PlantNet parser single-sourced (M1/L1) with a parser test.
- [ ] Signup side-effects centralized across all 3 paths (M7).
- [ ] M6/M9/M8 contracts corrected; M8 covered by rate-limit tests.
- [ ] M11 magic numbers replaced by constants.
- [ ] L4/L6 addressed; full backend suite green.

## Work Log

### 2026-06-09 - Created

- Deferred from the 2026-06-09 maintainability audit (fix-now batch was
  dead-code + hollow-tests). Grouped backend duplication/contracts findings.

## Notes

p2: no exploitable/user-facing bug, but high maintenance cost (multi-site edits,
false contracts the web SPA / client SDKs rely on). M8 touches the 429 path —
treat as the most delicate item.
