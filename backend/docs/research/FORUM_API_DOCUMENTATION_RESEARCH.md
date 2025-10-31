# Forum Feature Implementation - Comprehensive Documentation Research

**Date**: October 28, 2025
**Research Focus**: Django REST Framework forum patterns for headless API architecture
**Current Stack**: Django 5.2.7 + DRF 3.16.1 + PostgreSQL + Redis
**Target Clients**: React web (port 5174) + Flutter mobile

---

## Executive Summary

This research compiles comprehensive documentation for implementing a forum feature using Django REST Framework in a headless API architecture. The project already has a reference implementation in `/existing_implementation/backend/apps/forum_integration/` using Django Machina, which provides valuable patterns for adaptation.

**Key Insights from Existing Implementation**:
- Django Machina 1.3.1 provides battle-tested forum models (Forum, Topic, Post)
- Rich content support via RichPost model with Draft.js JSON format
- React integration with PlainDraftEditor for mobile-friendly WYSIWYG
- Trust level system (0-4) for progressive permissions
- Post reactions (like, love, helpful, thanks) for engagement
- Image uploads with automatic resizing (max 6 per post, ImageKit integration)
- AI assistance integration for content generation

---

## 1. Django REST Framework Core Documentation

### Version-Specific Resources

**Django 5.2 Documentation**:
- Official Docs: https://docs.djangoproject.com/en/5.2/
- Release Notes: https://docs.djangoproject.com/en/5.2/releases/5.2/
- Model Reference: https://docs.djangoproject.com/en/5.2/ref/models/
- ORM Optimization: https://docs.djangoproject.com/en/5.2/topics/db/optimization/

**Django REST Framework 3.16.1**:
- Official Docs: https://www.django-rest-framework.org/
- Viewsets & Routers: https://www.django-rest-framework.org/api-guide/viewsets/
- Serializers: https://www.django-rest-framework.org/api-guide/serializers/
- Pagination: https://www.django-rest-framework.org/api-guide/pagination/
- Filtering: https://www.django-rest-framework.org/api-guide/filtering/
- Throttling: https://www.django-rest-framework.org/api-guide/throttling/
- Versioning: https://www.django-rest-framework.org/api-guide/versioning/

**Critical Patterns for Forum API**:

1. **Nested Routers** for hierarchical resources:
```python
# Pattern from existing implementation
/api/v1/forums/                    # List forums
/api/v1/forums/{id}/topics/        # Topics in forum
/api/v1/forums/{id}/topics/{id}/posts/  # Posts in topic
```

Documentation: https://www.django-rest-framework.org/api-guide/routers/#nested-routers
Third-party: `drf-nested-routers` (https://github.com/alanjds/drf-nested-routers)

2. **Recursive Serializers** for threaded content:
```python
class RecursiveSerializer(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data

class PostSerializer(serializers.ModelSerializer):
    replies = RecursiveSerializer(many=True, read_only=True)
```

Documentation: https://www.django-rest-framework.org/api-guide/serializers/#dealing-with-nested-objects

3. **Custom Pagination** for infinite scroll:
```python
class InfiniteScrollPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
```

Documentation: https://www.django-rest-framework.org/api-guide/pagination/#custom-pagination-styles

4. **Throttling for User-Generated Content**:
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10/hour',
        'user': '100/hour',
        'post_creation': '30/day',
        'topic_creation': '10/day'
    }
}
```

Documentation: https://www.django-rest-framework.org/api-guide/throttling/#custom-throttles

---

## 2. Django ORM Patterns for Hierarchical Data

### Tree Structures and Recursive Queries

**Options for Forum Hierarchies**:

1. **django-mptt** (Most Popular - Currently in requirements.txt):
   - GitHub: https://github.com/django-mptt/django-mptt
   - Documentation: https://django-mptt.readthedocs.io/
   - Version: 0.18.0 (in your requirements.txt)
   - Use Case: Categories, nested forums, threaded comments
   - Performance: O(1) reads, O(n) writes
   - Pattern:
```python
from mptt.models import MPTTModel, TreeForeignKey

