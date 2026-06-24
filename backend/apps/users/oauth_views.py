"""
Custom OAuth views for handling social authentication with JWT token generation.
"""

import logging
import secrets

from apps.core.ratelimit import client_ip_key, ratelimit
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.conf import settings
from django.contrib.auth import login as django_login
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .authentication import set_jwt_cookies

logger = logging.getLogger(__name__)


def get_oauth_redirect_url(provider):
    """
    Get the OAuth redirect URL for the frontend.
    """
    # Use configured frontend base URL
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000")
    return f"{frontend_base}/auth/{provider}/callback"


@api_view(["GET"])
@permission_classes([AllowAny])
@ratelimit(key=client_ip_key, rate="10/m", method="GET", block=True)
def oauth_login(request, provider):
    """
    Initiate OAuth login process for the specified provider.
    """
    try:
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state

        if provider == "google":
            # Build Google OAuth URL
            client_id = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"]
            if not client_id:
                return Response(
                    {"error": "Google OAuth not configured"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Use backend URL (port 8000) for redirect URI to match OAuth app configuration
            # In development, requests come through proxy (port 3000) but OAuth needs backend URL
            if settings.DEBUG:
                redirect_uri = "http://localhost:8000/api/auth/oauth/google/callback/"
            else:
                redirect_uri = f"{request.build_absolute_uri('/').rstrip('/')}/api/auth/oauth/google/callback/"
            scope = "+".join(settings.SOCIALACCOUNT_PROVIDERS["google"]["SCOPE"])

            oauth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"scope={scope}&"
                f"response_type=code&"
                f"access_type=online&"
                f"prompt=select_account&"
                f"state={state}"
            )

        elif provider == "github":
            # Build GitHub OAuth URL
            client_id = settings.SOCIALACCOUNT_PROVIDERS["github"]["APP"]["client_id"]
            if not client_id:
                return Response(
                    {"error": "GitHub OAuth not configured"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Use backend URL (port 8000) for redirect URI to match OAuth app configuration
            # In development, requests come through proxy (port 3000) but OAuth needs backend URL
            if settings.DEBUG:
                redirect_uri = "http://localhost:8000/api/auth/oauth/github/callback/"
            else:
                redirect_uri = f"{request.build_absolute_uri('/').rstrip('/')}/api/auth/oauth/github/callback/"
            scope = "+".join(settings.SOCIALACCOUNT_PROVIDERS["github"]["SCOPE"])

            oauth_url = (
                f"https://github.com/login/oauth/authorize?"
                f"client_id={client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"scope={scope}&"
                f"response_type=code&"
                f"state={state}"
            )

        else:
            return Response(
                {"error": f"Provider {provider} not supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"oauth_url": oauth_url, "provider": provider})

    except Exception as e:
        logger.error(f"OAuth login error for {provider}: {str(e)}")
        return Response(
            {"error": "OAuth initialization failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
@ratelimit(key=client_ip_key, rate="10/m", method="GET", block=True)
def oauth_callback(request, provider):
    """
    Handle OAuth callback and generate JWT tokens.
    """
    try:
        # Get authorization code from query params
        code = request.GET.get("code")
        error = request.GET.get("error")

        if error:
            logger.warning(f"OAuth error for {provider}: {error}")
            # Redirect to frontend with error
            frontend_url = get_oauth_redirect_url(provider)
            return HttpResponseRedirect(f"{frontend_url}?error={error}")

        # Validate state to prevent CSRF attacks
        received_state = request.GET.get("state", "")
        expected_state = request.session.pop("oauth_state", None)
        if not expected_state or not secrets.compare_digest(
            expected_state, received_state
        ):
            logger.warning(
                f"[SECURITY] OAuth state mismatch for {provider} — possible CSRF"
            )
            frontend_url = get_oauth_redirect_url(provider)
            return HttpResponseRedirect(f"{frontend_url}?error=invalid_state")

        if not code:
            logger.warning(f"No authorization code received for {provider}")
            frontend_url = get_oauth_redirect_url(provider)
            return HttpResponseRedirect(f"{frontend_url}?error=no_code")

        # Exchange code for access token and get user info
        if provider == "google":
            user_data = _handle_google_callback(request, code)
        elif provider == "github":
            user_data = _handle_github_callback(request, code)
        else:
            logger.error(f"Unsupported provider: {provider}")
            frontend_url = get_oauth_redirect_url(provider)
            return HttpResponseRedirect(f"{frontend_url}?error=unsupported_provider")

        if not user_data:
            logger.error(f"Failed to get user data from {provider}")
            frontend_url = get_oauth_redirect_url(provider)
            return HttpResponseRedirect(f"{frontend_url}?error=user_data_failed")

        # Find or create user
        user = _find_or_create_user(provider, user_data)

        if not user:
            logger.error(f"Failed to create/find user for {provider}")
            frontend_url = get_oauth_redirect_url(provider)
            return HttpResponseRedirect(f"{frontend_url}?error=user_creation_failed")

        # Log the user in with explicit backend
        django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        # Set httpOnly cookies with JWT tokens and redirect to frontend without exposing tokens in URL
        # Cookies are scoped to the host (localhost), not the port; they'll be sent with API requests to backend
        frontend_url = get_oauth_redirect_url(provider)
        redirect_url = f"{frontend_url}?success=true"
        response = HttpResponseRedirect(redirect_url)
        response = set_jwt_cookies(response, user)

        logger.info(
            f"Successful OAuth login for {log_safe_user_context(user)} via {provider}"
        )
        return response

    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {str(e)}")
        frontend_url = get_oauth_redirect_url(provider)
        return HttpResponseRedirect(f"{frontend_url}?error=callback_failed")


def _handle_google_callback(request, code):
    """
    Handle Google OAuth callback and return user data.
    """
    import requests

    try:
        # Exchange code for access token
        token_url = "https://oauth2.googleapis.com/token"
        # Use backend URL (port 8000) for redirect URI to match OAuth app configuration
        if settings.DEBUG:
            redirect_uri = "http://localhost:8000/api/auth/oauth/google/callback/"
        else:
            redirect_uri = f"{request.build_absolute_uri('/').rstrip('/')}/api/auth/oauth/google/callback/"

        token_data = {
            "client_id": settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"],
            "client_secret": settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"][
                "secret"
            ],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()

        if "access_token" not in token_json:
            logger.error(f"Google token exchange failed: {token_json}")
            return None

        # Get user profile
        profile_url = f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={token_json['access_token']}"
        profile_response = requests.get(profile_url)

        if profile_response.status_code != 200:
            logger.error(f"Google profile fetch failed: {profile_response.text}")
            return None

        profile = profile_response.json()

        # Refuse to trust an unverified email. Matching (or creating) a Django
        # account by an email Google has not verified is an account-takeover
        # vector — the same stance the GitHub path takes (primary AND verified).
        # The v2 userinfo endpoint returns `verified_email`; fall back to the
        # OIDC `email_verified` claim, and default to unverified if absent.
        email_verified = profile.get(
            "verified_email", profile.get("email_verified", False)
        )
        if profile.get("email") and not email_verified:
            logger.warning(
                "[SECURITY] Google returned an unverified email — refusing to "
                "match/create an account (GDPR: no email logged)"
            )
            profile.pop("email", None)

        return profile

    except Exception as e:
        logger.error(f"Google OAuth handling error: {str(e)}")
        return None


def _handle_github_callback(request, code):
    """
    Handle GitHub OAuth callback and return user data.
    """
    import requests

    try:
        # Exchange code for access token
        token_url = "https://github.com/login/oauth/access_token"

        token_data = {
            "client_id": settings.SOCIALACCOUNT_PROVIDERS["github"]["APP"]["client_id"],
            "client_secret": settings.SOCIALACCOUNT_PROVIDERS["github"]["APP"][
                "secret"
            ],
            "code": code,
        }

        token_response = requests.post(
            token_url, data=token_data, headers={"Accept": "application/json"}
        )
        token_json = token_response.json()

        if "access_token" not in token_json:
            logger.error(f"GitHub token exchange failed: {token_json}")
            return None

        # Get user profile
        profile_url = "https://api.github.com/user"
        headers = {
            "Authorization": f"token {token_json['access_token']}",
            "Accept": "application/vnd.github.v3+json",
        }

        profile_response = requests.get(profile_url, headers=headers)

        if profile_response.status_code != 200:
            logger.error(f"GitHub profile fetch failed: {profile_response.text}")
            return None

        user_data = profile_response.json()

        # Get user email if not public
        if not user_data.get("email"):
            email_url = "https://api.github.com/user/emails"
            email_response = requests.get(email_url, headers=headers)
            if email_response.status_code == 200:
                emails = email_response.json()
                # Require BOTH primary and verified — matching a Django account by
                # an unverified email is an account-takeover vector.
                primary_email = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                if primary_email:
                    user_data["email"] = primary_email["email"]

        return user_data

    except Exception as e:
        logger.error(f"GitHub OAuth handling error: {str(e)}")
        return None


def _find_or_create_user(provider, user_data):
    """
    Find existing user or create new user from OAuth data.
    """
    from apps.users.signup import create_default_plant_collection
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        email = user_data.get("email")
        if not email:
            logger.error(f"No email provided by {provider} (GDPR: no email logged)")
            return None

        # Check if user exists with this email
        try:
            user = User.objects.get(email=email)
            logger.info(f"Found existing {log_safe_user_context(user)}")
            return user
        except User.DoesNotExist:
            pass

        # Create new user
        if provider == "google":
            username = user_data.get("email").split("@")[0]
            first_name = user_data.get("given_name", "")[:30]
            last_name = user_data.get("family_name", "")[:150]
        elif provider == "github":
            username = user_data.get("login", user_data.get("email").split("@")[0])
            name = user_data.get("name", "")
            name_parts = name.split(" ", 1) if name else ["", ""]
            first_name = name_parts[0][:30]
            last_name = name_parts[1][:150] if len(name_parts) > 1 else ""
        else:
            username = email.split("@")[0]
            first_name = ""
            last_name = ""

        # Ensure username is unique
        original_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            counter += 1

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        # Create default plant collection (shared signup side-effect)
        create_default_plant_collection(user)

        # Update additional fields for GitHub
        if provider == "github":
            if user_data.get("bio"):
                user.bio = user_data.get("bio", "")[:500]
            if user_data.get("blog"):
                user.website = user_data.get("blog", "")[:200]
            if user_data.get("location"):
                user.location = user_data.get("location", "")[:100]
            user.save()

        logger.info(f"Created new {log_safe_user_context(user)} via {provider}")
        return user

    except Exception as e:
        logger.error(f"User creation error for {provider}: {str(e)}")
        return None
