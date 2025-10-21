# Forum Customizations Documentation

**Date**: October 21, 2025  
**App**: `forum_integration`  
**Purpose**: Document all custom forum features and Django Machina + Wagtail integration

---

## Overview

The Plant ID Community forum is built on **Django Machina** (a powerful Django forum engine) wrapped in **Wagtail CMS pages**. This hybrid approach gives us:

- ✅ **Forum functionality**: Django Machina's robust forum features
- ✅ **CMS flexibility**: Wagtail's page management and content editing
- ✅ **Custom features**: Plant-specific forum enhancements
- ✅ **API access**: RESTful API for mobile app integration

---

## Architecture

### Integration Pattern

```
Wagtail Pages (CMS Layer)
       ↓
  Custom Page Models
       ↓
Django Machina (Forum Engine)
       ↓
  PostgreSQL Database
```

### Key Components

1. **Wagtail Page Models** (`models.py`)
   - `ForumBasePage` - Abstract base class
   - `ForumIndexPage` - Main forum landing page
   - `ForumCategoryPage` - Individual forum categories
   - `ForumAnnouncementPage` - Announcements system
   - `ForumModerationPage` - Moderation tools

2. **Django Views** (`views.py`)
   - Simple function-based views for forum operations
   - Bypasses Wagtail page serving for better performance

3. **REST API** (`api_views.py` - 1271 lines!)
   - Complete DRF API for mobile app access
   - 20+ API endpoints

4. **Serializers** (`serializers.py` - 469 lines)
   - Data serialization for API responses
   - User, Forum, Topic, Post serializers

---

## Custom Wagtail Page Models

### 1. ForumBasePage (Abstract)

**Purpose**: Base class providing common functionality for all forum pages

#### Features:
- **Flat StreamField blocks** (NO NESTING - user requirement!)
- SEO metadata (meta_description)
- Breadcrumb navigation toggle
- Social sharing toggle
- Search indexing

#### StreamField Blocks:
```python
ForumStreamBlocks:
  - heading: Title blocks
  - paragraph: Rich text content
  - forum_announcement: Pinned announcements with expiry dates
  - forum_rules: Forum rules display
  - moderator_info: Moderator profiles with contact info
  - image: Image embeds via Wagtail's ImageChooser
  - call_to_action: CTA buttons with URLs
  - statistics: Forum statistics display
  - plant_mention: Links to PlantSpeciesPage (plant references)
```

**Critical Design Constraint**: 
> **NO NESTED BLOCKS** - All StreamField blocks are flat structure only. This was a specific user requirement.

---

### 2. ForumIndexPage

**Purpose**: Main forum landing page displaying all categories

#### Custom Fields:
- `forums_per_page` (IntegerField) - Pagination control
- `show_statistics` (BooleanField) - Toggle forum stats
- `welcome_message` (TextField) - Welcome text for visitors

#### Context Data:
```python
{
    'forums': Forum.objects.filter(type=Forum.FORUM_POST),
    'welcome_message': str,
    'show_statistics': bool
}
```

#### Use Case:
- Single page showing all forum categories
- Forum statistics (total posts, topics, members)
- Welcome message for new users

---

### 3. ForumCategoryPage

**Purpose**: Display specific forum category with topics list

#### Custom Fields:
- `machina_forum_id` (IntegerField) - **Links to Django Machina forum**
- `topics_per_page` (IntegerField, default=25) - Pagination
- `allow_new_topics` (BooleanField, default=True) - Topic creation toggle
- `show_topic_stats` (BooleanField, default=True) - Stats display
- `require_approval` (BooleanField, default=False) - **Moderation control**

#### Context Data:
```python
{
    'forum': machina.Forum,
    'topics': Paginated(Topic.objects),
    'allow_new_topics': bool,
    'show_topic_stats': bool,
    'require_approval': bool
}
```

#### Key Integration Point:
The `machina_forum_id` field **bridges Wagtail pages to Machina forums**. Each Wagtail page wraps a specific Machina forum by its ID.

#### Features:
- Lists all topics in the forum
- Pagination (configurable per page)
- Topic statistics (replies, views, last post)
- Moderation approval workflow
- Permission-based topic creation

