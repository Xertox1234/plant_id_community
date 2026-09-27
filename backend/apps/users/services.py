"""
User services for trust level management and notifications.
"""

import json
import logging
from typing import Any, Dict, Optional

from apps.core.utils.pii_safe_logging import log_safe_email, log_safe_user_context
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .constants import (
    WEB_PUSH_GONE_STATUSES,
    WEB_PUSH_TIMEOUT_SECONDS,
    WEB_PUSH_TTL_SECONDS,
)

# External dependency for Web Push (requires: pip install pywebpush)
try:
    from pywebpush import WebPushException, webpush

    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    WebPushException = Exception

logger = logging.getLogger(__name__)


def vapid_claims_email() -> str:
    """The VAPID ``sub`` contact address without a ``mailto:`` prefix, or ""."""
    email = (getattr(settings, "VAPID_CLAIMS_EMAIL", "") or "").strip()
    if email.lower().startswith("mailto:"):
        email = email[len("mailto:") :].strip()
    return email


def web_push_enabled() -> bool:
    """True when the server can both hand out a key and sign a push."""
    return bool(
        getattr(settings, "VAPID_PUBLIC_KEY", "")
        and getattr(settings, "VAPID_PRIVATE_KEY", "")
        and vapid_claims_email()
    )


class NotificationService:
    """
    Service class for handling various types of notifications.
    """

    @staticmethod
    def send_web_push_notification(
        subscription,  # PushSubscription instance
        title: str,
        body: str,
        icon: str = "/icons/icon-192x192.png",
        badge: str = "/icons/badge-72x72.png",
        actions: Optional[list] = None,
        data: Optional[Dict[str, Any]] = None,
        tag: Optional[str] = None,
    ) -> bool:
        """
        Send a Web Push notification to a specific subscription.

        Args:
            subscription: PushSubscription instance
            title: Notification title
            body: Notification body text
            icon: Icon URL for the notification
            badge: Badge icon URL
            actions: List of action buttons
            data: Additional data to include
            tag: Notification tag for grouping/replacing

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not WEBPUSH_AVAILABLE:
            logger.error(
                "[PUSH] pywebpush library not available. Install with: pip install pywebpush"
            )
            return False

        try:
            # Prepare notification payload
            payload = {
                "title": title,
                "body": body,
                "icon": icon,
                "badge": badge,
                "tag": tag or "plant-community",
                "requireInteraction": True,
                "data": data or {},
                "actions": actions or [],
            }

            # Prepare subscription info for pywebpush
            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh_key,
                    "auth": subscription.auth_key,
                },
            }

            vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
            claims_email = vapid_claims_email()
            if not vapid_private_key or not claims_email:
                logger.error(
                    "[PUSH] VAPID_PRIVATE_KEY or VAPID_CLAIMS_EMAIL not configured"
                )
                return False

            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": f"mailto:{claims_email}"},
                content_encoding="aes128gcm",
                ttl=WEB_PUSH_TTL_SECONDS,
                timeout=WEB_PUSH_TIMEOUT_SECONDS,
            )

            # Mark subscription as used
            subscription.mark_as_used()

            logger.info(
                f"[PUSH] Push notification sent successfully to {log_safe_user_context(subscription.user)}"
            )
            return True

        except WebPushException as e:
            logger.error(
                f"[PUSH] WebPush error for {log_safe_user_context(subscription.user)}: {e}"
            )

            # `is not None`, never truthiness: requests.Response.__bool__ is
            # `.ok`, so an error response is falsy (PR #852 review).
            if (
                e.response is not None
                and e.response.status_code in WEB_PUSH_GONE_STATUSES
            ):
                subscription.deactivate()
                logger.warning(
                    f"[PUSH] Deactivated push subscription for {log_safe_user_context(subscription.user)}"
                )

            return False

        except Exception as e:
            logger.error(f"[PUSH] Unexpected error sending push notification: {e}")
            return False

    @staticmethod
    def send_care_reminder_push(reminder) -> bool:
        """
        Send a care reminder push notification to all user's active subscriptions.

        Args:
            reminder: CareReminder instance

        Returns:
            bool: True if sent to at least one subscription
        """
        if not reminder.user.care_reminder_notifications:
            logger.info(
                f"[REMINDER] Care reminder push disabled for {log_safe_user_context(reminder.user)}"
            )
            return False

        # Get all active push subscriptions for the user
        subscriptions = reminder.user.push_subscriptions.filter(is_active=True)

        if not subscriptions.exists():
            logger.info(
                f"[PUSH] No active push subscriptions for {log_safe_user_context(reminder.user)}"
            )
            return False

        # Prepare notification content
        plant_name = reminder.saved_care_instructions.display_name
        title = f"🌱 {reminder.title}"
        body = (
            f"Time to {reminder.get_reminder_type_display().lower()} your {plant_name}"
        )

        # Prepare action buttons
        actions = [
            {
                "action": "mark_completed",
                "title": "✅ Mark Completed",
                "icon": "/icons/check.png",
            },
            {
                "action": "snooze_reminder",
                "title": "⏰ Snooze 24h",
                "icon": "/icons/snooze.png",
            },
        ]

        # Prepare data for the notification
        data = {
            "type": "care_reminder",
            "reminder_id": str(reminder.uuid),
            "plant_name": plant_name,
            "reminder_type": reminder.reminder_type,
            "url": f"/profile/care-reminders/{reminder.uuid}/",
        }

        # Send to all active subscriptions
        success_count = 0
        for subscription in subscriptions:
            if NotificationService.send_web_push_notification(
                subscription=subscription,
                title=title,
                body=body,
                actions=actions,
                data=data,
                tag=f"care-reminder-{reminder.uuid}",
            ):
                success_count += 1

        # Log the reminder action (import here to avoid circular import)
        from .models import CareReminderLog

        CareReminderLog.objects.create(
            reminder=reminder,
            action="sent",
            action_data={
                "push_sent": success_count > 0,
                "subscriptions_attempted": subscriptions.count(),
                "subscriptions_successful": success_count,
            },
        )

        logger.info(
            f"[REMINDER] Care reminder sent to {success_count}/{subscriptions.count()} "
            f"subscriptions for {log_safe_user_context(reminder.user)}"
        )
        return success_count > 0

    @staticmethod
    def send_care_reminder_email(reminder) -> bool:
        """
        Send a care reminder email notification.

        Args:
            reminder: CareReminder instance

        Returns:
            bool: True if sent successfully
        """
        if not (
            reminder.user.care_reminder_email and reminder.user.email_notifications
        ):
            return False

        try:
            plant_name = reminder.saved_care_instructions.display_name

            # Prepare email content
            subject = f"🌱 Plant Care Reminder: {reminder.title}"

            context = {
                "user": reminder.user,
                "reminder": reminder,
                "plant_name": plant_name,
                "care_instructions": reminder.saved_care_instructions,
                "site_url": getattr(settings, "SITE_URL", "http://localhost:3000"),
            }

            # For now, create simple text content (templates can be added later)
            text_message = f"""
