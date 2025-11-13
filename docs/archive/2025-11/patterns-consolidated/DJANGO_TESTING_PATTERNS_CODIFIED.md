# Django Testing Patterns Codified

**Version**: 1.0.0
**Date**: November 5, 2025
**Project**: Plant ID Community Backend
**Django Version**: 5.2.7
**DRF Version**: 3.16.1
**Python Version**: 3.13.9

---

## Table of Contents

1. [Django Testing Framework](#1-django-testing-framework)
2. [Django REST Framework Testing](#2-django-rest-framework-testing)
3. [Cache Testing Utilities](#3-cache-testing-utilities)
4. [Signal Testing Patterns](#4-signal-testing-patterns)
5. [Time and Date Mocking](#5-time-and-date-mocking)
6. [Test Data Factories](#6-test-data-factories)
7. [Coverage and Quality](#7-coverage-and-quality)
8. [Performance Testing](#8-performance-testing)
9. [Project-Specific Patterns](#9-project-specific-patterns)

---

## 1. Django Testing Framework

### 1.1 TestCase vs TransactionTestCase

**Official Documentation**: https://docs.djangoproject.com/en/5.2/topics/testing/tools/

#### TestCase (Preferred for Most Tests)

**Characteristics:**
- Wraps tests within two nested `atomic()` blocks (one for the whole class, one for each test)
- Uses database transaction facilities to speed up resetting the database
- Fastest option for most test scenarios
- Does NOT commit transactions to the database

**When to Use:**
- Standard CRUD operations
- Most DRF viewset tests
- Serializer validation tests
- Permission and authentication tests

**Example from Project:**
```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

class PostViewSetTests(TestCase):
    """Test PostViewSet API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_list_posts_requires_thread_parameter(self):
        """GET /posts/ without thread parameter returns 400."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/forum/posts/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
```

#### TransactionTestCase (For Transaction Testing)

**Characteristics:**
- Resets database by truncating all tables after each test
- Can call `commit()` and `rollback()` and observe effects
- Slower than TestCase (no transaction optimization)
- Required for testing transaction-specific behavior

**When to Use:**
- Testing `select_for_update()` behavior
- Testing explicit transaction commit/rollback
- Testing signals that depend on transaction state
- Testing database constraints that require commit

**Example:**
```python
from django.test import TransactionTestCase

class PaymentTransactionTests(TransactionTestCase):
    """Test payment processing with real transactions."""

    def test_payment_rollback_on_error(self):
        """Test that payment rolls back on processing error."""
        # Can test actual commit/rollback behavior
        pass
```

**Key Difference:**
> TestCase wraps tests in transactions (faster, no real commits).
> TransactionTestCase truncates tables (slower, real commits/rollbacks).

---

## 2. Django REST Framework Testing

### 2.1 APITestCase and APIClient

**Official Documentation**: https://www.django-rest-framework.org/api-guide/testing/

#### APIClient Authentication

**Pattern: force_authenticate() for Testing**
```python
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class ThreadViewSetTests(APITestCase):
    """Test ThreadViewSet endpoints."""

    def setUp(self):
        """Set up test client and authentication."""
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_thread_requires_authentication(self):
        """POST /threads/ requires authentication."""
        # Unauthenticated request
        response = self.client.post('/api/v1/forum/threads/', {
            'title': 'Test Thread',
            'category': 'plant-care'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_thread_with_authentication(self):
        """POST /threads/ succeeds with authentication."""
        # Force authentication for this request
        self.client.force_authenticate(user=self.user)

        response = self.client.post('/api/v1/forum/threads/', {
            'title': 'Test Thread',
            'category': 'plant-care'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
```

**Note on force_authenticate():**
- Bypasses authentication entirely (no JWT tokens needed)
- Ideal for testing business logic without auth complexity
- Use `client.force_authenticate(user=user)` or `client.force_authenticate(user=None)` to unauthenticate

**Known Limitation:**
> Calling `force_authenticate()` with a token parameter but without a user parameter doesn't work as intended. Always provide `user` parameter.

### 2.2 Status Code Constants

**Official Documentation**: https://www.django-rest-framework.org/api-guide/status-codes/

**Best Practice: Always Use Named Constants**

❌ **Bad (Magic Numbers):**
```python
self.assertEqual(response.status_code, 200)
self.assertEqual(response.status_code, 404)
self.assertEqual(response.status_code, 401)
```

✅ **Good (Named Constants):**
```python
from rest_framework import status

self.assertEqual(response.status_code, status.HTTP_200_OK)
self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
```

**Common Status Codes in Project:**
```python
# Success codes
status.HTTP_200_OK              # GET, PUT, PATCH success
status.HTTP_201_CREATED         # POST success (resource created)
status.HTTP_204_NO_CONTENT      # DELETE success

# Client error codes
status.HTTP_400_BAD_REQUEST     # Validation error, missing required field
status.HTTP_401_UNAUTHORIZED    # Authentication required
status.HTTP_403_FORBIDDEN       # Permission denied
status.HTTP_404_NOT_FOUND       # Resource not found
status.HTTP_429_TOO_MANY_REQUESTS  # Rate limit exceeded

# Server error codes
status.HTTP_500_INTERNAL_SERVER_ERROR  # Unexpected server error
status.HTTP_503_SERVICE_UNAVAILABLE    # Service temporarily down
```

**Helper Functions:**
```python
from rest_framework import status

# Test if status code is in range
self.assertTrue(status.is_success(response.status_code))  # 2xx
self.assertTrue(status.is_client_error(response.status_code))  # 4xx
self.assertTrue(status.is_server_error(response.status_code))  # 5xx
```

### 2.3 Testing Permissions

**Pattern: Test Both Authenticated and Unauthenticated**
```python
class PostPermissionTests(APITestCase):
    """Test post permissions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.author = User.objects.create_user(username='author', password='pass')
        self.other_user = User.objects.create_user(username='other', password='pass')

        self.post = Post.objects.create(
            author=self.author,
            content_raw='Test post'
        )

    def test_list_posts_anonymous(self):
        """Anonymous users can list posts (read-only)."""
        response = self.client.get('/api/v1/forum/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_post_requires_authentication(self):
        """Creating posts requires authentication."""
        response = self.client.post('/api/v1/forum/posts/', {
            'content_raw': 'New post'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_post_requires_ownership(self):
        """Users can only update their own posts."""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.patch(f'/api/v1/forum/posts/{self.post.id}/', {
            'content_raw': 'Updated content'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_can_update_post(self):
        """Authors can update their own posts."""
        self.client.force_authenticate(user=self.author)

        response = self.client.patch(f'/api/v1/forum/posts/{self.post.id}/', {
            'content_raw': 'Updated content'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
```

### 2.4 Testing Rate Limiting / Throttling

**Disabling Throttling for Tests:**

**Method 1: DummyCache (Preferred)**
```python
from django.test import TestCase, override_settings

@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
)
class APIThrottleTests(TestCase):
    """Test API with throttling disabled."""

    def test_many_requests_without_throttle(self):
        """Can make many requests when cache is disabled."""
        for i in range(100):
            response = self.client.get('/api/v1/forum/posts/')
            self.assertEqual(response.status_code, 200)
```

**Method 2: Remove Throttle Rates**
```python
@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {}
    }
)
class APINoThrottleTests(TestCase):
    """Test API without throttle classes."""
    pass
```

**Testing Throttle Behavior (When Enabled):**
```python
class ThrottleBehaviorTests(APITestCase):
    """Test that throttling works correctly."""

    def test_rate_limit_exceeded(self):
        """Requests beyond rate limit return 429."""
        self.client.force_authenticate(user=self.user)

        # Make requests up to limit (10 per minute in this example)
        for i in range(10):
            response = self.client.post('/api/v1/forum/posts/', {...})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 11th request should be throttled
        response = self.client.post('/api/v1/forum/posts/', {...})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
```

---

## 3. Cache Testing Utilities

**Official Reference**: https://docs.djangoproject.com/en/5.2/topics/cache/

### 3.1 Cache Clearing in Tests

**Pattern: Clear Cache in setUp/tearDown**
```python
from django.test import TestCase
from django.core.cache import cache

class CacheIntegrationTests(TestCase):
    """Test cache invalidation."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()  # Ensure clean cache state

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()  # Prevent cache pollution
```

**Important Limitation:**
> Django doesn't flush caches between tests automatically (unlike databases). You must manually call `cache.clear()` in `setUp()`/`tearDown()`.

### 3.2 Mocking Cache for Tests

**Pattern: DummyCache Backend**
```python
from django.test import TestCase, override_settings

@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
)
class NoCacheTests(TestCase):
    """Test behavior with cache disabled."""

    def test_functionality_without_cache(self):
        """Verify code works when cache is unavailable."""
        # Cache.set() and cache.get() will be no-ops
        pass
```

**When to Use DummyCache:**
- Testing fallback behavior when cache unavailable
- Eliminating cache side effects between tests
- Testing that code doesn't break without cache

### 3.3 Testing Cache Invalidation

**Pattern: Mock Cache Service Methods**

Example from `backend/apps/forum/tests/test_cache_integration.py`:

```python
from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, call

class CacheIntegrationTests(TestCase):
    """Test cache invalidation via signals."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    @patch('apps.forum.signals.get_forum_cache_service')
    def test_creating_thread_invalidates_cache(self, mock_get_service):
        """
        Test that creating a thread invalidates thread list cache.

        Signal: post_save with created=True
        Expected invalidations:
        - Thread detail cache (new slug)
        - All thread list caches
        - Category cache (thread count changed)
        """
        mock_service = mock_get_service.return_value

        # Create thread (triggers post_save signal)
        thread = Thread.objects.create(
            title="New Thread",
            slug="new-thread",
            category=self.category,
            author=self.user
        )

        # Verify cache invalidation methods were called
        mock_service.invalidate_thread.assert_called_once_with(thread.slug)
        mock_service.invalidate_thread_lists.assert_called_once()
        mock_service.invalidate_category.assert_called_once_with(self.category.slug)
```

**Key Pattern:**
- Mock the cache service at the signal level
- Verify invalidation methods are called with correct arguments
- Use `assert_called_once_with()` for precise verification

---

## 4. Signal Testing Patterns

**Official Reference**: Django signals don't have dedicated testing docs, but community best practices are well-established.

### 4.1 Context Manager Pattern (Recommended)

**Pattern: Catch Signal with Context Manager**
```python
from unittest import mock
from contextlib import contextmanager
from django.db.models.signals import post_save

@contextmanager
def catch_signal(signal):
    """Catch django signal and return the mocked call."""
    handler = mock.Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)

# Usage
def test_post_save_signal_fired(self):
    """Test that post_save signal is fired when creating a post."""
    with catch_signal(post_save) as handler:
        Post.objects.create(content_raw='Test')

        # Verify signal was called
        self.assertEqual(handler.call_count, 1)

        # Check signal arguments
        call_kwargs = handler.call_args[1]
        self.assertEqual(call_kwargs['sender'], Post)
        self.assertTrue(call_kwargs['created'])
```

**Advantages:**
- Automatic cleanup (signal disconnected after test)
- No side effects on other tests
- Access to signal arguments for verification

### 4.2 Mock Signal Receivers

**Pattern: Mock Signal Handler Function**

Project example from `backend/apps/forum/tests/test_cache_integration.py`:

```python
from unittest.mock import patch

class SignalTests(TestCase):
    """Test signal handlers."""

    @patch('apps.forum.signals.invalidate_thread_cache')
    def test_thread_update_calls_cache_invalidation(self, mock_invalidate):
        """Test that updating a thread calls cache invalidation."""
        thread = Thread.objects.create(title='Test')

        # Update thread (triggers post_save signal)
        thread.title = 'Updated'
        thread.save()

        # Verify signal handler was called
        mock_invalidate.assert_called_once_with(
            sender=Thread,
            instance=thread,
            created=False,
            update_fields=None
        )
```

### 4.3 Testing Custom Signals

**Pattern: Emit Custom Signal in Test**
```python
from django.dispatch import Signal, receiver
from unittest.mock import Mock

# Custom signal
trust_level_changed = Signal()

class CustomSignalTests(TestCase):
    """Test custom signal emission."""

    def test_trust_level_changed_signal(self):
        """Test that trust_level_changed signal is emitted correctly."""
        # Create a mock receiver
        mock_handler = Mock()
        trust_level_changed.connect(mock_handler)

        # Emit signal
        trust_level_changed.send(
            sender=UserProfile,
            user=self.user,
            old_level=0,
            new_level=1
        )

        # Verify handler was called with correct arguments
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args[1]
        self.assertEqual(call_kwargs['old_level'], 0)
        self.assertEqual(call_kwargs['new_level'], 1)

        # Clean up
        trust_level_changed.disconnect(mock_handler)
```

---

## 5. Time and Date Mocking

### 5.1 Freezegun for Time Travel

**Package**: `freezegun` (installed in project)
**Documentation**: https://github.com/spulec/freezegun

**Pattern: Freeze Time for Testing**
```python
from freezegun import freeze_time
from django.utils import timezone
from datetime import timedelta

class TrustLevelProgressionTests(TestCase):
    """Test trust level progression over time."""

    @freeze_time("2025-01-01 12:00:00")
    def test_user_promoted_after_30_days(self):
        """Users promoted to BASIC after 30 days + 5 posts."""
        # Create user (time frozen at Jan 1, 2025)
        user = User.objects.create_user(username='testuser')

        # Create 5 posts
        for i in range(5):
            Post.objects.create(author=user, content_raw=f'Post {i}')

        # Advance time 30 days
        with freeze_time("2025-01-31 12:00:00"):
            # Check trust level promotion
            trust_service = TrustLevelService()
            info = trust_service.get_trust_level_info(user)

            self.assertEqual(info['current_level'], TrustLevel.BASIC)
```

**Pattern: Test with Timezone Awareness**
```python
from freezegun import freeze_time
from django.utils import timezone

class TimezoneTests(TestCase):
    """Test timezone-aware datetime handling."""

    @freeze_time("2025-01-01 12:00:00", tz_offset=0)  # UTC
    def test_post_created_at_utc(self):
        """Posts are created with UTC timestamp."""
        post = Post.objects.create(content_raw='Test')

        # Django stores in UTC
        expected_time = timezone.datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(post.created_at, expected_time)
```

**Important: Use timezone.now() not datetime.now()**
```python
# ❌ Bad (naive datetime, won't be frozen correctly)
from datetime import datetime
now = datetime.now()

# ✅ Good (timezone-aware, works with freezegun)
from django.utils import timezone
now = timezone.now()
```

### 5.2 Manual Time Mocking with Patch

**Pattern: Mock timezone.now()**
```python
from unittest.mock import patch
from django.utils import timezone
from datetime import datetime

class TimeBasedTests(TestCase):
    """Test time-based functionality."""

    @patch('django.utils.timezone.now')
    def test_post_age_calculation(self, mock_now):
        """Test calculating post age."""
        # Set mock time
        mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        post = Post.objects.create(content_raw='Test')

        # Advance mock time 5 days
        mock_now.return_value = datetime(2025, 1, 6, 12, 0, 0, tzinfo=timezone.utc)

        age_days = (timezone.now() - post.created_at).days
        self.assertEqual(age_days, 5)
```

---

## 6. Test Data Factories

### 6.1 Factory Pattern (Project Standard)

**Location**: `backend/apps/forum/tests/factories.py`

**Why Factories Over Fixtures:**
- ✅ Faster (no JSON deserialization)
- ✅ Easier to maintain (no schema updates needed)
- ✅ More flexible (generate data on-the-fly)
- ✅ Better readability (explicit parameters)
- ❌ Fixtures are slow, brittle, and hard to maintain

**Project Pattern: Simple Function Factories**

Example from project:
```python
import uuid
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()

class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: str = 'testpass123',
        **kwargs
    ) -> User:
        """Create a test user with sensible defaults."""
        if not username:
            username = f'user_{uuid.uuid4().hex[:8]}'
        if not email:
            email = f'{username}@test.com'

        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            **kwargs
        )

    @staticmethod
    def create_batch(count: int = 5, **kwargs) -> list:
        """Create multiple users."""
        return [UserFactory.create(**kwargs) for _ in range(count)]
```

**Usage in Tests:**
```python
from apps.forum.tests.factories import UserFactory, ThreadFactory, PostFactory

class ThreadTests(TestCase):
    """Test thread functionality."""

    def setUp(self):
        """Set up test data."""
        # Create users
        self.author = UserFactory.create(username='author')
        self.users = UserFactory.create_batch(count=5)

        # Create thread with posts
        self.thread = ThreadFactory.create_with_posts(
            post_count=10,
            author=self.author
        )
```

### 6.2 Factory Boy (Alternative Pattern)

**Package**: `factory_boy==3.3.3` (installed in project)
**Documentation**: https://factoryboy.readthedocs.io/

**Pattern: Class-Based Factories**
```python
import factory
from factory.django import DjangoModelFactory
from apps.forum.models import Thread, Post

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set password after creation."""
        if not create:
            return
        if extracted:
            self.set_password(extracted)
        else:
            self.set_password('testpass123')

class ThreadFactory(DjangoModelFactory):
    class Meta:
        model = Thread

    title = factory.Sequence(lambda n: f'Thread {n}')
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title))
    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)

# Usage
user = UserFactory()
thread = ThreadFactory(author=user)
threads = ThreadFactory.create_batch(10)
```

**When to Use Factory Boy:**
- Complex relationships (SubFactory, RelatedFactory)
- Need for `build()` vs `create()` strategies
- Integration with pytest-factoryboy

**Project Uses Simple Factories Because:**
- More explicit and readable for team
- No magic (clear what's happening)
- Easier to customize per test
- Less dependency overhead

### 6.3 Faker for Realistic Data

**Package**: `Faker==37.12.0` (installed in project)
**Documentation**: https://faker.readthedocs.io/

**Pattern: Generate Realistic Test Data**
```python
from faker import Faker

fake = Faker()

class PostFactory:
    """Factory for creating test posts."""

    @staticmethod
    def create_realistic_post(**kwargs):
        """Create a post with realistic content."""
        return Post.objects.create(
            content_raw=fake.paragraph(nb_sentences=5),
            author=UserFactory.create(
                username=fake.user_name(),
                email=fake.email()
            ),
            **kwargs
        )
```

---

## 7. Coverage and Quality

### 7.1 Coverage Tools

**Installed Packages:**
- `coverage==7.11.0` - Core coverage measurement
- `pytest-cov==7.0.0` - Pytest plugin for coverage
- `django-coverage-plugin==3.1.0` - Coverage for Django templates

**Configuration: pyproject.toml or .coveragerc**
```toml
[tool.coverage.run]
branch = true
source = ["apps"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
precision = 2
show_missing = true
```

**Running Coverage:**
```bash
# With Django test runner
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report

# With pytest
pytest --cov=apps --cov-report=html --cov-report=term
```

### 7.2 Branch Coverage

**What is Branch Coverage?**
- Line coverage: Did this line execute?
- Branch coverage: Did both True and False paths execute?

**Example:**
```python
def process_post(post):
    if post.is_active:
        return publish(post)  # Branch 1
    else:
        return archive(post)  # Branch 2

# Tests need to cover BOTH branches
def test_process_active_post():
    """Test processing active post (Branch 1)."""
    post = Post.objects.create(is_active=True)
    result = process_post(post)
    # Assert publish was called

def test_process_inactive_post():
    """Test processing inactive post (Branch 2)."""
    post = Post.objects.create(is_active=False)
    result = process_post(post)
    # Assert archive was called
```

**Enable Branch Coverage:**
```bash
coverage run --branch manage.py test
```

### 7.3 Assertion Best Practices

**Use Specific Assertions:**
```python
# ❌ Bad (generic, unclear failure message)
self.assertTrue(response.status_code == 200)
self.assertTrue('error' in response.data)

# ✅ Good (specific, clear failure message)
self.assertEqual(response.status_code, status.HTTP_200_OK)
self.assertIn('error', response.data)
self.assertIsNotNone(response.data.get('id'))
self.assertIsInstance(response.data['results'], list)
```

**Common Assertions:**
```python
# Equality
self.assertEqual(actual, expected)
self.assertNotEqual(actual, expected)

# Truthiness
self.assertTrue(condition)
self.assertFalse(condition)
self.assertIsNone(value)
self.assertIsNotNone(value)

# Membership
self.assertIn(item, container)
self.assertNotIn(item, container)

# Types
self.assertIsInstance(obj, Class)
self.assertNotIsInstance(obj, Class)

# Comparisons
self.assertGreater(a, b)
self.assertLess(a, b)
self.assertGreaterEqual(a, b)
self.assertLessEqual(a, b)

# Containers
self.assertListEqual(list1, list2)
self.assertDictEqual(dict1, dict2)
self.assertSetEqual(set1, set2)

# Exceptions
self.assertRaises(ValueError, function, arg1, arg2)
with self.assertRaises(ValueError):
    function(arg1, arg2)

# Regex
self.assertRegex(text, r'pattern')
self.assertNotRegex(text, r'pattern')
```

---

## 8. Performance Testing

### 8.1 Query Count Testing (Issue #117 Pattern)

**Official Documentation**: https://docs.djangoproject.com/en/5.2/topics/testing/tools/#django.test.TransactionTestCase.assertNumQueries

**Pattern: Strict Query Count Assertions**

From `backend/apps/forum/tests/test_post_performance.py`:

```python
from django.test import TestCase, override_settings
from django.db import connection

class PostPerformanceTestCase(TestCase):
    """Test N+1 query optimization for post list view."""

    @override_settings(DEBUG=True)  # Required for query logging
    def test_list_view_query_count(self):
        """
        List view should use single annotated query for optimal performance.

        Regression protection: Ensures conditional annotations are used (Issue #113).
        Any increase from 1 query indicates N+1 or missing optimization.

        Without optimization: 21 queries (1 main + 20 reaction queries)
        With optimization: 1 query (annotations included)
        """
        # Reset query counter
        connection.queries_log.clear()

        # Make list request
        response = self.client.get(f'/api/v1/forum/posts/?thread={self.thread.slug}')

        self.assertEqual(response.status_code, 200)

        # Count queries
        query_count = len(connection.queries)

        # STRICT: Expect exactly 1 query (annotated queryset)
        self.assertEqual(
            query_count,
            1,
            f"Performance regression detected! Expected 1 annotated query, got {query_count}. "
            f"This indicates N+1 problem or missing conditional optimization in PostViewSet. "
            f"See Issue #113 for details."
        )
```

**Why Strict Equality, Not `assertLess`?**

❌ **Bad (Lenient - Misses Regressions):**
```python
# This allows query count to creep up from 1 → 2 → 3 → 9
self.assertLess(query_count, 10)
```

✅ **Good (Strict - Catches Regressions):**
```python
# This catches ANY deviation from expected count
self.assertEqual(query_count, 1)
```

**Pattern: Context Manager for Query Counting**
```python
from django.test.utils import override_settings
from django.db import connection
from django.test import TestCase

class QueryCountTests(TestCase):
    """Test query optimization."""

    @override_settings(DEBUG=True)
    def test_optimized_queryset(self):
        """Test that queryset uses select_related and prefetch_related."""
        # Clear existing queries
        connection.queries_log.clear()

        # Execute code
        threads = Thread.objects.select_related('author', 'category').all()
        list(threads)  # Force evaluation

        # Check query count
        query_count = len(connection.queries)
        self.assertEqual(
            query_count,
            1,
            f"Expected 1 query with select_related, got {query_count}"
        )
```

### 8.2 assertNumQueries Context Manager

**Built-in Django Method:**
```python
from django.test import TestCase

class QueryCountTests(TestCase):
    """Test query optimization."""

    def test_list_threads_query_count(self):
        """Test that listing threads uses optimized queryset."""
        with self.assertNumQueries(1):
            threads = Thread.objects.select_related('author').all()
            list(threads)
```

**Advantages:**
- Built-in Django utility
- Fails if query count doesn't match exactly
- Clear assertion in test

**Disadvantages:**
- Less informative error messages than custom assertions
- Doesn't log actual queries for debugging

### 8.3 Detecting N+1 Queries

**Pattern: Test with Multiple Objects**

Example from project:
```python
def setUp(self):
    """Create test data with multiple posts."""
    # Create 20 posts with reactions
    self.posts = []
    for i in range(20):
        post = Post.objects.create(content_raw=f'Post {i}')
        self.posts.append(post)

        # Add 3 reactions to each post
        for reaction_type in ['like', 'love', 'helpful']:
            Reaction.objects.create(post=post, reaction_type=reaction_type)

@override_settings(DEBUG=True)
def test_list_view_query_count(self):
    """
    Without optimization: 1 + 20 queries (N+1 problem)
    With optimization: 1 query (annotations)
    """
    connection.queries_log.clear()

    response = self.client.get('/api/v1/forum/posts/')

    query_count = len(connection.queries)
    self.assertEqual(query_count, 1, "N+1 query detected!")
```

**Why 20 Objects?**
- Small counts (2-3) might pass accidentally
- 20 objects makes N+1 obvious (21 queries vs 1)
- Realistic test of list view performance

---

## 9. Project-Specific Patterns

### 9.1 Testing with Redis Cache

**Project Requirement**: Redis is required for caching and distributed locks.

**Pattern: Ensure Redis is Running**
```python
from django.core.cache import cache
from django.test import TestCase

class RedisCacheTests(TestCase):
    """Test Redis cache integration."""

    def setUp(self):
        """Verify Redis is available and clear cache."""
        # Check Redis connectivity
        try:
            cache.set('test_key', 'test_value', timeout=1)
            result = cache.get('test_key')
            self.assertEqual(result, 'test_value')
        except Exception as e:
            self.skipTest(f"Redis not available: {e}")

        # Clear cache for clean state
        cache.clear()

    def tearDown(self):
        """Clean up cache after test."""
        cache.clear()
```

**Pattern: Test Cache Service Methods**

From project (`backend/apps/forum/services/forum_cache_service.py`):

```python
from apps.forum.services import ForumCacheService

class CacheServiceTests(TestCase):
    """Test ForumCacheService."""

    def setUp(self):
        """Set up cache service."""
        self.cache_service = ForumCacheService()
        cache.clear()

    def test_cache_thread_detail(self):
        """Test caching thread detail."""
        thread = ThreadFactory.create(slug='test-thread')

        # Cache thread
        self.cache_service.cache_thread(thread.slug, thread)

        # Retrieve from cache
        cached_thread = self.cache_service.get_thread(thread.slug)

        self.assertIsNotNone(cached_thread)
        self.assertEqual(cached_thread['id'], str(thread.id))

    def test_invalidate_thread(self):
        """Test cache invalidation."""
        thread = ThreadFactory.create(slug='test-thread')
        self.cache_service.cache_thread(thread.slug, thread)

        # Invalidate cache
        self.cache_service.invalidate_thread(thread.slug)

        # Should return None
        cached_thread = self.cache_service.get_thread(thread.slug)
        self.assertIsNone(cached_thread)
```

### 9.2 Testing UUID Primary Keys

**Project Standard**: All forum models use UUID primary keys.

**Pattern: Use String Representation in Tests**
```python
class UUIDModelTests(TestCase):
    """Test UUID primary key handling."""

    def test_retrieve_post_by_uuid(self):
        """Test retrieving post by UUID string."""
        post = PostFactory.create()

        # API expects string representation of UUID
        response = self.client.get(f'/api/v1/forum/posts/{post.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(post.id))  # Compare as string

    def test_uuid_in_response(self):
        """Test that UUID is serialized as string."""
        post = PostFactory.create()

        response = self.client.get(f'/api/v1/forum/posts/{post.id}/')

        # Verify it's a string, not a UUID object
        self.assertIsInstance(response.data['id'], str)

        # Verify it's a valid UUID format
        import uuid
        uuid_obj = uuid.UUID(response.data['id'])
        self.assertEqual(str(uuid_obj), response.data['id'])
```

### 9.3 Testing Soft Deletes

**Project Pattern**: Forum models use `is_active` flag for soft deletion.

**Pattern: Test Soft Delete Behavior**
```python
class SoftDeleteTests(TestCase):
    """Test soft delete functionality."""

    def test_soft_delete_post(self):
        """Test that deleting a post sets is_active=False."""
        post = PostFactory.create(is_active=True)

        # Soft delete
        response = self.client.delete(f'/api/v1/forum/posts/{post.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Post still exists in database
        post.refresh_from_db()
        self.assertFalse(post.is_active)
        self.assertIsNotNone(post.deleted_at)

    def test_list_excludes_inactive_by_default(self):
        """Test that listing excludes soft-deleted posts."""
        active_post = PostFactory.create(is_active=True)
        deleted_post = PostFactory.create(is_active=False)

        response = self.client.get('/api/v1/forum/posts/')

        post_ids = [post['id'] for post in response.data['results']]
        self.assertIn(str(active_post.id), post_ids)
        self.assertNotIn(str(deleted_post.id), post_ids)
```

### 9.4 Testing File Uploads

**Project Pattern**: Forum posts support image attachments (max 6 per post).

**Pattern: Test File Upload Validation**
```python
from django.core.files.uploadedfile import SimpleUploadedFile

class AttachmentUploadTests(APITestCase):
    """Test image attachment uploads."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory.create()
        self.client.force_authenticate(user=self.user)

        self.post = PostFactory.create(author=self.user)

    def test_upload_valid_image(self):
        """Test uploading a valid image file."""
        # Create test image
        image = SimpleUploadedFile(
            name='test_image.jpg',
            content=b'fake image content',
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.post.id}/upload_image/',
            {'image': image},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)

    def test_upload_invalid_file_type(self):
        """Test that non-image files are rejected."""
        # Create test PDF
        pdf = SimpleUploadedFile(
            name='test.pdf',
            content=b'fake pdf content',
            content_type='application/pdf'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.post.id}/upload_image/',
            {'image': pdf},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_upload_exceeds_max_attachments(self):
        """Test that uploads are limited to 6 per post."""
        from apps.forum.constants import MAX_ATTACHMENTS_PER_POST

        # Create max attachments
        for i in range(MAX_ATTACHMENTS_PER_POST):
            AttachmentFactory.create(post=self.post)

        # Try to upload one more
        image = SimpleUploadedFile(
            name='extra.jpg',
            content=b'fake image',
            content_type='image/jpeg'
        )

        response = self.client.post(
            f'/api/v1/forum/posts/{self.post.id}/upload_image/',
            {'image': image},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Maximum', response.data['error'])
```

---

## Summary: Key Testing Principles

### 1. Use TestCase for Most Tests
- Faster than TransactionTestCase
- Sufficient for 95% of tests
- Use TransactionTestCase only when testing transaction behavior

### 2. Always Use Named Status Code Constants
```python
from rest_framework import status
self.assertEqual(response.status_code, status.HTTP_200_OK)
```

### 3. Clear Cache in setUp/tearDown
```python
from django.core.cache import cache
cache.clear()  # Required! Django doesn't auto-clear
```

### 4. Use Factories, Not Fixtures
```python
user = UserFactory.create(username='testuser')  # ✅ Fast, flexible
# fixtures.json  # ❌ Slow, brittle
```

### 5. Strict Query Count Assertions (Issue #117)
```python
self.assertEqual(query_count, 1)  # ✅ Catches regressions
self.assertLess(query_count, 10)  # ❌ Allows query creep
```

### 6. Use freezegun for Time Travel
```python
from freezegun import freeze_time

@freeze_time("2025-01-01 12:00:00")
def test_time_based_logic():
    # Time is frozen at Jan 1, 2025
    pass
```

### 7. Mock Signals with Context Managers
```python
@contextmanager
def catch_signal(signal):
    handler = mock.Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)
```

### 8. Test Both Success and Failure Cases
- Test authenticated and unauthenticated
- Test valid and invalid inputs
- Test permissions (owner, non-owner, moderator)
- Test edge cases (max limits, empty lists)

### 9. Use Descriptive Test Names
```python
def test_list_posts_requires_thread_parameter():  # ✅ Clear
def test_list():  # ❌ Unclear
```

### 10. Include Regression Protection Comments
```python
# Regression protection: Ensures conditional annotations are used (Issue #113).
# Any increase from 1 query indicates N+1 or missing optimization.
```

---

## Additional Resources

### Official Documentation
- **Django 5.2 Testing**: https://docs.djangoproject.com/en/5.2/topics/testing/
- **DRF Testing**: https://www.django-rest-framework.org/api-guide/testing/
- **DRF Status Codes**: https://www.django-rest-framework.org/api-guide/status-codes/

### Project Documentation
- **Performance Testing Patterns**: `/backend/PERFORMANCE_TESTING_PATTERNS_CODIFIED.md`
- **Security Patterns**: `/backend/SECURITY_PATTERNS_CODIFIED.md`
- **Forum Architecture**: `/backend/apps/forum/docs/`
- **Test Examples**: `/backend/apps/forum/tests/`

### Community Resources
- **Factory Boy**: https://factoryboy.readthedocs.io/
- **Freezegun**: https://github.com/spulec/freezegun
- **pytest-django**: https://pytest-django.readthedocs.io/

---

**End of Document**

*Last Updated: November 5, 2025*
*Maintained by: Development Team*
*Version: 1.0.0*