class ForumCategory(MPTTModel):
    name = models.CharField(max_length=100)
    parent = TreeForeignKey('self', on_delete=models.CASCADE,
                           null=True, blank=True)

    class MPTTMeta:
        order_insertion_by = ['name']

# Query all descendants
category.get_descendants(include_self=True)
# Query all ancestors
category.get_ancestors(include_self=True)
```

2. **django-treebeard** (Currently in requirements.txt):
   - GitHub: https://github.com/django-treebeard/django-treebeard
   - Documentation: https://django-treebeard.readthedocs.io/
   - Version: 4.7.1 (in your requirements.txt)
   - Use Case: Wagtail pages (already used in your project)
   - Algorithms: Adjacency List, Nested Sets, Materialized Path
   - Better performance than MPTT for large datasets
   - Pattern:
```python
from treebeard.mp_tree import MP_Node

class Category(MP_Node):
    name = models.CharField(max_length=30)

    node_order_by = ['name']

# Bulk operations
Category.load_bulk(bulk_data)
# Move operations
category.move(target, pos='sorted-child')
```

3. **PostgreSQL Recursive CTEs** (Native - Recommended for Performance):
   - Documentation: https://docs.djangoproject.com/en/5.2/ref/models/expressions/#django.db.models.expressions.RawSQL
   - Use Case: Deep comment threads, forum breadcrumbs
   - Pattern:
```python
from django.db.models import Q, Prefetch

# Recursive CTE for all replies
Post.objects.raw('''
    WITH RECURSIVE post_tree AS (
        SELECT id, parent_id, content, 0 AS depth
        FROM forum_post WHERE id = %s
        UNION ALL
        SELECT p.id, p.parent_id, p.content, pt.depth + 1
        FROM forum_post p
        INNER JOIN post_tree pt ON p.parent_id = pt.id
    )
    SELECT * FROM post_tree ORDER BY depth, created_at
''', [root_post_id])
```

**Recommendation**: Use django-mptt for forum categories (shallow trees) and PostgreSQL CTEs for deep comment threads (better performance at scale).

### Query Optimization Patterns

**select_related and prefetch_related**:

From your existing blog implementation (`apps/blog/api/viewsets.py`):
```python
def get_queryset(self):
    action = getattr(self, 'action', None)

    if action == 'list':
        # Limited prefetch for list views
        queryset = queryset.select_related('author', 'series')
        queryset = queryset.prefetch_related('categories', 'tags')
    elif action == 'retrieve':
        # Full prefetch for detail views
        queryset = queryset.select_related('author', 'series')
        queryset = queryset.prefetch_related(
            'categories', 'tags', 'related_posts',
            Prefetch('images', queryset=Image.objects.all())
        )
```

**Forum-Specific Optimization**:
```python
# Topic list with poster and last post info
Topic.objects.filter(forum_id=forum_id).select_related(
    'poster',           # Topic author
    'forum',            # Forum category
    'last_post',        # Last activity
    'last_post__poster' # Last poster name
).prefetch_related(
    Prefetch('posts', queryset=Post.objects.filter(approved=True))
)
```

Documentation: https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-related

### Aggregation for Vote Counts and Reply Counts

```python
from django.db.models import Count, Sum, Q, F, Prefetch

# Topic list with aggregated counts
topics = Topic.objects.annotate(
    reply_count=Count('posts') - 1,  # Exclude first post
    like_count=Count('posts__reactions',
                    filter=Q(posts__reactions__type='like')),
    view_count=F('views_count')  # Use existing field
).order_by('-last_post_on')

# User reputation aggregation
user_stats = User.objects.annotate(
    total_posts=Count('posts', filter=Q(posts__approved=True)),
    total_topics=Count('topics', filter=Q(topics__approved=True)),
    helpful_count=Count('posts__reactions',
                       filter=Q(posts__reactions__type='helpful'))
)
```

Documentation: https://docs.djangoproject.com/en/5.2/topics/db/aggregation/

### Full-Text Search with PostgreSQL

**Using GIN Indexes** (Already implemented in your project):

From your migration: `backend/apps/plant_identification/migrations/0012_add_performance_indexes.py`

```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.indexes import GinIndex

