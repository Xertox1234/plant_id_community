# Wagtail Blog Quick Reference Guide

**Version**: Wagtail 7.0.3
**Date**: October 23, 2025

---

## Quick Setup Checklist

```python
# 1. Install (already in requirements.txt)
wagtail==7.0.3
django-taggit==6.1.0
django-modelcluster==6.4

# 2. Add to INSTALLED_APPS
INSTALLED_APPS = [
    'wagtail.contrib.routable_page',  # For archives
    'django.contrib.sitemaps',         # For sitemap
    'rest_framework',                  # For API
    'wagtail.api.v2',                  # For API
]

# 3. Create blog app
python manage.py startapp blog
```

---

## Essential Code Patterns

### Basic Blog Page Model

```python
from django.db import models
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail.admin.panels import FieldPanel
from wagtail import blocks
from wagtail.images.blocks import ImageBlock

class BlogPage(Page):
    publication_date = models.DateField()
    author = models.CharField(max_length=100)
    intro = models.TextField(blank=True)

    body = StreamField([
        ('heading', blocks.CharBlock(form_classname="title")),
        ('paragraph', blocks.RichTextBlock()),
        ('image', ImageBlock()),
    ], use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel('publication_date'),
        FieldPanel('author'),
        FieldPanel('intro'),
        FieldPanel('body'),
    ]

    parent_page_types = ['BlogIndexPage']
    subpage_types = []

    class Meta:
        verbose_name = "Blog Post"
```

### Blog Index with Pagination

```python
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from wagtail.models import Page

class BlogIndexPage(Page):
    subpage_types = ['BlogPage']

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Get posts
        posts = BlogPage.objects.child_of(self).live().order_by('-publication_date')

        # Paginate
        paginator = Paginator(posts, 10)
        page_number = request.GET.get('page', 1)

        try:
            posts = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            posts = paginator.page(1)

        context['posts'] = posts
        return context
```

### Tags Implementation

```python
from modelcluster.fields import ParentalKey
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase

class BlogPageTag(TaggedItemBase):
    content_object = ParentalKey('blog.BlogPage', related_name='tagged_items')

class BlogPage(Page):
    tags = ClusterTaggableManager(through=BlogPageTag, blank=True)

    promote_panels = Page.promote_panels + [
        FieldPanel('tags'),
    ]

# Filter by tag
def get_context(self, request):
    posts = BlogPage.objects.live()
    tag = request.GET.get('tag')
    if tag:
        posts = posts.filter(tags__name=tag)
```

### Categories with InlinePanel

```python
from wagtail.models import Orderable
from wagtail.snippets.models import register_snippet
from wagtail.admin.panels import InlinePanel

@register_snippet
class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

class BlogPageCategory(Orderable):
    page = ParentalKey('BlogPage', related_name='categories')
    category = models.ForeignKey('BlogCategory', on_delete=models.CASCADE)

class BlogPage(Page):
    content_panels = Page.content_panels + [
        InlinePanel('categories', label="Categories", max_num=3),
    ]
```

### API Configuration

```python
# api.py
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet

api_router = WagtailAPIRouter('wagtailapi')
api_router.register_endpoint('pages', PagesAPIViewSet)
api_router.register_endpoint('images', ImagesAPIViewSet)

# urls.py
urlpatterns = [
    path('api/v2/', api_router.urls),
]

# models.py
from wagtail.api import APIField

class BlogPage(Page):
    api_fields = [
        APIField('publication_date'),
        APIField('author'),
        APIField('intro'),
        APIField('body'),
    ]
```

### Routable Pages for Archives

```python
from wagtail.contrib.routable_page.models import RoutablePageMixin, path

class BlogIndexPage(RoutablePageMixin, Page):
    @path('year/<int:year>/')
    def posts_by_year(self, request, year):
        posts = BlogPage.objects.live().filter(publication_date__year=year)
        return self.render(request, context_overrides={'posts': posts})

    @path('tag/<str:tag>/')
    def posts_by_tag(self, request, tag):
        posts = BlogPage.objects.live().filter(tags__name=tag)
        return self.render(request, context_overrides={'posts': posts})

# Template usage
{% load wagtailroutablepage_tags %}
<a href="{% routablepageurl page 'posts_by_year' 2025 %}">2025 Posts</a>
```

