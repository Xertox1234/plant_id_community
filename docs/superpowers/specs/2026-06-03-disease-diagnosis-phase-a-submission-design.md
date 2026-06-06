# Design: Revive disease diagnosis — Phase A (submission flow)

**Date:** 2026-06-03
**Status:** Approved (design) — pending spec review
**Phase:** A of 3 (A = submission · B = save/track/remind · C = async). This spec covers **only Phase A.**

## Context

The plant disease-diagnosis feature is orphaned. `DiagnosisCard`/`DiagnosisReminder`
were deleted **accidentally** — bundled silently into the Garden Calendar Phase 1
commit (#195, migration 0025), whose message never mentions disease. The web has a
save/track/remind UI (`DiagnosisListPage`, `DiagnosisDetailPage`, `DiagnosisCard`,
`SaveDiagnosisModal`, `ReminderManager`) wired via `diagnosisService.ts` to the now
non-existent `diagnosis-cards/` + `diagnosis-reminders/` routes (16/16 calls 404),
and those pages aren't even routed in `App.tsx`.

Critically, **there has never been a disease-diagnosis *submission* flow on web** —
nothing uploads a photo to get a diagnosis. The backend submission path works and is
unwired:

- `POST /api/[v1/]plant-identification/disease-requests/` → `PlantDiseaseRequestViewSet`
  → `PlantDiseaseService.diagnose_disease_from_request` (plant.health API), run
  **synchronously** in `perform_create`.
- `GET /disease-requests/{uuid}/results/` → `{request_id, status, results[]}`.
- `GET /disease-requests/{uuid}/status/` → lightweight status.

Phase A delivers the missing core: a web page to submit and view a diagnosis. It does
**not** touch the save/track layer (Phase B) or async (Phase C).

## Goal

A logged-in user opens `/diagnose`, uploads a sick-plant photo + symptom description,
and sees the AI diagnosis (disease, confidence, severity, treatments) rendered — using
the existing backend, with the minimum change needed to make its response usable.

## Architecture / data flow

1. `/diagnose` — a **protected** route (redirect to login if unauthenticated;
   `disease-requests` requires `IsAuthenticated`, unlike anonymous `/identify`).
2. `DiseaseDiagnosePage` renders a form: photo upload (reuse `FileUpload`), a
   **required** symptoms textarea, and optional `plant_condition` (select) + `location`.
3. Submit → `diseaseService.submitDiagnosis(form)` →
   `POST /api/v1/plant-identification/disease-requests/` (multipart;
   `X-CSRFToken` + `credentials: 'include'`; **versioned** `/api/v1/` URL, matching the
   working `plantIdService` — NOT the unversioned `diagnosisService` pattern that
   targets dead routes).
4. Backend `perform_create` runs `diagnose_disease_from_request` **synchronously**, then
   returns `{request_id, status, ...}`.
5. Web → `diseaseService.getDiagnosisResults(request_id)` →
   `GET /api/v1/plant-identification/disease-requests/{uuid}/results/` →
   `{request_id, status, results[]}` → render.

**Approach choice:** two-call POST→GET-results, reusing the existing `results/` action.
Rejected alternatives: (a) return results inline from POST — couples create to result
shaping, bigger change; (b) poll `status/` until `diagnosed` — unnecessary while
processing is synchronous; it becomes relevant only in Phase C.

## Backend change (the only one)

`PlantDiseaseRequestCreateSerializer` (`apps/plant_identification/serializers.py`)
currently returns only input fields, so the POST response omits the request UUID — the
client can't fetch results. Add two **read-only** fields to its `Meta.fields`:

- `request_id` — so the web can call `results/`.
- `status` — so the web can detect a `failed` diagnosis (the viewset sets `status="failed"`
  on exception but still returns 201).

No model changes, no migration. (The viewset's `get_serializer_class` already returns
this serializer for `create`, so the response picks the new fields up automatically.)

## Web components

All net-new except the reused `FileUpload`. Follow existing conventions
(`web/docs/patterns/react-typescript.md`, `tailwind.md`; cookie auth; `react-router-dom`).

**Single image in Phase A.** The backend accepts `image_1`/`image_2`/`image_3`, but the
existing `FileUpload` component is single-file (so is `/identify`). Phase A sends only
`image_1`; multi-image is a deferred enhancement, not Phase A scope.

| File | Responsibility |
|------|----------------|
| `web/src/services/diseaseService.ts` | `submitDiagnosis(input): Promise<{request_id, status}>` and `getDiagnosisResults(requestId): Promise<DiseaseDiagnosisResults>`. Versioned `/api/v1/` URLs. **Both** include `X-CSRFToken` + `credentials: 'include'` — even the `getDiagnosisResults` GET, matching `plantIdService.getHistory` (which sends CSRF on a GET for consistency). Mirrors `plantIdService` structure. |
| `web/src/pages/diagnosis/DiseaseDiagnosePage.tsx` | The form — reuses `FileUpload` (imported from `web/src/components/PlantIdentification/FileUpload.tsx`; **not** moved to a shared dir in Phase A) — single image + required symptoms textarea + optional `plant_condition`/`location`. Submit/loading/results/error states; renders the results list. |
| `web/src/components/diagnosis/DiseaseDiagnosisResults.tsx` | Presentational list of `PlantDiseaseResult`s: disease name, `confidence_percentage`, `severity_assessment`, `symptoms_identified`, `recommended_treatments`, `immediate_actions`, primary flag. |
| `web/src/types/diagnosis.ts` (edit) | Add a `PlantDiseaseResult` type matching `PlantDiseaseResultSerializer` + a `DiseaseDiagnosisResults` (`{request_id, status, results}`) type. **`status` must use the backend enum** `'pending' \| 'processing' \| 'diagnosed' \| 'needs_help' \| 'failed'` (`models.py:876-881`) — NOT the stale `'completed'` value in the existing unused `DiagnosisResponse` interface. Fix/remove the stale `DiagnosisRequest`/`DiagnosisResponse`/`Disease` types so the enum mismatch can't be reintroduced. |
| `web/src/App.tsx` (edit) | Add a **lazy-loaded** `/diagnose` route. **Place it inside the `ProtectedLayout` → `RootLayout` chain (App.tsx:60-64), beside `/profile` and `/settings`** — NOT in the public `RootLayout` block. Lazy-load like the other non-critical routes. |
| `web/src/components/layout/Header.tsx` (edit) | Add a **"Diagnose"** link next to "Identify" in **both** the desktop nav (~line 50) **and** the mobile menu (~line 131). |

## Error handling

- Form validation: missing image / empty symptoms → inline field errors (mirror the
  backend's two `ValidationError`s).
- Unauthenticated → redirect to `/login` with return-to `/diagnose`.
- Status handling uses the real enum (`models.py:876-881`): `diagnosed` → render results;
  `needs_help` → render results with a "needs community help" note; `failed` (or empty
  `results`) → an honest "Diagnosis unavailable — please try again" message. **No
  fabricated results.**
- Slow synchronous POST: a loading state during the request (accepted latency, same
  pattern as `IdentifyPage`; Phase C async would remove the wait).

## Open item to verify during implementation

Confirm whether `diagnose_disease_from_request` fabricates fake fallback results on a
plant.health API failure (the plant-ID service's `_create_fallback_results` did exactly
this — Rosa/Monstera/Ficus). Phase A does **not** change disease-service internals, but
if it fabricates, the web would render fake diagnoses — flag it as a Phase-A-adjacent
follow-up, don't silently ship fake data behind an honest-looking UI.

## Testing

- **Backend** (`apps/plant_identification`): a test that `POST disease-requests/` returns
  `request_id` + `status` (the new fields), and that `results/` returns the diagnosis —
  mocking the **plant.health API client** (`PlantHealthAPIService`), not the whole
  service (same discipline as the autoretry tests). No DB mocks; strict assertions.
- **Web** (Vitest, matching the `plantIdService.test.ts` convention):
  `web/src/services/diseaseService.test.ts` (mock `fetch`: submit returns `request_id`,
  results shape, CSRF header present) and
  `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx` (submit → renders results;
  `failed` status → error message; validation). Playwright e2e optional (excluded from CI).

## Out of scope (deferred to later phases)

- **Phase B:** saving diagnoses as cards, treatment-status tracking, reminders — requires
  restoring `DiagnosisCard`/`DiagnosisReminder` (or extending `SavedDiagnosis`) +
  routing the existing `DiagnosisListPage`/`DetailPage`. Its own spec.
- **Phase C:** async via Celery (the `views.py` `perform_create` TODO) — needs worker
  infrastructure that doesn't exist; its own effort.
- Mobile disease diagnosis (none today).
- Changing `PlantDiseaseService` internals / its fallback behavior.

## Verification strategy

- `python manage.py check` + `manage.py spectacular` (the new create-response fields
  appear in the schema).
- `python manage.py test apps.plant_identification` → OK.
- `cd web && npm run type-check && npm run lint && npm run test` → clean.
- Manual: log in, open `/diagnose`, submit a photo + symptoms, see a diagnosis.
