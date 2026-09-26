"""
Django signals for user-related events.

Handles email notifications for user authentication events like
email verification, password resets, and profile updates.
"""

import logging

from allauth.account.signals import (
    email_confirmed,
    password_changed,
    password_reset,
    password_set,
    user_signed_up,
)
from apps.core.utils.pii_safe_logging import log_safe_user_context
from apps.users.account_links import revoke_refresh_tokens
from apps.users.email_verification import enqueue_on_commit
from django.contrib.auth import get_user_model
from django.dispatch import receiver

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(password_reset)
@receiver(password_changed)
@receiver(password_set)
def revoke_refresh_tokens_on_password_change(sender, request, user, **kwargs):
    """Blacklist every outstanding refresh token when allauth changes a password.

    Without this, a squatter keeps their session through the address owner's
    reset: owner resets the squatter's account at /accounts/password/reset/,
    signs in and verifies, and the squatter's refresh token still refreshes
    into the now-verified account (todo 447, reproduced). Access tokens are not
    revocable and live out their short lifetime.
    """
    revoke_refresh_tokens(user)
    logger.info(
        f"[AUTH] Revoked refresh tokens after a password change for "
        f"{log_safe_user_context(user)}"
    )


@receiver(email_confirmed)
def send_welcome_email_on_verification(sender, request, email_address, **kwargs):
    """Queue the welcome mail once the address is confirmed.

    Sent by Celery after the transaction commits, so SMTP latency never lands
    on the confirming request (todo 447 item 11).
    """
    user = email_address.user
    enqueue_on_commit(
        "send_welcome_email_task", user.pk, context=log_safe_user_context(user)
    )


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
            OnboardingProgress.objects.create(
                user=user,
                current_step="account_created",
                completed_steps=["account_created"],
                onboarding_entry_point="direct_signup",
            )
            logger.info(
                f"[ONBOARDING] Created onboarding progress for new {log_safe_user_context(user)}"
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
            f"[SIGNUP] New user signed up: {log_safe_user_context(user, include_email=True)}"
        )

    except Exception as e:
        logger.error(
            f"[SIGNUP] Error handling user signup for {log_safe_user_context(user)}: {e}"
        )
