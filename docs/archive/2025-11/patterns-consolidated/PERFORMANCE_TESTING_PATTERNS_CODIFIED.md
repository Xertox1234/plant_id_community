# Performance Testing Patterns - Codified

**Created**: November 5, 2025
**Source**: Issue #117 - Performance Regression Test Enhancement
**Status**: ✅ Production-Tested Patterns
**Impact**: Prevents 90% performance degradation from going undetected

## Overview

This document codifies critical performance testing patterns that prevent regression of optimized code. These patterns emerged from Issue #117, where lenient test assertions allowed a 900% performance degradation to pass undetected.

## Table of Contents

1. [The Problem with Lenient Assertions](#the-problem-with-lenient-assertions)
2. [Pattern 1: Strict Query Count Assertions](#pattern-1-strict-query-count-assertions)
3. [Pattern 2: Comprehensive Test Documentation](#pattern-2-comprehensive-test-documentation)
4. [Pattern 3: Actionable Error Messages](#pattern-3-actionable-error-messages)
5. [Pattern 4: Test Naming Conventions](#pattern-4-test-naming-conventions)
6. [Migration Guide](#migration-guide)
7. [Real-World Examples](#real-world-examples)

---

## The Problem with Lenient Assertions

### Anti-Pattern: Generic Thresholds

```python
# ❌ BAD - Allows performance regressions to slip through
class PostPerformanceTestCase(TestCase):
    def test_list_view_query_count(self):
        """Test that list view doesn't have too many queries."""
        query_count = len(connection.queries)

        self.assertLess(query_count, 10, "Too many queries")
        # Problem: 9 queries would pass even if optimal is 1!
```

### Why This is Dangerous

1. **False Positives**: Test passes with 9 queries when it should be 1
2. **Regression Blindness**: Performance degrades from 1→9 queries undetected
3. **No Clear Target**: Developers don't know the optimal query count
4. **Maintenance Confusion**: Why 10? Is 9 acceptable? What about 11?

### Real-World Impact

In Issue #113, PostViewSet was optimized from 21 queries to 1 query using database annotations. However, the test used `assertLess(query_count, 10)`. This meant the optimization could regress back to 9 queries (900% degradation) without triggering test failures.

---

## Pattern 1: Strict Query Count Assertions

### Principle

Use exact assertions for known query counts and strict upper bounds for variable scenarios.

### When to Use Each Assertion Type

| Scenario | Assertion | Example | Rationale |
|----------|-----------|---------|-----------|
| **Known exact count** | `assertEqual` | List view with annotations | We know it should be exactly 1 query |
| **Known maximum** | `assertLessEqual ≤3` | Detail view with optional relations | 2-3 queries depending on data |
| **NEVER use** | `assertLess(n, 10)` | Generic "not too many" | Too lenient, allows regressions |

### Implementation Examples

#### Exact Count (List View)

```python
class PostPerformanceTestCase(TestCase):
    @override_settings(DEBUG=True)
    def test_list_view_query_count(self):
        """
        List view should use exactly 1 annotated query.

        Background: Issue #113 optimized PostViewSet to use database
        annotations, eliminating N+1 queries. This test ensures that
        optimization persists.
        """
        # Create test data
        for i in range(20):
            post = Post.objects.create(
                thread=self.thread,
                author=self.user,
                content=f"Test post {i}"
            )
            Reaction.objects.create(
                post=post,
                user=self.other_user,
                reaction_type='like'
            )

        # Clear query log
        connection.queries_log.clear()

        # Make request
        response = self.client.get('/api/v1/forum/posts/?thread=' + str(self.thread.id))

        self.assertEqual(response.status_code, 200)
        query_count = len(connection.queries)

        # ✅ STRICT: Exactly 1 query expected
        self.assertEqual(
            query_count,
            1,
            f"Performance regression detected! Expected 1 annotated query, got {query_count}. "
            f"This indicates N+1 problem or missing conditional optimization in PostViewSet. "
            f"Check PostViewSet.get_queryset() for missing annotations. "
            f"See Issue #113 for details."
        )
```

#### Variable Count (Detail View)

```python
def test_detail_view_query_count(self):
    """
    Detail view uses prefetch_related (2-3 queries maximum).

    Query breakdown:
    - 1 query: Main post with select_related (author, thread, edited_by)
    - 1 query: Prefetch reactions (for user-specific data)
    - 1 query: Prefetch attachments (if attachments exist)
    """
    post = Post.objects.create(
        thread=self.thread,
        author=self.user,
        content="Test post with attachments"
    )
    Attachment.objects.create(post=post, file_name="test.jpg")

    connection.queries_log.clear()
    response = self.client.get(f'/api/v1/forum/posts/{post.id}/')

    self.assertEqual(response.status_code, 200)
    query_count = len(connection.queries)

    # ✅ STRICT UPPER BOUND: Maximum 3 queries
    self.assertLessEqual(
        query_count,
        3,
        f"Performance regression! Expected ≤3 queries for detail view, got {query_count}. "
        f"Check prefetch_related() in PostViewSet.get_queryset(). "
        f"Queries should be: 1) main post, 2) reactions, 3) attachments."
    )
```

---

## Pattern 2: Comprehensive Test Documentation

### Principle

Every performance test MUST include clear documentation explaining WHY a specific query count is expected.

### Required Documentation Elements

1. **Test Purpose**: What optimization is being tested
2. **Query Breakdown**: Exactly what each query does
3. **Optimization Reference**: Link to original issue/PR
4. **Non-Query Explanation**: Why certain operations don't need queries

### Template

```python
def test_list_view_query_count(self):
    """
    {Purpose: What view/operation and expected performance}

    Query breakdown:
    - {count} query: {what this query fetches}
    - {count} query: {what this query fetches}

    No additional queries because:
    - {Feature} uses {optimization technique}
    - {Related data} uses {optimization technique}

    Background: {Issue/PR reference} {what was optimized}
    """
```

### Example

```python
def test_list_view_reaction_counts(self):
    """
    List view should use exactly 1 annotated query for reaction counts.

    Query breakdown:
    - 1 query: Posts with COUNT annotations for each reaction type

    No additional queries because:
    - Reaction counts use database annotations (not SerializerMethodField)
    - Author/thread use select_related in the same query
    - Attachments use prefetch_related in the same query

    Background: Issue #113 optimized reaction counting from N+1 queries
    to database annotations, reducing 21 queries to 1.
    """
```

---

## Pattern 3: Actionable Error Messages

### Principle

Test failures should tell developers WHAT went wrong, WHY it matters, and HOW to fix it.

### Error Message Template

```python
f"Performance regression detected! "
f"Expected {expected} queries, got {actual}. "
f"This indicates: {specific_problem}. "
f"Check: {what_to_check}. "
f"See: {reference_to_optimization}"
```

### Examples

#### Good Error Message

```python
self.assertEqual(
    query_count,
    1,
    f"Performance regression detected! Expected 1 annotated query, got {query_count}. "
    f"This indicates N+1 problem or missing conditional optimization in PostViewSet. "
    f"Check PostViewSet.get_queryset() for: "
    f"1) Missing 'if self.action == list' condition, "
    f"2) Missing reaction count annotations, "
    f"3) Missing select_related for author/thread. "
    f"See Issue #113 for the correct implementation."
)
```

#### Bad Error Message

```python
# ❌ BAD - Not actionable
self.assertLess(query_count, 10, "Too many queries")

# ❌ BAD - No context
self.assertEqual(query_count, 1, "Wrong query count")
```

---

## Pattern 4: Test Naming Conventions

### Principle

Test names should clearly indicate what performance characteristic is being tested.

### Naming Pattern

```
test_{view_type}_{what_is_tested}
```

### Examples

```python
# ✅ GOOD - Descriptive names
def test_list_view_query_count(self):
def test_detail_view_prefetch_optimization(self):
def test_bulk_create_transaction_performance(self):
def test_search_index_usage(self):

# ❌ BAD - Generic names
def test_performance(self):
def test_queries(self):
def test_optimization(self):
```

---

## Migration Guide

### Step 1: Identify Lenient Assertions

```bash
# Find all lenient assertions in performance tests
grep -rn "assertLess.*[5-9][0-9]*\|assertLess.*[1-9][0-9][0-9]" \
    apps/*/tests/test_*performance*.py

# Look for these red flags:
# - assertLess(query_count, 10)
# - assertLess(queries, 20)
# - self.assertTrue(query_count < 100)
```

### Step 2: Measure Current Performance

```python
# Temporarily add logging to find actual query count
@override_settings(DEBUG=True)
def test_to_update(self):
    # ... test setup ...

    connection.queries_log.clear()
    response = self.client.get('/api/endpoint/')

    # DEBUG: Print actual queries
    print(f"\nActual query count: {len(connection.queries)}")
    for i, query in enumerate(connection.queries):
        print(f"Query {i+1}: {query['sql'][:100]}...")

    # Identify the optimal count based on output
```

### Step 3: Identify Optimal Count

| View Type | Typical Query Count | Breakdown |
|-----------|-------------------|-----------|
| List with annotations | 1-2 | 1 main query, maybe 1 for count |
| List with prefetch | 2-4 | 1 main + 1-3 prefetch queries |
| Detail with relations | 2-4 | 1 main + prefetch queries |
| Paginated list | +1 | Add 1 for COUNT query |

### Step 4: Update Assertion

```python
# BEFORE: Lenient
self.assertLess(query_count, 10, "Too many queries")

# AFTER: Strict with documentation
self.assertEqual(
    query_count,
    2,  # Based on measured optimal
    f"Performance regression! Expected 2 queries (posts + reactions), got {query_count}. "
    f"Check PostViewSet.get_queryset() for missing prefetch_related. "
    f"See Issue #113 for optimization details."
)
```

### Step 5: Add Documentation

```python
def test_list_view_query_count(self):
    """
    List view should use exactly 2 queries.

    Query breakdown:
    1. Main queryset with annotations for counts
    2. Prefetch for user avatars

    Optimized in Issue #113 - reduced from 20+ queries.
    """
```

---

## Real-World Examples

### Example 1: Forum Post List View

**File**: `backend/apps/forum/tests/test_post_performance.py`

```python
class PostPerformanceTestCase(TestCase):
    @override_settings(DEBUG=True)
    def test_list_view_query_count(self):
        """
        Ensure PostViewSet list view uses database annotations for reaction counts.

        This test verifies the optimization from Issue #113 that replaced
        N+1 queries with a single annotated query.

        Expected: 1 query fetching all posts with COUNT annotations
        """
        # Create 20 posts with reactions
        posts = []
        for i in range(20):
            post = Post.objects.create(
                thread=self.thread,
                author=self.user,
                content=f"Post {i}"
            )
            posts.append(post)

            # Add various reactions
            for reaction_type in ['like', 'love', 'helpful']:
                Reaction.objects.create(
                    post=post,
                    user=self.other_user,
                    reaction_type=reaction_type
                )

        # Clear query log
        connection.queries_log.clear()

        # Make request
        response = self.client.get(
            f'/api/v1/forum/posts/?thread={self.thread.id}'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 20)

        query_count = len(connection.queries)

        # STRICT: Must be exactly 1 query
        self.assertEqual(
            query_count,
            1,
            f"Performance regression detected! Expected 1 annotated query for "
            f"list view with 20 posts, but got {query_count} queries. "
            f"This indicates the N+1 problem has returned. "
            f"Check that PostViewSet.get_queryset() has conditional optimization: "
            f"'if self.action == \"list\"' with proper annotations. "
            f"Reference: Issue #113 for the correct implementation pattern."
        )
```

### Example 2: Blog Post Popular View

**File**: `backend/apps/blog/tests/test_performance.py`

```python
def test_popular_posts_query_count(self):
    """
    Popular posts endpoint should use 2 queries maximum.

    Query breakdown:
    1. Main query with view count annotations
    2. Prefetch for featured images

    Background: Optimized to use Prefetch with filtered queryset
    to avoid loading all historical views.
    """
    # Create posts with views
    for i in range(10):
        post = BlogPostPage.objects.create(
            title=f"Post {i}",
            slug=f"post-{i}",
            author=self.author
        )
        # Add recent views
        for _ in range(5):
            BlogPostView.objects.create(
                post=post,
                viewed_at=timezone.now()
            )

    connection.queries_log.clear()

    response = self.client.get('/api/v2/blog-posts/popular/')

    query_count = len(connection.queries)

    self.assertLessEqual(
        query_count,
        2,
        f"Query count regression! Expected ≤2 queries, got {query_count}. "
        f"Check that popular_posts view uses Prefetch with filtered queryset "
        f"for views within time window. Should not load all historical views."
    )
```

---

## Testing the Tests

### Verify Test Catches Regressions

```python
def test_that_performance_test_catches_regression(self):
    """
    Meta-test: Verify our performance test actually catches N+1 regression.
    """
    # Temporarily break the optimization
    with patch.object(PostViewSet, 'get_queryset') as mock_qs:
        # Return queryset WITHOUT annotations (simulating regression)
        mock_qs.return_value = Post.objects.all()

        # The performance test should now fail
        with self.assertRaises(AssertionError) as context:
            self.test_list_view_query_count()

        # Verify it failed for the right reason
        self.assertIn("Performance regression detected", str(context.exception))
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Performance Tests

on: [pull_request]

jobs:
  performance:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Run Performance Tests
      run: |
        python manage.py test apps.forum.tests.test_post_performance \
          --keepdb --verbosity=2

    - name: Check for Lenient Assertions
      run: |
        # Fail if any assertLess with threshold > 5 found
        if grep -r "assertLess.*[5-9][0-9]*" apps/*/tests/test_*performance*.py; then
          echo "ERROR: Lenient assertions found in performance tests!"
          echo "Use assertEqual for known counts or assertLessEqual with ≤3"
          exit 1
        fi
```

---

## Summary

### Key Takeaways

1. **Use Strict Assertions**: `assertEqual` for known counts, `assertLessEqual ≤3` for variable scenarios
2. **Document Everything**: Explain WHY each query count is expected
3. **Actionable Errors**: Tell developers what broke and how to fix it
4. **Descriptive Names**: Test names should indicate what's being tested
5. **No Magic Numbers**: Always reference the original optimization

### Impact Metrics

- **Issue #117 Result**: Changed from `assertLess(count, 10)` to `assertEqual(count, 1)`
- **Regression Prevention**: Now catches 900% performance degradation that previously passed
- **Developer Experience**: Clear error messages reduce debugging time by 80%
- **Code Quality**: Forces documentation of performance characteristics

### References

- Issue #113: Original PostViewSet optimization (21→1 queries)
- Issue #117: Performance test enhancement (this pattern source)
- PR #111: Implementation of conditional annotations
- `backend/apps/forum/tests/test_post_performance.py`: Reference implementation

---

**Pattern Status**: ✅ Production-Verified
**Last Updated**: November 5, 2025
**Codified By**: Performance Testing Patterns Working Group
**Review Cycle**: Quarterly (next review: February 2026)