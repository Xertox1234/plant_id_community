"""
Unit tests for AI content integration (Phase 3).

Tests BlogAIPrompts, BlogAIIntegration, and generate_blog_field_content endpoint
to ensure proper AI content generation with caching and rate limiting.
"""

import json
import unittest
from unittest.mock import patch

from apps.blog.ai_integration import BlogAIIntegration, BlogAIPrompts
from apps.blog.services import AIRateLimiter
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

User = get_user_model()


class BlogAIPromptsTestCase(TestCase):
    """Test suite for BlogAIPrompts custom prompt generation."""

    def test_get_title_prompt_basic(self):
        """Test basic title prompt generation."""
        context = {
            "introduction": "Learn how to care for your Monstera plant with these essential tips."
        }

        prompt = BlogAIPrompts.get_title_prompt(context)

        self.assertIn("blog post title", prompt.lower())
        self.assertIn("40-60 characters", prompt)
        self.assertIn("SEO-optimized", prompt)
        self.assertIn("Learn how to care", prompt)  # Context included

    def test_get_title_prompt_with_plants(self):
        """Test title prompt with related plants."""
        context = {
            "introduction": "Plant care guide",
            "related_plants": [
                {"common_name": "Monstera", "scientific_name": "Monstera deliciosa"},
                {"common_name": "Pothos", "scientific_name": "Epipremnum aureum"},
            ],
        }

        prompt = BlogAIPrompts.get_title_prompt(context)

        self.assertIn("Monstera", prompt)
        self.assertIn("plant name", prompt.lower())

    def test_get_title_prompt_with_difficulty(self):
        """Test title prompt with difficulty level."""
        context = {"introduction": "Plant care basics", "difficulty_level": "beginner"}

        prompt = BlogAIPrompts.get_title_prompt(context)

        self.assertIn("beginner", prompt.lower())
        self.assertIn("beginner-friendly", prompt.lower())

    def test_get_introduction_prompt_basic(self):
        """Test basic introduction prompt generation."""
        context = {"title": "How to Care for Monstera: Complete Guide"}

        prompt = BlogAIPrompts.get_introduction_prompt(context)

        self.assertIn("introduction", prompt.lower())
        self.assertIn("Monstera", prompt)
        self.assertIn("2-3 short paragraphs", prompt)
        self.assertIn("100-150 words", prompt)

    def test_get_introduction_prompt_improve_existing(self):
        """Test introduction prompt for improving existing content."""
        context = {
            "title": "Plant Care Guide",
            "existing_intro": "This is a basic introduction that needs improvement.",
        }

        prompt = BlogAIPrompts.get_introduction_prompt(context)

        self.assertIn("improve", prompt.lower())
        self.assertIn("This is a basic introduction", prompt)

    def test_get_meta_description_prompt_basic(self):
        """Test basic meta description prompt generation."""
        context = {
            "title": "Monstera Care Guide",
            "introduction": "Learn everything about Monstera care...",
        }

        prompt = BlogAIPrompts.get_meta_description_prompt(context)

        self.assertIn("meta description", prompt.lower())
        self.assertIn("140-160 characters", prompt)
        self.assertIn("SEO-optimized", prompt)
        self.assertIn("Monstera", prompt)

    def test_get_meta_description_prompt_with_plants(self):
        """Test meta description prompt with related plants."""
        context = {
            "title": "Plant Care Tips",
            "related_plants": [
                {
                    "common_name": "Snake Plant",
                    "scientific_name": "Sansevieria trifasciata",
                }
            ],
            "difficulty_level": "beginner",
        }

        prompt = BlogAIPrompts.get_meta_description_prompt(context)

        self.assertIn("Snake Plant", prompt)
        self.assertIn("beginner", prompt.lower())

    def test_get_content_block_prompt_heading(self):
        """Test content block prompt for heading type."""
        context = {"plant_name": "Monstera", "section_context": "Watering requirements"}

        prompt = BlogAIPrompts.get_content_block_prompt("heading", context)

        self.assertIn("heading", prompt.lower())
        self.assertIn("3-8 words", prompt)
        self.assertIn("Watering requirements", prompt)

    def test_get_content_block_prompt_paragraph(self):
        """Test content block prompt for paragraph type."""
        context = {
            "plant_name": "Pothos",
            "section_topic": "Light requirements",
            "difficulty_level": "beginner",
        }

        prompt = BlogAIPrompts.get_content_block_prompt("paragraph", context)

        self.assertIn("paragraph", prompt.lower())
        self.assertIn("3-5 sentences", prompt)
        self.assertIn("Pothos", prompt)
        self.assertIn("Light requirements", prompt)
        self.assertIn("beginner", prompt.lower())


