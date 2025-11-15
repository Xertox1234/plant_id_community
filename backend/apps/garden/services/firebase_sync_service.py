"""
Firebase Sync Service

Real-time data synchronization with Firebase Firestore.

Provides:
- Reminder sync to Firestore for cross-platform access
- Automatic sync on model changes (via Django signals)
- Batch sync for initial data load
- Offline-first architecture support
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from django.contrib.auth import get_user_model

from ..models import CareReminder, GardenPlant, Garden
from ..firebase_config import get_firestore_client, is_firebase_available

logger = logging.getLogger(__name__)

User = get_user_model()


class FirebaseSyncService:
    """
    Firebase Firestore synchronization service.

    Syncs care reminders to Firestore for:
    - Real-time updates across devices
    - Offline access via Firebase SDK
    - Push notification triggers
    """

    # Firestore collection names
    COLLECTION_REMINDERS = 'care_reminders'
    COLLECTION_USER_REMINDERS = 'user_reminders'  # Subcollection per user

    @classmethod
    def is_available(cls) -> bool:
        """Check if Firebase sync is available."""
        return is_firebase_available()

    @classmethod
    def _serialize_reminder(cls, reminder: CareReminder) -> Dict[str, Any]:
        """
        Serialize CareReminder to Firestore-compatible dict.

        Args:
            reminder: CareReminder instance

        Returns:
            Dict with Firestore-compatible data types
        """
        return {
            'id': str(reminder.id),
            'user_id': str(reminder.user.id),
            'garden_plant_id': str(reminder.garden_plant.id),
            'garden_plant_name': reminder.garden_plant.common_name,
            'garden_id': str(reminder.garden_plant.garden.id),
            'garden_name': reminder.garden_plant.garden.name,
            'reminder_type': reminder.reminder_type,
            'reminder_type_display': reminder.get_reminder_type_display(),
            'custom_type_name': reminder.custom_type_name or '',
            'scheduled_date': reminder.scheduled_date.isoformat(),
            'recurring': reminder.recurring,
            'interval_days': reminder.interval_days,
            'completed': reminder.completed,
            'completed_at': reminder.completed_at.isoformat() if reminder.completed_at else None,
            'skipped': reminder.skipped,
            'skip_reason': reminder.skip_reason or '',
            'notes': reminder.notes or '',
            'notification_sent': reminder.notification_sent,
            'created_at': reminder.created_at.isoformat(),
            'updated_at': datetime.now().isoformat()
        }

    @classmethod
    def sync_reminder(cls, reminder: CareReminder) -> bool:
        """
        Sync single reminder to Firestore.

        Args:
            reminder: CareReminder instance

        Returns:
            True if sync successful, False otherwise
        """
        if not cls.is_available():
            logger.debug("[FIREBASE] Firebase not available, skipping sync")
            return False

        db = get_firestore_client()
        if not db:
            logger.error("[FIREBASE] Failed to get Firestore client")
            return False

        try:
            # Serialize reminder
            data = cls._serialize_reminder(reminder)

            # Store in user's reminders subcollection
            user_id = str(reminder.user.id)
            reminder_id = str(reminder.id)

            doc_ref = db.collection(cls.COLLECTION_USER_REMINDERS).document(user_id) \
                        .collection('reminders').document(reminder_id)

            doc_ref.set(data)

            logger.info(
                f"[FIREBASE] Synced reminder {reminder.id} for user {user_id} "
                f"({reminder.reminder_type})"
            )
            return True

        except Exception as e:
            logger.error(f"[FIREBASE] Failed to sync reminder {reminder.id}: {str(e)}")
            return False

    @classmethod
    def delete_reminder(cls, reminder_id: int, user_id: int) -> bool:
        """
        Delete reminder from Firestore.

        Args:
            reminder_id: Reminder ID
            user_id: User ID

        Returns:
            True if deletion successful, False otherwise
        """
        if not cls.is_available():
            return False

        db = get_firestore_client()
        if not db:
            return False

        try:
            doc_ref = db.collection(cls.COLLECTION_USER_REMINDERS).document(str(user_id)) \
                        .collection('reminders').document(str(reminder_id))

            doc_ref.delete()

            logger.info(f"[FIREBASE] Deleted reminder {reminder_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[FIREBASE] Failed to delete reminder {reminder_id}: {str(e)}")
            return False

    @classmethod
    def sync_user_reminders(cls, user: User) -> Dict[str, int]:
        """
        Sync all reminders for a user (initial sync or recovery).

        Args:
            user: User instance

        Returns:
            Dict with:
            - synced: int (number synced)
            - failed: int (number failed)
        """
        if not cls.is_available():
            return {'synced': 0, 'failed': 0}

        reminders = CareReminder.objects.filter(user=user).select_related(
            'garden_plant__garden'
        )

        synced = 0
        failed = 0

        for reminder in reminders:
            if cls.sync_reminder(reminder):
                synced += 1
            else:
                failed += 1

        logger.info(
            f"[FIREBASE] Bulk sync for user {user.id}: "
            f"{synced} synced, {failed} failed"
        )

        return {'synced': synced, 'failed': failed}

    @classmethod
    def get_upcoming_reminders_firestore(
        cls,
        user: User,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming reminders from Firestore (for mobile app).

        Args:
            user: User instance
            limit: Maximum number of reminders to return

        Returns:
            List of reminder dicts
        """
        if not cls.is_available():
            return []

        db = get_firestore_client()
        if not db:
            return []

        try:
            user_id = str(user.id)
            now = datetime.now().isoformat()

            # Query upcoming incomplete reminders
            docs = db.collection(cls.COLLECTION_USER_REMINDERS).document(user_id) \
                     .collection('reminders') \
                     .where('completed', '==', False) \
                     .where('scheduled_date', '>=', now) \
                     .order_by('scheduled_date') \
                     .limit(limit) \
                     .stream()

            reminders = []
            for doc in docs:
                reminders.append(doc.to_dict())

            logger.info(
                f"[FIREBASE] Retrieved {len(reminders)} upcoming reminders "
                f"for user {user_id} from Firestore"
            )

            return reminders

        except Exception as e:
            logger.error(f"[FIREBASE] Failed to get upcoming reminders: {str(e)}")
            return []

    @classmethod
    def mark_notification_sent(cls, reminder_id: int, user_id: int) -> bool:
        """
        Mark reminder as notification sent in Firestore.

        Args:
            reminder_id: Reminder ID
            user_id: User ID

        Returns:
            True if update successful, False otherwise
        """
        if not cls.is_available():
            return False

        db = get_firestore_client()
        if not db:
            return False

        try:
            doc_ref = db.collection(cls.COLLECTION_USER_REMINDERS).document(str(user_id)) \
                        .collection('reminders').document(str(reminder_id))

            doc_ref.update({
                'notification_sent': True,
                'updated_at': datetime.now().isoformat()
            })

            logger.info(f"[FIREBASE] Marked notification sent for reminder {reminder_id}")
            return True

        except Exception as e:
            logger.error(f"[FIREBASE] Failed to mark notification sent: {str(e)}")
            return False

    @classmethod
    def cleanup_completed_reminders(cls, user: User, days_old: int = 30) -> int:
        """
        Clean up old completed reminders from Firestore.

        Args:
            user: User instance
            days_old: Delete reminders completed more than N days ago

        Returns:
            Number of reminders deleted
        """
        if not cls.is_available():
            return 0

        db = get_firestore_client()
        if not db:
            return 0

        try:
            from datetime import timedelta

            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            user_id = str(user.id)

            # Query old completed reminders
            docs = db.collection(cls.COLLECTION_USER_REMINDERS).document(user_id) \
                     .collection('reminders') \
                     .where('completed', '==', True) \
                     .where('completed_at', '<=', cutoff_date) \
                     .stream()

            deleted_count = 0
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1

            if deleted_count > 0:
                logger.info(
                    f"[FIREBASE] Cleaned up {deleted_count} old completed reminders "
                    f"for user {user_id}"
                )

            return deleted_count

        except Exception as e:
            logger.error(f"[FIREBASE] Failed to cleanup reminders: {str(e)}")
            return 0

    @classmethod
    def sync_reminder_batch(cls, reminders: List[CareReminder]) -> Dict[str, int]:
        """
        Sync batch of reminders efficiently.

        Args:
            reminders: List of CareReminder instances

        Returns:
            Dict with synced/failed counts
        """
        if not cls.is_available():
            return {'synced': 0, 'failed': 0}

        db = get_firestore_client()
        if not db:
            return {'synced': 0, 'failed': 0}

        synced = 0
        failed = 0

        try:
            # Use batch write for efficiency (max 500 operations per batch)
            batch = db.batch()
            operations = 0

            for reminder in reminders:
                if operations >= 500:
                    # Commit current batch
                    batch.commit()
                    logger.info(f"[FIREBASE] Committed batch of {operations} reminders")
                    batch = db.batch()
                    operations = 0

                try:
                    data = cls._serialize_reminder(reminder)
                    user_id = str(reminder.user.id)
                    reminder_id = str(reminder.id)

                    doc_ref = db.collection(cls.COLLECTION_USER_REMINDERS).document(user_id) \
                                .collection('reminders').document(reminder_id)

                    batch.set(doc_ref, data)
                    operations += 1
                    synced += 1

                except Exception as e:
                    logger.error(f"[FIREBASE] Failed to prepare reminder {reminder.id}: {str(e)}")
                    failed += 1

            # Commit final batch
            if operations > 0:
                batch.commit()
                logger.info(f"[FIREBASE] Committed final batch of {operations} reminders")

            logger.info(
                f"[FIREBASE] Batch sync complete: {synced} synced, {failed} failed"
            )

        except Exception as e:
            logger.error(f"[FIREBASE] Batch sync failed: {str(e)}")
            failed = len(reminders) - synced

        return {'synced': synced, 'failed': failed}