---

### 4. ForumAnnouncementPage

**Purpose**: Special page type for forum-wide announcements

#### Custom Fields:
- `is_pinned` (BooleanField, default=True) - Pin to top
- `show_until` (DateTimeField, nullable) - **Auto-expiration**
- `announcement_type` (ChoiceField) - Styling variants
  - `info` - Information
  - `warning` - Warning
  - `urgent` - Urgent
  - `maintenance` - Maintenance notice
- `show_to_all` (BooleanField, default=True) - Public visibility
- `show_to_members_only` (BooleanField, default=False) - Member-only

#### Use Cases:
- System maintenance notices
- Forum rule updates
- Important community announcements
- Temporary alerts with expiration

#### Smart Feature:
Announcements can **auto-hide after a date** (`show_until` field), perfect for time-sensitive notices.

---

### 5. ForumModerationPage

**Purpose**: Moderation dashboard and tools (staff/admin only)

#### Custom Fields:
- `show_pending_posts` (BooleanField, default=True)
- `show_reported_content` (BooleanField, default=True)
- `show_user_management` (BooleanField, default=True)
- `enable_spam_detection` (BooleanField, default=True)
- `auto_approve_trusted_users` (BooleanField, default=True)

#### Access Control:
```python
def serve(self, request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_staff or request.user.is_superuser):
        raise Http404("Page not found")
    
    return super().serve(request)
```

#### Moderation Features:
- Pending posts queue
- Reported content review
- User management tools
- Spam detection system
- Trusted user auto-approval

---

## Custom Forum Features

### 1. Plant Mention Block

**Unique Feature**: Reference plant species directly in forum posts

```python
class PlantMentionBlock(blocks.StructBlock):
    plant_page = blocks.PageChooserBlock(
        target_model='plant_identification.PlantSpeciesPage'
    )
    display_text = blocks.CharBlock(required=False)
```

**Use Case**: Users can mention specific plants and link to their species pages, creating rich interconnected content.

---

### 2. Forum AI Usage Tracking

**Model**: `ForumAIUsage` (from `models.py`, needs full implementation)

**Purpose**: Track AI-generated content in forums

Expected fields:
- AI provider (GPT, Claude, etc.)
- Usage timestamp
- Token count
- Associated post/topic

**Migration Impact**: May need Firebase integration for mobile app AI usage tracking.

---

### 3. Post Image Management

**Model**: `ForumPostImage`

**Purpose**: Image attachments in forum posts

Features:
- ImageKit integration for thumbnails/optimizations
- Multiple images per post
- Image galleries

---

### 4. Post Reactions System

**Model**: `PostReaction`

**Purpose**: Like/react to forum posts (beyond simple upvotes)

Expected reaction types:
- Like
- Helpful
- Insightful
- Agree/Disagree

---

### 5. Post Templates

**Model**: `PostTemplate`

**Purpose**: Pre-formatted post templates for common questions

Use cases:
- "Help identifying this plant" template
- "Disease diagnosis request" template
- "Care question" template

---

## REST API Endpoints

### Complete API (from `api_views.py` - 1271 lines)

#### Forum Categories
```
GET /api/forum/categories/
  → ForumCategoryListView
  → Returns: List of all forum categories
  → Serializer: ForumCategorySerializer
  → Permissions: AllowAny
```

#### Topics
```
GET /api/forum/forum/<forum_id>/topics/
  → ForumTopicsListView
  → Returns: Topics in specific forum
  → Serializer: TopicSerializer
  → Permissions: AllowAny

GET /api/forum/topics/
  → all_topics_list (function-based view)
  → Returns: All topics across all forums
  → Pagination: 25 per page (configurable)
  → Permissions: AllowAny

GET /api/forum/topic/<topic_id>/
  → TopicDetailView
  → Returns: Single topic details
  → Serializer: TopicSerializer
  → Permissions: AllowAny

POST /api/forum/topic/create/
  → CreateTopicView
  → Creates: New forum topic
  → Serializer: CreateTopicSerializer
  → Permissions: IsAuthenticated

PUT /api/forum/topic/<topic_id>/update/
  → TopicUpdateView
  → Updates: Topic subject/content
  → Serializer: CreateTopicSerializer
  → Permissions: IsAuthenticated (author only)
```

