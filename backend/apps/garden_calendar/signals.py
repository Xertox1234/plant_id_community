"""
Garden Calendar Signals

Signal handlers for automatic actions when calendar events occur.

The community-event, RSVP and weather-alert notification receivers were
removed in todo 659: they called NotificationService methods that never
existed, so every run raised an AttributeError that ``except Exception``
swallowed, and none had ever sent anything (no templates, no clients).
"""

import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CommunityEvent

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=CommunityEvent)
def cleanup_orphaned_forum_topics(sender, instance, **kwargs):
    """
    Handle cleanup when community events are deleted.
    """
    try:
        # If the event had an associated forum topic, we might want to:
        # 1. Archive it
        # 2. Add a note that the event was canceled
        # 3. Leave it as-is for historical discussion
        # For now, we'll leave forum topics intact
        pass
    except Exception as e:
        logger.exception("[GARDEN] Error cleaning up deleted community event: %s", e)
