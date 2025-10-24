# Wagtail Blog Implementation: Comprehensive Documentation Research

**Research Date**: October 23, 2025
**Wagtail Version**: 7.0.3 (installed)
**Latest Stable**: 7.1.1 (documentation references)
**Project**: Plant ID Community Backend

---

## Table of Contents

1. [Summary](#summary)
2. [Version Information](#version-information)
3. [Wagtail Core Documentation](#wagtail-core-documentation)
4. [StreamField Reference](#streamfield-reference)
5. [Wagtail API v2](#wagtail-api-v2)
6. [Images and Media](#images-and-media)
7. [Advanced Blog Features](#advanced-blog-features)
8. [Testing](#testing)
9. [SEO and Metadata](#seo-and-metadata)
10. [References](#references)

---

## Summary

This document provides comprehensive research on implementing a full-featured blog using Wagtail 7.x. The research covers official Wagtail documentation, community best practices, and real-world implementation patterns for:

- **Content Management**: StreamField blocks, rich text editing, image handling
- **Blog Features**: Tags, categories, pagination, archives, search
- **API Integration**: REST API endpoints, custom serializers, filtering
- **SEO**: Meta tags, sitemaps, OpenGraph, Twitter cards
- **Testing**: Test utilities, fixtures, API endpoint testing

All documentation references are from official Wagtail sources (docs.wagtail.org) and well-maintained community resources.

---

## Version Information

### Installed Version
- **Wagtail**: 7.0.3
- **Location**: `/Users/williamtower/projects/plant_id_community/backend/venv/lib/python3.13/site-packages/wagtail/`
- **Python**: 3.13
- **Django**: 5.2.7
- **Django REST Framework**: 3.16.1

### Current Dependencies
```python
# From requirements.txt
wagtail==7.0.3
django-modelcluster==6.4
django-taggit==6.1.0
django-treebeard==4.7.1
```

### Key Features Available in 7.0.3
- StreamField with JSON storage (use_json_field=True)
- ImageBlock with accessibility features (alt text, decorative flag)
- Wagtail API v2 with full filtering support
- RoutablePageMixin for custom URL patterns
- ClusterTaggableManager for in-memory tag management
- Django 5.2+ compatibility

---

## Wagtail Core Documentation

### 1. Page Models

**Official Documentation**: https://docs.wagtail.org/en/stable/topics/pages.html

#### Core Concepts

All Wagtail page types inherit from `wagtail.models.Page` and function as Django models. Each page represents a distinct content category with customizable fields and editing interfaces.

#### Basic Page Structure

```python
from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel
from wagtail import blocks
from wagtail.images.blocks import ImageBlock

class BlogPage(Page):
    # Database fields
    publication_date = models.DateField("Post date")
    intro = models.CharField(max_length=250)
    body = StreamField([
        ('heading', blocks.CharBlock(form_classname="title")),
        ('paragraph', blocks.RichTextBlock()),
        ('image', ImageBlock()),
    ], use_json_field=True)

    # Editor panels
    content_panels = Page.content_panels + [
        FieldPanel('publication_date'),
        FieldPanel('intro'),
        FieldPanel('body'),
    ]

    # Template context
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context['recent_posts'] = BlogPage.objects.live().public().order_by('-publication_date')[:5]
        return context

    # Meta
    class Meta:
        verbose_name = "Blog Post"
```

#### Essential Attributes

**Panel Organization**:
- `content_panels`: Main editorial content
- `promote_panels`: SEO metadata, tags, thumbnails
- `settings_panels`: Publication scheduling, URL configuration

**Search Configuration**:
```python
from wagtail.search import index

class BlogPage(Page):
    search_fields = Page.search_fields + [
        index.SearchField('intro'),
        index.SearchField('body'),
        index.FilterField('publication_date'),
    ]
```

**Page Hierarchy Control**:
```python
class BlogPage(Page):
    parent_page_types = ['BlogIndexPage']  # Can only be created under BlogIndexPage
    subpage_types = []  # Cannot have children
```

#### Template Rendering

**Default Template Path**: `<app_label>/<model_name_snake_case>.html`
- Example: `BlogPage` → `blog/blog_page.html`

**Template Variables**:
```django
{% load wagtailcore_tags %}

<h1>{{ page.title }}</h1>
<p class="meta">{{ page.publication_date }}</p>
<div class="intro">{{ page.intro }}</div>

{% include_block page.body %}
```

**Dynamic Template Selection**:
```python
def get_template(self, request, *args, **kwargs):
    if request.is_ajax():
        return 'blog/blog_page_ajax.html'
    return 'blog/blog_page.html'
```

#### Custom URL Patterns

Override `get_url_parts()` for custom routing:
```python
def get_url_parts(self, request=None):
    site_id, root_url, page_path = super().get_url_parts(request)
    # Customize page_path
    return (site_id, root_url, custom_path)
```

#### Best Practices

- Use `verbose_name` in Meta class for user-friendly page type names
- Always pass `request` argument to `get_url()` for per-request caching
- Field names must differ from class names (Django constraint)
- Use `page_description` to help editors understand page purpose
- Override `serve()` method for custom rendering logic (JSON responses, etc.)

---

## StreamField Reference

**Official Documentation**:
- Overview: https://docs.wagtail.org/en/v7.0.3/topics/streamfield.html
- Block Reference: https://docs.wagtail.org/en/stable/reference/streamfield/blocks.html

### Purpose and Architecture

StreamField provides a content editing model for pages with non-fixed structures (blog posts, news articles) where content is composed as a sequence of reusable "blocks" that can be arranged in any order. Data is stored as JSON, preserving full informational content rather than just HTML.

### Basic Usage

```python
from wagtail.fields import StreamField
from wagtail import blocks
from wagtail.images.blocks import ImageBlock

class BlogPage(Page):
    body = StreamField([
        ('heading', blocks.CharBlock(form_classname="title")),
        ('paragraph', blocks.RichTextBlock()),
        ('image', ImageBlock()),
        ('quote', blocks.BlockQuoteBlock()),
        ('embed', blocks.EmbedBlock()),
    ], use_json_field=True, blank=True)
```

**Important**: `use_json_field=True` is required in Wagtail 4+ to use Django's native JSONField.

### Built-in Block Types

#### Text Input Blocks

**CharBlock** - Single-line text
```python
blocks.CharBlock(
    max_length=255,
    min_length=10,
    required=True,
    help_text="Enter a heading",
    validators=[...],
    form_classname="title"  # CSS class for admin
)
```

**TextBlock** - Multi-line textarea
```python
blocks.TextBlock(
    rows=5,  # Number of rows in admin
    max_length=1000,
    help_text="Enter body text"
)
```

**RichTextBlock** - WYSIWYG editor
```python
blocks.RichTextBlock(
    features=['h2', 'h3', 'bold', 'italic', 'link', 'ol', 'ul'],
    editor='default',  # Or custom editor from settings
    max_length=5000
)
```

**EmailBlock** - Email validation
```python
blocks.EmailBlock(required=True)
```

**URLBlock** - URL validation
```python
blocks.URLBlock(help_text="Enter a valid URL")
```

#### Numeric Blocks

**IntegerBlock** - Whole numbers
```python
blocks.IntegerBlock(min_value=0, max_value=100)
```

**FloatBlock** - Decimal numbers
```python
blocks.FloatBlock(min_value=0.0, max_value=1.0)
```

**DecimalBlock** - Precise decimals
```python
blocks.DecimalBlock(max_digits=10, decimal_places=2)
```

#### Selection Blocks

**BooleanBlock** - Checkbox
```python
blocks.BooleanBlock(required=False, default=True)
```

**ChoiceBlock** - Dropdown
```python
blocks.ChoiceBlock(choices=[
    ('left', 'Left aligned'),
    ('center', 'Center aligned'),
    ('right', 'Right aligned'),
])
```

#### Date/Time Blocks

**DateBlock** - Date picker
```python
blocks.DateBlock(format='%Y-%m-%d')
```

**TimeBlock** - Time picker
```python
blocks.TimeBlock(format='%H:%M')
```

**DateTimeBlock** - Combined date/time
```python
blocks.DateTimeBlock()
```

#### Chooser Blocks

**ImageBlock** - Image with alt text (RECOMMENDED)
```python
ImageBlock(required=False)  # Built-in accessibility features
```

**ImageChooserBlock** - Legacy image selector (use ImageBlock instead)
```python
blocks.ImageChooserBlock(required=False)
```

**PageChooserBlock** - Page selection
```python
blocks.PageChooserBlock(
    page_type='blog.BlogPage',  # Filter by page type
    can_choose_root=False
)
```

**DocumentChooserBlock** - Document upload/selection
```python
blocks.DocumentChooserBlock()
```

**SnippetChooserBlock** - Snippet selection
```python
from wagtail.snippets.blocks import SnippetChooserBlock
SnippetChooserBlock('blog.Author', required=True)
```

**EmbedBlock** - Media embeds (YouTube, Vimeo, etc.)
```python
blocks.EmbedBlock(
    max_width=800,
    max_height=600,
    help_text="Paste a YouTube or Vimeo URL"
)
```

#### Structural Blocks

**StructBlock** - Grouped fields

```python
class PersonBlock(blocks.StructBlock):
    first_name = blocks.CharBlock()
    surname = blocks.CharBlock()
    photo = ImageBlock(required=False)
    biography = blocks.RichTextBlock()

    class Meta:
        icon = 'user'
        label = 'Person'
        form_classname = 'person-block'
```

**ListBlock** - Repeatable block sequence
```python
blocks.ListBlock(
    blocks.CharBlock(label="Ingredient"),
    min_num=1,
    max_num=10
)
```

**StreamBlock** - Mixed block types
```python
class CarouselBlock(blocks.StreamBlock):
    image = ImageBlock()
    video = blocks.EmbedBlock()
    quote = blocks.BlockQuoteBlock()

    class Meta:
        min_num = 1
        max_num = 10
        block_counts = {
            'video': {'max_num': 3},  # Limit specific block types
        }
```

**StaticBlock** - Content-less placeholder
```python
blocks.StaticBlock(
    admin_text='Latest blog posts will be shown here.',
    template='blog/blocks/latest_posts.html'
)
```

### Advanced Block Features

#### Custom Templates

```python
('paragraph', blocks.RichTextBlock(template='blog/blocks/paragraph.html'))
```

Template file (`blog/blocks/paragraph.html`):
```django
<div class="prose">
    {{ value }}
</div>
```

#### Block Context Customization

```python
class PersonBlock(blocks.StructBlock):
    # ... fields ...

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context['author_count'] = Person.objects.count()
        return context
```

#### Block Constraints

```python
body = StreamField([
    ('heading', blocks.CharBlock()),
    ('paragraph', blocks.RichTextBlock()),
    ('image', ImageBlock()),
],
    min_num=1,  # Minimum total blocks
    max_num=20,  # Maximum total blocks
    block_counts={
        'heading': {'min_num': 1, 'max_num': 5},
        'image': {'max_num': 10},
    },
    use_json_field=True
)
```

### Template Rendering

**Simple Rendering**:
```django
{% load wagtailcore_tags %}
{% include_block page.body %}
```

**Granular Control**:
```django
{% for block in page.body %}
    {% if block.block_type == 'heading' %}
        <h2 class="heading">{{ block.value }}</h2>
    {% elif block.block_type == 'paragraph' %}
        <div class="paragraph">
            {% include_block block %}
        </div>
    {% elif block.block_type == 'image' %}
        {% image block.value fill-800x600 class="featured-image" %}
    {% else %}
        {% include_block block %}
    {% endif %}
{% endfor %}
```

### Common Block Patterns for Blogs

**Article Body**:
```python
body = StreamField([
    ('heading', blocks.CharBlock(form_classname="title")),
    ('subheading', blocks.CharBlock(form_classname="subtitle")),
    ('paragraph', blocks.RichTextBlock(features=['bold', 'italic', 'link', 'ol', 'ul'])),
    ('image', ImageBlock()),
    ('quote', blocks.BlockQuoteBlock()),
    ('code', blocks.TextBlock(help_text="Code snippet")),
    ('embed', blocks.EmbedBlock()),
], use_json_field=True)
```

**Feature Cards**:
```python
class FeatureBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    description = blocks.TextBlock()
    image = ImageBlock()
    link = blocks.PageChooserBlock(required=False)

    class Meta:
        icon = 'cog'
        template = 'blog/blocks/feature.html'

features = StreamField([
    ('feature', FeatureBlock()),
], use_json_field=True)
```

---

## Wagtail API v2

**Official Documentation**:
- Configuration: https://docs.wagtail.org/en/stable/advanced_topics/api/v2/configuration.html
- Usage: https://docs.wagtail.org/en/stable/advanced_topics/api/v2/usage.html

### Setup and Installation

**1. Add to INSTALLED_APPS**:
```python
INSTALLED_APPS = [
    # ...
    'rest_framework',  # Optional, for browsable API
    'wagtail.api.v2',
    # ...
]
```

**2. Create API Router** (`api.py`):
```python
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet

api_router = WagtailAPIRouter('wagtailapi')

# Register endpoints
api_router.register_endpoint('pages', PagesAPIViewSet)
api_router.register_endpoint('images', ImagesAPIViewSet)
api_router.register_endpoint('documents', DocumentsAPIViewSet)
```

**3. URL Configuration** (`urls.py`):
```python
from .api import api_router

urlpatterns = [
    path('api/v2/', api_router.urls),
    # ... other patterns
]
```

### API Endpoints

**Available endpoints**:
- `/api/v2/pages/` - Page listing and detail
- `/api/v2/images/` - Image listing and detail
- `/api/v2/documents/` - Document listing and detail

### Exposing Custom Fields

**Model Definition**:
```python
from wagtail.api import APIField
from rest_framework.fields import DateField

class BlogPage(Page):
    publication_date = models.DateField()
    author_name = models.CharField(max_length=100)
    body = StreamField([...], use_json_field=True)

    # Expose fields to API
    api_fields = [
        APIField('publication_date'),
        APIField('author_name'),
        APIField('body'),
    ]
```

**Custom Serialization**:
```python
from wagtail.images.api.fields import ImageRenditionField

class BlogPage(Page):
    header_image = models.ForeignKey('wagtailimages.Image', ...)

    api_fields = [
        APIField('publication_date',
                serializer=DateField(format='%B %d, %Y')),
        APIField('header_image_thumbnail',
                serializer=ImageRenditionField('fill-300x200', source='header_image')),
    ]
```

### Filtering Options

**Type Filtering**:
```
GET /api/v2/pages/?type=blog.BlogPage
```

**Field Selection**:
```
GET /api/v2/pages/?fields=title,publication_date,author_name
```

**Descendant Filtering**:
```
GET /api/v2/pages/?descendant_of=5
```

**Child Filtering**:
```
GET /api/v2/pages/?child_of=5
```

**Search**:
```
GET /api/v2/pages/?search=django
```

**Ordering**:
```
GET /api/v2/pages/?order=-publication_date
```

### Custom API Endpoints

**Create Custom ViewSet**:
```python
from rest_framework.renderers import JSONRenderer
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.api.v2.filters import FieldsFilter, OrderingFilter

class BlogAPIViewSet(PagesAPIViewSet):
    renderer_classes = [JSONRenderer]

    # Customize model
    model = BlogPage

    # Custom filters
    filter_backends = [
        FieldsFilter,
        OrderingFilter,
        # Add custom filters
    ]

    # Customize queryset
    def get_queryset(self):
        return super().get_queryset().filter(
            live=True
        ).order_by('-publication_date')

# Register custom endpoint
api_router.register_endpoint('blog', BlogAPIViewSet)
```

### API Settings

**Django Settings**:
```python
# Maximum items per page
WAGTAILAPI_LIMIT_MAX = 100  # Default: 20

# Enable/disable search
WAGTAILAPI_SEARCH_ENABLED = True  # Default: True

# Base URL for cache invalidation
WAGTAILAPI_BASE_URL = 'https://yourdomain.com'
```

### Authentication

**Token Authentication**:
```python
INSTALLED_APPS = [
    'rest_framework.authtoken',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ]
}

# In ViewSet
from rest_framework.permissions import IsAuthenticated

class SecureBlogAPIViewSet(PagesAPIViewSet):
    permission_classes = [IsAuthenticated]
```

### Response Format

**Listing Response**:
```json
{
    "meta": {
        "total_count": 42
    },
    "items": [
        {
            "id": 15,
            "meta": {
                "type": "blog.BlogPage",
                "detail_url": "http://api.example.com/api/v2/pages/15/",
                "html_url": "http://example.com/blog/my-post/",
                "slug": "my-post",
                "first_published_at": "2025-10-23T10:00:00Z"
            },
            "title": "My Blog Post",
            "publication_date": "2025-10-23",
            "author_name": "John Doe"
        }
    ]
}
```

---

## Images and Media

**Official Documentation**: https://docs.wagtail.org/en/stable/advanced_topics/images/renditions.html

### Image Model

Wagtail provides a built-in `Image` model with these key features:
- Automatic rendition generation
- Multiple file format support
- Focal point selection
- Alt text and metadata
- Collections for organization

### Image Renditions

**In Python**:
```python
# Single rendition
rendition = image.get_rendition('fill-300x200')
print(rendition.url)
print(rendition.width)
print(rendition.height)

# Multiple renditions (efficient)
renditions = image.get_renditions('fill-300x200', 'width-600', 'height-400')
thumbnail = renditions['fill-300x200']
mobile = renditions['width-600']
```

**Filter Operations**:
- `fill-{width}x{height}` - Crop to exact dimensions
- `min-{width}x{height}` - Resize to fit within dimensions
- `max-{width}x{height}` - Resize proportionally
- `width-{width}` - Resize to width
- `height-{height}` - Resize to height
- `scale-{percentage}` - Scale by percentage
- `jpegquality-{quality}` - JPEG compression (1-100)
- `webpquality-{quality}` - WebP compression
- `format-{format}` - Convert format (jpeg, png, webp)

**Chaining Filters**:
```python
rendition = image.get_rendition('fill-800x600|jpegquality-60')
```

### Performance Optimization

**Prefetch Renditions**:
```python
from wagtail.images.models import Image

# Prefetch for queryset
images = Image.objects.filter(
    uploaded_by_user=user
).prefetch_renditions('fill-300x200', 'width-600')

for image in images:
    # No additional queries
    thumbnail = image.get_rendition('fill-300x200')
```

**Related Models**:
```python
from django.db.models import Prefetch
from wagtail.images.models import Image

# Prefetch images with renditions
blog_posts = BlogPage.objects.prefetch_related(
    Prefetch(
        'header_image',
        queryset=Image.objects.prefetch_renditions('fill-800x400')
    )
)
```

### Template Usage

**Basic Rendering**:
```django
{% load wagtailimages_tags %}

{% image page.header_image fill-800x400 %}
```

**With Attributes**:
```django
{% image page.header_image fill-800x400 class="featured" alt="Custom alt text" %}
```

**As Variable**:
```django
{% image page.header_image fill-800x400 as img %}
<img src="{{ img.url }}" width="{{ img.width }}" height="{{ img.height }}" alt="{{ img.alt }}">
```

**Responsive Images**:
```django
{% load wagtailimages_tags %}

{% image page.header_image fill-800x400 as desktop %}
{% image page.header_image fill-400x300 as mobile %}

<picture>
    <source media="(min-width: 768px)" srcset="{{ desktop.url }}">
    <img src="{{ mobile.url }}" alt="{{ page.title }}">
</picture>
```

### API Integration

**Image Renditions in API**:
```python
from wagtail.api import APIField
from wagtail.images.api.fields import ImageRenditionField

class BlogPage(Page):
    header_image = models.ForeignKey('wagtailimages.Image', ...)

    api_fields = [
        APIField('header_image'),
        APIField('thumbnail',
                serializer=ImageRenditionField('fill-300x200', source='header_image')),
        APIField('mobile_image',
                serializer=ImageRenditionField('width-600', source='header_image')),
    ]
```

**API Response**:
```json
{
    "header_image": {
        "id": 42,
        "title": "Blog Header",
        "width": 1920,
        "height": 1080
    },
    "thumbnail": {
        "url": "/media/images/blog-header.fill-300x200.jpg",
        "width": 300,
        "height": 200
    }
}
```

---

## Advanced Blog Features

### 1. Tags with django-taggit

**Official Documentation**: https://docs.wagtail.org/en/stable/advanced_topics/tags.html

#### Setup

**Install Dependencies** (already in requirements.txt):
```python
# django-taggit==6.1.0
# django-modelcluster==6.4
```

#### Implementation

**Model Definition**:
```python
from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase, TagBase, ItemBase
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel

# Through model for tag relationship
class BlogPageTag(TaggedItemBase):
    content_object = ParentalKey(
        'blog.BlogPage',
        on_delete=models.CASCADE,
        related_name='tagged_items'
    )

class BlogPage(Page):
    # Add tags field
    tags = ClusterTaggableManager(through=BlogPageTag, blank=True)

    # Add to promote panels
    promote_panels = Page.promote_panels + [
        FieldPanel('tags'),
    ]
```

**Custom Tag Pool** (prevents cross-model contamination):
```python
# Custom tag model
class BlogTag(TagBase):
    free_tagging = False  # Optional: restrict to pre-existing tags

    class Meta:
        verbose_name = "Blog Tag"
        verbose_name_plural = "Blog Tags"

# Through model with custom tag
class TaggedBlog(ItemBase):
    tag = models.ForeignKey(
        BlogTag,
        related_name="tagged_blogs",
        on_delete=models.CASCADE
    )
    content_object = ParentalKey(
        'blog.BlogPage',
        on_delete=models.CASCADE,
        related_name='tagged_items'
    )

class BlogPage(Page):
    tags = ClusterTaggableManager(through='blog.TaggedBlog', blank=True)
```

#### Filtering by Tags

**Index Page with Tag Filtering**:
```python
class BlogIndexPage(Page):
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Get all blog posts
        blog_posts = BlogPage.objects.child_of(self).live()

        # Filter by tag if provided
        tag = request.GET.get('tag')
        if tag:
            blog_posts = blog_posts.filter(tags__name=tag)

        context['blog_posts'] = blog_posts
        context['current_tag'] = tag
        return context
```

**Template**:
```django
{# Tag filter links #}
<div class="tags">
    {% for tag in page.tags.all %}
        <a href="{% pageurl blog_index %}?tag={{ tag|urlencode }}"
           class="tag {% if tag.name == current_tag %}active{% endif %}">
            {{ tag }}
        </a>
    {% endfor %}
</div>

{# Filtered posts #}
{% if current_tag %}
    <h2>Posts tagged with "{{ current_tag }}"</h2>
{% endif %}

{% for post in blog_posts %}
    <article>
        <h3><a href="{% pageurl post %}">{{ post.title }}</a></h3>
        <div class="tags">
            {% for tag in post.tags.all %}
                <span class="tag">{{ tag }}</span>
            {% endfor %}
        </div>
    </article>
{% endfor %}
```

#### Managing Tags as Snippets

**Register tags in admin** (`wagtail_hooks.py`):
```python
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail import hooks
from .models import BlogTag

class BlogTagSnippetViewSet(SnippetViewSet):
    model = BlogTag
    icon = "tag"
    add_to_admin_menu = True
    list_display = ["name", "slug"]
    search_fields = ["name"]
    panels = [
        FieldPanel("name"),
    ]

@hooks.register("register_snippets")
def register_blog_tag_snippet():
    return BlogTagSnippetViewSet()
```

### 2. Categories with InlinePanel

**Official Documentation**: https://docs.wagtail.org/en/stable/topics/pages.html

#### Implementation

**Models**:
```python
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.models import Page, Orderable
from wagtail.snippets.models import register_snippet
from wagtail.admin.panels import FieldPanel, InlinePanel

# Category snippet
@register_snippet
class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    panels = [
        FieldPanel('name'),
        FieldPanel('slug'),
        FieldPanel('description'),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"

# Many-to-many through model
class BlogPageCategory(Orderable):
    page = ParentalKey('blog.BlogPage', on_delete=models.CASCADE, related_name='categories')
    category = models.ForeignKey('blog.BlogCategory', on_delete=models.CASCADE, related_name='blog_pages')

    panels = [
        FieldPanel('category'),
    ]

    class Meta:
        unique_together = ('page', 'category')

class BlogPage(Page):
    # ... other fields ...

    content_panels = Page.content_panels + [
        # ... other panels ...
        InlinePanel('categories', label="Categories", min_num=1, max_num=5),
    ]
```

#### Filtering by Category

**Index Page**:
```python
class BlogIndexPage(Page):
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Get all posts
        blog_posts = BlogPage.objects.child_of(self).live()

        # Filter by category
        category_slug = request.GET.get('category')
        if category_slug:
            blog_posts = blog_posts.filter(
                categories__category__slug=category_slug
            )

        context['blog_posts'] = blog_posts
        context['categories'] = BlogCategory.objects.all()
        context['current_category'] = category_slug
        return context
```

### 3. Routable Pages for Archives

**Official Documentation**: https://docs.wagtail.org/en/stable/reference/contrib/routablepage.html

#### Setup

**Add to INSTALLED_APPS**:
```python
INSTALLED_APPS = [
    'wagtail.contrib.routable_page',
    # ...
]
```

#### Implementation

```python
from wagtail.contrib.routable_page.models import RoutablePageMixin, path, re_path

class BlogIndexPage(RoutablePageMixin, Page):
    # Main index route
    def get_posts(self):
        return BlogPage.objects.child_of(self).live().order_by('-publication_date')

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context['posts'] = self.get_posts()
        return context

    # Archive by year
    @path('year/<int:year>/')
    def posts_by_year(self, request, year):
        posts = self.get_posts().filter(publication_date__year=year)
        return self.render(
            request,
            context_overrides={'posts': posts, 'filter_year': year}
        )

    # Archive by year and month
    @path('year/<int:year>/<int:month>/')
    def posts_by_month(self, request, year, month):
        posts = self.get_posts().filter(
            publication_date__year=year,
            publication_date__month=month
        )
        return self.render(
            request,
            context_overrides={
                'posts': posts,
                'filter_year': year,
                'filter_month': month
            }
        )

    # Tag filter route
    @path('tag/<str:tag>/')
    def posts_by_tag(self, request, tag):
        posts = self.get_posts().filter(tags__name=tag)
        return self.render(
            request,
            context_overrides={'posts': posts, 'filter_tag': tag}
        )

    # Category filter route
    @path('category/<slug:category_slug>/')
    def posts_by_category(self, request, category_slug):
        posts = self.get_posts().filter(
            categories__category__slug=category_slug
        )
        return self.render(
            request,
            context_overrides={'posts': posts, 'filter_category': category_slug}
        )
```

**Template Usage** (`routablepageurl` tag):
```django
{% load wagtailroutablepage_tags %}

{# Archive links #}
<ul>
    <li><a href="{% routablepageurl page 'posts_by_year' 2025 %}">2025 Posts</a></li>
    <li><a href="{% routablepageurl page 'posts_by_month' 2025 10 %}">October 2025</a></li>
    <li><a href="{% routablepageurl page 'posts_by_tag' 'django' %}">Django Posts</a></li>
    <li><a href="{% routablepageurl page 'posts_by_category' 'tutorials' %}">Tutorials</a></li>
</ul>
```

### 4. Pagination

**Implementation in get_context**:
```python
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

class BlogIndexPage(Page):
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Get all posts
        all_posts = BlogPage.objects.child_of(self).live().order_by('-publication_date')

        # Paginate
        paginator = Paginator(all_posts, 10)  # 10 posts per page
        page_number = request.GET.get('page', 1)

        try:
            posts = paginator.page(page_number)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        context['posts'] = posts
        return context
```

**Template**:
```django
{% for post in posts %}
    <article>
        <h2><a href="{% pageurl post %}">{{ post.title }}</a></h2>
    </article>
{% endfor %}

{# Pagination controls #}
<nav class="pagination">
    {% if posts.has_previous %}
        <a href="?page={{ posts.previous_page_number }}">Previous</a>
    {% endif %}

    <span class="current">
        Page {{ posts.number }} of {{ posts.paginator.num_pages }}
    </span>

    {% if posts.has_next %}
        <a href="?page={{ posts.next_page_number }}">Next</a>
    {% endif %}
</nav>
```

### 5. Search Integration

**Model Configuration**:
```python
from wagtail.search import index

class BlogPage(Page):
    search_fields = Page.search_fields + [
        index.SearchField('intro'),
        index.SearchField('body'),
        index.FilterField('publication_date'),
        index.FilterField('author_name'),
        index.AutocompleteField('title'),
    ]
```

**Search View**:
```python
class BlogIndexPage(Page):
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Get query
        search_query = request.GET.get('q', '')

        # Base queryset
        posts = BlogPage.objects.child_of(self).live()

        # Apply search
        if search_query:
            posts = posts.search(search_query)
        else:
            posts = posts.order_by('-publication_date')

        context['posts'] = posts
        context['search_query'] = search_query
        return context
```

**Search Template**:
```django
<form action="{% pageurl page %}" method="get">
    <input type="text" name="q" value="{{ search_query }}" placeholder="Search posts...">
    <button type="submit">Search</button>
</form>

{% if search_query %}
    <p>Results for "{{ search_query }}"</p>
{% endif %}

{% for post in posts %}
    <article>
        <h2><a href="{% pageurl post %}">{{ post.title }}</a></h2>
    </article>
{% empty %}
    <p>No posts found.</p>
{% endfor %}
```

---

## Testing

**Official Documentation**: https://docs.wagtail.org/en/stable/advanced_topics/testing.html

### WagtailPageTestCase

Wagtail extends Django's `TestCase` with specialized assertions:

```python
from django.test import TestCase
from wagtail.test.utils import WagtailPageTestCase
from wagtail.models import Page, Site
from .models import BlogPage, BlogIndexPage

class BlogPageTests(WagtailPageTestCase):
    def setUp(self):
        # Get root page
        self.root = Page.get_first_root_node()

        # Create site
        self.site = Site.objects.create(
            hostname='testserver',
            root_page=self.root,
            is_default_site=True
        )

        # Create blog index
        self.blog_index = BlogIndexPage(
            title="Blog",
            slug="blog"
        )
        self.root.add_child(instance=self.blog_index)

    def test_can_create_blog_page(self):
        # Test page can be created under correct parent
        self.assertCanCreateAt(BlogIndexPage, BlogPage)

    def test_cannot_create_blog_page_under_root(self):
        # Test page cannot be created under wrong parent
        self.assertCanNotCreateAt(Page, BlogPage)

    def test_blog_page_parent_types(self):
        # Test allowed parent types
        self.assertAllowedParentPageTypes(
            BlogPage,
            {BlogIndexPage}
        )

    def test_blog_index_subpage_types(self):
        # Test allowed child types
        self.assertAllowedSubpageTypes(
            BlogIndexPage,
            {BlogPage}
        )
```

### Testing StreamField Content

```python
from wagtail.test.utils.form_data import nested_form_data, streamfield, rich_text
from wagtail.rich_text import RichText

class BlogPageTests(WagtailPageTestCase):
    def test_create_blog_page_with_streamfield(self):
        # Create page with StreamField content
        blog_page = BlogPage(
            title="Test Post",
            slug="test-post",
            publication_date=date.today()
        )

        # Set StreamField content
        blog_page.body = [
            ('heading', 'Introduction'),
            ('paragraph', RichText('<p>This is a test post.</p>')),
            ('image', self.test_image),
        ]

        self.blog_index.add_child(instance=blog_page)
        blog_page.save_revision().publish()

        # Verify content
        self.assertEqual(len(blog_page.body), 3)
        self.assertEqual(blog_page.body[0].block_type, 'heading')
        self.assertEqual(blog_page.body[0].value, 'Introduction')
```

### Testing with Form Data

```python
def test_create_blog_page_via_form(self):
    post_data = nested_form_data({
        'title': 'Test Post',
        'slug': 'test-post',
        'publication_date': '2025-10-23',
        'body': streamfield([
            ('heading', 'Test Heading'),
            ('paragraph', rich_text('<p>Test content</p>')),
        ])
    })

    response = self.client.post(
        reverse('wagtailadmin_pages:add', args=('blog', 'blogpage', self.blog_index.id)),
        post_data
    )

    self.assertEqual(response.status_code, 302)
```

### Testing API Endpoints

```python
from rest_framework.test import APIClient
from django.urls import reverse
import json

class BlogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Set up pages...

    def test_blog_page_listing(self):
        response = self.client.get(reverse('wagtailapi_v2:pages:listing'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        content = json.loads(response.content)
        self.assertIn('meta', content)
        self.assertIn('items', content)

    def test_blog_page_detail(self):
        response = self.client.get(
            reverse('wagtailapi_v2:pages:detail', args=(self.blog_page.id,))
        )

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        self.assertEqual(content['title'], self.blog_page.title)
        self.assertIn('body', content)

    def test_filter_by_type(self):
        response = self.client.get(
            reverse('wagtailapi_v2:pages:listing'),
            {'type': 'blog.BlogPage'}
        )

        content = json.loads(response.content)
        for item in content['items']:
            self.assertEqual(item['meta']['type'], 'blog.BlogPage')
```

### Test Utilities

**WagtailPageTestCase Assertions**:
- `assertPageIsRoutable(page)` - Page can be routed (no 404)
- `assertPageIsRenderable(page)` - Page renders without errors
- `assertPageIsEditable(page)` - Edit view works
- `assertPageIsPreviewable(page)` - Preview works
- `assertCanCreateAt(ParentModel, ChildModel)` - Can create child
- `assertCanNotCreateAt(ParentModel, ChildModel)` - Cannot create child
- `assertCanCreate(parent, child_model, data)` - Can create with data
- `assertAllowedParentPageTypes(model, types)` - Parent types match
- `assertAllowedSubpageTypes(model, types)` - Subpage types match

**Form Data Helpers**:
- `nested_form_data(data_dict)` - Convert nested dict to flat form data
- `streamfield(block_list)` - Convert block tuples to StreamField form data
- `rich_text(html)` - Convert HTML to RichText form data
- `inline_formset(formset_data)` - Convert formset data

---

## SEO and Metadata

### 1. Built-in SEO Fields

Wagtail provides built-in SEO fields in the promote panel:

```python
class BlogPage(Page):
    # Built-in fields available:
    # - seo_title (overrides page title for <title> tag)
    # - search_description (meta description)
    # - show_in_menus (boolean for navigation)

    promote_panels = Page.promote_panels + [
        # Add custom SEO fields here
    ]
```

### 2. Sitemap Generation

**Official Documentation**: https://docs.wagtail.org/en/stable/reference/contrib/sitemaps.html

**Setup**:
```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.sitemaps',
    # ...
]

# urls.py
from wagtail.contrib.sitemaps.views import sitemap

urlpatterns = [
    path('sitemap.xml', sitemap),
    # ... other patterns (must be before wagtail_urls)
    path('', include(wagtail_urls)),
]
```

**Customization**:
```python
class BlogPage(Page):
    def get_sitemap_urls(self, request=None):
        return [
            {
                'location': self.get_full_url(request),
                'lastmod': self.latest_revision_created_at,
                'changefreq': 'monthly',
                'priority': 0.8,
            }
        ]
```

**Exclude from Sitemap**:
```python
def get_sitemap_urls(self, request=None):
    # Return empty list to exclude
    return []
```

### 3. Third-Party SEO Packages

**wagtail-metadata** (recommended):
```bash
pip install wagtail-metadata
```

**Usage**:
```python
from wagtailmetadata.models import MetadataPageMixin

class BlogPage(MetadataPageMixin, Page):
    # Adds fields:
    # - search_image (for social sharing)
    # - search_description (enhanced)
    pass
```

**Template**:
```django
{% load wagtailmetadata_tags %}
{% meta_tags %}  {# Outputs all meta tags #}
```

**wagtail-seo** (by CodeRed):
```bash
pip install wagtail-seo
```

Features:
- Meta tags
- Open Graph tags
- Twitter cards
- Google rich results (structured data)
- Article-specific metadata

---

## References

### Official Wagtail Documentation

**Core Documentation**:
- **Main Site**: https://docs.wagtail.org/
- **Version 7.0.3 Docs**: https://docs.wagtail.org/en/v7.0.3/
- **Latest Stable (7.1.1)**: https://docs.wagtail.org/en/stable/

**Key Topics**:
- **Page Models**: https://docs.wagtail.org/en/stable/topics/pages.html
- **StreamField Overview**: https://docs.wagtail.org/en/v7.0.3/topics/streamfield.html
- **StreamField Block Reference**: https://docs.wagtail.org/en/stable/reference/streamfield/blocks.html
- **API Configuration**: https://docs.wagtail.org/en/stable/advanced_topics/api/v2/configuration.html
- **API Usage**: https://docs.wagtail.org/en/stable/advanced_topics/api/v2/usage.html
- **Image Renditions**: https://docs.wagtail.org/en/stable/advanced_topics/images/renditions.html
- **Tagging**: https://docs.wagtail.org/en/stable/advanced_topics/tags.html
- **RoutablePageMixin**: https://docs.wagtail.org/en/stable/reference/contrib/routablepage.html
- **Testing**: https://docs.wagtail.org/en/stable/advanced_topics/testing.html
- **Sitemaps**: https://docs.wagtail.org/en/stable/reference/contrib/sitemaps.html
- **Search Indexing**: https://docs.wagtail.org/en/stable/topics/search/indexing.html
- **Panels**: https://docs.wagtail.org/en/stable/reference/panels.html

### Community Resources

**Tutorials**:
- **LearnWagtail.com**:
  - Adding Tags to Pages
  - Pagination Guide
  - Routable Pages for Categories and Years
  - RichText Content Areas
  - Sitemap Customization

- **SaasHammer**:
  - Add Blog Models to Wagtail
  - Using StreamField in Wagtail

- **AccordBox**:
  - Wagtail SEO Guide
  - Pagination Components

**SEO Packages**:
- **wagtail-metadata**: https://pypi.org/project/wagtail-metadata/
- **wagtail-seo**: https://docs.coderedcorp.com/wagtail-seo/
- **wagtail-metadata-mixin**: https://github.com/bashu/wagtail-metadata-mixin

### Source Code Locations

**Installed Wagtail** (for reference):
```
/Users/williamtower/projects/plant_id_community/backend/venv/lib/python3.13/site-packages/wagtail/

Key modules:
- blocks/            # StreamField block types
- api/v2/           # API implementation
- images/           # Image handling
- contrib/
  - routable_page/  # RoutablePageMixin
  - sitemaps/       # Sitemap generation
  - taggit/         # Tag integration
- test/
  - utils/          # Test helpers
  - testapp/        # Example models
```

### Django Dependencies

**Related Packages** (already installed):
- **django-taggit** (6.1.0): Tag management
- **django-modelcluster** (6.4): In-memory models for previews
- **django-treebeard** (4.7.1): Tree structure (page hierarchy)
- **Pillow** (11.3.0): Image processing

### Testing Examples

**Official Test Suite**:
```
/Users/williamtower/projects/plant_id_community/backend/venv/lib/python3.13/site-packages/wagtail/api/v2/tests/

- test_pages.py      # Page API testing patterns
- test_images.py     # Image API testing
- test_documents.py  # Document API testing
```

---

## Next Steps

### Implementation Roadmap

**Phase 1: Basic Blog Structure**
1. Create `BlogIndexPage` and `BlogPage` models
2. Implement StreamField with common block types
3. Set up content panels and promote panels
4. Create basic templates

**Phase 2: Content Organization**
5. Add tagging with ClusterTaggableManager
6. Implement categories with InlinePanel
7. Add search functionality
8. Set up pagination

**Phase 3: Advanced Features**
9. Implement RoutablePageMixin for archives
10. Add API endpoints with custom fields
11. Configure image renditions
12. Set up RSS feeds (Django syndication)

**Phase 4: SEO and Performance**
13. Configure sitemaps
14. Add SEO metadata (wagtail-metadata)
15. Implement caching strategy
16. Optimize queries with select_related/prefetch_related

**Phase 5: Testing and Deployment**
17. Write comprehensive test suite
18. API endpoint testing
19. Performance testing
20. Production deployment

### Key Considerations

**Performance**:
- Use `prefetch_renditions()` for image-heavy pages
- Implement query optimization with `select_related()`
- Enable template fragment caching
- Consider Django Debug Toolbar for development

**Security**:
- Restrict StreamField block types in production
- Validate user-generated content
- Configure CORS for API endpoints
- Use authentication for sensitive endpoints

**Scalability**:
- Plan for content growth (pagination, lazy loading)
- Consider CDN for images/static files
- Implement caching strategy (Redis/Memcached)
- Monitor API rate limits

---

**Document End**
