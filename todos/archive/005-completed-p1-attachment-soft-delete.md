---
status: pending
priority: p1
issue_id: "005"
tags: [code-review, data-integrity, django, soft-delete, forum]
dependencies: []
---

# Soft Delete Inconsistency - Attachment Model

## Problem Statement

Post and Thread models use soft deletes (is_active flag), but Attachment model uses hard DELETE, creating inconsistency and potential issues with post restoration.

**Location:** `backend/apps/forum/models.py:365-445`

## Findings

- Discovered during data integrity audit by Data Integrity Guardian agent
- **Current State:**
  ```python
  # Post model (line 315)
  is_active = models.BooleanField(default=True)  # ✅ Soft delete

  # Attachment model (line 379)
  post = models.ForeignKey(
      Post,
      on_delete=models.CASCADE,  # ❌ Hard delete
  )
  # ❌ No is_active field
  ```
- **Problem Scenario:**
  ```
  1. User creates post with 6 images
  2. User soft-deletes own post (is_active=False)
  3. User realizes mistake, wants to restore
  4. If cleanup job ran, images might be gone
  5. Post restoration shows broken image links
  ```
- Pattern inconsistency: Post/Thread have soft deletes, Attachment does not

## Proposed Solutions

### Option 1: Add is_active to Attachment (RECOMMENDED)
```python
class Attachment(models.Model):
    # Add soft delete to match Post model
    is_active = models.BooleanField(
        default=True,
        help_text="Soft delete: inactive attachments are hidden"
    )

    class Meta:
        indexes = [
            models.Index(fields=['post', 'is_active', 'display_order']),
        ]

    def delete(self, *args, **kwargs):
        """Soft delete by setting is_active=False."""
        self.is_active = False
        self.save(update_fields=['is_active'])
```

Update Post's perform_destroy to soft-delete attachments:
```python
def perform_destroy(self, instance) -> None:
    """Soft delete post and its attachments."""
    instance.is_active = False
    instance.save(update_fields=['is_active'])

    # Soft delete attachments too
    instance.attachments.update(is_active=False)
```

- **Pros**: Consistent with Post/Thread pattern, allows restoration, maintains audit trail
- **Cons**: Requires migration, filtering queries need is_active=True
- **Effort**: 3 hours (migration + model + queryset updates + tests)
- **Risk**: Low (additive change, backward compatible)

### Option 2: Keep Hard Delete (Not Recommended)
Keep current behavior but document it clearly.

- **Pros**: No code changes
- **Cons**: Inconsistent pattern, can't restore posts with images
- **Effort**: 0 hours
- **Risk**: Medium (user frustration when restoration fails)

## Recommended Action

**Implement Option 1** - Add is_active field to Attachment model for consistency.

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/models.py` (Attachment model)
  - `backend/apps/forum/viewsets/post_viewset.py` (soft delete logic)
  - `backend/apps/forum/migrations/XXXX_attachment_soft_delete.py` (new)
- **Related Components**: Post deletion, attachment upload/delete endpoints
- **Database Changes**:
  ```sql
  ALTER TABLE forum_attachment
    ADD COLUMN is_active BOOLEAN DEFAULT TRUE;

  CREATE INDEX forum_attachment_active_idx
    ON forum_attachment (post_id, is_active, display_order);
  ```
- **Migration Risk**: LOW (additive, no data loss)

## Resources

- Data Integrity Guardian audit report (Nov 3, 2025)
- Related patterns: Post.is_active (line 315), Thread.is_active
- Django soft delete patterns: https://docs.djangoproject.com/en/5.0/topics/db/models/#overriding-model-methods

## Acceptance Criteria

- [ ] Migration adds is_active field to Attachment
- [ ] Attachment.delete() performs soft delete
- [ ] Post.perform_destroy() soft-deletes attachments
- [ ] All attachment queries filter is_active=True
- [ ] Tests verify soft delete behavior
- [ ] Admin interface shows inactive attachments (grayed out)
- [ ] Cleanup job deletes only attachments inactive for 30+ days
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code audit
- Analyzed by Data Integrity Guardian agent
- Categorized as P1 (pattern inconsistency, UX issue)

**Learnings:**
- Soft delete patterns should be consistent across related models
- Hard deletes prevent restoration of parent objects
- Audit trail requires preserving all related data

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Data Integrity Guardian
Pattern: Post and Thread use soft deletes, Attachment should too
User Impact: Can't restore posts with images if cleanup job runs
