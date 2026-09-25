"""
URL configuration for user authentication and profile management.
"""

from django.urls import path

from . import email_preferences_views, firebase_auth_views, oauth_views, views

app_name = "users"

urlpatterns = [
    # CSRF token endpoint
    path("csrf/", views.get_csrf_token, name="get_csrf_token"),
    # Authentication endpoints
    path("register/", views.register, name="register"),
    path("verify-email/", views.verify_email, name="verify_email"),
    path(
        "verify-email/resend/",
        views.resend_verification_email,
        name="resend_verification_email",
    ),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    # Firebase authentication (mobile app)
    path(
        "firebase-token-exchange/",
        firebase_auth_views.firebase_token_exchange,
        name="firebase_token_exchange",
    ),
    # OAuth endpoints
    path("oauth/<str:provider>/login/", oauth_views.oauth_login, name="oauth_login"),
    path(
        "oauth/<str:provider>/callback/",
        oauth_views.oauth_callback,
        name="oauth_callback",
    ),
    # User profile endpoints
    path("user/", views.current_user, name="current_user"),
    path("user/update/", views.update_profile, name="update_profile"),
    # User collections endpoints
    path("me/collections/", views.user_collections, name="user_collections"),
    path(
        "me/collections/<int:collection_id>/",
        views.user_collection_detail,
        name="user_collection_detail",
    ),
    # User previous searches endpoints
    path("me/searches/", views.previous_searches, name="previous_searches"),
    path("me/searches/<uuid:request_id>/", views.search_detail, name="search_detail"),
    # User dashboard stats
    path("me/dashboard-stats/", views.dashboard_stats, name="dashboard_stats"),
    # Token refresh endpoint
    path("token/refresh/", views.token_refresh, name="token_refresh"),
    # Push notification endpoints
    path(
        "me/push-notifications/subscribe/",
        views.subscribe_push_notifications,
        name="subscribe_push_notifications",
    ),
    path(
        "me/push-notifications/unsubscribe/",
        views.unsubscribe_push_notifications,
        name="unsubscribe_push_notifications",
    ),
    path("me/push-notifications/", views.push_subscriptions, name="push_subscriptions"),
    # Care reminder endpoints
    path("me/care-reminders/", views.care_reminders, name="care_reminders"),
    path(
        "me/care-reminders/<uuid:reminder_uuid>/",
        views.care_reminder_detail,
        name="care_reminder_detail",
    ),
    path(
        "me/care-reminders/<uuid:reminder_uuid>/action/",
        views.care_reminder_action,
        name="care_reminder_action",
    ),
    path(
        "me/care-reminders/stats/",
        views.care_reminder_stats,
        name="care_reminder_stats",
    ),
    path(
        "me/care-reminders/export/calendar/",
        views.export_care_reminders_calendar,
        name="export_care_reminders_calendar",
    ),
    path(
        "me/care-reminders/calendar/preview/",
        views.care_reminder_calendar_preview,
        name="care_reminder_calendar_preview",
    ),
    # Onboarding endpoints
    path(
        "me/onboarding/progress/", views.onboarding_progress, name="onboarding_progress"
    ),
    path(
        "me/onboarding/create-demo-data/",
        views.create_demo_data,
        name="create_demo_data",
    ),
    path(
        "me/onboarding/track-event/",
        views.track_onboarding_event,
        name="track_onboarding_event",
    ),
    path("me/onboarding/demo-data/", views.delete_demo_data, name="delete_demo_data"),
    # Signed-link unsubscribe (todo 408) — the web app's /unsubscribe page
    # calls these; email links are built by apps/users/email_unsubscribe.py.
    path(
        "unsubscribe/check/",
        email_preferences_views.email_unsubscribe_check,
        name="email_unsubscribe_check",
    ),
    path(
        "unsubscribe/",
        email_preferences_views.email_unsubscribe,
        name="email_unsubscribe",
    ),
    # RFC 8058 one-click (todo 416): the List-Unsubscribe header's URL.
    path(
        "unsubscribe/one-click/",
        email_preferences_views.email_unsubscribe_one_click,
        name="email_unsubscribe_one_click",
    ),
]
