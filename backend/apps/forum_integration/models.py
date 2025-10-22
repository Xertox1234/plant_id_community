"""
Wagtail page models for forum integration.

This module creates Wagtail page types that wrap Django Machina forums,
allowing forum pages to leverage Wagtail's features while using Machina's backend.
"""

from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import Http404
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.search import index
from machina.core.db.models import get_model
from machina.core.loading import get_class
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic, Post
from imagekit.models import ImageSpecField, ProcessedImageField
from imagekit.processors import ResizeToFill, ResizeToFit

User = get_user_model()


# FLAT StreamField blocks - NO NESTING!
class ForumStreamBlocks(blocks.StreamBlock):
    """
    Flat StreamField blocks for forum pages.
    IMPORTANT: No nested blocks allowed per user requirement!
    """
    
    heading = blocks.CharBlock(
        icon="title",
        template="forum_integration/blocks/heading.html"
    )
    
    paragraph = blocks.RichTextBlock(
        icon="pilcrow",
        template="forum_integration/blocks/paragraph.html"
    )
    
    forum_announcement = blocks.StructBlock([
        ('title', blocks.CharBlock()),
        ('content', blocks.RichTextBlock()),
        ('is_pinned', blocks.BooleanBlock(required=False)),
        ('show_until', blocks.DateTimeBlock(required=False))
    ], icon="warning", template="forum_integration/blocks/announcement.html")
    
    forum_rules = blocks.StructBlock([
        ('rule_title', blocks.CharBlock()),
        ('rule_description', blocks.RichTextBlock())
    ], icon="list-ul", template="forum_integration/blocks/rules.html")
    
    moderator_info = blocks.StructBlock([
        ('moderator_name', blocks.CharBlock()),
        ('moderator_bio', blocks.RichTextBlock()),
        ('contact_info', blocks.CharBlock(required=False))
    ], icon="user", template="forum_integration/blocks/moderator.html")
    
    image = ImageChooserBlock(
        icon="image",
        template="forum_integration/blocks/image.html"
    )
    
    call_to_action = blocks.StructBlock([
        ('button_text', blocks.CharBlock()),
        ('button_url', blocks.URLBlock()),
        ('description', blocks.TextBlock(required=False))
    ], icon="link", template="forum_integration/blocks/cta.html")
    
    statistics = blocks.StructBlock([
        ('stat_label', blocks.CharBlock()),
        ('stat_value', blocks.CharBlock()),
        ('stat_description', blocks.TextBlock(required=False))
    ], icon="view", template="forum_integration/blocks/statistics.html")

    # Plant mention block: references a Wagtail page for a plant species
    class PlantMentionBlock(blocks.StructBlock):
        plant_page = blocks.PageChooserBlock(
            target_model='plant_identification.PlantSpeciesPage',
            help_text="Choose the plant species page to mention"
        )
        display_text = blocks.CharBlock(
            required=False,
            help_text="Optional override text to display for the mention"
        )

        class Meta:
            icon = "tag"
            template = "forum_integration/blocks/plant_mention.html"
            label = "Plant mention"

    plant_mention = PlantMentionBlock()


class ForumBasePage(Page):
    """
    Abstract base class for all forum-related Wagtail pages.
    Provides common functionality and ensures flat StreamField usage.
    """
    
    # Flat content blocks - NO NESTING
    content_blocks = StreamField(
        ForumStreamBlocks(),
        blank=True,
        help_text="Add content blocks for this forum page. Note: Nested blocks are not allowed.",
        use_json_field=True
    )
    
    # SEO and metadata
    meta_description = models.TextField(
        max_length=160,
        blank=True,
        help_text="Meta description for search engines"
    )
    
    # Forum integration settings
    show_breadcrumbs = models.BooleanField(
        default=True,
        help_text="Show breadcrumb navigation"
    )
    
    enable_social_sharing = models.BooleanField(
        default=True,
        help_text="Enable social media sharing buttons"
    )
    
    content_panels = Page.content_panels + [
        FieldPanel('content_blocks'),
        MultiFieldPanel([
            FieldPanel('meta_description'),
            FieldPanel('show_breadcrumbs'),
            FieldPanel('enable_social_sharing'),
        ], heading="Page Settings")
    ]
    
    search_fields = Page.search_fields + [
        index.SearchField('content_blocks'),
        index.SearchField('meta_description'),
    ]
    
    class Meta:
        abstract = True


