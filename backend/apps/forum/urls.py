"""
Forum API URL configuration.

Registers all forum ViewSets with DRF router for RESTful API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    CategoryViewSet,
    ThreadViewSet,
    PostViewSet,
    ReactionViewSet,
    UserProfileViewSet,
    ModerationQueueViewSet,
)

app_name = 'forum'

# Create router and register ViewSets
router = DefaultRouter()

# Register all forum ViewSets
router.register('categories', CategoryViewSet, basename='category')
router.register('threads', ThreadViewSet, basename='thread')
router.register('posts', PostViewSet, basename='post')
router.register('reactions', ReactionViewSet, basename='reaction')
router.register('profiles', UserProfileViewSet, basename='userprofile')

# Phase 4.2: Content Moderation Queue
router.register('moderation-queue', ModerationQueueViewSet, basename='moderation-queue')

urlpatterns = [
    path('', include(router.urls)),
]
