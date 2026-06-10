---
status: pending
priority: p3
issue_id: "223"
tags: [maintainability, audit, cleanup]
dependencies: []
source_review: "docs/audits/2026-06-09-maintainability.md"
source_finding: "L2,L3,L10"
---

# Maintainability: misc low-severity cleanups

## Problem

Small, low-cost maintainability nits from the 2026-06-09 audit that don't fit the
backend-duplication (todo 221) or web (todo 222) groups. Deferred from that audit.

## Findings

Source: `docs/audits/2026-06-09-maintainability.md`.

- **L2** Copy-pasted no-op `if hasattr(image_file, "read")` branch where both
  branches are identical (dead conditional), duplicated verbatim across two
  `_prepare_image` methods — invites an asymmetric "fix" to a branch that does
  nothing. `apps/plant_identification/services/plantnet_service.py:166-169`;
  `plant_health_service.py:71-74`.
- **L3** `images`/`image_thumbnails` model properties byte-identical across two
  sibling request models — paired helpers of the already-drifted M4 serializer
  layer (todo 221). `apps/plant_identification/models.py:432-449,917-934`.
- **L10** Stale TODO claims avatar upload is blocked "when FirebaseStorageService
  is implemented" — but that service is fully implemented and in use. Remove the
  false-dependency comment (or implement avatar upload).
  `plant_community_mobile/lib/services/user_profile_service.dart:180-181`.

## Recommended Action

1. L2: collapse the identical-branch conditional to a single `Image.open(image_file)` in both `_prepare_image` methods.
2. L3: extract the shared `images`/`image_thumbnails` property (coordinate with M4 in todo 221).
3. L10: delete the stale TODO comment, or wire `uploadAvatar()` to the existing `FirebaseStorageService`.

## Technical Details

Per-finding file:line above.

## Acceptance Criteria

- [ ] L2 dead conditional collapsed in both files; plant_identification tests green.
- [ ] L3 model image properties single-sourced.
- [ ] L10 stale TODO removed or avatar upload implemented; `flutter analyze` clean.

## Work Log

### 2026-06-09 - Created

- Deferred from the 2026-06-09 maintainability audit (misc low-severity bucket).

## Notes

p3: cosmetic/quality; no functional impact. L3 is best done together with M4
(todo 221) since they're the model+serializer halves of the same duplication.
