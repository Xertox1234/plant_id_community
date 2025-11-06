# Django Testing Best Practices

**Research Date**: November 5, 2025
**Authority Level**: Compiled from official Django/DRF documentation, well-regarded style guides, and community best practices

This document synthesizes best practices for comprehensive Django and Django REST Framework testing, compiled from authoritative sources including official documentation, HackSoft Django Styleguide, and production-proven patterns.

---

## Table of Contents

1. [Test Organization](#test-organization)
2. [Django Testing Patterns](#django-testing-patterns)
3. [Django REST Framework Testing](#django-rest-framework-testing)
4. [Service Layer Testing](#service-layer-testing)
5. [Cache Testing Strategies](#cache-testing-strategies)
6. [Signal Testing Patterns](#signal-testing-patterns)
7. [Permission Testing](#permission-testing)
8. [Rate Limiting Testing](#rate-limiting-testing)
9. [Performance Testing](#performance-testing)
10. [Test Fixtures and Factories](#test-fixtures-and-factories)
11. [Best Practices Summary](#best-practices-summary)

---

## Test Organization

### File Structure

**Official Django Recommendation**:
> "As your test suite grows you'll likely want to restructure it into a tests package so you can split your tests into different submodules such as `test_models.py`, `test_views.py`, `test_forms.py`."

**Recommended Structure**:
```
my_app/
  tests/
    __init__.py
    test_models.py      # Model validation, properties, methods
    test_views.py       # View logic and HTTP responses
    test_api.py         # DRF endpoints and serializers
    test_services.py    # Business logic services
    test_permissions.py # Permission classes
    test_signals.py     # Signal emission and handlers
    test_cache.py       # Caching behavior
    conftest.py         # pytest fixtures (if using pytest)
```

### Naming Conventions

**PEP8 Standard** (widely adopted by Django community):

- **Test classes**: `{ModelName}Test` (e.g., `ArticleTest`, `PostTest`)
  - Django/SQLAlchemy both use "Name"Test(s) format
  - NOT `TestModelName` (less common)

- **Test methods**: `test_{what_is_being_tested}` (descriptive)
  - Good: `test_course_end_date_cannot_be_before_start_date`
  - Good: `test_create_account_with_valid_data`
  - Bad: `test_case_1`, `test_function`

- **Test files**: Must start with `test_` for Django discovery
  - `test_models.py`, `test_views.py`, `test_api.py`

### Test Discovery

Django automatically finds test files matching the pattern `test*.py` using unittest's built-in discovery mechanism.

---

## Django Testing Patterns

### Test Case Classes

**Official Django Documentation**: "If your tests rely on database access such as creating or querying models, be sure to create your test classes as subclasses of `django.test.TestCase` rather than `unittest.TestCase`."

**Available Test Cases**:

1. **`django.test.TestCase`** (most common)
   - Wraps each test in a database transaction
   - Rolls back after each test for isolation
   - Use for model/database-dependent tests

2. **`django.test.SimpleTestCase`**
   - No database access allowed
   - Use for logic tests without DB dependencies
   - Faster than TestCase

3. **`django.test.TransactionTestCase`**
   - Tests that need to test transaction behavior
   - Slower than TestCase (flushes DB)

4. **`django.test.LiveServerTestCase`**
   - Launches live server for Selenium/browser tests

### setUp/tearDown Patterns

**Pattern**: Use `setUp()` for test data creation, Django handles cleanup automatically via transactions.

```python
from django.test import TestCase
from .models import Animal

class AnimalTestCase(TestCase):
    """Tests for Animal model behavior."""

    def setUp(self):
        """Create test data before each test runs."""
        Animal.objects.create(name="lion", sound="roar")
        Animal.objects.create(name="cat", sound="meow")

    def test_animals_can_speak(self):
        """Animals that can speak are correctly identified."""
        lion = Animal.objects.get(name="lion")
        cat = Animal.objects.get(name="cat")
        self.assertEqual(lion.speak(), 'The lion says "roar"')
        self.assertEqual(cat.speak(), 'The cat says "meow"')
```

**setUpTestData() for Performance**:

> "setUpTestData runs once per test class, so use it for heavy, immutable data you can safely share across methods—this can dramatically cut suite runtime."

```python
class PostTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Create immutable test data shared across all test methods."""
        cls.user = User.objects.create_user(username='testuser')
        cls.category = Category.objects.create(name='Test Category')
        # Heavy data creation that doesn't change

    def test_post_creation(self):
        """Test uses shared data from setUpTestData."""
        post = Post.objects.create(
            author=self.user,
            category=self.category,
            title='Test Post'
        )
        self.assertTrue(post.pk)
```

### Model Testing

**HackSoft Django Styleguide**: "Models need to be tested only if there's something additional to them - like validation, properties or methods."

**What to Test**:
- Custom validation logic
- Calculated properties
- Custom methods (like `__str__`, business logic)
- Constraints and unique constraints
- Signals triggered by model actions

**What NOT to Test**:
- Basic field definitions (Django handles this)
- Default Django behavior (ORM, migrations)
- Framework functionality

**Example**:
```python
class ThreadModelTest(TestCase):
    def test_thread_slug_auto_generated_from_title(self):
        """Thread slug is automatically generated from title."""
        thread = Thread.objects.create(title="Test Thread")
        self.assertEqual(thread.slug, "test-thread")

    def test_thread_title_cannot_exceed_max_length(self):
        """Thread title validation rejects titles over 255 chars."""
        with self.assertRaises(ValidationError):
            thread = Thread(title="x" * 256)
            thread.full_clean()

    def test_soft_delete_preserves_record(self):
        """Soft delete sets deleted_at without removing from DB."""
        thread = Thread.objects.create(title="Test")
        thread.soft_delete()
        self.assertIsNotNone(thread.deleted_at)
        self.assertTrue(Thread.all_objects.filter(pk=thread.pk).exists())
```

---

## Django REST Framework Testing

### DRF Test Case Classes

**Official DRF Documentation**: REST framework supplies dedicated test case classes that automatically use `APIClient`:

- `APISimpleTestCase` - No database access
- `APITransactionTestCase` - Transaction testing
- `APITestCase` - Most common, database transactions
- `APILiveServerTestCase` - Live server testing

```python
from rest_framework.test import APITestCase
from rest_framework import status

class AccountTests(APITestCase):
    def test_create_account(self):
        """Verify account creation endpoint."""
        url = '/api/accounts/'
        data = {'name': 'testuser'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'testuser')
```

### API Client vs Request Factory

**APIClient** (recommended for most tests):
- Mimics Django's standard test client
- Runs full request-response cycle
- Supports DRF features (authentication, content negotiation)
- Tests middleware, URL routing, response rendering

```python
from rest_framework.test import APIClient

client = APIClient()
response = client.post('/notes/', {'title': 'new idea'}, format='json')
```

**APIRequestFactory** (for unit testing views directly):
- Creates individual test requests
- Does NOT run middleware or URL resolution
- Faster but less comprehensive
- Use for isolated view testing

```python
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()
request = factory.post('/notes/', {'title': 'new idea'}, format='json')
response = view(request)  # Call view directly
```

### Authentication Testing

**Three Authentication Strategies**:

1. **Session Authentication** (standard Django):
```python
client = APIClient()
client.login(username='testuser', password='password')
response = client.get('/api/protected/')
```

2. **Token/Header Authentication** (JWT, Token):
```python
client = APIClient()
client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
response = client.get('/api/protected/')
```

3. **Force Authentication** (bypass credentials):
```python
from rest_framework.test import force_authenticate

factory = APIRequestFactory()
user = User.objects.get(username='testuser')
request = factory.get('/api/protected/')
force_authenticate(request, user=user)
response = view(request)
```

### Testing ViewSets

**Pattern**: Use `as_view()` with actions dict to test specific actions.

```python
from rest_framework.test import APIRequestFactory
from .viewsets import PostViewSet

class PostViewSetTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser')

    def test_list_posts(self):
        """Test list action returns all posts."""
        view = PostViewSet.as_view({'get': 'list'})
        request = self.factory.get('/api/posts/')
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_retrieve_post(self):
        """Test retrieve action returns single post."""
        post = Post.objects.create(title='Test', author=self.user)
        view = PostViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get(f'/api/posts/{post.pk}/')
        force_authenticate(request, user=self.user)
        response = view(request, pk=post.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Test')

    def test_create_post_unauthenticated_returns_403(self):
        """Unauthenticated users cannot create posts."""
        view = PostViewSet.as_view({'post': 'create'})
        request = self.factory.post('/api/posts/', {'title': 'Test'})
        response = view(request)
        self.assertEqual(response.status_code, 403)
```

### Testing Custom Actions

```python
def test_custom_action_upload_image(self):
    """Test custom @action for image upload."""
    view = PostViewSet.as_view({'post': 'upload_image'})
    post = Post.objects.create(title='Test', author=self.user)

    # Create test image file
    image = SimpleUploadedFile(
        "test.jpg",
        b"file_content",
        content_type="image/jpeg"
    )

    request = self.factory.post(
        f'/api/posts/{post.pk}/upload_image/',
        {'image': image},
        format='multipart'
    )
    force_authenticate(request, user=self.user)
    response = view(request, pk=post.pk)
    self.assertEqual(response.status_code, 201)
```

---

## Service Layer Testing

**HackSoft Django Styleguide**: "Services warrant comprehensive testing since they encapsulate business logic. Test both success and failure scenarios, including validation errors."

### Service Testing Pattern

```python
from django.test import TestCase
from .services import PostService
from .models import Post, User

class PostServiceTest(TestCase):
    """Tests for PostService business logic."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser')
        self.service = PostService()

    def test_create_post_success(self):
        """Service creates post with valid data."""
        data = {
            'title': 'Test Post',
            'content': 'Test content',
            'author': self.user
        }
        post = self.service.create_post(**data)
        self.assertIsNotNone(post.pk)
        self.assertEqual(post.title, 'Test Post')

    def test_create_post_invalid_data_raises_validation_error(self):
        """Service raises ValidationError for invalid data."""
        data = {
            'title': '',  # Empty title should fail
            'content': 'Test content',
            'author': self.user
        }
        with self.assertRaises(ValidationError):
            self.service.create_post(**data)

    def test_delete_post_soft_deletes(self):
        """Service soft deletes post instead of hard delete."""
        post = Post.objects.create(title='Test', author=self.user)
        self.service.delete_post(post.pk)
        post.refresh_from_db()
        self.assertIsNotNone(post.deleted_at)

    @patch('apps.forum.services.external_api_client')
    def test_external_api_call_handles_timeout(self, mock_client):
        """Service handles external API timeouts gracefully."""
        mock_client.get.side_effect = Timeout()
        result = self.service.fetch_data_from_api()
        self.assertIsNone(result)  # Should return None on timeout
```

### Mocking External Services

**Pattern**: Mock external APIs and services to isolate business logic.

```python
from unittest.mock import patch, Mock
from django.test import TestCase
from .services import PlantIdentificationService

class PlantIdentificationServiceTest(TestCase):
    @patch('apps.plant_identification.services.plant_id_client')
    def test_identify_plant_success(self, mock_client):
        """Service correctly processes Plant.id API response."""
        # Mock API response
        mock_response = {
            'suggestions': [{
                'plant_name': 'Rose',
                'probability': 0.95
            }]
        }
        mock_client.identify.return_value = mock_response

        service = PlantIdentificationService()
        result = service.identify_plant(image_file=Mock())

        self.assertEqual(result['plant_name'], 'Rose')
        self.assertEqual(result['probability'], 0.95)

    @patch('apps.plant_identification.services.plant_id_client')
    def test_identify_plant_api_failure_returns_none(self, mock_client):
        """Service returns None when API fails."""
        mock_client.identify.side_effect = Exception("API Error")

        service = PlantIdentificationService()
        result = service.identify_plant(image_file=Mock())

        self.assertIsNone(result)
```

---

## Cache Testing Strategies

### Testing Cache Behavior

**Sources**: Django-redis test suite, Stack Overflow community patterns

**Key Approaches**:

1. **Use FakeRedis for Unit Tests** (recommended)
2. **Use DummyCache to Disable Caching**
3. **Use Real Redis with Separate Test Database**

### Pattern 1: FakeRedis (Recommended)

```python
# settings_test.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'REDIS_CLIENT_CLASS': 'fakeredis.FakeStrictRedis',  # Use FakeRedis
        }
    }
}
```

```python
from django.core.cache import cache
from django.test import TestCase
from .services import BlogCacheService

class BlogCacheServiceTest(TestCase):
    def setUp(self):
        cache.clear()  # Clear cache before each test

    def test_cache_hit_returns_cached_data(self):
        """Service returns cached data on cache hit."""
        cache.set('blog:post:1', {'title': 'Cached Post'}, timeout=300)

        service = BlogCacheService()
        result = service.get_post(post_id=1)

        self.assertEqual(result['title'], 'Cached Post')

    def test_cache_miss_fetches_from_db(self):
        """Service fetches from DB on cache miss and caches result."""
        post = Post.objects.create(title='New Post')

        service = BlogCacheService()
        result = service.get_post(post_id=post.pk)

        # Verify fetched from DB
        self.assertEqual(result['title'], 'New Post')

        # Verify cached for next request
        cached = cache.get(f'blog:post:{post.pk}')
        self.assertIsNotNone(cached)

    def test_cache_invalidation_on_update(self):
        """Cache is invalidated when post is updated."""
        post = Post.objects.create(title='Original')
        cache_key = f'blog:post:{post.pk}'
        cache.set(cache_key, {'title': 'Original'}, timeout=300)

        service = BlogCacheService()
        service.update_post(post.pk, title='Updated')

        # Cache should be invalidated
        cached = cache.get(cache_key)
        self.assertIsNone(cached)
```

### Pattern 2: DummyCache (Disable Caching)

```python
# settings_test.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
```

Use when you want to test logic without caching interference.

### Testing Cache Hit Rates

```python
from django.test import TestCase
from django.core.cache import cache
from django.test.utils import override_settings

class CachePerformanceTest(TestCase):
    def test_cache_hit_rate_measurement(self):
        """Measure cache hit rate for blog posts."""
        posts = [Post.objects.create(title=f'Post {i}') for i in range(10)]
        service = BlogCacheService()

        # First pass - all cache misses
        hits = 0
        misses = 0
        for post in posts:
            if cache.get(f'blog:post:{post.pk}'):
                hits += 1
            else:
                service.get_post(post.pk)  # Fetches and caches
                misses += 1

        self.assertEqual(misses, 10)

        # Second pass - all cache hits
        cache.clear()
        for post in posts:
            service.get_post(post.pk)  # Populate cache

        hits = 0
        for post in posts:
            if cache.get(f'blog:post:{post.pk}'):
                hits += 1

        self.assertEqual(hits, 10)
        hit_rate = (hits / len(posts)) * 100
        self.assertGreaterEqual(hit_rate, 90)  # 90% hit rate
```

---

## Signal Testing Patterns

**Authority**: Haki Benita - "How to Test Django Signals Like a Pro"

### Recommended Pattern: Context Manager with Mock

```python
from contextlib import contextmanager
from unittest import mock
from django.test import TestCase
from django.db.models.signals import post_save
from .models import Order
from .signals import order_created

@contextmanager
def catch_signal(signal):
    """Context manager to capture signal emissions."""
    handler = mock.Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)

class OrderSignalTest(TestCase):
    """Tests for Order-related signals."""

    def test_order_created_signal_emitted_on_save(self):
        """order_created signal emits when new order is saved."""
        with catch_signal(order_created) as handler:
            order = Order.objects.create(
                customer='John Doe',
                total=100.00
            )

            handler.assert_called_once_with(
                sender=Order,
                instance=order,
                created=True,
                signal=order_created
            )

    def test_order_created_signal_not_emitted_on_update(self):
        """order_created signal does not emit on updates."""
        order = Order.objects.create(customer='John Doe', total=100.00)

        with catch_signal(order_created) as handler:
            order.total = 150.00
            order.save()

            handler.assert_not_called()

    def test_signal_handler_executes_correctly(self):
        """Signal handler performs expected actions."""
        with catch_signal(post_save) as handler:
            order = Order.objects.create(customer='John Doe', total=100.00)

            # Verify handler was called
            handler.assert_called_once()

            # Verify handler received correct arguments
            args, kwargs = handler.call_args
            self.assertEqual(kwargs['sender'], Order)
            self.assertEqual(kwargs['instance'], order)
            self.assertTrue(kwargs['created'])
```

### Testing Signal Handlers Directly

```python
from django.test import TestCase
from .models import Order
from .signals import send_order_confirmation_email

class OrderSignalHandlerTest(TestCase):
    """Tests for order signal handlers."""

    @patch('apps.orders.signals.send_email')
    def test_send_order_confirmation_email(self, mock_send_email):
        """Handler sends confirmation email with correct data."""
        order = Order.objects.create(
            customer='John Doe',
            email='john@example.com',
            total=100.00
        )

        # Call handler directly
        send_order_confirmation_email(
            sender=Order,
            instance=order,
            created=True
        )

        # Verify email was sent
        mock_send_email.assert_called_once_with(
            to='john@example.com',
            subject='Order Confirmation',
            body__contains='Order #'
        )

    @patch('apps.orders.signals.send_email')
    def test_handler_skips_email_on_update(self, mock_send_email):
        """Handler does not send email on order updates."""
        order = Order.objects.create(customer='John Doe', total=100.00)

        # Call handler with created=False (update)
        send_order_confirmation_email(
            sender=Order,
            instance=order,
            created=False
        )

        # No email should be sent
        mock_send_email.assert_not_called()
```

---

## Permission Testing

### Testing DRF Permission Classes

**Official DRF Documentation**: "Testing a permission is as easy as instantiating the permission and testing its `has_permission` method with contrived objects."

```python
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from .permissions import IsAuthorOrReadOnly
from .models import Post, User

class IsAuthorOrReadOnlyTest(TestCase):
    """Tests for IsAuthorOrReadOnly permission class."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsAuthorOrReadOnly()
        self.author = User.objects.create_user(username='author')
        self.other_user = User.objects.create_user(username='other')

    def test_read_permission_granted_to_all_users(self):
        """Any user can read (GET) objects."""
        request = self.factory.get('/api/posts/1/')
        request.user = self.other_user

        self.assertTrue(
            self.permission.has_permission(request, view=None)
        )

    def test_write_permission_requires_authentication(self):
        """Unauthenticated users cannot write."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.post('/api/posts/')
        request.user = AnonymousUser()

        self.assertFalse(
            self.permission.has_permission(request, view=None)
        )

    def test_author_can_edit_own_post(self):
        """Authors can edit their own posts."""
        post = Post.objects.create(title='Test', author=self.author)

        request = self.factory.put(f'/api/posts/{post.pk}/')
        request.user = self.author

        self.assertTrue(
            self.permission.has_object_permission(request, view=None, obj=post)
        )

    def test_non_author_cannot_edit_post(self):
        """Non-authors cannot edit posts."""
        post = Post.objects.create(title='Test', author=self.author)

        request = self.factory.put(f'/api/posts/{post.pk}/')
        request.user = self.other_user

        self.assertFalse(
            self.permission.has_object_permission(request, view=None, obj=post)
        )
```

### Testing ViewSet Permissions Integration

```python
from rest_framework.test import APITestCase
from rest_framework import status

class PostViewSetPermissionTest(APITestCase):
    """Integration tests for PostViewSet permissions."""

    def setUp(self):
        self.author = User.objects.create_user(
            username='author',
            password='password'
        )
        self.other_user = User.objects.create_user(
            username='other',
            password='password'
        )

    def test_unauthenticated_user_can_list_posts(self):
        """Anonymous users can view post list."""
        response = self.client.get('/api/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_user_cannot_create_post(self):
        """Anonymous users cannot create posts."""
        response = self.client.post('/api/posts/', {'title': 'Test'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_create_post(self):
        """Authenticated users can create posts."""
        self.client.login(username='author', password='password')
        response = self.client.post('/api/posts/', {
            'title': 'Test Post',
            'content': 'Test content'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_author_can_delete_own_post(self):
        """Authors can delete their own posts."""
        post = Post.objects.create(title='Test', author=self.author)
        self.client.login(username='author', password='password')

        response = self.client.delete(f'/api/posts/{post.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_non_author_cannot_delete_post(self):
        """Non-authors cannot delete others' posts."""
        post = Post.objects.create(title='Test', author=self.author)
        self.client.login(username='other', password='password')

        response = self.client.delete(f'/api/posts/{post.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
```

---

## Rate Limiting Testing

### Testing DRF Throttling

**Official DRF Documentation**: When rate limits are exceeded, clients receive a 429 Too Many Requests response with a `Retry-After` header.

```python
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class PostThrottlingTest(APITestCase):
    """Tests for post creation rate limiting."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='password'
        )
        self.client.login(username='testuser', password='password')

    def test_rate_limit_enforced_after_threshold(self):
        """Users receive 429 after exceeding rate limit."""
        # Assuming rate limit is 5 posts per minute
        for i in range(5):
            response = self.client.post('/api/posts/', {
                'title': f'Post {i}',
                'content': 'Test content'
            })
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 6th request should be throttled
        response = self.client.post('/api/posts/', {
            'title': 'Post 6',
            'content': 'Test content'
        })
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', response)

    def test_rate_limit_message_includes_retry_time(self):
        """429 response includes time until rate limit resets."""
        # Exceed rate limit
        for i in range(6):
            self.client.post('/api/posts/', {
                'title': f'Post {i}',
                'content': 'Test'
            })

        response = self.client.post('/api/posts/', {'title': 'Test'})

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('detail', response.data)
        self.assertIn('second', response.data['detail'].lower())
```

### Disabling Throttling for Tests

**Community Best Practice**: Use DummyCache or remove throttle rates in test settings.

```python
# settings_test.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# OR

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {}  # Remove all throttling
}
```

### Testing Trust Level Rate Limits (Custom Implementation)

```python
from django.test import TestCase
from .services import TrustLevelService
from .models import UserProfile, Post

class TrustLevelRateLimitTest(TestCase):
    """Tests for trust-level-based rate limiting."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser')
        self.profile = UserProfile.objects.create(
            user=self.user,
            trust_level=0  # NEW user
        )

    def test_new_user_daily_post_limit(self):
        """NEW trust level users limited to 10 posts per day."""
        # Create 10 posts (should succeed)
        for i in range(10):
            can_post = TrustLevelService.check_daily_limit(
                self.user,
                'posts'
            )
            self.assertTrue(can_post)
            Post.objects.create(author=self.user, title=f'Post {i}')

        # 11th post should fail
        can_post = TrustLevelService.check_daily_limit(self.user, 'posts')
        self.assertFalse(can_post)

    def test_trusted_user_higher_limits(self):
        """TRUSTED users have higher rate limits."""
        self.profile.trust_level = 2  # TRUSTED
        self.profile.save()

        # Create 50 posts (NEW limit is 10, TRUSTED is 100)
        for i in range(50):
            can_post = TrustLevelService.check_daily_limit(self.user, 'posts')
            self.assertTrue(can_post)
            Post.objects.create(author=self.user, title=f'Post {i}')
```

---

## Performance Testing

### N+1 Query Detection with assertNumQueries

**Authority**: Django Official Documentation + Valentino Gagliardi

**Official Pattern**:

```python
from django.test import TestCase
from django.db import connection
from django.test.utils import override_settings

class PostListPerformanceTest(TestCase):
    """Performance tests for post listing."""

    def setUp(self):
        # Create test data
        user = User.objects.create_user(username='testuser')
        for i in range(10):
            Post.objects.create(
                title=f'Post {i}',
                author=user
            )

    def test_post_list_query_count(self):
        """Post list endpoint uses optimal query count."""
        # Should use select_related('author') to avoid N+1
        with self.assertNumQueries(1):  # 1 query with JOIN
            posts = list(Post.objects.select_related('author').all())
            # Access related data (should not trigger additional queries)
            for post in posts:
                _ = post.author.username

    def test_post_list_without_optimization_n_plus_1(self):
        """Demonstrates N+1 problem without select_related."""
        # This will trigger 1 query for posts + 10 queries for authors
        with self.assertNumQueries(11):  # N+1 problem!
            posts = list(Post.objects.all())
            for post in posts:
                _ = post.author.username

    def test_post_list_with_prefetch_related(self):
        """Use prefetch_related for reverse foreign keys."""
        category = Category.objects.create(name='Test')
        for i in range(5):
            Post.objects.create(title=f'Post {i}', category=category)

        # Without prefetch: 1 + N queries
        # With prefetch: 2 queries (categories + posts)
        with self.assertNumQueries(2):
            categories = list(
                Category.objects.prefetch_related('posts').all()
            )
            for cat in categories:
                _ = list(cat.posts.all())
```

### Query Count Best Practices

**Issue #117 Pattern - Strict Equality**:

> "Use strict equality for known query counts: `assertEqual(query_count, 1)` not `assertLess(query_count, 10)`"

```python
def test_retrieve_post_performance(self):
    """
    Retrieve single post should execute exactly 1 query.

    Query breakdown:
    1. SELECT post with related author (select_related)

    Issue #117: Use strict equality to catch regressions.
    """
    post = Post.objects.create(title='Test', author=self.user)

    with self.assertNumQueries(1) as context:
        retrieved = Post.objects.select_related('author').get(pk=post.pk)
        _ = retrieved.author.username

    # Strict assertion - any increase indicates regression
    self.assertEqual(
        len(context.captured_queries),
        1,
        msg="Query count regression detected. Expected exactly 1 query. "
            "See Issue #117 for investigation procedure."
    )
```

### Testing Response Times

```python
import time
from django.test import TestCase

class ResponseTimeTest(TestCase):
    def test_cached_response_under_50ms(self):
        """Cached responses return in under 50ms."""
        # Populate cache
        cache.set('blog:post:1', {'title': 'Test'}, timeout=300)

        start = time.time()
        result = BlogCacheService().get_post(post_id=1)
        duration = (time.time() - start) * 1000  # Convert to ms

        self.assertLess(duration, 50, "Cached response too slow")

    def test_parallel_api_call_performance(self):
        """Parallel API calls complete within timeout."""
        service = PlantIdentificationService()

        start = time.time()
        result = service.identify_parallel(image_file=mock_image)
        duration = time.time() - start

        self.assertLess(duration, 10.0, "Parallel call exceeded 10s timeout")
```

### Using nplusone Package

```python
# settings_test.py
INSTALLED_APPS += ['nplusone.ext.django']

MIDDLEWARE += ['nplusone.ext.django.NPlusOneMiddleware']

NPLUSONE_RAISE = True  # Raise exception on N+1 detection

# In tests
from django.test.utils import override_settings

class PostListTest(TestCase):
    @override_settings(NPLUSONE_RAISE=True)
    def test_post_list_no_n_plus_1_queries(self):
        """Post list view has no N+1 queries."""
        response = self.client.get('/api/posts/')
        # Will raise NPlusOneError if N+1 detected
        self.assertEqual(response.status_code, 200)
```

---

## Test Fixtures and Factories

### Django Fixtures (Not Recommended)

**Community Consensus**: "Django fixtures are slow and hard to maintain… avoid them!"

**Why Avoid**:
- Hard to maintain as schemas change
- Slow to load (especially JSON fixtures)
- Brittle (break easily with migrations)
- Difficult to share across test files

### Factory Pattern (Recommended)

**Authority**: pytest-django, HackSoft Django Styleguide, Real Python

**Use factory_boy + pytest-django**:

```bash
pip install factory-boy pytest-django
```

**Define Factories**:

```python
# tests/factories.py
import factory
from factory.django import DjangoModelFactory
from apps.forum.models import Post, User, Category

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')

class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f'Category {n}')
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))

class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post

    title = factory.Faker('sentence', nb_words=5)
    content = factory.Faker('paragraph', nb_sentences=3)
    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    published = True
```

**Use in Tests**:

```python
from .factories import PostFactory, UserFactory

class PostTest(TestCase):
    def test_post_creation(self):
        """Factory creates valid post."""
        post = PostFactory()
        self.assertTrue(post.pk)
        self.assertIsNotNone(post.author)

    def test_create_multiple_posts(self):
        """Factory creates multiple posts easily."""
        posts = PostFactory.create_batch(10)
        self.assertEqual(len(posts), 10)

    def test_override_factory_attributes(self):
        """Factory attributes can be overridden."""
        user = UserFactory(username='customuser')
        post = PostFactory(
            title='Custom Title',
            author=user
        )
        self.assertEqual(post.title, 'Custom Title')
        self.assertEqual(post.author.username, 'customuser')
```

### pytest Fixtures (for pytest users)

```python
# conftest.py
import pytest
from .factories import UserFactory, PostFactory

@pytest.fixture
def user():
    """Create a test user."""
    return UserFactory()

@pytest.fixture
def post(user):
    """Create a test post with user as author."""
    return PostFactory(author=user)

@pytest.fixture
def posts(user):
    """Create multiple test posts."""
    return PostFactory.create_batch(10, author=user)

# In tests
def test_post_creation(post):
    """Test uses fixture-provided post."""
    assert post.pk is not None
    assert post.author is not None

def test_multiple_posts(posts):
    """Test uses fixture-provided list of posts."""
    assert len(posts) == 10
```

### Factory as Fixture Pattern

**Real Python Best Practice**: "Instead of returning data directly, the fixture instead returns a function which generates the data."

```python
# conftest.py
@pytest.fixture
def make_post(db):
    """Factory fixture that returns a function."""
    def _make_post(**kwargs):
        return PostFactory(**kwargs)
    return _make_post

# In tests
def test_create_multiple_posts_in_test(make_post):
    """Use factory fixture multiple times in single test."""
    post1 = make_post(title='First Post')
    post2 = make_post(title='Second Post')

    assert Post.objects.count() == 2
    assert post1.title == 'First Post'
    assert post2.title == 'Second Post'
```

---

## Best Practices Summary

### Must Have (Critical)

1. **Test Organization**: Split tests into logical files (`test_models.py`, `test_api.py`, etc.)
2. **Test Independence**: Each test runs in isolation, no inter-test dependencies
3. **Use TestCase for DB Tests**: Subclass `django.test.TestCase` for database access
4. **setUpTestData for Performance**: Use for shared, immutable test data
5. **assertNumQueries**: Test query counts to prevent N+1 problems
6. **Mock External APIs**: Never call real external services in tests
7. **Test Permissions**: Both authentication and object-level permissions
8. **Test Rate Limiting**: Verify 429 responses when limits exceeded
9. **Use Factories**: factory_boy > Django fixtures for test data
10. **Descriptive Test Names**: `test_{what_is_being_tested}` pattern

### Recommended (Best Practice)

1. **DRF Test Classes**: Use `APITestCase`, `APIClient` for DRF testing
2. **Signal Testing**: Use context manager pattern for signal testing
3. **Cache Testing**: Use FakeRedis or DummyCache for cache testing
4. **Performance Baselines**: Document expected query counts in docstrings
5. **Test Both Success and Failure**: Test validation errors, edge cases
6. **Force Authenticate**: Use `force_authenticate()` for isolated view tests
7. **Test Fixtures**: pytest fixtures > Django fixtures for reusability
8. **Parallel Testing**: Use `--parallel` flag for faster test runs
9. **Coverage Measurement**: Track test coverage with coverage.py
10. **Test Custom Actions**: Test all custom ViewSet actions

### Optional (Advanced)

1. **pytest-django**: Consider pytest for more concise test syntax
2. **nplusone Package**: Automatic N+1 detection in tests
3. **pytest-xdist**: Parallel test execution with pytest
4. **pytest-randomly**: Randomize test order to expose dependencies
5. **Response Time Testing**: Add performance assertions for critical paths
6. **Live Server Tests**: Use `LiveServerTestCase` for Selenium tests
7. **Test Serializers**: Unit test serializer validation separately
8. **Test Selectors**: Test query logic in isolation from views
9. **Test Signals Handlers**: Test handler logic directly
10. **Cache Hit Rate Testing**: Measure and assert cache effectiveness

---

## Authoritative Sources

### Official Documentation

1. **Django Testing Documentation**: https://docs.djangoproject.com/en/5.2/topics/testing/
   - Writing and running tests
   - Test case classes
   - Test database
   - Advanced topics

2. **Django REST Framework Testing**: https://www.django-rest-framework.org/api-guide/testing/
   - APIClient and APIRequestFactory
   - Authentication in tests
   - Test case classes

3. **Django Coding Style**: https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/
   - Official Django conventions

### Well-Regarded Guides

4. **HackSoft Django Styleguide**: https://github.com/HackSoftware/Django-Styleguide
   - Service layer testing
   - Test organization
   - Production-proven patterns

5. **Haki Benita - Signal Testing**: https://hakibenita.com/how-to-test-django-signals-like-a-pro
   - Context manager pattern
   - Signal isolation strategies

6. **Valentino Gagliardi - N+1 Detection**: https://www.valentinog.com/blog/n-plus-one/
   - assertNumQueries usage
   - Performance testing patterns

7. **Real Python - Django Fixtures**: https://realpython.com/django-pytest-fixtures/
   - Factory patterns
   - pytest fixtures

8. **Pytest Django Documentation**: https://pytest-django.readthedocs.io/
   - pytest integration
   - Fixture patterns

### Testing Tools

9. **factory_boy**: https://factoryboy.readthedocs.io/
   - Test data generation
   - Faker integration

10. **pytest-django**: https://pytest-django.readthedocs.io/
    - pytest + Django integration

11. **django-redis**: https://github.com/jazzband/django-redis
    - Redis cache backend (includes test examples)

12. **fakeredis**: https://pypi.org/project/fakeredis/
    - In-memory Redis for testing

13. **nplusone**: https://github.com/jmcarp/nplusone
    - Automatic N+1 detection

---

## Conclusion

This guide synthesizes best practices from official Django and DRF documentation, well-regarded community style guides, and production-proven patterns. Key takeaways:

- **Organize tests logically** by file and class structure
- **Test services, not just views** - isolate business logic
- **Use factories, not fixtures** for maintainable test data
- **Mock external dependencies** to keep tests fast and reliable
- **Test performance proactively** with assertNumQueries
- **Verify permissions comprehensively** at multiple levels
- **Leverage DRF test utilities** for API testing
- **Test signals in isolation** with context manager pattern

Following these patterns will lead to comprehensive, maintainable, and fast test suites that catch regressions early and document expected behavior.
