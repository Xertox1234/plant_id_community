"""
Unit tests for AIRateLimiter.

Tests rate limiting behavior, quota enforcement, and decorator functionality
to ensure cost protection and fair usage.
"""

from apps.blog.services.ai_rate_limiter import AIRateLimiter, ai_rate_limit
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

User = get_user_model()


class AIRateLimiterTestCase(TestCase):
    """Test suite for AI rate limiting."""

    def setUp(self):
        """Clear cache and create test user before each test."""
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def test_user_within_limit_allows_call(self):
        """Test that user within limit is allowed to make AI calls."""
        result = AIRateLimiter.check_user_limit(self.user.id, has_premium=False)

        self.assertTrue(result)

    def test_user_exceeds_limit_blocks_call(self):
        """Test that user exceeding limit is blocked."""
        # Make USER_LIMIT calls (default: 10)
        for _ in range(AIRateLimiter.USER_LIMIT):
            result = AIRateLimiter.check_user_limit(self.user.id, has_premium=False)
            self.assertTrue(result)

        # Next call should be blocked
        result = AIRateLimiter.check_user_limit(self.user.id, has_premium=False)
        self.assertFalse(result)

    def test_premium_user_has_elevated_limit(self):
        """Test that premium entitlement grants an elevated rate limit."""
        # Premium limit is 50, regular is 10
        self.assertEqual(AIRateLimiter.PREMIUM_LIMIT, 50)
        self.assertEqual(AIRateLimiter.USER_LIMIT, 10)

        # A non-staff premium user, resolved through the real entitlement helper
        # (isolates the premium path from the staff path).
        premium_user = User.objects.create_user(username="premiumuser", is_premium=True)
        self.assertFalse(premium_user.is_staff)
        has_premium = premium_user.has_premium_access()

        # Should be able to make more than the free limit.
        for _ in range(AIRateLimiter.USER_LIMIT + 1):
            result = AIRateLimiter.check_user_limit(premium_user.id, has_premium)
            self.assertTrue(result)  # Still within premium limit

    def test_staff_user_gets_premium_limit_through_decorator(self):
        """Regression guard: a non-premium staff user still gets PREMIUM_LIMIT.

        The rate limiter no longer branches on ``is_staff`` directly — the
        decorator computes ``user.has_premium_access()``, which grants staff
        premium-equivalent access implicitly. Without this, migrating off the
        is_staff proxy would silently drop staff from 50 to 10 calls/hour on
        the staff-only AI endpoints.
        """
        factory = RequestFactory()

        @ai_rate_limit
        def test_view(request):
            return HttpResponse("Success")

        # Staff, but explicitly NOT premium.
        self.assertFalse(self.staff_user.is_premium)
        request = factory.get("/")
        request.user = self.staff_user

        # More than USER_LIMIT (10) but within PREMIUM_LIMIT (50) — all allowed.
        for _ in range(AIRateLimiter.USER_LIMIT + 1):
            response = test_view(request)
            self.assertEqual(response.status_code, 200)

    def test_global_limit_enforcement(self):
        """Test that global rate limit is enforced."""
        # Make GLOBAL_LIMIT calls (default: 100)
        for _ in range(AIRateLimiter.GLOBAL_LIMIT):
            result = AIRateLimiter.check_global_limit()
            self.assertTrue(result)

        # Next call should be blocked
        result = AIRateLimiter.check_global_limit()
        self.assertFalse(result)

    def test_different_users_have_independent_limits(self):
        """Test that different users have independent rate limits."""
        user2 = User.objects.create_user(username="testuser2", password="testpass123")

        # Exhaust user1's limit
        for _ in range(AIRateLimiter.USER_LIMIT):
            AIRateLimiter.check_user_limit(self.user.id)

        # user1 should be blocked
        self.assertFalse(AIRateLimiter.check_user_limit(self.user.id))

        # user2 should still be allowed
        self.assertTrue(AIRateLimiter.check_user_limit(user2.id))

    def test_get_remaining_calls_accuracy(self):
        """Test that get_remaining_calls returns accurate count."""
        # Initially should have full limit
        remaining = AIRateLimiter.get_remaining_calls(self.user.id, has_premium=False)
        self.assertEqual(remaining, AIRateLimiter.USER_LIMIT)

        # Make 5 calls
        for _ in range(5):
            AIRateLimiter.check_user_limit(self.user.id)

        # Should have 5 remaining
        remaining = AIRateLimiter.get_remaining_calls(self.user.id, has_premium=False)
        self.assertEqual(remaining, AIRateLimiter.USER_LIMIT - 5)

    def test_reset_user_limit_clears_counter(self):
        """Test that reset_user_limit clears the rate limit counter."""
        # Exhaust limit
        for _ in range(AIRateLimiter.USER_LIMIT):
            AIRateLimiter.check_user_limit(self.user.id)

        # Should be blocked
        self.assertFalse(AIRateLimiter.check_user_limit(self.user.id))

        # Reset
        AIRateLimiter.reset_user_limit(self.user.id)

        # Should be allowed again
        self.assertTrue(AIRateLimiter.check_user_limit(self.user.id))

    def test_reset_global_limit_clears_global_counter(self):
        """Test that reset_global_limit clears the global rate limit."""
        # Make some calls
        for _ in range(50):
            AIRateLimiter.check_global_limit()

        # Reset
        AIRateLimiter.reset_global_limit()

        # Should start from 0 again
        # Make GLOBAL_LIMIT more calls - should all succeed
        for _ in range(AIRateLimiter.GLOBAL_LIMIT):
            result = AIRateLimiter.check_global_limit()
            self.assertTrue(result)

    def test_decorator_allows_within_limit(self):
        """Test that @ai_rate_limit decorator allows calls within limit."""
        factory = RequestFactory()

        @ai_rate_limit
        def test_view(request):
            return HttpResponse("Success")

        request = factory.get("/")
        request.user = self.user

        response = test_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Success")

    def test_decorator_blocks_over_limit(self):
        """Test that @ai_rate_limit decorator blocks calls over limit."""
        factory = RequestFactory()

        @ai_rate_limit
        def test_view(request):
            return HttpResponse("Success")

        request = factory.get("/")
        request.user = self.user

        # Exhaust limit
        for _ in range(AIRateLimiter.USER_LIMIT):
            response = test_view(request)
            self.assertEqual(response.status_code, 200)

        # Next call should return 429
        response = test_view(request)
        self.assertEqual(response.status_code, 429)
        self.assertIn("AI rate limit exceeded", response.content.decode())

    def test_decorator_returns_retry_after_header(self):
        """Test that decorator includes Retry-After header."""
        factory = RequestFactory()

        @ai_rate_limit
        def test_view(request):
            return HttpResponse("Success")

        request = factory.get("/")
        request.user = self.user

        # Exhaust limit
        for _ in range(AIRateLimiter.USER_LIMIT):
            test_view(request)

        # Next call should have Retry-After header
        response = test_view(request)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)
        self.assertEqual(response.headers["Retry-After"], "3600")  # 1 hour

    def test_anonymous_user_has_zero_id(self):
        """Test that anonymous users get user_id=0 for rate limiting."""
        factory = RequestFactory()

        @ai_rate_limit
        def test_view(request):
            return HttpResponse("Success")

        request = factory.get("/")
        request.user = type(
            "AnonymousUser", (), {"is_authenticated": False, "is_staff": False}
        )()

        # Should still work for anonymous users
        response = test_view(request)
        self.assertEqual(response.status_code, 200)

    def test_cache_ttl_is_one_hour(self):
        """Test that rate limit TTL is set to 1 hour (3600 seconds)."""
        self.assertEqual(AIRateLimiter.TTL, 3600)

    def test_concurrent_checks_increment_correctly(self):
        """Test that concurrent limit checks increment counter correctly."""
        # Make multiple rapid checks
        for i in range(5):
            AIRateLimiter.check_user_limit(self.user.id)

        # Remaining should be correct
        remaining = AIRateLimiter.get_remaining_calls(self.user.id)
        self.assertEqual(remaining, AIRateLimiter.USER_LIMIT - 5)
