#!/usr/bin/env python
"""
Test script to validate JWT_SECRET_KEY enforcement in settings.py

This script demonstrates that JWT_SECRET_KEY is strictly required
in all environments and cannot fall back to SECRET_KEY.

Usage:
    python test_jwt_secret_key_validation.py
"""
import os
import sys
import tempfile
import subprocess


def test_missing_jwt_secret_key():
    """Test that settings fail loudly when JWT_SECRET_KEY is missing."""
    print("\n" + "=" * 70)
    print("TEST 1: Missing JWT_SECRET_KEY")
    print("=" * 70)

    # Create a temporary .env file without JWT_SECRET_KEY
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write('DEBUG=True\n')
        f.write('SECRET_KEY=' + 'x' * 75 + '\n')  # Valid SECRET_KEY
        f.write('DATABASE_URL=sqlite:///test.db\n')
        temp_env_path = f.name

    try:
        # Try to import settings
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'plant_community_backend.settings'
        env.pop('JWT_SECRET_KEY', None)  # Remove any existing JWT_SECRET_KEY

        result = subprocess.run(
            [sys.executable, '-c',
             f'import os; '
             f'os.environ["DEBUG"] = "True"; '
             f'os.environ["SECRET_KEY"] = "{"x" * 75}"; '
             f'os.environ.pop("JWT_SECRET_KEY", None); '
             f'from plant_community_backend import settings'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        if result.returncode != 0 and 'JWT_SECRET_KEY' in result.stderr:
            print("✓ PASS: Settings correctly rejected missing JWT_SECRET_KEY")
            print("\nError message preview:")
            print(result.stderr[:400] + "...")
            return True
        else:
            print("✗ FAIL: Settings loaded without JWT_SECRET_KEY")
            print("STDOUT:", result.stdout[:300])
            print("STDERR:", result.stderr[:300])
            return False
    finally:
        os.unlink(temp_env_path)


def test_same_keys():
    """Test that settings fail when JWT_SECRET_KEY equals SECRET_KEY."""
    print("\n" + "=" * 70)
    print("TEST 2: JWT_SECRET_KEY equals SECRET_KEY")
    print("=" * 70)

    same_key = 'x' * 75  # Both keys the same

    result = subprocess.run(
        [sys.executable, '-c',
         f'import os; '
         f'os.environ["DEBUG"] = "True"; '
         f'os.environ["SECRET_KEY"] = "{same_key}"; '
         f'os.environ["JWT_SECRET_KEY"] = "{same_key}"; '
         f'from plant_community_backend import settings'],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    if result.returncode != 0 and 'cannot be the same' in result.stderr:
        print("✓ PASS: Settings correctly rejected identical keys")
        print("\nError message preview:")
        print(result.stderr[:400] + "...")
        return True
    else:
        print("✗ FAIL: Settings allowed identical JWT_SECRET_KEY and SECRET_KEY")
        print("STDERR:", result.stderr[:300])
        return False


def test_short_jwt_key():
    """Test that settings fail when JWT_SECRET_KEY is too short."""
    print("\n" + "=" * 70)
    print("TEST 3: JWT_SECRET_KEY too short")
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, '-c',
         f'import os; '
         f'os.environ["DEBUG"] = "True"; '
         f'os.environ["SECRET_KEY"] = "{"a" * 75}"; '
         f'os.environ["JWT_SECRET_KEY"] = "short"; '  # Only 5 characters
         f'from plant_community_backend import settings'],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    if result.returncode != 0 and 'too short' in result.stderr:
        print("✓ PASS: Settings correctly rejected short JWT_SECRET_KEY")
        print("\nError message preview:")
        print(result.stderr[:400] + "...")
        return True
    else:
        print("✗ FAIL: Settings allowed short JWT_SECRET_KEY")
        print("STDERR:", result.stderr[:300])
        return False


def test_valid_configuration():
    """Test that settings load successfully with valid JWT_SECRET_KEY."""
    print("\n" + "=" * 70)
    print("TEST 4: Valid JWT_SECRET_KEY configuration")
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, '-c',
         f'import os; '
         f'os.environ["DEBUG"] = "True"; '
         f'os.environ["SECRET_KEY"] = "{"a" * 75}"; '
         f'os.environ["JWT_SECRET_KEY"] = "{"b" * 75}"; '  # Valid and different
         f'from plant_community_backend import settings; '
         f'print("SUCCESS: Settings loaded correctly")'],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    if result.returncode == 0 and 'SUCCESS' in result.stdout:
        print("✓ PASS: Settings loaded successfully with valid configuration")
        return True
    else:
        print("✗ FAIL: Settings failed to load with valid configuration")
        print("STDOUT:", result.stdout[:300])
        print("STDERR:", result.stderr[:300])
        return False


def main():
    """Run all validation tests."""
    print("\n" + "=" * 70)
    print("JWT_SECRET_KEY Validation Test Suite")
    print("=" * 70)
    print("Testing enforcement of JWT_SECRET_KEY separation (TODO #007)")
    print("Location: backend/plant_community_backend/settings.py:573-637")

    tests = [
        ("Missing JWT_SECRET_KEY", test_missing_jwt_secret_key),
        ("Identical keys", test_same_keys),
        ("Short JWT_SECRET_KEY", test_short_jwt_key),
        ("Valid configuration", test_valid_configuration),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ ERROR in {name}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n✓ All validation tests passed!")
        print("JWT_SECRET_KEY enforcement is working correctly.")
        return 0
    else:
        print(f"\n✗ {total_count - passed_count} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
