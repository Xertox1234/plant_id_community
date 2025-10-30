# Forum Phase 2c Recommendations

**Source**: Code Review for Phase 2b (ViewSets Layer)
**Date**: October 30, 2025
**Status**: Phase 2a (Serializers) ✅ Grade A+ (100/100), Phase 2b (ViewSets) ✅ Grade A+ (100/100)

---

## Overview

Phase 2c completes the forum API implementation by adding:
1. **Permissions Layer** - Trust level-based access control
2. **URL Configuration** - DRF router with RESTful endpoints
3. **Comprehensive Testing** - Full test coverage for all ViewSets
4. **API Documentation** - Endpoint reference guide (optional)

---

## 1. Permissions Layer (High Priority)

### Recommended Permission Classes

Create `backend/apps/forum/permissions.py` with the following permission classes:

#### 1.1 IsAuthorOrReadOnly

```python
from rest_framework import permissions

class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Allow authors to edit/delete their own content.

    Read-only access for all users.
    Write access only for the author.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions (GET, HEAD, OPTIONS) allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for the author
        return obj.author == request.user
```

**Apply to**:
- ThreadViewSet (update/delete own threads)
- PostViewSet (update/delete own posts)

#### 1.2 IsModerator

```python
class IsModerator(permissions.BasePermission):
    """
    Allow moderators to manage any content.

    Moderators are:
    - Staff users (is_staff=True)
    - Members of 'Moderators' group
    """

    def has_permission(self, request, view):
        # Check if user is staff or in Moderators group
        return (
            request.user.is_staff or
            request.user.groups.filter(name='Moderators').exists()
        )
```

**Apply to**:
- CategoryViewSet (create/update/delete categories)
- ThreadViewSet (lock/pin threads, delete any thread)
- PostViewSet (delete any post)

#### 1.3 CanCreateThread

```python
class CanCreateThread(permissions.BasePermission):
    """
    Require minimum trust level to create threads.

    New users (trust_level='new') cannot create threads to prevent spam.
    """

    def has_permission(self, request, view):
        # Allow all non-POST requests
        if request.method != 'POST':
            return True

        # Require authenticated user with profile
        if not request.user.is_authenticated:
            return False

        # Check trust level (new users cannot create threads)
        try:
            profile = request.user.forum_profile
            return profile.trust_level != 'new'
        except AttributeError:
            # No forum profile, deny permission
            return False
```

**Apply to**:
- ThreadViewSet (create action only)

### Permission Application Strategy

#### ThreadViewSet

```python
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from ..permissions import IsAuthorOrReadOnly, IsModerator, CanCreateThread

class ThreadViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """Dynamic permissions based on action."""
        if self.action == 'create':
            # Creating threads requires minimum trust level
            return [CanCreateThread()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Editing requires being author OR moderator
            return [IsAuthorOrReadOnly() | IsModerator()]
        return [IsAuthenticatedOrReadOnly()]
```

#### PostViewSet

```python
class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """Dynamic permissions based on action."""
        if self.action in ['update', 'partial_update', 'destroy']:
            # Editing requires being author OR moderator
            return [IsAuthorOrReadOnly() | IsModerator()]
        return [IsAuthenticatedOrReadOnly()]
```

#### CategoryViewSet

```python
class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """Dynamic permissions based on action."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Managing categories requires moderator
            return [IsModerator()]
        return [IsAuthenticatedOrReadOnly()]
```

---

## 2. URL Configuration (High Priority)

### Create Router Configuration

**File**: `backend/apps/forum/urls.py`

```python
"""
Forum API URL configuration.

Registers all forum ViewSets with DRF router.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    CategoryViewSet,
    ThreadViewSet,
    PostViewSet,
    ReactionViewSet,
    UserProfileViewSet,
)

app_name = 'forum'

# Create router and register ViewSets
router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('threads', ThreadViewSet, basename='thread')
router.register('posts', PostViewSet, basename='post')
router.register('reactions', ReactionViewSet, basename='reaction')
router.register('profiles', UserProfileViewSet, basename='userprofile')

urlpatterns = [
    path('', include(router.urls)),
]
```

