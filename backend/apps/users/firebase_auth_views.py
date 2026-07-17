"""
Firebase Authentication Views for Mobile App Integration

This module handles authentication between Firebase (mobile app) and Django (backend).
It validates Firebase ID tokens and exchanges them for Django JWT tokens.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple

import firebase_admin
from apps.core.ratelimit import (  # rate-preserving wrapper (Retry-After)
    client_ip_key,
    ratelimit,
)
from apps.plant_identification.constants import RATE_LIMITS
from apps.users.signup import create_default_plant_collection
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from firebase_admin import auth as firebase_auth
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

# Federated providers that self-verify email — no explicit email_verified check needed.
_TRUSTED_FIREBASE_PROVIDERS = frozenset({"google.com", "apple.com"})

logger = logging.getLogger(__name__)
User = get_user_model()


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
    if not email or "@" not in email:
        return "***"

    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{'*' * len(local)}@{domain}"

    return f"{local[:2]}***@{domain}"


def _ensure_firebase_initialized() -> None:
    """
    Initialize the shared firebase_admin default app if not already done.

    Lazy so tests/CI/dev run without Firebase credentials (with mocking).
    Resolution order:

    1. An existing default app — initialized by any code path (e.g.
       apps/garden/firebase_config.py's FCM bootstrap) — is reused as-is; the
       firebase_admin app registry, not a module flag, is the source of truth
       (a flag can't survive test-side ``reset_firebase()`` app deletion).
    2. ``settings.FIREBASE_CREDENTIALS_PATH`` — the canonical service-account
       setting (it also absorbs GOOGLE_APPLICATION_CREDENTIALS; settings.py),
       initialized through the same apps/garden bootstrap the FCM sender
       uses, so the shared app is fully credentialed whichever side runs
       first.
    3. projectId-only (``settings.FIREBASE_PROJECT_ID``): serves the Firebase
       Auth *emulator* dev loop (FIREBASE_AUTH_EMULATOR_HOST — emulator mode
       substitutes its own credentials) and ADC-resolvable environments.
       Against production Firebase with no resolvable ADC, verification
       still fails as a handled 401 — this tier does NOT make a key-less
       machine verify production tokens (verified live: firebase_admin 7.4.0
       resolves the app credential eagerly in its verifier).

    Never raises: a broken credential file or a lost first-touch init race
    must degrade to failed verification (handled 401), not 500 every login.
    """
    try:
        firebase_admin.get_app()
        logger.info("[FIREBASE] Firebase Admin SDK already initialized")
        return
    except ValueError:
        pass

    from apps.garden.firebase_config import initialize_firebase
    from django.conf import settings

    try:
        if initialize_firebase():
            # Tier 2: certificate init via the shared bootstrap (it logs its
            # own credential source).
            return
        if getattr(settings, "FIREBASE_CREDENTIALS_PATH", None):
            # A credentials path IS configured but failed to initialize
            # (bad/missing/wrong-type file). Do NOT substitute a
            # credential-less default app: the FCM sender's reuse branch
            # would adopt it and burn send+3 retries per push on credential
            # errors instead of its clean unavailable skip (review sweep).
            # Verification fails as a handled 401; the bootstrap error was
            # already logged by initialize_firebase.
            logger.error(
                "[FIREBASE AUTH ERROR] Credentials path configured but "
                "initialization failed — refusing projectId-only fallback"
            )
            return
        # Tier 3: projectId-only — auth-emulator dev loop / ADC envs. FCM
        # sending stays disabled (it needs FIREBASE_CREDENTIALS_PATH).
        project_id = getattr(settings, "FIREBASE_PROJECT_ID", None)
        firebase_admin.initialize_app(
            options={"projectId": project_id} if project_id else None
        )
        logger.info(
            "[FIREBASE] Firebase Admin SDK initialized (projectId-only — "
            "FCM sending disabled)"
        )
    except ValueError:
        # Lost a concurrent first-touch race — adopt the winner's app. The
        # adoption itself must honor the never-raises contract too (a
        # ValueError raised INSIDE this handler would escape the sibling
        # except below): if no winner exists after all, log and degrade.
        try:
            firebase_admin.get_app()
            logger.info("[FIREBASE] Adopted concurrently-initialized default app")
        except Exception:
            logger.exception(
                "[FIREBASE AUTH ERROR] Init raised ValueError with no "
                "existing app to adopt"
            )
    except Exception:
        # Surface loudly, but let verification fail as a handled 401 rather
        # than 500ing every login over a bootstrap problem (e.g. a typo'd
        # credentials path).
        logger.exception("[FIREBASE AUTH ERROR] Firebase initialization failed")


@api_view(["POST"])
@permission_classes([AllowAny])
@ratelimit(
    key=client_ip_key,
    rate=RATE_LIMITS["auth_endpoints"]["firebase_token_exchange"],
    method="POST",
    block=True,
)
def firebase_token_exchange(request: Request) -> Response:
    """
    Exchange Firebase ID token for Django JWT tokens.

    This endpoint is called by the mobile app after Firebase authentication.
    It validates the Firebase token and creates/retrieves a Django user,
    then returns JWT access and refresh tokens.

    Request Body:
        {
            "firebase_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
        }

    Note: only the Firebase ID token is trusted. Any client-supplied identity
    fields (email, display_name) are ignored — identity is read from the verified
    token claims to prevent the account-takeover vector (audit C8).

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
        firebase_token = request.data.get("firebase_token")

        if not firebase_token:
            logger.warning("[FIREBASE AUTH] No firebase_token in request")
            return Response(
                {"error": "firebase_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate Firebase token
        try:
            decoded_token = firebase_auth.verify_id_token(firebase_token)
            firebase_uid = decoded_token["uid"]
            firebase_email = decoded_token.get("email")
            email_verified = bool(decoded_token.get("email_verified"))
            sign_in_provider = decoded_token.get("firebase", {}).get(
                "sign_in_provider", ""
            )

            # Reject unverified-email tokens to prevent account takeover via Firebase
            # email/password sign-up to a never-verified address that collides with an
            # existing Django user. Federated providers (Google, Apple) self-verify.
            if (
                firebase_email
                and not email_verified
                and sign_in_provider not in _TRUSTED_FIREBASE_PROVIDERS
            ):
                logger.warning(
                    f"[FIREBASE AUTH] Rejected unverified email login "
                    f"(provider={sign_in_provider}, email={redact_email(firebase_email)})"
                )
                return Response(
                    {"error": "Email address must be verified before logging in."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            logger.info(
                f"[FIREBASE AUTH] Token validated for uid={firebase_uid}, email={redact_email(firebase_email)}"
            )

        except firebase_auth.ExpiredIdTokenError as e:
            # NOTE: ExpiredIdTokenError must be caught before InvalidIdTokenError
            # because it's a subclass of InvalidIdTokenError
            logger.warning(f"[FIREBASE AUTH] Expired Firebase token: {str(e)}")
            return Response(
                {"error": "Firebase token has expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except firebase_auth.InvalidIdTokenError as e:
            logger.warning(f"[FIREBASE AUTH] Invalid Firebase token: {str(e)}")
            return Response(
                {"error": "Invalid Firebase token"}, status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"[FIREBASE AUTH ERROR] Token verification failed: {str(e)}")
            return Response(
                {"error": "Token verification failed"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get or create Django user. display_name comes from the verified
        # Firebase token's `name` claim — never from client-supplied request data.
        user, created = get_or_create_user_from_firebase(
            firebase_uid=firebase_uid,
            firebase_email=firebase_email,
            display_name=decoded_token.get("name"),
            email_verified=email_verified
            or sign_in_provider in _TRUSTED_FIREBASE_PROVIDERS,
        )

        if created:
            logger.info(f"[FIREBASE AUTH] Created new user: {redact_email(user.email)}")
        else:
            logger.info(
                f"[FIREBASE AUTH] Existing user authenticated: {redact_email(user.email)}"
            )

        # Generate Django JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Return tokens and user info
        return Response(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.get_full_name() or user.username,
                    "is_active": user.is_active,
                },
            },
            status=status.HTTP_200_OK,
        )

    except ValueError as e:
        # Account-linking conflict (e.g., the email is already bound to a different
        # Firebase UID). Fail closed with a 409 rather than an opaque 500.
        logger.warning(f"[FIREBASE AUTH] Account linking conflict: {str(e)}")
        return Response(
            {"error": "Account linking conflict"}, status=status.HTTP_409_CONFLICT
        )

    except Exception as e:
        logger.error(f"[FIREBASE AUTH ERROR] Unexpected error: {str(e)}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def get_or_create_user_from_firebase(
    firebase_uid: str,
    firebase_email: str,
    display_name: Optional[str] = None,
    email_verified: bool = False,
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
        email_verified: Whether the caller has proven control of the email
            (Firebase `email_verified` claim, or a trusted federated provider).
            Required before linking/backfilling a UID onto an existing email
            account — prevents account takeover via an unverified email.

    Returns:
        Tuple of (User instance, created boolean)

    Raises:
        ValueError: If email is invalid, already bound to a different Firebase
            UID, or unverified when linking to an existing account.
    """
    if not firebase_email or "@" not in firebase_email:
        # Redact: this message is surfaced via str(e) into a warning log upstream.
        raise ValueError(f"Invalid Firebase email: {redact_email(firebase_email)}")

    # Prefer the stable Firebase UID. Linking by email alone is a takeover risk
    # if an email is ever reassigned at the identity provider.
    try:
        user = User.objects.get(firebase_uid=firebase_uid)
        if display_name and not user.first_name:
            user.first_name = display_name
            user.save(update_fields=["first_name"])
            logger.info(
                f"[FIREBASE AUTH] Updated display name for {redact_email(user.email)}"
            )
        return user, False
    except User.DoesNotExist:
        pass

    # Fall back to email for accounts created before UID binding existed.
    try:
        user = User.objects.get(email=firebase_email)

        if user.firebase_uid and user.firebase_uid != firebase_uid:
            # This email is already bound to a different Firebase identity.
            logger.warning(
                f"[FIREBASE AUTH] UID mismatch for {redact_email(firebase_email)}: "
                f"account bound to a different Firebase UID"
            )
            raise ValueError("Email is already linked to a different Firebase account")

        # Only link/backfill a UID onto an existing account when the caller has
        # proven control of the email. Without this, an unverified email could be
        # used to seize an existing account. (The token-exchange view already
        # enforces this upstream; re-checked here as defence-in-depth.)
        if not user.firebase_uid and not email_verified:
            logger.warning(
                f"[FIREBASE AUTH] Refused to bind unverified email "
                f"{redact_email(firebase_email)} to existing account"
            )
            raise ValueError(
                "Email must be verified before linking to an existing account"
            )

        # Backfill the binding on first sign-in for a legacy email account.
        update_fields = []
        if not user.firebase_uid:
            user.firebase_uid = firebase_uid
            update_fields.append("firebase_uid")
        if display_name and not user.first_name:
            user.first_name = display_name
            update_fields.append("first_name")
        if update_fields:
            user.save(update_fields=update_fields)
            logger.info(
                f"[FIREBASE AUTH] Bound Firebase UID for {redact_email(user.email)}"
            )

        return user, False

    except User.DoesNotExist:
        pass
    except User.MultipleObjectsReturned:
        # `email` is not DB-unique; app-layer registration enforces uniqueness,
        # but defend against a duplicate slipping in rather than 500-ing on the
        # ambiguous .get(). Fail closed as a linking conflict (→ 409 upstream).
        logger.error(
            f"[FIREBASE AUTH] Multiple accounts share email "
            f"{redact_email(firebase_email)} — refusing ambiguous login"
        )
        raise ValueError("Multiple accounts exist for this email")

    # User doesn't exist - create new user with collision-safe username
    base_username = firebase_email.split("@")[0]
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
            first_name=display_name or "",
            is_active=True,
            firebase_uid=firebase_uid,
        )
        # Shared signup side-effect — Firebase users previously did NOT get the
        # default "My Plants" collection that registration/OAuth create (M7).
        create_default_plant_collection(user)
        logger.info(
            f"[FIREBASE AUTH] Created user '{user.username}' for {redact_email(firebase_email)}"
        )

        return user, True

    except IntegrityError:
        # A concurrent first sign-in for THIS identity won the create race —
        # return the row it inserted. Match strictly on the unique firebase_uid;
        # never fall back to email here, or a different identity that won an email
        # race could be handed this caller's session (account takeover). If no row
        # matches our UID, fail closed — the retry hits the explicit
        # "different Firebase account" check and returns 409.
        existing = User.objects.filter(firebase_uid=firebase_uid).first()
        if existing is not None:
            return existing, False
        raise

    except Exception as e:
        logger.error(
            f"[FIREBASE AUTH ERROR] Failed to create user for {redact_email(firebase_email)}: {str(e)}"
        )
        raise
