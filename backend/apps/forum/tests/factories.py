"""
Test factories for forum models.

Provides factory pattern for creating test data with realistic defaults.
Uses factory_boy pattern for clean, maintainable test data creation.
"""

import uuid
from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils import timezone

User = get_user_model()


class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: str = 'testpass123',
        **kwargs
    ) -> User:
        """
        Create a test user.

        Args:
            username: Username (auto-generated if not provided)
            email: Email address (auto-generated if not provided)
            password: Password (default: 'testpass123')
            **kwargs: Additional user fields

        Returns:
            User instance
        """
        if not username:
            username = f'user_{uuid.uuid4().hex[:8]}'
        if not email:
            email = f'{username}@test.com'

        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            **kwargs
        )

    @staticmethod
    def create_batch(count: int = 5, **kwargs) -> list:
        """Create multiple users."""
        return [UserFactory.create(**kwargs) for _ in range(count)]


class CategoryFactory:
    """Factory for creating test forum categories."""

    @staticmethod
    def create(
        name: Optional[str] = None,
        slug: Optional[str] = None,
        parent=None,
        **kwargs
    ):
        """
        Create a test category.

        Args:
            name: Category name (auto-generated if not provided)
            slug: URL slug (auto-generated from name if not provided)
            parent: Parent category for hierarchy
            **kwargs: Additional category fields

        Returns:
            Category instance
        """
        # Import here to avoid circular dependency
        from apps.forum.models import Category

        if not name:
            name = f'Category {uuid.uuid4().hex[:8]}'
        if not slug:
            slug = slugify(name)

        return Category.objects.create(
            name=name,
            slug=slug,
            parent=parent,
            **kwargs
        )

    @staticmethod
    def create_hierarchy(depth: int = 2) -> tuple:
        """
        Create a category hierarchy.

        Args:
            depth: How many levels deep (default: 2)

        Returns:
            Tuple of (parent, child) categories
        """
        parent = CategoryFactory.create(name="Parent Category")
        child = CategoryFactory.create(
            name="Child Category",
            parent=parent
        )
        return (parent, child)

    @staticmethod
    def create_batch(count: int = 3, **kwargs) -> list:
        """Create multiple categories."""
        return [CategoryFactory.create(**kwargs) for _ in range(count)]


class ThreadFactory:
    """Factory for creating test forum threads."""

    @staticmethod
    def create(
        title: Optional[str] = None,
        slug: Optional[str] = None,
        author: Optional[User] = None,
        category = None,
        **kwargs
    ):
        """
        Create a test thread.

        Args:
            title: Thread title (auto-generated if not provided)
            slug: URL slug (auto-generated from title if not provided)
            author: Thread author (created if not provided)
            category: Forum category (created if not provided)
            **kwargs: Additional thread fields

        Returns:
            Thread instance
        """
        # Import here to avoid circular dependency
        from apps.forum.models import Thread

        if not title:
            title = f'Test Thread {uuid.uuid4().hex[:8]}'
        if not slug:
            slug = f'{slugify(title)}-{uuid.uuid4().hex[:8]}'
        if not author:
            author = UserFactory.create()
        if not category:
            category = CategoryFactory.create()

        return Thread.objects.create(
            title=title,
            slug=slug,
            author=author,
            category=category,
            **kwargs
        )

    @staticmethod
    def create_with_posts(
        post_count: int = 5,
        **thread_kwargs
    ):
        """
        Create a thread with multiple posts.

        Args:
            post_count: Number of posts to create
            **thread_kwargs: Arguments for thread creation

        Returns:
            Thread instance with posts
        """
        thread = ThreadFactory.create(**thread_kwargs)

        # Create first post
        PostFactory.create(
            thread=thread,
            author=thread.author,
            is_first_post=True
        )

        # Create additional posts
        for _ in range(post_count - 1):
            PostFactory.create(thread=thread)

        # Update thread statistics
        thread.post_count = post_count
        thread.save()

        return thread

    @staticmethod
    def create_batch(count: int = 3, **kwargs) -> list:
        """Create multiple threads."""
        return [ThreadFactory.create(**kwargs) for _ in range(count)]


