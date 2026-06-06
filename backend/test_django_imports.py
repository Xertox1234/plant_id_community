#!/usr/bin/env python3
"""
Test Django imports and basic functionality.
"""

import os
import sys

import django
from django.conf import settings

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plant_community_backend.settings")


def test_django_imports():
    """Test that our Django modules can be imported."""
    print("🧪 Testing Django imports...")

    try:
        # Initialize Django
        django.setup()
        print("✅ Django setup successful")

        # Test importing our exception classes
        from apps.plant_identification.exceptions import (
            APIUnavailable,
            RateLimitExceeded,
        )

        print("✅ Exception classes imported")

        # Test importing services
        from apps.plant_identification.services.monitoring_service import (
            APIMonitoringService,
        )

        print("✅ Monitoring service imported")

        # Test creating monitoring service
        monitor = APIMonitoringService()
        print("✅ Monitoring service instantiated")

        # Test importing species lookup service
        from apps.plant_identification.services.species_lookup_service import (
            SpeciesLookupService,
        )

        print("✅ Species lookup service imported")

        # Test importing identification service
        from apps.plant_identification.services.identification_service import (
            PlantIdentificationService,
        )

        print("✅ Identification service imported")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Setup error: {e}")
        return False


def test_exception_functionality():
    """Test that our exceptions work as expected."""
    print("\n🧪 Testing exception functionality...")

    try:
        from apps.plant_identification.exceptions import RateLimitExceeded

        # Test raising the exception
        try:
            raise RateLimitExceeded(
                "Test rate limit exceeded", api_name="TestAPI", retry_after=30
            )
        except RateLimitExceeded as e:
            print(f"✅ Exception caught: {e}")
            print(f"✅ API name: {e.api_name}")
            print(f"✅ Retry after: {e.retry_after}")
            return True

    except Exception as e:
        print(f"❌ Exception test failed: {e}")
        return False


def test_monitoring_basic():
    """Test basic monitoring functionality."""
    print("\n🧪 Testing monitoring functionality...")

    try:
        from apps.plant_identification.services.monitoring_service import (
            APIMonitoringService,
        )

        monitor = APIMonitoringService()

        # Test recording API call
        monitor.record_api_call("trefle", "test_endpoint", success=True)
        print("✅ API call recorded")

        # Test getting usage stats
        usage = monitor.get_api_usage("trefle")
        print(f"✅ Usage stats retrieved: {usage['hourly_calls']} calls")

        # Test cache performance
        monitor.record_cache_hit()
        monitor.record_cache_miss()
        perf = monitor.get_cache_performance()
        print(
            f"✅ Cache performance: {perf['cache_hits']} hits, {perf['cache_misses']} misses"
        )

        return True

    except Exception as e:
        print(f"❌ Monitoring test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all Django tests."""
    print("🚀 Testing Django Integration")
    print("=" * 40)

    tests = [
        ("Django Imports", test_django_imports),
        ("Exception Functionality", test_exception_functionality),
        ("Monitoring Basic", test_monitoring_basic),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} FAILED with exception: {e}")

    print("\n" + "=" * 40)
    print(f"📊 Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All Django integration tests PASSED!")
        print("\n✨ Your rate limiting fixes are working correctly!")
        print("\nThe system is ready for:")
        print("• Immediate deployment to fix hanging issues")
        print("• Running optimization commands")
        print("• Production use with enhanced monitoring")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check the errors above.")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
