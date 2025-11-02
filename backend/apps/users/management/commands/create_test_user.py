"""
Django management command to create/reset E2E test user.

Usage:
    python manage.py create_test_user

This creates a test user with predictable credentials for E2E testing:
    - Username: e2e_test_user
    - Email: e2e@test.com
    - Password: E2ETestPassword123456
    - First Name: E2E
    - Last Name: Test User

If the user already exists, it will be deleted and recreated to ensure
a clean state for testing.
"""

from typing import Any
from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create or reset E2E test user for Playwright tests'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            '--delete-only',
            action='store_true',
            help='Only delete the test user without creating a new one',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        username: str = 'e2e_test_user'
        email: str = 'e2e@test.com'
        password: str = 'E2ETestPassword123456'
        first_name: str = 'E2E'
        last_name: str = 'Test User'

        # Delete existing test user if it exists
        deleted_count, _ = User.objects.filter(username=username).delete()
        if deleted_count > 0:
            self.stdout.write(
                self.style.WARNING(f'Deleted existing test user: {username}')
            )

        # If delete-only flag is set, stop here
        if options['delete_only']:
            self.stdout.write(
                self.style.SUCCESS('Test user deleted successfully')
            )
            return

        # Create new test user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nTest user created successfully!\n'
                f'Username: {user.username}\n'
                f'Email: {user.email}\n'
                f'Password: {password}\n'
                f'Name: {user.first_name} {user.last_name}\n'
            )
        )
