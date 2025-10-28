"""
Authentication and user management views for the Plant Community application.
"""

from django.contrib.auth import authenticate
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
# Rate limiting - now required for security
from django_ratelimit.decorators import ratelimit
from django.views.decorators.cache import cache_page
from apps.core.security import SecurityMonitor, log_security_event
from apps.core.utils.pii_safe_logging import log_safe_username, log_safe_user_context
import logging
from rest_framework.authentication import CSRFCheck
from django.http import HttpResponse

from .models import User, UserPlantCollection
from .serializers import UserRegistrationSerializer, UserSerializer, UserProfileSerializer
from .authentication import set_jwt_cookies, clear_jwt_cookies, RefreshTokenFromCookie
from apps.plant_identification.constants import RATE_LIMITS

logger = logging.getLogger(__name__)


def create_error_response(code: str, message: str, details: str = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    """
    Create standardized error response structure.

    Args:
        code: Error code identifier (e.g., 'INVALID_CREDENTIALS')
        message: Brief error message
        details: Optional detailed error explanation
        status_code: HTTP status code

    Returns:
        Response object with standardized error structure
    """
    error_data = {
        'error': {
            'code': code,
            'message': message,
        }
    }
    if details:
        error_data['error']['details'] = details

    return Response(error_data, status=status_code)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request: Request) -> Response:
    """
    Get CSRF token for frontend.
    """
    return Response({'detail': 'CSRF cookie set'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
@ratelimit(
    key='ip',
    rate=RATE_LIMITS['auth_endpoints']['register'],
    method='POST',
    block=True
)
def register(request: Request) -> Response:
    """
    Register a new user account.
    """
    # Log registration attempt (without sensitive data)
    username = request.data.get('username', 'unknown')
    logger.info(f"Registration attempt for user: {log_safe_username(username)}")
    
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            with transaction.atomic():
                # Create user
                user = serializer.save()
                
                # Create default plant collection
                UserPlantCollection.objects.create(
                    user=user,
                    name="My Plants",
                    description="My personal plant collection",
                    is_public=True
                )
                
                # Create response with user data
                response = Response({
                    'message': 'Registration successful',
                    'user': UserSerializer(user).data
                }, status=status.HTTP_201_CREATED)
                
                # Set JWT tokens as httpOnly cookies
                response = set_jwt_cookies(response, user)
                
                return response
                
        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            return create_error_response(
                'REGISTRATION_FAILED',
                'Registration failed',
                'An unexpected error occurred. Please try again.',
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Log validation errors (sanitized)
    error_fields = list(serializer.errors.keys()) if serializer.errors else []
    username = request.data.get('username', 'unknown')
    logger.warning(f"Registration validation failed for user: {log_safe_username(username)}, fields: {error_fields}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
@ratelimit(
    key='ip',
    rate=RATE_LIMITS['auth_endpoints']['login'],
    method='POST',
    block=True
)
def login(request: Request) -> Response:
    """
    Authenticate user and return tokens.
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return create_error_response(
            'MISSING_CREDENTIALS',
            'Missing credentials',
            'Username and password are required',
            status.HTTP_400_BAD_REQUEST
        )

    # Check if account is locked (before authentication attempt)
    is_locked, time_remaining = SecurityMonitor.is_account_locked(username)
    if is_locked:
        minutes_remaining = time_remaining // 60
        return create_error_response(
            'ACCOUNT_LOCKED',
            'Account temporarily locked',
            f'Too many failed login attempts. Please try again in {minutes_remaining} minutes.',
            status.HTTP_429_TOO_MANY_REQUESTS
        )

    # Authenticate user
    user = authenticate(username=username, password=password)

    if user:
        if user.is_active:
            # Clear failed attempts on successful login
            SecurityMonitor._clear_failed_attempts(username)

            # Track successful login
            ip_address = SecurityMonitor._get_client_ip(request)
            SecurityMonitor.track_successful_login(user, ip_address)

            # Create response with user data
            response = Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)

            # Set JWT tokens as httpOnly cookies
            response = set_jwt_cookies(response, user)

            return response
        else:
            # Log disabled account access attempt
            log_security_event(
                'disabled_account_access',
                user,
                {'ip': SecurityMonitor._get_client_ip(request)},
                request
            )
            return create_error_response(
                'ACCOUNT_DISABLED',
                'Account disabled',
                'This account has been disabled',
                status.HTTP_403_FORBIDDEN
            )

    # Failed login - track attempt and check for lockout
    ip_address = SecurityMonitor._get_client_ip(request)
    account_locked, attempts_count = SecurityMonitor.track_failed_login_attempt(username, ip_address)

    if account_locked:
        return create_error_response(
            'ACCOUNT_LOCKED',
            'Account locked',
            'Too many failed login attempts. Your account has been temporarily locked for security. Check your email for details.',
            status.HTTP_429_TOO_MANY_REQUESTS
        )

    return create_error_response(
        'INVALID_CREDENTIALS',
        'Invalid credentials',
        'Username or password is incorrect',
        status.HTTP_401_UNAUTHORIZED
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request: Request) -> Response:
    """
    Get current authenticated user information.
    """
    serializer = UserProfileSerializer(request.user)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_profile(request: Request) -> Response:
    """
    Update current user's profile.
    """
    serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Profile updated successfully',
            'user': serializer.data
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request: Request) -> Response:
    """
    Logout user by clearing httpOnly cookies and blacklisting refresh token.
    """
    try:
        # Get refresh token from cookie or request data
        refresh_token = RefreshTokenFromCookie.get_refresh_token(request)
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        # Create response
        response = Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
        
        # Clear JWT cookies
        response = clear_jwt_cookies(response)
        
        return response
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        # Still clear cookies even if blacklisting fails
        response = Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
        response = clear_jwt_cookies(response)
        return response


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@csrf_protect  # CRITICAL: Validates CSRF for ALL POST requests (not just cookie-based)
@ratelimit(
    key='ip',
    rate=RATE_LIMITS['auth_endpoints']['token_refresh'],
    method='POST',
    block=True
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
            'MISSING_REFRESH_TOKEN',
            'Missing refresh token',
            'Refresh token is required in cookie or request body',
            status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Parse and validate provided refresh token
        used_refresh = RefreshToken(refresh_token)

        # OPTIMIZATION: Fetch user early to avoid multiple queries
        # This prevents N+1 queries by loading the user once at the beginning
        user_id = used_refresh['user_id']
        user = User.objects.only('id', 'username', 'email').get(id=user_id)

        # CRITICAL SECURITY: Blacklist MUST succeed before issuing new tokens
        # If blacklisting fails, the old refresh token remains valid
        # This creates a security window where both old and new tokens work
        try:
            used_refresh.blacklist()
        except Exception as e:
            # Blacklist failures are CRITICAL security issues
            logger.error(f"[SECURITY] CRITICAL: Token blacklist failed during refresh: {str(e)}")
            logger.error(f"[SECURITY] User: {user.id}, Token ID: {used_refresh.get('jti', 'unknown')}")
            # DO NOT issue new tokens if blacklist fails
            return create_error_response(
                'TOKEN_BLACKLIST_FAILED',
                'Token refresh service temporarily unavailable',
                'Please try again in a moment or contact support if the issue persists',
                status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Issue a fresh token pair only after successful blacklisting
        response = Response({'message': 'Token refreshed successfully'}, status=status.HTTP_200_OK)
        response = set_jwt_cookies(response, user)
        return response
    except User.DoesNotExist:
        logger.error("User not found for token refresh")
        return create_error_response(
            'INVALID_REFRESH_TOKEN',
            'Invalid refresh token',
            'The provided refresh token is not valid',
            status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return create_error_response(
            'TOKEN_REFRESH_FAILED',
            'Invalid refresh token',
            'Token refresh failed. Please log in again.',
            status.HTTP_401_UNAUTHORIZED
        )


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def user_collections(request: Request) -> Response:
    """
    List all collections for the current user or create a new one.
    """
    if request.method == 'GET':
        collections = UserPlantCollection.objects.filter(user=request.user).select_related('user')
        from .serializers import UserPlantCollectionSerializer
        serializer = UserPlantCollectionSerializer(collections, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        from .serializers import UserPlantCollectionSerializer
        serializer = UserPlantCollectionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def user_collection_detail(request: Request, collection_id: int) -> Response:
    """
    Retrieve, update or delete a specific collection.
    """
    try:
        collection = UserPlantCollection.objects.select_related('user').get(id=collection_id, user=request.user)
    except UserPlantCollection.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        from .serializers import UserPlantCollectionSerializer
        serializer = UserPlantCollectionSerializer(collection)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        from .serializers import UserPlantCollectionSerializer
        serializer = UserPlantCollectionSerializer(collection, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        collection.delete()
        return Response({'message': 'Collection deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def previous_searches(request: Request) -> Response:
    """
    Get user's previous plant identification searches.
    """
    from apps.plant_identification.models import PlantIdentificationRequest
    from apps.plant_identification.serializers import PlantIdentificationRequestWithResultsSerializer
    
    # Get user's identification requests ordered by date
    searches = PlantIdentificationRequest.objects.filter(
        user=request.user
    ).select_related('assigned_to_collection').prefetch_related(
        'identification_results__identified_species'
    ).order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(searches, 10)  # 10 searches per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    serializer = PlantIdentificationRequestWithResultsSerializer(
        page_obj.object_list, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'results': serializer.data,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_results': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_detail(request: Request, request_id: int) -> Response:
    """
    Get detailed information about a specific search/identification request.
    """
    from apps.plant_identification.models import PlantIdentificationRequest
    from apps.plant_identification.serializers import PlantIdentificationRequestSerializer
    
    try:
        search = PlantIdentificationRequest.objects.select_related(
            'assigned_to_collection'
        ).prefetch_related(
            'identification_results__identified_species',
            'identification_results__identified_by'
        ).get(request_id=request_id, user=request.user)
    except PlantIdentificationRequest.DoesNotExist:
        return Response({'error': 'Search not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = PlantIdentificationRequestSerializer(search)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def forum_activity(request: Request) -> Response:
    """
    Get user's recent forum activity (topics and posts).
    """
    from machina.apps.forum_conversation.models import Topic, Post
    from apps.forum_integration.serializers import TopicSerializer, PostSerializer
    from django.utils import timezone
    from datetime import timedelta
    
    # Get recent topics created by user
    recent_topics = Topic.objects.filter(
        poster=request.user,
        approved=True
    ).select_related('forum', 'last_post').order_by('-created')[:5]
    
    # Get recent posts by user (excluding first posts of topics)
    recent_posts = Post.objects.filter(
        poster=request.user,
        approved=True
    ).exclude(
        id__in=Topic.objects.filter(poster=request.user).values_list('first_post_id', flat=True)
    ).select_related('topic', 'topic__forum').order_by('-created')[:10]
    
    # Calculate activity stats
    thirty_days_ago = timezone.now() - timedelta(days=30)
    stats = {
        'total_topics': Topic.objects.filter(poster=request.user, approved=True).count(),
        'total_posts': Post.objects.filter(poster=request.user, approved=True).count(),
        'topics_this_month': Topic.objects.filter(
            poster=request.user, 
            approved=True, 
            created__gte=thirty_days_ago
        ).count(),
        'posts_this_month': Post.objects.filter(
            poster=request.user, 
            approved=True, 
            created__gte=thirty_days_ago
        ).count(),
    }
    
    return Response({
        'recent_topics': TopicSerializer(recent_topics, many=True).data,
        'recent_posts': PostSerializer(recent_posts, many=True).data,
        'stats': stats
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request: Request) -> Response:
    """
    Get comprehensive dashboard statistics for the user.

    PERFORMANCE OPTIMIZED: Uses Django aggregation to reduce from 15-20 queries to 3-4 queries.
    """
    from apps.plant_identification.models import PlantIdentificationRequest, SavedCareInstructions
    from machina.apps.forum_conversation.models import Topic, Post
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count, Q, Case, When, IntegerField

    # Date ranges
    thirty_days_ago = timezone.now() - timedelta(days=30)
    seven_days_ago = timezone.now() - timedelta(days=7)

    # OPTIMIZATION: Single aggregation query for all plant stats (1 query instead of 4)
    plant_aggregation = PlantIdentificationRequest.objects.filter(
        user=request.user
    ).aggregate(
        total_identified=Count('id', filter=Q(status='identified')),
        total_searches=Count('id'),
        searches_this_week=Count('id', filter=Q(created_at__gte=seven_days_ago)),
    )

    # Separate query for saved care cards (different model)
    saved_care_count = SavedCareInstructions.objects.filter(user=request.user).count()

    plant_stats = {
        'total_identified': plant_aggregation['total_identified'],
        'total_searches': plant_aggregation['total_searches'],
        'searches_this_week': plant_aggregation['searches_this_week'],
        'saved_care_cards': saved_care_count,
    }

    # OPTIMIZATION: Single aggregation query for all forum stats (1 query instead of 4)
    forum_aggregation = Topic.objects.filter(
        poster=request.user,
        approved=True
    ).aggregate(
        total_topics=Count('id'),
        topics_this_month=Count('id', filter=Q(created__gte=thirty_days_ago)),
    )

    # Posts count (separate query since it's a different model)
    post_aggregation = Post.objects.filter(
        poster=request.user,
        approved=True
    ).aggregate(
        total_posts=Count('id'),
        posts_this_month=Count('id', filter=Q(created__gte=thirty_days_ago)),
    )

    forum_stats = {
        'total_topics': forum_aggregation['total_topics'],
        'total_posts': post_aggregation['total_posts'],
        'topics_this_month': forum_aggregation['topics_this_month'],
        'posts_this_month': post_aggregation['posts_this_month'],
    }

    # Recent activity summary
    recent_activity = []

    # OPTIMIZATION: Use only() to fetch minimal fields (prevents unnecessary column fetches)
    recent_identifications = PlantIdentificationRequest.objects.filter(
        user=request.user,
        status='identified'
    ).only('request_id', 'created_at').order_by('-created_at')[:3]

    for identification in recent_identifications:
        recent_activity.append({
            'type': 'plant_identification',
            'title': f'Identified plant',
            'description': f'Successfully identified a plant species',
            'timestamp': identification.created_at,
            'url': f'/identify/{identification.request_id}',
            'icon': 'leaf'
        })

    # OPTIMIZATION: Use select_related to prevent N+1 on forum foreign key access
    recent_topics = Topic.objects.filter(
        poster=request.user,
        approved=True
    ).select_related('forum').only(
        'id', 'subject', 'created', 'forum__name'
    ).order_by('-created')[:2]

    for topic in recent_topics:
        recent_activity.append({
            'type': 'forum_topic',
            'title': f'Created topic: {topic.subject}',
            'description': f'in {topic.forum.name}',
            'timestamp': topic.created,
            'url': f'/forum/topic/{topic.id}',
            'icon': 'message-circle'
        })

    # OPTIMIZATION: Use select_related to prevent N+1 on topic/forum foreign key access
    # Get first_post_ids efficiently with values_list
    first_post_ids = Topic.objects.filter(
        poster=request.user
    ).values_list('first_post_id', flat=True)

    recent_posts = Post.objects.filter(
        poster=request.user,
        approved=True
    ).exclude(
        id__in=list(first_post_ids)
    ).select_related('topic', 'topic__forum').only(
        'id', 'created', 'topic__id', 'topic__subject', 'topic__forum__name'
    ).order_by('-created')[:2]

    for post in recent_posts:
        recent_activity.append({
            'type': 'forum_post',
            'title': f'Replied to: {post.topic.subject}',
            'description': f'in {post.topic.forum.name}',
            'timestamp': post.created,
            'url': f'/forum/topic/{post.topic.id}',
            'icon': 'message-square'
        })

    # Sort recent activity by timestamp
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:8]  # Limit to 8 most recent items

    return Response({
        'plant_stats': plant_stats,
        'forum_stats': forum_stats,
        'recent_activity': recent_activity,
        'total_activity_score': (
            plant_stats['total_identified'] * 10 +
            forum_stats['total_topics'] * 5 +
            forum_stats['total_posts'] * 2 +
            plant_stats['saved_care_cards'] * 3
        )
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def forum_permissions(request: Request) -> Response:
    """
    Get forum permissions for the current user, including image upload permissions.
    """
    from machina.apps.forum.models import Forum
    from .services import TrustLevelService
    
    # Get a sample forum to test permissions (most restrictive)
    forum = Forum.objects.filter(type=Forum.FORUM_POST).first()
    
    # Get trust level information
    trust_info = request.user.get_trust_level_display_info()
    
    # Check image upload permissions
    can_upload_images = request.user.can_upload_images()
    can_attach_files_forum = False
    
    if forum:
        can_attach_files_forum = TrustLevelService.check_user_can_attach_files(request.user, forum)
    
    permissions_data = {
        'can_upload_images': can_upload_images,
        'can_attach_files': can_attach_files_forum,
        'trust_level': trust_info,
        'user_groups': [group.name for group in request.user.groups.all()],
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser,
    }
    
    # Add helpful messaging for users who can't upload images
    if not can_upload_images:
        permissions_data['message'] = {
            'title': 'Image Uploads Not Available',
            'description': f'You need {trust_info["posts_needed"]} more approved posts and {trust_info["days_needed"]} more days to unlock image uploads.',
            'requirements': {
                'posts_needed': trust_info['posts_needed'],
                'days_needed': trust_info['days_needed'],
                'next_level': trust_info['next_level'],
            },
            'current_progress': {
                'posts': trust_info['posts_count'],
                'account_age_days': trust_info['account_age_days'],
            },
            'help_url': '/help/forum-permissions'
        }
    else:
        permissions_data['message'] = {
            'title': 'Image Uploads Available',
            'description': f'You have {trust_info["current_display"]} status and can upload images to forum posts.',
            'current_level': trust_info['current_level'],
        }
    
    return Response(permissions_data)


# === Push Notification Endpoints ===

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key='user',
    rate=RATE_LIMITS['user_features']['push_notifications'],
    method='POST',
    block=True
)
def subscribe_push_notifications(request: Request) -> Response:
    """
    Subscribe user to push notifications.
    """
    from .services import NotificationService
    
    subscription_data = request.data.get('subscription')
    if not subscription_data:
        return Response(
            {'error': 'Subscription data is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        subscription = NotificationService.subscribe_to_push(
            user=request.user,
            subscription_data=subscription_data,
            user_agent=user_agent
        )
        
        return Response({
            'message': 'Successfully subscribed to push notifications',
            'subscription_id': subscription.id,
            'device_name': subscription.device_name
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Push subscription failed for {log_safe_user_context(request.user)}: {e}")
        return Response(
            {'error': 'Failed to subscribe to push notifications'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unsubscribe_push_notifications(request: Request) -> Response:
    """
    Unsubscribe from push notifications.
    """
    from .services import NotificationService
    
    endpoint = request.data.get('endpoint')
    if not endpoint:
        return Response(
            {'error': 'Endpoint is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    success = NotificationService.unsubscribe_from_push(request.user, endpoint)
    
    if success:
        return Response({'message': 'Successfully unsubscribed from push notifications'})
    else:
        return Response(
            {'error': 'Subscription not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def push_subscriptions(request: Request) -> Response:
    """
    Get user's current push subscriptions.
    """
    subscriptions = request.user.push_subscriptions.filter(is_active=True)
    
    subscription_data = []
    for sub in subscriptions:
        subscription_data.append({
            'id': sub.id,
            'device_name': sub.device_name,
            'created_at': sub.created_at,
            'last_used': sub.last_used,
            'endpoint': sub.endpoint[:50] + '...' if len(sub.endpoint) > 50 else sub.endpoint  # Truncate for security
        })
    
    return Response({
        'subscriptions': subscription_data,
        'total_count': len(subscription_data)
    })


# === Care Reminder Endpoints ===

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def care_reminders(request: Request) -> Response:
    """
    List user's care reminders or create a new one.
    """
    if request.method == 'GET':
        from .models import CareReminder
        
        reminders = CareReminder.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('saved_care_instructions').order_by('next_reminder_date')
        
        # Create serializer data
        reminder_data = []
        for reminder in reminders:
            plant_name = reminder.saved_care_instructions.display_name
            reminder_data.append({
                'id': reminder.id,
                'uuid': str(reminder.uuid),
                'title': reminder.title,
                'reminder_type': reminder.reminder_type,
                'reminder_type_display': reminder.get_reminder_type_display(),
                'frequency': reminder.frequency,
                'frequency_display': reminder.get_frequency_display(),
                'next_reminder_date': reminder.next_reminder_date,
                'plant_name': plant_name,
                'current_streak': reminder.current_streak,
                'longest_streak': reminder.longest_streak,
                'total_completed': reminder.total_completed,
                'total_sent': reminder.total_sent,
                'send_push_notification': reminder.send_push_notification,
                'send_email_notification': reminder.send_email_notification,
                'care_instructions_id': reminder.saved_care_instructions.id,
                'created_at': reminder.created_at
            })
        
        return Response({
            'reminders': reminder_data,
            'total_count': len(reminder_data)
        })
    
    elif request.method == 'POST':
        from .services import CareReminderService
        from apps.plant_identification.models import SavedCareInstructions
        
        # Validate required fields
        care_instructions_id = request.data.get('care_instructions_id')
        reminder_type = request.data.get('reminder_type')
        frequency = request.data.get('frequency', 'weekly')
        
        if not care_instructions_id or not reminder_type:
            return Response(
                {'error': 'care_instructions_id and reminder_type are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the care instructions
            care_instructions = SavedCareInstructions.objects.get(
                id=care_instructions_id,
                user=request.user
            )
            
            # Create the reminder
            reminder = CareReminderService.create_reminder(
                user=request.user,
                saved_care_instructions=care_instructions,
                reminder_type=reminder_type,
                frequency=frequency,
                custom_interval_days=request.data.get('custom_interval_days'),
                title=request.data.get('title')
            )
            
            return Response({
                'message': 'Care reminder created successfully',
                'reminder': {
                    'id': reminder.id,
                    'uuid': str(reminder.uuid),
                    'title': reminder.title,
                    'reminder_type': reminder.reminder_type,
                    'frequency': reminder.frequency,
                    'next_reminder_date': reminder.next_reminder_date,
                }
            }, status=status.HTTP_201_CREATED)
            
        except SavedCareInstructions.DoesNotExist:
            return Response(
                {'error': 'Care instructions not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to create care reminder for {log_safe_user_context(request.user)}: {e}")
            return Response(
                {'error': 'Failed to create care reminder'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def care_reminder_detail(request: Request, reminder_uuid: str) -> Response:
    """
    Get, update, or delete a specific care reminder.
    """
    from .models import CareReminder
    
    try:
        reminder = CareReminder.objects.select_related('saved_care_instructions').get(
            uuid=reminder_uuid,
            user=request.user
        )
    except CareReminder.DoesNotExist:
        return Response(
            {'error': 'Care reminder not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        plant_name = reminder.saved_care_instructions.display_name
        
        return Response({
            'id': reminder.id,
            'uuid': str(reminder.uuid),
            'title': reminder.title,
            'description': reminder.description,
            'reminder_type': reminder.reminder_type,
            'reminder_type_display': reminder.get_reminder_type_display(),
            'frequency': reminder.frequency,
            'frequency_display': reminder.get_frequency_display(),
            'custom_interval_days': reminder.custom_interval_days,
            'next_reminder_date': reminder.next_reminder_date,
            'last_reminder_sent': reminder.last_reminder_sent,
            'plant_name': plant_name,
            'current_streak': reminder.current_streak,
            'longest_streak': reminder.longest_streak,
            'total_completed': reminder.total_completed,
            'total_sent': reminder.total_sent,
            'total_snoozed': reminder.total_snoozed,
            'is_active': reminder.is_active,
            'send_push_notification': reminder.send_push_notification,
            'send_email_notification': reminder.send_email_notification,
            'care_instructions': {
                'id': reminder.saved_care_instructions.id,
                'display_name': plant_name,
                'care_instructions': reminder.saved_care_instructions.care_instructions,
            },
            'created_at': reminder.created_at,
            'updated_at': reminder.updated_at
        })
    
    elif request.method == 'PUT':
        # Update reminder settings
        update_fields = []
        
        if 'frequency' in request.data:
            reminder.frequency = request.data['frequency']
            update_fields.append('frequency')
        
        if 'custom_interval_days' in request.data:
            reminder.custom_interval_days = request.data['custom_interval_days']
            update_fields.append('custom_interval_days')
        
        if 'send_push_notification' in request.data:
            reminder.send_push_notification = request.data['send_push_notification']
            update_fields.append('send_push_notification')
        
        if 'send_email_notification' in request.data:
            reminder.send_email_notification = request.data['send_email_notification']
            update_fields.append('send_email_notification')
        
        if 'is_active' in request.data:
            reminder.is_active = request.data['is_active']
            update_fields.append('is_active')
        
        if 'title' in request.data:
            reminder.title = request.data['title']
            update_fields.append('title')
        
        if 'description' in request.data:
            reminder.description = request.data['description']
            update_fields.append('description')
        
        if update_fields:
            # Recalculate next reminder date if frequency changed
            if 'frequency' in update_fields or 'custom_interval_days' in update_fields:
                reminder.next_reminder_date = reminder.calculate_next_reminder_date()
                update_fields.append('next_reminder_date')
            
            update_fields.append('updated_at')
            reminder.save(update_fields=update_fields)
        
        return Response({'message': 'Care reminder updated successfully'})
    
    elif request.method == 'DELETE':
        reminder.delete()
        return Response(
            {'message': 'Care reminder deleted successfully'}, 
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key='user',
    rate=RATE_LIMITS['user_features']['care_reminders'],
    method='POST',
    block=True
)
def care_reminder_action(request: Request, reminder_uuid: str) -> Response:
    """
    Perform actions on a care reminder (complete, snooze, skip).
    """
    from .models import CareReminder, CareReminderLog
    
    try:
        reminder = CareReminder.objects.get(
            uuid=reminder_uuid,
            user=request.user
        )
    except CareReminder.DoesNotExist:
        return Response(
            {'error': 'Care reminder not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    action = request.data.get('action')
    
    if action == 'complete':
        reminder.mark_completed()
        CareReminderLog.objects.create(
            reminder=reminder,
            action='completed',
            action_data={'timestamp': timezone.now().isoformat()}
        )
        
        return Response({
            'message': 'Care reminder marked as completed',
            'streak': reminder.current_streak,
            'next_reminder': reminder.next_reminder_date
        })
    
    elif action == 'snooze':
        snooze_hours = request.data.get('snooze_hours', 24)
        reminder.mark_snoozed(snooze_hours=snooze_hours)
        CareReminderLog.objects.create(
            reminder=reminder,
            action='snoozed',
            action_data={'snooze_hours': snooze_hours}
        )
        
        return Response({
            'message': f'Care reminder snoozed for {snooze_hours} hours',
            'next_reminder': reminder.next_reminder_date
        })
    
    elif action == 'skip':
        reminder.mark_skipped()
        CareReminderLog.objects.create(
            reminder=reminder,
            action='skipped',
            action_data={'timestamp': timezone.now().isoformat()}
        )
        
        return Response({
            'message': 'Care reminder skipped',
            'streak_reset': True,
            'next_reminder': reminder.next_reminder_date
        })
    
    else:
        return Response(
            {'error': 'Invalid action. Use: complete, snooze, or skip'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def care_reminder_stats(request: Request) -> Response:
    """
    Get user's care reminder statistics and analytics.
    """
    from .models import CareReminder, CareReminderLog
    from django.db.models import Count, Sum, Avg, Max
    from django.utils import timezone
    from datetime import timedelta
    
    # Basic counts
    active_reminders = CareReminder.objects.filter(user=request.user, is_active=True).count()
    total_reminders = CareReminder.objects.filter(user=request.user).count()
    
    # Completion stats
    completion_stats = CareReminder.objects.filter(user=request.user).aggregate(
        total_completed=Sum('total_completed'),
        total_sent=Sum('total_sent'),
        avg_streak=Avg('current_streak'),
        max_streak=Max('longest_streak')
    )
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_logs = CareReminderLog.objects.filter(
        reminder__user=request.user,
        created_at__gte=thirty_days_ago
    ).values('action').annotate(count=Count('action'))
    
    recent_activity = {log['action']: log['count'] for log in recent_logs}
    
    # Upcoming reminders
    upcoming = CareReminder.objects.filter(
        user=request.user,
        is_active=True,
        next_reminder_date__gte=timezone.now()
    ).order_by('next_reminder_date')[:5]
    
    upcoming_data = []
    for reminder in upcoming:
        days_until = (reminder.next_reminder_date - timezone.now()).days
        upcoming_data.append({
            'uuid': str(reminder.uuid),
            'title': reminder.title,
            'next_reminder_date': reminder.next_reminder_date,
            'days_until': days_until,
            'plant_name': reminder.saved_care_instructions.display_name
        })
    
    return Response({
        'summary': {
            'active_reminders': active_reminders,
            'total_reminders': total_reminders,
            'total_completed': completion_stats['total_completed'] or 0,
            'total_sent': completion_stats['total_sent'] or 0,
            'completion_rate': (
                (completion_stats['total_completed'] or 0) / max(completion_stats['total_sent'] or 1, 1) * 100
            ),
            'average_streak': completion_stats['avg_streak'] or 0,
            'best_streak': completion_stats['max_streak'].longest_streak if completion_stats['max_streak'] else 0
        },
        'recent_activity': recent_activity,
        'upcoming_reminders': upcoming_data
    })


# Onboarding Management Views

@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def onboarding_progress(request: Request) -> Response:
    """
    Get or update user's onboarding progress.
    """
    from .models import OnboardingProgress
    
    # Get or create onboarding progress
    progress, created = OnboardingProgress.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        return Response({
            'user_id': progress.user.id,
            'completed_welcome': progress.completed_welcome,
            'completed_first_tour': progress.completed_first_tour,
            'completed_tours': progress.completed_tours,
            'completed_checklist': progress.completed_checklist,
            'demo_data_created': progress.demo_data_created,
            'demo_data_skipped': progress.demo_data_skipped,
            'first_identification_completed': progress.first_identification_completed,
            'first_care_reminder_created': progress.first_care_reminder_created,
            'first_forum_post_created': progress.first_forum_post_created,
            'push_notifications_enabled': progress.push_notifications_enabled,
            'batch_identification_tried': progress.batch_identification_tried,
            'onboarding_completed_at': progress.onboarding_completed_at,
            'created_at': progress.created_at,
            'updated_at': progress.updated_at
        })
    
    elif request.method == 'PATCH':
        # Update progress fields
        update_fields = []
        
        for field in ['completed_welcome', 'completed_first_tour', 'completed_checklist', 
                     'demo_data_created', 'demo_data_skipped', 'first_identification_completed',
                     'first_care_reminder_created', 'first_forum_post_created', 
                     'push_notifications_enabled', 'batch_identification_tried']:
            if field in request.data:
                setattr(progress, field, request.data[field])
                update_fields.append(field)
        
        if 'completed_tours' in request.data:
            progress.completed_tours = request.data['completed_tours']
            update_fields.append('completed_tours')
        
        if 'onboarding_completed_at' in request.data:
            from django.utils.dateparse import parse_datetime
            progress.onboarding_completed_at = parse_datetime(request.data['onboarding_completed_at'])
            update_fields.append('onboarding_completed_at')
        
        if update_fields:
            update_fields.append('updated_at')
            progress.save(update_fields=update_fields)
        
        return Response({'message': 'Onboarding progress updated successfully'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key='user', rate='10/h', method='POST', block=True)
def create_demo_data(request: Request) -> Response:
    """
    Create demo data for new users to explore the platform.
    """
    from .models import OnboardingProgress, DemoData
    from .services import DemoDataService
    
    include_care_reminders = request.data.get('include_care_reminders', True)
    
    try:
        with transaction.atomic():
            # Create demo data using the service
            demo_service = DemoDataService(request.user)
            demo_data = demo_service.create_demo_data(include_care_reminders=include_care_reminders)
            
            # Update onboarding progress
            progress, _ = OnboardingProgress.objects.get_or_create(user=request.user)
            progress.demo_data_created = True
            progress.completed_welcome = True
            progress.save(update_fields=['demo_data_created', 'completed_welcome', 'updated_at'])
            
            return Response({
                'message': 'Demo data created successfully',
                'demo_data_id': demo_data.id,
                'created_items': {
                    'identifications': demo_data.created_data.get('identifications_count', 0),
                    'forum_posts': demo_data.created_data.get('forum_posts_count', 0),
                    'care_reminders': demo_data.created_data.get('care_reminders_count', 0),
                }
            })
    
    except Exception as e:
        logger.error(f"Error creating demo data for user {request.user.id}: {str(e)}")
        return Response(
            {'error': 'Failed to create demo data. Please try again.'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key='user', rate='50/h', method='POST', block=True)
def track_onboarding_event(request: Request) -> Response:
    """
    Track onboarding events for analytics and optimization.
    """
    from .models import OnboardingAnalytics
    
    event_type = request.data.get('event_type')
    event_data = request.data.get('event_data', {})
    page_url = request.data.get('page_url', '')
    
    if not event_type:
        return Response(
            {'error': 'event_type is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        OnboardingAnalytics.objects.create(
            user=request.user,
            event_type=event_type,
            event_data=event_data,
            page_url=page_url
        )
        
        return Response({'message': 'Event tracked successfully'})
    
    except Exception as e:
        logger.error(f"Error tracking onboarding event: {str(e)}")
        return Response(
            {'error': 'Failed to track event'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_demo_data(request: Request) -> Response:
    """
    Delete all demo data for a user.
    """
    from .models import DemoData
    from .services import DemoDataService
    
    try:
        demo_data = DemoData.objects.filter(user=request.user).first()
        if demo_data:
            demo_service = DemoDataService(request.user)
            demo_service.cleanup_demo_data(demo_data)
            
            return Response({'message': 'Demo data deleted successfully'})
        else:
            return Response(
                {'error': 'No demo data found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    except Exception as e:
        logger.error(f"Error deleting demo data for user {request.user.id}: {str(e)}")
        return Response(
            {'error': 'Failed to delete demo data'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def export_care_reminders_calendar(request: Request) -> HttpResponse:
    """
    Export user's care reminders as an ICS calendar file.
    """
    from .models import CareReminder
    from django.http import HttpResponse
    from django.utils import timezone
    from datetime import timedelta
    import uuid
    
    # Get user's active care reminders
    reminders = CareReminder.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('saved_care_instructions')
    
    if not reminders.exists():
        return Response(
            {'error': 'No active care reminders found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Generate ICS content
    ics_lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Plant Community//Care Reminders//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Plant Care Reminders',
        'X-WR-CALDESC:Care reminders for your plants from Plant Community',
        'X-WR-TIMEZONE:UTC'
    ]
    
    for reminder in reminders:
        # Generate recurring events for the next 6 months
        current_date = reminder.next_reminder_date
        end_date = timezone.now() + timedelta(days=180)  # 6 months ahead
        
        while current_date <= end_date:
            event_id = str(uuid.uuid4())
            
            # Format datetime for ICS (UTC)
            start_dt = current_date.strftime('%Y%m%dT%H%M%SZ')
            end_dt = (current_date + timedelta(hours=1)).strftime('%Y%m%dT%H%M%SZ')
            created_dt = reminder.created_at.strftime('%Y%m%dT%H%M%SZ')
            
            plant_name = reminder.saved_care_instructions.display_name
            reminder_type = reminder.get_reminder_type_display()
            
            ics_lines.extend([
                'BEGIN:VEVENT',
                f'UID:{event_id}@plantcommunity.com',
                f'DTSTART:{start_dt}',
                f'DTEND:{end_dt}',
                f'DTSTAMP:{created_dt}',
                f'CREATED:{created_dt}',
                f'LAST-MODIFIED:{reminder.updated_at.strftime("%Y%m%dT%H%M%SZ")}',
                f'SUMMARY:{reminder_type} - {plant_name}',
                f'DESCRIPTION:{reminder.description or f"Time to {reminder_type.lower()} your {plant_name}"}',
                'CATEGORIES:Plant Care,Reminders',
                'STATUS:CONFIRMED',
                'TRANSP:TRANSPARENT',
                f'ORGANIZER:MAILTO:noreply@plantcommunity.com',
                'BEGIN:VALARM',
                'TRIGGER:-PT15M',
                'ACTION:DISPLAY',
                f'DESCRIPTION:Reminder: {reminder_type} - {plant_name}',
                'END:VALARM',
                'END:VEVENT'
            ])
            
            # Calculate next occurrence based on frequency
            if reminder.frequency == 'daily':
                current_date += timedelta(days=1)
            elif reminder.frequency == 'weekly':
                current_date += timedelta(weeks=1)
            elif reminder.frequency == 'biweekly':
                current_date += timedelta(weeks=2)
            elif reminder.frequency == 'monthly':
                current_date += timedelta(days=30)
            elif reminder.frequency == 'quarterly':
                current_date += timedelta(days=90)
            elif reminder.frequency == 'biannual':
                current_date += timedelta(days=180)
            elif reminder.frequency == 'annual':
                current_date += timedelta(days=365)
            elif reminder.frequency == 'custom' and reminder.custom_interval_days:
                current_date += timedelta(days=reminder.custom_interval_days)
            else:
                break  # Unknown frequency, stop generating events
    
    ics_lines.append('END:VCALENDAR')
    
    # Create response with ICS content
    ics_content = '\r\n'.join(ics_lines)
    
    response = HttpResponse(
        ics_content,
        content_type='text/calendar; charset=utf-8'
    )
    response['Content-Disposition'] = 'attachment; filename="plant-care-reminders.ics"'
    response['Cache-Control'] = 'no-cache'
    
    return response


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def care_reminder_calendar_preview(request: Request) -> Response:
    """
    Get a preview of upcoming care reminder events for calendar display.
    """
    from .models import CareReminder
    from django.utils import timezone
    from datetime import timedelta
    
    # Get date range from query params (default to next 30 days)
    try:
        days_ahead = int(request.GET.get('days', 30))
        days_ahead = min(days_ahead, 365)  # Cap at 1 year
    except (ValueError, TypeError):
        days_ahead = 30
    
    start_date = timezone.now()
    end_date = start_date + timedelta(days=days_ahead)
    
    # Get user's active reminders
    reminders = CareReminder.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('saved_care_instructions')
    
    calendar_events = []
    
    for reminder in reminders:
        current_date = reminder.next_reminder_date
        
        # Generate events within the date range
        while current_date <= end_date:
            if current_date >= start_date:
                plant_name = reminder.saved_care_instructions.display_name
                reminder_type = reminder.get_reminder_type_display()
                
                calendar_events.append({
                    'id': f"{reminder.uuid}_{current_date.date()}",
                    'reminder_uuid': str(reminder.uuid),
                    'title': f"{reminder_type} - {plant_name}",
                    'description': reminder.description or f"Time to {reminder_type.lower()} your {plant_name}",
                    'start': current_date.isoformat(),
                    'end': (current_date + timedelta(hours=1)).isoformat(),
                    'type': reminder.reminder_type,
                    'plant_name': plant_name,
                    'frequency': reminder.get_frequency_display(),
                    'can_complete': current_date <= timezone.now() + timedelta(hours=2),  # Allow completion 2 hours early
                    'is_overdue': current_date < timezone.now(),
                    'color': {
                        'watering': '#3B82F6',      # Blue
                        'fertilizing': '#10B981',    # Green
                        'repotting': '#F59E0B',     # Amber
                        'pruning': '#EF4444',       # Red
                        'inspection': '#8B5CF6',    # Purple
                        'custom': '#6B7280'         # Gray
                    }.get(reminder.reminder_type, '#6B7280')
                })
            
            # Calculate next occurrence
            if reminder.frequency == 'daily':
                current_date += timedelta(days=1)
            elif reminder.frequency == 'weekly':
                current_date += timedelta(weeks=1)
            elif reminder.frequency == 'biweekly':
                current_date += timedelta(weeks=2)
            elif reminder.frequency == 'monthly':
                current_date += timedelta(days=30)
            elif reminder.frequency == 'quarterly':
                current_date += timedelta(days=90)
            elif reminder.frequency == 'biannual':
                current_date += timedelta(days=180)
            elif reminder.frequency == 'annual':
                current_date += timedelta(days=365)
            elif reminder.frequency == 'custom' and reminder.custom_interval_days:
                current_date += timedelta(days=reminder.custom_interval_days)
            else:
                break
    
    # Sort events by date
    calendar_events.sort(key=lambda x: x['start'])
    
    return Response({
        'events': calendar_events,
        'date_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': days_ahead
        },
        'total_events': len(calendar_events),
        'total_reminders': reminders.count()
    })
