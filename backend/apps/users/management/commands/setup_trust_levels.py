"""
Management command to set up trust level system and forum permissions.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import models
from apps.users.services import TrustLevelService, ForumPostService

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up trust level system with forum permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-users',
            action='store_true',
            help='Update trust levels for all existing users',
        )
        parser.add_argument(
            '--setup-permissions',
            action='store_true',
            help='Set up forum permissions for trust levels',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all setup tasks',
        )

    def handle(self, *args, **options):
        if options['all']:
            options['setup_permissions'] = True
            options['update_users'] = True

        self.stdout.write(
            self.style.SUCCESS('=== Trust Level System Setup ===')
        )

        # Step 1: Set up forum permissions
        if options['setup_permissions']:
            self.stdout.write('Setting up forum permissions...')
            try:
                TrustLevelService.setup_forum_permissions()
                self.stdout.write(
                    self.style.SUCCESS('✓ Forum permissions configured')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to set up permissions: {e}')
                )

        # Step 2: Update existing users
        if options['update_users']:
            self.stdout.write('Updating user trust levels...')
            try:
                # First, update post counts for all users
                self.stdout.write('Updating post counts...')
                for user in User.objects.all():
                    ForumPostService.update_user_post_count(user)
                
                # Then update trust levels and group assignments
                updated_count = TrustLevelService.update_all_user_trust_levels()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Updated {updated_count} users')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to update users: {e}')
                )

        # Step 3: Show summary
        self.show_summary()

    def show_summary(self):
        """Show summary of current trust level distribution."""
        self.stdout.write('\n=== Trust Level Summary ===')
        
        trust_levels = ['new', 'basic', 'trusted', 'veteran']
        total_users = 0
        
        for level in trust_levels:
            count = User.objects.filter(trust_level=level).count()
            total_users += count
            
            # Show users who can upload images
            can_upload_note = ""
            if level in ['basic', 'trusted', 'veteran']:
                can_upload_note = " (can upload images)"
            
            self.stdout.write(f'  {level.title()}: {count} users{can_upload_note}')
        
        self.stdout.write(f'\nTotal users: {total_users}')
        
        # Show users who can upload images
        image_uploaders = User.objects.filter(
            trust_level__in=['basic', 'trusted', 'veteran']
        ).count()
        staff_uploaders = User.objects.filter(
            models.Q(is_staff=True) | models.Q(is_superuser=True)
        ).count()
        
        self.stdout.write(f'Users who can upload images: {image_uploaders} (trust) + {staff_uploaders} (staff)')
        
        # Show some example users for verification
        self.stdout.write('\n=== Example Users ===')
        for level in trust_levels:
            users = User.objects.filter(trust_level=level)[:3]
            if users:
                self.stdout.write(f'{level.title()}:')
                for user in users:
                    info = user.get_trust_level_display_info()
                    self.stdout.write(
                        f'  - {user.username}: {info["posts_count"]} posts, '
                        f'{info["account_age_days"]} days old'
                    )