### Register in Main URLs

**File**: `backend/plant_community_backend/urls.py`

Add to existing urlpatterns:

```python
urlpatterns = [
    # ... existing patterns ...
    path('api/v1/forum/', include('apps.forum.urls')),
]
```

### Expected API Endpoints

After router registration, the following endpoints will be available:

#### Categories
- `GET /api/v1/forum/categories/` - List all categories
- `POST /api/v1/forum/categories/` - Create category (moderator only)
- `GET /api/v1/forum/categories/{slug}/` - Retrieve category
- `PATCH /api/v1/forum/categories/{slug}/` - Update category (moderator only)
- `DELETE /api/v1/forum/categories/{slug}/` - Delete category (moderator only)
- `GET /api/v1/forum/categories/tree/` - Get full category tree

#### Threads
- `GET /api/v1/forum/threads/` - List threads
- `POST /api/v1/forum/threads/` - Create thread (requires trust level)
- `GET /api/v1/forum/threads/{slug}/` - Retrieve thread (increments view count)
- `PATCH /api/v1/forum/threads/{slug}/` - Update thread (author or moderator)
- `DELETE /api/v1/forum/threads/{slug}/` - Delete thread (author or moderator)
- `GET /api/v1/forum/threads/pinned/` - List pinned threads
- `GET /api/v1/forum/threads/recent/?days=7` - List recent threads

#### Posts
- `GET /api/v1/forum/posts/?thread={slug}` - List posts in thread (required param)
- `POST /api/v1/forum/posts/` - Create post
- `GET /api/v1/forum/posts/{id}/` - Retrieve post
- `PATCH /api/v1/forum/posts/{id}/` - Update post (author or moderator)
- `DELETE /api/v1/forum/posts/{id}/` - Soft delete post (author or moderator)
- `GET /api/v1/forum/posts/first_posts/` - List thread starter posts

#### Reactions
- `GET /api/v1/forum/reactions/?post={uuid}` - List reactions on post (required param)
- `POST /api/v1/forum/reactions/toggle/` - Toggle reaction (add/remove)
- `GET /api/v1/forum/reactions/aggregate/?post={uuid}` - Get reaction counts

#### User Profiles
- `GET /api/v1/forum/profiles/` - List user profiles (leaderboard)
- `GET /api/v1/forum/profiles/{user_id}/` - Retrieve user profile
- `GET /api/v1/forum/profiles/top_contributors/?limit=10` - Top contributors
- `GET /api/v1/forum/profiles/most_helpful/?limit=10` - Most helpful users
- `GET /api/v1/forum/profiles/veterans/` - Veteran/expert users
- `GET /api/v1/forum/profiles/new_members/?limit=10` - Recently joined

---

## 3. Testing Strategy (High Priority)

### Test Structure

Create comprehensive test coverage in `backend/apps/forum/tests/`:

```
tests/
├── __init__.py
├── test_category_viewset.py      # CategoryViewSet tests
├── test_thread_viewset.py        # ThreadViewSet tests
├── test_post_viewset.py          # PostViewSet tests
├── test_reaction_viewset.py      # ReactionViewSet tests
├── test_user_profile_viewset.py  # UserProfileViewSet tests
└── test_permissions.py           # Permission class tests
```

### Key Test Cases by ViewSet

#### test_category_viewset.py

```python
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

class CategoryViewSetTests(TestCase):
    """Test CategoryViewSet endpoints."""

    def setUp(self):
        self.client = APIClient()
        # Create test data

    def test_list_categories_flat(self):
        """List categories without children."""

    def test_list_categories_with_children(self):
        """List categories with include_children=true."""

    def test_retrieve_single_category(self):
        """Retrieve single category by slug."""

    def test_tree_action_returns_hierarchy(self):
        """Tree action returns full category hierarchy."""

    def test_prefetching_children_works(self):
        """Verify children are prefetched (no N+1)."""

    def test_active_inactive_filtering(self):
        """Filter by is_active parameter."""

    def test_create_category_requires_moderator(self):
        """Creating category requires moderator permission."""

    def test_update_category_requires_moderator(self):
        """Updating category requires moderator permission."""
```

