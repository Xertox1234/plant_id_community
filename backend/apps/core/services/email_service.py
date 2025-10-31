"""
Central email service for the Plant Community application.

Provides a unified interface for sending emails with tracking, preferences,
and template rendering capabilities.
"""

import logging
from typing import Dict, List, Optional, Union, Any
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.utils.pii_safe_logging import log_safe_email, log_safe_user_context

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailType:
    """Email type constants for categorization and preferences."""
    
    # Plant care related emails
    PLANT_CARE_REMINDER = 'plant_care_reminder'
    DISEASE_ALERT = 'disease_alert' 
    SEASONAL_CARE = 'seasonal_care'
    
    # Forum related emails
    FORUM_REPLY = 'forum_reply'
    FORUM_MENTION = 'forum_mention'
    FORUM_DIGEST = 'forum_digest'
    
    # Newsletter and content
    NEWSLETTER = 'newsletter'
    BLOG_POST = 'blog_post'
    PLANT_TIPS = 'plant_tips'
    
    # System emails
    ACCOUNT_VERIFICATION = 'account_verification'
    PASSWORD_RESET = 'password_reset'
    SECURITY_ALERT = 'security_alert'
    
    # Community emails
    IDENTIFICATION_RESULT = 'identification_result'
    COMMUNITY_UPDATE = 'community_update'


