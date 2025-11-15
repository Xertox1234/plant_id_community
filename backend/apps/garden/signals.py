"""
Garden Planner Django Signals

Automatic Firebase synchronization on model changes.

Provides:
- Reminder sync on create/update
- Reminder deletion sync
- Background notification sending
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import CareReminder
from .services.firebase_sync_service import FirebaseSyncService
from .firebase_config import is_firebase_available

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CareReminder)
def sync_reminder_to_firebase(sender, instance, created, **kwargs):
    """
    Auto-sync reminder to Firebase on save.

    Args:
        sender: Model class
        instance: CareReminder instance
        created: True if new reminder, False if update
    """
    if not is_firebase_available():
        logger.debug("[SIGNAL] Firebase not available, skipping sync")
        return

    # Sync to Firestore
    success = FirebaseSyncService.sync_reminder(instance)

    if success:
        action = "created" if created else "updated"
        logger.info(
            f"[SIGNAL] Auto-synced {action} reminder {instance.id} "
            f"for user {instance.user.id}"
        )
    else:
        logger.warning(
            f"[SIGNAL] Failed to sync reminder {instance.id} to Firebase"
        )


@receiver(post_delete, sender=CareReminder)
def delete_reminder_from_firebase(sender, instance, **kwargs):
    """
    Remove reminder from Firebase on delete.

    Args:
        sender: Model class
        instance: CareReminder instance
    """
    if not is_firebase_available():
        return

    # Delete from Firestore
    success = FirebaseSyncService.delete_reminder(instance.id, instance.user.id)

    if success:
        logger.info(
            f"[SIGNAL] Auto-deleted reminder {instance.id} "
            f"from Firebase for user {instance.user.id}"
        )
    else:
        logger.warning(
            f"[SIGNAL] Failed to delete reminder {instance.id} from Firebase"
        )
