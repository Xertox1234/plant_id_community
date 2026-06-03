# Remove Legacy `/requests/` Plant-ID Stack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the unused legacy `/requests/` plant-ID processing stack (DRF viewset, Celery task, `identify_plant_from_request` + fake-fallback chain, websocket consumer, and their tests) while leaving the shared models, `get_service_status`, and the live `/identify/` path untouched.

**Architecture:** Pure deletion. No DB migration — the `PlantIdentificationRequest`/`Result` models stay (they are FK targets and demo-data/stats/blog dependencies). Each task removes one coherent unit, then verifies with `manage.py check` + a targeted grep, and commits. The whole-suite + OpenAPI + dangling-reference sweep runs at the end.

**Tech Stack:** Django 5 / DRF, Celery, Django Channels (websockets), pytest via `manage.py test`, flake8/black/isort (pre-commit), kimi-review commit gate.

**Spec:** `docs/superpowers/specs/2026-06-03-remove-legacy-plant-id-requests-stack-design.md`

**Branch:** `chore/remove-legacy-plant-id-requests-stack` (already created off `main`).

**Working directory for all commands:** `/Users/williamtower/projects/plant_id_community/backend` unless stated otherwise. Activate the venv first: `source venv/bin/activate`.

---

## Pre-flight (run once)

- [ ] **Step 0.1: Confirm branch + clean tree**

Run (from repo root `/Users/williamtower/projects/plant_id_community`):

```bash
git branch --show-current && git status --short
```

Expected: `chore/remove-legacy-plant-id-requests-stack` and no uncommitted changes (the spec commit `64ff37f` is already in).

- [ ] **Step 0.2: Baseline — the suite is green before we start**

Run (from `backend/`, venv active):

```bash
python manage.py test apps.plant_identification --keepdb 2>&1 | tail -3
```

Expected: ends with `OK` (this is the "before" reference; the count drops as we delete tests).

---

## Task 1: Remove the legacy tests

Removing tests first means subsequent code deletions can't leave the suite importing deleted symbols.

**Files:**

- Delete: `apps/plant_identification/tests/test_autoretry.py`
- Delete: `apps/plant_identification/tests/test_celery_idempotency.py`
- Modify: `apps/plant_identification/test_services.py` (remove the `identify_plant_from_request` tests)
- Modify: `apps/plant_identification/test_api.py` (remove the `requests`-create tests)

- [ ] **Step 1.1: Delete the two task/autoretry test files**

```bash
git rm apps/plant_identification/tests/test_autoretry.py \
       apps/plant_identification/tests/test_celery_idempotency.py
```

- [ ] **Step 1.2: Find the `identify_plant_from_request` tests in `test_services.py`**

Run:

```bash
grep -n "identify_plant_from_request\|class TestServiceIntegration\|class TestPlantIdentificationServiceWorkflow\|def test_" apps/plant_identification/test_services.py
```

Identify every test method that calls `self.service.identify_plant_from_request(...)` (e.g. `test_complete_identification_workflow`, `test_identification_failure_handling`, `test_low_confidence_handling`, and any enrichment/integration test that calls it). Note their line ranges.

- [ ] **Step 1.3: Remove those test methods (and any now-empty test class)**

Edit `apps/plant_identification/test_services.py`: delete each test method identified in 1.2. If a test class (e.g. a workflow/integration class) becomes empty, delete the class too. **Keep** `TestPlantNetAPIService` and any test that does not touch `identify_plant_from_request`. Remove now-unused imports flake8 flags in step 1.5.

- [ ] **Step 1.4: Find and remove the `requests`-create tests in `test_api.py`**

Run:

```bash
grep -n "requests-list\|requests-detail\|identification_request\|def test_" apps/plant_identification/test_api.py
```

Delete the tests that POST to / read the `requests` viewset endpoint (e.g. `test_create_identification_request_authenticated`, `test_create_identification_request_unauthenticated`, and any `requests-detail`/`status`/`results`-action test). Keep disease, species, and other unrelated tests.

