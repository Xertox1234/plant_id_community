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

from .email_service import EmailOutcome, EmailService, EmailType

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
                    logger.warning(f"[NOTIFY] Channel {channel} not implemented yet")
                    success = False

                results[channel.value] = success

            except Warning:
                # A RemovedInDjango70Warning is an error under pytest.ini (todo
                # 364) and Warning subclasses Exception: never log it as a
                # failed send (todos 454, 537).
                raise
            except Exception as e:
                logger.error(f"[NOTIFY] Failed to send notification via {channel}: {e}")
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
                logger.error(
                    f"[NOTIFY] User not found for email: {log_safe_email(recipient)}"
                )
                return False
        else:
            user = recipient

        # Create in-app notification record
        try:
            # This will be implemented when we add the InAppNotification model
            logger.info(
                f"[NOTIFY] In-app notification sent to {log_safe_user_context(user)}: {title}"
            )
            return True
        except Exception as e:
            logger.error(f"[NOTIFY] Failed to create in-app notification: {e}")
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
            "[NOTIFY] Scheduled notifications not yet implemented. Sending immediately instead."
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
                    logger.warning(f"[NOTIFY] Channel {channel} not implemented yet")
                    success = False

                results[channel.value] = success

            except Warning:
                # As in send_notification (todos 454, 537).
                raise
            except Exception as e:
                logger.error(
                    f"[NOTIFY] Failed to send scheduled notification via {channel}: {e}"
                )
                results[channel.value] = False

        return results

    def _get_email_template_for_type(self, notification_type: str) -> str:
        """Get default email template name for notification type."""
        template_map = {
            EmailType.DISEASE_ALERT: "disease_alert",
            EmailType.FORUM_REPLY: "forum_reply",
            EmailType.FORUM_MENTION: "forum_mention",
            EmailType.FORUM_DIGEST: "forum_digest",
            EmailType.BLOG_POST: "blog_post",
            EmailType.PLANT_TIPS: "plant_tips",
            EmailType.IDENTIFICATION_RESULT: "identification_result",
            EmailType.COMMUNITY_UPDATE: "community_update",
        }

        return template_map.get(notification_type, "generic_notification")

    # Convenience methods for common notification types

    def send_forum_reply_notification(
        self,
        user: User,
        topic_title: str,
        reply_author: str,
        reply_excerpt: str,
        topic_url: str,
        post_url: Optional[str] = None,
        count: int = 1,
    ) -> bool:
        """Send forum reply notification.

        ``count`` > 1 is a coalesced send (todo 624): that many replies on
        the topic in one message, the excerpt and author being the newest.

        ``post_url`` is the reply's own link (the topic at ``#post-<id>``);
        the email's main button opens it and falls back to ``topic_url``
        (todo 622).

        THE WORDING IS NOT HERE (todo 287). Subject and body come from
        ``apps/forum_host/notification_copy.py``, which both backend surfaces
        read — this email path and the FCM tray
        (``apps/forum_host/tasks.py::_notification_content``). Edit copy there.
        The import is function-level and one-directional on purpose: this
        service is NOT forum-specific (it also serves identification results
        and newsletters), so the forum owns its copy and
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
            "post_url": post_url or topic_url,
            "reply_count": count,
        }

        copy = email_content(
            "reply_added", topic_title=topic_title, actor=reply_author, count=count
        )
        if copy is None:
            # Unreachable while the table carries a reply_added email arm, but
            # NOT merely defensive: send_forum_email_batch's retry config is
            # justified by "a send failure never raises" (see its docstring),
            # and an unpacking TypeError here would abort the batch mid-loop,
            # silently skipping every remaining recipient with no retry.
            logger.error("[EMAIL] No forum email copy for 'reply_added'; skipping send")
            # Never reached send_email: say why, or the outbox would read the
            # unset outcome as a transport failure and retry it (todo 652).
            self.email_service.last_outcome = EmailOutcome.PERMANENT
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

    def send_forum_event_notification(
        self,
        user: User,
        event: str,
        topic_title: str,
        actor_name: str,
        post_excerpt: str,
        topic_url: str,
        post_url: Optional[str] = None,
        author_name: Optional[str] = None,
    ) -> bool:
        """Send the optional important-event email (todo 624): a mention, a
        quote of the member's post, or their answer accepted. Off unless the
        member turned that cell on (``wagtail_forum.preferences``); the
        caller (``send_forum_email_batch``) checks it, and this email's
        signed unsubscribe link turns off exactly that cell.

        Wording comes from ``apps/forum_host/notification_copy.py``, like the
        reply email's. ``actor_name`` is who did it (for an accepted answer,
        the acceptor) and goes in the event line; ``author_name`` labels the
        excerpt and defaults to ``actor_name``. Returns False, never raises, for an event with no
        email arm (``send_forum_email_batch``'s retry safety relies on it).
        """
        from apps.forum_host.notification_copy import email_content

        email_type = {
            "mention": EmailType.FORUM_MENTION,
            "quote": EmailType.FORUM_QUOTE,
            "answer_accepted": EmailType.FORUM_SOLUTION,
        }.get(str(event))
        copy = email_content(str(event), topic_title=topic_title, actor=actor_name)
        if email_type is None or copy is None:
            logger.error("[EMAIL] No forum email arm for %r; skipping send", event)
            self.email_service.last_outcome = EmailOutcome.PERMANENT  # todo 652
            return False
        subject, message = copy
        context = {
            "topic_title": topic_title,
            "author_name": actor_name if author_name is None else author_name,
            "post_excerpt": post_excerpt,
            "topic_url": topic_url,
            "post_url": post_url or topic_url,
            "event_line": message,
        }
        results = self.send_notification(
            notification_type=email_type,
            recipient=user,
            title=subject,
            message=message,
            context=context,
            template_name="forum_event",
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
