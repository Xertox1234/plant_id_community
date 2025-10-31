"""
Management command to seed forum with test data for development.

Usage:
    python manage.py seed_forum_data
    python manage.py seed_forum_data --clear  # Clear existing data first
    python manage.py seed_forum_data --scenario=active  # Specific scenario
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.forum.tests.fixtures import ForumTestFixtures
from apps.forum.tests.factories import (
    UserFactory,
    CategoryFactory,
    ThreadFactory,
    PostFactory,
)


class Command(BaseCommand):
    help = 'Seed forum with test data for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing forum data before seeding',
        )
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['basic', 'hierarchy', 'active', 'attachments', 'moderation', 'all'],
            default='all',
            help='Which test scenario to create',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create (default: 10)',
        )
        parser.add_argument(
            '--threads',
            type=int,
            default=20,
            help='Number of threads to create (default: 20)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Seeding forum data...'))

        if options['clear']:
            self.clear_data()

        scenario = options['scenario']

        try:
            with transaction.atomic():
                if scenario == 'all':
                    self.create_all_scenarios()
                else:
                    self.create_scenario(scenario)

                # Create additional random data if specified
                if options['users'] > 10 or options['threads'] > 20:
                    self.create_additional_data(
                        users=options['users'],
                        threads=options['threads']
                    )

            self.stdout.write(self.style.SUCCESS('✅ Forum data seeded successfully!'))
            self.print_summary()

        except Exception as e:
            raise CommandError(f'Error seeding data: {str(e)}')

    def clear_data(self):
        """Clear existing forum data."""
        self.stdout.write(self.style.WARNING('Clearing existing forum data...'))

        from apps.forum.models import Category, Thread, Post, Attachment, Reaction

        # Delete in reverse order of dependencies
        deleted_counts = {
            'Reactions': Reaction.objects.all().delete()[0],
            'Attachments': Attachment.objects.all().delete()[0],
            'Posts': Post.objects.all().delete()[0],
            'Threads': Thread.objects.all().delete()[0],
            'Categories': Category.objects.all().delete()[0],
        }

        for model, count in deleted_counts.items():
            self.stdout.write(f'  Deleted {count} {model}')

    def create_all_scenarios(self):
        """Create all test scenarios."""
        self.stdout.write('Creating all test scenarios...')

        scenarios = {
            'basic': ForumTestFixtures.create_basic_forum,
            'hierarchy': ForumTestFixtures.create_forum_with_hierarchy,
            'active': ForumTestFixtures.create_active_discussion,
            'attachments': ForumTestFixtures.create_forum_with_attachments,
            'moderation': ForumTestFixtures.create_moderation_scenario,
            'search': ForumTestFixtures.create_search_test_data,
        }

        for name, func in scenarios.items():
            self.stdout.write(f'  Creating {name} scenario...')
            func()

    def create_scenario(self, scenario: str):
        """Create a specific test scenario."""
        self.stdout.write(f'Creating {scenario} scenario...')

        scenario_map = {
            'basic': ForumTestFixtures.create_basic_forum,
            'hierarchy': ForumTestFixtures.create_forum_with_hierarchy,
            'active': ForumTestFixtures.create_active_discussion,
            'attachments': ForumTestFixtures.create_forum_with_attachments,
            'moderation': ForumTestFixtures.create_moderation_scenario,
        }

        if scenario in scenario_map:
            scenario_map[scenario]()
        else:
            raise CommandError(f'Unknown scenario: {scenario}')

    def create_additional_data(self, users: int, threads: int):
        """Create additional random data."""
        self.stdout.write(f'Creating {users} users and {threads} threads...')

        # Create users
        created_users = UserFactory.create_batch(users)
        self.stdout.write(f'  Created {len(created_users)} users')

        # Create categories
        categories = CategoryFactory.create_batch(5)
        self.stdout.write(f'  Created {len(categories)} categories')

        # Create threads with posts
        for i in range(threads):
            thread = ThreadFactory.create(
                author=created_users[i % len(created_users)],
                category=categories[i % len(categories)]
            )

            # Add 1-5 posts per thread
            import random
            post_count = random.randint(1, 5)
            for j in range(post_count):
                PostFactory.create(
                    thread=thread,
                    author=created_users[(i + j) % len(created_users)],
                    is_first_post=(j == 0)
                )

            # Update thread statistics
            thread.post_count = post_count
            thread.save()

        self.stdout.write(f'  Created {threads} threads with posts')

    def print_summary(self):
        """Print summary of created data."""
        from apps.forum.models import Category, Thread, Post, Attachment, Reaction
        from django.contrib.auth import get_user_model

        User = get_user_model()

        self.stdout.write('\n' + self.style.SUCCESS('=== Summary ==='))
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Categories: {Category.objects.count()}')
        self.stdout.write(f'Threads: {Thread.objects.count()}')
        self.stdout.write(f'Posts: {Post.objects.count()}')
        self.stdout.write(f'Attachments: {Attachment.objects.count()}')
        self.stdout.write(f'Reactions: {Reaction.objects.count()}')
        self.stdout.write(self.style.SUCCESS('=' * 20))

        self.stdout.write('\n' + self.style.HTTP_INFO('Access the forum at:'))
        self.stdout.write('  API: http://localhost:8000/api/v1/forum/')
        self.stdout.write('  Admin: http://localhost:8000/admin/forum/')
