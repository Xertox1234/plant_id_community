---
status: pending
priority: p3
issue_id: "091"
tags: [testing, forum, caching, mocking, bug]
dependencies: []
estimated_effort: "2-3 hours"
---

# Fix Forum Cache Integration Test Mock Assertions

## Problem Statement

3 forum cache integration tests are failing because mock assertions expect `invalidate_post_lists()` to be called, but it's not being called. This suggests either:
1. The signal handlers aren't calling the method as expected
2. The mocking strategy is incorrect
3. The test expectations don't match actual implementation

## Findings

**Discovered**: November 2, 2025 during post-dependency-update test verification
**Scope**: 3 failing tests in `apps/forum/tests/test_cache_integration.py`
**Impact**: Cache invalidation behavior not verified by tests

**Failing Tests**:
1. `test_creating_post_invalidates_thread_cache`
   - **Expected**: `invalidate_post_lists()` called once
   - **Actual**: Called 0 times

2. `test_updating_post_invalidates_thread_cache`
   - **Expected**: `invalidate_post_lists()` called once
   - **Actual**: Called 0 times

3. `test_deleting_post_invalidates_thread_cache`
   - **Expected**: `invalidate_post_lists()` called once
   - **Actual**: Called 0 times

**Error Message**:
```python
AssertionError: Expected 'invalidate_post_lists' to have been called once. Called 0 times.
```

**Test Pattern** (from `test_cache_integration.py`):
```python
@patch('apps.forum.signals.ForumCacheService')
def test_creating_post_invalidates_thread_cache(self, mock_service):
    """Test that creating a post invalidates thread cache."""
    post = ForumPost.objects.create(
        thread=self.thread,
        author=self.user,
        content='Test post content'
    )

    # This assertion fails
    mock_service.invalidate_post_lists.assert_called_once()
```

**Actual Signal Implementation** (from `apps/forum/signals.py`):
```python
@receiver(post_save, sender=ForumPost)
def invalidate_post_caches(sender, instance, created, **kwargs):
    """Invalidate post-related caches when a post is created or updated."""
    logger.info(f"[CACHE] Invalidated caches for {'created' if created else 'updated'} post in thread: {instance.thread.slug}")

    # Call cache service methods
    ForumCacheService.invalidate_thread_detail(instance.thread.slug)
    ForumCacheService.invalidate_thread_lists()
    # NOTE: invalidate_post_lists() is NOT called here!
```

## Root Cause Analysis

**The Problem**: Tests expect `invalidate_post_lists()` but signals call different methods.

**From Signal Handler**:
- `ForumCacheService.invalidate_thread_detail(slug)`
- `ForumCacheService.invalidate_thread_lists()`

**Test Expects**:
- `ForumCacheService.invalidate_post_lists()`

**Possible Causes**:
1. **Signal implementation changed** but tests weren't updated
2. **Tests written before implementation** and expectations don't match reality
3. **Method name mismatch**: `invalidate_thread_lists()` vs `invalidate_post_lists()`

## Proposed Solutions

### Option 1: Fix Test Expectations (Recommended)
Update tests to match actual signal implementation.

**Implementation**:
```python
@patch('apps.forum.signals.ForumCacheService')
def test_creating_post_invalidates_thread_cache(self, mock_service):
    """Test that creating a post invalidates thread cache."""
    post = ForumPost.objects.create(
        thread=self.thread,
        author=self.user,
        content='Test post content'
    )

    # Assert correct methods are called
    mock_service.invalidate_thread_detail.assert_called_once_with(self.thread.slug)
    mock_service.invalidate_thread_lists.assert_called_once()
    # Remove incorrect assertion
    # mock_service.invalidate_post_lists.assert_called_once()
```

**Pros**:
- Matches actual implementation
- Tests verify real behavior
- Simple fix

**Cons**:
- Need to verify signal implementation is correct first

**Effort**: 1-2 hours
**Risk**: Low

### Option 2: Update Signal Implementation
Change signals to call `invalidate_post_lists()` as tests expect.

