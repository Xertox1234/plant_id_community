"""
Forum app test suite.

Provides comprehensive testing infrastructure for the forum implementation.
"""

from .base import ForumTestCase, ForumAPITestCase
from .factories import (
    UserFactory,
    CategoryFactory,
    ThreadFactory,
    PostFactory,
    AttachmentFactory,
    ReactionFactory,
)
from .fixtures import ForumTestFixtures
from .utils import ForumTestUtils

__all__ = [
    # Base test cases
    'ForumTestCase',
    'ForumAPITestCase',

    # Factories
    'UserFactory',
    'CategoryFactory',
    'ThreadFactory',
    'PostFactory',
    'AttachmentFactory',
    'ReactionFactory',

    # Utilities
    'ForumTestFixtures',
    'ForumTestUtils',
]
