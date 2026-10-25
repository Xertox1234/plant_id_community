---
status: pending
priority: p2
issue_id: "661"
tags: [backend, plant-identification]
dependencies: []
---

# Identify ranks Plant.id and PlantNet answers on different scales, and reports one provider's confidence for the other's plant

## Problem

The combined identify answer can name the wrong plant. On 2026-10-25 a fiddle-leaf fig photo came back as
*Adenium obesum* while PlantNet's own top result was *Ficus lyrata*. The merge sorts both providers'
suggestions by one `probability` key, but the two numbers come from different models and are not
comparable. The response's `confidence` always comes from Plant.id, even when the plant named came
from PlantNet.

## Findings

Found 2026-10-25 by Claude while verifying PR #1199 end to end on the iPhone 17 sim against the prod API
(gallery photo of a fiddle-leaf fig → Identify → results screen).

- **Observed:** the results screen showed *Adenium obesum*. The same response's `care_instructions`
  carried `scientific_name: Ficus lyrata`, which comes from PlantNet's top result
  (`_extract_care_info` reads `results[0].species`). So the two providers disagreed, and the Plant.id
  answer won.
- **Correction to the #1199 PR body:** it says "the merge prefers Plant.id". The code doesn't do that.
  `backend/apps/plant_identification/services/combined_identification_service.py:491`
  `_merge_suggestions` appends Plant.id's top 5 (their `probability`), then PlantNet's top 3. Each
  PlantNet entry gets `"probability": result.get("score", 0)` (L561). The list is then sorted by that
  key across both providers (L571). Plant.id's probability and PlantNet's score are separate model
  outputs on different scales.
- When the providers agree on a species, the PlantNet entry is folded into the Plant.id entry
  (`plantnet_matched`). That only happens on an exact `scientific_name` string match, so a synonym or an
  author-suffix difference counts as disagreement.
- **Confidence mismatch, verified from code:** `results["confidence_score"]` is set from Plant.id only
  (L268). The view (`api/simple_views.py`, `identify_plant`) returns `combined_suggestions[0]` as
  `plant_name`/`scientific_name`, alongside that `confidence`. If a PlantNet suggestion sorts first,
  the client shows PlantNet's plant with Plant.id's confidence for a different plant.
  `get_identification_summary` uses the top suggestion's own probability, so `summary` and
  `confidence` can disagree within one response.
- **Hypothesis, not verified:** for the fiddle-leaf photo, Plant.id's raw Adenium probability was simply
  higher than PlantNet's Ficus score. I didn't capture either number (the identify call goes through
  Cloudflare, and a direct probe was blocked with 1010). It's equally possible that Plant.id was
  confidently wrong and no merge rule would have saved it.

## Proposed Solutions

### Option 1: Rank within a provider, reconcile across them explicitly (recommended)

- **Implementation:**
  - Keep each provider's list in its own order.
  - Pick the top answer by an explicit rule: agreement between providers wins (match on a normalised
    scientific name, genus + species, author stripped). Otherwise take the provider with the higher
    *calibrated* confidence, with thresholds set from logged real results, not from raw scores.
  - Report the confidence of the suggestion actually returned, and add `top_source`.
- **Pros:** the named plant and its confidence always belong together, and agreement is rewarded.
- **Cons:** calibration needs data. Start by logging both providers' top answers and scores.
- **Effort:** half a day plus a logging period.
- **Risk:** medium, because it changes which plant users see.

### Option 2: Plant.id first, PlantNet supplemental only

- **Implementation:** sort Plant.id entries by probability, then append PlantNet entries after them.
  Confidence stays Plant.id's.
- **Pros:** small, and matches what the code comments and docs already claim.
- **Cons:** the fiddle-leaf case would still be wrong.
- **Effort:** 1 h.
- **Risk:** low.

## Recommended Action

1. Add logging of both providers' top suggestion + raw score per identify, without image data or user ids.
2. Fix the confidence mismatch now: return the top suggestion's own probability (or its source's) and
   add `top_source`.
3. Decide the cross-provider rule (Option 1) from a week of logged disagreements.
4. Normalise scientific names before the agreement match.

## Technical Details

- `backend/apps/plant_identification/services/combined_identification_service.py`: L268
  (`confidence_score`), L491–577 (`_merge_suggestions`, sort at L571), L561 (PlantNet score as
  probability).
- `backend/apps/plant_identification/api/simple_views.py`: `identify_plant`, the `top_suggestion` /
  `response_data` block.
- Clients: mobile `plant_community_mobile/lib/services/plant_identification_service.dart` reads
  `plant_name`, `scientific_name`, `confidence`, and `suggestions[0].description`; the web types are
  in `web/src/types/plantId.ts`. An additive `top_source` doesn't break either.
- Related: todo 662 (care data comes from PlantNet's top result even when Plant.id's plant is shown).

## Acceptance Criteria

- [ ] The response's `confidence` belongs to the suggestion returned as `plant_name`, with a test where a
      PlantNet suggestion ranks first.
- [ ] A response says which provider the top answer came from.
- [ ] The cross-provider rule is documented and tested for agree, disagree and single-provider responses,
      including a scientific-name match that differs only by author suffix.
- [ ] The full backend `pytest` passes.

## Work Log

### 2026-10-25 - Filed from the PR #1199 sim check

- Saw *Adenium obesum* for a fiddle-leaf fig, with PlantNet's species *Ficus lyrata* in the same response.
  Read `_merge_suggestions` and found a mixed-scale sort, not the Plant.id-first merge the #1199 body
  described. Filed at the owner's request.