class EmailService:
    """
    Central email service that handles all email sending with user preferences,
    tracking, and template rendering.
    """
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@plantcommunity.com')
        self.site_name = getattr(settings, 'SITE_NAME', 'Plant Community')
    
    def send_email(
        self,
        email_type: str,
        recipient: Union[str, User],
        subject: str,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
        from_email: Optional[str] = None,
        attachments: Optional[List] = None,
        priority: str = 'normal',
        track_opens: bool = True,
        respect_preferences: bool = True
    ) -> bool:
        """
        Send an email with full tracking and preference checking.
        
        Args:
            email_type: Type of email from EmailType constants
            recipient: Email address string or User instance
            subject: Email subject line
            template_name: Base name of email template (without .html/.txt)
            context: Template context variables
            from_email: Sender email (defaults to site default)
            attachments: List of file attachments
            priority: Email priority ('low', 'normal', 'high')
            track_opens: Whether to track email opens
            respect_preferences: Whether to check user preferences
            
        Returns:
            bool: True if email was sent successfully
        """
        # Normalize recipient
        if isinstance(recipient, User):
            user = recipient
            recipient_email = user.email
        else:
            recipient_email = recipient
            try:
                user = User.objects.get(email=recipient_email)
            except User.DoesNotExist:
                user = None
        
        # Check user preferences if requested
        if respect_preferences and user and not self._should_send_email(user, email_type):
            logger.info(f"Email {email_type} skipped for {log_safe_email(recipient_email)} due to user preferences")
            return False
        
        # Prepare context
        context = context or {}
        context.update(self._get_base_context(user, email_type))
        
        # Render email content
        try:
            html_content = render_to_string(f'emails/{template_name}.html', context)
            text_content = render_to_string(f'emails/{template_name}.txt', context)
        except TemplateDoesNotExist as e:
            logger.error(f"Email template not found: {template_name} - {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to render email template {template_name}: {e}")
            return False
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email or self.from_email,
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Add attachments
        if attachments:
            for attachment in attachments:
                email.attach(*attachment)
        
        # Send email
        try:
            email.send()
            
            # Track email sending
            self._track_email_sent(
                email_type=email_type,
                recipient_email=recipient_email,
                user=user,
                subject=subject,
                template_name=template_name,
                priority=priority
            )

            logger.info(f"Email {email_type} sent successfully to {log_safe_email(recipient_email)}")
            return True

        except ConnectionError as e:
            logger.error(f"Email connection failed for {email_type} to {log_safe_email(recipient_email)}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email {email_type} to {log_safe_email(recipient_email)}: {e}")
            return False
    
    def send_bulk_email(
        self,
        email_type: str,
        recipients: List[Union[str, User]],
        subject: str,
        template_name: str,
        context_factory: callable,
        **kwargs
    ) -> Dict[str, int]:
        """
        Send bulk emails with individual context for each recipient.
        
        Args:
            email_type: Type of email
            recipients: List of email addresses or User instances
            subject: Email subject line
            template_name: Email template name
            context_factory: Function that takes recipient and returns context
            **kwargs: Additional arguments passed to send_email
            
        Returns:
            Dict with 'sent' and 'failed' counts
        """
        results = {'sent': 0, 'failed': 0}
        
        for recipient in recipients:
            try:
                context = context_factory(recipient)
                if self.send_email(
                    email_type=email_type,
                    recipient=recipient,
                    subject=subject,
                    template_name=template_name,
                    context=context,
                    **kwargs
                ):
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                # recipient could be email or User object - handle both cases
                safe_recipient = log_safe_email(recipient) if isinstance(recipient, str) else log_safe_user_context(recipient)
                logger.error(f"Bulk email failed for recipient {safe_recipient}: {e}")
                results['failed'] += 1

        logger.info(f"Bulk email {email_type} completed: {results['sent']} sent, {results['failed']} failed")
        return results
    
    def _should_send_email(self, user: User, email_type: str) -> bool:
        """
        Check if user preferences allow sending this email type.
        
        Args:
            user: User instance
            email_type: Type of email to check
            
        Returns:
            bool: True if email should be sent
        """
        # Check master email toggle (using direct user model attributes)
        if not user.email_notifications:
            return False
        
        # Check specific email type preferences
        email_preference_map = {
            EmailType.PLANT_CARE_REMINDER: user.plant_id_notifications,
            EmailType.DISEASE_ALERT: user.plant_id_notifications,
            EmailType.SEASONAL_CARE: user.plant_id_notifications,
            EmailType.FORUM_REPLY: user.forum_notifications,
            EmailType.FORUM_MENTION: user.forum_notifications,
            EmailType.FORUM_DIGEST: user.forum_notifications,
            EmailType.IDENTIFICATION_RESULT: user.plant_id_notifications,
        }
        
        # System emails (security, verification) always send
        system_emails = {
            EmailType.ACCOUNT_VERIFICATION,
            EmailType.PASSWORD_RESET,
            EmailType.SECURITY_ALERT,
        }
        
        if email_type in system_emails:
            return True
        
        # Check specific preference or default to True
        return email_preference_map.get(email_type, True)
    
    def _get_base_context(self, user: Optional[User], email_type: str) -> Dict[str, Any]:
        """
        Get base context variables for all email templates.
        
        Args:
            user: User instance or None
            email_type: Type of email being sent
            
        Returns:
            Dict: Base context variables
        """
        site_url = getattr(settings, 'SITE_URL', 'https://plantcommunity.com')
        
        context = {
            'site_name': self.site_name,
            'site_url': site_url,
            'app_url': site_url,  # PWA-compatible URL (same as site_url for now)
            'user': user,
            'email_type': email_type,
            'current_year': timezone.now().year,
        }
        
        # Add unsubscribe URL if user exists
        if user:
            context['unsubscribe_url'] = self._generate_unsubscribe_url(user, email_type)
            context['preferences_url'] = self._generate_preferences_url(user)
        
        return context
    
    def _generate_unsubscribe_url(self, user: User, email_type: str) -> str:
        """Generate unsubscribe URL for user and email type."""
        try:
            unsubscribe_path = reverse('users:unsubscribe')
            return f"{getattr(settings, 'SITE_URL', 'https://plantcommunity.com')}{unsubscribe_path}?user={user.uuid}&type={email_type}"
        except Exception:
            # Fallback if reverse fails
            return f"{getattr(settings, 'SITE_URL', 'https://plantcommunity.com')}/api/auth/unsubscribe/?user={user.uuid}&type={email_type}"
    
    def _generate_preferences_url(self, user: User) -> str:
        """Generate email preferences URL for user."""
        try:
            preferences_path = reverse('users:email_preferences')
            site_url = getattr(settings, 'SITE_URL', 'https://plantcommunity.com')
            return f"{site_url}#!/settings/email-preferences"  # PWA route
        except Exception:
            # Fallback if reverse fails
            site_url = getattr(settings, 'SITE_URL', 'https://plantcommunity.com')
            return f"{site_url}#!/settings"
    
    def _track_email_sent(
        self,
        email_type: str,
        recipient_email: str,
        user: Optional[User],
        subject: str,
        template_name: str,
        priority: str
    ):
        """
        Track email sending for analytics and debugging.
        """
        # Import here to avoid circular imports
        try:
            from apps.core.models import EmailNotification
            EmailNotification.objects.create(
                email_type=email_type,
                recipient_email=recipient_email,
                user=user,
                subject=subject,
                template_name=template_name,
                priority=priority,
                sent_at=timezone.now(),
                status=EmailNotification.STATUS_SENT
            )
        except (ImportError, Exception) as e:
            # Log but don't fail email sending if tracking fails
            logger.warning(f"Failed to track email: {e}")
    
    def send_transactional_email(
        self,
        recipient: Union[str, User],
        subject: str,
        message: str,
        html_message: Optional[str] = None
    ) -> bool:
        """
        Send a simple transactional email without templates.
        
        Args:
            recipient: Email address or User instance
            subject: Email subject
            message: Plain text message
            html_message: Optional HTML message
            
        Returns:
            bool: True if sent successfully
        """
        if isinstance(recipient, User):
            recipient_email = recipient.email
        else:
            recipient_email = recipient
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                html_message=html_message
            )
            logger.info(f"Transactional email sent to {log_safe_email(recipient_email)}")
            return True
        except Exception as e:
            logger.error(f"Failed to send transactional email to {log_safe_email(recipient_email)}: {e}")
            return False
    
    def send_welcome_email(self, user: User) -> bool:
        """
        Send welcome email to newly verified users.
        
        Args:
            user: User instance who just verified their email
            
        Returns:
            bool: True if email was sent successfully
        """
        context = {
            'user': user,
            'user_first_name': user.first_name or user.username,
        }
        
        return self.send_email(
            email_type=EmailType.ACCOUNT_VERIFICATION,
            recipient=user,
            subject=f"🎉 Welcome to Plant Community, {user.first_name or user.username}!",
            template_name='welcome_email',
            context=context,
            priority='high',
            respect_preferences=False  # Welcome emails should always be sent
        )