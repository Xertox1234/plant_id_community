---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, data-integrity, django, race-condition]
dependencies: []
---

# Missing Transaction Boundaries - Post Statistics Updates

## Problem Statement

The `Post.save()` method updates thread statistics (post_count, last_activity) without transaction protection, causing potential race conditions and lost updates under concurrent access.

**Location:** `backend/apps/forum/models.py:348-357`

## Findings

- Discovered during data integrity audit by Data Integrity Guardian agent
- **Race Condition Scenario:**
  ```
  User A creates Post 1 → Reads Thread.post_count (5)
  User B creates Post 2 → Reads Thread.post_count (5)
  User A commits post_count = 6
  User B commits post_count = 6  ← Lost Post A's increment!
  ```
- Current code executes separate queries without atomicity
- No use of F() expressions for atomic updates

## Proposed Solutions

### Option 1: Transaction + F() Expressions (RECOMMENDED)
```python
from django.db import transaction
from django.db.models import F

def save(self, *args, **kwargs):
    is_new = not self.pk

    with transaction.atomic():
        super().save(*args, **kwargs)

        if is_new and self.is_active:
            # Use F() expressions for atomic updates
            Thread.objects.filter(pk=self.thread_id).update(
                post_count=F('post_count') + 1,
                last_activity_at=timezone.now()
            )
            self.thread.refresh_from_db(fields=['post_count', 'last_activity_at'])
```

- **Pros**: Prevents race conditions, atomic updates, simple implementation
- **Cons**: None
- **Effort**: 2 hours (implementation + tests)
- **Risk**: Low (F() expressions are well-tested Django pattern)

### Option 2: select_for_update() Lock
```python
with transaction.atomic():
    thread = Thread.objects.select_for_update().get(pk=self.thread_id)
    super().save(*args, **kwargs)
    thread.post_count += 1
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=['post_count', 'last_activity_at'])
```

- **Pros**: Explicit locking, complete control
- **Cons**: Potential for deadlocks, slower than F() expressions
- **Effort**: 3 hours
- **Risk**: Medium (requires careful testing)

## Recommended Action

**Implement Option 1** - Use transaction.atomic() with F() expressions.

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/models.py` (Post model save method)
- **Related Components**: Thread model, post creation API
- **Database Changes**: No schema changes required
- **Performance Impact**: Minimal (F() expressions are more efficient)

## Resources

- Data Integrity Guardian audit report (Nov 3, 2025)
- Django F() expressions: https://docs.djangoproject.com/en/5.0/ref/models/expressions/#f-expressions
- Django transactions: https://docs.djangoproject.com/en/5.0/topics/db/transactions/

## Acceptance Criteria

- [ ] Post.save() wrapped in transaction.atomic()
- [ ] Thread statistics use F() expressions for atomic updates
- [ ] Unit tests pass for concurrent post creation
- [ ] Load test verifies no lost updates under 50 concurrent requests
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code audit
- Analyzed by Data Integrity Guardian agent
- Categorized as P1 (critical race condition)

**Learnings:**
- Read-then-write patterns are vulnerable to race conditions
- F() expressions provide database-level atomicity
- Transaction boundaries prevent partial updates

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Data Integrity Guardian