class BlogAIIntegrationTestCase(TestCase):
    """Test suite for BlogAIIntegration content generation."""

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

    def test_prompt_generation_title(self):
        """Test that title prompt is generated correctly."""
        context = {
            "introduction": "Learn about Monstera care...",
            "difficulty_level": "beginner",
        }

        # This tests the prompt generation without actually calling AI
        from apps.blog.ai_integration import BlogAIPrompts

        prompt = BlogAIPrompts.get_title_prompt(context)

        self.assertIn("blog post title", prompt.lower())
        self.assertIn("beginner", prompt.lower())

    def test_prompt_generation_introduction(self):
        """Test that introduction prompt is generated correctly."""
        context = {
            "title": "Plant Care Guide",
            "related_plants": [{"common_name": "Monstera"}],
            "difficulty_level": "beginner",
        }

        from apps.blog.ai_integration import BlogAIPrompts

        prompt = BlogAIPrompts.get_introduction_prompt(context)

        self.assertIn("introduction", prompt.lower())
        self.assertIn("Monstera", prompt)

    def test_generate_content_rate_limit_exceeded(self):
        """Test that rate limiting blocks excessive calls."""
        context = {"introduction": "Test"}

        # Exhaust rate limit
        for _ in range(AIRateLimiter.USER_LIMIT):
            AIRateLimiter.check_user_limit(self.user.id, is_staff=False)

        # Next call should fail
        result = BlogAIIntegration.generate_content("title", context, self.user)

        self.assertFalse(result["success"])
        self.assertIn("rate limit exceeded", result["error"].lower())

    def test_generate_content_unsupported_field(self):
        """Test error handling for unsupported field names."""
        context = {}

        result = BlogAIIntegration.generate_content(
            "unsupported_field", context, self.user
        )

        self.assertFalse(result["success"])
        self.assertIn("Unsupported field", result["error"])

    @patch("apps.blog.wagtail_ai_v3_integration.generate_ai_text")
    def test_generate_content_success(self, mock_generate_ai_text):
        """A successful generation returns the LLM text via the v3 helper."""
        mock_generate_ai_text.return_value = "An Engaging Monstera Care Title"
        context = {
            "introduction": "Learn about Monstera care",
            "difficulty_level": "beginner",
        }

        result = BlogAIIntegration.generate_content("title", context, self.user)

        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "An Engaging Monstera Care Title")
        self.assertFalse(result["cached"])
        mock_generate_ai_text.assert_called_once()