- [ ] **Step 1.5: Lint the two modified test files**

```bash
flake8 apps/plant_identification/test_services.py apps/plant_identification/test_api.py
```

Expected: no output. If F401 unused-import errors appear, remove those imports and re-run.

- [ ] **Step 1.6: Run the remaining plant_identification suite**

```bash
python manage.py test apps.plant_identification --keepdb 2>&1 | tail -3
```

Expected: `OK` (fewer tests than the baseline; nothing references the deleted symbols yet because the production code still exists).

- [ ] **Step 1.7: Commit**

```bash
git add -A
git commit -m "chore: remove legacy /requests/ plant-ID tests (stack retirement)"
```

---

## Task 2: Remove the `PlantIdentificationRequestViewSet` and its route

This removes the sole HTTP entry point and the only production caller of `run_identification` and `identify_plant_from_request`.

**Files:**

- Modify: `apps/plant_identification/views.py` (delete the class, currently ~L128–293; remove now-unused imports at ~L60, ~L69, ~L72)
- Modify: `apps/plant_identification/urls.py` (remove `router.register(r"requests", …)`, currently ~L78–80)

- [ ] **Step 2.1: Delete the viewset class**

In `apps/plant_identification/views.py`, delete the entire `class PlantIdentificationRequestViewSet(viewsets.ModelViewSet):` block (from `class PlantIdentificationRequestViewSet` down to — but NOT including — the next `class PlantIdentificationResultViewSet`). This includes its `create`/`perform_create`/`retrieve`/`status`/`results`/`process_now` methods.

> Do NOT touch `class PlantDiseaseRequestViewSet`'s own `process_now` (a different class, ~L912). Only the one inside `PlantIdentificationRequestViewSet` goes.

- [ ] **Step 2.2: Remove the `requests` router registration**

In `apps/plant_identification/urls.py`, delete the line(s):

```python
router.register(
    r"requests", views.PlantIdentificationRequestViewSet, basename="requests"
)
```

Leave all other `router.register(...)` lines (species, results, plants, disease-*) intact, and leave the `get_service_status` health route intact.

- [ ] **Step 2.3: Prune now-unused imports in `views.py` (flake8-guided)**

```bash
flake8 apps/plant_identification/views.py apps/plant_identification/urls.py
```

Expected after pruning: no output. flake8 will flag (remove these):

- `from .tasks import run_identification` (now unused)
- `PlantIdentificationRequestSerializer` in the views import block (still imported independently by `apps/users/views.py`, but no longer used in `plant_identification/views.py`)
- `PlantIdentificationService` import in `views.py` **only if** flake8 reports it unused (it is used solely by the deleted viewset).
Do NOT remove `PlantIdentificationResultSerializer` (still used by `PlantIdentificationResultViewSet` and elsewhere) or `Count` unless flake8 says it's unused.

- [ ] **Step 2.4: Django system check + OpenAPI schema**

```bash
python manage.py check 2>&1 | tail -3
python manage.py spectacular --file /tmp/schema.yml 2>&1 | tail -3
```

Expected: `System check identified no issues` and a clean schema generation (no errors about missing `requests` routes/serializers).

- [ ] **Step 2.5: Run the suite**

```bash
python manage.py test apps.plant_identification apps.users --keepdb 2>&1 | tail -3
```

Expected: `OK`. (Includes `apps.users` because its views import the shared serializers / model.)

- [ ] **Step 2.6: Commit**

```bash
git add -A
git commit -m "chore: remove PlantIdentificationRequestViewSet + /requests/ route"
```

---

## Task 3: Delete the Celery task module

Nothing imports `run_identification` anymore (the viewset that did is gone, tests are gone).

**Files:**

- Delete: `apps/plant_identification/tasks.py`

- [ ] **Step 3.1: Confirm no remaining importers**