class Post(models.Model):
    content = models.TextField()
    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'], name='post_search_idx'),
            # Trigram index for fuzzy search
            GinIndex(
                fields=['content'],
                name='post_content_trgm_idx',
                opclasses=['gin_trgm_ops']
            )
        ]

# Full-text search query
search_query = SearchQuery('plant disease')
search_vector = SearchVector('content', 'title', weight='A') + \
                SearchVector('tags__name', weight='B')

posts = Post.objects.annotate(
    rank=SearchRank(search_vector, search_query)
).filter(
    rank__gte=0.3
).order_by('-rank')
```

Documentation:
- https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/
- https://www.postgresql.org/docs/current/pgtrgm.html

**Trigram Similarity** (pg_trgm extension):
```python
from django.contrib.postgres.search import TrigramSimilarity

# Fuzzy search for typos
posts = Post.objects.annotate(
    similarity=TrigramSimilarity('title', 'plant disese')  # typo
).filter(similarity__gt=0.3).order_by('-similarity')
```

---

## 3. Django Signals & Caching Patterns

### Signal-Based Cache Invalidation

**Pattern from Your Blog Implementation** (`apps/blog/signals.py`):

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from wagtail.signals import page_published, page_unpublished

@receiver(page_published)
def invalidate_blog_cache_on_publish(sender, instance, **kwargs):
    """Invalidate blog cache when page is published."""
    if not isinstance(instance, BlogPostPage):
        return

    cache_service = BlogCacheService()
    cache_service.invalidate_post_cache(instance.slug)
    cache_service.invalidate_list_cache()

@receiver(post_delete, sender=BlogPostPage)
def invalidate_blog_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when blog post is deleted."""
    cache_service = BlogCacheService()
    cache_service.invalidate_post_cache(instance.slug)
    cache_service.invalidate_list_cache()
```

**Forum-Specific Signals**:
```python
from django.db.models.signals import post_save, pre_delete
from machina.apps.forum_conversation.models import Topic, Post

@receiver(post_save, sender=Post)
def invalidate_topic_cache(sender, instance, created, **kwargs):
    """Invalidate topic cache when new post is created."""
    if created:
        cache.delete(f'topic:{instance.topic_id}:posts')
        cache.delete(f'topic:{instance.topic_id}:count')
        # Update last activity
        cache.set(f'topic:{instance.topic_id}:last_activity',
                 timezone.now(), timeout=3600)

@receiver(pre_delete, sender=Topic)
def cleanup_topic_cache(sender, instance, **kwargs):
    """Clean up all topic-related cache entries."""
    cache.delete_many([
        f'topic:{instance.id}:posts',
        f'topic:{instance.id}:count',
        f'forum:{instance.forum_id}:topics'
    ])
```

Documentation: https://docs.djangoproject.com/en/5.2/topics/signals/

### Redis Caching Strategy

**Pattern from Your Plant ID Service** (`apps/plant_identification/services/plant_id_service.py`):

```python
from django.core.cache import cache
from django.conf import settings

class ForumCacheService:
    """Centralized cache management for forum."""

    # Cache timeouts
    TOPIC_LIST_TIMEOUT = 300  # 5 minutes
    TOPIC_DETAIL_TIMEOUT = 3600  # 1 hour
    POST_LIST_TIMEOUT = 600  # 10 minutes

    def get_topic_list(self, forum_id, page=1):
        """Get cached topic list or fetch from DB."""
        cache_key = f'forum:{forum_id}:topics:page:{page}'
        topics = cache.get(cache_key)

        if topics is None:
            topics = self._fetch_topics(forum_id, page)
            cache.set(cache_key, topics, self.TOPIC_LIST_TIMEOUT)

        return topics

    def invalidate_forum_cache(self, forum_id):
        """Invalidate all cache entries for a forum."""
        # Pattern matching with Redis SCAN
        pattern = f'forum:{forum_id}:*'
        cursor = 0
        while True:
            cursor, keys = cache.client.scan(cursor, match=pattern)
            if keys:
                cache.delete_many(keys)
            if cursor == 0:
                break
```

**Distributed Locks** (Your existing pattern from `combined_identification_service.py`):

