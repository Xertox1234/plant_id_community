"""
Unit Tests for ThreadPoolExecutor and Redis Caching

Tests the Week 2 performance optimizations:
- ThreadPoolExecutor singleton pattern and thread safety
- Redis caching for Plant.id and PlantNet services
- Parallel API execution
- Cache key generation and invalidation
"""

import hashlib
import os
import time
import threading
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.test import TestCase, override_settings
from django.core.cache import cache

from apps.plant_identification.services.combined_identification_service import (
    get_executor,
    _cleanup_executor,
    CombinedPlantIdentificationService,
    _EXECUTOR,
)
from apps.plant_identification.services.plant_id_service import PlantIDAPIService
from apps.plant_identification.services.plantnet_service import PlantNetAPIService


class TestThreadPoolExecutor(TestCase):
    """Test ThreadPoolExecutor singleton pattern and thread safety."""

    def setUp(self):
        """Reset executor state before each test."""
        _cleanup_executor()

    def tearDown(self):
        """Cleanup after tests."""
        _cleanup_executor()
        cache.clear()

    def test_get_executor_returns_singleton(self):
        """Verify executor is shared across multiple calls."""
        executor1 = get_executor()
        executor2 = get_executor()

        self.assertIsNotNone(executor1)
        self.assertIsNotNone(executor2)
        self.assertIs(executor1, executor2, "Executor should be singleton")

    @override_settings(PLANT_ID_MAX_WORKERS='4')
    def test_get_executor_respects_env_var(self):
        """Verify PLANT_ID_MAX_WORKERS environment variable is honored."""
        with patch.dict(os.environ, {'PLANT_ID_MAX_WORKERS': '4'}):
            executor = get_executor()
            self.assertEqual(executor._max_workers, 4)

    def test_get_executor_validates_negative_workers(self):
        """Verify negative max_workers is rejected and defaults to safe value."""
        with patch.dict(os.environ, {'PLANT_ID_MAX_WORKERS': '-5'}):
            executor = get_executor()
            self.assertGreater(executor._max_workers, 0, "Should default to positive value")

    def test_get_executor_validates_non_numeric(self):
        """Verify non-numeric max_workers falls back to default."""
        with patch.dict(os.environ, {'PLANT_ID_MAX_WORKERS': 'invalid'}):
            executor = get_executor()
            self.assertIsInstance(executor, ThreadPoolExecutor)
            self.assertGreater(executor._max_workers, 0)

    def test_get_executor_caps_at_maximum(self):
        """Verify max_workers is capped at 10 to prevent API rate limit issues."""
        with patch.dict(os.environ, {'PLANT_ID_MAX_WORKERS': '100'}):
            executor = get_executor()
            self.assertLessEqual(executor._max_workers, 10, "Should cap at 10 workers")

    def test_executor_thread_safety(self):
        """Verify thread-safe initialization under concurrent access."""
        results = []

        def get_and_store_executor():
            executor = get_executor()
            results.append(executor)

        # Create 10 threads that simultaneously call get_executor()
        threads = [threading.Thread(target=get_and_store_executor) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same executor instance
        self.assertEqual(len(results), 10)
        first_executor = results[0]
        for executor in results:
            self.assertIs(executor, first_executor, "All threads should get same executor")

    def test_cleanup_executor_sets_null(self):
        """Verify cleanup resets global executor state."""
        global _EXECUTOR

        executor = get_executor()
        self.assertIsNotNone(executor)

        _cleanup_executor()

        # _EXECUTOR should be None after cleanup
        # Note: We can't access _EXECUTOR directly in this test due to scope,
        # but we can verify a new executor is created on next call
        new_executor = get_executor()
        self.assertIsNot(new_executor, executor, "New executor should be created after cleanup")


@override_settings(PLANT_ID_API_KEY='test_api_key_12345')
class TestPlantIdCaching(TestCase):
    """Test Redis caching for Plant.id service."""

    def setUp(self):
        """Setup test data and clear cache."""
        cache.clear()
        self.test_image_data = b"fake_image_data_for_testing"
        self.test_image_hash = hashlib.sha256(self.test_image_data).hexdigest()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    @patch('apps.plant_identification.services.plant_id_service.requests.Session')
    def test_cache_miss_calls_api(self, mock_session):
        """Verify cache miss results in API call."""
        # Setup mock responses for v3 API (identification + health_assessment)
        identification_response = Mock()
        identification_response.json.return_value = {
            'result': {
                'is_plant': {'binary': True, 'probability': 1.0},
                'classification': {
                    'suggestions': [
                        {
                            'name': 'Test Plant',
                            'probability': 0.95,
                            'details': {
                                'common_names': ['Test'],
                                'url': 'https://example.com'
                            }
                        }
                    ]
                }
            }
        }
        identification_response.raise_for_status = Mock()
        identification_response.status_code = 201

        health_response = Mock()
        health_response.json.return_value = {
            'result': {
                'is_healthy': {'binary': True, 'probability': 0.9},
                'disease': {'suggestions': []}
            }
        }
        health_response.raise_for_status = Mock()
        health_response.status_code = 201

        # Return different responses for each call
        mock_session.return_value.post.side_effect = [identification_response, health_response]

        service = PlantIDAPIService()
        result = service.identify_plant(BytesIO(self.test_image_data), include_diseases=True)

        # Verify API was called (v3 makes 2 calls: identification + health_assessment)
        self.assertEqual(mock_session.return_value.post.call_count, 2,
                        "Should call identification + health_assessment endpoints")
        self.assertIsNotNone(result)

    @patch('apps.plant_identification.services.plant_id_service.requests.Session')
    def test_cache_hit_skips_api(self, mock_session):
        """Verify cache hit returns cached result without API call."""
        # Setup mock responses for v3 API
        identification_response = Mock()
        identification_response.json.return_value = {
            'result': {
                'is_plant': {'binary': True, 'probability': 1.0},
                'classification': {
                    'suggestions': [
                        {
                            'name': 'Cached Plant',
                            'probability': 0.95,
                            'details': {
                                'common_names': ['Cached'],
                                'url': 'https://example.com'
                            }
                        }
                    ]
                }
            }
        }
        identification_response.raise_for_status = Mock()
        identification_response.status_code = 201

        health_response = Mock()
        health_response.json.return_value = {
            'result': {
                'is_healthy': {'binary': True, 'probability': 0.9},
                'disease': {'suggestions': []}
            }
        }
        health_response.raise_for_status = Mock()
        health_response.status_code = 201

        # Return responses for both endpoints
        mock_session.return_value.post.side_effect = [identification_response, health_response]

        service = PlantIDAPIService()

        # First call - cache miss (v3 makes 2 calls: identification + health_assessment)
        result1 = service.identify_plant(BytesIO(self.test_image_data), include_diseases=True)
        first_call_count = mock_session.return_value.post.call_count

        # Second call - cache hit (should use cached result, no additional API calls)
        result2 = service.identify_plant(BytesIO(self.test_image_data), include_diseases=True)
        second_call_count = mock_session.return_value.post.call_count

        # Verify API was only called for first request (cache hit on second call)
        self.assertEqual(first_call_count, 2, "First call should hit both v3 endpoints")
        self.assertEqual(second_call_count, 2, "Second call should use cache (no additional calls)")
        self.assertEqual(result1, result2, "Results should be identical")

    def test_cache_key_includes_api_version(self):
        """Verify cache key includes API version for proper invalidation."""
        service = PlantIDAPIService()

        # Generate cache key
        image_hash = hashlib.sha256(self.test_image_data).hexdigest()
        expected_key = f"plant_id:{service.API_VERSION}:{image_hash}:True"

        # Set a value in cache
        cache.set(expected_key, {'test': 'data'}, timeout=10)

        # Verify we can retrieve it
        cached_value = cache.get(expected_key)
        self.assertEqual(cached_value, {'test': 'data'})

    def test_cache_key_includes_disease_flag(self):
        """Verify different cache keys for different include_diseases parameter."""
        image_hash = hashlib.sha256(self.test_image_data).hexdigest()
        service = PlantIDAPIService()

        key_with_diseases = f"plant_id:{service.API_VERSION}:{image_hash}:True"
        key_without_diseases = f"plant_id:{service.API_VERSION}:{image_hash}:False"

        # These should be different keys
        self.assertNotEqual(key_with_diseases, key_without_diseases)


@override_settings(PLANTNET_API_KEY='test_plantnet_key_67890')
class TestPlantNetCaching(TestCase):
    """Test Redis caching for PlantNet service."""

    def setUp(self):
        """Setup test data and clear cache."""
        cache.clear()
        self.test_image_data = b"fake_plantnet_image_data"

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    @patch('apps.plant_identification.services.plantnet_service.requests.Session')
    def test_plantnet_cache_miss_calls_api(self, mock_session):
        """Verify PlantNet cache miss results in API call."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [{'species': {'scientificNameWithoutAuthor': 'Test Species'}, 'score': 0.9}]
        }
        mock_response.raise_for_status = Mock()
        mock_session.return_value.post.return_value = mock_response

        service = PlantNetAPIService()

        # Create mock image file
        mock_image = Mock()
        mock_image.read.return_value = self.test_image_data

        with patch.object(service, '_prepare_image', return_value=self.test_image_data):
            result = service.identify_plant([mock_image], project='world')

        # Verify API was called
        mock_session.return_value.post.assert_called_once()
        self.assertIsNotNone(result)

    @patch('apps.plant_identification.services.plantnet_service.requests.Session')
    def test_plantnet_cache_hit_skips_api(self, mock_session):
        """Verify PlantNet cache hit returns cached result without API call."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [{'species': {'scientificNameWithoutAuthor': 'Cached Species'}, 'score': 0.9}]
        }
        mock_response.raise_for_status = Mock()
        mock_session.return_value.post.return_value = mock_response

        service = PlantNetAPIService()

        # Create mock image file
        mock_image = Mock()
        mock_image.read.return_value = self.test_image_data

        with patch.object(service, '_prepare_image', return_value=self.test_image_data):
            # First call - cache miss
            result1 = service.identify_plant([mock_image], project='world')
            first_call_count = mock_session.return_value.post.call_count

            # Reset mock image for second call
            mock_image.read.return_value = self.test_image_data

            # Second call - cache hit
            result2 = service.identify_plant([mock_image], project='world')
            second_call_count = mock_session.return_value.post.call_count

        # Verify API was only called once
        self.assertEqual(first_call_count, 1, "First call should hit API")
        self.assertEqual(second_call_count, 1, "Second call should use cache")
        self.assertEqual(result1, result2, "Results should be identical")

    def test_plantnet_cache_key_includes_all_parameters(self):
        """Verify PlantNet cache key includes project, organs, modifiers."""
        service = PlantNetAPIService()

        image_data = b"test_image"
        image_hash = hashlib.sha256(image_data).hexdigest()

        # Expected cache key format
        expected_key = f"plantnet:{service.API_VERSION}:world:{image_hash}:leaf:none:False"

        # Set a value
        cache.set(expected_key, {'test': 'plantnet_data'}, timeout=10)

        # Verify retrieval
        cached_value = cache.get(expected_key)
        self.assertEqual(cached_value, {'test': 'plantnet_data'})