```bash
grep -rn "from .tasks import\|plant_identification.tasks\|run_identification\|IdentificationTask" apps --include="*.py" | grep -v "/tasks.py:"
```

Expected: no output. If anything appears, stop and remove that reference first.

- [ ] **Step 3.2: Delete the file**

```bash
git rm apps/plant_identification/tasks.py
```

- [ ] **Step 3.3: System check (Celery autodiscovery tolerates a missing tasks.py)**

```bash
python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues`.

- [ ] **Step 3.4: Commit**

```bash
git add -A
git commit -m "chore: delete dormant run_identification Celery task"
```

---

## Task 4: Remove the websocket consumer + its route

The `IdentificationConsumer` (group `plant_id_req_*`) only ever received events from `run_identification`. No client connects to it.

**Files:**

- Delete: `apps/plant_identification/consumers.py`
- Modify: `plant_community_backend/routing.py` (remove the import + path → empty list)

- [ ] **Step 4.1: Confirm the consumer is unreferenced except by routing**

```bash
grep -rn "IdentificationConsumer\|plant_id_req\|consumers" apps plant_community_backend --include="*.py" | grep -v "/consumers.py:"
```

Expected: only `plant_community_backend/routing.py` references it.

- [ ] **Step 4.2: Empty out the websocket routing**

Replace the contents of `plant_community_backend/routing.py` with:

```python
# WebSocket routes. The plant-identification request consumer was removed with
# the legacy /requests/ stack (2026-06-03); no live websocket routes remain.
websocket_urlpatterns = []
```

- [ ] **Step 4.3: Delete the consumer file**

```bash
git rm apps/plant_identification/consumers.py
```

- [ ] **Step 4.4: System check (ASGI imports routing at startup)**

```bash
python manage.py check 2>&1 | tail -3
python -c "import plant_community_backend.routing as r; print('ws routes:', r.websocket_urlpatterns)"
```

Expected: no issues; prints `ws routes: []`.

- [ ] **Step 4.5: Commit**

```bash
git add -A
git commit -m "chore: remove IdentificationConsumer websocket (legacy /requests/ stack)"
```

---

## Task 5: Slim `PlantIdentificationService` to `__init__` + `get_service_status`

Every method in the `identify_plant_from_request` chain is called only by that chain (verified). Once it goes, all its helpers are dead. Keep only what the `urls.py` health route needs (`get_service_status`).

**Files:**

- Modify: `apps/plant_identification/services/identification_service.py`

- [ ] **Step 5.1: Delete the legacy method chain + module constant**

In `apps/plant_identification/services/identification_service.py`, delete these methods in full:

- `identify_plant_from_request`
- `_identify_with_plantnet`
- `_identify_with_trefle_search`
- `_enrich_with_trefle_data`
- `_find_or_create_species_from_suggestion`
- `_find_or_create_species_from_data`
- `_update_species_with_data`
- `_update_species_with_trefle_data`
- `add_to_user_collection`
- `_get_local_species_matches`
- `_create_fallback_result`
- `_create_fallback_results`

