"""
Authentication and user management views for the Plant Community application.
"""

import hashlib
import logging
import uuid
from typing import Optional

from apps.core import ratelimit as core_ratelimit
from apps.core.ratelimit import client_ip_key
from apps.core.security import SecurityMonitor, log_security_event
from apps.core.utils.pii_safe_logging import log_safe_user_context, log_safe_username
from apps.plant_identification.constants import RATE_LIMITS
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

# Rate limiting - now required for security
from django_ratelimit.decorators import ratelimit
from rest_framework import permissions, status
from rest_framework.authentication import CSRFCheck
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from . import view_schemas as vs
from .authentication import RefreshTokenFromCookie, clear_jwt_cookies, set_jwt_cookies
from .avatars import avatar_file_names, delete_avatar_files_on_commit
from .constants import RATE_LIMIT_ONBOARDING_EVENT, RATE_LIMIT_PUSH_RESUBSCRIBE
from .email_verification import (
    VerificationKeyInvalid,
    confirm_verification_key,
    is_email_verified,
    send_verification_email,
    verification_cap_reached,
)
from .models import User, UserPlantCollection
from .serializers import (
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .signup import create_default_plant_collection, join_forum_members_group

logger = logging.getLogger(__name__)


def create_error_response(
    code: str,
    message: str,
    details: Optional[str] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """
    Create a standardized error response.

    Matches the canonical error shape emitted by
    ``apps.core.exceptions.custom_exception_handler`` so every API error has the
    same contract: a flat body with ``error``, ``message``, ``code`` and
    ``status_code``, plus an optional ``errors`` map for field/detail data.

    Args:
        code: Error code identifier (e.g., 'INVALID_CREDENTIALS')
        message: Brief error message
        details: Optional detailed error explanation
        status_code: HTTP status code

    Returns:
        Response object with standardized error structure
    """
    error_data = {
        "error": True,
        "message": message,
        "code": code,
        "status_code": status_code,
    }
    if details:
        error_data["errors"] = {"detail": details}

    return Response(error_data, status=status_code)


@vs.CSRF_TOKEN_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request: Request) -> Response:
    """
    Get CSRF token for frontend.
    """
    return Response({"detail": "CSRF cookie set"})


@vs.REGISTER_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@csrf_protect  # SECURITY: Enforce CSRF protection for registration
@ratelimit(
    key=client_ip_key,
    rate=RATE_LIMITS["auth_endpoints"]["register"],
    method="POST",
    block=True,
)
def register(request: Request) -> Response:
    """
    Register a new user account.

    SECURITY: CSRF protection is enforced to prevent automated bot registrations
    and cross-site request forgery attacks. Frontend must include X-CSRFToken header.
    """
    # Log registration attempt (without sensitive data)
    username = request.data.get("username", "unknown")
    logger.info(
        f"[SIGNUP] Registration attempt for user: {log_safe_username(username)}"
    )

    serializer = UserRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        try:
            with transaction.atomic():
                # Create user
                user = serializer.save()

                # Shared signup side-effects
                create_default_plant_collection(user)
                join_forum_members_group(user)

                # The account is usable at once, but no sign-in path will match
                # it by email until the owner confirms the address (todo 446).
                # Queued for Celery once this transaction commits (todo 447).
                send_verification_email(user)

                # Create response with user data
                response = Response(
                    {
                        "message": "Registration successful",
                        "user": UserSerializer(user).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

                # Set JWT tokens as httpOnly cookies
                response = set_jwt_cookies(response, user)

                return response

        except Exception as e:
            logger.error(f"[SIGNUP] Registration failed: {str(e)}")
            return create_error_response(
                "REGISTRATION_FAILED",
                "Registration failed",
                "An unexpected error occurred. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Log validation errors (sanitized)
    error_fields = list(serializer.errors.keys()) if serializer.errors else []
    username = request.data.get("username", "unknown")
    logger.warning(
        f"[SIGNUP] Registration validation failed for user: {log_safe_username(username)}, fields: {error_fields}"
    )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@vs.VERIFY_EMAIL_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key="user",
    rate=RATE_LIMITS["auth_endpoints"]["verify_email"],
    method="POST",
    block=True,
)
def verify_email(request: Request) -> Response:
    """Confirm the signed-in user's email from the key in their verification link.

    Needs BOTH the key (proves the inbox) and a session for the key's account
    (proves the account): the key alone would let a victim who clicks the link
    verify an attacker's pre-registered account. POST only, because mail
    scanners prefetch GET links (todo 446).
    """
    key = request.data.get("key") if isinstance(request.data, dict) else None
    try:
        confirm_verification_key(key, request.user, request=request._request)
    except VerificationKeyInvalid:
        return create_error_response(
            "VERIFICATION_KEY_INVALID",
            "Invalid verification link",
            "This link is invalid, expired, already used, or for a different "
            "account than the one you are signed in to.",
            status.HTTP_400_BAD_REQUEST,
        )
    return Response({"verified": True})


@vs.RESEND_VERIFICATION_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key="user",
    rate=RATE_LIMITS["auth_endpoints"]["verify_email_resend"],
    method="POST",
    block=True,
)
def resend_verification_email(request: Request) -> Response:
    """Queue a fresh verification link for the signed-in user (todo 446).

    ``sent`` means queued; the mail goes out from Celery. ``limit_reached``
    means the account has had its ``VERIFICATION_EMAIL_CAP`` mails for this
    window and none was queued (todo 447 item 9).
    """
    if is_email_verified(request.user):
        return Response({"verified": True, "sent": False})
    sent = send_verification_email(request.user)
    request.user.refresh_from_db(
        fields=["verification_emails_sent", "verification_window_started_at"]
    )
    limit_reached = not sent and verification_cap_reached(request.user)
    return Response({"verified": False, "sent": sent, "limit_reached": limit_reached})


@vs.LOGIN_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@csrf_protect
@ensure_csrf_cookie  # Ensure CSRF cookie is set in response so clients can use it for subsequent requests
@ratelimit(
    key=client_ip_key,
    rate=RATE_LIMITS["auth_endpoints"]["login"],
    method="POST",
    block=True,
)
def login(request: Request) -> Response:
    """
    Authenticate user and return tokens.
    Accepts either 'username' or 'email' as the identifier.
    """
    # Support both 'username' and 'email' fields for flexibility
    username = request.data.get("username") or request.data.get("email")
    password = request.data.get("password")

    if not username or not password:
        return create_error_response(
            "MISSING_CREDENTIALS",
            "Missing credentials",
            "Email/username and password are required",
            status.HTTP_400_BAD_REQUEST,
        )

    # Check if account is locked (before authentication attempt)
    is_locked, time_remaining = SecurityMonitor.is_account_locked(username)
    if is_locked:
        minutes_remaining = (time_remaining or 0) // 60
        return create_error_response(
            "ACCOUNT_LOCKED",
            "Account temporarily locked",
            f"Too many failed login attempts. Please try again in {minutes_remaining} minutes.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # SECURITY FIX (Issue #183 - CWE-204): Constant-time authentication
    # Always compute password hash to prevent timing attacks that reveal user existence
    from django.contrib.auth.hashers import check_password

    user = None
    user_obj = None

    # Try to find user by username first
    try:
        user_obj = User.objects.get(username=username)
    except User.DoesNotExist:
        # If username not found and identifier looks like email, try email lookup
        if "@" in username:
            try:
                user_obj = User.objects.get(email=username)
            except User.DoesNotExist:
                pass

    # Always perform password check (constant time)
    if user_obj:
        # Real user: check actual password hash
        if check_password(password, user_obj.password):
            user = user_obj
    else:
        # No user found: compute dummy hash to prevent timing oracle
        # This ensures both paths (user exists / doesn't exist) take similar time
        from django.contrib.auth.hashers import make_password

        dummy_hash = make_password(password)
        user = None  # Explicitly set to None after dummy computation

    if user:
        if user.is_active:
            # Clear failed attempts on successful login
            SecurityMonitor._clear_failed_attempts(username)

            # Track successful login
            ip_address = SecurityMonitor._get_client_ip(request)
            SecurityMonitor.track_successful_login(user, ip_address)

            # Update last_login (Django's login() does this automatically but we use JWT)
            from django.contrib.auth.models import update_last_login

            # The signal receiver ignores its sender; Django passes the model.
            update_last_login(None, user)  # type: ignore[arg-type]

            # Create response with user data
            response = Response(
                {"message": "Login successful", "user": UserSerializer(user).data},
                status=status.HTTP_200_OK,
            )

            # Set JWT tokens as httpOnly cookies
            response = set_jwt_cookies(response, user)

            return response
        else:
            # Log disabled account access attempt
            log_security_event(
                "disabled_account_access",
                user,
                {"ip": SecurityMonitor._get_client_ip(request)},
                request,
            )
            return create_error_response(
                "ACCOUNT_DISABLED",
                "Account disabled",
                "This account has been disabled",
                status.HTTP_403_FORBIDDEN,
            )

    # Failed login - track attempt and check for lockout
    ip_address = SecurityMonitor._get_client_ip(request)
    account_locked, attempts_count = SecurityMonitor.track_failed_login_attempt(
        username, ip_address
    )
    # Per-IP brute-force tracking (the per-username lockout is above). The
    # view holds the identifier it resolved and the client IP, so it reports
    # here instead of SecurityMiddleware re-parsing the body on a 401 (todo
    # 435). Every rejected credential counts, including the one that locks
    # the account (the 429 below). Neither early return is a rejected
    # credential, so neither counts: the locked one comes before the password
    # is checked, the disabled one after it matched. A wrong password on a
    # disabled account falls through to here and counts (todo 553 finding 5,
    # pinned by LoginTrackerPlacementTests).
    SecurityMonitor.track_failed_login(ip_address, username)

    if account_locked:
        return create_error_response(
            "ACCOUNT_LOCKED",
            "Account locked",
            "Too many failed login attempts. Your account has been temporarily locked for security. Check your email for details.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    return create_error_response(
        "INVALID_CREDENTIALS",
        "Invalid credentials",
        "Username or password is incorrect",
        status.HTTP_401_UNAUTHORIZED,
    )


@vs.CURRENT_USER_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def current_user(request: Request) -> Response:
    """
    Get current authenticated user information.
    """
    # The request in context makes `avatar` an absolute URL on local storage
    # too (a bare "/media/..." path is not loadable by the mobile app) and
    # fills `avatar_thumbnail`, which is null without it (todo 455).
    serializer = UserProfileSerializer(request.user, context={"request": request})
    return Response(serializer.data)


@vs.UPDATE_PROFILE_SCHEMA
@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
@core_ratelimit.ratelimit(
    key="user",
    rate=RATE_LIMITS["user_features"]["profile_updates"],
    method="PATCH",
    block=True,
)
def update_profile(request: Request) -> Response:
    """
    Update current user's profile.

    A refusal is the API's error envelope (``message`` plus the field
    ``errors``), not the bare field map: the mobile client reads only
    ``message``/``detail``/``error``, and showed every avatar refusal as "Bad
    Request" (todo 565 finding 1). A replaced avatar is deleted with its
    thumbnail, and the user is throttled (todo 565 finding 2).
    """
    previous_avatar = avatar_file_names(request.user)
    serializer = UserProfileSerializer(
        request.user, data=request.data, partial=True, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    if previous_avatar and previous_avatar[0] != (user.avatar.name or ""):
        delete_avatar_files_on_commit(user, previous_avatar)
    return Response(
        {"message": "Profile updated successfully", "user": serializer.data}
    )


@vs.DELETE_AVATAR_SCHEMA
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
@core_ratelimit.ratelimit(
    key="user",
    rate=RATE_LIMITS["user_features"]["profile_updates"],
    method="DELETE",
    block=True,
)
def delete_avatar(request: Request) -> Response:
    """Remove the current user's avatar and delete its files (todo 565
    finding 9). Idempotent: with no avatar it changes nothing."""
    user = request.user
    previous_avatar = avatar_file_names(user)
    if previous_avatar:
        user.avatar = None
        user.save(update_fields=["avatar"])
        delete_avatar_files_on_commit(user, previous_avatar)
    serializer = UserProfileSerializer(user, context={"request": request})
    return Response({"message": "Profile photo removed", "user": serializer.data})


@vs.LOGOUT_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@csrf_protect
def logout(request: Request) -> Response:
    """
    Logout user by clearing httpOnly cookies and blacklisting refresh token.
    """
    try:
        # Get refresh token from cookie or request data
        refresh_token = RefreshTokenFromCookie.get_refresh_token(request)
        if refresh_token:
            # simplejwt hints Token, but decodes an encoded token string.
            token = RefreshToken(refresh_token)  # type: ignore[arg-type]
            token.blacklist()

        # Create response
        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)

        # Clear JWT cookies
        response = clear_jwt_cookies(response)

        return response
    except Exception as e:
        logger.error(f"[AUTH] Logout failed: {str(e)}")
        # Still clear cookies even if blacklisting fails
        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        response = clear_jwt_cookies(response)
        return response


@vs.TOKEN_REFRESH_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@csrf_protect  # CRITICAL: Validates CSRF for ALL POST requests (not just cookie-based)
@ratelimit(
    key=client_ip_key,
    rate=RATE_LIMITS["auth_endpoints"]["token_refresh"],
    method="POST",
    block=True,
)
def token_refresh(request: Request) -> Response:
    """
    Refresh JWT access token using refresh token from cookie or request data.

    SECURITY: CSRF protection is enforced via @csrf_protect decorator for ALL requests.
    This prevents CSRF attacks regardless of whether the refresh token comes from
    cookies or POST data.

    Implements token rotation by blacklisting the used token and issuing a new one.
    """
    # CSRF is now enforced by @csrf_protect decorator for all POST requests
    # No need for manual CSRF check here

    # Get refresh token from cookie or request data
    refresh_token = RefreshTokenFromCookie.get_refresh_token(request)

    if not refresh_token:
        return create_error_response(
            "MISSING_REFRESH_TOKEN",
            "Missing refresh token",
            "Refresh token is required in cookie or request body",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Parse and validate provided refresh token
        # simplejwt hints Token, but decodes an encoded token string.
        used_refresh = RefreshToken(refresh_token)  # type: ignore[arg-type]

        # OPTIMIZATION: Fetch user early to avoid multiple queries
        # This prevents N+1 queries by loading the user once at the beginning
        user_id = used_refresh["user_id"]
        user = User.objects.only("id", "username", "email").get(id=user_id)

        # A refresh is a sign-in for expire_unverified_accounts (todo 485).
        # The cron runs flushexpiredtokens first, which deletes the rotated
        # token rows, so this stamp is the activity signal that survives. Not
        # last_login: Django's password-reset token hashes it.
        #
        # Stamp BEFORE blacklisting (todo 627 item 3). RefreshToken() above
        # already refused an invalid or blacklisted token, so only a live
        # token gets here. Stamped first, there is no moment where the old
        # token is burned, the new one not yet written and the stamp missing,
        # which a cron re-check could read as "never came back". A failed
        # stamp is logged and the refresh goes on: the web client logs out on
        # any non-2xx refresh, and the next successful refresh restamps.
        try:
            User.objects.filter(pk=user.pk).update(last_token_refresh=timezone.now())
        except Exception as e:
            logger.error(f"[AUTH] last_token_refresh stamp failed: {str(e)}")

        # CRITICAL SECURITY: Blacklist MUST succeed before issuing new tokens
        # If blacklisting fails, the old refresh token remains valid
        # This creates a security window where both old and new tokens work
        try:
            used_refresh.blacklist()
        except Exception as e:
            # Blacklist failures are CRITICAL security issues
            logger.error(
                f"[SECURITY] CRITICAL: Token blacklist failed during refresh: {str(e)}"
            )
            logger.error(
                f"[SECURITY] User: {user.id}, Token ID: {used_refresh.get('jti', 'unknown')}"
            )
            # DO NOT issue new tokens if blacklist fails
            return create_error_response(
                "TOKEN_BLACKLIST_FAILED",
                "Token refresh service temporarily unavailable",
                "Please try again in a moment or contact support if the issue persists",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Issue a fresh token pair only after successful blacklisting
        response = Response(
            {"message": "Token refreshed successfully"}, status=status.HTTP_200_OK
        )
        response = set_jwt_cookies(response, user)
        return response
    except User.DoesNotExist:
        logger.error("[AUTH] User not found for token refresh")
        return create_error_response(
            "INVALID_REFRESH_TOKEN",
            "Invalid refresh token",
            "The provided refresh token is not valid",
            status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        logger.error(f"[AUTH] Token refresh failed: {str(e)}")
        return create_error_response(
            "TOKEN_REFRESH_FAILED",
            "Invalid refresh token",
            "Token refresh failed. Please log in again.",
            status.HTTP_401_UNAUTHORIZED,
        )


@vs.COLLECTIONS_LIST_SCHEMA
@vs.COLLECTIONS_CREATE_SCHEMA
@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def user_collections(request: Request) -> Response:
    """
    List all collections for the current user or create a new one.
    """
    if request.method == "GET":
        collections = UserPlantCollection.objects.filter(
            user=request.user
        ).select_related("user")
        from .serializers import UserPlantCollectionSerializer

        serializer = UserPlantCollectionSerializer(collections, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        from .serializers import UserPlantCollectionSerializer

        serializer = UserPlantCollectionSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@vs.COLLECTION_RETRIEVE_SCHEMA
@vs.COLLECTION_UPDATE_SCHEMA
@vs.COLLECTION_DELETE_SCHEMA
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def user_collection_detail(request: Request, collection_id: int) -> Response:
    """
    Retrieve, update or delete a specific collection.
    """
    try:
        collection = UserPlantCollection.objects.select_related("user").get(
            id=collection_id, user=request.user
        )
    except UserPlantCollection.DoesNotExist:
        return Response(
            {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        from .serializers import UserPlantCollectionSerializer

        serializer = UserPlantCollectionSerializer(collection)
        return Response(serializer.data)

    elif request.method == "PUT":
        from .serializers import UserPlantCollectionSerializer

        serializer = UserPlantCollectionSerializer(
            collection, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        collection.delete()
        # A 204 has no body (todo 599 item 5): the message it used to carry
        # was undocumented, and HTTP clients may drop it anyway.
        return Response(status=status.HTTP_204_NO_CONTENT)


@vs.PREVIOUS_SEARCHES_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def previous_searches(request: Request) -> Response:
    """
    Get user's previous plant identification searches.
    """
    from apps.plant_identification.models import (
        PlantIdentificationRequest,
        PlantIdentificationResult,
        PlantIdentificationVote,
    )
    from apps.plant_identification.serializers import (
        PlantIdentificationRequestWithResultsSerializer,
    )
    from django.db.models import CharField, OuterRef, Prefetch, Subquery

    # Annotate results with the current user's vote to avoid N+1 in get_user_vote()
    annotated_results = PlantIdentificationResult.objects.annotate(
        user_vote_annotation=Subquery(
            PlantIdentificationVote.objects.filter(
                user=request.user,
                result=OuterRef("pk"),
            ).values("vote_type")[:1],
            output_field=CharField(),
        )
    ).select_related("identified_species")

    # Get user's identification requests ordered by date
    searches = (
        PlantIdentificationRequest.objects.filter(user=request.user)
        .select_related("assigned_to_collection")
        .prefetch_related(
            Prefetch("identification_results", queryset=annotated_results),
        )
        .order_by("-created_at")
    )

    # Pagination
    from django.core.paginator import Paginator

    paginator = Paginator(searches, 10)  # 10 searches per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    serializer = PlantIdentificationRequestWithResultsSerializer(
        page_obj.object_list, many=True, context={"request": request}
    )

    return Response(
        {
            "results": serializer.data,
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_results": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
        }
    )


@vs.SEARCH_DETAIL_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def search_detail(request: Request, request_id: uuid.UUID) -> Response:
    """
    Get detailed information about a specific search/identification request.
    """
    from apps.plant_identification.models import PlantIdentificationRequest
    from apps.plant_identification.serializers import (
        PlantIdentificationRequestSerializer,
    )

    try:
        search = (
            PlantIdentificationRequest.objects.select_related("assigned_to_collection")
            .prefetch_related(
                "identification_results__identified_species",
                "identification_results__identified_by",
            )
            .get(request_id=request_id, user=request.user)
        )
    except PlantIdentificationRequest.DoesNotExist:
        return Response({"error": "Search not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = PlantIdentificationRequestSerializer(search)
    return Response(serializer.data)


@vs.DASHBOARD_STATS_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request: Request) -> Response:
    """
    Get the signed-in user's forum dashboard statistics.

    Returns ``forum_stats`` (live topic/reply totals and 30-day counts) and
    ``recent_activity`` (up to 2 recent topics + 2 recent replies, newest
    first). Five queries: the view-restriction lookup behind ``.public()``,
    two aggregates and two ``select_related`` lists.

    ``total_posts`` / ``posts_this_month`` count REPLIES only (todo 439,
    owner decision 2026-09-28): an opening post is already counted by the
    topic totals beside them, and the web card is labelled "Replies". The
    wire names are kept so no client breaks.

    Todo 411 removed ``plant_stats``, the ``plant_identification`` activity
    entries and ``total_activity_score``. They read
    ``PlantIdentificationRequest`` / ``SavedCareInstructions``, whose only
    writer is the broken demo seeder (todo 412), so every value was a
    permanent zero. Re-add them together with a real write path.
    """
    from datetime import timedelta

    from django.db.models import Count, Q
    from wagtail_forum.models import ForumBoard, Post, Topic

    thirty_days_ago = timezone.now() - timedelta(days=30)
    # Only what the forum itself would show (PR #821 review): a topic on a
    # live, unrestricted board, and a post in such a live topic. Mirrors the
    # package's api.views._visible_boards() and its own post recount
    # (live=True, topic__live=True), so a taken-down topic's replies stop
    # counting and never link to a 404.
    visible_boards = ForumBoard.objects.live().public()
    my_topics = Topic.objects.filter(
        author=request.user, live=True, board__in=visible_boards
    )
    # Replies only (todo 439): opening posts are the topics counted above.
    # Not ForumProfile.post_count: that counter includes opening posts and
    # posts on unpublished/restricted boards, and has no 30-day window.
    my_replies = Post.objects.filter(
        author=request.user,
        live=True,
        is_opening_post=False,
        topic__live=True,
        topic__board__in=visible_boards,
    )

    # One aggregation query per model.
    forum_aggregation = my_topics.aggregate(
        total_topics=Count("pk"),
        topics_this_month=Count("pk", filter=Q(created_at__gte=thirty_days_ago)),
    )
    post_aggregation = my_replies.aggregate(
        total_posts=Count("pk"),
        posts_this_month=Count("pk", filter=Q(created_at__gte=thirty_days_ago)),
    )

    forum_stats = {
        "total_topics": forum_aggregation["total_topics"],
        "total_posts": post_aggregation["total_posts"],
        "topics_this_month": forum_aggregation["topics_this_month"],
        "posts_this_month": post_aggregation["posts_this_month"],
    }

    recent_activity = []

    def _forum_topic_url(topic):
        board = topic.board
        return f"/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}"

    # select_related prevents an N+1 on the board FK.
    recent_topics = my_topics.select_related("board").order_by("-created_at", "-pk")[:2]

    for topic in recent_topics:
        recent_activity.append(
            {
                "type": "forum_topic",
                "title": f"Created topic: {topic.title}",
                "description": f"in {topic.board.title}",
                "timestamp": topic.created_at,
                "url": _forum_topic_url(topic),
                "icon": "message-circle",
            }
        )

    # select_related prevents an N+1 on the topic/board FKs.
    recent_posts = my_replies.select_related("topic", "topic__board").order_by(
        "-created_at", "-pk"
    )[:2]

    for post in recent_posts:
        recent_activity.append(
            {
                "type": "forum_post",
                "title": f"Replied to: {post.topic.title}",
                "description": f"in {post.topic.board.title}",
                "timestamp": post.created_at,
                "url": f"{_forum_topic_url(post.topic)}#post-{post.pk}",
                "icon": "message-square",
            }
        )

    recent_activity.sort(key=lambda x: x["timestamp"], reverse=True)

    return Response(
        {
            "forum_stats": forum_stats,
            "recent_activity": recent_activity,
        }
    )


# === Push Notification Endpoints ===


@vs.SUBSCRIBE_PUSH_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key="user",
    rate=RATE_LIMITS["user_features"]["push_notifications"],
    method="POST",
    block=True,
)
def subscribe_push_notifications(request: Request) -> Response:
    """
    Subscribe user to push notifications.
    """
    from .services import NotificationService
    from .web_push import clean_subscription

    # Validated before storing: sending a push POSTs to the endpoint, so an
    # unchecked one is SSRF (todo 413).
    subscription_data = clean_subscription(request.data.get("subscription"))
    if not subscription_data:
        return Response(
            {
                "error": "A browser push subscription (an https endpoint on a "
                "known push service, with p256dh and auth keys) is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        subscription = NotificationService.subscribe_to_push(
            user=request.user,
            subscription_data=subscription_data,
            user_agent=user_agent,
        )

        return Response(
            {
                "message": "Successfully subscribed to push notifications",
                "subscription_id": subscription.id,
                "device_name": subscription.device_name,
            },
            status=status.HTTP_201_CREATED,
        )

    except IntegrityError:
        # Lost the endpoint race twice (todo 628 item 3): a conflict the
        # client can retry, not a server fault.
        return Response(
            {"error": "Subscription changed concurrently; retry"},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        logger.error(
            f"[PUSH] Push subscription failed for {log_safe_user_context(request.user)}: {e}"
        )
        return Response(
            {"error": "Failed to subscribe to push notifications"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# CSRF-exempt by design (todo 456, owner decision 2026-10-11). The caller is
# the service worker's `pushsubscriptionchange` handler: a worker has no
# document.cookie and so no CSRF token, and when the event fires there may be
# no page open at all. `authentication_classes([])` means no session or JWT
# cookie is read, so a cross-site POST carries no ambient authority. The
# credential is the old subscription itself: its endpoint plus its `auth`
# secret, compared in constant time. Same SSRF allowlist on the new endpoint
# as subscribe; one 404 for "no row" and "wrong secret"; rate-limited per IP.
@vs.RESUBSCRIBE_PUSH_SCHEMA
@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    key=client_ip_key, rate=RATE_LIMIT_PUSH_RESUBSCRIBE, method="POST", block=True
)
def resubscribe_push_notifications(request: Request) -> Response:
    """Replace a browser's push subscription after the browser changed it."""
    from .services import NotificationService
    from .web_push import clean_subscription

    # A JSON array or scalar body makes request.data a list or str: treat it
    # as empty, so it is a 400 and not an AttributeError 500 (todo 602).
    data = request.data if isinstance(request.data, dict) else {}
    old = data.get("old_subscription")
    old = old if isinstance(old, dict) else {}
    subscription_data = clean_subscription(data.get("subscription"))
    if not subscription_data:
        return Response(
            {
                "error": "A browser push subscription (an https endpoint on a "
                "known push service, with p256dh and auth keys) is required."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        subscription = NotificationService.resubscribe_push(
            old.get("endpoint"),
            old.get("auth"),
            subscription_data,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
    except IntegrityError:
        # The new endpoint was taken by other accounts twice running (todo
        # 628 item 3). Everything rolled back, the old row included, so the
        # worker can retry.
        return Response(
            {"error": "Subscription changed concurrently; retry"},
            status=status.HTTP_409_CONFLICT,
        )
    if subscription is None:
        return Response(
            {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
        )
    return Response({"message": "Push subscription replaced"})


@vs.UNSUBSCRIBE_PUSH_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def unsubscribe_push_notifications(request: Request) -> Response:
    """
    Unsubscribe from push notifications.
    """
    from .services import NotificationService

    endpoint = request.data.get("endpoint")
    if not endpoint:
        return Response(
            {"error": "Endpoint is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    success = NotificationService.unsubscribe_from_push(request.user, endpoint)

    if success:
        return Response(
            {"message": "Successfully unsubscribed from push notifications"}
        )
    else:
        return Response(
            {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
        )


@vs.PUSH_PUBLIC_KEY_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def push_public_key(request: Request) -> Response:
    """The VAPID public key a browser subscribes with (todo 413).

    ``enabled`` is false when either half of the key pair, or the claims
    email, is missing: the web app then offers no browser notifications rather
    than a subscription the server could never send to.
    """
    from django.conf import settings

    from .services import web_push_enabled

    public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    enabled = web_push_enabled()
    return Response({"enabled": enabled, "public_key": public_key if enabled else ""})


@vs.PUSH_SUBSCRIPTIONS_SCHEMA
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def push_subscriptions(request: Request) -> Response:
    """
    Get user's current push subscriptions.
    """
    subscriptions = request.user.push_subscriptions.filter(is_active=True)

    subscription_data = []
    for sub in subscriptions:
        subscription_data.append(
            {
                "id": sub.id,
                "device_name": sub.device_name,
                "created_at": sub.created_at,
                "last_used": sub.last_used,
                "endpoint": (
                    sub.endpoint[:50] + "..."
                    if len(sub.endpoint) > 50
                    else sub.endpoint
                ),  # Truncate for security
                # The web app finds its own browser's row by this (todo 456):
                # an exact match that does not hand back the capability URL.
                "endpoint_sha256": hashlib.sha256(sub.endpoint.encode()).hexdigest(),
            }
        )

    return Response(
        {"subscriptions": subscription_data, "total_count": len(subscription_data)}
    )


# Onboarding Management Views


@vs.ONBOARDING_GET_SCHEMA
@vs.ONBOARDING_PATCH_SCHEMA
@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def onboarding_progress(request: Request) -> Response:
    """
    Get or update the user's onboarding progress.

    GET includes ``checklist`` (todo 412): the mobile home checklist, each
    step DERIVED from what the user has actually done, never from a flag the
    client sets. PATCH updates the stored flags, of which the client needs
    only ``completed_checklist`` (dismiss). Every flag must be a JSON boolean:
    a string "false" is truthy and used to be stored as True.
    """
    from .models import OnboardingProgress
    from .onboarding import onboarding_checklist

    progress, _ = OnboardingProgress.objects.get_or_create(user=request.user)

    if request.method == "GET":
        return Response(
            {
                "user_id": progress.user.id,
                "completed_welcome": progress.completed_welcome,
                "completed_first_tour": progress.completed_first_tour,
                "completed_tours": progress.completed_tours,
                "completed_checklist": progress.completed_checklist,
                "first_identification_completed": progress.first_identification_completed,
                "push_notifications_enabled": progress.push_notifications_enabled,
                "batch_identification_tried": progress.batch_identification_tried,
                "onboarding_completed_at": progress.onboarding_completed_at,
                "checklist": onboarding_checklist(request.user, progress),
                "created_at": progress.created_at,
                "updated_at": progress.updated_at,
            }
        )

    # first_identification_completed / first_forum_post_created are not
    # client-settable: the checklist derives its steps, so a client cannot
    # tick a step it did not do.
    boolean_fields = (
        "completed_welcome",
        "completed_first_tour",
        "completed_checklist",
        "push_notifications_enabled",
        "batch_identification_tried",
    )
    invalid = [
        field
        for field in boolean_fields
        if field in request.data and not isinstance(request.data[field], bool)
    ]
    if invalid:
        return Response(
            {"error": "These fields must be true or false.", "fields": invalid},
            status=status.HTTP_400_BAD_REQUEST,
        )

    update_fields = []
    for field in boolean_fields:
        if field in request.data:
            setattr(progress, field, request.data[field])
            update_fields.append(field)

    if "completed_tours" in request.data:
        if not isinstance(request.data["completed_tours"], list):
            return Response(
                {
                    "error": "completed_tours must be a list.",
                    "fields": ["completed_tours"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        progress.completed_tours = request.data["completed_tours"]
        update_fields.append("completed_tours")

    if "onboarding_completed_at" in request.data:
        from django.utils.dateparse import parse_datetime

        raw = request.data["onboarding_completed_at"]
        try:
            # parse_datetime returns None for garbage and RAISES for a
            # well-formed but impossible date (2026-13-01): both are a 400,
            # never a 500 or a silently cleared timestamp.
            completed_at = parse_datetime(raw) if isinstance(raw, str) else None
        except ValueError:
            completed_at = None
        if completed_at is None:
            return Response(
                {
                    "error": "onboarding_completed_at must be an ISO 8601 datetime.",
                    "fields": ["onboarding_completed_at"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        progress.onboarding_completed_at = completed_at
        update_fields.append("onboarding_completed_at")

    if update_fields:
        update_fields.append("updated_at")
        progress.save(update_fields=update_fields)

    return Response(
        {
            "message": "Onboarding progress updated successfully",
            "checklist": onboarding_checklist(request.user, progress),
        }
    )


@vs.TRACK_ONBOARDING_EVENT_SCHEMA
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key="user", rate=RATE_LIMIT_ONBOARDING_EVENT, method="POST", block=True)
def track_onboarding_event(request: Request) -> Response:
    """
    Track onboarding events for analytics and optimization.
    """
    from .models import OnboardingAnalytics

    event_type = request.data.get("event_type")
    event_data = request.data.get("event_data", {})
    page_url = request.data.get("page_url", "")

    if not event_type:
        return Response(
            {"error": "event_type is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        OnboardingAnalytics.log_event(
            user=request.user,
            action_type=event_type,
            event_data=event_data,
            page_url=page_url,
        )

        return Response({"message": "Event tracked successfully"})

    except Exception as e:
        logger.error(f"[ONBOARDING] Error tracking onboarding event: {str(e)}")
        return Response(
            {"error": "Failed to track event"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
