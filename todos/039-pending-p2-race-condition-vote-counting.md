---
status: pending
priority: p2
issue_id: "039"
tags: [code-review, data-integrity, concurrency, race-condition]
dependencies: []
---

# Fix Race Conditions in Vote Counting with Atomic Operations

## Problem Statement
Vote counters increment without atomic operations, causing lost updates under concurrent access. Only blog app has correct F() expressions; plant identification app has race conditions.

## Findings
- Discovered during comprehensive code review by kieran-python-reviewer and data-integrity-guardian agents
- **Location**: `backend/apps/plant_identification/models.py:588-596`
- **Severity**: HIGH (CVSS 6.5 - Data corruption)
- **Impact**: Lost vote updates with concurrent requests, incorrect vote counts

**Problematic code**:
```python
# PlantIdentificationResult model (lines 588-596)
upvotes = models.PositiveIntegerField(default=0)
downvotes = models.PositiveIntegerField(default=0)

# Current usage (race condition):
result.upvotes += 1
result.save()  # ❌ Read-modify-write race condition
```

**Good example found** (blog middleware):
```python
# ✅ CORRECT: Uses F() expression for atomic increment
BlogPostPage.objects.filter(id=page.id).update(
    view_count=models.F('view_count') + 1
)
```

**Why it's broken**:
- Two concurrent requests both read `upvotes=5`
- Both increment to 6
- Both save with value 6
- Result: Only 1 vote counted instead of 2 (lost update)

## Proposed Solutions

### Option 1: Add Atomic Increment Methods (RECOMMENDED)
```python
class PlantIdentificationResult(models.Model):
    upvotes = models.PositiveIntegerField(default=0, db_index=True)
    downvotes = models.PositiveIntegerField(default=0, db_index=True)

    def increment_upvotes(self) -> None:
        """Atomically increment upvote count (thread-safe)."""
        type(self).objects.filter(pk=self.pk).update(
            upvotes=models.F('upvotes') + 1
        )
        self.refresh_from_db(fields=['upvotes'])

    def increment_downvotes(self) -> None:
        """Atomically increment downvote count (thread-safe)."""
        type(self).objects.filter(pk=self.pk).update(
            downvotes=models.F('downvotes') + 1
        )
        self.refresh_from_db(fields=['downvotes'])

    def decrement_upvotes(self) -> None:
        """Atomically decrement upvote count (prevents negative)."""
        type(self).objects.filter(pk=self.pk, upvotes__gt=0).update(
            upvotes=models.F('upvotes') - 1
        )
        self.refresh_from_db(fields=['upvotes'])

    def decrement_downvotes(self) -> None:
        """Atomically decrement downvote count (prevents negative)."""
        type(self).objects.filter(pk=self.pk, downvotes__gt=0).update(
            downvotes=models.F('downvotes') - 1
        )
        self.refresh_from_db(fields=['downvotes'])
```

**Usage in views**:
```python
# Replace this:
result.upvotes += 1
result.save()

# With this:
result.increment_upvotes()
```

**Pros**:
- Thread-safe atomic operations
- Database-level increment (no race conditions)
- Prevents negative vote counts
- Self-documenting API

**Cons**:
- Need to update all views using vote counters
- Requires refactor of vote tracking logic

**Effort**: Small (1 hour)
**Risk**: Low (standard Django pattern)

### Option 2: Use select_for_update() with Transaction
For vote changes (upvote ↔ downvote swap):

```python
from django.db import transaction

@transaction.atomic
def change_vote(user_id: int, result_id: int, old_vote: str, new_vote: str) -> None:
    """Atomically change vote from upvote to downvote or vice versa."""
    with transaction.atomic():
        vote = PlantIdentificationVote.objects.select_for_update().get(
            user_id=user_id, result_id=result_id
        )
        vote.vote_type = new_vote
        vote.save()

        # Atomic counter updates
        PlantIdentificationResult.objects.filter(pk=result_id).update(
            upvotes=models.F('upvotes') + (1 if new_vote == 'upvote' else -1),
            downvotes=models.F('downvotes') + (1 if new_vote == 'downvote' else -1),
        )
```

**Pros**:
- Ensures consistency between vote record and counters
- Locks row to prevent concurrent modifications

**Cons**:
- More complex than Option 1
- Potential deadlock risk if not careful

**Effort**: Medium (2 hours)
**Risk**: Medium

## Recommended Action
Implement **Option 1** (atomic methods) for all counter fields:
- `PlantIdentificationResult.upvotes/downvotes`
- `PlantSpecies.identification_count` (line 230)
- `PlantDiseaseDatabase.diagnosis_count` (line 1098)

## Technical Details
- **Affected Files**:
  - `backend/apps/plant_identification/models.py` (3 counter fields)
  - `backend/apps/plant_identification/views.py` (vote tracking logic)
  - `backend/apps/blog/middleware.py` (already correct ✅)

- **Related Components**:
  - Vote tracking system (upvote/downvote API endpoints)
  - Species popularity tracking
  - Disease diagnosis statistics

- **Database Changes**: None (F() expressions are ORM-level)

## Resources
- Django F() expressions: https://docs.djangoproject.com/en/5.2/ref/models/expressions/#f-expressions
- Atomic operations: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
- select_for_update: https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update

## Acceptance Criteria
- [ ] Atomic increment/decrement methods added to all counter fields
- [ ] All views updated to use new methods (no more `+=` operations)
- [ ] Tests added for concurrent vote updates
- [ ] Load test with 100 concurrent votes (verify no lost updates)
- [ ] Code review confirms no remaining race conditions
- [ ] Documentation updated for vote tracking patterns

## Work Log

### 2025-10-28 - Code Review Discovery
**By:** Kieran Python Reviewer + Data Integrity Guardian
**Actions:**
- Found atomic F() expressions in blog middleware (good example)
- Discovered missing atomic operations in plant identification
- Identified 3 counter fields with race condition risk
- Categorized as HIGH priority (data corruption under load)

**Learnings:**
- Blog app has correct pattern (use as reference)
- `+=` operator is NOT atomic in Django
- F() expressions compile to SQL increment (atomic)
- Need consistent pattern across all counter fields

## Notes
- Grade impact: -2 points (B+ → B for partial fix)
- Quick win: Blog app already has fix, copy pattern
- Part of comprehensive code review findings (Finding #5 of 26)
- Related to Finding #23 (missing transaction boundaries)
