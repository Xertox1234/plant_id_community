"""
Management command to warm the moderation dashboard cache.

Usage:
    python manage.py warm_moderation_cache

This command pre-populates the moderation dashboard cache on server startup
or after cache clearing, ensuring the first moderator request is fast.

Performance Impact:
- Eliminates cold cache penalty (~500ms first load)
- Provides instant dashboard response (<50ms cached)
- Recommended to run on app deployment/restart
"""

import logging
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.forum.viewsets.moderation_queue_viewset import ModerationQueueViewSet
from apps.forum.constants import CACHE_KEY_MOD_DASHBOARD

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Pre-populate moderation dashboard cache for faster initial load'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cache refresh even if cache exists'
        )

    def handle(self, *args, **options):
        force_refresh = options.get('force', False)

        # Check if cache already exists
        if not force_refresh:
            cached_data = cache.get(CACHE_KEY_MOD_DASHBOARD)
            if cached_data:
                self.stdout.write(
                    self.style.SUCCESS(
                        '✓ Dashboard cache already warm (use --force to refresh)'
                    )
                )
                return

        try:
            # Get or create a staff user for the request
            User = get_user_model()
            staff_user = User.objects.filter(
                is_staff=True,
                is_active=True
            ).first()

            if not staff_user:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠ No active staff user found. Dashboard cache requires staff permissions.'
                    )
                )
                self.stdout.write('  Run: python manage.py createsuperuser')
                return

            # Create a fake request context
            factory = APIRequestFactory()
            request = factory.get('/api/v1/forum/moderation/dashboard/')
            request.user = staff_user

            # Call the dashboard endpoint to populate cache
            viewset = ModerationQueueViewSet()
            viewset.request = request
            viewset.format_kwarg = None

            # Trigger dashboard method (will cache results)
            response = viewset.dashboard(request)

            if response.status_code == 200:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Dashboard cache warmed successfully '
                        f'(TTL: 5 minutes)'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Cache key: {CACHE_KEY_MOD_DASHBOARD}'
                    )
                )

                # Show summary stats
                data = response.data
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Pending flags: {data.get("pending_flags", 0)}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Flags today: {data.get("flags_today", 0)}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Failed to warm cache: HTTP {response.status_code}'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ Error warming dashboard cache: {str(e)}'
                )
            )
            logger.exception("[CACHE] Failed to warm moderation dashboard cache")
            raise

        # Optional: Show cache stats
        if options.get('verbosity', 1) >= 2:
            self.stdout.write('\nCache Statistics:')
            self.stdout.write(f'  Key format: {CACHE_KEY_MOD_DASHBOARD}')
            self.stdout.write('  TTL: 5 minutes (300 seconds)')
            self.stdout.write('  Invalidation: Automatic on flag actions')