#### test_thread_viewset.py

```python
class ThreadViewSetTests(TestCase):
    """Test ThreadViewSet endpoints."""

    def test_list_threads_pagination(self):
        """List threads with pagination."""

    def test_retrieve_thread_increments_view_count(self):
        """Retrieving thread increments view_count."""

    def test_create_thread_with_first_post_atomic(self):
        """Creating thread creates first post atomically."""

    def test_create_thread_requires_trust_level(self):
        """New users cannot create threads."""

    def test_update_thread_requires_author_or_moderator(self):
        """Only author or moderator can update thread."""

    def test_delete_thread_requires_author_or_moderator(self):
        """Only author or moderator can delete thread."""

    def test_pinned_threads_action(self):
        """Pinned action returns only pinned threads."""

    def test_recent_threads_action_with_days_parameter(self):
        """Recent action filters by days parameter."""

    def test_filter_by_category_slug(self):
        """Filter threads by category slug."""

    def test_filter_by_author_username(self):
        """Filter threads by author username."""

    def test_filter_by_is_pinned(self):
        """Filter by is_pinned parameter."""

    def test_filter_by_is_locked(self):
        """Filter by is_locked parameter."""

    def test_search_in_title_and_excerpt(self):
        """Search functionality works."""
```

#### test_post_viewset.py

```python
class PostViewSetTests(TestCase):
    """Test PostViewSet endpoints."""

    def test_list_posts_requires_thread_parameter(self):
        """List posts without thread param returns 400."""

    def test_list_posts_in_thread(self):
        """List posts filtered by thread slug."""

    def test_create_post_in_thread(self):
        """Create new post in thread."""

    def test_update_post_marks_as_edited(self):
        """Updating post sets edited_at and edited_by."""

    def test_update_post_requires_author_or_moderator(self):
        """Only author or moderator can update post."""

    def test_delete_post_soft_deletes(self):
        """Deleting post sets is_active=False (not hard delete)."""

    def test_delete_post_requires_author_or_moderator(self):
        """Only author or moderator can delete post."""

    def test_first_posts_action(self):
        """First posts action returns only thread starters."""

    def test_filter_by_author_username(self):
        """Filter posts by author username."""

    def test_prefetch_reactions_and_attachments(self):
        """Reactions and attachments are prefetched (no N+1)."""
```

#### test_reaction_viewset.py

```python
class ReactionViewSetTests(TestCase):
    """Test ReactionViewSet endpoints."""

    def test_list_reactions_requires_post_parameter(self):
        """List reactions without post param returns 400."""

    def test_list_reactions_on_post(self):
        """List reactions filtered by post UUID."""

    def test_toggle_reaction_adds_if_not_exists(self):
        """Toggle creates reaction if doesn't exist."""

    def test_toggle_reaction_removes_if_exists(self):
        """Toggle deactivates reaction if exists (toggle twice)."""

    def test_toggle_reaction_requires_authentication(self):
        """Toggle requires authenticated user."""

    def test_aggregate_returns_counts_and_user_reactions(self):
        """Aggregate returns counts dict and user_reactions list."""

    def test_aggregate_requires_post_parameter(self):
        """Aggregate without post param returns 400."""

    def test_filter_by_reaction_type(self):
        """Filter reactions by type."""

    def test_filter_by_is_active(self):
        """Filter by is_active parameter."""
```

#### test_user_profile_viewset.py

```python
class UserProfileViewSetTests(TestCase):
    """Test UserProfileViewSet endpoints."""

    def test_list_profiles_leaderboard(self):
        """List profiles ordered by helpful_count."""

    def test_retrieve_by_user_id(self):
        """Retrieve profile by user_id (not profile id)."""

    def test_top_contributors_action(self):
        """Top contributors ordered by post_count."""

    def test_top_contributors_respects_limit(self):
        """Top contributors limit parameter works (max 100)."""

    def test_most_helpful_action(self):
        """Most helpful ordered by helpful_count."""

    def test_most_helpful_respects_limit(self):
        """Most helpful limit parameter works (max 100)."""

    def test_veterans_action(self):
        """Veterans action returns veteran/expert users only."""

    def test_new_members_action(self):
        """New members ordered by created_at (newest first)."""

    def test_new_members_respects_limit(self):
        """New members limit parameter works (max 100)."""

    def test_filter_by_trust_level(self):
        """Filter profiles by trust_level parameter."""

    def test_public_access_allowed(self):
        """Profiles are publicly accessible (AllowAny)."""
```

