"""
API URL patterns for forum integration.
"""

from django.urls import path
from . import api_views

app_name = 'forum_api'

urlpatterns = [
    # Forum categories
    path('categories/', api_views.ForumCategoryListView.as_view(), name='category_list'),
    
    # Topics - more specific patterns first to avoid conflicts
    path('topics/feed/', api_views.TopicsFeedView.as_view(), name='topics_feed'),
    path('topics-test/', api_views.all_topics_list, name='all_topics_test'),
    path('topics/<int:topic_id>/mark-viewed/', api_views.TopicMarkViewedView.as_view(), name='mark_viewed'),
    path('topics/<int:topic_id>/update/', api_views.TopicUpdateView.as_view(), name='update_topic'),
    path('topics/<int:topic_id>/', api_views.TopicDetailView.as_view(), name='topic_detail'),
    path('categories/<int:forum_id>/topics/create/', api_views.CreateTopicView.as_view(), name='create_topic'),
    path('categories/<int:forum_id>/topics/', api_views.ForumTopicsListView.as_view(), name='topic_list'),
    path('topics/', api_views.all_topics_list, name='all_topics_list'),
    
    # Posts
    path('posts/', api_views.PostListView.as_view(), name='post_list'),
    path('posts/create/', api_views.PostCreateView.as_view(), name='create_post'),
    path('posts/<int:post_id>/', api_views.PostUpdateView.as_view(), name='update_post'),
    path('posts/<int:post_id>/delete/', api_views.PostDeleteView.as_view(), name='delete_post'),
    path('topics/<int:topic_id>/posts/create/', api_views.CreatePostView.as_view(), name='create_post_legacy'),
    
    # Post Images
    path('posts/<int:post_id>/images/', api_views.PostImageListView.as_view(), name='post_images_list'),
    path('posts/<int:post_id>/images/upload/', api_views.PostImageUploadView.as_view(), name='post_images_upload'),
    path('posts/<int:post_id>/images/<int:image_id>/', api_views.PostImageUpdateView.as_view(), name='post_image_update'),
    path('posts/<int:post_id>/images/<int:image_id>/delete/', api_views.PostImageDeleteView.as_view(), name='post_image_delete'),
    
    # Post Reactions
    path('posts/<int:post_id>/reactions/', api_views.PostReactionView.as_view(), name='post_reactions'),
    
    # Search and stats
    path('search/', api_views.forum_search, name='forum_search'),
    path('stats/', api_views.forum_stats, name='forum_stats'),
    
    # AI assistance
    path('ai-assist/', api_views.forum_ai_assist, name='forum_ai_assist'),
    
    # User trust level
    path('user/trust-level/', api_views.user_trust_level, name='user_trust_level'),
    
    # User-specific endpoints
    path('users/<int:user_id>/topics/', api_views.UserTopicsListView.as_view(), name='user_topics'),
    path('users/<int:user_id>/watched-topics/', api_views.UserWatchedTopicsListView.as_view(), name='user_watched_topics'),
]