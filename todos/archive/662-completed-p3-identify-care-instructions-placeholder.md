---
status: completed
priority: p3
issue_id: "662"
tags: [backend, plant-identification, mobile]
dependencies: []
triage: ready
triaged: 2026-10-27
owner_decision: "Owner chose 'None for now (Recommended)': remove the placeholder care text and the taxonomy rows, return care_instructions null, hide the Care section on mobile and web; Scan 2.0 part 4 brings real care guides later (2026-10-27)"
---

# Identify's "care instructions" are the same placeholder text for every plant, plus taxonomy rows

## Problem

Every identify response carries one fixed set of care strings ("Moderate watering recommended",
"Bright indirect light", …) whatever the plant is. PlantNet's taxonomy (scientific name, family, genus)
is merged into the same dict. The mobile results screen, fixed in PR #1199 to render this dict, now
shows that generic advice under "Care Instructions", plus rows like "Family: Moraceae". A succulent and
a fern get the same watering advice.

## Findings

Found 2026-10-25 by Claude while verifying PR #1199 on the iPhone 17 sim against prod (results screen
screenshot showed "Scientific name", "Family" and "Genus" rows in Care Instructions).

- `backend/apps/plant_identification/services/combined_identification_service.py:457`
  `_extract_care_info` starts from a hard-coded dict (L467–475: `watering`, `light`, `temperature`,
  `humidity`, `fertilizing`, `pruning`, `common_issues: []`). Its own comment says PlantNet returns
  scientific data only, and that care "would need to be enriched from other sources".
- L487 `care_info.update(parse_plantnet_species(species))` adds `scientific_name`, `family` and `genus`
  (`services/plantnet_service.py:47`) to the care dict.
- The care data comes from PlantNet's top result, even when the plant shown came from Plant.id. In the
  fiddle-leaf case, the care dict said *Ficus lyrata* under a *Adenium obesum* heading. See todo 661.
- Mobile: `plant_community_mobile/lib/services/plant_identification_service.dart:153` renders each string
  entry as `"<Label>: <value>"` (`_careLabel`, L171) and skips non-strings, so the taxonomy rows appear and
  `common_issues` doesn't.
- Before #1199 the mobile app never reached the results screen at all, so this was invisible until now.

## Proposed Solutions

### Option 1: Real care data, taxonomy moved out (recommended)

- **Implementation:**
  - Move `scientific_name`/`family`/`genus` out of `care_instructions` into the suggestion. The
    suggestion already carries `family`/`genus` for PlantNet entries.
  - Source care from the identified species. Plant.id v3 can return `watering` and care details as
    suggestion details, and the species DB / Trefle data the app already has is another source.
  - Return `care_instructions: null` when no real data exists, and have the clients hide the section.
- **Pros:** honest output; the care matches the plant shown.
- **Cons:** needs a care source decision.
- **Effort:** half a day to a day.
- **Risk:** low to medium.

### Option 2: Stop the bleeding

- **Implementation:** drop the taxonomy keys from `care_instructions` and label the defaults as "General
  houseplant tips" (or drop them).
- **Pros:** 30 minutes.
- **Cons:** still not plant-specific.
- **Effort:** 30 min.
- **Risk:** low.

## Recommended Action

1. Owner: pick the care source (Plant.id details, species DB, or none for now).
2. Move the taxonomy keys out of `care_instructions`, and check the web client (`web/src/types/plantId.ts`)
   for readers of them.
3. Make care follow the returned top suggestion, not PlantNet's top result.
4. Return null when there's no plant-specific care, and hide the section on mobile and web.

## Technical Details

- `backend/apps/plant_identification/services/combined_identification_service.py`: L290 (care from
  PlantNet), L457–489 (`_extract_care_info`).
- `backend/apps/plant_identification/services/plantnet_service.py:47` (`parse_plantnet_species`).
- `plant_community_mobile/lib/services/plant_identification_service.dart`: L134–175 (care rendering).
- Scan 2.0 Part 3 (results) and Part 4 (premium guides) in
  `docs/superpowers/specs/2026-10-24-scan-2-0-design.md` may own the long-term care content. Check before
  building a care source here.