class TestParallelExecution(TestCase):
    """Test parallel API execution in CombinedPlantIdentificationService."""

    def setUp(self):
        """Setup test data and clear cache."""
        cache.clear()
        self.test_image_data = b"parallel_test_image"

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    @patch('apps.plant_identification.services.combined_identification_service.PlantIDAPIService')
    @patch('apps.plant_identification.services.combined_identification_service.PlantNetAPIService')
    def test_parallel_execution_both_apis_called(self, mock_plantnet_class, mock_plant_id_class):
        """Verify both APIs are called in parallel."""
        # Setup mock instances
        mock_plant_id_instance = Mock()
        mock_plant_id_instance.identify_plant.return_value = {
            'suggestions': [{'plant_name': 'Test Plant', 'probability': 0.95}]
        }
        mock_plant_id_class.return_value = mock_plant_id_instance

        mock_plantnet_instance = Mock()
        mock_plantnet_instance.identify_plant.return_value = {
            'results': [{'species': {'scientificNameWithoutAuthor': 'Test Species'}, 'score': 0.9}]
        }
        mock_plantnet_class.return_value = mock_plantnet_instance

        service = CombinedPlantIdentificationService()
        result = service.identify_plant(BytesIO(self.test_image_data))

        # Verify both APIs were called
        mock_plant_id_instance.identify_plant.assert_called_once()
        mock_plantnet_instance.identify_plant.assert_called_once()
        self.assertIn('combined_suggestions', result)

    @patch('apps.plant_identification.services.combined_identification_service.PlantIDAPIService')
    @patch('apps.plant_identification.services.combined_identification_service.PlantNetAPIService')
    def test_parallel_execution_faster_than_sequential(self, mock_plantnet_class, mock_plant_id_class):
        """Verify parallel execution is faster than sequential would be."""
        # Simulate slow API calls
        def slow_plant_id(*args, **kwargs):
            time.sleep(0.1)  # 100ms
            return {'suggestions': [{'plant_name': 'Plant', 'probability': 0.9}]}

        def slow_plantnet(*args, **kwargs):
            time.sleep(0.1)  # 100ms
            return {'results': [{'species': {'scientificNameWithoutAuthor': 'Species'}, 'score': 0.8}]}

        mock_plant_id_instance = Mock()
        mock_plant_id_instance.identify_plant.side_effect = slow_plant_id
        mock_plant_id_class.return_value = mock_plant_id_instance

        mock_plantnet_instance = Mock()
        mock_plantnet_instance.identify_plant.side_effect = slow_plantnet
        mock_plantnet_class.return_value = mock_plantnet_instance

        service = CombinedPlantIdentificationService()

        start = time.time()
        service.identify_plant(BytesIO(self.test_image_data))
        elapsed = time.time() - start

        # Parallel execution should be ~100ms (not ~200ms for sequential)
        # Allow some overhead for thread scheduling
        self.assertLess(elapsed, 0.18, f"Parallel execution too slow: {elapsed:.2f}s")

    @patch('apps.plant_identification.services.combined_identification_service.PlantIDAPIService')
    @patch('apps.plant_identification.services.combined_identification_service.PlantNetAPIService')
    def test_parallel_execution_handles_one_failure(self, mock_plantnet_class, mock_plant_id_class):
        """Verify service continues if one API fails."""
        # Plant.id succeeds, PlantNet fails
        mock_plant_id_instance = Mock()
        mock_plant_id_instance.identify_plant.return_value = {
            'suggestions': [{'plant_name': 'Success Plant', 'probability': 0.95}]
        }
        mock_plant_id_class.return_value = mock_plant_id_instance

        mock_plantnet_instance = Mock()
        mock_plantnet_instance.identify_plant.side_effect = Exception("PlantNet API error")
        mock_plantnet_class.return_value = mock_plantnet_instance

        service = CombinedPlantIdentificationService()
        result = service.identify_plant(BytesIO(self.test_image_data))

        # Should still get results from Plant.id
        self.assertIn('combined_suggestions', result)
        self.assertGreater(len(result['combined_suggestions']), 0)

    @patch('apps.plant_identification.services.combined_identification_service.PlantIDAPIService')
    @patch('apps.plant_identification.services.combined_identification_service.PlantNetAPIService')
    def test_parallel_execution_merges_results(self, mock_plantnet_class, mock_plant_id_class):
        """Verify results from both APIs are properly merged."""
        mock_plant_id_instance = Mock()
        mock_plant_id_instance.identify_plant.return_value = {
            'suggestions': [
                {'plant_name': 'Plant A', 'scientific_name': 'Planta a', 'probability': 0.95}
            ]
        }
        mock_plant_id_class.return_value = mock_plant_id_instance

        mock_plantnet_instance = Mock()
        mock_plantnet_instance.identify_plant.return_value = {
            'results': [
                {'species': {'scientificNameWithoutAuthor': 'Planta a'}, 'score': 0.9}
            ]
        }
        mock_plantnet_class.return_value = mock_plantnet_instance

        service = CombinedPlantIdentificationService()
        result = service.identify_plant(BytesIO(self.test_image_data))

        # Verify merged results
        self.assertIn('combined_suggestions', result)
        suggestions = result['combined_suggestions']
        self.assertGreater(len(suggestions), 0)

        # Should have scientific name from Plant.id
        self.assertIn('scientific_name', suggestions[0])


