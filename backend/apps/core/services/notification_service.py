"""
Notification service for routing and managing different types of notifications.

Handles routing notifications to appropriate channels (email, in-app, etc.)
and manages user preferences and notification scheduling.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from apps.core.utils.pii_safe_logging import log_safe_email, log_safe_user_context
from django.contrib.auth import get_user_model
from django.utils import timezone

from .email_service import EmailService, EmailType

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Available notification channels."""

    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"  # For future implementation
    SMS = "sms"  # For future implementation


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationService:
    """
    Central service for managing all types of notifications across different channels.
    """

    def __init__(self):
        self.email_service = EmailService()

    def send_notification(
        self,
        notification_type: str,
        recipient: Union[str, User],
        title: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        template_name: Optional[str] = None,
        schedule_for: Optional[timezone.datetime] = None,
    ) -> Dict[str, bool]:
        """
        Send a notification through specified channels.

        Args:
            notification_type: Type of notification (from EmailType or custom)
            recipient: User instance or email address
            title: Notification title/subject
            message: Notification message
            context: Additional context for templates
            channels: List of channels to send through
            priority: Notification priority
            template_name: Email template name (if different from type)
            schedule_for: When to send (None for immediate)

        Returns:
            Dict mapping channel names to success status
        """
        if channels is None:
            channels = [NotificationChannel.EMAIL]

        results = {}

        # If scheduled, queue for later (we'll implement this with Celery tasks)
        if schedule_for and schedule_for > timezone.now():
            return self._schedule_notification(
                notification_type,
                recipient,
                title,
                message,
                context,
                channels,
                priority,
                template_name,
                schedule_for,
            )

        # Send through each channel
        for channel in channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = self._send_email_notification(
                        notification_type,
                        recipient,
                        title,
                        message,
                        context,
                        priority,
                        template_name,
                    )
                elif channel == NotificationChannel.IN_APP:
                    success = self._send_in_app_notification(
                        notification_type, recipient, title, message, context
                    )
                else:
                    logger.warning(f"Channel {channel} not implemented yet")
                    success = False

                results[channel.value] = success

            except Exception as e:
                logger.error(f"Failed to send notification via {channel}: {e}")
                results[channel.value] = False

        return results

    def _send_email_notification(
        self,
        notification_type: str,
        recipient: Union[str, User],
        subject: str,
        message: str,
        context: Optional[Dict[str, Any]],
        priority: NotificationPriority,
        template_name: Optional[str],
    ) -> bool:
        """Send notification via email."""
        # Prepare email context
        email_context = context or {}
        email_context.update(
            {
                "notification_message": message,
                "notification_title": subject,
            }
        )

        # Use template name or derive from notification type
        template = template_name or self._get_email_template_for_type(notification_type)

        return self.email_service.send_email(
            email_type=notification_type,
            recipient=recipient,
            subject=subject,
            template_name=template,
            context=email_context,
            priority=priority.value,
        )

    def _send_in_app_notification(
        self,
        notification_type: str,
        recipient: Union[str, User],
        title: str,
        message: str,
        context: Optional[Dict[str, Any]],
    ) -> bool:
        """Send in-app notification (to be implemented with WebSocket or database)."""
        # Get user instance
        if isinstance(recipient, str):
            try:
                user = User.objects.get(email=recipient)
            except User.DoesNotExist:
                logger.error(f"User not found for email: {log_safe_email(recipient)}")
                return False
        else:
            user = recipient

        # Create in-app notification record
        try:
            # This will be implemented when we add the InAppNotification model
            logger.info(
                f"In-app notification sent to {log_safe_user_context(user)}: {title}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")
            return False

    def _schedule_notification(
        self,
        notification_type: str,
        recipient: Union[str, User],
        title: str,
        message: str,
        context: Optional[Dict[str, Any]],
        channels: List[NotificationChannel],
        priority: NotificationPriority,
        template_name: Optional[str],
        schedule_for: timezone.datetime,
    ) -> Dict[str, bool]:
        """Schedule notification for later delivery."""
        # TODO: Implement proper scheduling with Celery or Django-RQ
        logger.warning(
            "Scheduled notifications not yet implemented. Sending immediately instead."
        )

        # For now, send immediately instead of scheduling
        results = {}
        for channel in channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = self._send_email_notification(
                        notification_type,
                        recipient,
                        title,
                        message,
                        context,
                        priority,
                        template_name,
                    )
                elif channel == NotificationChannel.IN_APP:
                    success = self._send_in_app_notification(
                        notification_type, recipient, title, message, context
                    )
                else:
                    logger.warning(f"Channel {channel} not implemented yet")
                    success = False

                results[channel.value] = success

            except Exception as e:
                logger.error(
                    f"Failed to send scheduled notification via {channel}: {e}"
                )
                results[channel.value] = False

        return results

    def _get_email_template_for_type(self, notification_type: str) -> str:
        """Get default email template name for notification type."""
        template_map = {
            EmailType.PLANT_CARE_REMINDER: "plant_care_reminder",
            EmailType.DISEASE_ALERT: "disease_alert",
            EmailType.SEASONAL_CARE: "seasonal_care",
            EmailType.FORUM_REPLY: "forum_reply",
            EmailType.FORUM_MENTION: "forum_mention",
            EmailType.FORUM_DIGEST: "forum_digest",
            EmailType.NEWSLETTER: "newsletter",
            EmailType.BLOG_POST: "blog_post",
            EmailType.PLANT_TIPS: "plant_tips",
            EmailType.IDENTIFICATION_RESULT: "identification_result",
            EmailType.COMMUNITY_UPDATE: "community_update",
        }

        return template_map.get(notification_type, "generic_notification")

    # Convenience methods for common notification types

    def send_plant_care_reminder(
        self,
        user: User,
        plant_name: str,
        care_type: str,
        care_instructions: str,
        care_data: Optional[Dict] = None,
    ) -> bool:
        """Send a plant care reminder notification."""
        context = {
            "plant_name": plant_name,
            "care_type": care_type,
            "care_instructions": care_instructions,
            "care_data": care_data or {},
        }

        subject = f"Time to care for your {plant_name}"
        message = f"It's time to {care_type.lower()} your {plant_name}!"

        results = self.send_notification(
            notification_type=EmailType.PLANT_CARE_REMINDER,
            recipient=user,
            title=subject,
            message=message,
            context=context,
            channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        )

        return results.get("email", False)

    def send_forum_reply_notification(
        self,
        user: User,
        topic_title: str,
        reply_author: str,
        reply_excerpt: str,
        topic_url: str,
    ) -> bool:
        """Send forum reply notification.

        THE WORDING IS NOT HERE (todo 287). Subject and body come from
        ``apps/forum_host/notification_copy.py``, which both backend surfaces
        read — this email path and the FCM tray
        (``apps/forum_host/tasks.py::_notification_content``). Edit copy there.
        The import is function-level and one-directional on purpose: this
        service is NOT forum-specific (it also serves plant-care reminders,
        identification results and newsletters), so the forum owns its copy and
        this reads it, never the reverse.

        This is the ONLY live forum email path — it is called from
        ``apps/forum_host/tasks.py`` (see ``notifications.py``'s slice-2 note).
        Its three ``send_forum_*`` siblings (mention / new-topic / digest) were
        deleted with todo 287: they had zero call sites repo-wide, so their
        emoji-bearing copy was never shipped behavior and folding it into the
        copy table would have enshrined wording no user has seen (docs/
        LEARNINGS.md 2026-07-29, todo 270 — a resolving citation is not a
        verified claim).
        """
        from apps.forum_host.notification_copy import email_content

        # Keys must match the template vars in emails/forum_reply.{html,txt}
        # (author_name/post_excerpt), not these parameter names — Django
        # silently renders an undefined var as '', so a mismatch here ships
        # a blank-author, blank-excerpt email instead of erroring.
        context = {
            "topic_title": topic_title,
            "author_name": reply_author,
            "post_excerpt": reply_excerpt,
            "topic_url": topic_url,
        }

        copy = email_content("reply_added", topic_title=topic_title, actor=reply_author)
        if copy is None:
            # Unreachable while the table carries a reply_added email arm, but
            # NOT merely defensive: send_forum_email_batch's retry config is
            # justified by "the send loop can never raise" (see its docstring),
            # and an unpacking TypeError here would abort the batch mid-loop,
            # silently skipping every remaining recipient with no retry.
            logger.error("[EMAIL] No forum email copy for 'reply_added'; skipping send")
            return False
        subject, message = copy

        results = self.send_notification(
            notification_type=EmailType.FORUM_REPLY,
            recipient=user,
            title=subject,
            message=message,
            context=context,
        )

        return results.get("email", False)

    def send_identification_result_notification(
        self,
        user: User,
        plant_name: str,
        confidence: float,
        identifier_name: str,
        result_url: str,
    ) -> bool:
        """Send plant identification result notification."""
        context = {
            "plant_name": plant_name,
            "confidence": confidence,
            "confidence_percent": f"{confidence * 100:.1f}%",
            "identifier_name": identifier_name,
            "result_url": result_url,
        }

        subject = f"Your plant has been identified as {plant_name}"
        message = "Great news! Your plant identification request has a new result."

        results = self.send_notification(
            notification_type=EmailType.IDENTIFICATION_RESULT,
            recipient=user,
            title=subject,
            message=message,
            context=context,
        )

        return results.get("email", False)

    def send_newsletter(
        self,
        recipients: List[User],
        subject: str,
        content_items: List[Dict],
        newsletter_type: str = "weekly",
    ) -> Dict[str, int]:
        """Send newsletter to multiple recipients."""

        def context_factory(user):
            return {
                "content_items": content_items,
                "newsletter_type": newsletter_type,
                "user_first_name": user.first_name or user.username,
            }

        return self.email_service.send_bulk_email(
            email_type=EmailType.NEWSLETTER,
            recipients=recipients,
            subject=subject,
            template_name="newsletter",
            context_factory=context_factory,
        )

    def get_user_notification_preferences(self, user: User) -> Dict[str, Any]:
        """Get user's notification preferences."""
        return {
            "email_notifications": user.email_notifications,
            "plant_id_notifications": user.plant_id_notifications,
            "forum_notifications": user.forum_notifications,
            "care_reminder_email": user.care_reminder_email,
            "newsletter_subscribed": hasattr(user, "newsletter_subscription"),
        }

    def update_user_notification_preferences(
        self, user: User, preferences: Dict[str, bool]
    ) -> bool:
        """Update user's notification preferences."""
        try:
            if "email_notifications" in preferences:
                user.email_notifications = preferences["email_notifications"]
            if "plant_id_notifications" in preferences:
                user.plant_id_notifications = preferences["plant_id_notifications"]
            if "forum_notifications" in preferences:
                user.forum_notifications = preferences["forum_notifications"]
            if "care_reminder_email" in preferences:
                user.care_reminder_email = preferences["care_reminder_email"]

            user.save()

            logger.info(
                f"Updated notification preferences for {log_safe_user_context(user)}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to update preferences for {log_safe_user_context(user)}: {e}"
            )
            return False
