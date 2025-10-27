---
status: ready
priority: p1
issue_id: "004"
tags: [code-review, data-integrity, race-condition, concurrency]
dependencies: []
---

# Fix Vote Counting Race Condition

## Problem Statement

Concurrent vote operations cause lost updates due to read-modify-write pattern without atomic operations. When two users vote simultaneously, one vote is lost.

## Findings

- **Discovered by**: data-integrity-guardian agent
- **Location**: `backend/apps/plant_identification/models.py:572-580` (upvotes/downvotes fields)
- **Pattern**: Read-modify-write without transaction protection
- **Impact**: Vote counts become incorrect (data corruption)

**Race Condition Scenario**:
```
Time  User A              User B              Database
----  --------            --------            ---------
T1    Read upvotes=10     -                   upvotes=10
T2    -                   Read upvotes=10     upvotes=10
T3    Increment to 11     -                   upvotes=10
T4    -                   Increment to 11     upvotes=10
T5    Save upvotes=11     -                   upvotes=11
T6    -                   Save upvotes=11     upvotes=11  ❌ Should be 12!
```

## Current Implementation

**PlantIdentificationResult model** (lines 572-580):
```python
class PlantIdentificationResult(models.Model):
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    # ... other fields
```

**View logic** (implied, not shown):
```python
# UNSAFE - race condition
result.upvotes += 1
result.save()
```

## Proposed Solutions

### Option 1: Atomic F() Expressions (Recommended)
- **Implementation**: Use Django's F() for atomic database operations
- **Code**:
  ```python
  from django.db.models import F

  # Thread-safe atomic update
  PlantIdentificationResult.objects.filter(id=result_id).update(
      upvotes=F('upvotes') + 1
  )

  # If you need the updated value:
  result = PlantIdentificationResult.objects.get(id=result_id)
  ```
- **Pros**:
  - Atomic at database level (PostgreSQL/SQLite support)
  - No race conditions
  - No need for row locks
  - Minimal code change
  - Excellent performance
- **Cons**: None
- **Effort**: Small (2 hours - update all vote increment locations)
- **Risk**: Low

### Option 2: select_for_update() Row Locking
- **Implementation**: Use pessimistic locking
- **Code**:
  ```python
  with transaction.atomic():
      result = PlantIdentificationResult.objects.select_for_update().get(id=result_id)
      result.upvotes += 1
      result.save()
  ```
- **Pros**: Explicit locking, prevents all concurrent modifications
- **Cons**:
  - Slower (lock contention on popular posts)
  - Requires transaction wrapper
  - Deadlock risk if used incorrectly
- **Effort**: Medium (4 hours)
- **Risk**: Medium (deadlock potential)
- **Verdict**: Not recommended - F() is simpler and faster

## Recommended Action

**Implement Option 1** - Use F() expressions for all vote operations.

### Implementation Steps:

1. **Find all vote increment locations**:
   ```bash
   cd backend
   grep -r "upvotes +=" apps/
   grep -r "downvotes +=" apps/
   ```

2. **Replace read-modify-write with F() expressions**:
   ```python
   # Before (all occurrences)
   result.upvotes += 1
   result.save()

   # After
   from django.db.models import F
   PlantIdentificationResult.objects.filter(id=result.id).update(
       upvotes=F('upvotes') + 1
   )
   ```

3. **Handle both upvote and downvote**:
   ```python
   # Upvote
   PlantIdentificationResult.objects.filter(id=result_id).update(
       upvotes=F('upvotes') + 1
   )

   # Downvote
   PlantIdentificationResult.objects.filter(id=result_id).update(
       downvotes=F('downvotes') + 1
   )

   # Remove vote (decrement)
   PlantIdentificationResult.objects.filter(id=result_id).update(
       upvotes=F('upvotes') - 1
   )
   ```

4. **Add concurrent vote test**:
   ```python
   # apps/plant_identification/tests/test_vote_race_condition.py
   from concurrent.futures import ThreadPoolExecutor

   def test_concurrent_votes_no_race_condition(self):
       result = PlantIdentificationResult.objects.create(...)

       def upvote():
           PlantIdentificationResult.objects.filter(id=result.id).update(
               upvotes=F('upvotes') + 1
           )

       # 10 concurrent votes
       with ThreadPoolExecutor(max_workers=10) as executor:
           executor.map(lambda _: upvote(), range(10))

       result.refresh_from_database()
       self.assertEqual(result.upvotes, 10)  # ✅ Should be exactly 10
   ```

5. **Verify existing tests pass**

## Technical Details

**Affected Files**:
- View files with vote logic (search for `upvotes +=`, `downvotes +=`)
- `backend/apps/plant_identification/models.py` (field definitions - no changes)
- Tests (add new race condition test)

**Related Models** (may have same pattern):
- Check all models with upvotes/downvotes fields
- Forum posts (if implemented)
- Comments (if implemented)

**Database Changes**: None (F() works with existing schema)

**Similar Patterns to Fix**:
- Any counter fields (view_count, like_count, etc.)
- Inventory decrements (if applicable)
- Balance updates (if applicable)

## Resources

- **Django F() docs**: https://docs.djangoproject.com/en/5.2/ref/models/expressions/#f-expressions
- **Race condition explanation**: data-integrity-guardian agent report
- **Testing patterns**: `/backend/docs/testing/AUTHENTICATION_TESTS.md`

## Acceptance Criteria

- [ ] All vote increment operations use F() expressions
- [ ] No read-modify-write pattern for upvotes/downvotes
- [ ] Concurrent vote test added and passing
- [ ] 10 concurrent votes result in exactly 10 increments (no lost votes)
- [ ] Existing tests still pass
- [ ] Similar patterns (view_count, etc.) also fixed

## Work Log

### 2025-10-25 - Code Review Discovery
**By**: Claude Code Review System (data-integrity-guardian agent)
**Actions**:
- Discovered during data integrity analysis
- Identified read-modify-write pattern on counter fields
- Created race condition scenario showing vote loss
- Verified F() expressions as Django best practice

**Learnings**:
- Race conditions are silent - tests may not catch them
- F() expressions are Django's recommended solution
- This affects any counter field (not just votes)
- Concurrent vote test would have caught this bug

## Notes

**Source**: Code review performed on 2025-10-25
**Review command**: `audit codebase and report back to me`
**Priority justification**: CRITICAL - data corruption violates user expectations (votes disappear)
**Common bug**: Many Django projects have this issue until they scale