#### test_permissions.py

```python
class PermissionTests(TestCase):
    """Test permission classes."""

    def test_is_author_or_read_only_allows_read(self):
        """IsAuthorOrReadOnly allows read for anyone."""

    def test_is_author_or_read_only_allows_author_write(self):
        """IsAuthorOrReadOnly allows author to write."""

    def test_is_author_or_read_only_denies_non_author_write(self):
        """IsAuthorOrReadOnly denies non-author write."""

    def test_is_moderator_allows_staff(self):
        """IsModerator allows staff users."""

    def test_is_moderator_allows_moderators_group(self):
        """IsModerator allows users in Moderators group."""

    def test_is_moderator_denies_regular_users(self):
        """IsModerator denies regular users."""

    def test_can_create_thread_allows_basic_users(self):
        """CanCreateThread allows users with trust_level != 'new'."""

    def test_can_create_thread_denies_new_users(self):
        """CanCreateThread denies users with trust_level == 'new'."""

    def test_can_create_thread_denies_unauthenticated(self):
        """CanCreateThread denies anonymous users."""
```

### Test Execution

Run tests with:

```bash
# All forum tests
python manage.py test apps.forum.tests --keepdb -v 2

# Specific test file
python manage.py test apps.forum.tests.test_thread_viewset --keepdb -v 2

# With coverage
coverage run --source='apps.forum' manage.py test apps.forum.tests
coverage report
coverage html
```

---

## 4. Integration with Cache Service (Medium Priority)

### Verify Cache Invalidation

**Note**: ViewSets correctly don't call cache directly - signals handle invalidation.

Test that signals properly invalidate caches:

1. **Creating thread** → invalidates thread list cache
2. **Updating thread** → invalidates thread detail cache
3. **Creating post** → invalidates thread detail cache (post count changes)
4. **Reactions** → don't invalidate thread cache (separate entity)

Create integration test:

```python
class CacheIntegrationTests(TestCase):
    """Test cache invalidation via signals."""

    def test_creating_thread_invalidates_cache(self):
        """Creating thread invalidates thread list cache."""

    def test_updating_thread_invalidates_cache(self):
        """Updating thread invalidates thread detail cache."""

    def test_creating_post_invalidates_thread_cache(self):
        """Creating post invalidates thread cache (post_count)."""
```

---

## 5. API Documentation (Optional)

### Create Endpoint Reference

**File**: `backend/docs/forum/API_REFERENCE.md`

Document all endpoints with:
- Request/response examples
- Query parameters
- Error responses
- Authentication requirements

Example structure:

```markdown
# Forum API Reference

## Authentication

All write operations require authentication via JWT token:

```
Authorization: Bearer <token>
```

## Categories

### List Categories

**Endpoint**: `GET /api/v1/forum/categories/`

**Query Parameters**:
- `is_active` (bool): Filter active categories (default: true)
- `include_children` (bool): Include nested children (default: false)

**Response** (200 OK):
```json
[
  {
    "id": "uuid",
    "name": "Plant Care",
    "slug": "plant-care",
    "description": "General plant care discussion",
    "parent": null,
    "parent_name": null,
    "icon": "leaf",
    "display_order": 1,
    "is_active": true,
    "thread_count": 42,
    "post_count": 156,
    "children": null,
    "created_at": "2025-10-01T12:00:00Z",
    "updated_at": "2025-10-15T14:30:00Z"
  }
]
```

(Continue for all endpoints...)
```

---

## 6. Pagination Configuration (Recommended)

### Create Custom Pagination Class

**File**: `backend/apps/forum/pagination.py`

