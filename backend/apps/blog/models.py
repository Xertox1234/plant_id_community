"""
Blog models for the Plant Community application.

This module contains Wagtail page models for the blog system with AI-enhanced
content creation and plant-specific features.
"""

from typing import List, Tuple, Optional
from django.db import models
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.urls import reverse
from django.core.paginator import Paginator
from django.utils.text import slugify
from wagtail.models import Page, Orderable
from wagtail.fields import StreamField, RichTextField
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel
from wagtail.search import index
from wagtail.snippets.models import register_snippet
from wagtail_headless_preview.models import HeadlessPreviewMixin
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

User = get_user_model()


# FLAT StreamField blocks for blog content - NO NESTING!
class BlogStreamBlocks(blocks.StreamBlock):
    """
    Flat StreamField blocks for blog content with AI assistance.
    IMPORTANT: No nested blocks allowed per architecture requirement!
    """
    
    heading = blocks.CharBlock(
        icon="title",
        template="blog/blocks/heading.html",
        help_text="Add a heading to structure your content"
    )
    
    paragraph = blocks.RichTextBlock(
        icon="pilcrow",
        template="blog/blocks/paragraph.html",
        help_text="Add paragraph text with AI assistance for plant content"
    )
    
    # Unused blocks removed (TODO #033) - can be re-added when needed:
    # - image (use paragraph with embedded images instead)
    # - care_instructions (no instances in blog posts)
    # - gallery (no instances in blog posts)
    # - video_embed (no instances in blog posts)

    quote = blocks.StructBlock([
        ('quote_text', blocks.RichTextBlock()),
        ('attribution', blocks.CharBlock(required=False, help_text="Who said this quote?"))
    ], icon="openquote", template="blog/blocks/quote.html")

    code = blocks.StructBlock([
        ('language', blocks.ChoiceBlock(choices=[
            ('python', 'Python'),
            ('javascript', 'JavaScript'),
            ('html', 'HTML'),
            ('css', 'CSS'),
            ('bash', 'Bash'),
            ('json', 'JSON'),
        ], required=False)),
        ('code', blocks.TextBlock())
    ], icon="code", template="blog/blocks/code.html")

    plant_spotlight = blocks.StructBlock([
        ('plant_name', blocks.CharBlock(
            help_text="🌱 Enter plant name - auto-population will fill other fields"
        )),
        ('scientific_name', blocks.CharBlock(
            required=False,
            help_text="Scientific name (auto-populated from plant database)"
        )),
        ('description', blocks.RichTextBlock(
            help_text="Plant description (auto-populated from database or AI-generated)"
        )),
        ('care_difficulty', blocks.ChoiceBlock(choices=[
            ('easy', 'Easy'),
            ('moderate', 'Moderate'),
            ('difficult', 'Difficult'),
        ], help_text="Care difficulty level (auto-calculated from plant requirements)")),
        ('image', ImageChooserBlock(
            required=False,
            help_text="Plant image (suggestions provided from database)"
        ))
    ], icon="snippet", template="blog/blocks/plant_spotlight.html",
    help_text="Spotlight a specific plant with auto-populated data from our plant database")

    call_to_action = blocks.StructBlock([
        ('cta_title', blocks.CharBlock()),
        ('cta_description', blocks.RichTextBlock(required=False)),
        ('button_text', blocks.CharBlock()),
        ('button_url', blocks.URLBlock()),
        ('button_style', blocks.ChoiceBlock(choices=[
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
            ('outline', 'Outline'),
        ], default='primary'))
    ], icon="link", template="blog/blocks/call_to_action.html")


# Tag models for blog posts
class BlogPostTag(TaggedItemBase):
    content_object = ParentalKey(
        'blog.BlogPostPage',
        related_name='tagged_items',
        on_delete=models.CASCADE
    )


