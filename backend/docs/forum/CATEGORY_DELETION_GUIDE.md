# Category Deletion Guide

**Issue**: #003 - Category Parent CASCADE Protection
**Status**: IMPLEMENTED
**Date**: November 11, 2025

## Problem Summary

Deleting a parent category with the default `CASCADE` behavior would automatically delete:
1. All child categories (subcategories)
2. All threads in those categories
3. All posts in those threads

This creates a **critical data loss risk** where deleting one parent category could cascade delete 900+ threads and thousands of posts.

## Solution Implemented

Changed the `Category.parent` ForeignKey from `CASCADE` to `PROTECT` in migration `0002_category_parent_protect.py`.

### What PROTECT Does

The `PROTECT` constraint prevents deletion of a parent category if it has any child categories, raising a `ProtectedError` exception.

**Before (CASCADE - DANGEROUS)**:
```
Delete "Plant Care" →
  Automatically deletes "Watering" (child)
  Automatically deletes "Fertilizing" (child)
  Automatically deletes 900 threads
  Automatically deletes 5,000+ posts
```

**After (PROTECT - SAFE)**:
```
Delete "Plant Care" →
  ERROR: Cannot delete - has 2 child categories
  Must delete children first (intentional, manual process)
```

## Proper Deletion Procedure

### For Administrators

When you need to delete a category hierarchy, follow this **bottom-up approach**:

#### 1. Identify Category Hierarchy

In Django admin at `/admin/forum/category/`, the category list shows:
- Category name
- Parent category
- Thread count
- Child count (via admin interface)

Example hierarchy:
```
Plants (0 threads, 2 children)
  ├─ Indoor (0 threads, 2 children)
  │   ├─ Succulents (150 threads, 0 children)
  │   └─ Ferns (200 threads, 0 children)
  └─ Outdoor (0 threads, 1 child)
      └─ Trees (300 threads, 0 children)
```

#### 2. Delete Leaf Categories First (Bottom-Up)

**Step 1**: Delete leaf categories (no children):
- Delete "Succulents" (150 threads will CASCADE delete - INTENDED)
- Delete "Ferns" (200 threads will CASCADE delete - INTENDED)
- Delete "Trees" (300 threads will CASCADE delete - INTENDED)

**Step 2**: Delete intermediate categories:
- Delete "Indoor" (now has no children)
- Delete "Outdoor" (now has no children)

**Step 3**: Delete root category:
- Delete "Plants" (now has no children)

### Admin Interface Error Messages

The enhanced CategoryAdmin provides clear guidance:

#### Attempting to Delete Parent with Children

```
ERROR: Cannot delete category 'Plant Care': Contains 2 subcategories.
Delete or move subcategories first to prevent data loss.
```

#### Attempting to Delete Category with Threads

```
WARNING: Category 'Succulents' contains 150 threads.
Deleting will CASCADE delete all threads and their posts!
```

This warning appears but allows deletion (intended behavior - threads should CASCADE with their category).

#### Successful Deletion

```
SUCCESS: Successfully deleted category 'Succulents'.
```

## Technical Details

### Model Configuration

**Location**: `/Users/williamtower/projects/plant_id_community/backend/apps/forum/models.py:79-86`

```python
parent = models.ForeignKey(
    'self',
    on_delete=models.PROTECT,  # Prevents parent deletion if children exist
    null=True,
    blank=True,
    related_name='children',
    help_text='Parent category. PROTECT prevents accidental deletion of category hierarchies.'
)
```

### Migration

**Location**: `/Users/williamtower/projects/plant_id_community/backend/apps/forum/migrations/0002_category_parent_protect.py`

```python
operations = [
    migrations.AlterField(
        model_name='category',
        name='parent',
        field=models.ForeignKey(
            blank=True,
            help_text='Parent category. PROTECT prevents accidental deletion of category hierarchies.',
            null=True,
            on_delete=django.db.models.deletion.PROTECT,
            related_name='children',
            to='forum.category'
        ),
    ),
]
```

### Admin Enhancements

**Location**: `/Users/williamtower/projects/plant_id_community/backend/apps/forum/admin.py:13-97`

**Key Features**:
1. **Thread Count Display**: Shows thread count in list view
2. **delete_model() Override**: Prevents single deletion with clear error
3. **delete_queryset() Override**: Prevents bulk deletion with clear error
4. **Warning Messages**: Warns about thread CASCADE before proceeding

## CASCADE Behavior Table

| Delete Action | Children | Threads | Result |
|--------------|----------|---------|--------|
| Delete parent category | Has children | Any | **BLOCKED** (ProtectedError) |
| Delete parent category | No children | 0 threads | **SUCCESS** (safe deletion) |
| Delete parent category | No children | Has threads | **SUCCESS** (threads CASCADE - INTENDED) |
| Delete leaf category | N/A (no children) | Has threads | **SUCCESS** (threads CASCADE - INTENDED) |

## Testing

### Test Coverage

**Location**: `/Users/williamtower/projects/plant_id_community/backend/apps/forum/tests/test_category_protection.py`

**Test Classes**:
1. `CategoryProtectionTestCase` - Model-level PROTECT behavior
2. `CategoryAdminProtectionTestCase` - Admin interface UX
3. `CategoryHierarchyIntegrationTestCase` - Multi-level hierarchy scenarios

**Run Tests**:
```bash
cd /Users/williamtower/projects/plant_id_community/backend
source venv/bin/activate
python manage.py test apps.forum.tests.test_category_protection --keepdb -v 2
```

