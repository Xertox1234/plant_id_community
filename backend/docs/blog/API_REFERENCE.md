# Blog API Reference

**Date**: October 24, 2025
**Status**: Production Ready
**Base URL**: `http://localhost:8000/api/v2/`
**Authentication**: Not required for public content (configurable)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Common Parameters](#common-parameters)
4. [Endpoints](#endpoints)
   - [Blog Posts](#blog-posts)
   - [Blog Index](#blog-index)
   - [Categories](#categories)
   - [Authors](#authors)
   - [Images](#images)
   - [Feeds](#feeds)
5. [Response Format](#response-format)
6. [Error Handling](#error-handling)
7. [Performance](#performance)
8. [Examples](#examples)

---

## Overview

The Wagtail Blog API provides headless CMS functionality for consuming blog content in React/Flutter applications. All endpoints follow Wagtail API v2 conventions with custom extensions for blog-specific features.

### Key Features

- **Headless CMS**: Full API access to blog content
- **StreamField Support**: Rich content blocks (12+ types)
- **Image Renditions**: Automatic image optimization
- **Redis Caching**: <50ms cached responses, 24h TTL
- **Query Optimization**: <20 queries for lists, 19 queries for details
- **Search Integration**: Full-text search with Wagtail Query tracking
- **RSS/Atom Feeds**: Standard feed formats

---

## Authentication

**Current**: No authentication required for public content
**Future**: JWT token authentication for draft/preview access

```http
Authorization: Bearer <jwt_token>
```

**Note**: Preview endpoints require authentication (see [Headless Preview](#headless-preview))

---

## Common Parameters

### Pagination

All list endpoints support pagination:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Number of results per page (max: 100) |
| `offset` | integer | 0 | Number of results to skip |

**Example**:
```http
GET /api/v2/blog-posts/?limit=10&offset=20
```

### Field Selection

Limit response fields for better performance:

| Parameter | Type | Description |
|-----------|------|-------------|
| `fields` | string (comma-separated) | Fields to include in response |

**Example**:
```http
GET /api/v2/blog-posts/?fields=title,slug,publish_date,author
```

### Ordering

Sort results by field:

| Parameter | Type | Description |
|-----------|------|-------------|
| `order` | string | Field name (prefix with `-` for descending) |

**Built-in Aliases**:
- `newest` → `-first_published_at`
- `oldest` → `first_published_at`
- `title` → `title`
- `popular` → `-views_count` (if enabled)

**Example**:
```http
GET /api/v2/blog-posts/?order=newest
GET /api/v2/blog-posts/?order=-publish_date
```

### Search

Full-text search across titles and content:

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Search query |

**Example**:
```http
GET /api/v2/blog-posts/?search=orchid+care
```

---

## Endpoints

### Blog Posts

#### List Blog Posts

```http
GET /api/v2/blog-posts/
```

**Query Parameters**:

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `category` | integer | Filter by category ID | `?category=1` |
| `category_slug` | string | Filter by category slug | `?category_slug=plant-care` |
| `author` | integer | Filter by author user ID | `?author=5` |
| `author_username` | string | Filter by author username | `?author_username=jane` |
| `series` | integer | Filter by series ID | `?series=2` |
| `series_slug` | string | Filter by series slug | `?series_slug=beginner-guide` |
| `tag` | string | Filter by tag name (case-insensitive) | `?tag=succulents` |
| `difficulty` | string | Filter by difficulty level | `?difficulty=easy` |
| `featured` | boolean | Show only featured posts | `?featured=true` |
| `date_from` | date (YYYY-MM-DD) | Posts published after this date | `?date_from=2025-01-01` |
| `date_to` | date (YYYY-MM-DD) | Posts published before this date | `?date_to=2025-12-31` |
| `plant_species` | integer | Posts related to plant species ID | `?plant_species=42` |

**Response**:
```json
{
  "meta": {
    "total_count": 25
  },
  "items": [
    {
      "id": 10,
      "title": "Getting Started with Indoor Plants",
      "slug": "getting-started-indoor-plants",
      "url": "/blog/getting-started-indoor-plants/",
      "author": {
        "id": 5,
        "username": "jane",
        "display_name": "Jane Smith"
      },
      "publish_date": "2025-10-15",
      "categories": [
        {
          "id": 1,
          "name": "Plant Care",
          "slug": "plant-care",
          "color": "#4CAF50",
          "icon": "🌿"
        }
      ],
      "tags": ["beginner", "indoor", "easy"],
      "featured_image_thumb": "https://example.com/media/images/plant_fill-300x200.jpg",
      "is_featured": true,
      "reading_time": 5,
      "difficulty_level": "easy",
      "excerpt": "Learn the basics of caring for indoor plants with this comprehensive beginner's guide...",
      "comment_count": 12
    }
  ]
}
```

**Performance**:
- Cached: <50ms
- Cold: ~300ms (5-8 queries)
- Cache TTL: 24 hours

---

#### Get Blog Post Detail

```http
GET /api/v2/blog-posts/{id}/
```

**Path Parameters**:
- `id` (integer, required): Blog post ID

**Response**:
```json
{
  "id": 10,
  "title": "Getting Started with Indoor Plants",
  "slug": "getting-started-indoor-plants",
  "url": "/blog/getting-started-indoor-plants/",
  "author": {
    "id": 5,
    "username": "jane",
    "first_name": "Jane",
    "last_name": "Smith",
    "display_name": "Jane Smith",
    "author_page_url": "/blog/authors/jane/"
  },
  "publish_date": "2025-10-15",
  "introduction": "<p>Learn the basics of caring for indoor plants...</p>",
  "content_blocks": [
    {
      "type": "heading",
      "value": "Why Indoor Plants?"
    },
    {
      "type": "paragraph",
      "value": "<p>Indoor plants improve air quality and boost mood...</p>"
    },
    {
      "type": "image",
      "value": {
        "image": 42,
        "caption": "A beautiful pothos plant",
        "alt_text": "Green pothos plant in white pot"
      }
    },
    {
      "type": "plant_spotlight",
      "value": {
        "plant_species": 15,
        "title": "Pothos - Perfect for Beginners",
        "description": "Low-maintenance and forgiving...",
        "care_level": "easy",
        "light_requirements": "Low to bright indirect light",
        "watering_schedule": "When soil is dry 2 inches down"
      }
    }
  ],
  "categories": [...],
  "tags": ["beginner", "indoor", "easy"],
  "series": {
    "id": 2,
    "title": "Beginner's Guide to Gardening",
    "slug": "beginner-guide"
  },
  "series_order": 1,
  "featured_image": "https://example.com/media/images/plant_fill-800x600.jpg",
  "featured_image_thumb": "https://example.com/media/images/plant_fill-300x200.jpg",
  "is_featured": true,
  "reading_time": 5,
  "difficulty_level": "easy",
  "allow_comments": true,
  "excerpt": "Learn the basics...",
  "comment_count": 12,
  "related_posts": [
    {
      "id": 11,
      "title": "Top 10 Easy Houseplants",
      "slug": "top-10-easy-houseplants",
      "url": "/blog/top-10-easy-houseplants/",
      "published_date": "2025-10-20",
      "excerpt": "Discover the easiest plants...",
      "featured_image": "..."
    }
  ],
  "related_plant_species": [
    {
      "id": 15,
      "common_name": "Pothos",
      "scientific_name": "Epipremnum aureum"
    }
  ],
  "social_image": "https://example.com/media/images/plant_fill-1200x630.jpg"
}
```

**Performance**:
- Cached: <30ms
- Cold: ~400ms (19 queries)
- Cache TTL: 24 hours

---

#### Featured Posts

```http
GET /api/v2/blog-posts/featured/
```

Returns up to 6 featured posts (shortcut for `?featured=true&limit=6`).

**Response**: Same format as list endpoint

---

#### Recent Posts

```http
GET /api/v2/blog-posts/recent/
```

**Query Parameters**:
- `limit` (integer, default: 10): Number of posts to return

**Response**: Same format as list endpoint

---

#### Posts by Category

```http
GET /api/v2/blog-posts/by_category/
```

Returns featured categories with their recent posts.

**Response**:
```json
[
  {
    "category": {
      "id": 1,
      "name": "Plant Care",
      "slug": "plant-care",
      "color": "#4CAF50",
      "icon": "🌿"
    },
    "posts": [
      {
        "id": 10,
        "title": "Getting Started with Indoor Plants",
        ...
      }
    ]
  }
]
```

---

#### Search Suggestions

```http
GET /api/v2/blog-posts/search_suggestions/
```

**Query Parameters**:
- `q` (string, required, min length: 2): Search query

**Response**:
```json
[
  {
    "type": "title",
    "text": "Getting Started with Indoor Plants"
  },
  {
    "type": "title",
    "text": "Indoor Plant Troubleshooting"
  },
  {
    "type": "tag",
    "text": "indoor"
  }
]
```

**Performance**: Returns top 10 suggestions (5 titles + 5 tags)

---

#### Related Posts

```http
GET /api/v2/blog-posts/{id}/related/
```

**Path Parameters**:
- `id` (integer, required): Blog post ID

Returns up to 6 related posts based on shared categories and tags.

**Response**: Same format as list endpoint

---

### Blog Index

#### Get Blog Index Page

```http
GET /api/v2/blog-index/
```

Returns blog index pages (usually just one).

**Response**:
```json
{
  "meta": {
    "total_count": 1
  },
  "items": [
    {
      "id": 5,
      "title": "Plant Community Blog",
      "slug": "blog",
      "url": "/blog/",
      "introduction": "<p>Welcome to our plant care blog...</p>",
      "posts_per_page": 10,
      "show_featured_posts": true,
      "show_categories": true,
      "featured_posts_title": "Featured Articles",
      "featured_posts": [...],
      "categories": [...],
      "recent_posts": [...]
    }
  ]
}
```

---

### Categories

Categories are managed as Wagtail snippets.

#### List Categories

```http
GET /api/v2/categories/
```

**Note**: This endpoint requires Wagtail Snippets API configuration.

**Alternative**: Use category pages:

```http
GET /api/v2/blog-categories/
```

**Response**:
```json
{
  "meta": {
    "total_count": 5
  },
  "items": [
    {
      "id": 8,
      "title": "Plant Care",
      "slug": "plant-care",
      "url": "/blog/categories/plant-care/",
      "category": {
        "id": 1,
        "name": "Plant Care",
        "slug": "plant-care",
        "description": "Tips and guides for caring for your plants",
        "icon": "🌿",
        "color": "#4CAF50",
        "is_featured": true,
        "post_count": 25
      },
      "posts_per_page": 10,
      "posts": [...]
    }
  ]
}
```

---

### Authors

#### List Authors

```http
GET /api/v2/blog-authors/
```

**Query Parameters**:
- `username` (string): Filter by username
- `expertise` (string): Filter by expertise area

**Response**:
```json
{
  "meta": {
    "total_count": 3
  },
  "items": [
    {
      "id": 12,
      "title": "Jane Smith",
      "slug": "jane-smith",
      "url": "/blog/authors/jane-smith/",
      "author": {
        "id": 5,
        "username": "jane",
        "first_name": "Jane",
        "last_name": "Smith",
        "display_name": "Jane Smith"
      },
      "bio": "<p>Jane is a botanist with 10 years of experience...</p>",
      "expertise_areas": ["Indoor Plants", "Succulents", "Plant Diseases"],
      "social_links": {
        "twitter": "https://twitter.com/janesmith",
        "instagram": "https://instagram.com/janesmith"
      },
      "post_count": 15,
      "recent_posts": [...]
    }
  ]
}
```

---

### Images

#### Get Image Renditions

Images are automatically served with optimized renditions:

```http
GET /api/v2/images/{id}/
```

**Response includes renditions**:
```json
{
  "id": 42,
  "title": "Beautiful Pothos Plant",
  "width": 3000,
  "height": 2000,
  "renditions": [
    {
      "url": "/media/images/plant_fill-300x200.jpg",
      "width": 300,
      "height": 200,
      "filter_spec": "fill-300x200"
    },
    {
      "url": "/media/images/plant_fill-800x600.jpg",
      "width": 800,
      "height": 600,
      "filter_spec": "fill-800x600"
    }
  ]
}
```

**Common Renditions**:
- `fill-300x200`: Thumbnail (list view)
- `fill-400x300`: Medium thumbnail
- `fill-800x600`: Hero image (detail view)
- `width-1200`: Full-width image
- `fill-1200x630`: Social media sharing

---

### Feeds

#### RSS Feed

```http
GET /api/v2/blog-feeds/?format=rss
```

Returns 20 most recent posts in RSS format.

**Response**: Standard RSS XML

---

#### Atom Feed

```http
GET /api/v2/blog-feeds/?format=atom
```

Returns 20 most recent posts in Atom format.

**Response**: Standard Atom XML

---

### Headless Preview

Preview unpublished content (requires authentication):

```http
GET /api/v2/page_preview/
```

**Query Parameters**:
- `content_type` (string, required): Content type ID
- `token` (string, required): Preview token from Wagtail admin

**Response**: Same as blog post detail, but includes unpublished changes

**Authentication**: Requires Wagtail session authentication

**Preview URLs**:
- Web: `http://localhost:5173/blog/preview/{content_type}/{token}/`
- Mobile: `plantid://blog/preview?content_type={content_type}&token={token}`

---

## Response Format

All responses follow Wagtail API v2 format:

### Success Response

```json
{
  "meta": {
    "total_count": 100
  },
  "items": [...]
}
```

### Single Item Response

```json
{
  "id": 10,
  "title": "...",
  ...
}
```

### Pagination Info

```json
{
  "meta": {
    "total_count": 100
  },
  "items": [...],
  "next": "/api/v2/blog-posts/?offset=20&limit=20",
  "previous": null
}
```

---

## Error Handling

### 404 Not Found

```json
{
  "message": "Not found"
}
```

### 400 Bad Request

```json
{
  "message": "Invalid query parameter: limit must be <= 100"
}
```

### 500 Internal Server Error

```json
{
  "message": "Internal server error"
}
```

**Error Response Format**: Standard DRF error format

---

## Performance

### Caching Strategy

**Redis Configuration**:
- Cache backend: `django-redis`
- TTL: 24 hours
- Key prefix: `blog:`

**Cache Keys**:
- Blog list: `blog:list:{page}:{limit}:{filters_hash}`
- Blog post: `blog:post:{slug}`

**Cache Invalidation**:
- Automatic on publish/unpublish/delete (Wagtail signals)
- Manual: `BlogCacheService.invalidate_blog_post(slug)`

### Query Optimization

**Techniques**:
- `select_related()`: Author, series (ForeignKey)
- `prefetch_related()`: Categories, tags, related plants (ManyToMany)
- `prefetch_renditions()`: Image optimization
- Conditional prefetching: List vs detail views

**Performance Targets**:
- List queries: <20 (actual: 8-15)
- Detail queries: <25 (actual: 19)
- Cache hit response: <50ms
- Cold response: <500ms

---

## Examples

### Example 1: Get Latest Posts in Category

```bash
curl "http://localhost:8000/api/v2/blog-posts/?category_slug=plant-care&order=newest&limit=5"
```

### Example 2: Search for Orchid Care

```bash
curl "http://localhost:8000/api/v2/blog-posts/?search=orchid+care"
```

### Example 3: Get Featured Posts with Limited Fields

```bash
curl "http://localhost:8000/api/v2/blog-posts/featured/?fields=title,slug,excerpt,featured_image_thumb"
```

### Example 4: Get Posts by Author with Pagination

```bash
curl "http://localhost:8000/api/v2/blog-posts/?author_username=jane&limit=10&offset=0"
```

### Example 5: Get Posts in Date Range

```bash
curl "http://localhost:8000/api/v2/blog-posts/?date_from=2025-10-01&date_to=2025-10-31&order=newest"
```

### Example 6: Get Posts by Difficulty Level

```bash
curl "http://localhost:8000/api/v2/blog-posts/?difficulty=easy&limit=20"
```

---

## Rate Limiting

**Current**: No rate limiting (to be implemented)

**Future**:
- Anonymous: 100 requests/hour
- Authenticated: 1000 requests/hour

---

## CORS

Cross-Origin Resource Sharing is enabled for:
- `http://localhost:5173` (React dev server)
- Production domain (to be configured)

**Headers**:
```
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

---

## Version History

- **v2.0** (October 24, 2025): Current version
  - Redis caching (24h TTL)
  - Query optimization (<20 queries)
  - Headless preview support
  - StreamField API support
  - 100% test coverage (79/79 tests)

---

## See Also

- [StreamField Blocks Reference](./STREAMFIELD_BLOCKS.md)
- [Admin Guide](./ADMIN_GUIDE.md)
- [Wagtail API v2 Documentation](https://docs.wagtail.org/en/stable/advanced_topics/api/v2/configuration.html)
