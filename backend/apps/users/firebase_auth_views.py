"""
Firebase Authentication Views for Mobile App Integration

This module handles authentication between Firebase (mobile app) and Django (backend).
It validates Firebase ID tokens and exchanges them for Django JWT tokens.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Any, Tuple, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

logger = logging.getLogger(__name__)
User = get_user_model()

# Firebase initialization flag (lazy initialization)
_firebase_initialized = False


def redact_email(email: str) -> str:
    """
    Redact email for GDPR-compliant logging.

    Shows first 2 characters of local part + domain.
    Example: john.doe@example.com -> jo***@example.com

    Args:
        email: Email address to redact

    Returns:
        Redacted email string safe for logs
    """
    if not email or '@' not in email:
        return '***'

    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f"{'*' * len(local)}@{domain}"

    return f"{local[:2]}***@{domain}"


def _ensure_firebase_initialized() -> None:
    """
    Initialize Firebase Admin SDK if not already done.

    This is called lazily on first use, allowing:
    - Tests to run without Firebase credentials (with mocking)
    - CI/CD to skip Firebase initialization if not needed
    - Local dev to work without Firebase setup

    Initialization uses GOOGLE_APPLICATION_CREDENTIALS environment variable.
    See FIREBASE_SETUP.md for configuration instructions.
    """
    global _firebase_initialized

    if _firebase_initialized:
        return

    try:
        firebase_admin.get_app()
        logger.info("[FIREBASE] Firebase Admin SDK already initialized")
    except ValueError:
        # Initialize Firebase app if not already done
        # This will use GOOGLE_APPLICATION_CREDENTIALS env variable
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        logger.info("[FIREBASE] Firebase Admin SDK initialized")

    _firebase_initialized = True


@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_token_exchange(request: Request) -> Response:
    """
    Exchange Firebase ID token for Django JWT tokens.

    This endpoint is called by the mobile app after Firebase authentication.
    It validates the Firebase token and creates/retrieves a Django user,
    then returns JWT access and refresh tokens.

    Request Body:
        {
            "firebase_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6...",
            "email": "user@example.com",  # Optional, for validation
            "display_name": "John Doe"     # Optional, for user creation
        }

    Response (200 OK):
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "display_name": "John Doe",
                "is_active": true
            }
        }

    Response (400 Bad Request):
        {
            "error": "firebase_token is required"
        }

    Response (401 Unauthorized):
        {
            "error": "Invalid Firebase token"
        }
    """
    # Initialize Firebase Admin SDK (lazy initialization)
    _ensure_firebase_initialized()

    try:
        # Extract Firebase token from request
        firebase_token = request.data.get('firebase_token')

        if not firebase_token:
            logger.warning("[FIREBASE AUTH] No firebase_token in request")
            return Response(
                {"error": "firebase_token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate Firebase token
        try:
            decoded_token = firebase_auth.verify_id_token(firebase_token)
            firebase_uid = decoded_token['uid']
            firebase_email = decoded_token.get('email')

            logger.info(f"[FIREBASE AUTH] Token validated for uid={firebase_uid}, email={redact_email(firebase_email)}")

        except firebase_auth.ExpiredIdTokenError as e:
            # NOTE: ExpiredIdTokenError must be caught before InvalidIdTokenError
            # because it's a subclass of InvalidIdTokenError
            logger.warning(f"[FIREBASE AUTH] Expired Firebase token: {str(e)}")
            return Response(
                {"error": "Firebase token has expired"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except firebase_auth.InvalidIdTokenError as e:
            logger.warning(f"[FIREBASE AUTH] Invalid Firebase token: {str(e)}")
            return Response(
                {"error": "Invalid Firebase token"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"[FIREBASE AUTH ERROR] Token verification failed: {str(e)}")
            return Response(
                {"error": "Token verification failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get or create Django user
        user, created = get_or_create_user_from_firebase(
            firebase_uid=firebase_uid,
            firebase_email=firebase_email,
            display_name=request.data.get('display_name'),
        )

        if created:
            logger.info(f"[FIREBASE AUTH] Created new user: {redact_email(user.email)}")
        else:
            logger.info(f"[FIREBASE AUTH] Existing user authenticated: {redact_email(user.email)}")

        # Generate Django JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Return tokens and user info
        return Response({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.get_full_name() or user.username,
                "is_active": user.is_active,
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"[FIREBASE AUTH ERROR] Unexpected error: {str(e)}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def get_or_create_user_from_firebase(
    firebase_uid: str,
    firebase_email: str,
    display_name: Optional[str] = None,
) -> Tuple[User, bool]:
    """
    Get or create a Django user from Firebase credentials.

    Handles username collisions by appending UUID suffix if needed.
    Example: john@gmail.com and john@yahoo.com would create
    'john' and 'john_a1b2c3d4' respectively.

    Args:
        firebase_uid: Firebase user ID
        firebase_email: User's email from Firebase
        display_name: Optional display name for new users

    Returns:
        Tuple of (User instance, created boolean)

    Raises:
        ValueError: If email is invalid or empty
    """
    if not firebase_email or '@' not in firebase_email:
        raise ValueError(f"Invalid Firebase email: {firebase_email}")

    # Try to find existing user by email
    try:
        user = User.objects.get(email=firebase_email)
        created = False

        # Update display name if provided and user has none
        if display_name and not user.first_name:
            user.first_name = display_name
            user.save()
            logger.info(f"[FIREBASE AUTH] Updated display name for {redact_email(user.email)}")

        return user, created

    except User.DoesNotExist:
        pass

    # User doesn't exist - create new user with collision-safe username
    base_username = firebase_email.split('@')[0]
    username = base_username

    # Check for username collision
    if User.objects.filter(username=username).exists():
        # Append UUID suffix to make username unique
        username = f"{base_username}_{uuid.uuid4().hex[:8]}"
        logger.info(
            f"[FIREBASE AUTH] Username collision for '{base_username}', "
            f"using '{username}' for {redact_email(firebase_email)}"
        )

    # Create new user
    try:
        user = User.objects.create(
            email=firebase_email,
            username=username,
            first_name=display_name or '',
            is_active=True,
        )
        logger.info(f"[FIREBASE AUTH] Created user '{user.username}' for {redact_email(firebase_email)}")

        return user, True

    except Exception as e:
        logger.error(
            f"[FIREBASE AUTH ERROR] Failed to create user for {redact_email(firebase_email)}: {str(e)}"
        )
        raise

    # NOTE: Store Firebase UID in user profile if you have a UserProfile model
    # with firebase_uid field:
    #
    # if hasattr(user, 'profile') and not user.profile.firebase_uid:
    #     user.profile.firebase_uid = firebase_uid
    #     user.profile.save()
