"""
Django signals for user-related events.

Handles email notifications for user authentication events like
email verification, password resets, and profile updates.
"""

import logging

from allauth.account.signals import email_confirmed, user_signed_up
from apps.core.services.email_service import EmailService
from apps.core.utils.pii_safe_logging import (
    log_safe_email,
    log_safe_user_context,
    log_safe_username,
)
from django.contrib.auth import get_user_model
from django.dispatch import receiver

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
            logger.info(
                f"Welcome email sent to {log_safe_user_context(user)} ({log_safe_email(email_address.email)})"
            )
        else:
            logger.error(
                f"Failed to send welcome email to {log_safe_user_context(user)}"
            )

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
        if not hasattr(user, "onboarding_progress"):
            onboarding = OnboardingProgress.objects.create(
                user=user,
                current_step="account_created",
                completed_steps=["account_created"],
                onboarding_entry_point="direct_signup",
            )
            logger.info(
                f"Created onboarding progress for new {log_safe_user_context(user)}"
            )

        # Log user signup in activity
        from apps.users.models import ActivityLog

        ActivityLog.objects.create(
            user=user,
            activity_type="account_created",
            description=f"User {user.username} created an account",
            is_public=False,
        )

        logger.info(
            f"New user signed up: {log_safe_user_context(user, include_email=True)}"
        )

    except Exception as e:
        logger.error(
            f"Error handling user signup for {log_safe_user_context(user)}: {e}"
        )