---

## Common StreamField Blocks

```python
body = StreamField([
    # Text
    ('heading', blocks.CharBlock(form_classname="title")),
    ('paragraph', blocks.RichTextBlock(features=['bold', 'italic', 'link'])),
    ('quote', blocks.BlockQuoteBlock()),

    # Media
    ('image', ImageBlock()),
    ('embed', blocks.EmbedBlock()),

    # Structured
    ('code', blocks.TextBlock(help_text="Code snippet")),
    ('list', blocks.ListBlock(blocks.CharBlock(label="Item"))),

    # Custom
    ('callout', blocks.StructBlock([
        ('title', blocks.CharBlock()),
        ('text', blocks.TextBlock()),
        ('style', blocks.ChoiceBlock(choices=[
            ('info', 'Info'),
            ('warning', 'Warning'),
        ])),
    ])),
], use_json_field=True)
```

---

## Template Patterns

### Blog Index Template

```django
{% extends "base.html" %}
{% load wagtailcore_tags %}

{% block content %}
    <h1>{{ page.title }}</h1>

    {% for post in posts %}
        <article>
            <h2><a href="{% pageurl post %}">{{ post.title }}</a></h2>
            <p class="meta">{{ post.publication_date|date:"F d, Y" }} by {{ post.author }}</p>
            <p>{{ post.intro }}</p>

            <div class="tags">
                {% for tag in post.tags.all %}
                    <a href="?tag={{ tag|urlencode }}">{{ tag }}</a>
                {% endfor %}
            </div>
        </article>
    {% endfor %}

    {# Pagination #}
    {% if posts.has_previous or posts.has_next %}
        <nav class="pagination">
            {% if posts.has_previous %}
                <a href="?page={{ posts.previous_page_number }}">Previous</a>
            {% endif %}

            <span>Page {{ posts.number }} of {{ posts.paginator.num_pages }}</span>

            {% if posts.has_next %}
                <a href="?page={{ posts.next_page_number }}">Next</a>
            {% endif %}
        </nav>
    {% endif %}
{% endblock %}
```

### Blog Post Template

```django
{% extends "base.html" %}
{% load wagtailcore_tags wagtailimages_tags %}

{% block content %}
    <article>
        <h1>{{ page.title }}</h1>
        <p class="meta">
            {{ page.publication_date|date:"F d, Y" }} by {{ page.author }}
        </p>

        {% if page.intro %}
            <div class="intro">{{ page.intro }}</div>
        {% endif %}

        <div class="content">
            {% include_block page.body %}
        </div>

        <div class="tags">
            {% for tag in page.tags.all %}
                <a href="{% pageurl page.get_parent %}?tag={{ tag|urlencode }}">
                    {{ tag }}
                </a>
            {% endfor %}
        </div>
    </article>
{% endblock %}
```

### Custom StreamField Block Template

```django
{# templates/blog/blocks/callout.html #}
<div class="callout callout-{{ value.style }}">
    <h3>{{ value.title }}</h3>
    <p>{{ value.text }}</p>
</div>

{# Use in StreamField #}
('callout', blocks.StructBlock([
    # ... fields ...
], template='blog/blocks/callout.html'))
```

---

## Testing Patterns

### Page Tests

```python
from wagtail.test.utils import WagtailPageTestCase
from .models import BlogPage, BlogIndexPage

class BlogTests(WagtailPageTestCase):
    def test_can_create_blog_page(self):
        self.assertCanCreateAt(BlogIndexPage, BlogPage)

    def test_blog_page_has_correct_fields(self):
        blog_page = BlogPage(title="Test", publication_date=date.today())
        self.assertTrue(hasattr(blog_page, 'body'))
        self.assertTrue(hasattr(blog_page, 'tags'))
```

### API Tests

```python
from rest_framework.test import APIClient
import json

class BlogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_blog_listing(self):
        response = self.client.get('/api/v2/pages/?type=blog.BlogPage')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn('items', data)
```

---

## Common Queries

