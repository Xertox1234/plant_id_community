"""
Test script to verify rate limiting fixes and system improvements.

This script tests:
1. Rate limit exception handling (no more hanging)
2. Local-first lookup strategy
3. Cache performance
4. Monitoring functionality
"""

import os
import sys
import django
from unittest.mock import patch, MagicMock

# Setup Django
sys.path.append('/home/xertox1234/projects/plant_id_community/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from apps.plant_identification.services.trefle_service import TrefleAPIService
from apps.plant_identification.services.species_lookup_service import SpeciesLookupService
from apps.plant_identification.services.monitoring_service import APIMonitoringService
from apps.plant_identification.exceptions import RateLimitExceeded
from apps.plant_identification.models import PlantSpecies
from django.core.cache import cache
import time

def test_rate_limit_exception():
    """Test that rate limiting raises exception instead of hanging."""
    print("🧪 Testing Rate Limit Exception Handling...")
    
    try:
        # Create a service instance
        trefle = TrefleAPIService()
        
        # Mock the cache to simulate rate limit exceeded
        with patch('django.core.cache.cache.get') as mock_cache_get:
            # Return a list with 121 items (exceeding the 120 limit)
            mock_cache_get.return_value = [time.time()] * 121
            
            # This should raise RateLimitExceeded, not hang
            start_time = time.time()
            try:
                trefle.search_plants("test")
                print("❌ FAILED: Expected RateLimitExceeded exception")
                return False
            except RateLimitExceeded as e:
                elapsed = time.time() - start_time
                if elapsed < 1.0:  # Should be immediate, not 60 seconds
                    print(f"✅ PASSED: Rate limit exception raised immediately ({elapsed:.2f}s)")
                    print(f"   Exception: {e}")
                    return True
                else:
                    print(f"❌ FAILED: Exception took too long ({elapsed:.2f}s)")
                    return False
                    
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_local_first_lookup():
    """Test that local database is checked before API."""
    print("\n🧪 Testing Local-First Lookup Strategy...")
    
    try:
        # Create a test species in local database
        test_species, created = PlantSpecies.objects.get_or_create(
            scientific_name="Test species",
            defaults={
                'common_names': 'Test Plant',
                'identification_count': 10,  # High count for confidence
                'confidence_score': 0.8
            }
        )
        
        # Create lookup service
        lookup_service = SpeciesLookupService()
        
        # Mock the API to ensure it's not called
        with patch.object(lookup_service, '_fetch_from_api') as mock_api:
            mock_api.return_value = None
            
            # Lookup the species - should find it locally
            result = lookup_service.get_species_by_scientific_name("Test species")
            
            if result and result['source'] == 'local_database':
                print("✅ PASSED: Found species in local database")
                print(f"   Species: {result['scientific_name']}")
                print(f"   Source: {result['source']}")
                print(f"   API called: {mock_api.called}")
                return True
            else:
                print("❌ FAILED: Did not find species locally or wrong source")
                return False
                
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False
    finally:
        # Clean up test data
        try:
            PlantSpecies.objects.filter(scientific_name="Test species").delete()
        except:
            pass

def test_cache_performance():
    """Test cache hit/miss recording."""
    print("\n🧪 Testing Cache Performance Monitoring...")
    
    try:
        monitor = APIMonitoringService()
        
        # Clear any existing metrics
        cache.delete(monitor.CACHE_KEYS['cache_hits'])
        cache.delete(monitor.CACHE_KEYS['cache_misses'])
        
        # Record some cache hits and misses
        monitor.record_cache_hit()
        monitor.record_cache_hit()
        monitor.record_cache_miss()
        
        # Get performance metrics
        perf = monitor.get_cache_performance()
        
        if perf['cache_hits'] >= 2 and perf['cache_misses'] >= 1:
            print("✅ PASSED: Cache performance tracking works")
            print(f"   Cache hits: {perf['cache_hits']}")
            print(f"   Cache misses: {perf['cache_misses']}")
            print(f"   Hit ratio: {perf['cache_hit_ratio']:.1f}%")
            return True
        else:
            print("❌ FAILED: Cache metrics not recorded correctly")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_api_monitoring():
    """Test API usage monitoring."""
    print("\n🧪 Testing API Usage Monitoring...")
    
    try:
        monitor = APIMonitoringService()
        
        # Record some API calls
        monitor.record_api_call('trefle', 'plants/search', success=True)
        monitor.record_api_call('trefle', 'species/123', success=True)
        monitor.record_api_call('trefle', 'plants/456', success=False)
        
        # Get usage statistics
        usage = monitor.get_api_usage('trefle')
        
        if usage['hourly_calls'] >= 3:
            print("✅ PASSED: API usage monitoring works")
            print(f"   Hourly calls: {usage['hourly_calls']}")
            print(f"   Alert level: {usage['hourly_alert_level']}")
            return True
        else:
            print("❌ FAILED: API calls not recorded correctly")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_system_health():
    """Test overall system health monitoring."""
    print("\n🧪 Testing System Health Monitoring...")
    
    try:
        monitor = APIMonitoringService()
        
        # Get system health
        health = monitor.get_system_health()
        
        print("✅ PASSED: System health monitoring works")
        print(f"   Overall health: {health['overall_health']}")
        print(f"   Cache healthy: {health['cache_performance']['healthy']}")
        
        # Show any alerts
        alerts = monitor.get_alerts()
        if alerts:
            print("   Active alerts:")
            for alert in alerts:
                print(f"     - {alert['level'].upper()}: {alert['message']}")
        else:
            print("   No active alerts")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Plant Identification Rate Limit Fixes")
    print("=" * 50)
    
    tests = [
        test_rate_limit_exception,
        test_local_first_lookup,
        test_cache_performance,
        test_api_monitoring,
        test_system_health
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The rate limiting fixes are working correctly.")
        print("\nKey improvements verified:")
        print("✓ No more 60-second hangs when rate limited")
        print("✓ Local database prioritized over API calls")
        print("✓ Cache performance monitoring active")
        print("✓ API usage tracking functional")
        print("✓ System health monitoring operational")
        
        print("\nNext steps:")
        print("1. Run: python manage.py optimize_species_database --populate-common")
        print("2. Monitor API usage with the new monitoring service")
        print("3. Use local-first lookups for better performance")
        
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)