# Forum Testing Guide

Complete guide to testing the forum implementation.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Infrastructure](#test-infrastructure)
- [Writing Tests](#writing-tests)
- [Test Patterns](#test-patterns)
- [Running Tests](#running-tests)
- [Test Data](#test-data)
- [Best Practices](#best-practices)

---

## Quick Start

### Run All Forum Tests

```bash
cd backend
python manage.py test apps.forum --keepdb -v 2
```

### Run Specific Test File

```bash
python manage.py test apps.forum.tests.test_models --keepdb
```

### Run With Coverage

```bash
coverage run --source='apps.forum' manage.py test apps.forum
coverage report
coverage html  # Open htmlcov/index.html
```

### Seed Test Data for Development

```bash
python manage.py seed_forum_data
python manage.py seed_forum_data --clear  # Clear first
python manage.py seed_forum_data --scenario=active  # Specific scenario
```

---

## Test Infrastructure

### Directory Structure

```
backend/apps/forum/tests/
├── __init__.py           # Package exports
├── base.py               # Base test cases (ForumTestCase, ForumAPITestCase)
├── factories.py          # Test data factories (UserFactory, ThreadFactory, etc.)
├── fixtures.py           # Reusable test scenarios
├── utils.py              # Helper functions
├── test_models.py        # Model tests
├── test_api.py           # API integration tests
└── test_cache_service.py # Cache service tests
```

### Available Test Classes

#### `ForumTestCase`
Base class for model and service tests.

```python
from apps.forum.tests import ForumTestCase

class MyModelTest(ForumTestCase):
    def test_something(self):
        # self.user, self.category, self.thread, self.post available
        # Cache automatically cleared before/after
        pass
```

**Provides:**
- Auto cache clearing
- Common test data (`user`, `category`, `thread`, `post`)
- Helper assertions (`assertCacheHit`, `assertValidSlug`, `assertValidUUID`)

#### `ForumAPITestCase`
Base class for API tests.

```python
from apps.forum.tests import ForumAPITestCase

class MyAPITest(ForumAPITestCase):
    def test_api_endpoint(self):
        self.authenticate()  # Authenticate with self.user
        response = self.client.get('/api/v1/forum/threads/')
        self.assertAPISuccess(response)
```

**Provides:**
- Authenticated API client
- Authentication helpers (`authenticate()`, `authenticate_as_admin()`)
- API assertions (`assertAPISuccess`, `assertRequiresAuthentication`)

---

## Writing Tests

### Model Tests

```python
from apps.forum.tests import ForumTestCase
from apps.forum.models import Thread

class ThreadModelTest(ForumTestCase):
    """Tests for Thread model."""

    def test_thread_creation(self):
        """Thread is created with all required fields."""
        self.assertIsNotNone(self.thread.id)
        self.assertValidUUID(self.thread.id)
        self.assertValidSlug(self.thread)
        self.assertEqual(self.thread.author, self.user)

    def test_thread_slug_auto_generated(self):
        """Slug is auto-generated with UUID suffix."""
        self.assertIn("test-thread", self.thread.slug)
        # Slug should be longer than title due to UUID
        self.assertGreater(len(self.thread.slug), len("test-thread"))
```

### API Tests

```python
from apps.forum.tests import ForumAPITestCase
from django.urls import reverse

class ThreadAPITest(ForumAPITestCase):
    """Tests for Thread API."""

    def test_list_threads(self):
        """Can list all threads."""
        url = reverse('forum:thread-list')
        response = self.client.get(url)

        self.assertAPISuccess(response)
        self.assertPaginatedResponse(response, min_count=1)

    def test_create_thread_requires_auth(self):
        """Creating thread requires authentication."""
        url = reverse('forum:thread-list')
        data = {'title': 'New Thread', 'category': self.category.id}

        self.assertRequiresAuthentication(url, method='post', data=data)

    def test_thread_detail_has_posts(self):
        """Thread detail includes posts."""
        url = reverse('forum:thread-detail', kwargs={'slug': self.thread.slug})
        response = self.client.get(url)

        self.assertAPISuccess(response)
        self.assertAPIResponseHasFields(response, ['id', 'title', 'posts'])
        self.assertGreater(len(response.data['posts']), 0)
```

### Cache Service Tests

```python
from apps.forum.tests import ForumTestCase
from apps.forum.services import ForumCacheService

class ForumCacheServiceTest(ForumTestCase):
    """Tests for ForumCacheService."""

    def test_get_thread_miss_returns_none(self):
        """Cache miss returns None."""
        result = ForumCacheService.get_thread('nonexistent')
        self.assertIsNone(result)

    def test_get_thread_hit_returns_data(self):
        """Cache hit returns cached data."""
        test_data = {'slug': 'test', 'title': 'Test Thread'}
        ForumCacheService.set_thread('test', test_data)

        result = ForumCacheService.get_thread('test')
        self.assertEqual(result, test_data)
        self.assertCacheHit(ForumCacheService._generate_thread_key('test'))
```

---

## Test Patterns

### Using Factories

```python
from apps.forum.tests import UserFactory, ThreadFactory, PostFactory

# Create single instances
user = UserFactory.create(username='alice')
thread = ThreadFactory.create(author=user)
post = PostFactory.create(thread=thread, author=user)

# Create batches
users = UserFactory.create_batch(5)
threads = ThreadFactory.create_batch(3, category=category)

# Create thread with posts
thread = ThreadFactory.create_with_posts(post_count=10)

# Create post with rich content
post = PostFactory.create_with_rich_content(thread=thread)

# Create mixed reactions
result = ReactionFactory.create_mixed_reactions(post=post)
# result = {'post': post, 'reactions': {...}, 'total_count': 18}
```

### Using Fixtures

```python
from apps.forum.tests import ForumTestFixtures

# Basic forum setup
data = ForumTestFixtures.create_basic_forum()
# data = {'category': ..., 'threads': [...], 'users': [...]}

# Active discussion with reactions
data = ForumTestFixtures.create_active_discussion()
# data = {'thread': ..., 'posts': [...], 'reactions': {...}}

# Forum with image attachments
data = ForumTestFixtures.create_forum_with_attachments()
# data = {'thread': ..., 'posts': [...], 'attachments': [...]}

# Search test data
data = ForumTestFixtures.create_search_test_data()
# data = {'threads': {...}, 'users': [...], 'categories': [...]}
```

### Query Count Assertions

```python
def test_thread_list_query_count(self):
    """Thread list view uses <12 queries."""
    with self.assertQueryCountLessThan(12):
        response = self.client.get('/api/v1/forum/threads/')
        self.assertAPISuccess(response)
```

### Testing Permissions

```python
def test_only_author_can_edit_post(self):
    """Only post author can edit post."""
    other_user = UserFactory.create()

    # Authenticate as other user
    self.authenticate(user=other_user)

    url = reverse('forum:post-detail', kwargs={'pk': self.post.id})
    response = self.client.patch(url, {'content_raw': 'Modified'})

    # Should be forbidden
    self.assertAPIError(response, status_code=403)
```

---

## Running Tests

### Basic Commands

```bash
# All forum tests
python manage.py test apps.forum

# Specific test file
python manage.py test apps.forum.tests.test_models

# Specific test class
python manage.py test apps.forum.tests.test_models.ThreadModelTest

# Specific test method
python manage.py test apps.forum.tests.test_models.ThreadModelTest.test_thread_creation

# Keep database between runs (faster)
python manage.py test apps.forum --keepdb

# Verbose output
python manage.py test apps.forum -v 2

# Parallel execution (faster)
python manage.py test apps.forum --parallel
```

### Coverage Commands

```bash
# Run with coverage
coverage run --source='apps.forum' manage.py test apps.forum

# Show coverage report
coverage report

# Generate HTML coverage report
coverage html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Show missing lines
coverage report -m

# Coverage for specific module
coverage run --source='apps.forum.models' manage.py test apps.forum
```

### CI/CD Commands

```bash
# Full test suite with coverage and linting
make test-forum

# Quick smoke test
python manage.py test apps.forum.tests.test_models --failfast

# Test specific to Phase 1
python manage.py test apps.forum.tests.test_models apps.forum.tests.test_api
```

---

## Test Data

### Seeding Development Data

```bash
# Seed all scenarios
python manage.py seed_forum_data

# Clear existing data first
python manage.py seed_forum_data --clear

# Specific scenario
python manage.py seed_forum_data --scenario=active
python manage.py seed_forum_data --scenario=hierarchy

# Custom amounts
python manage.py seed_forum_data --users=50 --threads=100
```

**Available Scenarios:**
- `basic` - Minimal forum with 3 threads
- `hierarchy` - Category hierarchy with parent/child
- `active` - Active discussion with 10 posts and reactions
- `attachments` - Threads with image attachments
- `moderation` - Mix of normal and flagged content
- `all` - All scenarios (default)

### Manual Test Data Creation

```python
from apps.forum.tests import ForumTestFixtures

# In Django shell
python manage.py shell

>>> from apps.forum.tests import ForumTestFixtures
>>> data = ForumTestFixtures.create_active_discussion()
>>> print(f"Created thread: {data['thread'].title}")
>>> print(f"Posts: {len(data['posts'])}")
>>> print(f"Reactions: {data['reactions']['total_count']}")
```

---

## Best Practices

### 1. Use setUp/tearDown for Common Data

```python
class MyTest(ForumTestCase):
    def setUp(self):
        super().setUp()
        # Create test-specific data
        self.special_category = CategoryFactory.create(name='Special')

    def tearDown(self):
        super().tearDown()
        # Clean up if needed (cache already cleared)
```

### 2. Use Factories Over Manual Creation

```python
# ❌ Bad: Manual creation
user = User.objects.create_user(username='test', password='test')
category = Category.objects.create(name='Test', slug='test')

# ✅ Good: Use factories
user = UserFactory.create()
category = CategoryFactory.create()
```

### 3. Test One Thing Per Test

```python
# ❌ Bad: Testing multiple things
def test_thread(self):
    # Tests creation, slug, author, AND listing
    thread = ThreadFactory.create()
    self.assertIsNotNone(thread.slug)
    self.assertEqual(thread.author, self.user)
    threads = Thread.objects.all()
    self.assertEqual(threads.count(), 1)

# ✅ Good: One test per concern
def test_thread_creation(self):
    thread = ThreadFactory.create()
    self.assertIsNotNone(thread.id)

def test_thread_slug_generated(self):
    thread = ThreadFactory.create()
    self.assertValidSlug(thread)

def test_thread_has_author(self):
    thread = ThreadFactory.create(author=self.user)
    self.assertEqual(thread.author, self.user)
```

### 4. Use Descriptive Test Names

```python
# ❌ Bad: Vague name
def test_thread(self):
    pass

# ✅ Good: Describes what's being tested
def test_thread_slug_auto_generated_from_title(self):
    pass
```

### 5. Test Edge Cases

```python
def test_thread_with_very_long_title(self):
    """Thread handles 200 character title limit."""
    long_title = 'A' * 200
    thread = ThreadFactory.create(title=long_title)
    self.assertEqual(len(thread.title), 200)

def test_thread_with_empty_excerpt(self):
    """Thread allows empty excerpt."""
    thread = ThreadFactory.create(excerpt='')
    self.assertEqual(thread.excerpt, '')
```

### 6. Use `--keepdb` for Speed

```bash
# First run (slow): Creates database
python manage.py test apps.forum --keepdb

# Subsequent runs (fast): Reuses database
python manage.py test apps.forum --keepdb
```

### 7. Clear Cache in Tests

```python
# Cache is automatically cleared in ForumTestCase/ForumAPITestCase
# If you need manual clearing:
from django.core.cache import cache

def test_something_with_cache(self):
    cache.clear()  # Start with clean cache
    # ... test code ...
```

### 8. Test Coverage Goal: >85%

```bash
# Check current coverage
coverage report

# Identify missing coverage
coverage report -m

# Goal: >85% for Phase 1
```

---

## Common Test Scenarios

### Testing Slugs

```python
def test_slug_uniqueness(self):
    """Slugs must be unique."""
    thread1 = ThreadFactory.create(title="Same Title")
    thread2 = ThreadFactory.create(title="Same Title")
    self.assertNotEqual(thread1.slug, thread2.slug)
```

### Testing Reactions

```python
def test_toggle_reaction_creates_new(self):
    """Toggling creates reaction if doesn't exist."""
    from apps.forum.models import Reaction

    reaction, created = Reaction.toggle_reaction(
        post_id=self.post.id,
        user_id=self.user.id,
        reaction_type='like'
    )
    self.assertTrue(created)
    self.assertTrue(reaction.is_active)

def test_toggle_reaction_deactivates_existing(self):
    """Toggling deactivates existing reaction."""
    from apps.forum.models import Reaction

    # First toggle: create
    Reaction.toggle_reaction(self.post.id, self.user.id, 'like')

    # Second toggle: deactivate
    reaction, created = Reaction.toggle_reaction(
        self.post.id, self.user.id, 'like'
    )
    self.assertFalse(created)
    self.assertFalse(reaction.is_active)
```

### Testing Permissions

```python
def test_anonymous_can_read(self):
    """Anonymous users can read threads."""
    self.unauthenticate()
    url = reverse('forum:thread-detail', kwargs={'slug': self.thread.slug})
    response = self.client.get(url)
    self.assertAPISuccess(response)

def test_authenticated_can_post(self):
    """Authenticated users can create posts."""
    self.authenticate()
    url = reverse('forum:post-list')
    data = {
        'thread': self.thread.id,
        'content_raw': 'Test post'
    }
    response = self.client.post(url, data)
    self.assertAPISuccess(response, status_code=201)
```

---

## Troubleshooting

### Tests Failing Due to Cache

**Problem**: Tests pass individually but fail when run together.

**Solution**: Ensure cache is cleared in `setUp` or use `ForumTestCase`.

```python
def setUp(self):
    super().setUp()
    cache.clear()  # Explicit clear
```

### Database Constraint Violations

**Problem**: UniqueConstraint violation on slug/email.

**Solution**: Use factories with unique values or clear DB between tests.

```python
# Use unique usernames
user1 = UserFactory.create(username='user1')
user2 = UserFactory.create(username='user2')

# Or let factory auto-generate
user1 = UserFactory.create()  # username='user_abc123'
user2 = UserFactory.create()  # username='user_def456'
```

### Slow Tests

**Problem**: Tests take too long to run.

**Solutions**:
1. Use `--keepdb` flag
2. Use `--parallel` for parallel execution
3. Reduce test data creation
4. Mock expensive operations

```bash
# Parallel execution (4 processes)
python manage.py test apps.forum --parallel=4 --keepdb
```

---

## Resources

- **Django Testing Docs**: https://docs.djangoproject.com/en/5.2/topics/testing/
- **DRF Testing Docs**: https://www.django-rest-framework.org/api-guide/testing/
- **Coverage.py Docs**: https://coverage.readthedocs.io/
- **Blog Test Reference**: `apps/blog/tests/test_blog_cache_service.py`

---

**Last Updated**: 2025-10-29
**Phase**: 1 (Core Models & API)
**Test Coverage Target**: >85%
