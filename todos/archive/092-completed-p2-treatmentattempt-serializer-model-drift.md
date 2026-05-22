---
status: completed
priority: p2
issue_id: "092"
tags: [api, drf, openapi, plant-identification, bug]
dependencies: []
---

# TreatmentAttemptSerializer references ~12 non-existent model fields (schema break + runtime 500)

## Problem

`TreatmentAttemptSerializer` (`apps/plant_identification/serializers.py:624`) lists
a `Meta.fields` set that is badly out of sync with the `TreatmentAttempt` model
(`apps/plant_identification/models.py:1487`). OpenAPI schema generation aborts:

```
django.core.exceptions.ImproperlyConfigured: Field name `uuid` is not valid for
model `TreatmentAttempt` in
`apps.plant_identification.serializers.TreatmentAttemptSerializer`.
```

`uuid` is only the *first* offender drf-spectacular hits; the serializer also
declares many other fields the model does not have. Because the serializer is
wired to live views, any request that serializes a `TreatmentAttempt` raises the
same `ImproperlyConfigured` and returns **HTTP 500** at runtime — not just a docs
break.

This is the next instance of the same class as todo 090
(`ForumPostImageSerializer`): 090 fixed the first serializer drf-spectacular hit,
so generation now proceeds far enough to hit this one.

## Findings

- **Pre-existing on `main`** — `git diff main` shows no change to the
  `TreatmentAttempt` region of `serializers.py`. Not introduced by the audit branch.
- **Live endpoint, not dead code** — `TreatmentAttemptSerializer` is used at
  `apps/plant_identification/views.py:1127` (`many=True`), `:1156` (single), and
  as `serializer_class` at `:1277`. Confirm whether the viewset is routed; if so
  the endpoint 500s on every call.
- **Field mismatches** (serializer field → model reality):
  - `uuid` → model has **no** uuid field (crashes first).
  - `user`, `username` (`source="user.username"`) → model has **no** `user` FK;
    it has `saved_diagnosis` (FK to `SavedDiagnosis`) and `treatment` (FK to
    `DiseaseCareInstructions`). The user is reachable via the diagnosis, not directly.
  - `diagnosis_result`, `diagnosis_info` (`source="diagnosis_result"`),
    `disease_name` (`source="diagnosis_result.suggested_disease_name"`) → model
    has `saved_diagnosis`, not `diagnosis_result`.
  - `treatment_name`, `treatment_type`, `application_method`, `dosage_frequency`,
    `expected_duration`, `completion_notes` → no such model fields.
  - `start_date` → model field is `started_date`.
  - `completion_date` → model field is `completed_date`.
  - `completed` → model field is `success` (BooleanField).
  - `effectiveness` → model field is `effectiveness_rating` (IntegerField).
  - `notes` → model field is `user_notes`; model also has `side_effects`.
  - Real model fields: `saved_diagnosis`, `treatment`, `started_date`,
    `completed_date`, `effectiveness_rating`, `success`, `user_notes`,
    `side_effects`, `created_at`, `updated_at` (+ implicit `id`).
- Likely a copy-paste from a sibling serializer — `SavedCareInstructions`
  (`models.py:1545`) *does* have a `uuid` field (`:1555`), which is probably where
  the stale field list originated.
- **There may be more breaks behind this one.** drf-spectacular aborts on the
  first `ImproperlyConfigured`, so whoever fixes this must re-run the gate
  iteratively (`python manage.py spectacular --file /dev/null`) until it exits 0 —
  do not assume `TreatmentAttempt` is the last offender.
- Note: the old `backend/test_schema.py` (`SchemaGenerator().get_schema()`)
  reported exit 0 in todo 090 *despite* this break — the new
  `manage.py spectacular` gate (todo 091) is strictly stricter and is what
  surfaced it.

## Recommended Action

Reconcile `TreatmentAttemptSerializer.Meta.fields` (and the declared
`SerializerMethodField`/`source=` fields) with the actual `TreatmentAttempt`
model — this is an API-contract decision, not a mechanical rename:

1. **Default (lowest risk):** rewrite the serializer to expose the fields that
   actually exist on the model, renaming the source-based fields to real
   relations (e.g. derive the username via `saved_diagnosis` → user if a
   SavedDiagnosis has a user FK; expose `started_date`/`completed_date`/
   `success`/`effectiveness_rating`/`user_notes`/`side_effects`). The endpoint
   currently 500s, so no consumer can depend on the present (non-existent)
   shape — aligning to the model is safe.
2. **Or, if the richer field set is a genuine product requirement,** add the
   missing model fields + a migration. Heavier; only if those fields are wanted.

Check the React/Flutter treatment-attempt consumers (if any) before finalizing
the response shape.

## Acceptance Criteria

