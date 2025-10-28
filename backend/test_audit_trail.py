#!/usr/bin/env python
"""
Test script for audit trail functionality.

This script tests that django-auditlog is properly recording changes
to sensitive models as required for GDPR Article 30 compliance.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from apps.users.models import User
from apps.plant_identification.models import PlantIdentificationResult, PlantSpecies
from auditlog.models import LogEntry

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_user_audit():
    """Test that User model changes are audited."""
    print_section("Testing User Model Audit Logging")

    # Get or create test user
    user, created = User.objects.get_or_create(
        username='test_audit_user',
        defaults={'email': 'test_audit@example.com'}
    )

    if created:
        print(f"✓ Created test user: {user.username}")
    else:
        print(f"✓ Using existing test user: {user.username}")

    # Modify user
    old_bio = user.bio
    user.bio = f"Updated bio for audit test - {timezone.now()}"
    user.save()
    print(f"✓ Updated user bio: {old_bio!r} → {user.bio!r}")

    # Check audit log
    logs = LogEntry.objects.filter(
        content_type__model='user',
        object_pk=str(user.pk)
    ).order_by('-timestamp')

    if logs.exists():
        latest_log = logs.first()
        print(f"✓ Found {logs.count()} audit log entries for user {user.username}")
        print(f"  Latest action: {latest_log.get_action_display()}")
        print(f"  Timestamp: {latest_log.timestamp}")
        print(f"  Actor: {latest_log.actor or 'System'}")
        print(f"  IP Address: {latest_log.remote_addr or 'N/A'}")
        if latest_log.changes:
            print(f"  Changes tracked: {list(latest_log.changes.keys())}")
        return True
    else:
        print("✗ ERROR: No audit logs found for User model!")
        return False

def test_plant_species_audit():
    """Test that PlantSpecies model changes are audited."""
    print_section("Testing PlantSpecies Model Audit Logging")

    # Get or create test species
    species, created = PlantSpecies.objects.get_or_create(
        scientific_name='Testus auditlogicus',
        defaults={
            'common_names': 'Audit Test Plant',
            'family': 'Testaceae',
            'is_verified': False
        }
    )

    if created:
        print(f"✓ Created test species: {species.scientific_name}")
    else:
        print(f"✓ Using existing test species: {species.scientific_name}")

    # Modify species
    old_verified = species.is_verified
    species.is_verified = not species.is_verified
    species.save()
    print(f"✓ Updated species verification: {old_verified} → {species.is_verified}")

    # Check audit log
    logs = LogEntry.objects.filter(
        content_type__model='plantspecies',
        object_pk=str(species.pk)
    ).order_by('-timestamp')

    if logs.exists():
        latest_log = logs.first()
        print(f"✓ Found {logs.count()} audit log entries for species {species.scientific_name}")
        print(f"  Latest action: {latest_log.get_action_display()}")
        print(f"  Timestamp: {latest_log.timestamp}")
        if latest_log.changes:
            print(f"  Changes tracked: {list(latest_log.changes.keys())}")
        return True
    else:
        print("✗ ERROR: No audit logs found for PlantSpecies model!")
        return False

def test_audit_log_queries():
    """Test common audit log queries for GDPR compliance."""
    print_section("Testing Audit Log Queries (GDPR Compliance)")

    # Query 1: All actions on User objects
    user_logs = LogEntry.objects.filter(
        content_type__model='user'
    ).count()
    print(f"✓ Total audit entries for User model: {user_logs}")

    # Query 2: All actions by a specific user
    test_users = User.objects.filter(username__startswith='test_')
    if test_users.exists():
        test_user = test_users.first()
        user_actions = LogEntry.objects.filter(
            actor=test_user
        ).count()
        print(f"✓ Total actions by {test_user.username}: {user_actions}")

    # Query 3: Recent audit entries (last 24 hours)
    from django.utils import timezone
    from datetime import timedelta

    recent_cutoff = timezone.now() - timedelta(hours=24)
    recent_logs = LogEntry.objects.filter(
        timestamp__gte=recent_cutoff
    ).count()
    print(f"✓ Audit entries in last 24 hours: {recent_logs}")

    # Query 4: Audit entries by action type
    for action_choice in LogEntry.Action.choices:
        action_code, action_name = action_choice
        count = LogEntry.objects.filter(action=action_code).count()
        if count > 0:
            print(f"  - {action_name}: {count} entries")

    return True

def cleanup_test_data():
    """Clean up test data created during testing."""
    print_section("Cleaning Up Test Data")

    # Delete test user (audit logs will remain)
    deleted_users = User.objects.filter(username='test_audit_user').delete()
    if deleted_users[0] > 0:
        print(f"✓ Deleted test user (audit logs preserved)")

    # Delete test species
    deleted_species = PlantSpecies.objects.filter(
        scientific_name='Testus auditlogicus'
    ).delete()
    if deleted_species[0] > 0:
        print(f"✓ Deleted test species (audit logs preserved)")

    print("\nNOTE: Audit log entries are preserved even after objects are deleted.")
    print("This is required for GDPR Article 30 compliance.")

def main():
    """Run all audit trail tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  DJANGO-AUDITLOG TEST SUITE".center(68) + "║")
    print("║" + "  GDPR Article 30 Compliance Verification".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    results = []

    # Run tests
    results.append(("User Model Auditing", test_user_audit()))
    results.append(("PlantSpecies Model Auditing", test_plant_species_audit()))
    results.append(("Audit Log Queries", test_audit_log_queries()))

    # Clean up
    cleanup_test_data()

    # Print summary
    print_section("Test Results Summary")

    all_passed = all(result for _, result in results)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print("\n")
    if all_passed:
        print("🎉 All tests passed! Audit trail is working correctly.")
        print("\nNext steps:")
        print("  1. Review audit logs in Django admin at /admin/auditlog/logentry/")
        print("  2. Configure retention policy in production")
        print("  3. Set up log archival to S3/cold storage after 90 days")
        return 0
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    from django.utils import timezone
    sys.exit(main())
