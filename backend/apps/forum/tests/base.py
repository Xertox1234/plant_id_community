"""
Base test cases for forum app.

Provides common setup and utilities for all forum tests.
"""

from django.test import TestCase, TransactionTestCase
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from typing import Optional

from .factories import UserFactory, CategoryFactory, ThreadFactory, PostFactory
from .fixtures import ForumTestFixtures


class ForumTestCase(TestCase):
    """
    Base test case for forum model and service tests.

    Provides:
    - Cache clearing
    - Common fixtures
    - Helper methods for assertions
    """

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures (runs once)."""
        super().setUpClass()

    def setUp(self):
        """Set up test environment before each test."""
        # Clear cache to ensure clean state
        cache.clear()

        # Create common test data
        self.user = UserFactory.create(username='testuser')
        self.category = CategoryFactory.create(name='General Discussion')
        self.thread = ThreadFactory.create(
            title='Test Thread',
            author=self.user,
            category=self.category
        )
        self.post = PostFactory.create(
            thread=self.thread,
            author=self.user,
            is_first_post=True
        )

    def tearDown(self):
        """Clean up after each test."""
        # Clear cache after test
        cache.clear()

    # Helper methods for common assertions

    def assertCacheHit(self, cache_key: str, msg: Optional[str] = None):
        """Assert that a cache key exists."""
        cached = cache.get(cache_key)
        self.assertIsNotNone(cached, msg or f"Expected cache hit for key: {cache_key}")
        return cached

    def assertCacheMiss(self, cache_key: str, msg: Optional[str] = None):
        """Assert that a cache key does not exist."""
        cached = cache.get(cache_key)
        self.assertIsNone(cached, msg or f"Expected cache miss for key: {cache_key}")

    def assertValidSlug(self, obj, msg: Optional[str] = None):
        """Assert that an object has a valid slug."""
        self.assertTrue(hasattr(obj, 'slug'), msg or "Object must have slug attribute")
        self.assertIsNotNone(obj.slug, msg or "Slug must not be None")
        self.assertGreater(len(obj.slug), 0, msg or "Slug must not be empty")
        # Slug should be lowercase alphanumeric with hyphens
        self.assertRegex(
            obj.slug,
            r'^[a-z0-9-]+$',
            msg or "Slug must be lowercase alphanumeric with hyphens"
        )

    def assertValidUUID(self, uuid_value, msg: Optional[str] = None):
        """Assert that a value is a valid UUID."""
        import uuid
        try:
            uuid.UUID(str(uuid_value))
        except (ValueError, AttributeError):
            self.fail(msg or f"Invalid UUID: {uuid_value}")

    def assertQueryCountLessThan(self, max_queries: int):
        """
        Context manager to assert query count is less than max.

        Usage:
            with self.assertQueryCountLessThan(10):
                # Your code here
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        class QueryCountAssertion:
            def __init__(self, test_case, max_queries):
                self.test_case = test_case
                self.max_queries = max_queries
                self.context = None

            def __enter__(self):
                self.context = CaptureQueriesContext(connection)
                self.context.__enter__()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.context.__exit__(exc_type, exc_val, exc_tb)
                if exc_type is None:
                    query_count = len(self.context.captured_queries)
                    self.test_case.assertLessEqual(
                        query_count,
                        self.max_queries,
                        f"Query count {query_count} exceeds maximum {self.max_queries}\n"
                        f"Queries:\n" + "\n".join(
                            f"{i+1}. {q['sql']}" for i, q in enumerate(self.context.captured_queries)
                        )
                    )

        return QueryCountAssertion(self, max_queries)


class ForumAPITestCase(APITestCase):
    """
    Base test case for forum API tests.

    Provides:
    - API client setup
    - Authentication helpers
    - Common API assertions
    """

    def setUp(self):
        """Set up test environment before each test."""
        # Clear cache
        cache.clear()

        # Create API client
        self.client = APIClient()

        # Create common test data
        self.user = UserFactory.create(username='apiuser', password='testpass')
        self.admin_user = UserFactory.create(
            username='admin',
            password='admin123',
            is_staff=True
        )

        self.category = CategoryFactory.create(name='API Test Category')
        self.thread = ThreadFactory.create(
            title='API Test Thread',
            author=self.user,
            category=self.category
        )
        self.post = PostFactory.create(
            thread=self.thread,
            author=self.user,
            is_first_post=True
        )

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    # Authentication helpers

    def authenticate(self, user=None):
        """
        Authenticate API client with user credentials.

        Args:
            user: User to authenticate (uses self.user if not provided)
        """
        if user is None:
            user = self.user
        self.client.force_authenticate(user=user)

    def unauthenticate(self):
        """Remove authentication from API client."""
        self.client.force_authenticate(user=None)

    def authenticate_as_admin(self):
        """Authenticate as admin user."""
        self.authenticate(user=self.admin_user)

    # API assertion helpers

    def assertAPISuccess(self, response, status_code=200):
        """Assert API response is successful."""
        self.assertEqual(
            response.status_code,
            status_code,
            f"Expected status {status_code}, got {response.status_code}. "
            f"Response: {response.data if hasattr(response, 'data') else response.content}"
        )

    def assertAPIError(self, response, status_code=400):
        """Assert API response is an error."""
        self.assertEqual(
            response.status_code,
            status_code,
            f"Expected error status {status_code}, got {response.status_code}"
        )

    def assertRequiresAuthentication(self, url, method='get', data=None):
        """
        Assert that an endpoint requires authentication.

        Args:
            url: API endpoint URL
            method: HTTP method (get, post, put, patch, delete)
            data: Optional request data for POST/PUT/PATCH
        """
        # Ensure not authenticated
        self.unauthenticate()

        # Make request
        http_method = getattr(self.client, method.lower())
        if data and method.lower() in ['post', 'put', 'patch']:
            response = http_method(url, data)
        else:
            response = http_method(url)

        # Should return 401 or 403
        self.assertIn(
            response.status_code,
            [401, 403],
            f"Expected 401/403 for unauthenticated request, got {response.status_code}"
        )

    def assertAPIResponseHasFields(self, response, fields):
        """
        Assert API response contains expected fields.

        Args:
            response: API response
            fields: List of expected field names
        """
        self.assertAPISuccess(response)
        for field in fields:
            self.assertIn(
                field,
                response.data,
                f"Expected field '{field}' in response"
            )

    def assertPaginatedResponse(self, response, min_count=0):
        """
        Assert response is paginated with expected structure.

        Args:
            response: API response
            min_count: Minimum number of results expected
        """
        self.assertAPISuccess(response)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)

        if min_count > 0:
            self.assertGreaterEqual(
                len(response.data['results']),
                min_count,
                f"Expected at least {min_count} results"
            )


class ForumTransactionTestCase(TransactionTestCase):
    """
    Base test case for tests requiring transaction control.

    Use this for:
    - Testing database constraints
    - Testing transaction rollback
    - Testing concurrent access patterns
    """

    def setUp(self):
        """Set up test environment."""
        cache.clear()
        self.user = UserFactory.create()
        self.category = CategoryFactory.create()

    def tearDown(self):
        """Clean up after test."""
        cache.clear()
