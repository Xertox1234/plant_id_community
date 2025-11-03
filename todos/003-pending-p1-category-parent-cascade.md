---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, data-integrity, django, cascade-policy, forum]
dependencies: []
---

# Category Parent CASCADE - Accidental Thread Deletion Risk

## Problem Statement

Deleting a parent category CASCADE deletes all child categories AND all threads in those categories, risking loss of 900+ threads from a single deletion.

**Location:** `backend/apps/forum/models.py:72-79`

## Findings

- Discovered during data integrity audit by Data Integrity Guardian agent
- **Current Configuration:**
  ```python
  parent = models.ForeignKey(
      'self',
      on_delete=models.CASCADE,  # ❌ Deletes children + all threads
      related_name='children',
  )
  ```
- **Data Loss Scenario:**
  ```
  Category Tree:
  ├─ Plant Care (100 threads)
     ├─ Watering (500 threads)
     ├─ Fertilizing (300 threads)

  Admin deletes "Plant Care" →
    ✅ Deletes "Watering" and "Fertilizing" (CASCADE)
    ❌ Deletes 900 total threads (via Category.threads CASCADE)
  ```
- Accidental deletion risk is HIGH for admin operations

## Proposed Solutions

### Option 1: PROTECT (RECOMMENDED)
```python
parent = models.ForeignKey(
    'self',
    on_delete=models.PROTECT,  # ✅ Prevent deletion if children exist
    null=True,
    blank=True,
    related_name='children',
    help_text='Parent category. PROTECT prevents accidental deletion of category hierarchies.'
)
```

- **Pros**: Prevents accidental cascade deletion, forces intentional cleanup
- **Cons**: Requires deleting children before parent (minor UX issue)
- **Effort**: 1 hour (migration only)
- **Risk**: Low (migration is reversible)

### Option 2: SET_NULL with Manual Reassignment
```python
parent = models.ForeignKey(
    'self',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='children',
)
```

- **Pros**: Allows deletion, children become top-level categories
- **Cons**: Can create unexpected category structure
- **Effort**: 2 hours
- **Risk**: Medium (orphaned categories may confuse users)

## Recommended Action

**Implement Option 1** - Change to PROTECT to prevent accidental cascade deletion.

Add admin interface method:
```python
def delete_queryset(self, request, queryset):
    for category in queryset:
        if category.children.exists():
            messages.error(
                request,
                f"Cannot delete '{category.name}' - contains {category.children.count()} subcategories. "
                f"Delete or move subcategories first."
            )
            return
    super().delete_queryset(request, queryset)
```

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/models.py` (Category model)
  - `backend/apps/forum/admin.py` (Category admin)
  - `backend/apps/forum/migrations/XXXX_category_protect.py` (new)
- **Related Components**: Thread model (threads also CASCADE on category)
- **Database Changes**:
  ```sql
  ALTER TABLE forum_category
    ALTER COLUMN parent_id SET ON DELETE PROTECT;
  ```
- **Migration Risk**: LOW (only affects future deletions)

## Resources

- Data Integrity Guardian audit report (Nov 3, 2025)
- Django PROTECT: https://docs.djangoproject.com/en/5.0/ref/models/fields/#django.db.models.PROTECT
- Forum CASCADE policies analysis

## Acceptance Criteria

- [ ] Migration created to change CASCADE to PROTECT
- [ ] Admin interface shows clear error when attempting to delete parent categories
- [ ] Tests verify protection works (raises ProtectedError)
- [ ] Documentation updated with deletion procedure
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code audit
- Analyzed by Data Integrity Guardian agent
- Categorized as P1 (critical data loss risk)

**Learnings:**
- CASCADE on self-referential ForeignKeys can cause massive deletions
- PROTECT is safer default for hierarchical data
- Admin UX should guide proper deletion order

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Data Integrity Guardian
Severity: CRITICAL - Risk of deleting 900+ threads from single action
Example: Deleting "Plant Care" cascades to "Watering" (500 threads) + "Fertilizing" (300 threads)
