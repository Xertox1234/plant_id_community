"""
Django signals for user-related events.

Handles email notifications for user authentication events like 
email verification, password resets, and profile updates.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from allauth.account.signals import email_confirmed, user_signed_up
from apps.core.services.email_service import EmailService

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(email_confirmed)
def send_welcome_email_on_verification(sender, request, email_address, **kwargs):
    """
    Send welcome email when user verifies their email address.
    
    This is triggered after successful email verification via Allauth.
    """
    try:
        user = email_address.user
        email_service = EmailService()
        
        # Send welcome email
        success = email_service.send_welcome_email(user)
        
        if success:
            logger.info(f"Welcome email sent to {user.username} ({email_address.email})")
        else:
            logger.error(f"Failed to send welcome email to {user.username}")
            
    except Exception as e:
        logger.error(f"Error sending welcome email: {e}")


@receiver(user_signed_up)
def handle_user_signup(sender, request, user, **kwargs):
    """
    Handle post-signup tasks for new users.
    
    Creates onboarding progress and logs the signup event.
    """
    try:
        # Create onboarding progress for new users
        from apps.users.models import OnboardingProgress
        
        # Check if onboarding progress already exists
        if not hasattr(user, 'onboarding_progress'):
            onboarding = OnboardingProgress.objects.create(
                user=user,
                current_step='account_created',
                completed_steps=['account_created'],
                onboarding_entry_point='direct_signup'
            )
            logger.info(f"Created onboarding progress for new user: {user.username}")
        
        # Log user signup in activity
        from apps.users.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            activity_type='account_created',
            description=f"User {user.username} created an account",
            is_public=False
        )
        
        logger.info(f"New user signed up: {user.username} ({user.email})")
        
    except Exception as e:
        logger.error(f"Error handling user signup for {user.username}: {e}")


@receiver(post_save, sender=User)
def handle_user_profile_update(sender, instance, created, **kwargs):
    """
    Handle user profile updates and trust level changes.
    
    Updates trust levels and sends notifications when appropriate.
    """
    if created:
        # New user creation is handled by user_signed_up signal
        return
    
    try:
        # Check if user's trust level needs updating
        old_trust_level = getattr(instance, '_old_trust_level', None)
        if old_trust_level and old_trust_level != instance.trust_level:
            # Trust level was upgraded
            logger.info(f"Trust level upgraded for {instance.username}: {old_trust_level} -> {instance.trust_level}")
            
            # Could send congratulations email here in the future
            # email_service = EmailService()
            # email_service.send_trust_level_upgrade_email(instance, old_trust_level, instance.trust_level)
            
    except Exception as e:
        logger.error(f"Error handling user profile update for {instance.username}: {e}")