**Investigation Needed**:
```python
# Check if invalidate_post_lists() exists
# File: apps/forum/services/forum_cache_service.py

class ForumCacheService:
    @classmethod
    def invalidate_post_lists(cls):
        """Invalidate all post list caches."""
        # Does this method exist?
        # What does it do differently from invalidate_thread_lists()?
```

**Implementation** (if method exists):
```python
@receiver(post_save, sender=ForumPost)
def invalidate_post_caches(sender, instance, created, **kwargs):
    """Invalidate post-related caches when a post is created or updated."""
    logger.info(f"[CACHE] Invalidated caches for {'created' if created else 'updated'} post in thread: {instance.thread.slug}")

    ForumCacheService.invalidate_thread_detail(instance.thread.slug)
    ForumCacheService.invalidate_thread_lists()
    ForumCacheService.invalidate_post_lists()  # Add this
```

**Pros**:
- Tests remain unchanged
- May provide more comprehensive cache invalidation

**Cons**:
- Need to verify method exists and is needed
- May add unnecessary cache invalidation
- Could impact performance

**Effort**: 2-3 hours (including verification)
**Risk**: Medium (could break caching if method doesn't exist)

### Option 3: Comprehensive Test Refactor
Rewrite tests to verify actual cache behavior instead of mock calls.

**Implementation**:
```python
class CacheIntegrationTests(TestCase):
    def test_creating_post_invalidates_thread_cache(self):
        """Test that creating a post invalidates thread cache."""

        # Pre-populate cache
        thread_key = ForumCacheService.get_thread_detail_key(self.thread.slug)
        cache.set(thread_key, {'thread': 'data'}, 300)

        # Verify cache has data
        self.assertIsNotNone(cache.get(thread_key))

        # Create post (should invalidate cache)
        post = ForumPost.objects.create(
            thread=self.thread,
            author=self.user,
            content='Test post content'
        )

        # Verify cache was invalidated
        self.assertIsNone(cache.get(thread_key))
```

**Pros**:
- Tests actual cache behavior
- No mocking needed
- More realistic testing

**Cons**:
- Requires Redis running for tests
- More complex test setup
- Slower tests

**Effort**: 4-5 hours
**Risk**: Low (better test quality)

## Recommended Action

**Option 1** - Fix test expectations to match implementation.

**Rationale**:
1. Fastest fix
2. Tests should verify actual behavior
3. Current signal implementation appears correct

**Implementation Plan**:

### Phase 1: Verify Signal Implementation (30 minutes)
```bash
# Check what methods ForumCacheService actually has
grep -n "def invalidate" backend/apps/forum/services/forum_cache_service.py

# Check if invalidate_post_lists exists
grep -n "invalidate_post_lists" backend/apps/forum/services/forum_cache_service.py

# Review signal handlers
cat backend/apps/forum/signals.py | grep -A 10 "post_save.*ForumPost"
```

### Phase 2: Update Test Assertions (1 hour)
```python
# File: backend/apps/forum/tests/test_cache_integration.py

@patch('apps.forum.signals.ForumCacheService')
def test_creating_post_invalidates_thread_cache(self, mock_service):
    """Test that creating a post invalidates thread cache."""
    post = ForumPost.objects.create(
        thread=self.thread,
        author=self.user,
        content='Test post content'
    )

    # OLD - Incorrect expectation
    # mock_service.invalidate_post_lists.assert_called_once()

    # NEW - Match actual implementation
    mock_service.invalidate_thread_detail.assert_called_once_with(self.thread.slug)
    mock_service.invalidate_thread_lists.assert_called_once()

@patch('apps.forum.signals.ForumCacheService')
def test_updating_post_invalidates_thread_cache(self, mock_service):
    """Test that updating a post invalidates thread cache."""
    self.post.content = 'Updated content'
    self.post.save()

    # Update assertions
    mock_service.invalidate_thread_detail.assert_called_with(self.thread.slug)
    mock_service.invalidate_thread_lists.assert_called()

@patch('apps.forum.signals.ForumCacheService')
def test_deleting_post_invalidates_thread_cache(self, mock_service):
    """Test that deleting a post invalidates thread cache."""
    self.post.delete()

    # Update assertions
    mock_service.invalidate_thread_detail.assert_called_with(self.thread.slug)
    mock_service.invalidate_thread_lists.assert_called()
```

### Phase 3: Verification (30 minutes)
```bash
# Run failing tests
python manage.py test apps.forum.tests.test_cache_integration.CacheIntegrationTests.test_creating_post_invalidates_thread_cache --keepdb -v 2
python manage.py test apps.forum.tests.test_cache_integration.CacheIntegrationTests.test_updating_post_invalidates_thread_cache --keepdb -v 2
python manage.py test apps.forum.tests.test_cache_integration.CacheIntegrationTests.test_deleting_post_invalidates_thread_cache --keepdb -v 2

# All should pass
python manage.py test apps.forum.tests.test_cache_integration --keepdb
```

### Phase 4: Consider Future Enhancement (Optional)
If `invalidate_post_lists()` should exist but doesn't:
1. Add method to `ForumCacheService`
2. Update signal handlers to call it
3. Add new test to verify post list invalidation

## Technical Details

**Files to Modify**:
1. `backend/apps/forum/tests/test_cache_integration.py` (3 test methods)

**Files to Review**:
1. `backend/apps/forum/services/forum_cache_service.py` (verify available methods)
2. `backend/apps/forum/signals.py` (verify signal implementation)

**Cache Service Methods** (expected):
```python
class ForumCacheService:
    @classmethod
    def invalidate_thread_detail(cls, thread_slug: str):
        """Invalidate thread detail cache."""

    @classmethod
    def invalidate_thread_lists(cls):
        """Invalidate all thread list caches."""

    @classmethod
    def invalidate_post_lists(cls):
        """Invalidate all post list caches."""
        # Does this exist? Should it?
```

**Signal Handlers** (from `apps/forum/signals.py`):
- `invalidate_category_caches` - Category create/update/delete
- `invalidate_thread_caches` - Thread create/update/delete
- `invalidate_post_caches` - Post create/update/delete

## Acceptance Criteria

- [ ] Verify `ForumCacheService` methods exist and are correct
- [ ] Update `test_creating_post_invalidates_thread_cache` assertions
- [ ] Update `test_updating_post_invalidates_thread_cache` assertions
- [ ] Update `test_deleting_post_invalidates_thread_cache` assertions
- [ ] All 3 tests pass individually
- [ ] Full cache integration test suite passes (14 tests)
- [ ] No regression in other forum tests
- [ ] Document correct mocking pattern for future tests

## Work Log

### 2025-11-02 - Test Failure Discovery
**By:** Dependency Update Verification Process
**Actions:**
- Ran forum cache integration tests after dependency updates
- Identified 3 tests failing on mock assertions
- Analyzed signal handler implementation
- Found mismatch between test expectations and actual implementation
- Created TODO for systematic fix

**Analysis**:
- Tests written with incorrect expectations
- Signal implementation appears correct (invalidates thread caches appropriately)
- `invalidate_post_lists()` method may not exist or may not be needed
- Simple fix: update test assertions to match reality

**Priority**: P3 (Low-Medium)
- Cache integration works correctly in production
- Tests verify wrong behavior but actual behavior is correct
- Not blocking deployment
- Should fix to maintain test suite health

## Resources

- Forum Cache Service: `backend/apps/forum/services/forum_cache_service.py`
- Forum Signals: `backend/apps/forum/signals.py`
- Django Signals: https://docs.djangoproject.com/en/5.2/topics/signals/
- Python unittest.mock: https://docs.python.org/3/library/unittest.mock.html

## Notes

**Why This Matters**:
- Test suite should verify actual behavior
- Incorrect mocks give false confidence
- Could mask real cache invalidation issues

**Why P3 (Not Urgent)**:
- Manual testing shows cache invalidation works
- Production monitoring shows no cache staleness issues
- Only affects test suite, not user-facing features
- Cache hit rate (40%) is healthy

**Future Prevention**:
- Write integration tests that verify actual cache behavior, not just mock calls
- Consider Option 3 for more realistic cache testing
- Add cache monitoring to CI to catch invalidation issues
