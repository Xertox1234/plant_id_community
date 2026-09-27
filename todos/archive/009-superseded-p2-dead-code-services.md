---
status: superseded
priority: p2
issue_id: "009"
tags: [code-review, cleanup, technical-debt, YAGNI]
dependencies: []
---

# Delete 4,500 Lines Dead Code (13 Unused Services)

## Problem

69% of service layer (13 files, 4,500 lines) is unused code for unimplemented features.

## Files to Delete

- trefle_service.py (469 lines)
- unsplash_service.py (306 lines)
- pexels_service.py (300 lines)
- monitoring_service.py (329 lines)
- ai_care_service.py (200 lines)
- ai_image_service.py (250 lines)
- disease_diagnosis_service.py (400 lines)
- plant_care_reminder_service.py (500 lines)
- plant_health_service.py (350 lines)
- plant_image_service.py (300 lines)
- species_lookup_service.py (450 lines)
- identification_service.py (400 lines)
- combined_identification_service_original.py (300 lines)

**Effort**: 2-3 hours  
**Impact**: Massive maintainability improvement

## Work Log

### 2026-09-27 - Triage verdict (todo 394)

**Verdict: not done as written; the premise is stale.**

- Only 1 of the 13 files was deleted:
  `combined_identification_service_original.py` in 21e345f6. The other 12
  are still in `backend/apps/plant_identification/services/` (4,758 lines).
- 8 of those 12 have live, non-test importers (trefle, unsplash, pexels,
  ai_image, disease_diagnosis, plant_health, plant_image,
  identification_service). Deleting them now would break the app, so they
  are not re-filed.
- 2 are weakly referenced: monitoring, and species_lookup (through a
  management command and root test scripts).
- 2 are genuinely orphaned:
  - `plant_care_reminder_service.py` is deleted by todo 410 slice B
    (PR #854);
  - `ai_care_service.py` has had no code references since 1b8efa66 (#800).
    Its deletion is filed as todo 467.