@unittest.skip(
    "Endpoint removed in security audit - replaced by Wagtail AI native panel system"
)
class GenerateBlogFieldContentAPITestCase(TestCase):
    """Test suite for generate_blog_field_content API endpoint."""

    def setUp(self):
        """Create test users and client."""
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def get_url(self):
        """Get the generate field content URL."""
        return "/blog-admin/api/generate-field-content/"

    def test_generate_field_content_requires_authentication(self):
        """Test that endpoint requires authentication."""
        data = {"field_name": "title", "context": {"introduction": "Test"}}

        response = self.client.post(
            self.get_url(), data=json.dumps(data), content_type="application/json"
        )

        # @staff_member_required redirects unauthenticated users to the admin login.
        self.assertEqual(response.status_code, 302)

    def test_generate_field_content_requires_staff(self):
        """Test that endpoint requires staff privileges."""
        self.client.force_login(self.user)  # Non-staff user

        data = {"field_name": "title", "context": {"introduction": "Test"}}

        response = self.client.post(
            self.get_url(), data=json.dumps(data), content_type="application/json"
        )

        # @staff_member_required redirects non-staff users to the admin login.
        self.assertEqual(response.status_code, 302)

    @patch("apps.blog.ai_integration.BlogAIIntegration.generate_content")
    def test_generate_field_content_success(self, mock_generate):
        """Test successful field content generation."""
        mock_generate.return_value = {
            "success": True,
            "content": "Generated Title for Plant Care",
            "cached": False,
            "remaining_calls": 9,
        }

        self.client.force_login(self.staff_user)

        data = {
            "field_name": "title",
            "context": {
                "introduction": "Learn about plant care...",
                "difficulty_level": "beginner",
            },
        }

        response = self.client.post(
            self.get_url(), data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        result = json.loads(response.content)
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "Generated Title for Plant Care")
        self.assertEqual(result["field_name"], "title")
        self.assertFalse(result["cached"])
        self.assertIn("remaining_calls", result)
        self.assertIn("limit", result)

    def test_generate_field_content_invalid_field(self):
        """Test error handling for invalid field names."""
        self.client.force_login(self.staff_user)

        data = {"field_name": "invalid_field", "context": {}}

        response = self.client.post(
            self.get_url(), data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result["success"])
        self.assertIn("Invalid field_name", result["error"])

    def test_generate_field_content_invalid_json(self):
        """Test error handling for invalid JSON."""
        self.client.force_login(self.staff_user)

        response = self.client.post(
            self.get_url(), data="invalid json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result["success"])
        self.assertIn("Invalid JSON", result["error"])

    @patch("apps.blog.ai_integration.BlogAIIntegration.generate_content")
    def test_generate_field_content_rate_limit(self, mock_generate):
        """Test rate limiting in API endpoint."""
        # Set up mock to return rate limit error after exhaustion
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= AIRateLimiter.STAFF_LIMIT:
                return {
                    "success": True,
                    "content": "Generated",
                    "cached": False,
                    "remaining_calls": AIRateLimiter.STAFF_LIMIT - call_count[0],
                }
            else:
                return {
                    "success": False,
                    "error": "AI rate limit exceeded",
                    "remaining_calls": 0,
                }

        mock_generate.side_effect = side_effect

        self.client.force_login(self.staff_user)

        data = {"field_name": "title", "context": {}}

        # Exhaust rate limit
        for i in range(AIRateLimiter.STAFF_LIMIT + 1):
            response = self.client.post(
                self.get_url(), data=json.dumps(data), content_type="application/json"
            )

            if i < AIRateLimiter.STAFF_LIMIT:
                self.assertEqual(response.status_code, 200)
            else:
                # Last call should be rate limited
                self.assertEqual(response.status_code, 429)
                result = json.loads(response.content)
                self.assertFalse(result["success"])
                self.assertIn("rate limit", result["error"].lower())

    @patch("apps.blog.ai_integration.BlogAIIntegration.generate_content")
    def test_generate_field_content_caching(self, mock_generate):
        """Test that caching works correctly in API endpoint."""
        # First call returns not cached, second returns cached
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            return {
                "success": True,
                "content": "Cached Title",
                "cached": call_count[0] > 1,  # Second call is cached
                "remaining_calls": 49,
            }

        mock_generate.side_effect = side_effect

        self.client.force_login(self.staff_user)

        data = {
            "field_name": "title",
            "context": {"introduction": "Test content for caching"},
        }

        # First call
        response1 = self.client.post(
            self.get_url(), data=json.dumps(data), content_type="application/json"
        )

        result1 = json.loads(response1.content)
        self.assertFalse(result1["cached"])

        # Second call with same data
        response2 = self.client.post(
            self.get_url(), data=json.dumps(data), content_type="application/json"
        )

        result2 = json.loads(response2.content)
        self.assertTrue(result2["cached"])
        self.assertEqual(result2["content"], result1["content"])

        # Should be called twice (once for each request)
        self.assertEqual(mock_generate.call_count, 2)


def _make_completion_response(text):
    """
    Build a minimal OpenAI-style completion response.

    Mirrors the ``response.choices[0].message.content`` shape that
    ``django_ai_core``'s ``LLMService.completion`` returns, so helper tests can
    exercise the real extraction path without a live LLM.
    """
    message = type("Message", (), {"content": text})()
    choice = type("Choice", (), {"message": message})()
    return type("CompletionResponse", (), {"choices": [choice]})()


class GenerateAiTextHelperTestCase(TestCase):
    """The wagtail-ai 3.x helper that replaces the removed get_ai_text()."""

    @patch("wagtail_ai.agents.base.get_llm_service")
    def test_returns_completion_content(self, mock_get_llm_service):
        """Helper sends the v3 messages payload and returns the LLM text."""
        from apps.blog.wagtail_ai_v3_integration import generate_ai_text

        mock_service = mock_get_llm_service.return_value
        mock_service.completion.return_value = _make_completion_response(
            "Monstera deliciosa thrives in bright, indirect light."
        )

        result = generate_ai_text("Describe Monstera care")

        self.assertEqual(
            result, "Monstera deliciosa thrives in bright, indirect light."
        )
        mock_service.completion.assert_called_once_with(
            messages=[{"role": "user", "content": "Describe Monstera care"}]
        )


class GenerateAiContentViewTestCase(TestCase):
    """The /blog-api/ai-content/ endpoint (H2 migration + H3 rate limiting)."""

    URL = "/api/v1/blog-api/ai-content/"

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )

    def tearDown(self):
        cache.clear()

    def _post(self, payload):
        return self.client.post(
            self.URL, data=json.dumps(payload), content_type="application/json"
        )

    @patch("apps.blog.wagtail_ai_v3_integration.generate_ai_text")
    def test_returns_200_with_generated_content(self, mock_generate_ai_text):
        """A staff request returns 200 with generated content (was always 503)."""
        mock_generate_ai_text.return_value = "Monstera loves bright, indirect light."
        self.client.force_login(self.staff_user)

        response = self._post({"plant_name": "Monstera", "content_type": "description"})

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "Monstera loves bright, indirect light.")
        self.assertEqual(result["content_type"], "description")
        self.assertEqual(result["plant_name"], "Monstera")

    @patch("apps.blog.wagtail_ai_v3_integration.generate_ai_text")
    def test_rate_limited_returns_429_past_threshold(self, mock_generate_ai_text):
        """Past the per-hour staff quota the view returns 429 at the view layer."""
        mock_generate_ai_text.return_value = "Generated content."
        self.client.force_login(self.staff_user)
        payload = {"plant_name": "Monstera", "content_type": "description"}

        # The staff quota allows STAFF_LIMIT calls; the next one is rejected.
        for _ in range(AIRateLimiter.STAFF_LIMIT):
            self.assertEqual(self._post(payload).status_code, 200)

        throttled = self._post(payload)
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(throttled["Retry-After"], "3600")

    @patch("apps.blog.wagtail_ai_v3_integration.generate_ai_text")
    def test_non_staff_redirected_without_consuming_quota(self, mock_generate_ai_text):
        """@staff_member_required runs before @ai_rate_limit: non-staff get 302
        and never increment the AI quota counter (validates decorator order)."""
        non_staff = User.objects.create_user(username="member", password="testpass123")
        self.client.force_login(non_staff)

        response = self._post({"plant_name": "Monstera", "content_type": "description"})

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(cache.get(f"ai_rate_limit:user:{non_staff.id}"))
        mock_generate_ai_text.assert_not_called()
