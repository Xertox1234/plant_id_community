---
status: pending
priority: p3
issue_id: "663"
tags: [backend, plant-identification]
dependencies: ["661"]
---

# Tune the identify cross-provider rule from the logged `[MERGE]` lines

## Problem

Todo 661 (PR #1201) shipped an interim rule for picking the top identify answer, with no data behind its
two judgment calls:

- **Agreement promotion:** a species both providers name goes first when it is either provider's top
  answer. If PlantNet's #1 is Plant.id's 5th-place 0.01, it beats Plant.id's own 0.95 #1. The shown
  `confidence` is then 0.01.
- **Disagreement:** Plant.id leads, whatever the raw scores. Before #1201, a higher PlantNet score could
  put PlantNet first.

The owner chose on 2026-10-25 to keep both as they are and tune them from real results.

## Findings

- Each identify with an answer logs one line:
  `[MERGE] plant_id_top=<name> (<probability>) plantnet_top=<name> (<score>) agree=<bool> top_source=<plant_id|plantnet|both>`.
  These are names and scores only. The line comes from `_log_merge` in
  `backend/apps/plant_identification/services/combined_identification_service.py`.
- The lines go to the production Railway service logs. That is the only environment.
- The line records each provider's own #1, not the full lists. If the analysis needs to know where an
  agreed species sat in Plant.id's list, extend the line first.

## Proposed Solutions

### Option 1: Collect, then set thresholds

- **Implementation:**
  - After at least a week of prod identifies, pull the `[MERGE]` lines.
  - Count agree versus disagree. Spot-check disagreements against the photos where the owner knows the
    plant.
  - Decide whether agreement promotion needs a minimum Plant.id probability, and whether a disagreement
    should ever go to PlantNet (for example, when the PlantNet score is above X and Plant.id is below Y).
  - Put any thresholds in `apps/plant_identification/constants.py`.
- **Effort:** 2 h of analysis plus a small code change.
- **Risk:** low to medium, because it changes which plant users see.

## Recommended Action

1. Not before 2026-11-01, and only once #1201 has been deployed for a week: export the `[MERGE]` lines.
2. Owner and Claude review the disagreements, then pick the thresholds.
3. Change `_merge_suggestions` and add tests to `apps/plant_identification/tests/test_merge_ranking.py`.

## Acceptance Criteria

- [ ] A summary of at least a week of `[MERGE]` lines (count, agree rate, notable disagreements) is
      recorded in this todo's Work Log.
- [ ] The owner's threshold decision is recorded here. If the decision is "keep as is", close the todo
      with that reason.
- [ ] Any rule change has tests in `test_merge_ranking.py`, and the full backend `pytest` passes.

## Work Log

### 2026-10-25 - Filed

- Filed with PR #1201 at the owner's request ("keep as is and tune").
