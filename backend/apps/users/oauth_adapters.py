"""
Custom adapters for django-allauth OAuth integration with JWT authentication.
"""

import logging
from typing import Any, Optional

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from apps.core.utils.pii_safe_logging import log_safe_user_context
from apps.users.account_links import on_first_provider_link
from apps.users.email_verification import (
    get_account_by_email,
    is_email_verified,
    send_verification_email,
)
from apps.users.oauth_views import get_oauth_redirect_url
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponseRedirect
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
        if sociallogin.account.provider not in ("google", "github"):
            return

        email = sociallogin.account.extra_data.get("email")
        if not email:
            return

        # The social account is already linked to a user (a returning login):
        # nothing to link, and no takeover surface.
        if sociallogin.is_existing:
            return

        try:
            # Case-insensitive, and the verified holder wins among case
            # variants, like the web and Firebase paths (todo 447).
            existing_user = get_account_by_email(email)
        except User.DoesNotExist:
            # No local account owns this email. allauth's auto-signup (gated by
            # the mandatory ACCOUNT_EMAIL_VERIFICATION) handles new users safely.
            return
        except User.MultipleObjectsReturned:
            logger.warning(
                f"[SECURITY] Refused {sociallogin.account.provider} login: "
                f"several accounts share this email"
            )
            error_url = (
                f"{get_oauth_redirect_url(sociallogin.account.provider)}"
                f"?error=user_creation_failed"
            )
            raise ImmediateHttpResponse(HttpResponseRedirect(error_url))

        # A local account already owns this email and this social account is not
        # yet linked. Only proceed when the provider has VERIFIED the email —
        # linking (or creating) off an unverified email is an account-takeover
        # vector. This is the allauth arm of the verified-email invariant
        # (canonical: docs/patterns/security/authentication.md → "Trust only
        # provider-verified emails").
        #
        # A bare `return` here is NOT safe: under SOCIALACCOUNT_AUTO_SIGNUP allauth
        # would then auto-create a SECOND account holding the victim's email
        # (User.email is not DB-unique, and allauth's uniqueness check only
        # sees EmailAddress rows, which an account may lack). Raise
        # ImmediateHttpResponse to abort the whole login pipeline before
        # allauth's signup/save_user runs.
        if not self._provider_email_verified(sociallogin, email):
            logger.warning(
                f"[SECURITY] Refused {sociallogin.account.provider} login: "
                f"unverified email collides with an existing account"
            )
            error_url = (
                f"{get_oauth_redirect_url(sociallogin.account.provider)}"
                f"?error=unverified_email"
            )
            raise ImmediateHttpResponse(HttpResponseRedirect(error_url))

        # The provider proved the email; the local account must have too, or
        # this links the provider user into an account a stranger registered
        # with their address (todo 446).
        if not is_email_verified(existing_user):
            logger.warning(
                f"[SECURITY] Refused {sociallogin.account.provider} login: email "
                f"matches an unverified local account"
            )
            error_url = (
                f"{get_oauth_redirect_url(sociallogin.account.provider)}"
                f"?error=account_unverified"
            )
            raise ImmediateHttpResponse(HttpResponseRedirect(error_url))

        # Verified: link the social account to the existing local user. It is
        # a new link (is_existing returned above): revoke and notify first.
        on_first_provider_link(existing_user, sociallogin.account.provider)
        sociallogin.connect(request, existing_user)
        logger.info(
            f"[AUTH] Connected {sociallogin.account.provider} account "
            f"to existing {log_safe_user_context(existing_user)}"
        )

    def is_open_for_signup(
        self, request: HttpRequest, sociallogin: SocialLogin
    ) -> bool:
        """allauth's default asks the ACCOUNT adapter, which is closed below
        for local signup only. Social signup stays as it was."""
        return True

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
            f"[AUTH] Created new {log_safe_user_context(user)} via {sociallogin.account.provider}"
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

        # Redirect to our custom callback view (the root OAuth mount,
        # /api/auth/oauth/<provider>/callback/)
        return reverse("oauth_callback", kwargs={"provider": provider})


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for regular authentication flow.
    """

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Closed: accounts are created by ``POST /api/v1/auth/register/``.
        allauth's ``/accounts/signup/`` skipped its checks, rate limit and
        side effects (todo 447)."""
        return False

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
        """Route allauth's verification mails through ours (todo 446).

        allauth's own mail links to ``/accounts/confirm-email/<key>/``, which
        confirms with the key alone. Ours links to the web page, whose endpoint
        also requires a session for the key's account.
        """
        send_verification_email(emailconfirmation.email_address.user)