```python
from rest_framework.pagination import PageNumberPagination

class ForumPagination(PageNumberPagination):
    """
    Custom pagination for forum endpoints.

    Uses constants from forum.constants for consistency.
    """
    page_size = 25  # Default threads/posts per page
    page_size_query_param = 'page_size'
    max_page_size = 100  # Maximum allowed page size
```

### Apply to ViewSets

```python
from .pagination import ForumPagination

class ThreadViewSet(viewsets.ModelViewSet):
    pagination_class = ForumPagination
    # ...
```

---

## 7. Production Deployment Checklist

Before deploying to production:

- [ ] All permissions implemented and tested
- [ ] URL configuration registered in main urls.py
- [ ] Comprehensive test suite passing (6 test modules)
- [ ] Cache invalidation verified via integration tests
- [ ] API documentation created (optional but recommended)
- [ ] Custom pagination configured
- [ ] Rate limiting configured (global settings)
- [ ] CORS settings updated for frontend origin
- [ ] Database migrations applied
- [ ] Static files collected
- [ ] Environment variables set (SECRET_KEY, etc.)

---

## Phase 2c Implementation Checklist

### Step 1: Permissions (High Priority)

- [ ] Create `backend/apps/forum/permissions.py`
- [ ] Implement `IsAuthorOrReadOnly` permission
- [ ] Implement `IsModerator` permission
- [ ] Implement `CanCreateThread` permission
- [ ] Apply permissions to CategoryViewSet
- [ ] Apply permissions to ThreadViewSet
- [ ] Apply permissions to PostViewSet
- [ ] Test all permission scenarios

### Step 2: URL Configuration (High Priority)

- [ ] Create `backend/apps/forum/urls.py`
- [ ] Register all ViewSets with DefaultRouter
- [ ] Add forum URLs to main urls.py
- [ ] Verify all endpoints are accessible
- [ ] Test URL routing

### Step 3: Testing (High Priority)

- [ ] Create `tests/test_category_viewset.py` (10+ tests)
- [ ] Create `tests/test_thread_viewset.py` (12+ tests)
- [ ] Create `tests/test_post_viewset.py` (10+ tests)
- [ ] Create `tests/test_reaction_viewset.py` (8+ tests)
- [ ] Create `tests/test_user_profile_viewset.py` (11+ tests)
- [ ] Create `tests/test_permissions.py` (9+ tests)
- [ ] All tests passing (60+ total tests)
- [ ] Coverage report > 90%

### Step 4: Optional Enhancements

- [ ] Create custom pagination class
- [ ] Create API documentation
- [ ] Add cache integration tests
- [ ] Configure rate limiting

### Step 5: Code Review

- [ ] Call code-review-specialist
- [ ] Address any issues found
- [ ] Achieve Grade A+ (95-100)

---

## Estimated Timeline

- **Permissions**: 2-3 hours
- **URL Configuration**: 30 minutes
- **Testing**: 6-8 hours (60+ comprehensive tests)
- **Documentation**: 1-2 hours (optional)
- **Code Review & Fixes**: 1-2 hours

**Total**: 10-16 hours for complete Phase 2c

---

## Success Criteria

Phase 2c is complete when:

1. ✅ All 3 permission classes implemented and working
2. ✅ URL configuration registered and all endpoints accessible
3. ✅ 60+ comprehensive tests passing with >90% coverage
4. ✅ Code review grade A+ (95-100)
5. ✅ Production deployment checklist complete
6. ✅ Integration with Phase 1 (models) and Phase 2a/2b (serializers/viewsets) verified

---

## References

- **Phase 1 Documentation**: `/backend/docs/forum/PHASE_1_FOUNDATION_COMPLETE.md`
- **Phase 2a Code Review**: Serializers Grade A+ (100/100)
- **Phase 2b Code Review**: ViewSets Grade A+ (100/100)
- **Django REST Framework**: https://www.django-rest-framework.org/
- **DRF Permissions**: https://www.django-rest-framework.org/api-guide/permissions/
- **DRF Testing**: https://www.django-rest-framework.org/api-guide/testing/