Hello {reminder.user.get_full_name() or reminder.user.username},

This is a reminder to {reminder.get_reminder_type_display().lower()} your {plant_name}.

Reminder Details:
- Type: {reminder.get_reminder_type_display()}
- Frequency: {reminder.get_frequency_display()}
- Plant: {plant_name}

You can manage your care reminders at: {context['site_url']}/profile/care-reminders/

Best regards,
The Plant Community Team
            """.strip()

            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reminder.user.email],
            )

            logger.info(
                f"[REMINDER] Care reminder email sent to {log_safe_email(reminder.user.email)}"
            )
            return True

        except Exception as e:
            logger.error(f"[REMINDER] Error sending care reminder email: {e}")
            return False

    @staticmethod
    def subscribe_to_push(
        user, subscription_data: Dict[str, Any], user_agent: str = ""
    ):
        """
        Create or update a push subscription for a user.

        Args:
            user: User instance
            subscription_data: Subscription data from the client
            user_agent: User agent string for device identification

        Returns:
            PushSubscription instance
        """
        from .models import PushSubscription

        endpoint = subscription_data.get("endpoint")
        keys = subscription_data.get("keys", {})

        # One browser endpoint belongs to one account: a shared browser where
        # another user subscribed last must not keep getting their
        # notifications (PR #852 review).
        released = (
            PushSubscription.objects.filter(endpoint=endpoint, is_active=True)
            .exclude(user=user)
            .update(is_active=False)
        )
        if released:
            logger.info(
                f"[PUSH] Released {released} subscription(s) on this endpoint "
                f"held by another account, for {log_safe_user_context(user)}"
            )

        subscription, created = PushSubscription.objects.update_or_create(
            user=user,
            endpoint=endpoint,
            defaults={
                "p256dh_key": keys.get("p256dh", ""),
                "auth_key": keys.get("auth", ""),
                "user_agent": user_agent,
                "device_name": NotificationService._extract_device_name(user_agent),
                "is_active": True,
            },
        )

        logger.info(
            f"[PUSH] Push subscription {'created' if created else 'updated'} for {log_safe_user_context(user)}"
        )
        return subscription

    @staticmethod
    def unsubscribe_from_push(user, endpoint: str) -> bool:
        """
        Deactivate a push subscription.

        Args:
            user: User instance
            endpoint: Subscription endpoint to deactivate

        Returns:
            bool: True if deactivated successfully
        """
        from .models import PushSubscription

        try:
            subscription = PushSubscription.objects.get(user=user, endpoint=endpoint)
            subscription.deactivate()
            logger.info(
                f"[PUSH] Push subscription deactivated for {log_safe_user_context(user)}"
            )
            return True
        except PushSubscription.DoesNotExist:
            logger.warning(
                f"[PUSH] Push subscription not found for {log_safe_user_context(user)} with endpoint {endpoint[:20]}..."
            )
            return False

    @staticmethod
    def _extract_device_name(user_agent: str) -> str:
        """
        Extract a human-readable device name from user agent string.

        Args:
            user_agent: User agent string

        Returns:
            str: Human-readable device name
        """
        if not user_agent:
            return "Unknown device"

        # Simple device detection (can be enhanced with a proper library)
        user_agent_lower = user_agent.lower()

        if "mobile" in user_agent_lower or "android" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Android"
            elif "firefox" in user_agent_lower:
                return "Firefox on Android"
            else:
                return "Mobile Browser"
        elif "iphone" in user_agent_lower or "ipad" in user_agent_lower:
            if "safari" in user_agent_lower:
                return "Safari on iOS"
            elif "chrome" in user_agent_lower:
                return "Chrome on iOS"
            else:
                return "iOS Browser"
        elif "windows" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Windows"
            elif "firefox" in user_agent_lower:
                return "Firefox on Windows"
            elif "edge" in user_agent_lower:
                return "Edge on Windows"
            else:
                return "Windows Browser"
        elif "mac" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Mac"
            elif "firefox" in user_agent_lower:
                return "Firefox on Mac"
            elif "safari" in user_agent_lower:
                return "Safari on Mac"
            else:
                return "Mac Browser"
        elif "linux" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Linux"
            elif "firefox" in user_agent_lower:
                return "Firefox on Linux"
            else:
                return "Linux Browser"
        else:
            return "Desktop Browser"


class CareReminderService:
    """
    Service class for managing care reminders.
    """

    @staticmethod
    def create_reminder(
        user,
        saved_care_instructions,
        reminder_type: str,
        frequency: str,
        custom_interval_days: Optional[int] = None,
        title: Optional[str] = None,
    ):
        """
        Create a new care reminder.

        Args:
            user: User instance
            saved_care_instructions: SavedCareInstructions instance
            reminder_type: Type of reminder (watering, fertilizing, etc.)
            frequency: How often to remind
            custom_interval_days: Custom interval for 'custom' frequency
            title: Custom title (auto-generated if not provided)

        Returns:
            CareReminder instance
        """
        from .models import CareReminder

        if not title:
            plant_name = saved_care_instructions.display_name
            type_display = dict(CareReminder.REMINDER_TYPES)[reminder_type]
            title = f"{type_display} for {plant_name}"

        # Calculate first reminder date
        from datetime import timedelta

        if frequency == "custom" and custom_interval_days:
            next_date = timezone.now() + timedelta(days=custom_interval_days)
        else:
            frequency_map = {
                "daily": timedelta(days=1),
                "weekly": timedelta(weeks=1),
                "biweekly": timedelta(weeks=2),
                "monthly": timedelta(days=30),
                "quarterly": timedelta(days=90),
                "biannual": timedelta(days=180),
                "annual": timedelta(days=365),
            }
            next_date = timezone.now() + frequency_map.get(
                frequency, timedelta(weeks=1)
            )

        reminder = CareReminder.objects.create(
            user=user,
            saved_care_instructions=saved_care_instructions,
            reminder_type=reminder_type,
            title=title,
            frequency=frequency,
            custom_interval_days=custom_interval_days,
            next_reminder_date=next_date,
            send_push_notification=user.care_reminder_notifications,
            send_email_notification=user.care_reminder_email,
        )

        logger.info(
            f"[REMINDER] Care reminder created for {log_safe_user_context(user)}: {title}"
        )
        return reminder

    @staticmethod
    def process_due_reminders():
        """
        Process all reminders that are due to be sent.
        This method should be called by a periodic task (Celery, cron, etc.).
        """
        from .models import CareReminder

        due_reminders = CareReminder.objects.filter(
            is_active=True, next_reminder_date__lte=timezone.now()
        ).select_related("user", "saved_care_instructions")

        sent_count = 0
        for reminder in due_reminders:
            try:
                reminder.send_reminder()
                sent_count += 1
            except Exception as e:
                logger.error(f"[REMINDER] Error sending reminder {reminder.id}: {e}")

        logger.info(f"[REMINDER] Processed {sent_count} care reminders")
        return sent_count