```python
from redis_lock import Lock
from django.core.cache import cache

def create_post_with_lock(topic_id, post_data):
    """Prevent duplicate posts with distributed lock."""
    lock_id = f'post_creation:{topic_id}:{user_id}'

    with Lock(cache.client, lock_id, expire=30, auto_renewal=True):
        # Check if post was already created
        cache_key = f'recent_post:{topic_id}:{user_id}'
        if cache.get(cache_key):
            raise ValidationError("Post already created")

        # Create post
        post = Post.objects.create(**post_data)

        # Mark as created for 60 seconds
        cache.set(cache_key, post.id, timeout=60)

        return post
```

Documentation:
- Django Cache: https://docs.djangoproject.com/en/5.2/topics/cache/
- python-redis-lock: https://github.com/ionelmc/python-redis-lock

### Optimistic Locking with select_for_update()

```python
from django.db import transaction

@transaction.atomic
def increment_view_count(topic_id):
    """Thread-safe view count increment."""
    topic = Topic.objects.select_for_update().get(id=topic_id)
    topic.views_count += 1
    topic.save(update_fields=['views_count'])
    return topic.views_count

# For high-concurrency operations
@transaction.atomic
def add_post_reaction(post_id, user_id, reaction_type):
    """Prevent duplicate reactions."""
    post = Post.objects.select_for_update(nowait=False).get(id=post_id)

    # Check existing reaction
    existing = Reaction.objects.filter(
        post=post, user_id=user_id, type=reaction_type
    ).exists()

    if not existing:
        Reaction.objects.create(
            post=post, user_id=user_id, type=reaction_type
        )
        post.reaction_count += 1
        post.save(update_fields=['reaction_count'])
```

Documentation: https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update

---

## 4. User-Generated Content Security

### HTML Sanitization

**Your Current Pattern** (from `SafeHTML` component):

```python
from django.utils.html import escape
import bleach

ALLOWED_TAGS_FORUM = [
    'p', 'br', 'strong', 'em', 'u', 'a', 'img',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'code', 'pre'
]

ALLOWED_ATTRIBUTES_FORUM = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    '*': ['class']
}

def sanitize_html(content, content_type='forum'):
    """Sanitize user-generated HTML content."""
    if content_type == 'forum':
        return bleach.clean(
            content,
            tags=ALLOWED_TAGS_FORUM,
            attributes=ALLOWED_ATTRIBUTES_FORUM,
            strip=True
        )
    return escape(content)
```

Documentation:
- bleach: https://bleach.readthedocs.io/
- django-bleach: https://github.com/marksweb/django-bleach

### Rich Text Editor Integration

**Options for Headless API**:

1. **Draft.js** (Your existing implementation):
   - GitHub: https://github.com/facebook/draft-js
   - Storage: JSON format in PostgreSQL JSONField
   - Frontend: React Draft WYSIWYG Editor
   - Pattern from your RichPost model:
```python
class RichPost(models.Model):
    rich_content = models.JSONField(
        null=True,
        help_text="Draftail editor content in Draft.js raw format"
    )
    content_format = models.CharField(
        max_length=20,
        choices=[
            ('plain', 'Plain Text'),
            ('draftail', 'Rich Content (Draftail)'),
            ('html', 'HTML'),
        ],
        default='plain'
    )
```

2. **Markdown with django-markdownx**:
   - GitHub: https://github.com/neutronX/django-markdownx
   - Better for mobile (simpler than WYSIWYG)
   - Pattern:
```python
from markdownx.models import MarkdownxField

class Post(models.Model):
    content_md = MarkdownxField()
    content_html = models.TextField(editable=False)

    def save(self, *args, **kwargs):
        # Convert markdown to HTML on save
        self.content_html = markdown.markdown(self.content_md)
        super().save(*args, **kwargs)
```

3. **Tiptap** (Modern alternative to Draft.js):
   - Website: https://tiptap.dev/
   - Better TypeScript support
   - Collaborative editing features
   - Headless (API-first)

### File/Image Upload Handling

**Your Current Pattern** (ForumPostImage model):

