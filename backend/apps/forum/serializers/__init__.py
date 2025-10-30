"""
Forum serializers package.

Provides JSON serialization for forum models following DRF best practices.
Pattern follows apps/blog/serializers.py structure.
"""

from .category_serializer import CategorySerializer, CategoryTreeSerializer
from .thread_serializer import (
    ThreadListSerializer,
    ThreadDetailSerializer,
    ThreadCreateSerializer,
)
from .post_serializer import (
    PostSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
)
from .attachment_serializer import AttachmentSerializer
from .reaction_serializer import (
    ReactionSerializer,
    ReactionToggleSerializer,
    ReactionAggregateSerializer,
)
from .user_profile_serializer import (
    UserProfileSerializer,
    UserProfileStatsSerializer,
)

__all__ = [
    # Category serializers
    'CategorySerializer',
    'CategoryTreeSerializer',
    # Thread serializers
    'ThreadListSerializer',
    'ThreadDetailSerializer',
    'ThreadCreateSerializer',
    # Post serializers
    'PostSerializer',
    'PostCreateSerializer',
    'PostUpdateSerializer',
    # Attachment serializers
    'AttachmentSerializer',
    # Reaction serializers
    'ReactionSerializer',
    'ReactionToggleSerializer',
    'ReactionAggregateSerializer',
    # User profile serializers
    'UserProfileSerializer',
    'UserProfileStatsSerializer',
]
