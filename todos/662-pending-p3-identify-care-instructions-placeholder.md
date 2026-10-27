---
status: pending
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

- [ ] `care_instructions` carries no taxonomy keys, with a test.
- [ ] Care data, when present, belongs to the returned `plant_name`'s species, with a test where the
      providers disagree.
- [ ] No identical placeholder care is presented as plant-specific advice on mobile or web.
- [ ] The full backend `pytest` and mobile `flutter test` pass.

## Work Log

### 2026-10-25 - Filed from the PR #1199 sim check

- The results screen showed taxonomy rows under Care Instructions. Reading `_extract_care_info` showed the
  rest of the care text is a fixed placeholder for every plant. Filed at the owner's request.
