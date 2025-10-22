"""
URL configuration for user authentication and profile management.
"""

from django.urls import path
from . import views, oauth_views, email_preferences_views

app_name = 'users'

urlpatterns = [
    # CSRF token endpoint
    path('csrf/', views.get_csrf_token, name='get_csrf_token'),
    
    # Authentication endpoints
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # OAuth endpoints
    path('oauth/<str:provider>/login/', oauth_views.oauth_login, name='oauth_login'),
    path('oauth/<str:provider>/callback/', oauth_views.oauth_callback, name='oauth_callback'),
    
    # User profile endpoints
    path('user/', views.current_user, name='current_user'),
    path('user/update/', views.update_profile, name='update_profile'),
    
    # User collections endpoints
    path('me/collections/', views.user_collections, name='user_collections'),
    path('me/collections/<int:collection_id>/', views.user_collection_detail, name='user_collection_detail'),
    
    # User previous searches endpoints
    path('me/searches/', views.previous_searches, name='previous_searches'),
    path('me/searches/<uuid:request_id>/', views.search_detail, name='search_detail'),
    
    # User forum activity and dashboard stats
    path('me/forum-activity/', views.forum_activity, name='forum_activity'),
    path('me/dashboard-stats/', views.dashboard_stats, name='dashboard_stats'),
    
    # Forum permissions
    path('forum-permissions/', views.forum_permissions, name='forum_permissions'),
    
    # Token refresh endpoint
    path('token/refresh/', views.token_refresh, name='token_refresh'),
    
    # Push notification endpoints
    path('me/push-notifications/subscribe/', views.subscribe_push_notifications, name='subscribe_push_notifications'),
    path('me/push-notifications/unsubscribe/', views.unsubscribe_push_notifications, name='unsubscribe_push_notifications'),
    path('me/push-notifications/', views.push_subscriptions, name='push_subscriptions'),
    
    # Care reminder endpoints
    path('me/care-reminders/', views.care_reminders, name='care_reminders'),
    path('me/care-reminders/<uuid:reminder_uuid>/', views.care_reminder_detail, name='care_reminder_detail'),
    path('me/care-reminders/<uuid:reminder_uuid>/action/', views.care_reminder_action, name='care_reminder_action'),
    path('me/care-reminders/stats/', views.care_reminder_stats, name='care_reminder_stats'),
    path('me/care-reminders/export/calendar/', views.export_care_reminders_calendar, name='export_care_reminders_calendar'),
    path('me/care-reminders/calendar/preview/', views.care_reminder_calendar_preview, name='care_reminder_calendar_preview'),
    
    # Onboarding endpoints
    path('me/onboarding/progress/', views.onboarding_progress, name='onboarding_progress'),
    path('me/onboarding/create-demo-data/', views.create_demo_data, name='create_demo_data'),
    path('me/onboarding/track-event/', views.track_onboarding_event, name='track_onboarding_event'),
    path('me/onboarding/demo-data/', views.delete_demo_data, name='delete_demo_data'),
    
    # Email preferences endpoints
    path('me/email-preferences/', email_preferences_views.email_preferences, name='email_preferences'),
    path('me/email-preferences/ajax-update/', email_preferences_views.ajax_update_preference, name='ajax_update_preference'),
    path('unsubscribe/', email_preferences_views.unsubscribe, name='unsubscribe'),
]