### Test Scenarios Covered

1. Cannot delete parent with children (ProtectedError)
2. Can delete leaf categories (threads CASCADE)
3. Can delete parent after children removed
4. Thread count calculation accuracy
5. Admin error message display
6. Admin warning for thread CASCADE
7. Multi-level hierarchy protection
8. Bottom-up deletion order

## Related Models

### Thread CASCADE (INTENDED)

Threads still CASCADE delete when their category is deleted:

```python
category = models.ForeignKey(
    Category,
    on_delete=models.CASCADE,  # Threads belong to category
    related_name='threads',
)
```

**Rationale**:
- Threads without a category are meaningless
- Orphaned threads would confuse users
- Admins are warned before deletion

### Post CASCADE (INTENDED)

Posts still CASCADE delete when their thread is deleted:

```python
thread = models.ForeignKey(
    Thread,
    on_delete=models.CASCADE,  # Posts belong to thread
    related_name='posts',
)
```

**Rationale**:
- Posts without a thread are meaningless
- Maintains referential integrity

## Alternative Considered: SET_NULL

**Not Implemented**: SET_NULL would orphan child categories as top-level categories.

**Pros**:
- Allows parent deletion
- Children become top-level

**Cons**:
- Can create unexpected category structure
- Confuses users with orphaned categories
- Requires additional UI for reassignment

**Decision**: PROTECT is safer and clearer. Manual deletion forces intentional action.

## Rollback Procedure

If you need to revert to CASCADE (NOT RECOMMENDED):

```bash
cd /Users/williamtower/projects/plant_id_community/backend
source venv/bin/activate

# Revert migration
python manage.py migrate forum 0001_initial

# DANGER: This re-enables CASCADE deletion
# Only use in development environments
```

## Monitoring

### Check for Protected Categories

Query to find parent categories with children:

```python
from apps.forum.models import Category

# Find all parent categories
parents = Category.objects.filter(children__isnull=False).distinct()

for parent in parents:
    child_count = parent.children.count()
    thread_count = parent.get_thread_count()
    print(f"{parent.name}: {child_count} children, {thread_count} threads")
```

### Check for Leaf Categories

Query to find deletable leaf categories:

```python
from apps.forum.models import Category

# Find leaf categories (no children)
leaves = Category.objects.filter(children__isnull=True)

for leaf in leaves:
    thread_count = leaf.get_thread_count()
    print(f"{leaf.name}: {thread_count} threads (can delete)")
```

## Best Practices

### Creating Categories

1. **Plan Hierarchy First**: Design category structure before creating threads
2. **Avoid Deep Nesting**: 2-3 levels maximum for UX
3. **Use Descriptive Names**: Clear category names prevent reorganization
4. **Set Display Order**: Control category sort order explicitly

### Reorganizing Categories

**Moving Threads Between Categories**:
1. Use Django admin bulk action
2. Select threads to move
3. Change category via dropdown
4. Save changes

**Merging Categories**:
1. Move all threads from old category to new category
2. Delete old category (now empty, no children)

**Renaming Categories**:
1. Edit category directly (no deletion needed)
2. Slug updates automatically

### Archiving vs. Deleting

**Consider Soft Delete**:
- Use `is_active=False` instead of deletion
- Preserves data for historical reference
- Can be restored if needed

**Hard Delete Only When**:
- Category was created by mistake
- Contains spam/inappropriate content
- Confirmed with site owner/admin team

## Troubleshooting

### Error: "Cannot delete category - contains subcategories"

**Cause**: Attempting to delete parent category with children

**Solution**: Delete children first (bottom-up approach)

### Error: "ProtectedError: Cannot delete some instances of model 'Category'"

**Cause**: Django ORM prevented CASCADE due to PROTECT constraint

**Solution**: Identify child categories and delete them first

### Warning: "Category contains X threads - will CASCADE delete"

**Not an Error**: This is informational - proceed if intended

**Solution**:
- If threads should be preserved: Move threads to another category first
- If threads should be deleted: Proceed with deletion

## References

- **Django PROTECT Documentation**: https://docs.djangoproject.com/en/5.0/ref/models/fields/#django.db.models.PROTECT
- **Issue #003**: Category Parent CASCADE - Accidental Thread Deletion Risk
- **Code Review**: Data Integrity Guardian audit (November 3, 2025)
- **Pattern**: TRUST_LEVEL_PATTERNS_CODIFIED.md (migration testing)

## Acceptance Criteria

- [x] Migration created to change CASCADE to PROTECT
- [x] Admin interface shows clear error when attempting to delete parent categories
- [x] Tests verify protection works (raises ProtectedError)
- [x] Tests verify admin error messages
- [x] Tests verify leaf category deletion still works
- [x] Tests verify proper deletion order (bottom-up)
- [x] Documentation updated with deletion procedure
- [x] Admin interface enhanced with thread count display
- [x] Admin interface provides warning messages for thread CASCADE
- [x] Code review approved

## Status

**COMPLETE** - Issue #003 resolved

**Changes**:
1. Migration `0002_category_parent_protect.py` applied
2. Admin interface enhanced with error handling
3. Comprehensive test suite added (15 test cases)
4. Documentation created

**Impact**: Prevents accidental deletion of 900+ threads from single admin action

**Risk**: LOW - Migration is reversible, admin UX improved, well-tested