class PostFactory:
    """Factory for creating test forum posts."""

    @staticmethod
    def create(
        thread = None,
        author: Optional[User] = None,
        content_raw: Optional[str] = None,
        content_format: str = 'plain',
        **kwargs
    ):
        """
        Create a test post.

        Args:
            thread: Thread this post belongs to (created if not provided)
            author: Post author (created if not provided)
            content_raw: Post content (auto-generated if not provided)
            content_format: Content format (default: 'plain')
            **kwargs: Additional post fields

        Returns:
            Post instance
        """
        # Import here to avoid circular dependency
        from apps.forum.models import Post

        if not thread:
            thread = ThreadFactory.create()
        if not author:
            author = UserFactory.create()
        if not content_raw:
            content_raw = f'This is a test post created at {timezone.now()}'

        return Post.objects.create(
            thread=thread,
            author=author,
            content_raw=content_raw,
            content_format=content_format,
            **kwargs
        )

    @staticmethod
    def create_with_rich_content(
        thread = None,
        author: Optional[User] = None,
        **kwargs
    ):
        """
        Create a post with Draft.js rich content.

        Returns:
            Post instance with rich content
        """
        rich_content = {
            "blocks": [
                {
                    "key": "abc123",
                    "text": "This is a test post with rich formatting.",
                    "type": "unstyled",
                    "depth": 0,
                    "inlineStyleRanges": [
                        {"offset": 0, "length": 4, "style": "BOLD"}
                    ],
                    "entityRanges": [],
                    "data": {}
                }
            ],
            "entityMap": {}
        }

        return PostFactory.create(
            thread=thread,
            author=author,
            content_raw="This is a test post with rich formatting.",
            content_rich=rich_content,
            content_format='rich',
            **kwargs
        )

    @staticmethod
    def create_batch(count: int = 3, thread=None, **kwargs) -> list:
        """Create multiple posts for a thread."""
        if not thread:
            thread = ThreadFactory.create()
        return [PostFactory.create(thread=thread, **kwargs) for _ in range(count)]


class AttachmentFactory:
    """Factory for creating test attachments."""

    @staticmethod
    def create(
        post = None,
        original_filename: Optional[str] = None,
        file_size: int = 1024000,  # 1MB default
        mime_type: str = 'image/jpeg',
        **kwargs
    ):
        """
        Create a test attachment.

        Args:
            post: Post this attachment belongs to (created if not provided)
            original_filename: Original filename
            file_size: File size in bytes (default: 1MB)
            mime_type: MIME type (default: 'image/jpeg')
            **kwargs: Additional attachment fields

        Returns:
            Attachment instance
        """
        # Import here to avoid circular dependency
        from apps.forum.models import Attachment
        from django.core.files.uploadedfile import SimpleUploadedFile

        if not post:
            post = PostFactory.create()
        if not original_filename:
            original_filename = f'test_image_{uuid.uuid4().hex[:8]}.jpg'

        # Create a simple test image file
        test_image = SimpleUploadedFile(
            name=original_filename,
            content=b'fake image content for testing',
            content_type=mime_type
        )

        return Attachment.objects.create(
            post=post,
            file=test_image,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            **kwargs
        )

    @staticmethod
    def create_batch(count: int = 3, post=None, **kwargs) -> list:
        """Create multiple attachments for a post."""
        if not post:
            post = PostFactory.create()
        return [
            AttachmentFactory.create(post=post, display_order=i, **kwargs)
            for i in range(count)
        ]


class ReactionFactory:
    """Factory for creating test reactions."""

    @staticmethod
    def create(
        post = None,
        user: Optional[User] = None,
        reaction_type: str = 'like',
        **kwargs
    ):
        """
        Create a test reaction.

        Args:
            post: Post being reacted to (created if not provided)
            user: User making the reaction (created if not provided)
            reaction_type: Type of reaction (default: 'like')
            **kwargs: Additional reaction fields

        Returns:
            Reaction instance
        """
        # Import here to avoid circular dependency
        from apps.forum.models import Reaction

        if not post:
            post = PostFactory.create()
        if not user:
            user = UserFactory.create()

        return Reaction.objects.create(
            post=post,
            user=user,
            reaction_type=reaction_type,
            **kwargs
        )

    @staticmethod
    def create_batch(
        count: int = 3,
        post=None,
        reaction_type: str = 'like',
        **kwargs
    ) -> list:
        """Create multiple reactions from different users."""
        if not post:
            post = PostFactory.create()

        reactions = []
        for _ in range(count):
            user = UserFactory.create()
            reactions.append(
                ReactionFactory.create(
                    post=post,
                    user=user,
                    reaction_type=reaction_type,
                    **kwargs
                )
            )
        return reactions

    @staticmethod
    def create_mixed_reactions(post=None) -> Dict[str, Any]:
        """
        Create a realistic mix of reactions for a post.

        Returns:
            Dict with post and reaction counts
        """
        if not post:
            post = PostFactory.create()

        # Create varied reactions
        reactions = {
            'like': ReactionFactory.create_batch(5, post=post, reaction_type='like'),
            'love': ReactionFactory.create_batch(3, post=post, reaction_type='love'),
            'helpful': ReactionFactory.create_batch(8, post=post, reaction_type='helpful'),
            'thanks': ReactionFactory.create_batch(2, post=post, reaction_type='thanks'),
        }

        return {
            'post': post,
            'reactions': reactions,
            'total_count': sum(len(r) for r in reactions.values())
        }