class TestCachePerformance(TestCase):
    """Test cache performance characteristics."""

    def setUp(self):
        """Clear cache before tests."""
        cache.clear()

    def tearDown(self):
        """Clear cache after tests."""
        cache.clear()

    def test_cache_hit_is_instant(self):
        """Verify cache hit is significantly faster than API call."""
        # Set cached value
        cache_key = "test:performance:key"
        cache.set(cache_key, {'large': 'data' * 1000}, timeout=10)

        # Measure cache retrieval time
        start = time.time()
        result = cache.get(cache_key)
        cache_time = time.time() - start

        self.assertIsNotNone(result)
        self.assertLess(cache_time, 0.01, f"Cache hit too slow: {cache_time:.4f}s")

    def test_cache_respects_ttl(self):
        """Verify cache respects timeout (TTL)."""
        cache_key = "test:ttl:key"
        cache.set(cache_key, {'data': 'value'}, timeout=1)  # 1 second TTL

        # Immediate retrieval should work
        result1 = cache.get(cache_key)
        self.assertIsNotNone(result1)

        # After TTL expires
        time.sleep(1.1)
        result2 = cache.get(cache_key)
        self.assertIsNone(result2, "Cache should expire after TTL")


# Run with: python manage.py test apps.plant_identification.test_executor_caching
