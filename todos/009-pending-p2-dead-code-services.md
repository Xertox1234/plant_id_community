---
status: ready
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