## Acceptance Criteria

- [x] `care_instructions` carries no taxonomy keys, with a test.
- [x] Care data, when present, belongs to the returned `plant_name`'s species, with a test where the
      providers disagree.
- [x] No identical placeholder care is presented as plant-specific advice on mobile or web.
- [x] The full backend `pytest` and mobile `flutter test` pass.

## Work Log

### 2026-10-25 - Filed from the PR #1199 sim check

- The results screen showed taxonomy rows under Care Instructions. Reading `_extract_care_info` showed the
  rest of the care text is a fixed placeholder for every plant. Filed at the owner's request.

### 2026-10-27 - Implemented by the todo sweep (run 2026-10-27-1646)

- Owner decision "None for now": removed `_extract_care_info` (the fixed placeholder strings plus PlantNet's
  scientific name, family and genus) from `combined_identification_service.py`, and the now-unused
  `TEMPERATURE_RANGE_CELSIUS` constant. Identify's `care_instructions` is always null; the taxonomy stays on
  the suggestions, where `_merge_suggestions` already puts it.
- New `backend/apps/plant_identification/tests/test_care_instructions.py`: no taxonomy keys, null care when
  the providers agree and when they disagree (Adenium vs Ficus), the placeholder strings gone from the
  module, and null through the identify view.
- Mobile: `_careInstructions` returns an empty list instead of the generic "Follow general care guidelines"
  sentence, and `results_screen.dart` hides the Care Instructions card when the list is empty (tests added).
- Web never rendered identify's care; the type now allows null with a note, a test pins that no care text
  shows, and `web/docs/API-Integration.md` shows `"care_instructions": null`.

### 2026-10-27 - Verified by the todo sweep (run 2026-10-27-1646)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider -v --create-db apps/plant_identification/tests/test_care_instructions.py::test_plantnet_taxonomy_never_lands_in_care_instructions apps/plant_identification/tests/test_care_instructions.py::test_no_placeholder_care_when_both_providers_agree apps/plant_identification/tests/test_care_instructions.py::test_the_placeholder_care_text_is_gone_from_the_service` — evidence `.sweep-evidence/g1/662-ac0.txt` (not committed), last lines:

  ```text
  ======================== 3 passed, 2 warnings in 0.29s =========================
  …
  Call stack:
    File "backend/apps/plant_identification/services/combined_identification_service.py", line 149, in _cleanup_executor
      logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider -v --create-db apps/plant_identification/tests/test_care_instructions.py::test_disagreeing_providers_get_no_care_from_the_other_plant apps/plant_identification/tests/test_care_instructions.py::IdentifyResponseCareIsNullTests` — evidence `.sweep-evidence/g1/662-ac1.txt` (not committed), last lines:

  ```text
  ======================== 2 passed, 3 warnings in 19.69s ========================
  …
  Call stack:
    File "backend/apps/plant_identification/services/combined_identification_service.py", line 149, in _cleanup_executor
      logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  ```

- AC 3: `cd plant_community_mobile && flutter test test/services/plant_identification_service_test.dart test/features/results/results_screen_test.dart && cd ../web && npx vitest run src/components/PlantIdentification/IdentificationResults.test.tsx` — evidence `.sweep-evidence/g1/662-ac2.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  6 passed (6)
     Start at  11:12:20
     Duration  502ms (transform 39ms, setup 56ms, import 77ms, tests 69ms, environment 236ms)
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest --create-db -q -p no:cacheprovider && cd ../plant_community_mobile && flutter test` — evidence `.sweep-evidence/g1/662-ac3.txt` (not committed), last lines:

  ```text
  =========== 5723 passed, 8 skipped, 27 warnings in 440.40s (0:07:20) ===========
  …
  01:23 +1390 ~9: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases an unparseable topic_id does not navigate at all (silent no-op, not a crash)
  01:23 +1391 ~9: plant_community_mobile/test/services/push_message_router_service_test.dart: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  01:23 +1392 ~9: All tests passed!
  exit=0
  ```

### 2026-10-27 - Completed by the todo sweep (run 2026-10-27-1646)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