class ForumIndexPage(ForumBasePage):
    """
    Main forum index page that displays all forum categories.
    Integrates with Django Machina's forum structure.
    """
    
    # Forum-specific settings
    forums_per_page = models.IntegerField(
        default=20,
        help_text="Number of forums to display per page"
    )
    
    show_statistics = models.BooleanField(
        default=True,
        help_text="Show forum statistics (total posts, topics, etc.)"
    )
    
    welcome_message = models.TextField(
        blank=True,
        help_text="Welcome message displayed at the top of the forum"
    )
    
    content_panels = ForumBasePage.content_panels + [
        MultiFieldPanel([
            FieldPanel('forums_per_page'),
            FieldPanel('show_statistics'),
            FieldPanel('welcome_message'),
        ], heading="Forum Index Settings")
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get all visible forums
        forums = Forum.objects.filter(
            type=Forum.FORUM_POST
        ).select_related('parent')
        
        context.update({
            'forums': forums,
            'welcome_message': self.welcome_message,
            'show_statistics': self.show_statistics,
        })
        
        return context
    
    class Meta:
        verbose_name = "Forum Index Page"


class ForumCategoryPage(ForumBasePage):
    """
    Page for displaying a specific forum category and its topics.
    Links to Django Machina forum by ID.
    """
    
    # Link to Machina forum
    machina_forum_id = models.IntegerField(
        help_text="ID of the Django Machina forum this page represents"
    )
    
    # Display settings
    topics_per_page = models.IntegerField(
        default=25,
        help_text="Number of topics to display per page"
    )
    
    allow_new_topics = models.BooleanField(
        default=True,
        help_text="Allow users to create new topics in this forum"
    )
    
    show_topic_stats = models.BooleanField(
        default=True,
        help_text="Show topic statistics (replies, views, etc.)"
    )
    
    # Moderation settings
    require_approval = models.BooleanField(
        default=False,
        help_text="Require moderator approval for new topics"
    )
    
    content_panels = ForumBasePage.content_panels + [
        MultiFieldPanel([
            FieldPanel('machina_forum_id'),
            FieldPanel('topics_per_page'),
            FieldPanel('allow_new_topics'),
            FieldPanel('show_topic_stats'),
        ], heading="Forum Settings"),
        MultiFieldPanel([
            FieldPanel('require_approval'),
        ], heading="Moderation Settings")
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        try:
            # Get the Machina forum
            forum = get_object_or_404(Forum, id=self.machina_forum_id)
            
            # Get topics for this forum
            topics = Topic.objects.filter(
                forum=forum,
                approved=True
            ).select_related('poster', 'last_post', 'last_post__poster').order_by('-last_post_on')
            
            # Pagination
            paginator = Paginator(topics, self.topics_per_page)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            
            context.update({
                'forum': forum,
                'topics': page_obj,
                'allow_new_topics': self.allow_new_topics,
                'show_topic_stats': self.show_topic_stats,
                'require_approval': self.require_approval,
            })
            
        except Forum.DoesNotExist:
            raise Http404("Forum not found")
        
        return context
    
    class Meta:
        verbose_name = "Forum Category Page"


class ForumAnnouncementPage(ForumBasePage):
    """
    Page for displaying forum announcements and important notices.
    Uses flat StreamField blocks for flexible content layout.
    """
    
    # Announcement settings
    is_pinned = models.BooleanField(
        default=True,
        help_text="Pin this announcement to the top of forum listings"
    )
    
    show_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Hide this announcement after this date (optional)"
    )
    
    announcement_type = models.CharField(
        max_length=20,
        choices=[
            ('info', 'Information'),
            ('warning', 'Warning'),
            ('urgent', 'Urgent'),
            ('maintenance', 'Maintenance'),
        ],
        default='info',
        help_text="Type of announcement affects styling"
    )
    
    # Target audience
    show_to_all = models.BooleanField(
        default=True,
        help_text="Show to all users, including guests"
    )
    
    show_to_members_only = models.BooleanField(
        default=False,
        help_text="Show only to registered members"
    )
    
    content_panels = ForumBasePage.content_panels + [
        MultiFieldPanel([
            FieldPanel('is_pinned'),
            FieldPanel('show_until'),
            FieldPanel('announcement_type'),
        ], heading="Announcement Settings"),
        MultiFieldPanel([
            FieldPanel('show_to_all'),
            FieldPanel('show_to_members_only'),
        ], heading="Visibility Settings")
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        context.update({
            'is_pinned': self.is_pinned,
            'announcement_type': self.announcement_type,
            'show_until': self.show_until,
        })
        
        return context
    
    class Meta:
        verbose_name = "Forum Announcement Page"


class ForumModerationPage(ForumBasePage):
    """
    Page for forum moderation tools and information.
    Accessible only to moderators and admins.
    """
    
    # Moderation settings
    show_pending_posts = models.BooleanField(
        default=True,
        help_text="Show pending posts awaiting approval"
    )
    
    show_reported_content = models.BooleanField(
        default=True,
        help_text="Show reported posts and topics"
    )
    
    show_user_management = models.BooleanField(
        default=True,
        help_text="Show user management tools"
    )
    
    # Auto-moderation settings
    enable_spam_detection = models.BooleanField(
        default=True,
        help_text="Enable automatic spam detection"
    )
    
    auto_approve_trusted_users = models.BooleanField(
        default=True,
        help_text="Automatically approve posts from trusted users"
    )
    
    content_panels = ForumBasePage.content_panels + [
        MultiFieldPanel([
            FieldPanel('show_pending_posts'),
            FieldPanel('show_reported_content'),
            FieldPanel('show_user_management'),
        ], heading="Moderation Tools"),
        MultiFieldPanel([
            FieldPanel('enable_spam_detection'),
            FieldPanel('auto_approve_trusted_users'),
        ], heading="Auto-Moderation Settings")
    ]
    
    def serve(self, request):
        # Check if user has moderation permissions
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not (request.user.is_staff or request.user.is_superuser):
            raise Http404("Page not found")
        
        return super().serve(request)
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get moderation data
        pending_posts = Post.objects.filter(approved=False).count()
        
        context.update({
            'pending_posts_count': pending_posts,
            'show_pending_posts': self.show_pending_posts,
            'show_reported_content': self.show_reported_content,
            'show_user_management': self.show_user_management,
        })
        
        return context
    
    class Meta:
        verbose_name = "Forum Moderation Page"


# Helper model for tracking forum page relationships
class ForumPageMapping(models.Model):
    """
    Maps Wagtail forum pages to Django Machina forums.
    Helps maintain relationships between Wagtail CMS and forum data.
    """
    
    wagtail_page = models.OneToOneField(
        'wagtailcore.Page',
        on_delete=models.CASCADE,
        related_name='forum_mapping'
    )
    
    machina_forum = models.ForeignKey(
        'forum.Forum',
        on_delete=models.CASCADE,
        related_name='wagtail_pages'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Is this mapping currently active?"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Forum Page Mapping"
        verbose_name_plural = "Forum Page Mappings"
        unique_together = ['wagtail_page', 'machina_forum']
    
    def __str__(self):
        return f"{self.wagtail_page.title} -> {self.machina_forum.name}"


# Rich Content Models for Forum Posts
class RichPost(models.Model):
    """
    Extension model for Post to support rich content.
    Linked to Machina's Post model via OneToOne relationship.
    """
    
    # Link to original Machina post
    post = models.OneToOneField(
        'forum_conversation.Post',
        on_delete=models.CASCADE,
        related_name='rich_content'
    )
    
    # Rich content in Draft.js raw format (JSON)
    rich_content = models.JSONField(
        null=True,
        blank=True,
        help_text="Draftail editor content in Draft.js raw format"
    )
    
    # Content format indicator
    content_format = models.CharField(
        max_length=20,
        choices=[
            ('plain', 'Plain Text'),
            ('draftail', 'Rich Content (Draftail)'),
            ('html', 'HTML'),
        ],
        default='plain'
    )
    
    # AI assistance metadata
    ai_assisted = models.BooleanField(
        default=False,
        help_text="Whether AI assistance was used in creating this post"
    )
    
    ai_prompts_used = models.JSONField(
        null=True,
        blank=True,
        help_text="AI prompts that were used (for analytics)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Rich Content Post"
        verbose_name_plural = "Rich Content Posts"
        db_table = 'forum_rich_posts'
    
    def __str__(self):
        return f"Rich content for post {self.post.id}"
    
    @property
    def has_rich_content(self):
        """Check if this post has rich content."""
        return self.content_format == 'draftail' and self.rich_content
    
    @property
    def display_content(self):
        """Get content for display based on format."""
        if self.has_rich_content:
            return self.rich_content
        return self.post.content


class PostTemplate(models.Model):
    """
    Templates for common post types (plant problems, solutions, etc.)
    """
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Template structure in StreamField-like format
    template_blocks = models.JSONField(
        help_text="Template blocks structure for forum posts"
    )
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    
    # Meta
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Post Template"
        verbose_name_plural = "Post Templates"
        ordering = ['-usage_count', 'name']
    
    def __str__(self):
        return f"{self.name} (used {self.usage_count} times)"


class ForumAIUsage(models.Model):
    """
    Track AI usage in forum posts for analytics and optimization
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(
        'forum_conversation.Post',
        on_delete=models.CASCADE
    )
    
    # AI usage details
    prompt_type = models.CharField(max_length=50)
    prompt_text = models.TextField()
    ai_response = models.TextField()
    
    # Usage context
    action_type = models.CharField(
        max_length=20,
        choices=[
            ('create', 'Create New Content'),
            ('enhance', 'Enhance Existing'),
            ('correct', 'Grammar/Style Correction'),
            ('continue', 'Continue Writing'),
            ('suggest', 'Suggest Improvements'),
        ]
    )
    
    # Performance tracking
    response_time_ms = models.IntegerField(null=True, blank=True)
    user_accepted = models.BooleanField(default=True)
    user_rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, str(i)) for i in range(1, 6)]  # 1-5 stars
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Forum AI Usage"
        verbose_name_plural = "Forum AI Usage Records"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"AI {self.action_type} for {self.user.username} on post {self.post.id}"


class ForumPostImage(models.Model):
    """
    Images attached to forum posts.
    Supports up to 6 images per post with automatic resizing and thumbnail generation.
    """
    
    # Link to forum post
    post = models.ForeignKey(
        'forum_conversation.Post',
        on_delete=models.CASCADE,
        related_name='images',
        help_text="The forum post this image belongs to"
    )
    
    # Main image with automatic resizing
    image = ProcessedImageField(
        upload_to='forum/posts/%Y/%m/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 85},
        help_text="Main image (automatically resized to max 1200x1200)"
    )
    
    # Thumbnail for gallery previews
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(120, 120)],
        format='JPEG',
        options={'quality': 80}
    )
    
    # Large thumbnail for modal viewer
    large_thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFit(800, 800)],
        format='JPEG',
        options={'quality': 85}
    )
    
    # Image metadata
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename when uploaded"
    )
    
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )
    
    # Ordering and management
    upload_order = models.PositiveIntegerField(
        default=0,
        help_text="Order of images in the post (0-based)"
    )
    
    # Image description for accessibility
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Alternative text for accessibility (optional)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Forum Post Image"
        verbose_name_plural = "Forum Post Images"
        ordering = ['upload_order', 'created_at']
        unique_together = ['post', 'upload_order']
    
    def __str__(self):
        return f"Image {self.upload_order + 1} for post {self.post.id}: {self.original_filename}"
    
    @property
    def display_name(self):
        """Get a user-friendly display name for the image."""
        if self.alt_text:
            return self.alt_text
        return f"Image {self.upload_order + 1}"
    
    @property
    def file_size_mb(self):
        """Get file size in MB for display."""
        return round(self.file_size / (1024 * 1024), 2)
    
    def save(self, *args, **kwargs):
        """Auto-set upload_order if not specified."""
        if self.upload_order is None or self.upload_order == 0:
            max_order = ForumPostImage.objects.filter(post=self.post).aggregate(
                models.Max('upload_order')
            )['upload_order__max']
            self.upload_order = (max_order or -1) + 1
        
        super().save(*args, **kwargs)


class PostReaction(models.Model):
    """
    Stores user reactions to forum posts.
    
    Supports multiple reaction types (like, love, helpful, thanks) to encourage
    community engagement and provide meaningful feedback to post authors.
    """
    
    # Reaction type choices
    REACTION_CHOICES = [
        ('like', 'Like'),
        ('love', 'Love'),
        ('helpful', 'Helpful'),
        ('thanks', 'Thanks'),
    ]
    
    # Core relationships
    post = models.ForeignKey(
        'forum_conversation.Post',
        on_delete=models.CASCADE,
        related_name='reactions',
        help_text="The forum post this reaction belongs to"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='forum_reactions',
        help_text="The user who made this reaction"
    )
    
    # Reaction details
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES,
        help_text="Type of reaction (like, love, helpful, thanks)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Soft delete support
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this reaction is currently active"
    )
    
    class Meta:
        verbose_name = "Post Reaction"
        verbose_name_plural = "Post Reactions"
        # Ensure one reaction type per user per post
        unique_together = ['post', 'user', 'reaction_type']
        # Optimize queries
        indexes = [
            models.Index(fields=['post', 'reaction_type']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['post', 'user']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} {self.reaction_type} on post {self.post.id}"
    
    @classmethod
    def get_post_reaction_counts(cls, post_id):
        """Get reaction counts for a specific post."""
        return cls.objects.filter(
            post_id=post_id,
            is_active=True
        ).values('reaction_type').annotate(
            count=models.Count('id')
        ).order_by('reaction_type')
    
    @classmethod
    def get_user_reactions_for_post(cls, post_id, user_id):
        """Get a user's reactions for a specific post."""
        if not user_id:
            return []
        
        return cls.objects.filter(
            post_id=post_id,
            user_id=user_id,
            is_active=True
        ).values_list('reaction_type', flat=True)
    
    @classmethod
    def toggle_reaction(cls, post_id, user_id, reaction_type):
        """
        Toggle a user's reaction on a post.
        Returns (reaction_obj, created) tuple similar to get_or_create.
        """
        try:
            # Try to get existing reaction
            reaction = cls.objects.get(
                post_id=post_id,
                user_id=user_id,
                reaction_type=reaction_type
            )
            
            # Toggle active state
            reaction.is_active = not reaction.is_active
            reaction.save()
            
            return reaction, False  # Existing reaction toggled
            
        except cls.DoesNotExist:
            # Create new reaction
            reaction = cls.objects.create(
                post_id=post_id,
                user_id=user_id,
                reaction_type=reaction_type,
                is_active=True
            )
            
            return reaction, True  # New reaction created