# Analytics models (Phase 6.2)
class BlogPostView(models.Model):
    """
    Track individual page views for blog post analytics.

    This model stores detailed view tracking data including:
    - User information (if authenticated)
    - IP address for anonymous tracking
    - User agent for device/browser analytics
    - Referrer for traffic source analysis
    - Timestamp for temporal analytics

    Used to generate:
    - Popular posts rankings
    - Trending content identification
    - Traffic source analytics
    - User engagement metrics
    """

    post = models.ForeignKey(
        'blog.BlogPostPage',
        on_delete=models.CASCADE,
        related_name='views',
        help_text="The blog post that was viewed"
    )

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User who viewed the post (if authenticated)"
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the viewer"
    )

    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text="Browser user agent string"
    )

    referrer = models.URLField(
        blank=True,
        help_text="Referrer URL (where the user came from)"
    )

    viewed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the post was viewed"
    )

    class Meta:
        verbose_name = "Blog Post View"
        verbose_name_plural = "Blog Post Views"
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['post', '-viewed_at']),
            models.Index(fields=['-viewed_at']),
            models.Index(fields=['user', '-viewed_at']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else self.ip_address
        return f"{self.post.title} - {user_str} at {self.viewed_at}"


# Snippet models
@register_snippet
class BlogCategory(models.Model):
    """
    Blog category snippet model.
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name"
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly name"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Category description"
    )
    
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="CSS icon class (e.g., 'fas fa-leaf')"
    )
    
    color = models.CharField(
        max_length=7,
        default="#28a745",
        help_text="Category color (hex code)"
    )
    
    is_featured = models.BooleanField(
        default=False,
        help_text="Show this category prominently"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    panels = [
        FieldPanel('name'),
        FieldPanel('slug'),
        FieldPanel('description'),
        MultiFieldPanel([
            FieldPanel('icon'),
            FieldPanel('color'),
            FieldPanel('is_featured'),
        ], heading="Display Settings")
    ]
    
    class Meta:
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


@register_snippet
class BlogSeries(models.Model):
    """
    Blog series for multi-part content.
    """
    
    title = models.CharField(
        max_length=200,
        help_text="Series title"
    )
    
    slug = models.SlugField(
        max_length=200,
        unique=True,
        help_text="URL-friendly name"
    )
    
    description = models.TextField(
        help_text="Series description"
    )
    
    image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Series cover image"
    )
    
    is_completed = models.BooleanField(
        default=False,
        help_text="Mark series as completed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    panels = [
        FieldPanel('title'),
        FieldPanel('slug'),
        FieldPanel('description'),
        FieldPanel('image'),
        FieldPanel('is_completed'),
    ]
    
    class Meta:
        verbose_name = "Blog Series"
        verbose_name_plural = "Blog Series"
        ordering = ['title']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


# Main blog page models
class BlogBasePage(Page):
    """
    Abstract base class for all blog-related Wagtail pages.
    """
    
    # SEO and metadata
    meta_description = models.TextField(
        max_length=160,
        blank=True,
        help_text="Meta description for search engines"
    )
    
    social_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Image for social media sharing"
    )
    
    # Display settings
    show_in_menus_default = True
    
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('meta_description'),
            FieldPanel('social_image'),
        ], heading="SEO Settings")
    ]
    
    search_fields = Page.search_fields + [
        index.SearchField('meta_description'),
    ]
    
    class Meta:
        abstract = True


class BlogIndexPage(BlogBasePage):
    """
    Main blog index page that displays blog posts and categories.
    """
    
    # Page content
    introduction = RichTextField(
        blank=True,
        help_text="Introduction text for the blog"
    )
    
    # Display settings
    posts_per_page = models.IntegerField(
        default=12,
        help_text="Number of posts to display per page"
    )
    
    show_featured_posts = models.BooleanField(
        default=True,
        help_text="Show featured posts section"
    )
    
    show_categories = models.BooleanField(
        default=True,
        help_text="Show categories section"
    )
    
    featured_posts_title = models.CharField(
        max_length=100,
        default="Featured Posts",
        help_text="Title for featured posts section"
    )
    
    content_panels = BlogBasePage.content_panels + [
        FieldPanel('introduction'),
        MultiFieldPanel([
            FieldPanel('posts_per_page'),
            FieldPanel('show_featured_posts'),
            FieldPanel('featured_posts_title'),
            FieldPanel('show_categories'),
        ], heading="Display Settings")
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get blog posts
        blog_posts = BlogPostPage.objects.live().public().order_by('-first_published_at')
        
        # Pagination
        paginator = Paginator(blog_posts, self.posts_per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Featured posts
        featured_posts = []
        if self.show_featured_posts:
            featured_posts = BlogPostPage.objects.live().public().filter(
                is_featured=True
            ).order_by('-first_published_at')[:3]
        
        # Categories
        categories = []
        if self.show_categories:
            categories = BlogCategory.objects.filter(is_featured=True)
        
        context.update({
            'blog_posts': page_obj,
            'featured_posts': featured_posts,
            'categories': categories,
            'introduction': self.introduction,
        })
        
        return context
    
    class Meta:
        verbose_name = "Blog Index Page"


class BlogCategoryPage(BlogBasePage):
    """
    Page for displaying posts in a specific category.
    """
    
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.PROTECT,
        help_text="The category this page represents"
    )
    
    posts_per_page = models.IntegerField(
        default=12,
        help_text="Number of posts to display per page"
    )
    
    content_panels = BlogBasePage.content_panels + [
        FieldPanel('category'),
        FieldPanel('posts_per_page'),
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get posts in this category
        blog_posts = BlogPostPage.objects.live().public().filter(
            categories=self.category
        ).order_by('-first_published_at')
        
        # Pagination
        paginator = Paginator(blog_posts, self.posts_per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context.update({
            'blog_posts': page_obj,
            'category': self.category,
        })
        
        return context
    
    class Meta:
        verbose_name = "Blog Category Page"


class BlogAuthorPage(BlogBasePage):
    """
    Page for displaying author information and their posts.
    """
    
    author = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        help_text="The user this author page represents"
    )
    
    bio = RichTextField(
        help_text="Author bio and background information"
    )
    
    expertise_areas = ClusterTaggableManager(
        through="blog.BlogAuthorExpertise",
        blank=True,
        help_text="Areas of plant expertise"
    )
    
    social_links = StreamField([
        ('website', blocks.URLBlock(icon="link")),
        ('twitter', blocks.URLBlock(icon="link")),
        ('instagram', blocks.URLBlock(icon="link")),
        ('youtube', blocks.URLBlock(icon="link")),
    ], blank=True, help_text="Social media links", use_json_field=True)
    
    posts_per_page = models.IntegerField(
        default=12,
        help_text="Number of posts to display per page"
    )
    
    content_panels = BlogBasePage.content_panels + [
        FieldPanel('author'),
        FieldPanel('bio'),
        FieldPanel('expertise_areas'),
        FieldPanel('social_links'),
        FieldPanel('posts_per_page'),
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get posts by this author
        blog_posts = BlogPostPage.objects.live().public().filter(
            author=self.author
        ).order_by('-first_published_at')
        
        # Pagination
        paginator = Paginator(blog_posts, self.posts_per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context.update({
            'blog_posts': page_obj,
            'author': self.author,
            'bio': self.bio,
            'expertise_areas': self.expertise_areas.all(),
            'social_links': self.social_links,
        })
        
        return context
    
    class Meta:
        verbose_name = "Blog Author Page"


# Tag models for author expertise
class BlogAuthorExpertise(TaggedItemBase):
    content_object = ParentalKey(
        'blog.BlogAuthorPage',
        related_name='expertise_items',
        on_delete=models.CASCADE
    )


class BlogPostPage(HeadlessPreviewMixin, BlogBasePage):
    """
    Individual blog post page with AI-enhanced content creation.
    Includes headless preview support for React/Flutter frontends.
    """
    
    # Author and publishing info
    author = models.ForeignKey(
        User,
        null=False,
        on_delete=models.PROTECT,
        help_text="Post author"
    )

    publish_date = models.DateField(
        help_text="Date to publish this post"
    )

    # Content
    introduction = RichTextField(
        blank=False,
        help_text="Brief introduction or excerpt"
    )
    
    # Flat content blocks with AI assistance - NO NESTING
    content_blocks = StreamField(
        BlogStreamBlocks(),
        help_text="Main content blocks with AI assistance for plant-related content",
        use_json_field=True
    )
    
    # Categorization
    categories = ParentalManyToManyField(
        BlogCategory,
        blank=True,
        help_text="Categories for this post"
    )
    
    tags = ClusterTaggableManager(
        through=BlogPostTag,
        blank=True,
        help_text="Tags for this post"
    )
    
    series = models.ForeignKey(
        BlogSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Part of a blog series?"
    )
    
    series_order = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Order within the series"
    )
    
    # Featured content
    featured_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Main image for this post"
    )
    
    is_featured = models.BooleanField(
        default=False,
        help_text="Feature this post on the blog index"
    )
    
    # Reading settings
    reading_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated reading time in minutes (auto-calculated)"
    )
    
    # Plant-specific fields
    related_plant_species = ParentalManyToManyField(
        'plant_identification.PlantSpecies',
        blank=True,
        help_text="Plant species mentioned in this post"
    )
    
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ],
        blank=True,
        help_text="Difficulty level for plant care content"
    )
    
    # Engagement settings
    allow_comments = models.BooleanField(
        default=True,
        help_text="Allow comments on this post"
    )

    # Analytics (Phase 6.2)
    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this post has been viewed"
    )
    
    content_panels = BlogBasePage.content_panels + [
        MultiFieldPanel([
            FieldPanel('author'),
            FieldPanel('publish_date'),
        ], heading="Publishing"),
        FieldPanel('introduction'),
        FieldPanel('content_blocks'),
        MultiFieldPanel([
            FieldPanel('categories'),
            FieldPanel('tags'),
            FieldPanel('series'),
            FieldPanel('series_order'),
        ], heading="Categorization"),
        MultiFieldPanel([
            FieldPanel('featured_image'),
            FieldPanel('is_featured'),
            FieldPanel('difficulty_level'),
        ], heading="Display Settings"),
        MultiFieldPanel([
            FieldPanel('related_plant_species'),
            FieldPanel('allow_comments'),
        ], heading="Plant Community Features")
    ]
    
    search_fields = BlogBasePage.search_fields + [
        index.SearchField('introduction'),
        index.SearchField('content_blocks'),
        index.FilterField('author'),
        index.FilterField('publish_date'),
        index.FilterField('categories'),
    ]
    
    # API fields for Wagtail API v2
    api_fields = [
        'author',
        'publish_date',
        'introduction',
        'content_blocks',
        'categories',
        'tags',
        'series',
        'series_order',
        'featured_image',
        'is_featured',
        'reading_time',
        'related_plant_species',
        'difficulty_level',
        'allow_comments',
        'view_count',  # Phase 6.2: Analytics
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Related posts (same categories or tags)
        related_posts = BlogPostPage.objects.live().public().exclude(
            id=self.id
        ).filter(
            categories__in=self.categories.all()
        ).distinct().order_by('-first_published_at')[:3]
        
        context.update({
            'related_posts': related_posts,
            'reading_time': self.reading_time or self.calculate_reading_time(),
        })
        
        return context
    
    def calculate_reading_time(self):
        """Calculate estimated reading time based on content."""
        # Simple calculation: ~200 words per minute
        word_count = 0
        
        # Count words in introduction
        if self.introduction:
            word_count += len(self.introduction.split())
        
        # Count words in content blocks (simplified)
        for block in self.content_blocks:
            if hasattr(block.value, 'source'):  # RichTextBlock
                word_count += len(str(block.value).split())
            elif isinstance(block.value, str):
                word_count += len(block.value.split())
        
        return max(1, word_count // 200)  # At least 1 minute

    # Headless Preview Configuration (Phase 3)
    @property
    def preview_modes(self) -> List[Tuple[str, str]]:
        """
        Define preview modes for different frontend platforms.

        Returns:
            List of tuples: (mode_key, mode_display_name)
        """
        return [
            ('', 'Default (Web)'),
            ('mobile', 'Mobile (Flutter)'),
        ]

    def get_client_root_url(self, request: Optional[HttpRequest] = None, mode: str = '') -> str:
        """
        Return the preview URL for the specified mode.

        IMPORTANT: This returns the BASE URL. The wagtail-headless-preview
        library automatically appends {content_type}/{token}/ dynamically.

        Args:
            request: The HTTP request object (optional, unused)
            mode: Preview mode - '' for web, 'mobile' for Flutter

        Returns:
            Base preview URL without content_type/token placeholders

        Example:
            Base URL: http://localhost:5173/blog/preview
            Library appends: /blog.blogpostpage/abc123xyz/
        """
        if mode == 'mobile':
            # Flutter deep link for mobile preview
            # Format: plantid://blog/preview
            return 'plantid://blog/preview'

        # React web preview (default)
        # URL structure: http://localhost:5173/blog/preview/{content_type}/{token}/
        # The {content_type} and {token} are replaced by wagtail-headless-preview
        from django.conf import settings
        preview_url = settings.HEADLESS_PREVIEW_CLIENT_URLS.get('default')

        # Extract base URL without placeholder variables for return
        # The library will append the content_type and token dynamically
        return preview_url.rsplit('/{content_type}', 1)[0] if preview_url else 'http://localhost:5173/blog/preview'

    def save(self, *args, **kwargs):
        # Auto-calculate reading time
        if not self.reading_time:
            self.reading_time = self.calculate_reading_time()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Blog Post"
        indexes = [
            # Index on view_count (local field) - migration 0006
            models.Index(fields=['-view_count'], name='blog_post_view_count_idx'),
            # Index on publish_date (local field) - migration 0007
            models.Index(fields=['-publish_date'], name='blog_post_publish_date_idx'),
        ]
        # NOTE: Cannot add indexes on inherited fields (first_published_at) in Meta class
        # Composite index on categories junction table created via RunSQL (see migration 0007)


class BlogComment(models.Model):
    """
    Comment model for blog posts with moderation support.
    """
    
    post = models.ForeignKey(
        BlogPostPage,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text="Blog post this comment is on"
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="Comment author"
    )
    
    content = models.TextField(
        help_text="Comment content"
    )
    
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies',
        help_text="Parent comment if this is a reply"
    )
    
    # Moderation
    is_approved = models.BooleanField(
        default=True,
        help_text="Is this comment approved for display?"
    )
    
    is_flagged = models.BooleanField(
        default=False,
        help_text="Has this comment been flagged by users?"
    )
    
    flag_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this comment has been flagged"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['is_approved', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"
    
    @property
    def is_reply(self):
        """Check if this is a reply to another comment."""
        return self.parent is not None
    
    def get_replies(self):
        """Get approved replies to this comment."""
        return self.replies.filter(is_approved=True).order_by('created_at')


class BlogNewsletter(models.Model):
    """
    Newsletter signup model for blog readers.
    """
    
    email = models.EmailField(
        unique=True,
        help_text="Subscriber email address"
    )
    
    first_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Subscriber first name"
    )
    
    # Subscription preferences
    is_active = models.BooleanField(
        default=True,
        help_text="Is subscription active?"
    )
    
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('weekly', 'Weekly Digest'),
            ('monthly', 'Monthly Digest'),
            ('instant', 'Instant Notifications'),
        ],
        default='weekly',
        help_text="Newsletter frequency preference"
    )
    
    categories = models.ManyToManyField(
        BlogCategory,
        blank=True,
        help_text="Categories of interest"
    )
    
    # Plant-specific preferences
    plant_types_interest = models.TextField(
        blank=True,
        help_text="Plant types of interest (comma-separated)"
    )
    
    experience_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ],
        blank=True,
        help_text="Gardening experience level"
    )
    
    # Tracking
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text="How did they find us?"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address when subscribed"
    )
    
    # Timestamps
    subscribed_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = "Newsletter Subscription"
        verbose_name_plural = "Newsletter Subscriptions"
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.email} ({status})"
    
    def unsubscribe(self):
        """Mark subscription as inactive."""
        from django.utils import timezone
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=['is_active', 'unsubscribed_at'])
