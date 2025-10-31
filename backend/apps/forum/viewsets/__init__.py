"""
Forum viewsets package.

Provides DRF ViewSets for forum models following REST API best practices.
Pattern follows standard DRF ModelViewSet structure.
"""

from .category_viewset import CategoryViewSet
from .thread_viewset import ThreadViewSet
from .post_viewset import PostViewSet
from .reaction_viewset import ReactionViewSet
from .user_profile_viewset import UserProfileViewSet

__all__ = [
    'CategoryViewSet',
    'ThreadViewSet',
    'PostViewSet',
    'ReactionViewSet',
    'UserProfileViewSet',
]
