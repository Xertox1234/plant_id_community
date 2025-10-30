"""
Forum models for Plant Community.

Headless forum implementation with:
- UUID primary keys for security
- Hierarchical categories
- Rich content support (Draft.js)
- Image attachments with ImageKit
- Reaction system (like, love, helpful, thanks)
- Trust level system
- Performance optimizations (indexes, prefetching)

Pattern follows apps/blog/models.py structure.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

from .constants import (
    MAX_THREAD_TITLE_LENGTH,
    MAX_THREAD_EXCERPT_LENGTH,
    MAX_POST_CONTENT_LENGTH,
    MAX_ATTACHMENTS_PER_POST,
    MAX_ATTACHMENT_SIZE_BYTES,
    DEFAULT_VIEW_COUNT,
    DEFAULT_POST_COUNT,
    DEFAULT_DISPLAY_ORDER,
    CONTENT_FORMAT_PLAIN,
    CONTENT_FORMATS,
    REACTION_TYPES,
    TRUST_LEVELS,
    TRUST_LEVEL_NEW,
)


class Category(models.Model):
    """
    Forum category with hierarchical support.

    Categories can have parent categories to create organized hierarchies.
    Similar to Wagtail's Page hierarchy but simpler.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key for security (prevents ID enumeration)"
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name (e.g., 'Plant Care', 'Pest Control')"
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text="URL-friendly slug (auto-generated from name)"
    )
    description = models.TextField(
        blank=True,
        help_text="Category description shown on category page"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent category for hierarchical structure"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name (e.g., 'leaf', 'bug') for UI display"
    )
    display_order = models.IntegerField(
        default=DEFAULT_DISPLAY_ORDER,
        help_text="Order for display (lower numbers first)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether category is visible to users"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug'], name='forum_cat_slug_idx'),
            models.Index(fields=['parent', 'is_active'], name='forum_cat_parent_active_idx'),
            models.Index(fields=['display_order'], name='forum_cat_order_idx'),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided."""
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_thread_count(self):
        """Get number of threads in this category."""
        return self.threads.filter(is_active=True).count()

    def get_post_count(self):
        """Get total number of posts in all threads in this category."""
        return sum(thread.post_count for thread in self.threads.filter(is_active=True))


class Thread(models.Model):
    """
    Forum thread (discussion topic).

    Each thread belongs to a category and contains multiple posts.
    First post in thread is the initial topic content.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key for security"
    )
    title = models.CharField(
        max_length=MAX_THREAD_TITLE_LENGTH,
        help_text="Thread title (max 200 characters)"
    )
    slug = models.SlugField(
        max_length=250,
        unique=True,
        help_text="URL-friendly slug with UUID suffix for uniqueness"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_threads',
        help_text="User who created the thread"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='threads',
        help_text="Category this thread belongs to"
    )
    excerpt = models.TextField(
        max_length=MAX_THREAD_EXCERPT_LENGTH,
        blank=True,
        help_text="Short excerpt for thread previews (max 500 chars)"
    )
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pinned threads appear at top of category"
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Locked threads don't allow new posts"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft delete: inactive threads are hidden"
    )
    view_count = models.IntegerField(
        default=DEFAULT_VIEW_COUNT,
        validators=[MinValueValidator(0)],
        help_text="Number of times thread has been viewed"
    )
    post_count = models.IntegerField(
        default=DEFAULT_POST_COUNT,
        validators=[MinValueValidator(0)],
        help_text="Number of posts in this thread (cached for performance)"
    )
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time a post was added (for sorting)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Thread"
        verbose_name_plural = "Threads"
        ordering = ['-is_pinned', '-last_activity_at', '-created_at']
        indexes = [
            models.Index(fields=['slug'], name='forum_thread_slug_idx'),
            models.Index(fields=['category', 'is_active', '-last_activity_at'], name='forum_thread_cat_active_idx'),
            models.Index(fields=['-is_pinned', '-last_activity_at'], name='forum_thread_pin_activity_idx'),
            models.Index(fields=['author', 'is_active'], name='forum_thread_author_idx'),
            models.Index(fields=['-created_at'], name='forum_thread_created_idx'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Auto-generate slug from title with UUID suffix for uniqueness."""
        if not self.slug:
            # Create slug with UUID suffix to ensure uniqueness
            base_slug = slugify(self.title)[:200]  # Leave room for UUID
            uuid_suffix = str(uuid.uuid4())[:8]
            self.slug = f"{base_slug}-{uuid_suffix}"

        # Set last_activity_at on creation
        if not self.pk and not self.last_activity_at:
            self.last_activity_at = timezone.now()

        super().save(*args, **kwargs)

    def increment_view_count(self):
        """Increment view count (use F() expression to avoid race conditions)."""
        from django.db.models import F
        Thread.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)

    def update_post_count(self):
        """Update cached post count from actual posts."""
        self.post_count = self.posts.filter(is_active=True).count()
        self.save(update_fields=['post_count'])

    def update_last_activity(self):
        """Update last_activity_at to current time."""
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])


class Post(models.Model):
    """
    Forum post within a thread.

    Supports plain text, Markdown, and rich content (Draft.js JSON).
    First post in thread is the topic post (is_first_post=True).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key for security"
    )
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name='posts',
        help_text="Thread this post belongs to"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_posts',
        help_text="User who created the post"
    )
    content_raw = models.TextField(
        max_length=MAX_POST_CONTENT_LENGTH,
        help_text="Raw content (plain text, Markdown, or Draft.js JSON string)"
    )
    content_rich = models.JSONField(
        null=True,
        blank=True,
        help_text="Rich content in Draft.js format (for rich text posts)"
    )
    content_format = models.CharField(
        max_length=20,
        choices=CONTENT_FORMATS,
        default=CONTENT_FORMAT_PLAIN,
        help_text="Format of content (plain, markdown, or rich)"
    )
    is_first_post = models.BooleanField(
        default=False,
        help_text="True if this is the first post (topic post) in the thread"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft delete: inactive posts are hidden"
    )
    edited_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time post was edited"
    )
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forum_posts_edited',
        help_text="User who last edited the post (moderator or author)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'is_active', 'created_at'], name='forum_post_thread_idx'),
            models.Index(fields=['author', 'is_active'], name='forum_post_author_idx'),
            models.Index(fields=['-created_at'], name='forum_post_created_idx'),
        ]

    def __str__(self):
        return f"Post by {self.author.username} in {self.thread.title}"

    def save(self, *args, **kwargs):
        """Update thread statistics on post creation."""
        is_new = not self.pk
        super().save(*args, **kwargs)

        if is_new and self.is_active:
            # Update thread post count and activity timestamp
            self.thread.update_post_count()
            self.thread.update_last_activity()

    def mark_edited(self, editor):
        """Mark post as edited by given user."""
        self.edited_at = timezone.now()
        self.edited_by = editor
        self.save(update_fields=['edited_at', 'edited_by', 'updated_at'])


