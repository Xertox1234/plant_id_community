# Forum API Reference

**Version**: 1.0
**Base URL**: `/api/v1/forum/`
**Date**: November 2, 2025
**Status**: Production Ready ✅

---

## Table of Contents

1. [Authentication](#authentication)
2. [Common Patterns](#common-patterns)
3. [Categories API](#categories-api)
4. [Threads API](#threads-api)
5. [Posts API](#posts-api)
6. [Reactions API](#reactions-api)
7. [User Profiles API](#user-profiles-api)
8. [Error Responses](#error-responses)

---

## Authentication

### JWT Token Authentication

All write operations (POST, PUT, PATCH, DELETE) require authentication via JWT token:

```http
Authorization: Bearer <your-jwt-token>
```

### Permission Levels

1. **Anonymous Users**: Read-only access to all public content
2. **Authenticated Users**: Can create posts, react to content
3. **Basic+ Trust Level**: Can create threads (not available to 'new' users)
4. **Moderators**: Can manage any content (staff users or 'Moderators' group)

### Trust Levels

- `new`: New members (cannot create threads)
- `basic`: Basic members (7+ days, 5+ posts)
- `trusted`: Trusted members (30+ days, 25+ posts)
- `veteran`: Veterans (90+ days, 100+ posts)
- `expert`: Experts (verified by admin)

---

## Common Patterns

### Pagination

All list endpoints support pagination with the following query parameters:

- `page`: Page number (default: 1)
- `page_size`: Items per page
  - Threads/Categories: default 25, max 100
  - Posts: default 20, max 50

**Paginated Response Format**:

```json
{
  "count": 150,
  "next": "http://api.example.com/api/v1/forum/threads/?page=2",
  "previous": null,
  "results": [...]
}
```

### Filtering

Most endpoints support filtering by:
- `is_active`: Include inactive items (default: `true`)
- Entity-specific filters documented per endpoint

### Ordering

Use `ordering` parameter with field names:
- Ascending: `?ordering=created_at`
- Descending: `?ordering=-created_at`
- Multiple: `?ordering=-is_pinned,-created_at`

### Search

Endpoints with search support use `search` parameter:
- `?search=plant+care` - Searches relevant fields

---

## Categories API

### List Categories

**Endpoint**: `GET /api/v1/forum/categories/`

**Description**: List all forum categories with optional hierarchy.

**Query Parameters**:
- `is_active` (bool): Filter active categories (default: `true`)
- `include_children` (bool): Include nested children (default: `false`)
- `page` (int): Page number
- `page_size` (int): Items per page (default: 25, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Plant Care",
      "slug": "plant-care",
      "description": "General plant care discussion and tips",
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
}
```

**With children** (`?include_children=true`):

```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
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
      "children": [
        {
          "id": "660e8400-e29b-41d4-a716-446655440001",
          "name": "Watering",
          "slug": "watering",
          "description": "How to water your plants",
          "parent": "550e8400-e29b-41d4-a716-446655440000",
          "parent_name": "Plant Care",
          "icon": "droplet",
          "display_order": 1,
          "is_active": true,
          "thread_count": 15,
          "post_count": 47,
          "children": null,
          "created_at": "2025-10-02T10:00:00Z",
          "updated_at": "2025-10-15T14:30:00Z"
        }
      ],
      "created_at": "2025-10-01T12:00:00Z",
      "updated_at": "2025-10-15T14:30:00Z"
    }
  ]
}
```

---

### Retrieve Category

**Endpoint**: `GET /api/v1/forum/categories/{slug}/`

**Description**: Get single category by slug with all details.

**URL Parameters**:
- `slug` (string): Category slug

**Permissions**: Public (AllowAny)

**Response** (200 OK): Same as list item format

**Response** (404 Not Found):

```json
{
  "detail": "Not found."
}
```

---

### Get Category Tree

**Endpoint**: `GET /api/v1/forum/categories/tree/`

**Description**: Get full category hierarchy with all descendants.

**Query Parameters**:
- `is_active` (bool): Filter active categories (default: `true`)

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
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
    "children": [
      {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "name": "Watering",
        "slug": "watering",
        "description": "How to water your plants",
        "parent": "550e8400-e29b-41d4-a716-446655440000",
        "parent_name": "Plant Care",
        "icon": "droplet",
        "display_order": 1,
        "is_active": true,
        "thread_count": 15,
        "post_count": 47,
        "children": [],
        "created_at": "2025-10-02T10:00:00Z",
        "updated_at": "2025-10-15T14:30:00Z"
      }
    ],
    "created_at": "2025-10-01T12:00:00Z",
    "updated_at": "2025-10-15T14:30:00Z"
  }
]
```

---

### Create Category

**Endpoint**: `POST /api/v1/forum/categories/`

**Description**: Create a new category.

**Permissions**: Moderators only (staff or 'Moderators' group)

**Request Body**:

```json
{
  "name": "Pest Control",
  "slug": "pest-control",
  "description": "Dealing with plant pests and diseases",
  "parent": "550e8400-e29b-41d4-a716-446655440000",
  "icon": "bug",
  "display_order": 5
}
```

**Response** (201 Created): Full category object

**Response** (403 Forbidden):

```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

### Update Category

**Endpoint**: `PATCH /api/v1/forum/categories/{slug}/`

**Description**: Update a category.

**Permissions**: Moderators only

**Request Body** (partial update):

```json
{
  "description": "Updated description",
  "display_order": 3
}
```

**Response** (200 OK): Full category object

---

### Delete Category

**Endpoint**: `DELETE /api/v1/forum/categories/{slug}/`

**Description**: Delete a category.

**Permissions**: Moderators only

**Response** (204 No Content)

**Note**: Deleting a category may affect threads in that category. Handle with care.

---

## Threads API

### List Threads

**Endpoint**: `GET /api/v1/forum/threads/`

**Description**: List all forum threads with pagination.

**Query Parameters**:
- `category` (slug): Filter by category slug
- `author` (username): Filter by author username
- `is_pinned` (bool): Filter pinned threads
- `is_locked` (bool): Filter locked threads
- `is_active` (bool): Include inactive threads (default: `true`)
- `search` (string): Search in thread title and excerpt
- `ordering` (string): Sort order (e.g., `-created_at`, `-last_activity_at`)
- `page` (int): Page number
- `page_size` (int): Items per page (default: 25, max: 100)

**Default Ordering**: Pinned first, then by last activity (newest first)

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
{
  "count": 150,
  "next": "http://api.example.com/api/v1/forum/threads/?page=2",
  "previous": null,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "title": "How often should I water succulents?",
      "slug": "how-often-water-succulents",
      "excerpt": "I'm new to succulents and wondering about watering frequency...",
      "author": {
        "id": 123,
        "username": "plant_lover",
        "display_name": "Plant Lover"
      },
      "category": {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "name": "Watering",
        "slug": "watering"
      },
      "is_pinned": false,
      "is_locked": false,
      "is_active": true,
      "view_count": 47,
      "post_count": 8,
      "created_at": "2025-10-30T14:30:00Z",
      "updated_at": "2025-10-31T09:15:00Z",
      "last_activity_at": "2025-10-31T09:15:00Z"
    }
  ]
}
```

---

### Retrieve Thread

**Endpoint**: `GET /api/v1/forum/threads/{slug}/`

**Description**: Get single thread with first post content. **Increments view count**.

**URL Parameters**:
- `slug` (string): Thread slug

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "title": "How often should I water succulents?",
  "slug": "how-often-water-succulents",
  "excerpt": "I'm new to succulents and wondering about watering frequency...",
  "author": {
    "id": 123,
    "username": "plant_lover",
    "display_name": "Plant Lover"
  },
  "category": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Watering",
    "slug": "watering"
  },
  "first_post": {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "content": "I just got my first succulent collection and I'm not sure how often to water them. I've heard different advice from different sources. What's the best practice?",
    "content_format": "markdown",
    "author": {
      "id": 123,
      "username": "plant_lover",
      "display_name": "Plant Lover"
    },
    "is_first_post": true,
    "created_at": "2025-10-30T14:30:00Z",
    "updated_at": "2025-10-30T14:30:00Z",
    "edited_at": null,
    "edited_by": null
  },
  "is_pinned": false,
  "is_locked": false,
  "is_active": true,
  "view_count": 48,
  "post_count": 8,
  "created_at": "2025-10-30T14:30:00Z",
  "updated_at": "2025-10-31T09:15:00Z",
  "last_activity_at": "2025-10-31T09:15:00Z"
}
```

---

### Create Thread

**Endpoint**: `POST /api/v1/forum/threads/`

**Description**: Create a new thread with first post (atomic operation).

**Permissions**:
- Authenticated users with trust_level != 'new'
- Creates both thread and first post in single transaction

**Request Body**:

```json
{
  "title": "Best soil for indoor plants?",
  "category": "plant-care",
  "first_post_content": "What type of soil do you recommend for indoor plants? I've been using regular potting soil but wondering if there's something better.",
  "content_format": "markdown"
}
```

**Request Fields**:
- `title` (string, required): Thread title (max 200 chars)
- `category` (slug, required): Category slug
- `first_post_content` (string, required): Content of first post (max 50,000 chars)
- `content_format` (string, optional): `plain`, `markdown`, or `rich` (default: `markdown`)

**Response** (201 Created): Full thread object with first post

**Response** (403 Forbidden) - New user:

```json
{
  "detail": "New users cannot create threads. Participate in discussions to increase your trust level."
}
```

**Response** (400 Bad Request):

```json
{
  "title": ["This field is required."],
  "category": ["Invalid category slug."]
}
```

---

### Update Thread

**Endpoint**: `PATCH /api/v1/forum/threads/{slug}/`

**Description**: Update thread details.

**Permissions**: Author or Moderator

**Request Body** (partial update):

```json
{
  "title": "Updated title",
  "category": "new-category-slug"
}
```

**Response** (200 OK): Full thread object

**Response** (403 Forbidden):

```json
{
  "detail": "You do not have permission to edit this thread."
}
```

---

### Delete Thread

**Endpoint**: `DELETE /api/v1/forum/threads/{slug}/`

**Description**: Soft delete a thread (sets `is_active=False`).

**Permissions**: Author or Moderator

**Response** (204 No Content)

---

### List Pinned Threads

**Endpoint**: `GET /api/v1/forum/threads/pinned/`

**Description**: Get all pinned threads across categories.

**Query Parameters**:
- `page` (int): Page number
- `page_size` (int): Items per page (default: 25, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK): Paginated list of pinned threads

---

### List Recent Threads

**Endpoint**: `GET /api/v1/forum/threads/recent/`

**Description**: Get threads with recent activity.

**Query Parameters**:
- `days` (int): Number of days to look back (default: 7, max: 365)
- `page` (int): Page number
- `page_size` (int): Items per page (default: 25, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK): Paginated list of recent threads

---

## Posts API

### List Posts

**Endpoint**: `GET /api/v1/forum/posts/`

**Description**: List posts in a thread (thread parameter **required**).

**Query Parameters**:
- `thread` (slug, **required**): Thread slug
- `author` (username): Filter by author username
- `is_active` (bool): Include inactive posts (default: `true`)
- `ordering` (string): Sort order (default: `created_at` - chronological)
- `page` (int): Page number
- `page_size` (int): Items per page (default: 20, max: 50)

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
{
  "count": 47,
  "next": "http://api.example.com/api/v1/forum/posts/?thread=my-thread-slug&page=2",
  "previous": null,
  "results": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "thread": {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "title": "How often should I water succulents?",
        "slug": "how-often-water-succulents"
      },
      "content": "Generally, succulents need water every 1-2 weeks in summer and every 3-4 weeks in winter. Check the soil - it should be completely dry before watering again.",
      "content_format": "markdown",
      "author": {
        "id": 456,
        "username": "succulent_expert",
        "display_name": "Succulent Expert"
      },
      "is_first_post": false,
      "is_active": true,
      "created_at": "2025-10-30T15:45:00Z",
      "updated_at": "2025-10-30T15:45:00Z",
      "edited_at": null,
      "edited_by": null,
      "reactions": [
        {
          "reaction_type": "helpful",
          "count": 5
        },
        {
          "reaction_type": "thanks",
          "count": 2
        }
      ],
      "attachments": []
    }
  ]
}
```

**Response** (400 Bad Request) - Missing thread parameter:

```json
{
  "error": "thread parameter is required for listing posts"
}
```

---

### Retrieve Post

**Endpoint**: `GET /api/v1/forum/posts/{id}/`

**Description**: Get single post by UUID.

**URL Parameters**:
- `id` (UUID): Post UUID

**Permissions**: Public (AllowAny)

**Response** (200 OK): Same as list item format

---

### Create Post

**Endpoint**: `POST /api/v1/forum/posts/`

**Description**: Create a new post in a thread.

**Permissions**: Authenticated users

**Request Body**:

```json
{
  "thread": "how-often-water-succulents",
  "content": "Great advice! I'll try the soil test method.",
  "content_format": "markdown"
}
```

**Request Fields**:
- `thread` (slug, required): Thread slug
- `content` (string, required): Post content (max 50,000 chars)
- `content_format` (string, optional): `plain`, `markdown`, or `rich` (default: `markdown`)

**Response** (201 Created): Full post object

**Response** (400 Bad Request) - Thread locked:

```json
{
  "error": "Cannot post in locked thread"
}
```

---

### Update Post

**Endpoint**: `PATCH /api/v1/forum/posts/{id}/`

**Description**: Update post content. Automatically sets `edited_at` and `edited_by`.

**Permissions**: Author or Moderator

**Request Body**:

```json
{
  "content": "Updated content with corrections"
}
```

**Response** (200 OK): Full post object with updated `edited_at` and `edited_by`

---

### Delete Post

**Endpoint**: `DELETE /api/v1/forum/posts/{id}/`

**Description**: Soft delete a post (sets `is_active=False`).

**Permissions**: Author or Moderator

**Response** (204 No Content)

**Note**: First posts cannot be deleted (delete the thread instead).

---

### List First Posts

**Endpoint**: `GET /api/v1/forum/posts/first_posts/`

**Description**: Get all thread starter posts.

**Query Parameters**:
- `category` (slug): Filter by category
- `page` (int): Page number
- `page_size` (int): Items per page (default: 20, max: 50)

**Permissions**: Public (AllowAny)

**Response** (200 OK): Paginated list of first posts

**Use Case**: Building thread previews with first post content

---

## Reactions API

### List Reactions

**Endpoint**: `GET /api/v1/forum/reactions/`

**Description**: List reactions on a post (post parameter **required**).

**Query Parameters**:
- `post` (UUID, **required**): Post UUID
- `reaction_type` (string): Filter by type (`like`, `love`, `helpful`, `thanks`)
- `user` (username): Filter by user who reacted
- `is_active` (bool): Include inactive reactions (default: `true`)

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "post": "880e8400-e29b-41d4-a716-446655440003",
    "user": {
      "id": 789,
      "username": "grateful_reader",
      "display_name": "Grateful Reader"
    },
    "reaction_type": "helpful",
    "is_active": true,
    "created_at": "2025-10-30T16:00:00Z"
  }
]
```

**Response** (400 Bad Request):

```json
{
  "error": "post parameter is required for listing reactions"
}
```

---

### Toggle Reaction

**Endpoint**: `POST /api/v1/forum/reactions/toggle/`

**Description**: Add or remove a reaction on a post.

**Permissions**: Authenticated users

**Request Body**:

```json
{
  "post": "880e8400-e29b-41d4-a716-446655440003",
  "reaction_type": "helpful"
}
```

**Request Fields**:
- `post` (UUID, required): Post UUID
- `reaction_type` (string, required): One of `like`, `love`, `helpful`, `thanks`

**Response** (200 OK) - Reaction added:

```json
{
  "action": "created",
  "reaction": {
    "id": "aa0e8400-e29b-41d4-a716-446655440005",
    "post": "880e8400-e29b-41d4-a716-446655440003",
    "user": {
      "id": 123,
      "username": "plant_lover",
      "display_name": "Plant Lover"
    },
    "reaction_type": "helpful",
    "is_active": true,
    "created_at": "2025-10-31T10:00:00Z"
  }
}
```

**Response** (200 OK) - Reaction removed:

```json
{
  "action": "deactivated",
  "reaction": {
    "id": "aa0e8400-e29b-41d4-a716-446655440005",
    "is_active": false
  }
}
```

**Response** (200 OK) - Reaction reactivated:

```json
{
  "action": "reactivated",
  "reaction": {
    "id": "aa0e8400-e29b-41d4-a716-446655440005",
    "is_active": true
  }
}
```

---

### Aggregate Reactions

**Endpoint**: `GET /api/v1/forum/reactions/aggregate/`

**Description**: Get reaction counts and user's reactions on a post.

**Query Parameters**:
- `post` (UUID, **required**): Post UUID

**Permissions**: Public (AllowAny for counts, user_reactions requires authentication)

**Response** (200 OK) - Authenticated user:

```json
{
  "counts": {
    "like": 12,
    "love": 3,
    "helpful": 8,
    "thanks": 5
  },
  "user_reactions": ["helpful", "thanks"]
}
```

**Response** (200 OK) - Anonymous user:

```json
{
  "counts": {
    "like": 12,
    "love": 3,
    "helpful": 8,
    "thanks": 5
  },
  "user_reactions": []
}
```

---

## User Profiles API

### List User Profiles

**Endpoint**: `GET /api/v1/forum/profiles/`

**Description**: List user profiles (leaderboard format).

**Query Parameters**:
- `trust_level` (string): Filter by trust level
- `ordering` (string): Sort order (default: `-helpful_count`)
- `page` (int): Page number
- `page_size` (int): Items per page (default: 25, max: 100)

**Default Ordering**: Most helpful users first

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
{
  "count": 500,
  "next": "http://api.example.com/api/v1/forum/profiles/?page=2",
  "previous": null,
  "results": [
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440006",
      "user": {
        "id": 456,
        "username": "succulent_expert",
        "display_name": "Succulent Expert"
      },
      "trust_level": "veteran",
      "trust_level_display": "Veteran",
      "post_count": 234,
      "helpful_count": 89,
      "created_at": "2025-06-15T10:00:00Z",
      "updated_at": "2025-10-31T09:00:00Z"
    }
  ]
}
```

---

### Retrieve User Profile

**Endpoint**: `GET /api/v1/forum/profiles/{user_id}/`

**Description**: Get profile by user ID.

**URL Parameters**:
- `user_id` (int): User ID (NOT profile UUID)

**Permissions**: Public (AllowAny)

**Response** (200 OK): Same as list item format

---

### Top Contributors

**Endpoint**: `GET /api/v1/forum/profiles/top_contributors/`

**Description**: Get users with most posts.

**Query Parameters**:
- `limit` (int): Number of users (default: 10, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK):

```json
[
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440006",
    "user": {
      "id": 456,
      "username": "succulent_expert",
      "display_name": "Succulent Expert"
    },
    "trust_level": "veteran",
    "trust_level_display": "Veteran",
    "post_count": 234,
    "helpful_count": 89,
    "created_at": "2025-06-15T10:00:00Z",
    "updated_at": "2025-10-31T09:00:00Z"
  }
]
```

---

### Most Helpful

**Endpoint**: `GET /api/v1/forum/profiles/most_helpful/`

**Description**: Get users with most 'helpful' reactions.

**Query Parameters**:
- `limit` (int): Number of users (default: 10, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK): Same as top contributors format

---

### Veterans

**Endpoint**: `GET /api/v1/forum/profiles/veterans/`

**Description**: Get users with veteran or expert trust level.

**Query Parameters**:
- `page` (int): Page number
- `page_size` (int): Items per page (default: 25, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK): Paginated list of veteran/expert users

---

### New Members

**Endpoint**: `GET /api/v1/forum/profiles/new_members/`

**Description**: Get recently joined users.

**Query Parameters**:
- `limit` (int): Number of users (default: 10, max: 100)

**Permissions**: Public (AllowAny)

**Response** (200 OK): List of newest users (ordered by `created_at` descending)

---

## Error Responses

### Standard Error Format

All errors follow Django REST Framework's standard format:

```json
{
  "detail": "Error message"
}
```

Or for field-specific errors:

```json
{
  "field_name": ["Error message for this field"],
  "another_field": ["Another error message"]
}
```

### Common HTTP Status Codes

- `200 OK`: Successful GET, PUT, PATCH
- `201 Created`: Successful POST
- `204 No Content`: Successful DELETE
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource doesn't exist
- `405 Method Not Allowed`: HTTP method not supported
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server-side error

### Permission Error Examples

**Not authenticated**:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

**Insufficient permissions**:

```json
{
  "detail": "You do not have permission to perform this action."
}
```

**New user creating thread**:

```json
{
  "detail": "New users cannot create threads. Participate in discussions to increase your trust level."
}
```

---

## Rate Limiting

API endpoints are protected by rate limiting:

- **Anonymous users**: 100 requests/hour
- **Authenticated users**: 1000 requests/hour
- **Moderators**: 5000 requests/hour

When rate limit is exceeded:

```json
{
  "detail": "Request was throttled. Expected available in 1800 seconds."
}
```

---

## Testing Endpoints

### Using cURL

```bash
# Get categories
curl -X GET http://localhost:8000/api/v1/forum/categories/

# Get threads in category
curl -X GET "http://localhost:8000/api/v1/forum/threads/?category=plant-care"

# Create thread (authenticated)
curl -X POST http://localhost:8000/api/v1/forum/threads/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Thread",
    "category": "plant-care",
    "first_post_content": "Test post content"
  }'

# Toggle reaction (authenticated)
curl -X POST http://localhost:8000/api/v1/forum/reactions/toggle/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "post": "880e8400-e29b-41d4-a716-446655440003",
    "reaction_type": "helpful"
  }'
```

### Using Python Requests

```python
import requests

BASE_URL = "http://localhost:8000/api/v1/forum"
TOKEN = "your_jwt_token_here"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# List threads
response = requests.get(f"{BASE_URL}/threads/")
threads = response.json()

# Create post
response = requests.post(
    f"{BASE_URL}/posts/",
    headers=HEADERS,
    json={
        "thread": "my-thread-slug",
        "content": "Great discussion!"
    }
)
new_post = response.json()
```

---

## Best Practices

### Pagination

1. Always handle paginated responses in loops:

```javascript
async function getAllThreads() {
  let allThreads = [];
  let url = '/api/v1/forum/threads/';

  while (url) {
    const response = await fetch(url);
    const data = await response.json();
    allThreads = allThreads.concat(data.results);
    url = data.next;  // null when no more pages
  }

  return allThreads;
}
```

### Error Handling

2. Always check response status before parsing:

```javascript
async function createThread(data) {
  const response = await fetch('/api/v1/forum/threads/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create thread');
  }

  return await response.json();
}
```

### Caching

3. Cache frequently accessed data (categories, pinned threads):

- Categories change infrequently, cache for 24 hours
- Pinned threads cache for 1 hour
- Thread lists cache for 6 hours
- Thread details cache for 1 hour

### Optimistic Updates

4. Use optimistic UI updates for reactions:

```javascript
// Update UI immediately
updateReactionCount(postId, reactionType, +1);

try {
  await toggleReaction(postId, reactionType);
} catch (error) {
  // Revert on failure
  updateReactionCount(postId, reactionType, -1);
  showError('Failed to update reaction');
}
```

---

## Changelog

### Version 1.0 (November 2, 2025)

- Initial API release
- Full CRUD operations for categories, threads, posts
- Reaction system with toggle endpoint
- User profile leaderboards
- Trust level-based permissions
- Comprehensive pagination support

---

## Support

For API issues or questions:

- **GitHub Issues**: https://github.com/Xertox1234/plant_id_community/issues
- **Documentation**: `/backend/docs/forum/`
- **Testing Guide**: `/backend/apps/forum/docs/TESTING.md`

---

**End of API Reference**