- [x] `python manage.py spectacular --file /dev/null` exits 0 (run iteratively —
      fix every `ImproperlyConfigured` it surfaces, not just `TreatmentAttempt`).
- [x] `TreatmentAttemptSerializer(instance).data` returns a dict without raising
      (unit test in `apps/plant_identification/`), proving the serializer↔model
      field drift is resolved (the same `ImproperlyConfigured` that 500s the
      endpoint at runtime).
- [x] `python manage.py test apps.plant_identification --noinput` passes.

## Relationship to other todos

- **Blocks todo 091** (CI schema-validation guard): 091's
  `spectacular` step is added to `backend-ci.yml`, but the job will be red until
  this break (and any behind it) is fixed. 091 is held `in_progress` pending this.

## Work Log

### 2026-05-21 - Created

- Discovered while implementing todo 091 (CI schema guard, run 2026-05-21-2253).
  Running the new gate locally surfaced this pre-existing break. Filed separately
  rather than rewriting a user-data API contract inside 091's p3 CI-hardening PR
  (per the "don't bundle unrelated work" precedent set by todo 090).

### 2026-05-21 - Implemented + verified (run 2026-05-21-2253)

- **Picked up to unblock todo 091** after the goal sweep required all four goal
  todos completed (091 was held only by this break).
- **Fix** (`apps/plant_identification/serializers.py` `TreatmentAttemptSerializer`):
  rewrote `Meta.fields` to the real model columns (`id`, `saved_diagnosis`,
  `treatment`, `started_date`, `completed_date`, `effectiveness_rating`,
  `success`, `user_notes`, `side_effects`, `created_at`, `updated_at`) and
  replaced the phantom `user`/`diagnosis_result`-based declared fields with two
  read-only derived fields: `username` (`source="saved_diagnosis.user.username"`)
  and `treatment_name` (`source="treatment.treatment_name"`). Both traversals are
  proven by the model's `__str__`.
- **No cascade:** after this single fix, `python manage.py spectacular --file
  /dev/null` → `SPEC_EXIT=0` (no further `ImproperlyConfigured`). `TreatmentAttempt`
  was the last offender behind todo 090's `ForumPostImage` fix.
- **Criterion 2:** new `apps/plant_identification/tests/test_serializers.py`
  (`TreatmentAttemptSerializerTest`) builds `.data` from real (in-memory) model
  instances and asserts it returns a dict, the derived fields resolve
  (`username`, `treatment_name`), and no phantom keys leak → `Ran 1 test ... OK`.
  In-memory instances are sufficient because the old `ImproperlyConfigured` fired
  at serializer field-build time, independent of persistence; the full DB chain
  (User→PlantDiseaseRequest→PlantDiseaseResult→SavedDiagnosis +
  PlantDiseaseDatabase→DiseaseCareInstructions, incl. a FileField) is
  disproportionate.
- **Criterion 3:** `python manage.py test apps.plant_identification --noinput` →
  `Ran 109 tests in 58.881s / OK`.

### 2026-05-21 - Code review (orchestrator → django-drf + api-design + test-quality)

- **0 blocking findings.** Reviewer confirmed every `Meta.fields` entry resolves,
  both derived fields are `read_only`, no N+1, and the test genuinely exercises
  the field-build regression path with real (non-mock) instances.
- 1 low (test method name convention) — **fixed** (renamed to
  `test_treatment_attempt_serializer_data_builds_with_real_model_fields`).
- 1 info (the API output shape changed) — harmless: the endpoint previously 500'd,
  so no working consumer depends on the old keys.

### Known issue — out of scope (separate follow-up)

- `TreatmentAttemptViewSet` (`apps/plant_identification/views.py:1271`) is ALSO
  broken at runtime, independent of the serializer: `get_queryset()` filters
  `user=self.request.user` but `TreatmentAttempt` has no `user` field (it's
  `saved_diagnosis.user`); `perform_create()` saves `user=...`; and
  `update_effectiveness()` writes `attempt.effectiveness` (model field is
  `effectiveness_rating`, an int with 1–5 choices, not the string values it
  assigns). The serializer fix clears the schema/`spectacular` break and the
  serializer-level 500, but the viewset's query/write paths remain broken. This
  is a deeper feature-repair (model/viewset/serializer alignment + product intent)
  and should be its own todo before the treatment-attempts endpoint is relied on.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-2253)

- Verification: all 3 acceptance criteria passed (spectacular exit 0; serializer
  `.data` builds; `apps.plant_identification` suite 109 OK).
- Review: 2 findings total, 0 blocking — 1 low fixed, 1 info recorded.

## Notes

p2 — a live runtime 500 on a user-facing endpoint (more severe than 090's
docs-only break) **and** the blocker preventing the 091 CI guard from landing.
