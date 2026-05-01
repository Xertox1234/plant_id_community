---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, data-integrity, django, cascade-policy]
dependencies: []
---

# CASCADE DELETE on PlantDiseaseResult - Data Loss Risk

## Problem Statement

Deleting a disease entry from `PlantDiseaseDatabase` CASCADE deletes all historical diagnosis results, destroying user data and community knowledge base.

**Location:** `backend/apps/plant_identification/models.py:1342-1350`

## Findings

- Discovered during data integrity audit by Data Integrity Guardian agent
- **Current Configuration:**
  ```python
  identified_disease = models.ForeignKey(
      PlantDiseaseDatabase,
      on_delete=models.CASCADE,  # ❌ DESTROYS historical data
      related_name='diagnosis_results',
  )
  ```
- **Data Loss Scenario:**
  ```
  1. Admin removes outdated "Powdery Mildew" from database
  2. CASCADE DELETE removes 1,243 PlantDiseaseResult records
  3. Users lose all historical diagnosis data
  4. Community knowledge base destroyed
  ```
- Pattern mismatch: `PlantIdentificationResult.identified_species` uses SET_NULL (correct)

## Proposed Solutions

### Option 1: SET_NULL with Fallback (RECOMMENDED)
```python
identified_disease = models.ForeignKey(
    PlantDiseaseDatabase,
    on_delete=models.SET_NULL,  # ✅ Preserve diagnosis data
    null=True,
    blank=True,
    related_name='diagnosis_results',
    help_text="Disease from local database. SET_NULL preserves historical diagnosis data."
)

# In model method:
def get_disease_name(self):
    """Get disease name, falling back to suggested_disease_name."""
    if self.identified_disease:
        return self.identified_disease.common_name
    return self.suggested_disease_name
```

- **Pros**: Preserves all historical data, matches pattern for identified_species
- **Cons**: Requires null handling in queries
- **Effort**: 2 hours (migration + model update + tests)
- **Risk**: Low (migration is reversible)

### Option 2: PROTECT to Prevent Deletion
```python
identified_disease = models.ForeignKey(
    PlantDiseaseDatabase,
    on_delete=models.PROTECT,  # ✅ Block deletion if results exist
    related_name='diagnosis_results',
)
```

- **Pros**: Prevents accidental data loss
- **Cons**: Makes database cleanup difficult (can't remove outdated diseases)
- **Effort**: 1 hour
- **Risk**: Low

## Recommended Action

**Implement Option 1** - Change to SET_NULL to preserve historical data while allowing database cleanup.

## Technical Details

- **Affected Files**:
  - `backend/apps/plant_identification/models.py` (PlantDiseaseResult model)
  - `backend/apps/plant_identification/migrations/XXXX_fix_disease_cascade.py` (new)
- **Related Components**: Disease database management, diagnosis API
- **Database Changes**:
  ```sql
  ALTER TABLE plant_identification_plantdiseaseresult
    ALTER COLUMN identified_disease_id DROP NOT NULL,
    ALTER COLUMN identified_disease_id SET ON DELETE SET NULL;
  ```
- **Migration Risk**: LOW (additive change, no data loss)

## Resources

- Data Integrity Guardian audit report (Nov 3, 2025)
- Related pattern: `PlantIdentificationResult.identified_species` (line 529-536)
- Django on_delete options: https://docs.djangoproject.com/en/5.0/ref/models/fields/#django.db.models.ForeignKey.on_delete

## Acceptance Criteria

- [ ] Migration created to change CASCADE to SET_NULL
- [ ] identified_disease field allows null=True
- [ ] get_disease_name() method handles null case
- [ ] Tests verify historical data preserved when disease deleted
- [ ] Admin interface updated to show fallback name
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code audit
- Analyzed by Data Integrity Guardian agent
- Categorized as P1 (critical data loss risk)

**Learnings:**
- CASCADE policies should preserve historical user data
- SET_NULL allows database cleanup without destroying history
- Consistent pattern with identified_species field

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Data Integrity Guardian
Severity: CRITICAL - Risk of destroying 1000+ diagnosis records