```python
# Get all blog posts
BlogPage.objects.live().public().order_by('-publication_date')

# Filter by tag
BlogPage.objects.filter(tags__name='django').live()

# Filter by category
BlogPage.objects.filter(categories__category__slug='tutorials').live()

# Filter by date range
from datetime import datetime, timedelta
last_month = datetime.now() - timedelta(days=30)
BlogPage.objects.filter(publication_date__gte=last_month).live()

# Search
BlogPage.objects.search('django wagtail').live()

# With prefetch for performance
BlogPage.objects.live().prefetch_related('tags', 'categories')
```

---

## SEO Checklist

```python
# 1. Add search fields
search_fields = Page.search_fields + [
    index.SearchField('intro'),
    index.SearchField('body'),
]

# 2. Configure sitemap
# settings.py
INSTALLED_APPS = ['django.contrib.sitemaps']

# urls.py
from wagtail.contrib.sitemaps.views import sitemap
urlpatterns = [path('sitemap.xml', sitemap)]

# 3. Custom sitemap entries
def get_sitemap_urls(self, request=None):
    return [{
        'location': self.get_full_url(request),
        'lastmod': self.latest_revision_created_at,
        'changefreq': 'weekly',
        'priority': 0.8,
    }]

# 4. Use built-in SEO fields
# - seo_title (in promote panel)
# - search_description (in promote panel)
```

---

## Image Renditions Quick Reference

```python
# In Python
thumbnail = image.get_rendition('fill-300x200')
print(thumbnail.url, thumbnail.width, thumbnail.height)

# Multiple renditions (efficient)
renditions = image.get_renditions('fill-300x200', 'width-600')

# In templates
{% load wagtailimages_tags %}
{% image page.photo fill-800x600 %}
{% image page.photo fill-800x600 class="featured" %}

# Responsive images
{% image page.photo fill-800x600 as desktop %}
{% image page.photo fill-400x300 as mobile %}
<picture>
    <source media="(min-width: 768px)" srcset="{{ desktop.url }}">
    <img src="{{ mobile.url }}" alt="{{ page.title }}">
</picture>

# Common filters
fill-{w}x{h}      # Crop to exact size
max-{w}x{h}       # Fit within size
width-{w}         # Resize to width
jpegquality-{q}   # JPEG compression (1-100)
```

---

## Performance Tips

```python
# 1. Prefetch related data
posts = BlogPage.objects.live().prefetch_related('tags', 'categories__category')

# 2. Select related for foreign keys
posts = BlogPage.objects.live().select_related('owner')

# 3. Prefetch image renditions
from wagtail.images.models import Image
images = Image.objects.prefetch_renditions('fill-300x200', 'width-600')

# 4. Use pagination
from django.core.paginator import Paginator
paginator = Paginator(posts, 10)

# 5. Cache expensive queries
from django.core.cache import cache
posts = cache.get_or_set('recent_posts', lambda: BlogPage.objects.live()[:10], 300)
```

---

## Common Issues & Solutions

**StreamField not saving**:
```python
# Always use use_json_field=True in Wagtail 4+
body = StreamField([...], use_json_field=True)
```

**Tags not showing in admin**:
```python
# Add to promote_panels
promote_panels = Page.promote_panels + [FieldPanel('tags')]
```

**API fields not appearing**:
```python
# Use APIField wrapper
api_fields = [APIField('publication_date'), APIField('body')]
```

**Images not rendering**:
```python
# Import correct tag library
{% load wagtailimages_tags %}
{% image page.photo fill-800x600 %}
```

**Pagination losing filters**:
```python
# Preserve query params
<a href="?page={{ posts.next_page_number }}&tag={{ current_tag }}">Next</a>
```

---

## Useful Commands

```bash
# Create superuser
python manage.py createsuperuser

# Make migrations
python manage.py makemigrations

# Run migrations
python manage.py migrate

# Update search index
python manage.py update_index

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test blog

# Run development server
python manage.py runserver
```

---

## Documentation Links

- **Wagtail Docs**: https://docs.wagtail.org/en/stable/
- **StreamField**: https://docs.wagtail.org/en/stable/topics/streamfield.html
- **API**: https://docs.wagtail.org/en/stable/advanced_topics/api/
- **Testing**: https://docs.wagtail.org/en/stable/advanced_topics/testing.html

---

**Quick Reference End**
