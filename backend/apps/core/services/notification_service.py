"""
Notification service for routing and managing different types of notifications.

Handles routing notifications to appropriate channels (email, in-app, etc.)
and manages user preferences and notification scheduling.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from django.contrib.auth import get_user_model
from django.utils import timezone
from enum import Enum

from .email_service import EmailService, EmailType
from apps.core.utils.pii_safe_logging import log_safe_email, log_safe_user_context

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Available notification channels."""
    EMAIL = 'email'
    IN_APP = 'in_app'
    PUSH = 'push'  # For future implementation
    SMS = 'sms'    # For future implementation


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'


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
        schedule_for: Optional[timezone.datetime] = None
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
                notification_type, recipient, title, message,
                context, channels, priority, template_name, schedule_for
            )
        
        # Send through each channel
        for channel in channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = self._send_email_notification(
                        notification_type, recipient, title, message,
                        context, priority, template_name
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
        template_name: Optional[str]
    ) -> bool:
        """Send notification via email."""
        # Prepare email context
        email_context = context or {}
        email_context.update({
            'notification_message': message,
            'notification_title': subject,
        })
        
        # Use template name or derive from notification type
        template = template_name or self._get_email_template_for_type(notification_type)
        
        return self.email_service.send_email(
            email_type=notification_type,
            recipient=recipient,
            subject=subject,
            template_name=template,
            context=email_context,
            priority=priority.value
        )
    
    def _send_in_app_notification(
        self,
        notification_type: str,
        recipient: Union[str, User],
        title: str,
        message: str,
        context: Optional[Dict[str, Any]]
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
            logger.info(f"In-app notification sent to {log_safe_user_context(user)}: {title}")
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
        schedule_for: timezone.datetime
    ) -> Dict[str, bool]:
        """Schedule notification for later delivery."""
        # TODO: Implement proper scheduling with Celery or Django-RQ
        logger.warning(f"Scheduled notifications not yet implemented. Sending immediately instead.")
        
        # For now, send immediately instead of scheduling
        results = {}
        for channel in channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = self._send_email_notification(
                        notification_type, recipient, title, message,
                        context, priority, template_name
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
                logger.error(f"Failed to send scheduled notification via {channel}: {e}")
                results[channel.value] = False
        
        return results
    
    def _get_email_template_for_type(self, notification_type: str) -> str:
        """Get default email template name for notification type."""
        template_map = {
            EmailType.PLANT_CARE_REMINDER: 'plant_care_reminder',
            EmailType.DISEASE_ALERT: 'disease_alert',
            EmailType.SEASONAL_CARE: 'seasonal_care',
            EmailType.FORUM_REPLY: 'forum_reply',
            EmailType.FORUM_MENTION: 'forum_mention',
            EmailType.FORUM_DIGEST: 'forum_digest',
            EmailType.NEWSLETTER: 'newsletter',
            EmailType.BLOG_POST: 'blog_post',
            EmailType.PLANT_TIPS: 'plant_tips',
            EmailType.IDENTIFICATION_RESULT: 'identification_result',
            EmailType.COMMUNITY_UPDATE: 'community_update',
        }
        
        return template_map.get(notification_type, 'generic_notification')
    
    # Convenience methods for common notification types
    
    def send_plant_care_reminder(
        self,
        user: User,
        plant_name: str,
        care_type: str,
        care_instructions: str,
        care_data: Optional[Dict] = None
    ) -> bool:
        """Send a plant care reminder notification."""
        context = {
            'plant_name': plant_name,
            'care_type': care_type,
            'care_instructions': care_instructions,
            'care_data': care_data or {},
        }
        
        subject = f"Time to care for your {plant_name}"
        message = f"It's time to {care_type.lower()} your {plant_name}!"
        
        results = self.send_notification(
            notification_type=EmailType.PLANT_CARE_REMINDER,
            recipient=user,
            title=subject,
            message=message,
            context=context,
            channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP]
        )
        
        return results.get('email', False)
    
    def send_forum_reply_notification(
        self,
        user: User,
        topic_title: str,
        reply_author: str,
        reply_excerpt: str,
        topic_url: str
    ) -> bool:
        """Send forum reply notification."""
        context = {
            'topic_title': topic_title,
            'reply_author': reply_author,
            'reply_excerpt': reply_excerpt,
            'topic_url': topic_url,
        }
        
        subject = f"New reply in: {topic_title}"
        message = f"{reply_author} replied to a topic you're following"
        
        results = self.send_notification(
            notification_type=EmailType.FORUM_REPLY,
            recipient=user,
            title=subject,
            message=message,
            context=context
        )
        
        return results.get('email', False)
    
    def send_identification_result_notification(
        self,
        user: User,
        plant_name: str,
        confidence: float,
        identifier_name: str,
        result_url: str
    ) -> bool:
        """Send plant identification result notification."""
        context = {
            'plant_name': plant_name,
            'confidence': confidence,
            'confidence_percent': f"{confidence * 100:.1f}%",
            'identifier_name': identifier_name,
            'result_url': result_url,
        }
        
        subject = f"Your plant has been identified as {plant_name}"
        message = f"Great news! Your plant identification request has a new result."
        
        results = self.send_notification(
            notification_type=EmailType.IDENTIFICATION_RESULT,
            recipient=user,
            title=subject,
            message=message,
            context=context
        )
        
        return results.get('email', False)
    
    def send_newsletter(
        self,
        recipients: List[User],
        subject: str,
        content_items: List[Dict],
        newsletter_type: str = 'weekly'
    ) -> Dict[str, int]:
        """Send newsletter to multiple recipients."""
        def context_factory(user):
            return {
                'content_items': content_items,
                'newsletter_type': newsletter_type,
                'user_first_name': user.first_name or user.username,
            }
        
        return self.email_service.send_bulk_email(
            email_type=EmailType.NEWSLETTER,
            recipients=recipients,
            subject=subject,
            template_name='newsletter',
            context_factory=context_factory
        )
    
    def get_user_notification_preferences(self, user: User) -> Dict[str, Any]:
        """Get user's notification preferences."""
        return {
            'email_notifications': user.email_notifications,
            'plant_id_notifications': user.plant_id_notifications,
            'forum_notifications': user.forum_notifications,
            'care_reminder_email': user.care_reminder_email,
            'newsletter_subscribed': hasattr(user, 'newsletter_subscription'),
        }
    
    def update_user_notification_preferences(
        self,
        user: User,
        preferences: Dict[str, bool]
    ) -> bool:
        """Update user's notification preferences."""
        try:
            if 'email_notifications' in preferences:
                user.email_notifications = preferences['email_notifications']
            if 'plant_id_notifications' in preferences:
                user.plant_id_notifications = preferences['plant_id_notifications']
            if 'forum_notifications' in preferences:
                user.forum_notifications = preferences['forum_notifications']
            if 'care_reminder_email' in preferences:
                user.care_reminder_email = preferences['care_reminder_email']
            
            user.save()

            logger.info(f"Updated notification preferences for {log_safe_user_context(user)}")
            return True

        except Exception as e:
            logger.error(f"Failed to update preferences for {log_safe_user_context(user)}: {e}")
            return False
    
    def send_forum_mention_notification(
        self,
        mentioned_user: User,
        mentioning_user: User,
        topic_title: str,
        post_content_excerpt: str,
        topic_url: str
    ) -> bool:
        """Send notification when a user is mentioned in a forum post."""
        context = {
            'mentioned_user': mentioned_user,
            'mentioning_user': mentioning_user,
            'topic_title': topic_title,
            'post_content_excerpt': post_content_excerpt,
            'topic_url': topic_url,
        }
        
        subject = f"💬 {mentioning_user.username} mentioned you in: {topic_title}"
        message = f"{mentioning_user.username} mentioned you in a forum discussion"
        
        results = self.send_notification(
            notification_type=EmailType.FORUM_MENTION,
            recipient=mentioned_user,
            title=subject,
            message=message,
            context=context,
            channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
            priority=NotificationPriority.NORMAL
        )
        
        return results.get('email', False)
    
    def send_new_topic_notification(
        self,
        subscriber: User,
        author: User,
        topic_title: str,
        topic_excerpt: str,
        category_name: str,
        topic_url: str
    ) -> bool:
        """Send notification when a new topic is created in a subscribed category."""
        context = {
            'subscriber': subscriber,
            'author': author,
            'topic_title': topic_title,
            'topic_excerpt': topic_excerpt,
            'category_name': category_name,
            'topic_url': topic_url,
        }
        
        subject = f"🌱 New topic in {category_name}: {topic_title}"
        message = f"{author.username} started a new discussion in {category_name}"
        
        results = self.send_notification(
            notification_type=EmailType.FORUM_REPLY,
            recipient=subscriber,
            title=subject,
            message=message,
            context=context,
            template_name='new_forum_topic'
        )
        
        return results.get('email', False)
    
    def send_forum_digest_email(
        self,
        user: User,
        digest_period: str,
        top_topics: list,
        new_replies_count: int,
        mentions_count: int
    ) -> bool:
        """Send forum activity digest email."""
        context = {
            'user': user,
            'digest_period': digest_period,
            'top_topics': top_topics,
            'new_replies_count': new_replies_count,
            'mentions_count': mentions_count,
        }
        
        subject = f"🌿 Your {digest_period} Plant Community forum digest"
        message = f"Here's what happened in the forums this {digest_period.lower()}"
        
        results = self.send_notification(
            notification_type=EmailType.FORUM_DIGEST,
            recipient=user,
            title=subject,
            message=message,
            context=context,
            template_name='forum_digest'
        )
        
        return results.get('email', False)