class Attachment(models.Model):
    """
    Image attachment for forum posts.

    Uses ImageKit for automatic thumbnail generation and optimization.
    Supports up to 6 images per post (MAX_ATTACHMENTS_PER_POST).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key for security"
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Post this attachment belongs to"
    )
    image = models.ImageField(
        upload_to='forum/attachments/%Y/%m/%d/',
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp']),
        ],
        help_text="Image file (JPG, PNG, GIF, WebP)"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename from upload"
    )
    file_size = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(MAX_ATTACHMENT_SIZE_BYTES)],
        help_text=f"File size in bytes (max {MAX_ATTACHMENT_SIZE_BYTES / 1024 / 1024}MB)"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type (e.g., 'image/jpeg')"
    )
    display_order = models.IntegerField(
        default=DEFAULT_DISPLAY_ORDER,
        help_text="Order for display in post"
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Alt text for accessibility"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ImageKit specifications for automatic thumbnail generation
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(200, 200)],
        format='JPEG',
        options={'quality': 85}
    )
    medium = ImageSpecField(
        source='image',
        processors=[ResizeToFit(800, 600)],
        format='JPEG',
        options={'quality': 90}
    )
    large = ImageSpecField(
        source='image',
        processors=[ResizeToFit(1200, 900)],
        format='JPEG',
        options={'quality': 90}
    )

    class Meta:
        verbose_name = "Attachment"
        verbose_name_plural = "Attachments"
        ordering = ['display_order', 'created_at']
        indexes = [
            models.Index(fields=['post', 'display_order'], name='forum_attach_post_idx'),
        ]

    def __str__(self):
        return f"Attachment {self.original_filename} on post {self.post.id}"

    def save(self, *args, **kwargs):
        """Extract file metadata on upload."""
        if self.image and not self.file_size:
            self.file_size = self.image.size
            self.original_filename = self.image.name
            # MIME type detection would happen here
            if self.image.name.lower().endswith('.jpg') or self.image.name.lower().endswith('.jpeg'):
                self.mime_type = 'image/jpeg'
            elif self.image.name.lower().endswith('.png'):
                self.mime_type = 'image/png'
            elif self.image.name.lower().endswith('.gif'):
                self.mime_type = 'image/gif'
            elif self.image.name.lower().endswith('.webp'):
                self.mime_type = 'image/webp'

        super().save(*args, **kwargs)


class Reaction(models.Model):
    """
    User reaction to a forum post.

    Supports like, love, helpful, and thanks reactions.
    Reactions can be toggled (is_active=False means reaction was removed).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key for security"
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='reactions',
        help_text="Post being reacted to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_reactions',
        help_text="User giving the reaction"
    )
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_TYPES,
        help_text="Type of reaction (like, love, helpful, thanks)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="False if reaction was toggled off (removed)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reaction"
        verbose_name_plural = "Reactions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'reaction_type', 'is_active'], name='forum_react_post_type_idx'),
            models.Index(fields=['user', 'is_active'], name='forum_react_user_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['post', 'user', 'reaction_type'],
                name='unique_post_user_reaction'
            )
        ]

    def __str__(self):
        return f"{self.user.username} {self.reaction_type} on post {self.post.id}"

    @classmethod
    def toggle_reaction(cls, post_id, user_id, reaction_type):
        """
        Toggle a reaction on/off.

        If reaction exists and is active, mark as inactive.
        If reaction exists and is inactive, mark as active.
        If reaction doesn't exist, create it.

        Returns:
            tuple: (reaction, created) where created is True if new reaction
        """
        reaction, created = cls.objects.get_or_create(
            post_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
            defaults={'is_active': True}
        )

        if not created:
            # Toggle existing reaction
            reaction.is_active = not reaction.is_active
            reaction.save(update_fields=['is_active', 'updated_at'])

        return reaction, created


