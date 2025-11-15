"""
Firebase Notification Service

Push notification delivery via Firebase Cloud Messaging.

Provides:
- Care reminder notifications
- Weather alert notifications
- Batch notification sending
- Device token management
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model

from ..models import CareReminder
from ..firebase_config import get_fcm_client, is_firebase_available

logger = logging.getLogger(__name__)

User = get_user_model()


class FirebaseNotificationService:
    """
    Firebase Cloud Messaging notification service.

    Sends push notifications for:
    - Care reminders (watering, fertilizing, etc.)
    - Weather alerts (frost, heatwave)
    - Task deadlines
    - Pest issue updates
    """

    @classmethod
    def is_available(cls) -> bool:
        """Check if FCM is available."""
        return is_firebase_available()

    @classmethod
    def send_reminder_notification(
        cls,
        reminder: CareReminder,
        device_token: str
    ) -> bool:
        """
        Send push notification for a care reminder.

        Args:
            reminder: CareReminder instance
            device_token: FCM device token

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not cls.is_available():
            logger.debug("[FCM] Firebase not available, skipping notification")
            return False

        fcm = get_fcm_client()
        if not fcm:
            logger.error("[FCM] Failed to get FCM client")
            return False

        try:
            # Build notification payload
            reminder_type = reminder.get_reminder_type_display()
            plant_name = reminder.garden_plant.common_name

            title = f"{reminder_type} Reminder"
            body = f"Time to {reminder_type.lower()} your {plant_name}"

            if reminder.custom_type_name:
                title = f"{reminder.custom_type_name} Reminder"
                body = f"{reminder.custom_type_name} for {plant_name}"

            # Create message
            message = fcm.Message(
                notification=fcm.Notification(
                    title=title,
                    body=body
                ),
                data={
                    'type': 'care_reminder',
                    'reminder_id': str(reminder.id),
                    'reminder_type': reminder.reminder_type,
                    'plant_id': str(reminder.garden_plant.id),
                    'plant_name': plant_name,
                    'garden_id': str(reminder.garden_plant.garden.id),
                    'scheduled_date': reminder.scheduled_date.isoformat()
                },
                token=device_token,
                android=fcm.AndroidConfig(
                    priority='high',
                    notification=fcm.AndroidNotification(
                        icon='ic_notification',
                        color='#4CAF50',  # Green for garden app
                        sound='default'
                    )
                ),
                apns=fcm.APNSConfig(
                    payload=fcm.APNSPayload(
                        aps=fcm.Aps(
                            sound='default',
                            badge=1
                        )
                    )
                )
            )

            # Send message
            response = fcm.send(message)

            logger.info(
                f"[FCM] Sent reminder notification for {plant_name} "
                f"(reminder {reminder.id}): {response}"
            )

            # Mark notification as sent
            reminder.notification_sent = True
            reminder.save(update_fields=['notification_sent'])

            return True

        except Exception as e:
            logger.error(f"[FCM] Failed to send reminder notification: {str(e)}")
            return False

    @classmethod
    def send_weather_alert(
        cls,
        user: User,
        device_token: str,
        alert_type: str,
        alert_data: Dict[str, Any]
    ) -> bool:
        """
        Send weather alert notification.

        Args:
            user: User instance
            device_token: FCM device token
            alert_type: 'frost' or 'heatwave'
            alert_data: Weather alert details

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not cls.is_available():
            return False

        fcm = get_fcm_client()
        if not fcm:
            return False

        try:
            # Build notification payload based on alert type
            if alert_type == 'frost':
                title = "⚠️ Frost Warning"
                date = alert_data.get('frost_date', 'soon')
                temp = alert_data.get('temp_min', 'below freezing')
                body = f"Frost expected {date} ({temp}°F). Protect sensitive plants."

            elif alert_type == 'heatwave':
                title = "🔥 Heat Warning"
                date = alert_data.get('heat_date', 'soon')
                temp = alert_data.get('temp_max', 'very high')
                body = f"Extreme heat expected {date} ({temp}°F). Water frequently and provide shade."

            else:
                logger.warning(f"[FCM] Unknown alert type: {alert_type}")
                return False

            # Create message
            message = fcm.Message(
                notification=fcm.Notification(
                    title=title,
                    body=body
                ),
                data={
                    'type': 'weather_alert',
                    'alert_type': alert_type,
                    **{k: str(v) for k, v in alert_data.items()}
                },
                token=device_token,
                android=fcm.AndroidConfig(
                    priority='high',
                    notification=fcm.AndroidNotification(
                        icon='ic_notification',
                        color='#FF9800',  # Orange for warnings
                        sound='default'
                    )
                ),
                apns=fcm.APNSConfig(
                    payload=fcm.APNSPayload(
                        aps=fcm.Aps(
                            sound='default',
                            badge=1
                        )
                    )
                )
            )

            # Send message
            response = fcm.send(message)

            logger.info(f"[FCM] Sent weather alert ({alert_type}) to user {user.id}: {response}")
            return True

        except Exception as e:
            logger.error(f"[FCM] Failed to send weather alert: {str(e)}")
            return False

    @classmethod
    def send_batch_reminders(
        cls,
        reminders: List[CareReminder],
        device_tokens: Dict[int, str]
    ) -> Dict[str, int]:
        """
        Send batch of reminder notifications.

        Args:
            reminders: List of CareReminder instances
            device_tokens: Dict mapping user_id to device_token

        Returns:
            Dict with:
            - sent: int (number sent)
            - failed: int (number failed)
        """
        if not cls.is_available():
            return {'sent': 0, 'failed': 0}

        sent = 0
        failed = 0

        for reminder in reminders:
            user_id = reminder.user.id
            device_token = device_tokens.get(user_id)

            if not device_token:
                logger.warning(f"[FCM] No device token for user {user_id}")
                failed += 1
                continue

            if cls.send_reminder_notification(reminder, device_token):
                sent += 1
            else:
                failed += 1

        logger.info(f"[FCM] Batch notification: {sent} sent, {failed} failed")

        return {'sent': sent, 'failed': failed}

    @classmethod
    def send_upcoming_reminders(
        cls,
        hours_ahead: int = 1
    ) -> Dict[str, int]:
        """
        Send notifications for upcoming reminders (cron job).

        Args:
            hours_ahead: Send notifications N hours before scheduled time

        Returns:
            Dict with sent/failed counts
        """
        from ..constants import REMINDER_NOTIFICATION_LEAD_TIME

        # Calculate time window
        now = datetime.now()
        window_start = now + timedelta(minutes=REMINDER_NOTIFICATION_LEAD_TIME - 5)
        window_end = now + timedelta(minutes=REMINDER_NOTIFICATION_LEAD_TIME + 5)

        # Get reminders in window
        reminders = CareReminder.objects.filter(
            scheduled_date__gte=window_start,
            scheduled_date__lte=window_end,
            completed=False,
            skipped=False,
            notification_sent=False
        ).select_related('user', 'garden_plant__garden')

        # Get device tokens (would come from UserProfile model)
        # For now, this is a placeholder - actual implementation would query UserProfile
        device_tokens = cls._get_device_tokens([r.user.id for r in reminders])

        # Send batch
        result = cls.send_batch_reminders(list(reminders), device_tokens)

        logger.info(
            f"[FCM] Sent {result['sent']} upcoming reminder notifications "
            f"({window_start} to {window_end})"
        )

        return result

    @classmethod
    def _get_device_tokens(cls, user_ids: List[int]) -> Dict[int, str]:
        """
        Get device tokens for users.

        Args:
            user_ids: List of user IDs

        Returns:
            Dict mapping user_id to device_token

        NOTE: This would query a UserProfile or DeviceToken model in production.
        Placeholder implementation for now.
        """
        # TODO: Implement actual device token storage/retrieval
        # from apps.users.models import UserProfile
        # tokens = UserProfile.objects.filter(
        #     user_id__in=user_ids,
        #     fcm_device_token__isnull=False
        # ).values_list('user_id', 'fcm_device_token')
        # return dict(tokens)

        logger.warning("[FCM] Device token retrieval not implemented yet")
        return {}

    @classmethod
    def send_test_notification(
        cls,
        device_token: str,
        title: str = "Test Notification",
        body: str = "This is a test notification from Garden Planner"
    ) -> bool:
        """
        Send test notification (for debugging/setup).

        Args:
            device_token: FCM device token
            title: Notification title
            body: Notification body

        Returns:
            True if sent successfully, False otherwise
        """
        if not cls.is_available():
            return False

        fcm = get_fcm_client()
        if not fcm:
            return False

        try:
            message = fcm.Message(
                notification=fcm.Notification(
                    title=title,
                    body=body
                ),
                data={
                    'type': 'test',
                    'timestamp': datetime.now().isoformat()
                },
                token=device_token
            )

            response = fcm.send(message)
            logger.info(f"[FCM] Sent test notification: {response}")
            return True

        except Exception as e:
            logger.error(f"[FCM] Failed to send test notification: {str(e)}")
            return False

    @classmethod
    def subscribe_to_topic(
        cls,
        device_token: str,
        topic: str
    ) -> bool:
        """
        Subscribe device to a topic (for broadcast notifications).

        Args:
            device_token: FCM device token
            topic: Topic name (e.g., 'weather_alerts', 'frost_warnings')

        Returns:
            True if subscription successful, False otherwise
        """
        if not cls.is_available():
            return False

        fcm = get_fcm_client()
        if not fcm:
            return False

        try:
            response = fcm.subscribe_to_topic([device_token], topic)
            logger.info(f"[FCM] Subscribed to topic '{topic}': {response}")
            return True

        except Exception as e:
            logger.error(f"[FCM] Failed to subscribe to topic: {str(e)}")
            return False

    @classmethod
    def send_topic_notification(
        cls,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Send notification to all devices subscribed to a topic.

        Args:
            topic: Topic name
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            True if sent successfully, False otherwise
        """
        if not cls.is_available():
            return False

        fcm = get_fcm_client()
        if not fcm:
            return False

        try:
            message = fcm.Message(
                notification=fcm.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                topic=topic
            )

            response = fcm.send(message)
            logger.info(f"[FCM] Sent topic notification to '{topic}': {response}")
            return True

        except Exception as e:
            logger.error(f"[FCM] Failed to send topic notification: {str(e)}")
            return False
