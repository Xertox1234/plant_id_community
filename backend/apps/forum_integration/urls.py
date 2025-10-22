"""
Simple working URL configuration for forum integration.
"""

from django.urls import path, include
from . import views

app_name = 'forum_integration'

urlpatterns = [
    # Basic forum navigation
    path('', views.forum_index, name='forum_index'),
    path('category/<int:forum_id>/', views.forum_category, name='forum_category'),
    path('topic/<int:topic_id>/', views.forum_topic, name='forum_topic'),
    
    # Topic and post creation
    path('category/<int:forum_id>/new-topic/', views.create_topic, name='create_topic'),
    path('topic/<int:topic_id>/reply/', views.create_post, name='create_post'),
    
    # Search
    path('search/', views.forum_search, name='forum_search'),
    
    # Fallback to Machina for advanced features
    path('machina/', include('machina.urls')),
]