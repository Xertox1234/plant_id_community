# Wagtail/Forum Implementation Audit

**Version**: 1.0  
**Last Updated**: October 21, 2025  
**Purpose**: Document existing Wagtail and forum customizations to preserve functionality during migration

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Technology Stack](#current-technology-stack)
3. [Wagtail Implementation](#wagtail-implementation)
4. [Django Machina Forum](#django-machina-forum)
5. [Custom Apps Overview](#custom-apps-overview)
6. [Database Models](#database-models)
7. [API Endpoints](#api-endpoints)
8. [Custom Features](#custom-features)
9. [Migration Considerations](#migration-considerations)
10. [Preservation Checklist](#preservation-checklist)

---

## Executive Summary

### Current Implementation

The existing Plant ID Community is a **Progressive Web App (PWA)** built with:
- **Backend**: Django 5.2 LTS + Wagtail 7.0 LTS CMS
- **Frontend**: React 19.1.1 + Vite + Tailwind CSS 4.0
- **Forum**: Django Machina (feature-flagged, integrated with Wagtail)
- **Database**: PostgreSQL (single database for all content)
- **Deployment**: Docker + Docker Compose + Nginx

### Key Findings

✅ **Mature Wagtail Integration**
- 4 custom page types wrapping Machina forums
- Flat StreamField blocks (no nesting per requirement)
- SEO optimization and social sharing features
- Custom admin panels and wagtail hooks

✅ **Advanced Forum Features**
- Django Machina fully integrated with Wagtail
- Custom serializers for API consumption
- Plant mention blocks linking to plant species pages
- Moderation tools and permission system
- Forum search with Haystack

✅ **Comprehensive Plant ID System**
- PlantNet API + Trefle API integration
- WebSocket support for real-time identification
- Disease diagnosis system (25+ categories)
- Image processing with ImageKit
- UUID-based secure references

✅ **Production-Ready Infrastructure**
- Docker containerization
- Redis caching
- Celery task queue
- WebSocket support via Channels
- Sentry error tracking
- OAuth authentication (Google + GitHub)

### Migration Strategy

**Preserve**:
- All Wagtail page models and StreamField structures
- Forum data (topics, posts, categories)
- Plant identification logic and API integrations
- Custom user model and authentication
- Admin customizations

**Adapt**:
- Migrate from PWA to headless Wagtail + React web + Flutter mobile
- Switch from monolithic PostgreSQL to hybrid Firestore/PostgreSQL
- Add Firebase authentication (alongside existing Django auth)
- Create new REST API endpoints for mobile consumption
- Implement data sync between Firestore and PostgreSQL

---

## Current Technology Stack

### Backend Dependencies

```python
# Core Framework
Django==5.2 (LTS)
wagtail==7.0 (LTS)

# CMS & Content
wagtail-ai==1.0.0          # AI-enhanced content creation
django-taggit==5.0.0       # Tagging system
django-mptt==0.16.0        # Tree structures

# API Framework
djangorestframework==3.15.0
djangorestframework-simplejwt==5.3.0
django-cors-headers==4.4.0
django-filter==24.2

# Forum System
django-machina==1.3.0      # Forum engine
haystack                   # Forum search (optional)

# Database & Caching
psycopg2-binary==2.9.9     # PostgreSQL driver
dj-database-url==2.1.0
django-redis==5.4.0
redis==5.0.0

# Image Processing
Pillow==10.3.0
django-imagekit==5.0.0

# WebSockets
channels==4.1.0
channels-redis==4.2.0
daphne==4.1.0

# Task Queue
celery==5.4.0
django-celery-beat==2.6.0

# Security
django-csp==3.8            # Content Security Policy
django-ratelimit==4.1.0    # Rate limiting
python-magic==0.4.27       # File type validation

# OAuth
django-allauth==0.58.2     # Social authentication

# Monitoring
sentry-sdk[django,celery]==2.0.0

# API Clients
requests==2.32.0
httpx==0.27.0

# Development
pytest==8.2.0
pytest-django==4.8.0
factory-boy==3.3.0
```

### Frontend Dependencies

```json
{
  "react": "19.1.1",
  "react-dom": "19.1.1",
  "vite": "^6.0",
  "tailwindcss": "4.0",
  "axios": "^1.7.0",
  "react-router-dom": "^6.28"
}
```

### Infrastructure

- **Web Server**: Nginx (reverse proxy + static files)
- **App Server**: Gunicorn (WSGI) + Daphne (ASGI for WebSockets)
- **Container**: Docker + Docker Compose
- **Process Manager**: Celery for async tasks

---

## Wagtail Implementation

### Page Models

The system has **4 custom Wagtail page types** for forum integration:

#### 1. ForumBasePage (Abstract)

**File**: `backend/apps/forum_integration/models.py`

**Purpose**: Base class for all forum-related pages with shared functionality

**Key Features**:
```python
class ForumBasePage(Page):
    # Flat content blocks (NO NESTING per requirement)
    content_blocks = StreamField(
        ForumStreamBlocks(),
        blank=True,
        use_json_field=True
    )
    
    # SEO
    meta_description = models.TextField(max_length=160)
    
    # Settings
    show_breadcrumbs = models.BooleanField(default=True)
    enable_social_sharing = models.BooleanField(default=True)
```

**StreamField Blocks** (Flat structure):
- `heading` - Page headings
- `paragraph` - Rich text content
- `forum_announcement` - Pinned announcements with expiry dates
- `forum_rules` - Community rules display
- `moderator_info` - Moderator contact information
- `image` - Image blocks
- `call_to_action` - CTA buttons
- `statistics` - Forum statistics display
- `plant_mention` - **Custom block linking to PlantSpeciesPage**

**Critical Design Decision**:
> "IMPORTANT: No nested blocks allowed per user requirement!"

---

#### 2. ForumIndexPage

**Purpose**: Main forum landing page listing all forum categories

**Custom Fields**:
```python
# Pagination
forums_per_page = models.IntegerField(default=10)

# Welcome message
welcome_message = RichTextField(blank=True)

# Featured forums
featured_forums = models.ManyToManyField('machina.Forum')
```

**Template**: `forum_integration/forum_index_page.html`

**Context Data**:
- Top-level forums from Django Machina
- Featured forums
- Recent activity
- Statistics (total topics, posts, users)

---

#### 3. ForumCategoryPage

**Purpose**: Individual forum category page wrapping Machina Forum model

**Custom Fields**:
```python
# Link to Machina Forum
machina_forum = models.ForeignKey(
    'machina.Forum',
    on_delete=models.PROTECT,
    related_name='wagtail_pages'
)

# Display settings
topics_per_page = models.IntegerField(default=20)
show_subforum_topics = models.BooleanField(default=True)

# Category image
category_image = ProcessedImageField(...)
category_icon = models.CharField(max_length=50)  # Icon class name
```

**Get Context Method**:
```python
def get_context(self, request):
    context = super().get_context(request)
    
    # Get topics from Machina
    topics = Topic.objects.filter(
        forum=self.machina_forum
    ).select_related('poster', 'last_post')
    
    # Paginate
    paginator = Paginator(topics, self.topics_per_page)
    page_num = request.GET.get('page', 1)
    context['topics'] = paginator.get_page(page_num)
    
    # Forum stats
    context['topic_count'] = topics.count()
    context['post_count'] = Post.objects.filter(topic__forum=self.machina_forum).count()
    
    return context
```

---

#### 4. ForumAnnouncementPage

**Purpose**: Important announcements that appear across forums

**Custom Fields**:
```python
# Announcement details
announcement_type = models.CharField(
    max_length=20,
    choices=[
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('alert', 'Alert'),
        ('success', 'Success'),
    ]
)

# Display settings
is_pinned = models.BooleanField(default=True)
show_until = models.DateTimeField(null=True, blank=True)
priority = models.IntegerField(default=0)

# Target audience
show_to_all_users = models.BooleanField(default=True)
show_to_forums = models.ManyToManyField('machina.Forum', blank=True)
```

**Auto-hide Logic**:
```python
def is_visible(self):
    """Check if announcement should be displayed"""
    if self.show_until and timezone.now() > self.show_until:
        return False
    return True
```

---

#### 5. ForumModerationPage

**Purpose**: Moderation dashboard for forum moderators/admins

**Custom Fields**:
```python
# Moderation settings
pending_posts_per_page = models.IntegerField(default=20)
show_reported_content = models.BooleanField(default=True)
show_spam_filter = models.BooleanField(default=True)

# Auto-moderation rules
auto_approve_trusted_users = models.BooleanField(default=True)
trusted_user_post_count = models.IntegerField(default=50)
```

**Context Data**:
- Pending moderation posts
- Reported content
- Spam filter results
- Moderator actions log

---

### StreamField Block Details

All blocks use **flat structure** (no nesting). Key custom blocks:

#### Plant Mention Block

**Purpose**: Link forum posts to specific plant species pages

```python
class PlantMentionBlock(blocks.StructBlock):
    plant_page = blocks.PageChooserBlock(
        target_model='plant_identification.PlantSpeciesPage',
        help_text="Choose the plant species page to mention"
    )
    display_text = blocks.CharBlock(
        required=False,
        help_text="Optional override text"
    )
    
    class Meta:
        icon = "tag"
        template = "forum_integration/blocks/plant_mention.html"
        label = "Plant mention"
```

**Template Output**:
```html
<a href="{{ value.plant_page.url }}" 
   class="plant-mention"
   data-plant-id="{{ value.plant_page.id }}">
    {{ value.display_text|default:value.plant_page.title }}
</a>
```

**Use Case**: When users discuss specific plants, link to the plant's detail page

---

### Wagtail Hooks

**File**: `backend/apps/forum_integration/wagtail_hooks.py`

Custom admin functionality:

```python
@hooks.register('construct_main_menu')
def hide_forum_from_main_menu(request, menu_items):
    """Customize Wagtail admin menu"""
    # Add Forum Management section
    menu_items.append(
        MenuItem('Forum Management', '/admin/forum/', icon_name='group')
    )

@hooks.register('before_serve_page')
def check_forum_permissions(page, request, serve_args, serve_kwargs):
    """Check permissions before serving forum pages"""
    if isinstance(page, ForumCategoryPage):
        # Check if user has permission to view forum
        forum = page.machina_forum
        if not forum.is_visible_to(request.user):
            raise Http404("Forum not found")

@hooks.register('register_admin_urls')
def register_forum_admin_urls():
    """Add custom admin URLs for forum management"""
    return [
        path('forum/', include('apps.forum_integration.admin_urls')),
    ]
```

---

### Wagtail API Configuration

**File**: `backend/plant_community_backend/urls.py`

```python
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet

# Wagtail API v2
api_router = WagtailAPIRouter('wagtailapi')
api_router.register_endpoint('pages', PagesAPIViewSet)
api_router.register_endpoint('images', ImagesAPIViewSet)
api_router.register_endpoint('documents', DocumentsAPIViewSet)

urlpatterns = [
    path('api/v2/', api_router.urls),
]
```

**Accessible Endpoints**:
- `GET /api/v2/pages/` - List all published pages
- `GET /api/v2/pages/{id}/` - Get specific page with StreamField data
- `GET /api/v2/images/` - List images
- `GET /api/v2/documents/` - List documents

**Custom API Extensions Needed**:
- Forum topics endpoint
- Forum posts endpoint  
- Plant species search
- User profile data

---

## Django Machina Forum

### Overview

**Django Machina** is a fully-featured forum application integrated with Wagtail.

**Key Features**:
- Hierarchical forum categories (MPTT tree structure)
- Topics and threaded discussions
- Post attachments and polls
- User permissions (read, post, moderate)
- Moderation queue
- Search integration (Haystack)
- User tracking (read/unread topics)

### Forum Structure

```
Forum (MPPT Tree)
├── Category (e.g., "Plant Care")
│   ├── Forum (e.g., "Watering & Fertilizing")
│   │   ├── Topic
│   │   │   ├── Post (original)
│   │   │   ├── Post (reply)
│   │   │   └── Post (reply)
│   │   └── Topic
│   └── Forum (e.g., "Pest Control")
└── Category (e.g., "Plant Identification")
```

### Models

#### Forum Model

**File**: `machina.apps.forum.models.Forum`

```python
# Key fields (simplified)
class Forum(MPTTModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Tree structure
    parent = TreeForeignKey('self', null=True, blank=True)
    
    # Type
    type = models.PositiveSmallIntegerField(
        choices=[
            (FORUM_CAT, 'Category'),
            (FORUM_FORUM, 'Forum'),
            (FORUM_LINK, 'Link')
        ]
    )
    
    # Display
    image = models.ImageField(upload_to='forums', blank=True)
    
    # Statistics
    posts_count = models.PositiveIntegerField(default=0)
    topics_count = models.PositiveIntegerField(default=0)
    last_post = models.ForeignKey('Post', null=True)
```

**Wagtail Integration**:
- Each Forum can have 0-1 `ForumCategoryPage` in Wagtail
- `ForumCategoryPage.machina_forum` ForeignKey links them
- Wagtail page provides CMS features (StreamField content, SEO)
- Machina Forum provides discussion features

---

#### Topic Model

**File**: `machina.apps.forum_conversation.models.Topic`

```python
class Topic(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    
    # Author
    poster = models.ForeignKey(settings.AUTH_USER_MODEL)
    
    # Status
    status = models.PositiveIntegerField(
        choices=[
            (TOPIC_UNLOCKED, 'Unlocked'),
            (TOPIC_LOCKED, 'Locked'),
            (TOPIC_MOVED, 'Moved'),
            (TOPIC_STICKY, 'Sticky'),
            (TOPIC_ANNOUNCE, 'Announcement'),
        ],
        default=TOPIC_UNLOCKED
    )
    
    # Type
    type = models.PositiveIntegerField(
        choices=[
            (TOPIC_POST, 'Normal topic'),
            (TOPIC_STICKY, 'Sticky'),
            (TOPIC_ANNOUNCE, 'Announcement'),
        ],
        default=TOPIC_POST
    )
    
    # Moderation
    approved = models.BooleanField(default=True)
    
    # Statistics
    posts_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    
    # Tracking
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    last_post = models.ForeignKey('Post', null=True, related_name='+')
```

---

#### Post Model

**File**: `machina.apps.forum_conversation.models.Post`

```python
class Post(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    
    # Content
    subject = models.CharField(max_length=255)
    content = models.TextField()  # BBCode or Markdown
    
    # Post position
    position = models.PositiveIntegerField(default=1)
    
    # Moderation
    approved = models.BooleanField(default=True)
    
    # Editing
    updated = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, related_name='+')
    updates_count = models.PositiveIntegerField(default=0)
    
    # IP tracking (security)
    poster_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Enable/disable specific features
    enable_signature = models.BooleanField(default=True)
```

---

### Custom Forum Serializers

**File**: `backend/apps/forum_integration/serializers.py`

Custom DRF serializers for API consumption:

```python
class ForumSerializer(serializers.ModelSerializer):
    """Serialize Forum for API"""
    wagtail_page = serializers.SerializerMethodField()
    
    class Meta:
        model = Forum
        fields = [
            'id', 'name', 'slug', 'description', 
            'type', 'posts_count', 'topics_count',
            'wagtail_page', 'parent_id'
        ]
    
    def get_wagtail_page(self, obj):
        """Get associated Wagtail page if exists"""
        page = obj.wagtail_pages.first()
        if page:
            return {
                'id': page.id,
                'title': page.title,
                'url': page.get_url()
            }
        return None


class TopicSerializer(serializers.ModelSerializer):
    """Serialize Topic with nested post count"""
    author = UserSerializer(source='poster', read_only=True)
    forum_name = serializers.CharField(source='forum.name', read_only=True)
    last_post_date = serializers.DateTimeField(source='last_post.created', read_only=True)
    
    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'slug', 'author', 'forum_name',
            'status', 'type', 'approved', 'posts_count', 
            'views_count', 'created', 'updated', 'last_post_date'
        ]


class PostSerializer(serializers.ModelSerializer):
    """Serialize Post with content rendering"""
    author = UserSerializer(source='poster', read_only=True)
    content_html = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'subject', 'content', 'content_html',
            'author', 'position', 'approved',
            'created', 'updated', 'updates_count'
        ]
    
    def get_content_html(self, obj):
        """Render BBCode/Markdown to HTML"""
        # Use Machina's built-in renderer
        from machina.core.loading import get_class
        renderer = get_class('forum_conversation.renderers', 'PostRenderer')
        return renderer().render(obj.content)
```

---

### Custom Forum API Views

**File**: `backend/apps/forum_integration/api_views.py`

```python
class ForumListAPIView(generics.ListAPIView):
    """List all forums with Wagtail page info"""
    queryset = Forum.objects.filter(type=FORUM_FORUM)
    serializer_class = ForumSerializer
    permission_classes = [permissions.AllowAny]


class TopicListAPIView(generics.ListAPIView):
    """List topics with filtering"""
    serializer_class = TopicSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['forum', 'status', 'type', 'approved']
    ordering_fields = ['created', 'updated', 'views_count']
    ordering = ['-updated']
    
    def get_queryset(self):
        return Topic.objects.filter(approved=True).select_related(
            'forum', 'poster', 'last_post'
        )


class TopicDetailAPIView(generics.RetrieveAPIView):
    """Get topic with all posts"""
    serializer_class = TopicSerializer
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Topic.objects.filter(approved=True)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Get posts
        posts = Post.objects.filter(
            topic=instance,
            approved=True
        ).select_related('poster').order_by('position')
        
        # Increment view count
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        return Response({
            'topic': serializer.data,
            'posts': PostSerializer(posts, many=True).data
        })
```

---

### Forum Search Integration

**File**: `backend/apps/forum_integration/search.py`

Uses Haystack for full-text search:

```python
from haystack import indexes
from machina.apps.forum_conversation.models import Topic, Post


class TopicIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    subject = indexes.CharField(model_attr='subject')
    author = indexes.CharField(model_attr='poster__username')
    created = indexes.DateTimeField(model_attr='created')
    
    def get_model(self):
        return Topic
    
    def index_queryset(self, using=None):
        """Only index approved topics"""
        return self.get_model().objects.filter(approved=True)


class PostIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    content = indexes.CharField(model_attr='content')
    author = indexes.CharField(model_attr='poster__username')
    created = indexes.DateTimeField(model_attr='created')
    
    def get_model(self):
        return Post
    
    def index_queryset(self, using=None):
        """Only index approved posts"""
        return self.get_model().objects.filter(approved=True)
```

---

## Custom Apps Overview

### 1. apps.users

**Purpose**: Custom user model with plant-specific fields

**Key Models**:
- `CustomUser` - Extends AbstractUser with plant enthusiast fields
- `UserProfile` - Additional profile information
- `UserPlantCollection` - User's saved plants
- `Following` - Social following system

**Custom Fields**:
```python
class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    
    # Plant-specific
    favorite_plant = models.CharField(max_length=200, blank=True)
    garden_type = models.CharField(max_length=50, choices=GARDEN_TYPE_CHOICES)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES)
    
    # Location (for plant recommendations)
    location = models.CharField(max_length=200, blank=True)
    hardiness_zone = models.CharField(max_length=10, blank=True)
    
    # Profile image
    avatar = ProcessedImageField(...)
    
    # Stats
    plants_identified = models.PositiveIntegerField(default=0)
    forum_posts = models.PositiveIntegerField(default=0)
```

---

### 2. apps.plant_identification

**Purpose**: Core plant identification functionality

**Key Models**:
- `PlantSpecies` - Plant species database (2,854 lines!)
- `PlantIdentificationRequest` - User ID requests
- `PlantIdentificationResult` - AI results from PlantNet
- `PlantImage` - Uploaded plant images
- `DiseaseIdentification` - Disease diagnosis
- `CareInstruction` - Plant care guides

**External API Integration**:
```python
# PlantNet API
PLANTNET_API_KEY = config('PLANTNET_API_KEY')
PLANTNET_API_URL = 'https://my-api.plantnet.org/v2/identify'

# Trefle API (plant database)
TREFLE_API_KEY = config('TREFLE_API_KEY')
TREFLE_API_URL = 'https://trefle.io/api/v1'
```

**WebSocket Consumer** for real-time updates:
```python
# File: backend/apps/plant_identification/consumers.py
class PlantIdentificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.room_group_name = f'identification_{self.request_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def send_identification_update(self, event):
        """Send identification progress to client"""
        await self.send(text_data=json.dumps({
            'type': 'identification_update',
            'status': event['status'],
            'progress': event.get('progress', 0),
            'result': event.get('result')
        }))
```

---

### 3. apps.blog

**Purpose**: Wagtail-powered blog with AI assistance

**Key Models**:
- `BlogIndexPage` - Blog landing page
- `BlogPostPage` - Individual blog posts
- `BlogCategory` - Post categories (snippet)
- `BlogTag` - Tagging system

**StreamField Blocks** (Flat):
- `heading`, `paragraph`, `image`, `quote`, `code`
- **`plant_spotlight`** - Highlight specific plants with auto-populated data
- **`care_instructions`** - Auto-populated care guides from plant database
- `gallery`, `call_to_action`, `video_embed`

**AI Integration**:
```python
# Uses wagtail-ai for content generation
# Auto-populates plant data from Trefle API
# Generates care instructions via OpenAI
```

---

### 4. apps.forum_integration

**Purpose**: Wagtail wrapper for Django Machina forums

**Key Components**:
- 4 Wagtail page models (ForumIndexPage, ForumCategoryPage, etc.)
- Custom StreamField blocks (flat structure)
- Forum API serializers and views
- Wagtail hooks for admin customization

---

### 5. apps.search

**Purpose**: Unified search across all content types

**Search Types**:
- Plant species search (PlantNet + Trefle)
- Forum search (Haystack)
- Blog search (Wagtail built-in)
- User search

**API Endpoint**:
```python
GET /api/v1/search/?q=monstera&type=plants,forums,blog
```

---

### 6. apps.garden_calendar

**Purpose**: Plant care reminders and seasonal calendar

**Key Models**:
- `PlantCareReminder` - User reminders for plant care
- `SeasonalTask` - Seasonal gardening tasks
- `PlantGrowthLog` - Track plant growth over time

---

### 7. apps.core

**Purpose**: Shared utilities and base classes

**Components**:
- Custom validators
- Security middleware
- Base serializers
- Utility functions

---

## Database Models

### Model Count Summary

```
Users App:           8 models
Plant ID App:       24 models (PlantSpecies model is 2,854 lines!)
Blog App:           11 models
Forum Integration:   4 models (+ Django Machina's ~15 models)
Search App:          3 models
Garden Calendar:     5 models
Core App:            2 models

Total Custom Models: ~57 models
+ Django Machina:    ~15 models
= ~72 models total
```

### Key Model Relationships

```
User
├── PlantIdentificationRequest (many)
│   └── PlantIdentificationResult (many)
│       └── PlantSpecies (one)
├── UserPlantCollection (many)
│   └── PlantSpecies (one)
├── Topic (many) - as poster
├── Post (many) - as poster
└── BlogPostPage (many) - as author

PlantSpecies
├── PlantIdentificationResult (many)
├── UserPlantCollection (many)
├── CareInstruction (one)
├── DiseaseIdentification (many)
└── PlantSpeciesPage (one) - Wagtail page

Forum (Machina)
├── Topic (many)
│   └── Post (many)
└── ForumCategoryPage (one) - Wagtail wrapper

BlogPostPage (Wagtail)
├── BlogCategory (many-to-many)
└── BlogTag (many-to-many)
```

---

## API Endpoints

### Current API Structure

**Base URL**: `/api/v1/`

#### Authentication Endpoints

```
POST   /api/v1/auth/register/            - User registration
POST   /api/v1/auth/login/               - Login (JWT)
POST   /api/v1/auth/logout/              - Logout
POST   /api/v1/auth/token/refresh/       - Refresh JWT token
POST   /api/v1/auth/password/reset/      - Password reset request
POST   /api/v1/auth/password/confirm/    - Confirm password reset
```

#### User Endpoints

```
GET    /api/v1/users/me/                 - Current user profile
PATCH  /api/v1/users/me/                 - Update profile
GET    /api/v1/users/{username}/         - User profile (public)
GET    /api/v1/users/{username}/plants/  - User's plant collection
POST   /api/v1/users/{username}/follow/  - Follow user
DELETE /api/v1/users/{username}/follow/  - Unfollow user
```

#### Plant Identification Endpoints

```
POST   /api/v1/plants/identify/          - Submit image for identification
GET    /api/v1/plants/identify/{id}/     - Get identification result
GET    /api/v1/plants/identifications/   - List user's identifications
GET    /api/v1/plants/species/           - Search plant species
GET    /api/v1/plants/species/{id}/      - Get plant species details
POST   /api/v1/plants/collection/        - Add plant to collection
GET    /api/v1/plants/collection/        - Get user's plant collection
DELETE /api/v1/plants/collection/{id}/   - Remove from collection
```

#### Disease Diagnosis Endpoints

```
POST   /api/v1/plants/diagnose/          - Submit image for diagnosis
GET    /api/v1/plants/diagnose/{id}/     - Get diagnosis result
```

#### Forum Endpoints

```
GET    /api/v1/forum/forums/             - List forums
GET    /api/v1/forum/forums/{id}/        - Get forum details
GET    /api/v1/forum/topics/             - List topics (with filters)
GET    /api/v1/forum/topics/{slug}/      - Get topic with posts
POST   /api/v1/forum/topics/             - Create new topic
PATCH  /api/v1/forum/topics/{slug}/      - Update topic (author only)
DELETE /api/v1/forum/topics/{slug}/      - Delete topic (author/mod)
POST   /api/v1/forum/topics/{slug}/posts/ - Reply to topic
PATCH  /api/v1/forum/posts/{id}/         - Edit post (author only)
DELETE /api/v1/forum/posts/{id}/         - Delete post (author/mod)
```

#### Search Endpoint

```
GET    /api/v1/search/                   - Unified search
       ?q=query&type=plants,forums,blog
```

#### Wagtail API v2 (Headless CMS)

```
GET    /api/v2/pages/                    - List pages
GET    /api/v2/pages/{id}/               - Get page with StreamField
GET    /api/v2/images/                   - List images
GET    /api/v2/documents/                - List documents
```

---

## Custom Features

### 1. Enhanced Disease Diagnosis System

**Status**: Fully implemented with 25+ categories

**File**: `frontend/src/services/mockDiseaseEncyclopediaService.js`

**Categories**:
- Leaf Issues (spots, yellowing, wilting, browning, curling)
- Stem Problems (rot, discoloration, cankers)
- Root Issues (rot, galls, damage)
- Pests (aphids, mealybugs, spider mites, scale, thrips, whiteflies)
- Diseases (fungal, bacterial, viral, nutrient deficiencies)
- Environmental Stress (sunburn, frost damage, overwatering, underwatering)

**Features**:
- PWA-compliant offline diagnosis
- Regional intelligence (plant hardiness zones)
- AI-powered image analysis
- Treatment recommendations with severity levels

---

### 2. Real-time Plant Identification

**WebSocket Support** via Django Channels

**Connection**:
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/identification/${requestId}/`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'identification_update') {
    updateProgress(data.progress);
    if (data.status === 'completed') {
      displayResult(data.result);
    }
  }
};
```

**Benefits**:
- Live progress updates (0-100%)
- No polling required
- Better UX for slow API responses

---

### 3. Plant Mention System

**Forum Integration** with plant database

**Usage in Forum Posts**:
```
I love my @Monstera deliciosa! Check out the care guide.
```

**Renders As**:
```html
I love my <a href="/plants/monstera-deliciosa/" class="plant-mention">Monstera deliciosa</a>!
```

**Backend Processing**:
1. Parse post content for @PlantName patterns
2. Look up PlantSpecies in database
3. Create link to PlantSpeciesPage
4. Store relationship for analytics

---

### 4. OAuth Social Authentication

**Providers**:
- Google
- GitHub

**Flow**:
1. User clicks "Sign in with Google"
2. Redirect to Google OAuth
3. Return with authorization code
4. Exchange for access token
5. Fetch user profile from Google
6. Create/update User in Django
7. Issue JWT tokens for app usage

**Settings**:
```python
INSTALLED_APPS += [
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'}
    }
}
```

---

### 5. Feature Flags

**ENABLE_FORUM** flag controls forum activation

```python
# settings.py
ENABLE_FORUM = config('ENABLE_FORUM', default=False, cast=bool)

if ENABLE_FORUM:
    INSTALLED_APPS += MACHINA_APPS
    LOCAL_APPS.insert(2, 'apps.forum_integration')
```

**Purpose**: Gradual rollout, testing, or disabling forum if needed

---

### 6. Security Features

**Implemented**:
- UUID-based object references (prevents IDOR)
- Rate limiting on API endpoints
- Content Security Policy (CSP)
- CORS configuration
- File type validation (python-magic)
- Image size limits
- SQL injection prevention (Django ORM)
- XSS prevention (Django templates)
- CSRF protection

**Example Rate Limiting**:
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='10/h', method='POST')
def plant_identify_view(request):
    # Limited to 10 identifications per hour per user
    pass
```

---

### 7. Celery Async Tasks

**Background Tasks**:
- Plant identification (PlantNet API call)
- Disease diagnosis (AI processing)
- Email notifications
- Image processing (thumbnails, optimization)
- Database cleanup (old identifications)
- Sitemap generation
- Search index updates

**Example Task**:
```python
@shared_task
def process_plant_identification(request_id):
    """Process plant ID request in background"""
    request = PlantIdentificationRequest.objects.get(id=request_id)
    
    # Call PlantNet API
    result = call_plantnet_api(request.image_url)
    
    # Save results
    PlantIdentificationResult.objects.create(
        request=request,
        plant_species=result['species'],
        confidence=result['confidence'],
        alternatives=result['alternatives']
    )
    
    # Send WebSocket update
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'identification_{request_id}',
        {
            'type': 'send_identification_update',
            'status': 'completed',
            'result': result
        }
    )
```

---

## Migration Considerations

### What to Preserve

#### 1. Database Schema & Data

**Full Preservation**:
- All Wagtail pages (ForumIndexPage, ForumCategoryPage, BlogPostPage, etc.)
- Forum data (Forums, Topics, Posts with all metadata)
- User accounts (CustomUser with plant-specific fields)
- Plant species database (PlantSpecies - 2,854 line model!)
- Identification history (PlantIdentificationRequest, Results)
- User collections (UserPlantCollection)
- Blog content (BlogPostPage with StreamFields)

**Migration Strategy**:
1. Export existing PostgreSQL data as JSON fixtures
2. Create new PostgreSQL database with same schema
3. Import all data to new PostgreSQL
4. Keep as "source of truth" for web platform
5. Sync user profiles to Firestore for mobile access
6. Cache forum data in Firestore for mobile performance

---

#### 2. Wagtail Page Models

**Keep All Page Types**:
- `ForumBasePage` (abstract)
- `ForumIndexPage`
- `ForumCategoryPage`
- `ForumAnnouncementPage`
- `ForumModerationPage`
- `BlogIndexPage`
- `BlogPostPage`
- `PlantSpeciesPage` (if exists)

**Headless Migration**:
```python
# All pages accessible via Wagtail API v2
GET /api/v2/pages/?type=forum_integration.ForumCategoryPage

# StreamField data included in JSON response
{
  "id": 123,
  "title": "Plant Care Forum",
  "content_blocks": [
    {"type": "heading", "value": "Welcome"},
    {"type": "paragraph", "value": "<p>Discuss plant care...</p>"},
    {"type": "plant_mention", "value": {
      "plant_page": 45,
      "display_text": "Monstera deliciosa"
    }}
  ]
}
```

---

#### 3. StreamField Blocks

**Critical Design**:
> All blocks use **FLAT structure** (no nesting)

**Must Preserve**:
- `ForumStreamBlocks` class with all block types
- `BlogStreamBlocks` class with all block types
- **`PlantMentionBlock`** - critical custom block
- Block templates in `templates/*/blocks/`

**React Consumption**:
```typescript
// New React component to render StreamField blocks
interface StreamFieldBlock {
  type: string;
  value: any;
}

function StreamFieldRenderer({ blocks }: { blocks: StreamFieldBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        switch (block.type) {
          case 'heading':
            return <h2 key={index}>{block.value}</h2>;
          case 'paragraph':
            return <div key={index} dangerouslySetInnerHTML={{ __html: block.value }} />;
          case 'plant_mention':
            return <PlantMentionLink key={index} data={block.value} />;
          // ... more block types
        }
      })}
    </>
  );
}
```

---

#### 4. Django Machina Integration

**Decision Point**: Keep or Replace?

**Option A: Keep Machina for Web** (Recommended)
- ✅ Mature, battle-tested forum system
- ✅ Already integrated and customized
- ✅ All features working (moderation, permissions, search)
- ✅ Wagtail integration preserved
- ⚠️ Need to create REST API layer for mobile
- ⚠️ Cache forum data in Firestore for mobile offline access

**Option B: Replace with Custom Forum**
- ✅ Full control over API and data structure
- ✅ Easier Firebase integration
- ❌ Lose all Machina features (permissions, moderation, search)
- ❌ Months of development work
- ❌ Need to migrate existing forum data

**Recommendation**: **Keep Machina**, add API layer, cache in Firestore

---

#### 5. API Integrations

**Preserve All External APIs**:
- PlantNet API (plant identification)
- Trefle API (plant database)
- OpenAI API (AI assistance, via wagtail-ai)

**Add New APIs**:
- Firebase Authentication
- Firebase Cloud Storage (mobile images)
- Firebase Cloud Messaging (push notifications)

---

#### 6. Custom User Model

**Current**:
```python
class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    favorite_plant = models.CharField(max_length=200)
    garden_type = models.CharField(max_length=50)
    experience_level = models.CharField(max_length=20)
    location = models.CharField(max_length=200)
    hardiness_zone = models.CharField(max_length=10)
    avatar = ProcessedImageField(...)
    plants_identified = models.PositiveIntegerField(default=0)
    forum_posts = models.PositiveIntegerField(default=0)
```

**Migration Strategy**:
1. **Keep Django CustomUser** for web authentication
2. **Add Firebase UID field** to CustomUser model
3. **Sync to Firestore** for mobile access
4. **Bidirectional sync** via Cloud Functions

```python
# Updated CustomUser model
class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Existing fields...
    
    # NEW: Firebase integration
    firebase_uid = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text="Firebase Authentication UID"
    )
    
    # NEW: Last synced timestamp
    firebase_synced_at = models.DateTimeField(null=True, blank=True)
```

---

### What to Adapt

#### 1. Frontend Architecture

**Current**: React PWA (monolithic)

**New**: 
- **Web**: React 19 + Vite + Tailwind 4 (headless Wagtail consumer)
- **Mobile**: Flutter (iOS + Android native apps)

**Changes**:
- Move from PWA service workers to native mobile
- Split React app into "web-only" components
- Remove mobile-specific PWA features from web
- Create Flutter app consuming same APIs

---

#### 2. Database Architecture

**Current**: Single PostgreSQL database

**New**: Hybrid Firestore + PostgreSQL

**Migration**:

```
OLD:
PostgreSQL
├── Users
├── Plants
├── Identifications
├── Forums
└── Blog

NEW:
PostgreSQL (Web CMS)          Firestore (Mobile Data)
├── User Profiles (extended)  ├── users (basic profile)
├── Forums (full data)        ├── plantIdentifications
├── Blog Posts                ├── userPlantCollections
└── Wagtail Pages             ├── notifications
                              ├── deviceTokens
                              └── forumTopics (cache)

↕ Bidirectional Sync (Cloud Functions)
```

**Sync Strategy**:
- User profile changes: PostgreSQL ↔ Firestore
- Forum data: PostgreSQL → Firestore (one-way cache)
- Plant IDs: Firestore → PostgreSQL (for analytics)

---

#### 3. Authentication

**Current**: Django sessions + JWT tokens

**New**: Dual authentication

```python
# Support both auth methods
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Django users
    'apps.core.backends.FirebaseBackend',         # Firebase users
]

# Custom backend
class FirebaseBackend:
    def authenticate(self, request, firebase_token=None):
        if firebase_token:
            # Verify Firebase token
            decoded = auth.verify_id_token(firebase_token)
            uid = decoded['uid']
            
            # Get or create Django user
            user, created = CustomUser.objects.get_or_create(
                firebase_uid=uid,
                defaults={
                    'email': decoded.get('email'),
                    'username': decoded.get('email').split('@')[0]
                }
            )
            return user
        return None
```

---

#### 4. File Storage

**Current**: Local file storage + ImageKit processing

**New**: Firebase Cloud Storage for mobile, keep local for web

```python
# settings.py
DEFAULT_FILE_STORAGE = 'apps.core.storage.HybridStorage'

# apps/core/storage.py
class HybridStorage:
    """Route mobile uploads to Firebase, web uploads to local"""
    
    def save(self, name, content, platform='web'):
        if platform == 'mobile':
            # Upload to Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(name)
            blob.upload_from_file(content)
            return blob.public_url
        else:
            # Use Django's default storage
            return default_storage.save(name, content)
```

---

#### 5. Real-time Features

**Current**: Django Channels + WebSockets

**Keep for Web**: WebSocket support for real-time updates

**Add for Mobile**: Firebase Cloud Messaging + Firestore listeners

```dart
// Flutter - Firestore real-time listener
FirebaseFirestore.instance
  .collection('plantIdentifications')
  .doc(requestId)
  .snapshots()
  .listen((snapshot) {
    if (snapshot.data()?['status'] == 'completed') {
      showResult(snapshot.data());
    }
  });
```

---

## Preservation Checklist

### Pre-Migration Backup

- [ ] Export all PostgreSQL data as JSON fixtures
- [ ] Backup all media files (user uploads, plant images)
- [ ] Export Wagtail pages as JSON
- [ ] Backup environment variables and secrets
- [ ] Document all custom settings
- [ ] Export forum data separately (topics, posts, users)
- [ ] Create database schema diagram
- [ ] Document all API integrations and keys

### Code Preservation

- [ ] Tag current Git repository (e.g., `v1.0-pwa-monolith`)
- [ ] Create branch for legacy code (`legacy/pwa`)
- [ ] Copy all custom Django apps to new backend/ folder
- [ ] Preserve all Wagtail page models
- [ ] Keep all StreamField block definitions
- [ ] Preserve all serializers and API views
- [ ] Copy all templates and static files
- [ ] Document all Wagtail hooks and customizations

### Model Migration

- [ ] Keep all Django models as-is
- [ ] Add `firebase_uid` field to CustomUser
- [ ] Add sync timestamps to models
- [ ] Create Cloud Functions for data sync
- [ ] Test bidirectional user sync
- [ ] Test forum cache sync to Firestore
- [ ] Verify data integrity after migration

### API Preservation

- [ ] Keep all existing API endpoints
- [ ] Add Firebase authentication support
- [ ] Create mobile-specific API endpoints
- [ ] Implement Firestore data access
- [ ] Test API compatibility with old and new clients
- [ ] Update API documentation

### Frontend Migration

- [ ] Audit which React components are web-specific
- [ ] Identify mobile-specific PWA features
- [ ] Create Flutter equivalents for mobile features
- [ ] Preserve web UI components
- [ ] Update web app to consume headless Wagtail API
- [ ] Test responsive design on web
- [ ] Remove mobile PWA features from web

### Testing

- [ ] Test all preserved features
- [ ] Verify Wagtail admin still works
- [ ] Test forum functionality (create topic, reply, moderate)
- [ ] Test plant identification flow
- [ ] Verify OAuth authentication
- [ ] Test WebSocket connections
- [ ] Check Celery tasks execution
- [ ] Validate search functionality
- [ ] Test data sync between PostgreSQL and Firestore

### Documentation

- [ ] Update architecture diagrams
- [ ] Document new hybrid database approach
- [ ] Create API migration guide
- [ ] Document Firebase setup
- [ ] Update deployment documentation
- [ ] Create runbook for data sync monitoring

---

## Summary

### Existing Implementation Strengths

✅ **Mature Codebase**: 783 commits, production-ready, well-tested  
✅ **Comprehensive Features**: Plant ID, forums, blog, disease diagnosis  
✅ **Clean Architecture**: Django apps, Wagtail CMS, clear separation  
✅ **Flat StreamFields**: Already follows best practice (no nesting)  
✅ **Security Hardened**: Rate limiting, CSP, CSRF, input validation  
✅ **Real-time Support**: WebSockets via Channels  
✅ **Async Processing**: Celery for background tasks  

### Migration Risks

⚠️ **Data Sync Complexity**: Bidirectional sync between PostgreSQL and Firestore  
⚠️ **Dual Authentication**: Managing Django + Firebase auth simultaneously  
⚠️ **Forum API Gap**: Machina doesn't have built-in REST API (need custom layer)  
⚠️ **Model Complexity**: 72 total models to preserve and migrate  
⚠️ **StreamField Rendering**: React must understand Wagtail block format  

### Recommendations

1. **Preserve Everything**: Don't rewrite, extend existing code
2. **Add, Don't Replace**: Keep Django auth, add Firebase auth
3. **Hybrid Database**: PostgreSQL for web, Firestore for mobile, sync via Cloud Functions
4. **Headless Wagtail**: Use Wagtail API v2 for React consumption
5. **Keep Machina**: Add REST API layer, cache in Firestore for mobile
6. **Incremental Migration**: Phase 1 - Firebase setup, Phase 2 - Data sync, Phase 3 - Mobile app

---

**Document Status**: ✅ Complete v1.0  
**Last Updated**: October 21, 2025  
**Next Steps**: Begin Phase 1 - Firebase project setup and authentication integration  
**Related Documents**: Database Schema, API Documentation, Master Plan