#### Posts
```
GET /api/forum/posts/
  → PostListView
  → Returns: All posts (with filters)
  → Serializer: PostSerializer
  → Permissions: AllowAny

POST /api/forum/posts/create/
  → PostCreateView
  → Creates: New post in topic
  → Serializer: CreatePostSerializer
  → Permissions: IsAuthenticated

PUT /api/forum/posts/<post_id>/update/
  → PostUpdateView
  → Updates: Post content
  → Serializer: CreatePostSerializer
  → Permissions: IsAuthenticated (author only)

DELETE /api/forum/posts/<post_id>/delete/
  → PostDeleteView
  → Deletes: Post (soft delete)
  → Permissions: IsAuthenticated (author/moderator)

POST /api/forum/posts/<post_id>/react/
  → PostReactionView
  → Creates: Reaction to post
  → Permissions: IsAuthenticated
```

#### Utilities
```
POST /api/forum/topic/<topic_id>/mark-viewed/
  → TopicMarkViewedView
  → Action: Increment view count
  → Permissions: AllowAny

GET /api/forum/posts/<post_id>/images/
  → PostImageListView
  → Returns: Images attached to post
  → Permissions: AllowAny
```

---

## Serializers

### User Serialization

```python
class UserSerializer(serializers.ModelSerializer):
    fields = ['id', 'username', 'first_name', 'last_name']
```

### Forum Category Serialization

```python
class ForumCategorySerializer(serializers.ModelSerializer):
    fields = [
        'id', 'name', 'description', 
        'topics_count', 'posts_count', 'last_activity'
    ]
    
    # Computed fields:
    topics_count = SerializerMethodField()
    posts_count = SerializerMethodField()
    last_activity = SerializerMethodField()
```

### Topic Serialization

**Simple Version** (for listings):
```python
class SimpleTopicSerializer:
    fields = [
        'id', 'subject', 'poster', 'forum', 'created',
        'posts_count', 'last_post_on', 'replies_count', 'views_count'
    ]
```

**Full Version** (for detail views):
```python
class TopicSerializer:
    fields = [
        'id', 'subject', 'poster', 'forum', 'created',
        'posts_count', 'last_post_on', 'last_poster',
        'replies_count', 'views_count'
    ]
    
    # Nested serializers:
    poster = UserSerializer()
    last_poster = SerializerMethodField()
```

### Post Serialization

```python
class PostSerializer:
    fields = [
        'id', 'topic', 'poster', 'content', 'created',
        'updated', 'approved'
    ]
    
    # Nested:
    poster = UserSerializer()
    topic = SimpleTopicSerializer()
```

### Create Serializers

```python
class CreateTopicSerializer:
    fields = ['subject', 'content', 'forum']
    
class CreatePostSerializer:
    fields = ['content', 'topic']
```

---

## Django Views (Simplified)

### Function-Based Views (`views.py`)

The implementation uses **simplified function-based views** instead of complex class-based views for better maintainability.

#### Key Views:

1. **`forum_index(request)`**
   - Lists all forum categories
   - Template: `forum_integration/forum_index_simple.html`

2. **`forum_category(request, forum_id)`**
   - Shows topics in a forum
   - Pagination: 25 topics per page
   - Template: `forum_integration/forum_category_simple.html`

3. **`forum_topic(request, topic_id)`**
   - Shows posts in a topic
   - Pagination: 10 posts per page
   - Template: `forum_integration/forum_topic_simple.html`

4. **`create_topic(request, forum_id)` [LOGIN REQUIRED]**
   - Create new topic form
   - Uses Django Machina's `PostForm`

**Design Decision**: Views temporarily bypass permission checks for debugging. This needs to be re-enabled for production.

---

## Django Machina Integration

### Core Machina Models Used

```python
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic, Post
```

#### Forum Model
- `type` field determines forum type (POST, LINK, CATEGORY)
- `Forum.FORUM_POST` = Standard post forum

#### Topic Model
- `subject` - Topic title
- `forum` - ForeignKey to Forum
- `poster` - Topic creator
- `approved` - Moderation status
- `posts_count` - Number of posts
- `views_count` - View tracking
- `last_post_on` - Last activity timestamp