```python
from imagekit.models import ProcessedImageField, ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

class ForumPostImage(models.Model):
    # Main image with automatic resizing
    image = ProcessedImageField(
        upload_to='forum/posts/%Y/%m/',
        processors=[ResizeToFit(1200, 1200)],
        format='JPEG',
        options={'quality': 85}
    )

    # Thumbnail for gallery previews
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(120, 120)],
        format='JPEG',
        options={'quality': 80}
    )

    # File validation
    def clean(self):
        if self.image.size > 5 * 1024 * 1024:  # 5MB
            raise ValidationError("Image file too large")

        if not self.image.content_type.startswith('image/'):
            raise ValidationError("File is not an image")
```

**DRF File Upload ViewSet**:
```python
from rest_framework.parsers import MultiPartParser, FormParser

class PostImageUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)

        # Check ownership
        if post.poster != request.user and not request.user.is_staff:
            raise PermissionDenied()

        # Limit images per post
        existing_count = ForumPostImage.objects.filter(post=post).count()
        if existing_count >= 6:
            return Response({'error': 'Maximum 6 images per post'},
                          status=400)

        # Create image
        serializer = PostImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(post=post)
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)
```

Documentation: https://www.django-rest-framework.org/api-guide/parsers/#fileuploadparser

---

## 5. Real-Time Features (Optional)

### Django Channels for WebSockets

**Your Current Setup** (from settings.py):
- Channels 4.3.1 installed
- ASGI application configured
- Redis channel layer

```python
# settings.py
ASGI_APPLICATION = 'plant_community_backend.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

**WebSocket Consumer for Live Forum Updates**:
```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

class ForumConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.forum_id = self.scope['url_route']['kwargs']['forum_id']
        self.forum_group_name = f'forum_{self.forum_id}'

        # Join forum group
        await self.channel_layer.group_add(
            self.forum_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.forum_group_name,
            self.channel_name
        )

    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        message_type = content.get('type')

        if message_type == 'new_post':
            # Broadcast new post to all users in forum
            await self.channel_layer.group_send(
                self.forum_group_name,
                {
                    'type': 'forum_new_post',
                    'post_id': content['post_id'],
                    'topic_id': content['topic_id'],
                    'author': content['author']
                }
            )

    async def forum_new_post(self, event):
        """Send new post notification to WebSocket."""
        await self.send_json({
            'type': 'new_post',
            'post_id': event['post_id'],
            'topic_id': event['topic_id'],
            'author': event['author']
        })
```

Documentation:
- Django Channels: https://channels.readthedocs.io/
- Channels Redis: https://github.com/django/channels_redis

### Notification Systems

**django-notifications-hq** (Simple notifications):
- GitHub: https://github.com/django-notifications/django-notifications
- Pattern:
```python
from notifications.signals import notify

# Send notification
notify.send(
    sender=request.user,
    recipient=topic.poster,
    verb='replied to your topic',
    action_object=post,
    target=topic
)

# Query notifications
user.notifications.unread()
user.notifications.mark_all_as_read()
```

**Real-time with WebSocket**:
```python
# In your view after creating post
async def send_notification(user_id, notification_data):
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f'user_{user_id}',
        {
            'type': 'notification',
            'data': notification_data
        }
    )
```

---

## 6. Testing Patterns for Forum APIs

### DRF Test Client Patterns

```python
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

class ForumAPITestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.forum = Forum.objects.create(name='Test Forum')

    def test_create_topic_authenticated(self):
        """Test creating topic with authentication."""
        self.client.force_authenticate(user=self.user)

        data = {
            'subject': 'Test Topic',
            'content': 'Test content'
        }

        response = self.client.post(
            f'/api/v1/forums/{self.forum.id}/topics/',
            data=data,
            format='json'
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['subject'], 'Test Topic')

    def test_create_topic_anonymous_forbidden(self):
        """Test creating topic without authentication."""
        data = {'subject': 'Test', 'content': 'Test'}

        response = self.client.post(
            f'/api/v1/forums/{self.forum.id}/topics/',
            data=data
        )

        self.assertEqual(response.status_code, 403)

    def test_list_topics_with_pagination(self):
        """Test topic listing with pagination."""
        # Create 30 topics
        for i in range(30):
            Topic.objects.create(
                forum=self.forum,
                subject=f'Topic {i}',
                poster=self.user
            )

        response = self.client.get(
            f'/api/v1/forums/{self.forum.id}/topics/?page=2&page_size=10'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
```

### Factory Pattern for Test Fixtures

```python
import factory
from factory.django import DjangoModelFactory

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')

class ForumFactory(DjangoModelFactory):
    class Meta:
        model = Forum

    name = factory.Sequence(lambda n: f'Forum {n}')
    description = factory.Faker('paragraph')

class TopicFactory(DjangoModelFactory):
    class Meta:
        model = Topic

    forum = factory.SubFactory(ForumFactory)
    poster = factory.SubFactory(UserFactory)
    subject = factory.Faker('sentence')

class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post

    topic = factory.SubFactory(TopicFactory)
    poster = factory.SubFactory(UserFactory)
    content = factory.Faker('paragraph')

# Usage in tests
def test_topic_with_many_posts():
    topic = TopicFactory()
    posts = PostFactory.create_batch(10, topic=topic)

    assert topic.posts_count == 10
```

Documentation: https://factoryboy.readthedocs.io/

### Testing Nested Resources and Permissions

```python
class ForumPermissionsTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            password='regular123'
        )
        self.topic = TopicFactory(poster=self.regular_user)
        self.post = PostFactory(topic=self.topic, poster=self.regular_user)

    def test_edit_own_post(self):
        """Regular user can edit their own post."""
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.patch(
            f'/api/v1/posts/{self.post.id}/',
            data={'content': 'Updated content'}
        )

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, 'Updated content')

    def test_cannot_edit_others_post(self):
        """Regular user cannot edit others' posts."""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)

        response = self.client.patch(
            f'/api/v1/posts/{self.post.id}/',
            data={'content': 'Hacked content'}
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_edit_any_post(self):
        """Admin can edit any post."""
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/v1/posts/{self.post.id}/',
            data={'content': 'Admin updated'}
        )

        self.assertEqual(response.status_code, 200)
```

---

## 7. TypeScript/Dart Client Considerations

### TypeScript API Client Pattern

**From Your Existing Frontend** (`web/src/services/apiService.js`):

```typescript
// forum-api.types.ts
export interface Forum {
  id: number;
  name: string;
  description: string;
  topics_count: number;
  posts_count: number;
}

export interface Topic {
  id: number;
  subject: string;
  poster: User;
  forum: Forum;
  created: string;
  posts_count: number;
  last_post_on: string;
  views_count: number;
}

export interface Post {
  id: number;
  content: string;
  poster: User;
  created: string;
  rich_content?: any;
  content_format: 'plain' | 'draftail' | 'html';
}

// forum-api-service.ts
class ForumApiService {
  private baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  async getForums(): Promise<Forum[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/forums/`, {
      credentials: 'include',  // Include httpOnly cookies
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch forums: ${response.statusText}`);
    }

    return response.json();
  }

  async createTopic(forumId: number, data: {
    subject: string;
    content: string;
    rich_content?: any;
  }): Promise<Topic> {
    // Get CSRF token
    const csrfToken = this.getCsrfToken();

    const response = await fetch(
      `${this.baseUrl}/api/v1/forums/${forumId}/topics/`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(data)
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create topic');
    }

    return response.json();
  }

  private getCsrfToken(): string {
    const name = 'csrftoken';
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || '';
    }
    return '';
  }
}

export const forumApi = new ForumApiService();
```

### Flutter/Dart API Client Pattern

```dart
// forum_api_service.dart
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class ForumApiService {
  static const String baseUrl = 'http://localhost:8000';

  Future<List<Forum>> getForums() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');

    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/forums/'),
      headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((json) => Forum.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load forums');
    }
  }

  Future<Topic> createTopic({
    required int forumId,
    required String subject,
    required String content,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');

    if (token == null) {
      throw Exception('Not authenticated');
    }

    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/forums/$forumId/topics/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: json.encode({
        'subject': subject,
        'content': content,
      }),
    );

    if (response.statusCode == 201) {
      return Topic.fromJson(json.decode(response.body));
    } else {
      final error = json.decode(response.body);
      throw Exception(error['detail'] ?? 'Failed to create topic');
    }
  }
}

