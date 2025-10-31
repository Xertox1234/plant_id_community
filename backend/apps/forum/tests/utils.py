"""
Test utility functions for forum testing.

Provides helper functions for common testing operations.
"""

import hashlib
import json
from typing import Optional, Dict, Any, List
from django.core.cache import cache
from django.urls import reverse


class ForumTestUtils:
    """Collection of test utility methods."""

    @staticmethod
    def generate_cache_key(prefix: str, identifier: str) -> str:
        """
        Generate a cache key with SHA-256 hash.

        Args:
            prefix: Cache key prefix
            identifier: Unique identifier

        Returns:
            Cache key string
        """
        hash_value = hashlib.sha256(identifier.encode()).hexdigest()
        return f"{prefix}:{hash_value[:16]}"

    @staticmethod
    def clear_forum_cache():
        """Clear all forum-related cache keys."""
        # Clear entire cache (safer for tests)
        cache.clear()

    @staticmethod
    def get_api_url(viewname: str, **kwargs) -> str:
        """
        Get API URL for a view.

        Args:
            viewname: View name (e.g., 'forum:thread-list')
            **kwargs: URL parameters

        Returns:
            Full API URL path
        """
        return reverse(viewname, kwargs=kwargs)

    @staticmethod
    def assert_json_structure(data: Dict[str, Any], expected_fields: List[str]):
        """
        Assert JSON data has expected structure.

        Args:
            data: JSON data dict
            expected_fields: List of required field names

        Raises:
            AssertionError: If fields are missing
        """
        for field in expected_fields:
            if field not in data:
                raise AssertionError(f"Expected field '{field}' not in data: {data.keys()}")

    @staticmethod
    def create_draft_js_content(text: str, bold_range: Optional[tuple] = None) -> Dict[str, Any]:
        """
        Create Draft.js format content for testing.

        Args:
            text: Plain text content
            bold_range: Optional (start, length) tuple for bold styling

        Returns:
            Draft.js content dict
        """
        block = {
            "key": "test123",
            "text": text,
            "type": "unstyled",
            "depth": 0,
            "inlineStyleRanges": [],
            "entityRanges": [],
            "data": {}
        }

        if bold_range:
            block["inlineStyleRanges"].append({
                "offset": bold_range[0],
                "length": bold_range[1],
                "style": "BOLD"
            })

        return {
            "blocks": [block],
            "entityMap": {}
        }

    @staticmethod
    def parse_draft_js_to_plain_text(content: Dict[str, Any]) -> str:
        """
        Extract plain text from Draft.js content.

        Args:
            content: Draft.js content dict

        Returns:
            Plain text string
        """
        if not content or "blocks" not in content:
            return ""

        texts = [block.get("text", "") for block in content["blocks"]]
        return "\n".join(texts)

    @staticmethod
    def count_database_queries(func):
        """
        Decorator to count database queries.

        Usage:
            @ForumTestUtils.count_database_queries
            def test_something(self):
                # test code
        """
        from django.test.utils import override_settings
        from django.db import connection, reset_queries

        def wrapper(*args, **kwargs):
            reset_queries()
            with override_settings(DEBUG=True):
                result = func(*args, **kwargs)
                query_count = len(connection.queries)
                print(f"\nQuery count: {query_count}")
                for i, query in enumerate(connection.queries, 1):
                    print(f"{i}. {query['sql']}")
            return result
        return wrapper

    @staticmethod
    def create_authenticated_client(user):
        """
        Create an authenticated API client.

        Args:
            user: User instance

        Returns:
            APIClient instance with authentication
        """
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @staticmethod
    def assert_paginated_response(response_data: Dict[str, Any], expected_min: int = 0):
        """
        Assert response has paginated structure.

        Args:
            response_data: API response data
            expected_min: Minimum expected results

        Raises:
            AssertionError: If pagination structure is invalid
        """
        required_fields = ['results', 'count', 'next', 'previous']
        for field in required_fields:
            if field not in response_data:
                raise AssertionError(
                    f"Missing pagination field '{field}' in response: {response_data.keys()}"
                )

        if len(response_data['results']) < expected_min:
            raise AssertionError(
                f"Expected at least {expected_min} results, got {len(response_data['results'])}"
            )

    @staticmethod
    def get_reaction_counts(post) -> Dict[str, int]:
        """
        Get reaction counts for a post.

        Args:
            post: Post instance

        Returns:
            Dict of reaction_type -> count
        """
        from apps.forum.models import Reaction
        from django.db.models import Count

        counts = Reaction.objects.filter(
            post=post,
            is_active=True
        ).values('reaction_type').annotate(
            count=Count('id')
        )

        return {item['reaction_type']: item['count'] for item in counts}

    @staticmethod
    def simulate_cache_stampede(cache_key: str, num_requests: int = 10):
        """
        Simulate cache stampede scenario for testing distributed locks.

        Args:
            cache_key: Cache key to test
            num_requests: Number of concurrent requests to simulate

        Returns:
            List of results from each request
        """
        import threading

        results = []
        lock = threading.Lock()

        def make_request():
            # Simulate cache check
            cached = cache.get(cache_key)
            if cached is None:
                # Simulate expensive operation
                import time
                time.sleep(0.1)
                data = {"computed": True}
                cache.set(cache_key, data, 60)
                with lock:
                    results.append(("computed", data))
            else:
                with lock:
                    results.append(("cached", cached))

        threads = [threading.Thread(target=make_request) for _ in range(num_requests)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        return results

    @staticmethod
    def create_test_image_file(filename: str = "test.jpg"):
        """
        Create a simple test image file.

        Args:
            filename: Desired filename

        Returns:
            SimpleUploadedFile instance
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create a simple 100x100 red image
        image = Image.new('RGB', (100, 100), color='red')
        byte_io = io.BytesIO()
        image.save(byte_io, 'JPEG')
        byte_io.seek(0)

        return SimpleUploadedFile(
            name=filename,
            content=byte_io.read(),
            content_type='image/jpeg'
        )

    @staticmethod
    def bulk_create_posts(thread, count: int = 100):
        """
        Efficiently create many posts for performance testing.

        Args:
            thread: Thread instance
            count: Number of posts to create

        Returns:
            List of created posts
        """
        from apps.forum.models import Post
        from .factories import UserFactory

        user = UserFactory.create()
        posts = [
            Post(
                thread=thread,
                author=user,
                content_raw=f"Post {i}",
                content_format='plain'
            )
            for i in range(count)
        ]

        return Post.objects.bulk_create(posts)

    @staticmethod
    def print_test_data_summary(data: Dict[str, Any]):
        """
        Print a summary of test data for debugging.

        Args:
            data: Dict of test data
        """
        print("\n=== Test Data Summary ===")
        for key, value in data.items():
            if isinstance(value, list):
                print(f"{key}: {len(value)} items")
            elif isinstance(value, dict):
                print(f"{key}: {len(value)} keys")
            else:
                print(f"{key}: {type(value).__name__}")
        print("=" * 25 + "\n")
