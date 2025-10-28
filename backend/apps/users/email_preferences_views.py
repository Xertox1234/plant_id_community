"""
Views for managing user email notification preferences.

Provides user-friendly interface for controlling all email notification types
with proper GDPR compliance and one-click unsubscribe functionality.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.utils.pii_safe_logging import log_safe_user_context
import logging

from apps.core.services.notification_service import NotificationService

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def email_preferences(request):
    """
    Display and handle email notification preferences for the logged-in user.
    """
    user = request.user
    notification_service = NotificationService()
    
    if request.method == 'POST':
        try:
            # Update email notification preferences
            preferences = {
                'email_notifications': request.POST.get('email_notifications') == 'on',
                'plant_id_notifications': request.POST.get('plant_id_notifications') == 'on',
                'forum_notifications': request.POST.get('forum_notifications') == 'on',
                'care_reminder_email': request.POST.get('care_reminder_email') == 'on',
            }
            
            # Update user preferences
            user.email_notifications = preferences['email_notifications']
            user.plant_id_notifications = preferences['plant_id_notifications'] 
            user.forum_notifications = preferences['forum_notifications']
            user.care_reminder_email = preferences['care_reminder_email']
            user.save()
            
            # Update forum subscription preferences
            update_forum_subscriptions(user, request.POST)
            
            messages.success(request, '✅ Your email preferences have been updated successfully!')
            logger.info(f"Email preferences updated for {log_safe_user_context(user)}")
            
        except Exception as e:
            messages.error(request, '❌ There was an error updating your preferences. Please try again.')
            logger.error(f"Error updating email preferences for {log_safe_user_context(user)}: {e}")
    
    # Get current preferences
    current_preferences = notification_service.get_user_notification_preferences(user)
    
    # Get forum subscription preferences
    forum_subscriptions = get_forum_subscription_preferences(user)
    
    context = {
        'user': user,
        'preferences': current_preferences,
        'forum_subscriptions': forum_subscriptions,
    }
    
    return render(request, 'users/email_preferences.html', context)


@require_http_methods(["GET", "POST"])
def unsubscribe(request):
    """
    Handle one-click unsubscribe from all emails or specific email types.
    GDPR compliant unsubscribe functionality.
    """
    user_uuid = request.GET.get('user')
    email_type = request.GET.get('type', 'all')
    
    if not user_uuid:
        return render(request, 'users/unsubscribe_error.html', {
            'error': 'Invalid unsubscribe link'
        })
    
    try:
        user = User.objects.get(uuid=user_uuid)
    except User.DoesNotExist:
        return render(request, 'users/unsubscribe_error.html', {
            'error': 'Invalid unsubscribe link'  # Don't reveal if user exists
        })
    
    if request.method == 'POST':
        # Process unsubscribe request
        if email_type == 'all':
            # Unsubscribe from all emails
            user.email_notifications = False
            user.plant_id_notifications = False
            user.forum_notifications = False
            user.care_reminder_email = False
            user.save()
            
            # Deactivate all forum subscriptions
            from apps.core.models import ForumNotificationSubscription
            ForumNotificationSubscription.objects.filter(
                user=user,
                is_active=True
            ).update(is_active=False)
            
            success_message = "You have been unsubscribed from all Plant Community emails."
            
        else:
            # Unsubscribe from specific email type
            if email_type == 'plant_care':
                user.plant_id_notifications = False
                user.care_reminder_email = False
                success_message = "You have been unsubscribed from plant care emails."
            elif email_type == 'forum':
                user.forum_notifications = False
                success_message = "You have been unsubscribed from forum emails."
            else:
                success_message = f"You have been unsubscribed from {email_type} emails."
            
            user.save()
        
        logger.info(f"{log_safe_user_context(user)} unsubscribed from {email_type} emails")
        
        return render(request, 'users/unsubscribe_success.html', {
            'user': user,
            'email_type': email_type,
            'success_message': success_message,
        })
    
    # Show unsubscribe confirmation page (GET request)
    return render(request, 'users/unsubscribe_confirm.html', {
        'user': user,
        'email_type': email_type,
    })


@login_required
@require_http_methods(["POST"])
def ajax_update_preference(request):
    """
    AJAX endpoint for updating individual email preferences.
    """
    # Define allowed preference names for security
    ALLOWED_PREFERENCES = {
        'email_notifications',
        'plant_id_notifications', 
        'forum_notifications',
        'care_reminder_email'
    }
    
    try:
        preference_name = request.POST.get('preference')
        enabled = request.POST.get('enabled') == 'true'
        
        # Validate preference name
        if not preference_name or preference_name not in ALLOWED_PREFERENCES:
            return JsonResponse({
                'success': False, 
                'error': 'Invalid preference name'
            }, status=400)
        
        user = request.user
        
        # Set the preference using getattr/setattr for safety
        if hasattr(user, preference_name):
            setattr(user, preference_name, enabled)
            user.save(update_fields=[preference_name])
        else:
            return JsonResponse({
                'success': False, 
                'error': 'User does not have this preference field'
            }, status=400)
        
        logger.info(f"AJAX preference update: {log_safe_user_context(user)} set {preference_name} to {enabled}")
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error in AJAX preference update: {e}")
        return JsonResponse({
            'success': False, 
            'error': 'An error occurred while updating preferences'
        }, status=500)


def update_forum_subscriptions(user, post_data):
    """Update user's forum subscription preferences."""
    from apps.core.models import ForumNotificationSubscription
    
    # Forum reply frequency
    reply_frequency = post_data.get('forum_reply_frequency', 'instant')
    mention_frequency = post_data.get('forum_mention_frequency', 'instant')
    digest_frequency = post_data.get('forum_digest_frequency', 'weekly')
    
    # Update or create forum subscriptions
    subscription_types = [
        ('topic_reply', reply_frequency),
        ('mention', mention_frequency), 
        ('digest', digest_frequency),
    ]
    
    for sub_type, frequency in subscription_types:
        subscription, created = ForumNotificationSubscription.objects.get_or_create(
            user=user,
            notification_type=sub_type,
            defaults={'frequency': frequency, 'is_active': frequency != 'never'}
        )
        
        if not created:
            subscription.frequency = frequency
            subscription.is_active = frequency != 'never'
            subscription.save()


def get_forum_subscription_preferences(user):
    """Get user's current forum subscription preferences."""
    from apps.core.models import ForumNotificationSubscription
    
    subscriptions = ForumNotificationSubscription.objects.filter(user=user)
    
    preferences = {
        'reply_frequency': 'instant',
        'mention_frequency': 'instant', 
        'digest_frequency': 'weekly',
    }
    
    for sub in subscriptions:
        if sub.notification_type == 'topic_reply':
            preferences['reply_frequency'] = sub.frequency
        elif sub.notification_type == 'mention':
            preferences['mention_frequency'] = sub.frequency
        elif sub.notification_type == 'digest':
            preferences['digest_frequency'] = sub.frequency
    
    return preferences