class UserProfile(models.Model):
    """
    Extended profile for forum users.

    Tracks trust level, post count, and forum-specific metadata.
    Linked to Django User model with OneToOne relationship.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key for security"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_profile',
        help_text="Linked Django user"
    )
    trust_level = models.CharField(
        max_length=20,
        choices=TRUST_LEVELS,
        default=TRUST_LEVEL_NEW,
        help_text="User's trust level (new, basic, trusted, veteran, expert)"
    )
    post_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total posts created (cached for performance)"
    )
    thread_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total threads created (cached for performance)"
    )
    helpful_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of 'helpful' reactions received"
    )
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user was active in forum"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['-helpful_count', '-post_count']
        indexes = [
            models.Index(fields=['user'], name='forum_profile_user_idx'),
            models.Index(fields=['trust_level', '-helpful_count'], name='forum_profile_trust_idx'),
        ]

    def __str__(self):
        return f"Forum profile for {self.user.username}"

    def update_post_count(self):
        """Update cached post count from actual posts."""
        self.post_count = Post.objects.filter(author=self.user, is_active=True).count()
        self.save(update_fields=['post_count'])

    def update_thread_count(self):
        """Update cached thread count from actual threads."""
        self.thread_count = Thread.objects.filter(author=self.user, is_active=True).count()
        self.save(update_fields=['thread_count'])

    def update_helpful_count(self):
        """Update helpful reaction count received."""
        from django.db.models import Count
        self.helpful_count = Reaction.objects.filter(
            post__author=self.user,
            reaction_type='helpful',
            is_active=True
        ).count()
        self.save(update_fields=['helpful_count'])

    def calculate_trust_level(self):
        """
        Calculate appropriate trust level based on activity.

        Returns new trust level (doesn't save automatically).
        """
        from datetime import timedelta
        from .constants import TRUST_LEVEL_REQUIREMENTS

        # Expert must be manually set by admin
        if self.trust_level == 'expert':
            return 'expert'

        days_active = (timezone.now() - self.user.date_joined).days
        post_count = self.post_count

        # Check requirements in reverse order (highest to lowest)
        for level in ['veteran', 'trusted', 'basic', 'new']:
            requirements = TRUST_LEVEL_REQUIREMENTS[level]
            if days_active >= requirements['days'] and post_count >= requirements['posts']:
                return level

        return 'new'