Also delete the module-level `RETRYABLE_EXCEPTIONS = (…)` constant and its comment block (added in PR #333).

**Keep:** the module docstring, `ProgressCallback` type alias **only if still referenced** (it is a param type on `identify_plant_from_request`, which is being removed — so remove it too if flake8/grep shows it unused), the `class PlantIdentificationService`, its `__init__`, and `get_service_status`.

- [ ] **Step 5.2: Prune now-unused imports (flake8-guided)**

```bash
flake8 apps/plant_identification/services/identification_service.py
```

Remove every F401 the linter reports. Expected unused after the cut: `requests`, `ExternalAPIError`, `APIUnavailable`, `RateLimitExceeded`, `timezone`, `PlantIdentificationRequest`, `PlantIdentificationResult`, `UserPlant`, `Callable`/`List`/`Dict` typing names not used by the survivors, and possibly `settings`. **Keep** whatever `__init__`/`get_service_status` use: `logging`, `PlantNetAPIService`, `TrefleAPIService`, `AIPlantCareService`, and `Dict`/`Optional` if still referenced. Re-run flake8 until it is silent.

- [ ] **Step 5.3: Confirm `get_service_status` is intact and importable**

```bash
python -c "from apps.plant_identification.services.identification_service import PlantIdentificationService as S; print('get_service_status' in dir(S), 'identify_plant_from_request' not in dir(S))"
```

Expected: `True True`.

- [ ] **Step 5.4: System check + the health route still works**

```bash
python manage.py check 2>&1 | tail -3
```

Expected: `System check identified no issues`.

- [ ] **Step 5.5: Run the suite (service tests + users + blog use the model/helpers)**

```bash
python manage.py test apps.plant_identification apps.users apps.blog --keepdb 2>&1 | tail -3
```

Expected: `OK`.

- [ ] **Step 5.6: Commit**

```bash
git add -A
git commit -m "chore: slim PlantIdentificationService to status-only (remove legacy chain)"
```

---

## Task 6: Remove the dead `PlantIdentificationRequestCreateSerializer`

It has zero references anywhere (the viewset used `serializer_class` directly, never this one).

**Files:**

- Modify: `apps/plant_identification/serializers.py`

- [ ] **Step 6.1: Re-confirm it is unreferenced**

```bash
grep -rn "PlantIdentificationRequestCreateSerializer" apps web plant_community_mobile --include="*.py" 2>/dev/null | grep -v "class PlantIdentificationRequestCreateSerializer"
```

Expected: no output.

- [ ] **Step 6.2: Delete the class**

In `apps/plant_identification/serializers.py`, delete the entire `class PlantIdentificationRequestCreateSerializer(serializers.ModelSerializer):` block (currently ~L400–425). **Keep** `PlantIdentificationRequestSerializer`, `PlantIdentificationResultSerializer`, and `PlantIdentificationRequestWithResultsSerializer` — all three are used by `apps/users/views.py` and/or `PlantIdentificationResultViewSet`.

- [ ] **Step 6.3: Lint + check**

```bash
flake8 apps/plant_identification/serializers.py && python manage.py check 2>&1 | tail -3
```

Expected: no flake8 output; `System check identified no issues`.

- [ ] **Step 6.4: Commit**

```bash
git add -A
git commit -m "chore: remove dead PlantIdentificationRequestCreateSerializer"
```

---

## Task 7: Documentation

**Files:**

- Modify: `backend/docs/development/CELERY_INTEGRATION_TODOS.md`
- Move + edit: `todos/211-pending-p3-celery-disabled-sync-path-resilience.md` → `todos/archive/211-completed-…`

- [ ] **Step 7.1: Note the retirement in the Celery integration doc**

In `backend/docs/development/CELERY_INTEGRATION_TODOS.md`, add a short dated note near the top stating: the plant-ID async stack (`run_identification` task + `/requests/` viewset + `identify_plant_from_request`) was **removed** on 2026-06-03 in favor of the synchronous `/identify/` → `CombinedPlantIdentificationService` path. The disease-diagnosis and scheduled-notification TODOs in that doc are unaffected.

- [ ] **Step 7.2: Close todo 211**

Edit `todos/211-pending-p3-celery-disabled-sync-path-resilience.md`: set frontmatter `status: completed`, check off its acceptance criteria (the fake fallback is gone with the stack; the decision was "retire, not enable"), and append a Work Log entry referencing this plan + PR. Then:

```bash
git mv todos/211-pending-p3-celery-disabled-sync-path-resilience.md \
       todos/archive/211-completed-p3-celery-disabled-sync-path-resilience.md
```

- [ ] **Step 7.3: Commit**

```bash
git add -A
git commit -m "docs: retire plant-ID async stack; close todo 211"
```

---

## Task 8: Final verification sweep

- [ ] **Step 8.1: Dangling-reference sweep across CODE files (strict)**

This must be clean — a live reference to a removed symbol in code breaks the app. Run (from repo root):

```bash
grep -rn "run_identification\|IdentificationTask\|identify_plant_from_request\|IdentificationConsumer\|_create_fallback_result\|RETRYABLE_EXCEPTIONS\|PlantIdentificationRequestViewSet\|PlantIdentificationRequestCreateSerializer\|requests-list\|requests-detail\|plant_id_req" \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.dart" .
```

Expected: **no output.** Any hit here is a real dangling reference — fix it before continuing.

- [ ] **Step 8.2: Doc-reference check (informational — do NOT edit history)**

```bash
grep -rln "run_identification\|identify_plant_from_request\|IdentificationConsumer\|PlantIdentificationRequestViewSet" --include="*.md" . | grep -v "docs/superpowers/"
```

Historical records legitimately mention the old symbols and are **left as-is**: `docs/LEARNINGS.md` (append-only), `docs/audits/*`, `docs/reviews/*`, `PLANNING/*`, and `backend/docs/architecture/*` (point-in-time analysis). The **only** docs this PR edits are the two in Task 7 (`CELERY_INTEGRATION_TODOS.md` and archived todo 211). Do not rewrite audits, reviews, LEARNINGS, or architecture docs — that is out of scope and corrupts the historical record.

- [ ] **Step 8.3: Django check + OpenAPI**

```bash
cd backend && source venv/bin/activate
python manage.py check 2>&1 | tail -3
python manage.py spectacular --file /tmp/schema.yml 2>&1 | tail -3
```

Expected: no issues; schema generates cleanly.

- [ ] **Step 8.4: Full affected-app suite**

```bash
python manage.py test apps.plant_identification apps.users apps.blog --keepdb 2>&1 | tail -4
```

Expected: `OK`.

- [ ] **Step 8.5: Confirm the live path is intact**

```bash
grep -n "def identify_plant\|CombinedPlantIdentificationService" apps/plant_identification/api/simple_views.py | head
python -c "from apps.plant_identification.api import simple_views; print('identify_plant' in dir(simple_views))"
```

Expected: prints `True` — the `/identify/` view is untouched.

- [ ] **Step 8.6: Push + open PR**

```bash
git push -u origin chore/remove-legacy-plant-id-requests-stack
gh pr create --base main --title "Remove legacy /requests/ plant-ID processing stack" --body-file <(cat <<'EOF'
Removes the unused legacy plant-ID processing stack (requests viewset, run_identification Celery task, identify_plant_from_request + fake Rosa/Monstera/Ficus fallback, IdentificationConsumer websocket, and their tests). The live /identify/ → CombinedPlantIdentificationService path and the shared PlantIdentificationRequest/Result models are untouched — no DB migration.

Spec: docs/superpowers/specs/2026-06-03-remove-legacy-plant-id-requests-stack-design.md
Closes todo 211. Supersedes the autoretry work in #333 (that stack is being retired).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

---

## Notes for the executor

- **Line numbers are references, not anchors.** They shift as you delete. Anchor on the symbol names and confirm with the grep/`manage.py check` step in each task.
- **flake8 is your scalpel for imports.** After each code deletion, run flake8 on the touched file and remove exactly what it flags — no more, no less.
- **`manage.py check` between tasks** is the cheap guard that catches a broken import before the test suite does.
- **Never touch** the `PlantIdentificationRequest`/`Result` models, `simple_views`, `CombinedPlantIdentificationService`, `apps/users` or `apps/blog` logic, or any `process_now`/serializer that is not the ones named here.
- **Commit gate:** pre-commit runs flake8 + kimi-review; markdownlint may reformat `.md` files in place and abort the commit — if so, `git add` the reformatted file and re-run the commit.
