# Design: Remove the legacy `/requests/` plant-ID processing stack

**Date:** 2026-06-03
**Status:** Approved (design) — pending spec review
**Related:** todo 208 (PR #333, merged), todo 211, `backend/docs/development/CELERY_INTEGRATION_TODOS.md`

## Context

Plant identification has **two parallel stacks** in the backend:

1. **Live path** — `POST /api/v1/plant-identification/identify/` →
   `apps/plant_identification/api/simple_views.py::identify_plant` →
   `CombinedPlantIdentificationService`. Stateless (returns suggestions, persists
   nothing) and already fails honestly (`"Unable to identify plant…"`, no fake
   species). **Both the web app (`web/src/services/plantIdService.ts`) and the
   mobile app (`plant_community_mobile/lib/services/plant_identification_service.dart`)
   use only this endpoint.**

2. **Legacy path** — the `requests` DRF viewset
   (`PlantIdentificationRequestViewSet`) → optional Celery task
   `run_identification` → `PlantIdentificationService.identify_plant_from_request`.
   This path returns **fabricated fallback species** (`Rosa damascena` /
   `Monstera deliciosa` / `Ficus elastica`) on an external-API failure, and its
   Celery side is dormant (`CELERY_ENABLED` is never defined in settings, so the
   create endpoint runs synchronously and the task is never enqueued).

A grep of `web/src` and `plant_community_mobile/lib` finds **zero** references to
the `requests` endpoint or the `plant_id_req_*` websocket. The user has confirmed
`/identify/` is the only active entry point and the `/requests/` stack is
legacy-to-remove.

This recontextualizes todo 208: the autoretry/`on_failure` work merged in PR #333
hardened a path no live client uses. It was a correct fix given what we knew; it
is now being retired along with the rest of the stack.

## Goal

Delete the unused legacy `/requests/` processing/ingestion stack in a single PR,
**without touching the shared `PlantIdentificationRequest`/`PlantIdentificationResult`
models** (and therefore without any DB migration or data change), and without
altering the live `/identify/` path.

## Scope

### Remove

| Area | What goes |
|------|-----------|
| `apps/plant_identification/views.py` | `PlantIdentificationRequestViewSet` (`create`/`perform_create`/`retrieve`/`status`/`results`/`process_now`) + its `from .tasks import run_identification` import + now-unused `PlantIdentificationService` imports in that class |
| `apps/plant_identification/urls.py` | `router.register(r"requests", …)` registration and any now-dead doc strings. **Keep** the health route that calls `PlantIdentificationService().get_service_status()` |
| `apps/plant_identification/tasks.py` | The **entire file** — `run_identification`, `IdentificationTask`, `TERMINAL_STATUSES` (sole task; not beat-scheduled; Celery autodiscovery tolerates its absence) |
| `apps/plant_identification/services/identification_service.py` | `identify_plant_from_request`, `_identify_with_plantnet`, `_enrich_with_trefle_data`, `_identify_with_trefle_search`, `_get_local_species_matches`, `_create_fallback_result`, `_create_fallback_results`, `RETRYABLE_EXCEPTIONS`, and any species/`add_to_user_collection` helpers + imports left unused once that call chain is gone |
| `apps/plant_identification/consumers.py` | `IdentificationConsumer` (entire file) |
| `plant_community_backend/routing.py` | The `IdentificationConsumer` import + `ws/plant-identification/requests/<uuid>/` path → `websocket_urlpatterns = []` |
| `apps/plant_identification/serializers.py` | The request/result serializer(s) used **only** by the deleted viewset (to be confirmed per-class during planning) |
| tests | `tests/test_autoretry.py`, `tests/test_celery_idempotency.py`, and the `identify_plant_from_request` / `requests`-create tests in `test_services.py` and `test_api.py` |

### Keep (shared / live)

- `PlantIdentificationRequest` and `PlantIdentificationResult` **models** — **no
  DB migration, no data touched.** They are FK targets for results, user plants,
  and disease diagnosis, are created for demo-data seeding
  (`apps/users/services.py`), and are read by user-stats aggregation
  (`apps/users/views.py`) and blog plant-data lookups (`apps/blog/services/…`).
- `PlantIdentificationService` the **class** — `get_service_status()` (used by a
  `urls.py` health route) plus only the helpers it still requires.
- The live `/identify/` → `simple_views` → `CombinedPlantIdentificationService`
  path, untouched.
- Demo-data seeding, disease diagnosis, user-stats aggregation, blog lookups.

### Non-goals

- Removing or migrating any model.
- Changing the `/identify/` path or `CombinedPlantIdentificationService`.
- Enabling Celery or building an async results-polling flow (that was todo 211
  Option 1; this PR instead retires the dormant stack and closes 211).

## Removal boundary — how "keep" is enforced

The cut line is: **anything reachable only from `run_identification` or
`PlantIdentificationRequestViewSet` is removed; anything also reachable from the
models, `get_service_status`, the `/identify/` path, demo data, disease, user
stats, or blog is kept.** During planning, each candidate helper in
`identification_service.py` and each serializer class is checked against this rule
before deletion (the verification grep + `manage.py check` catch any miscut).

## Verification strategy

A wide deletion is made safe by mechanical checks, not by eyeballing:

1. **`python manage.py check`** and **`python manage.py spectacular --file /tmp/schema.yml`**
   — catch dangling imports, removed-serializer references, and broken OpenAPI
   routes.
2. **Test suite:** `python manage.py test apps.plant_identification apps.users apps.blog --keepdb`
   — proves the live `/identify/` path, demo-data seeding, disease diagnosis, and
   user-stats aggregation still pass after the cut. No migration changes (the
   models stay), so `--keepdb` is safe and faster.
3. **Dangling-reference sweep:** grep the whole repo (incl. `web/`, mobile, docs)
   for every removed symbol — `run_identification`, `IdentificationTask`,
   `identify_plant_from_request`, `IdentificationConsumer`, `_create_fallback_results`,
   `_create_fallback_result`, `RETRYABLE_EXCEPTIONS`, `requests-list`/`requests-detail`
   — and confirm zero live references remain.
4. **flake8** clean on every touched file (no newly-unused imports left behind).

## Risks & mitigations

- **Dangling reference to a removed symbol** → caught by step 1 (`manage.py check`)
  and step 3 (grep sweep) before commit.
- **A serializer or helper assumed legacy is actually shared** → the boundary rule
  - `manage.py check` + the test suite surface it; keep anything ambiguous.
- **Undocumented external consumer of `POST /requests/`** → user confirmed
  `/identify/` is the only active entry point; accepted.
- **Wide diff** → mitigated by zero behavior change to the live path and the model
  staying intact; the PR is deletions plus small edits to shared files.

## Rollback

Pure code deletion with no migration, so rollback is `git revert` of the PR. No
data or schema implications.

## Documentation updates

- Close todo 211 (the fake-fallback concern is removed with the stack).
- Add a short note in `backend/docs/development/CELERY_INTEGRATION_TODOS.md` that
  the plant-ID async stack was retired in favor of the synchronous `/identify/`
  path (the disease-diagnosis and notification TODOs in that doc are unaffected).