// forum.model.dart
class Forum {
  final int id;
  final String name;
  final String description;
  final int topicsCount;
  final int postsCount;

  Forum({
    required this.id,
    required this.name,
    required this.description,
    required this.topicsCount,
    required this.postsCount,
  });

  factory Forum.fromJson(Map<String, dynamic> json) {
    return Forum(
      id: json['id'],
      name: json['name'],
      description: json['description'],
      topicsCount: json['topics_count'],
      postsCount: json['posts_count'],
    );
  }
}
```

---

## 8. Key Architectural Recommendations

### 1. Leverage Django Machina Models

**Recommendation**: Continue using Django Machina's battle-tested models:
- `Forum` - Forum categories with MPTT hierarchy
- `Topic` - Discussion threads with status flags
- `Post` - Individual messages with approval workflow

**Benefits**:
- Permission system already implemented (PermissionHandler)
- Trust levels and moderation built-in
- Extensive test coverage
- Active community and updates

### 2. Extend with Custom Models

**Pattern from Your Implementation**:
```python
# RichPost for enhanced content
class RichPost(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE)
    rich_content = models.JSONField()  # Draft.js or Tiptap JSON

# PostReaction for engagement
class PostReaction(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reaction_type = models.CharField(choices=REACTIONS)

    class Meta:
        unique_together = ['post', 'user', 'reaction_type']

# ForumPostImage for media
class ForumPostImage(models.Model):
    post = models.ForeignKey(Post, related_name='images')
    image = ProcessedImageField(...)
    thumbnail = ImageSpecField(...)
```

### 3. Use Conditional Prefetching

**Pattern**:
```python
def get_queryset(self):
    action = getattr(self, 'action', None)

    if action == 'list':
        # Minimal data for list views
        return Topic.objects.select_related(
            'poster', 'forum', 'last_post__poster'
        )
    elif action == 'retrieve':
        # Full data for detail views
        return Topic.objects.select_related(
            'poster', 'forum'
        ).prefetch_related(
            Prefetch('posts', queryset=Post.objects.select_related('poster')),
            'posts__images',
            'posts__reactions'
        )
```

### 4. Implement Dual-Strategy Caching

**From Your Blog Service**:
```python
# List cache with pagination and filters
cache_key = f'topics:{forum_id}:page:{page}:filter:{filter_hash}'
# Detail cache with slug
cache_key = f'topic:{topic_id}:posts'

# Invalidation on signals
@receiver(post_save, sender=Post)
def invalidate_topic_cache(sender, instance, **kwargs):
    cache.delete(f'topic:{instance.topic_id}:*')
    cache.delete(f'forum:{instance.topic.forum_id}:topics:*')
```

### 5. Progressive Trust Levels

**Trust Level Algorithm** (from your implementation):
```python
Level 0: New User (just registered)
Level 1: Basic User (1+ posts, can participate)
Level 2: Regular User (5+ posts, 1+ topics, 7+ days, can upload images)
Level 3: Trusted User (20+ posts, 5+ topics, 14+ days)
Level 4: Veteran User (50+ posts, 10+ topics, 30+ days)
```

**Permission Mapping**:
```python
def can_attach_files(self, forum, user):
    return user.trust_level >= 2 or user.is_staff

def can_edit_posts(self, post, user):
    return post.poster == user or user.is_staff

def can_moderate(self, forum, user):
    return user.trust_level >= 3 or user.is_staff
```

### 6. Mobile-First Rich Text

**Recommendation**: Use markdown for mobile, Draft.js for web
```python
class Post(models.Model):
    content = models.TextField()  # Always store plain/markdown
    content_format = models.CharField(
        choices=[
            ('plain', 'Plain Text'),
            ('markdown', 'Markdown'),
            ('draftail', 'Rich Text')
        ]
    )
    rich_content = models.JSONField(null=True)  # Optional enhanced format
```

**Flutter markdown rendering**:
```dart
// Use flutter_markdown package
import 'package:flutter_markdown/flutter_markdown.dart';

Markdown(data: post.content)
```

---

## 9. Known Issues and Pitfalls

### Issue 1: Empty Content Handling

**Problem**: Draft.js editor can return empty string instead of null
**Solution**:
```python
class CreateTopicSerializer(serializers.Serializer):
    def validate_content(self, value):
        if not value or value.strip() == '':
            return None  # Return null not empty string
        return value
```

### Issue 2: Enter/Shift+Enter Behavior

**Problem**: Inconsistent submit behavior across platforms
**Solution**: Universal pattern
- `Enter` alone: Submit (configurable)
- `Shift+Enter`: New line
- Mobile: Dedicated send button

### Issue 3: Nested Resource Performance

**Problem**: `/forums/{id}/topics/{id}/posts/` causes N+1 queries
**Solution**:
```python
class PostViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return Post.objects.select_related(
            'poster', 'topic', 'topic__forum'
        ).prefetch_related('images', 'reactions')
```

### Issue 4: WebSocket Authentication

**Problem**: Different auth in dev vs prod
**Documentation**: See `backend/docs/api/endpoints/plant-identification.md`
**Solution**:
```python
# Dev: Token from query params
# Prod: Session auth from cookies
```

### Issue 5: CORS for WebSocket

**Problem**: WebSocket upgrade fails with CORS
**Solution**: Nginx configuration
```nginx
location /ws/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

---

## 10. Implementation Priority Recommendations

### Phase 1: Core Forum API (MVP)
1. Forum list/detail endpoints
2. Topic CRUD operations
3. Post CRUD operations
4. Basic authentication and permissions
5. Plain text content only

### Phase 2: Rich Content
1. Rich text serialization (Draft.js or Markdown)
2. HTML sanitization
3. Image upload endpoints
4. Content preview generation

### Phase 3: Engagement Features
1. Post reactions (like, helpful, etc.)
2. User trust levels
3. View tracking
4. Search functionality

### Phase 4: Real-Time (Optional)
1. WebSocket integration
2. Live post notifications
3. Online user presence
4. Typing indicators

### Phase 5: Advanced Features
1. Moderation tools
2. Report/flag system
3. AI content assistance
4. Analytics and insights

---

## 11. Quick Reference Links

### Official Documentation
- **Django 5.2**: https://docs.djangoproject.com/en/5.2/
- **DRF 3.16**: https://www.django-rest-framework.org/
- **Django Machina**: https://django-machina.readthedocs.io/
- **PostgreSQL Full-Text Search**: https://www.postgresql.org/docs/current/textsearch.html
- **Redis**: https://redis.io/docs/

### Third-Party Packages
- **django-mptt**: https://django-mptt.readthedocs.io/
- **django-treebeard**: https://django-treebeard.readthedocs.io/
- **drf-nested-routers**: https://github.com/alanjds/drf-nested-routers
- **django-filter**: https://django-filter.readthedocs.io/
- **bleach**: https://bleach.readthedocs.io/
- **factory-boy**: https://factoryboy.readthedocs.io/

### Real-Time Features
- **Django Channels**: https://channels.readthedocs.io/
- **channels-redis**: https://github.com/django/channels_redis
- **django-notifications-hq**: https://github.com/django-notifications/django-notifications

### Frontend Integration
- **Draft.js**: https://draftjs.org/
- **Tiptap**: https://tiptap.dev/
- **flutter_markdown**: https://pub.dev/packages/flutter_markdown

---

## 12. Next Steps

1. **Review Existing Implementation**: Study `/existing_implementation/backend/apps/forum_integration/`
2. **Decide on Content Format**: Plain text, Markdown, or Draft.js
3. **Design API Endpoints**: Follow your existing versioning pattern (`/api/v1/`)
4. **Create Database Models**: Extend Django Machina or build custom
5. **Implement Caching Strategy**: Follow blog cache service pattern
6. **Add Signal Handlers**: Cache invalidation on create/update/delete
7. **Write Tests**: Use factory pattern for fixtures
8. **Document API**: Add to drf-spectacular schema
9. **Build TypeScript Client**: For React web frontend
10. **Build Dart Client**: For Flutter mobile app

---

**Research compiled**: October 28, 2025
**For questions**: Refer to existing patterns in `/backend/apps/blog/` and `/existing_implementation/`
