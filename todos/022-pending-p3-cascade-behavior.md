---
status: ready
priority: p3
issue_id: "022"
tags: [data-integrity, database, foreign-keys]
dependencies: []
---

# Add Explicit CASCADE Behavior to Foreign Keys

**CVSS**: N/A (Data integrity issue)

## Problem

Foreign key relationships in models.py lack explicit `on_delete` behavior, relying on Django defaults. This creates ambiguity and potential data loss risks.

## Findings

**data-integrity-guardian**:
- `PlantIdentificationResult.user` (line 525): Missing explicit `on_delete`
- `PlantIdentificationResult.plant_species` (line 530): Missing explicit `on_delete`
- Risk: Deleting a user could cascade delete all their plant identifications without clear intent
- Risk: Deleting a plant species could cascade delete identification results

## Proposed Solutions

### Option 1: Explicit CASCADE (Recommended)
```python
user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,  # Explicit: delete results when user deleted
    related_name='plant_identifications'
)

plant_species = models.ForeignKey(
    'PlantSpecies',
    on_delete=models.SET_NULL,  # Preserve results, mark species as deleted
    null=True,
    blank=True,
    related_name='identification_results'
)
```

**Pros**: Clear intent, prevents accidental data loss
**Cons**: Requires migration, team decision on cascade policy
**Effort**: 30 minutes
**Risk**: Low (migration is reversible)

### Option 2: Keep Django Defaults
**Pros**: No migration needed
**Cons**: Ambiguous behavior, potential data loss
**Risk**: Medium (data integrity)

## Recommended Action

**Option 1** - Add explicit `on_delete` behavior:
1. Review all foreign keys in models.py
2. Document CASCADE policy decisions
3. Create migration with explicit behavior
4. Update model documentation

## Technical Details

**Location**: `backend/apps/plant_identification/models.py`
- Line 525: `PlantIdentificationResult.user`
- Line 530: `PlantIdentificationResult.plant_species`

**Django defaults**:
- `on_delete=models.CASCADE` is the default
- Making it explicit improves code clarity

**CASCADE policy considerations**:
- User deletion: Should CASCADE (GDPR right to be forgotten)
- Plant species deletion: Should SET_NULL (preserve research data)

## Resources

- Django on_delete options: https://docs.djangoproject.com/en/5.2/ref/models/fields/#django.db.models.ForeignKey.on_delete
- Data retention policies: Consider GDPR Article 17
- Related models: Check UserProfile, GardenEntry for consistency

## Acceptance Criteria

- [ ] All foreign keys have explicit `on_delete` behavior
- [ ] CASCADE policy documented in models.py docstrings
- [ ] Migration created and tested
- [ ] Tests verify cascade behavior (user deletion, species deletion)
- [ ] No unintended data loss in test scenarios

## Work Log

- 2025-10-25: Issue identified by data-integrity-guardian agent

## Notes

**Priority rationale**: P3 (Medium) - Not critical but improves data integrity clarity
**Related issues**: Part of broader data retention policy review
