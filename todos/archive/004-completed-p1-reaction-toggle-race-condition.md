---
status: pending
priority: p1
issue_id: "004"
tags: [code-review, data-integrity, django, race-condition, forum]
dependencies: []
---

# Race Condition in Reaction Toggle Method

## Problem Statement

The `Reaction.toggle_reaction()` classmethod has a race condition where concurrent toggle requests can produce incorrect final state (user's reaction appears removed when they wanted to add it).

**Location:** `backend/apps/forum/models.py:534-538` (toggle_reaction method)

## Findings

- Discovered during data integrity audit by Data Integrity Guardian agent
- **Current Implementation:**
  ```python
  @classmethod
  def toggle_reaction(cls, post_id: uuid.UUID, user_id: int, reaction_type: str):
      reaction, created = cls.objects.get_or_create(
          post_id=post_id,
          user_id=user_id,
          reaction_type=reaction_type,
          defaults={'is_active': True}
      )

      if not created:
          reaction.is_active = not reaction.is_active  # ❌ Not atomic
          reaction.save(update_fields=['is_active', 'updated_at'])

      return reaction, created
  ```
- **Race Condition Scenario:**
  ```
  User double-clicks "like" button rapidly:
  Request 1: get_or_create → created=True, starts save
  Request 2: get_or_create → created=False, reads is_active=True
  Request 1: commits (is_active=True)
  Request 2: toggles to False, saves
  Result: ❌ User's reaction removed instead of added
  ```

## Proposed Solutions

### Option 1: select_for_update() Lock (RECOMMENDED)
```python
@classmethod
def toggle_reaction(cls, post_id: uuid.UUID, user_id: int, reaction_type: str):
    from django.db import transaction

    with transaction.atomic():
        # Lock the row to prevent concurrent modifications
        try:
            reaction = cls.objects.select_for_update().get(
                post_id=post_id,
                user_id=user_id,
                reaction_type=reaction_type
            )
            # Toggle existing reaction
            reaction.is_active = not reaction.is_active
            reaction.save(update_fields=['is_active', 'updated_at'])
            created = False
        except cls.DoesNotExist:
            # Create new reaction
            reaction = cls.objects.create(
                post_id=post_id,
                user_id=user_id,
                reaction_type=reaction_type,
                is_active=True
            )
            created = True

        return reaction, created
```

- **Pros**: Prevents race conditions, simple implementation
- **Cons**: Slightly slower (lock acquisition), potential for deadlocks if combined with other locks
- **Effort**: 2 hours (implementation + tests)
- **Risk**: Low (well-tested Django pattern)

### Option 2: F() Expression Toggle (Alternative)
```python
from django.db.models import F

@classmethod
def toggle_reaction(cls, post_id: uuid.UUID, user_id: int, reaction_type: str):
    reaction, created = cls.objects.get_or_create(
        post_id=post_id,
        user_id=user_id,
        reaction_type=reaction_type,
        defaults={'is_active': True}
    )

    if not created:
        # Atomic toggle using F() and Case/When
        cls.objects.filter(pk=reaction.pk).update(
            is_active=Case(
                When(is_active=True, then=Value(False)),
                When(is_active=False, then=Value(True)),
            )
        )
        reaction.refresh_from_db()

    return reaction, created
```

- **Pros**: Database-level atomicity, no locking
- **Cons**: More complex SQL, harder to test
- **Effort**: 3 hours
- **Risk**: Medium

## Recommended Action

**Implement Option 1** - Use select_for_update() for explicit locking.

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/models.py` (Reaction model toggle_reaction method)
  - `backend/apps/forum/viewsets/reaction_viewset.py` (calls toggle_reaction)
- **Related Components**: Post reaction counts, reaction API endpoints
- **Database Changes**: No schema changes required
- **Performance Impact**: Minimal (~10ms lock acquisition time)

## Resources

- Data Integrity Guardian audit report (Nov 3, 2025)
- Django select_for_update: https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-for-update
- Django transactions: https://docs.djangoproject.com/en/5.0/topics/db/transactions/

## Acceptance Criteria

- [ ] toggle_reaction() wrapped in transaction.atomic()
- [ ] select_for_update() used to lock reaction row
- [ ] Unit tests pass for concurrent toggle operations
- [ ] Load test verifies correct state under 50 concurrent toggles
- [ ] Frontend double-click protection (debouncing) added as defense-in-depth
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code audit
- Analyzed by Data Integrity Guardian agent
- Categorized as P1 (race condition under load)

**Learnings:**
- get_or_create + toggle pattern is vulnerable to races
- select_for_update() provides row-level locking
- Frontend debouncing is defense-in-depth, not primary fix

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Data Integrity Guardian
Severity: HIGH - Affects user experience (reactions appear/disappear randomly)
Common trigger: Mobile users with slow networks, double-tap gestures