#### Post Model
- `topic` - ForeignKey to Topic
- `poster` - Post author
- `content` - Post text content
- `approved` - Moderation status
- `created` / `updated` - Timestamps

### Permission System

Django Machina includes a sophisticated permission system:

```python
from machina.core.loading import get_class

PermissionHandler = get_class('forum_permission.handler', 'PermissionHandler')
perm_handler = PermissionHandler()

# Usage:
perm_handler.can_see_forum(forum, user)
perm_handler.can_read_forum(forum, user)
perm_handler.can_create_topic(forum, user)
```

**Migration Impact**: Need to ensure Firebase-authenticated users work with Machina permissions.

---

## Database Models Summary

### Custom Models (in `forum_integration/models.py`)

1. **ForumBasePage** (Abstract) - Wagtail page base
2. **ForumIndexPage** - Main forum page
3. **ForumCategoryPage** - Category pages
4. **ForumAnnouncementPage** - Announcements
5. **ForumModerationPage** - Moderation tools
6. **ForumAIUsage** - AI content tracking
7. **ForumPostImage** - Image attachments
8. **PostReaction** - Post reactions/likes
9. **PostTemplate** - Reusable post templates
10. **RichPost** - Enhanced post with rich content

### Django Machina Models (built-in)

- `Forum` - Forum categories
- `Topic` - Discussion topics
- `Post` - Forum posts/replies
- Many more (permissions, tracking, etc.)

---

## Migration Impact Analysis

### ✅ Keep (No Changes)

1. **All Django Machina forum functionality**
   - Topic creation, posting, replies
   - Moderation system
   - Permission system

2. **Wagtail CMS integration**
   - Page models
   - StreamField blocks
   - Admin interface

3. **Database schema**
   - All PostgreSQL tables
   - Relationships between models

### ➕ Add (New Features)

1. **REST API expansion for Flutter**
   - Read-only forum browsing
   - Topic viewing
   - Search functionality
   - User profile integration

2. **Firebase integration**
   - Firebase Auth → Django User mapping
   - Sync user profiles

3. **Mobile-specific features**
   - Push notifications for replies
   - Offline forum reading
   - Optimized images for mobile

### 🔄 Modify (Changes Needed)

1. **Authentication system**
   - Add Firebase authentication backend
   - Map Firebase UID to Django User
   - Update API authentication

2. **API permissions**
   - Ensure Firebase tokens work with DRF
   - Update permission classes

3. **Image handling**
   - Optimize for mobile upload/download
   - Consider Firebase Storage integration

### ❌ Remove (Deprecate)

1. **PWA-specific features** (if any in forum)
2. **React-specific integrations** (if moving to Wagtail templates)

---

## Templates Structure

```
forum_integration/templates/
├── forum_integration/
│   ├── forum_index_simple.html
│   ├── forum_category_simple.html
│   ├── forum_topic_simple.html
│   └── blocks/
│       ├── heading.html
│       ├── paragraph.html
│       ├── announcement.html
│       ├── rules.html
│       ├── moderator.html
│       ├── image.html
│       ├── cta.html
│       ├── statistics.html
│       └── plant_mention.html
```

**Migration Impact**: 
- Templates work with Django/Wagtail rendering
- May need API responses for Flutter app instead
- Consider headless approach (API-only)

---

## Static Assets

```
forum_integration/static/
└── (CSS, JavaScript for forum UI)
```

**Migration Impact**:
- Web app keeps static assets
- Flutter app has its own UI (no shared assets)

---

## Testing

```
forum_integration/tests/
└── (Test suite for forum functionality)
```

**Migration Impact**:
- Keep all existing tests
- Add API endpoint tests for mobile
- Add Firebase auth integration tests

---

## Key Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| `models.py` | 826 | Wagtail page models + custom models |
| `api_views.py` | 1,271 | Complete REST API (20+ endpoints) |
| `serializers.py` | 469 | DRF serializers for API |
| `views.py` | 214 | Simplified Django views |
| `admin.py` | ? | Django admin configuration |
| `wagtail_hooks.py` | ? | Wagtail customizations |
| `context_processors.py` | ? | Template context |
| `urls.py` | ? | URL routing |
| `api_urls.py` | ? | API URL routing |

