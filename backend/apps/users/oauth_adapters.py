"""
Custom adapters for django-allauth OAuth integration with JWT authentication.
"""

import logging
from typing import Any, Optional

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.urls import reverse

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter to handle OAuth flow with JWT token generation.
    """

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        """
        Invoked just after a user successfully authenticates via a social provider,
        but before the login is actually processed.

        Args:
            request: Django HTTP request object
            sociallogin: SocialLogin instance containing OAuth provider data
        """
        # Check if user exists with same email
        if (
            sociallogin.account.provider == "google"
            or sociallogin.account.provider == "github"
        ):
            email = sociallogin.account.extra_data.get("email")
            if email:
                # Only auto-link to an existing local account when the provider
                # has VERIFIED the email. Linking by an unverified email is an
                # account-takeover vector — the same stance the custom
                # oauth_views path takes. allauth's connect() bypasses
                # SOCIALACCOUNT_EMAIL_VERIFICATION, so we gate it explicitly here.
                if not self._provider_email_verified(sociallogin, email):
                    logger.warning(
                        f"[SECURITY] Refused to auto-link "
                        f"{sociallogin.account.provider} account by unverified email"
                    )
                    return
                try:
                    existing_user = User.objects.get(email=email)
                    if not sociallogin.is_existing:
                        # Connect the social account to existing user
                        sociallogin.connect(request, existing_user)
                        logger.info(
                            f"Connected {sociallogin.account.provider} account "
                            f"to existing {log_safe_user_context(existing_user)}"
                        )
                except User.DoesNotExist:
                    pass

    @staticmethod
    def _provider_email_verified(sociallogin: SocialLogin, email: str) -> bool:
        """Return True only if the provider has verified `email`.

        allauth populates ``sociallogin.email_addresses`` (``EmailAddress``
        instances with a ``.verified`` flag) from the provider's own signal —
        for Google that mirrors the ``email_verified`` claim; for GitHub it
        reflects the verified-emails API. Fail closed: an email the provider
        did not return as verified (or did not enumerate) is treated as
        unverified.
        """
        target = email.lower()
        for addr in sociallogin.email_addresses:
            if addr.email and addr.email.lower() == target:
                return bool(addr.verified)
        return False

    def save_user(
        self, request: HttpRequest, sociallogin: SocialLogin, form: Optional[Any] = None
    ) -> User:
        """
        Saves a newly signed up social login user.

        Args:
            request: Django HTTP request object
            sociallogin: SocialLogin instance containing OAuth provider data
            form: Optional form data (usually None for social auth)

        Returns:
            Created or updated User instance
        """
        user = super().save_user(request, sociallogin, form)

        # Update user profile with social data
        extra_data = sociallogin.account.extra_data

        if sociallogin.account.provider == "google":
            # Update from Google profile
            if not user.first_name and extra_data.get("given_name"):
                user.first_name = extra_data.get("given_name", "")[:30]
            if not user.last_name and extra_data.get("family_name"):
                user.last_name = extra_data.get("family_name", "")[:150]

        elif sociallogin.account.provider == "github":
            # Update from GitHub profile
            if not user.first_name and extra_data.get("name"):
                name_parts = extra_data.get("name", "").split(" ", 1)
                user.first_name = name_parts[0][:30] if name_parts else ""
                if len(name_parts) > 1:
                    user.last_name = name_parts[1][:150]

            # Set bio from GitHub bio if available
            if not user.bio and extra_data.get("bio"):
                user.bio = extra_data.get("bio", "")[:500]

            # Set website from GitHub blog if available
            if not user.website and extra_data.get("blog"):
                user.website = extra_data.get("blog", "")[:200]

        user.save()
        logger.info(
            f"Created new {log_safe_user_context(user)} via {sociallogin.account.provider}"
        )
        return user

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        """
        Return the URL to redirect to after a successful social login.
        We'll redirect to our custom callback view that handles JWT token generation.

        Args:
            request: Django HTTP request object

        Returns:
            URL string for redirect after social login
        """
        # Get the provider name
        provider = getattr(request, "_oauth_provider", "unknown")

        # Redirect to our custom callback view
        return reverse("users:oauth_callback", kwargs={"provider": provider})


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for regular authentication flow.
    """

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        """
        Return the URL to redirect to after login.

        Args:
            request: Django HTTP request object

        Returns:
            URL string for redirect after login
        """
        # For API-based authentication, we don't need to redirect
        return "/"

    def get_logout_redirect_url(self, request: HttpRequest) -> str:
        """
        Return the URL to redirect to after logout.

        Args:
            request: Django HTTP request object

        Returns:
            URL string for redirect after logout
        """
        return "/"

    def send_confirmation_mail(
        self, request: HttpRequest, emailconfirmation: Any, signup: bool
    ) -> None:
        """
        Custom email confirmation logic.

        Args:
            request: Django HTTP request object
            emailconfirmation: EmailConfirmation instance
            signup: Whether this is a new signup (True) or email change (False)
        """
        # You can customize email confirmation here if needed
        super().send_confirmation_mail(request, emailconfirmation, signup)
