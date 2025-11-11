"""
URL routing for blog administration interface.
"""

from django.urls import path
from . import admin_views, api_views

app_name = 'blog_admin'

urlpatterns = [
    # Main dashboard
    path('', admin_views.blog_admin_dashboard, name='dashboard'),

    # Comment moderation
    path('comments/', admin_views.moderate_comments, name='moderate_comments'),
    path('comments/approve/<int:comment_id>/', admin_views.approve_comment, name='approve_comment'),
    path('comments/reject/<int:comment_id>/', admin_views.reject_comment, name='reject_comment'),

    # Featured posts management
    path('featured/', admin_views.featured_posts, name='featured_posts'),
    path('posts/<int:post_id>/toggle-featured/', admin_views.toggle_featured, name='toggle_featured'),

    # Post-specific management
    path('posts/<int:post_id>/comments/', admin_views.post_comments, name='post_comments'),
    path('posts/<int:post_id>/ai-suggestions/', admin_views.ai_content_suggestions, name='post_ai_suggestions'),
    path('posts/<int:post_id>/tag-plants/', admin_views.tag_plants, name='tag_plants'),
    path('posts/<int:post_id>/feature/', admin_views.toggle_featured, name='feature_post'),
    path('posts/<int:post_id>/unfeature/', admin_views.toggle_featured, name='unfeature_post'),

    # AI content suggestions
    path('ai-suggestions/', admin_views.ai_content_suggestions, name='ai_suggestions'),

    # AI content generation (Phase 3: Issue #157)
    path('api/generate-field-content/', api_views.generate_blog_field_content, name='generate_field_content'),
    path('api/plant-lookup/', api_views.PlantLookupView.as_view(), name='plant_lookup'),
    path('api/plant-suggestions/', api_views.PlantSuggestionsView.as_view(), name='plant_suggestions'),

    # Search
    path('search/', admin_views.blog_search, name='search'),

    # Settings
    path('settings/', admin_views.blog_settings, name='settings'),

    # Data export
    path('export/', admin_views.export_data, name='export_data'),
]