**Total**: 2,780+ lines of custom forum code (excluding Django Machina itself!)

---

## Critical Design Decisions

### 1. Why Wagtail + Machina?

**Benefits**:
- ✅ Leverage Machina's battle-tested forum features
- ✅ Use Wagtail's CMS for flexible content management
- ✅ Best of both worlds

**Tradeoffs**:
- Complex integration layer
- Two systems to maintain
- Steeper learning curve

### 2. Flat StreamField Blocks

**User Requirement**: NO NESTED BLOCKS

**Rationale**: Simpler content management, easier to understand for non-technical users.

### 3. Simplified Views

**Decision**: Use function-based views instead of complex class-based views

**Benefits**:
- Easier to understand and debug
- Better performance
- Less abstraction

---

## Mobile App Integration Strategy

### Flutter App Access (Read-Only)

The Flutter app should have **read-only** access to forums:

✅ **Allowed**:
- Browse forum categories
- View topics
- Read posts
- Search forums
- View user profiles

❌ **Not Allowed** (use web app):
- Create new topics
- Post replies
- Edit posts
- Moderate content

**Rationale**: 
- Forums are better on larger screens
- Complex text editing on mobile is difficult
- Web app provides full forum experience
- Mobile app focuses on plant identification

### API Strategy

1. **Existing API**: Already has read-only endpoints
2. **Authentication**: Add Firebase token support
3. **Optimization**: Add mobile-specific response formats
4. **Caching**: Implement aggressive caching for mobile

---

## Next Steps for Migration

### Phase 1: Foundation (Weeks 1-2)

1. ✅ Document forum customizations (this document!)
2. ⏳ Add Firebase authentication backend
3. ⏳ Map Firebase UID to Django User
4. ⏳ Test API with Firebase tokens

### Phase 2: API Expansion (Weeks 3-4)

1. ⏳ Add mobile-optimized API endpoints
2. ⏳ Implement API caching
3. ⏳ Add search functionality
4. ⏳ Document API for Flutter team

### Phase 3: Flutter Integration (Weeks 5-6)

1. ⏳ Create Flutter forum UI
2. ⏳ Implement forum reading features
3. ⏳ Add search
4. ⏳ Test with real API

---

## Security Considerations

### Current Security

1. **CSRF Protection**: Django CSRF for web forms
2. **Authentication**: Django sessions + JWT
3. **Permissions**: Django Machina permission system
4. **XSS Protection**: Django template escaping

### Migration Security

1. **Firebase Auth**: Secure token validation
2. **API Rate Limiting**: Prevent abuse
3. **CORS Configuration**: Restrict origins
4. **Input Validation**: Sanitize all inputs

---

## Performance Considerations

### Current Optimizations

1. **Database Queries**:
   - `select_related()` for foreign keys
   - `prefetch_related()` for many-to-many
   - Pagination to limit result sets

2. **Caching**:
   - Redis for session storage
   - Query result caching

3. **Images**:
   - ImageKit for thumbnails
   - Lazy loading

### Mobile Optimizations Needed

1. **API Response Size**:
   - Minimize fields in responses
   - Compress images
   - Use pagination aggressively

2. **Network Efficiency**:
   - Cache forum data on device
   - Implement offline reading
   - Delta updates for topics

---

## Conclusion

The forum integration is a **sophisticated hybrid system** combining Django Machina's forum engine with Wagtail's CMS capabilities. It features:

- ✅ Complete REST API (1,271 lines)
- ✅ Custom Wagtail page models (826 lines)
- ✅ Flat StreamField architecture
- ✅ Plant-specific features (plant mentions)
- ✅ Moderation system
- ✅ Reaction system
- ✅ Image attachments

**For Migration**:
- **Keep all backend code intact**
- **Add Firebase authentication support**
- **Extend API for mobile read-only access**
- **Build Flutter UI for forum reading**
- **Keep web app for full forum participation**

**Status**: Forum Customizations Documentation Complete ✅  
**Next**: Database Schema Documentation 📋
