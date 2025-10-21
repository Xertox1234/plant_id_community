# API Documentation

**Version**: 1.0  
**Last Updated**: October 21, 2025  
**Purpose**: Complete REST API documentation for Plant ID Community

---

## Table of Contents

1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Plant Identification APIs](#plant-identification-apis)
4. [User APIs](#user-apis)
5. [Forum APIs](#forum-apis)
6. [Blog APIs](#blog-apis)
7. [Notification APIs](#notification-apis)
8. [Admin APIs](#admin-apis)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)
11. [Webhooks](#webhooks)

---

## API Overview

### Base URLs

```
Production:  https://api.plantid.community/v1
Staging:     https://staging-api.plantid.community/v1
Development: http://localhost:8000/api/v1
```

### API Architecture

```
┌─────────────────┐
│   Mobile App    │
│   (Flutter)     │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐  ┌──────────────────┐
│  Firebase       │  │  Django REST     │
│  (Direct SDK)   │  │  API Backend     │
│                 │  │                  │
│ - Auth          │  │ - Forum          │
│ - Firestore     │  │ - Blog           │
│ - Storage       │  │ - User Sync      │
│ - Functions     │  │ - Admin          │
└─────────────────┘  └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │   React Web      │
                     │   (Headless)     │
                     └──────────────────┘
```

### Technology Stack

- **API Framework**: Django REST Framework (DRF) 3.15+
- **Authentication**: Firebase Auth (JWT tokens)
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **File Storage**: Firebase Cloud Storage
- **Rate Limiting**: Django REST Framework throttling
- **Documentation**: OpenAPI 3.0 (Swagger)

### Request/Response Format

**Content Type**: `application/json`

**Standard Response Structure**:
```json
{
  "success": true,
  "data": { /* response data */ },
  "message": "Success message",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Error Response Structure**:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { /* additional error context */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

## Authentication

### Overview

All API requests (except public endpoints) require Firebase Authentication.

**Authentication Flow**:
1. User authenticates via Firebase Auth SDK (mobile/web)
2. Client receives Firebase ID token
3. Client includes token in `Authorization` header
4. Backend validates token via Firebase Admin SDK
5. Backend identifies user and processes request

### Headers

```http
Authorization: Bearer <firebase_id_token>
Content-Type: application/json
X-Client-Version: 1.0.0
X-Platform: ios|android|web
```

### Public Endpoints (No Auth Required)

- `GET /health` - Health check
- `GET /blog/posts` - List blog posts
- `GET /blog/posts/{slug}` - Get blog post
- `GET /forum/categories` - List forum categories
- `GET /forum/topics` - Browse forum topics (read-only)
- `POST /auth/register` - User registration (creates Firebase user)

### Token Refresh

Firebase tokens expire after 1 hour. The Firebase SDK automatically handles refresh.

**Token Validation**:
```python
# Backend validates token
decoded_token = auth.verify_id_token(id_token)
uid = decoded_token['uid']
```

---

## Plant Identification APIs

### 1. Submit Plant Identification Request

Submit an image for plant identification.

**Endpoint**: `POST /identifications`

**Authentication**: Required

**Request Headers**:
```http
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**Request Body** (multipart/form-data):
```
image: File (required) - Plant image (max 10MB, jpg/png/webp)
platform: string (required) - "mobile" or "web"
location: object (optional) - {latitude, longitude, city, country}
```

**Example Request**:
```bash
curl -X POST https://api.plantid.community/v1/identifications \
  -H "Authorization: Bearer <token>" \
  -F "image=@plant_photo.jpg" \
  -F "platform=mobile" \
  -F 'location={"latitude": 37.7749, "longitude": -122.4194}'
```

**Response** (202 Accepted):
```json
{
  "success": true,
  "data": {
    "identificationId": "abc123",
    "status": "processing",
    "estimatedTime": 3,
    "message": "Your plant is being identified..."
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Flow**:
1. Image uploaded to Firebase Storage
2. Identification request created in Firestore (status: "pending")
3. Cloud Function triggered
4. Plant.id API called
5. Results stored in Firestore
6. Client receives real-time update via Firestore listener

**Status Codes**:
- `202 Accepted` - Request accepted and processing
- `400 Bad Request` - Invalid image or parameters
- `401 Unauthorized` - Missing or invalid token
- `413 Payload Too Large` - Image exceeds size limit
- `429 Too Many Requests` - Rate limit exceeded

---

### 2. Get Identification Result

Retrieve identification result (alternative to Firestore real-time listener).

**Endpoint**: `GET /identifications/{identificationId}`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "abc123",
    "status": "completed",
    "requestedAt": "2025-10-21T12:00:00Z",
    "completedAt": "2025-10-21T12:00:03Z",
    "imageUrl": "https://storage.googleapis.com/...",
    "plant": {
      "name": "Monstera deliciosa",
      "scientificName": "Monstera deliciosa",
      "commonNames": ["Swiss Cheese Plant", "Split-leaf Philodendron"],
      "confidence": 0.95,
      "family": "Araceae",
      "genus": "Monstera",
      "species": "deliciosa",
      "description": "A species of flowering plant native to...",
      "nativeRegion": "Central America",
      "category": "houseplant"
    },
    "alternatives": [
      {
        "name": "Monstera adansonii",
        "scientificName": "Monstera adansonii",
        "confidence": 0.78
      }
    ],
    "care": {
      "watering": {
        "frequency": "weekly",
        "amount": "moderate",
        "instructions": "Water when top 2 inches..."
      },
      "sunlight": {
        "requirement": "indirect",
        "hours": "4-6",
        "instructions": "Bright indirect light..."
      },
      "temperature": {
        "min": 65,
        "max": 85,
        "optimal": 75,
        "instructions": "Keep above 65°F..."
      },
      "humidity": {
        "level": "high",
        "percentage": "60-80",
        "instructions": "Mist regularly..."
      },
      "soil": {
        "type": "well-draining",
        "ph": "5.5-7.0",
        "instructions": "Use peat-based mix..."
      },
      "fertilizer": {
        "frequency": "monthly",
        "type": "balanced",
        "instructions": "Feed during growing season..."
      },
      "difficulty": "easy"
    },
    "healthCheck": {
      "healthy": true,
      "issues": [],
      "confidence": 0.92
    }
  },
  "timestamp": "2025-10-21T12:00:05Z"
}
```

**Status Codes**:
- `200 OK` - Success
- `404 Not Found` - Identification not found
- `403 Forbidden` - Not authorized to view this identification

---

### 3. List User's Identifications

Get history of user's plant identifications.

**Endpoint**: `GET /identifications`

**Authentication**: Required

**Query Parameters**:
```
page: integer (default: 1)
limit: integer (default: 20, max: 100)
category: string (optional) - Filter by plant category
saved: boolean (optional) - Filter saved plants only
sort: string (default: "-requestedAt") - Sort field
```

**Example Request**:
```bash
GET /identifications?page=1&limit=20&saved=true&sort=-requestedAt
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "abc123",
        "plantName": "Monstera deliciosa",
        "scientificName": "Monstera deliciosa",
        "thumbnailUrl": "https://...",
        "confidence": 0.95,
        "category": "houseplant",
        "saved": true,
        "requestedAt": "2025-10-21T12:00:00Z"
      }
      // ... more items
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 42,
      "pages": 3,
      "hasNext": true,
      "hasPrev": false
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 4. Save to Collection

Add a plant identification to user's collection.

**Endpoint**: `POST /identifications/{identificationId}/save`

**Authentication**: Required

**Request Body**:
```json
{
  "customName": "My Monstera Baby",
  "location": "Living Room",
  "notes": "Birthday gift from mom",
  "tags": ["favorite", "indoor"]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "saved": true,
    "collectionId": "xyz789"
  },
  "message": "Added to your collection",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 5. Delete Identification

Delete a plant identification from history.

**Endpoint**: `DELETE /identifications/{identificationId}`

**Authentication**: Required

**Response** (204 No Content)

---

## User APIs

### 1. Get Current User Profile

Get authenticated user's profile.

**Endpoint**: `GET /users/me`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "uid": "firebase_uid",
    "email": "user@example.com",
    "displayName": "John Doe",
    "username": "johndoe123",
    "photoURL": "https://...",
    "bio": "Plant enthusiast from SF",
    "location": "San Francisco, CA",
    "website": "https://johndoe.com",
    "verified": false,
    "role": "user",
    "stats": {
      "plantsIdentified": 42,
      "collectionSize": 28,
      "forumPosts": 15,
      "forumReplies": 67,
      "likesReceived": 234,
      "solutionsProvided": 8
    },
    "settings": {
      "theme": "dark",
      "language": "en",
      "notifications": {
        "push": true,
        "email": true,
        "forumReplies": true
      },
      "privacy": {
        "profilePublic": true,
        "showEmail": false
      }
    },
    "createdAt": "2024-01-15T10:00:00Z",
    "lastLoginAt": "2025-10-21T12:00:00Z"
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 2. Update User Profile

Update user profile information.

**Endpoint**: `PATCH /users/me`

**Authentication**: Required

**Request Body**:
```json
{
  "displayName": "John Doe",
  "bio": "Plant enthusiast and gardener",
  "location": "San Francisco, CA",
  "website": "https://johndoe.com",
  "settings": {
    "theme": "dark",
    "notifications": {
      "push": true,
      "email": false
    }
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    // Updated user object
  },
  "message": "Profile updated successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Sync Behavior**:
- Updates PostgreSQL `user_profiles` table
- Cloud Function syncs to Firestore `users` collection
- Changes propagate to mobile clients via Firestore real-time sync

---

### 3. Upload Profile Photo

Update user's profile photo.

**Endpoint**: `POST /users/me/photo`

**Authentication**: Required

**Request** (multipart/form-data):
```
photo: File (required) - Image file (max 5MB, jpg/png)
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "photoURL": "https://storage.googleapis.com/..."
  },
  "message": "Photo updated successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 4. Get User by Username

Get public profile of another user.

**Endpoint**: `GET /users/{username}`

**Authentication**: Optional (public profiles visible to all)

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "username": "johndoe123",
    "displayName": "John Doe",
    "photoURL": "https://...",
    "bio": "Plant enthusiast",
    "location": "San Francisco, CA",
    "verified": false,
    "stats": {
      "forumPosts": 15,
      "forumReplies": 67,
      "likesReceived": 234,
      "solutionsProvided": 8
    },
    "memberSince": "2024-01-15T10:00:00Z"
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Note**: Only public information shown. Private fields excluded.

---

### 5. Get User's Collection

Get a user's plant collection (if public).

**Endpoint**: `GET /users/{username}/collection`

**Authentication**: Optional

**Query Parameters**:
```
page: integer (default: 1)
limit: integer (default: 20)
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "xyz789",
        "plantName": "Monstera deliciosa",
        "customName": "My Monstera",
        "thumbnailUrl": "https://...",
        "category": "houseplant",
        "addedAt": "2025-01-15T10:00:00Z"
      }
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

## Forum APIs

### 1. List Forum Categories

Get all forum categories.

**Endpoint**: `GET /forum/categories`

**Authentication**: Optional

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Plant Care",
      "slug": "plant-care",
      "description": "General plant care questions and tips",
      "icon": "droplet",
      "color": "#4CAF50",
      "topicCount": 234,
      "postCount": 1523,
      "displayOrder": 1
    },
    {
      "id": 2,
      "name": "Plant Problems",
      "slug": "plant-problems",
      "description": "Diagnose and solve plant issues",
      "icon": "alert-circle",
      "color": "#F44336",
      "topicCount": 156,
      "postCount": 892,
      "displayOrder": 2
    }
  ],
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 2. List Forum Topics

Browse forum topics (with filtering and sorting).

**Endpoint**: `GET /forum/topics`

**Authentication**: Optional

**Query Parameters**:
```
page: integer (default: 1)
limit: integer (default: 20, max: 100)
category: integer (optional) - Filter by category ID
tag: string (optional) - Filter by tag slug
search: string (optional) - Full-text search
sort: string (default: "-lastActivityAt")
  Options: -lastActivityAt, -createdAt, -replyCount, -viewCount
pinned: boolean (optional) - Show pinned only
solved: boolean (optional) - Filter by solved status
```

**Example Request**:
```bash
GET /forum/topics?category=1&sort=-lastActivityAt&page=1&limit=20
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 123,
        "title": "Help with yellowing leaves on my Monstera",
        "slug": "help-yellowing-leaves-monstera",
        "contentPreview": "My monstera has been getting yellow leaves...",
        "category": {
          "id": 1,
          "name": "Plant Care",
          "slug": "plant-care"
        },
        "author": {
          "username": "sarah123",
          "displayName": "Sarah",
          "photoURL": "https://...",
          "verified": false
        },
        "tags": ["monstera", "yellowing", "help"],
        "pinned": false,
        "locked": false,
        "solved": false,
        "viewCount": 234,
        "replyCount": 12,
        "likeCount": 5,
        "createdAt": "2025-10-20T14:30:00Z",
        "lastActivityAt": "2025-10-21T10:15:00Z",
        "lastReplyBy": {
          "username": "plantexpert",
          "displayName": "Dr. Green"
        }
      }
      // ... more topics
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 234,
      "pages": 12,
      "hasNext": true,
      "hasPrev": false
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 3. Get Topic Details

Get full topic with replies.

**Endpoint**: `GET /forum/topics/{slug}`

**Authentication**: Optional

**Query Parameters**:
```
page: integer (default: 1) - For paginated replies
limit: integer (default: 20) - Replies per page
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": 123,
    "title": "Help with yellowing leaves on my Monstera",
    "slug": "help-yellowing-leaves-monstera",
    "content": "My monstera has been getting yellow leaves for the past two weeks. I water it weekly and it gets indirect sunlight. What could be wrong?",
    "contentHtml": "<p>My monstera has been getting yellow leaves...</p>",
    "category": {
      "id": 1,
      "name": "Plant Care",
      "slug": "plant-care"
    },
    "author": {
      "username": "sarah123",
      "displayName": "Sarah",
      "photoURL": "https://...",
      "verified": false,
      "stats": {
        "forumPosts": 5,
        "forumReplies": 12
      }
    },
    "tags": ["monstera", "yellowing", "help"],
    "attachments": [
      {
        "id": 456,
        "fileName": "monstera_leaves.jpg",
        "fileUrl": "https://...",
        "thumbnailUrl": "https://...",
        "width": 1920,
        "height": 1080
      }
    ],
    "pinned": false,
    "locked": false,
    "solved": false,
    "solutionReplyId": null,
    "viewCount": 235,
    "replyCount": 12,
    "likeCount": 5,
    "isLikedByUser": false,
    "isSubscribed": true,
    "createdAt": "2025-10-20T14:30:00Z",
    "updatedAt": "2025-10-20T14:30:00Z",
    "lastActivityAt": "2025-10-21T10:15:00Z",
    "replies": {
      "items": [
        {
          "id": 789,
          "content": "This could be overwatering. Check the soil moisture...",
          "contentHtml": "<p>This could be overwatering...</p>",
          "author": {
            "username": "plantexpert",
            "displayName": "Dr. Green",
            "photoURL": "https://...",
            "verified": true
          },
          "isSolution": true,
          "likeCount": 8,
          "isLikedByUser": false,
          "edited": false,
          "createdAt": "2025-10-20T15:00:00Z",
          "nestedReplies": [
            {
              "id": 790,
              "content": "Thanks! That makes sense...",
              "author": { /* ... */ },
              "createdAt": "2025-10-20T15:30:00Z"
            }
          ]
        }
        // ... more replies
      ],
      "pagination": { /* ... */ }
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Note**: This endpoint also increments `viewCount`.

---

### 4. Create Forum Topic

Create a new forum discussion topic.

**Endpoint**: `POST /forum/topics`

**Authentication**: Required

**Request Body**:
```json
{
  "categoryId": 1,
  "title": "Help with yellowing leaves on my Monstera",
  "content": "My monstera has been getting yellow leaves...",
  "tags": ["monstera", "yellowing", "help"],
  "attachments": ["file_id_1", "file_id_2"]
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": 123,
    "slug": "help-yellowing-leaves-monstera",
    "title": "Help with yellowing leaves on my Monstera",
    // ... full topic object
  },
  "message": "Topic created successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Flow**:
1. Topic created in PostgreSQL
2. Django signal fires
3. Cloud Function syncs to Firestore (for mobile cache)
4. Notifications sent to category subscribers

---

### 5. Update Forum Topic

Update an existing topic (author only).

**Endpoint**: `PATCH /forum/topics/{slug}`

**Authentication**: Required

**Request Body**:
```json
{
  "title": "Updated title",
  "content": "Updated content...",
  "tags": ["updated", "tags"]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    // Updated topic object
  },
  "message": "Topic updated successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 6. Delete Forum Topic

Delete a topic (author or moderator only).

**Endpoint**: `DELETE /forum/topics/{slug}`

**Authentication**: Required

**Response** (204 No Content)

**Note**: Soft delete - sets `deleted_at` timestamp.

---

### 7. Create Reply

Reply to a forum topic.

**Endpoint**: `POST /forum/topics/{slug}/replies`

**Authentication**: Required

**Request Body**:
```json
{
  "content": "This could be overwatering...",
  "parentId": 789,
  "attachments": ["file_id_1"]
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": 790,
    "content": "This could be overwatering...",
    // ... full reply object
  },
  "message": "Reply posted successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Flow**:
1. Reply created in PostgreSQL
2. Topic's `reply_count` incremented
3. Topic's `last_reply_at` updated
4. Notification sent to topic author
5. Notification sent to mentioned users (@username)

---

### 8. Update Reply

Update a reply (author only, within time limit or if moderator).

**Endpoint**: `PATCH /forum/replies/{replyId}`

**Authentication**: Required

**Request Body**:
```json
{
  "content": "Updated reply content..."
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    // Updated reply object
    "edited": true,
    "editedAt": "2025-10-21T12:00:00Z"
  },
  "message": "Reply updated successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 9. Delete Reply

Delete a reply (author or moderator).

**Endpoint**: `DELETE /forum/replies/{replyId}`

**Authentication**: Required

**Response** (204 No Content)

---

### 10. Like/Unlike Topic

Toggle like on a forum topic.

**Endpoint**: `POST /forum/topics/{slug}/like`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "liked": true,
    "likeCount": 6
  },
  "message": "Topic liked",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Note**: Same endpoint toggles between like/unlike.

---

### 11. Like/Unlike Reply

Toggle like on a forum reply.

**Endpoint**: `POST /forum/replies/{replyId}/like`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "liked": true,
    "likeCount": 9
  },
  "message": "Reply liked",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 12. Mark Reply as Solution

Mark a reply as the solution (topic author or moderator).

**Endpoint**: `POST /forum/replies/{replyId}/mark-solution`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "isSolution": true,
    "topicSolved": true
  },
  "message": "Reply marked as solution",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Effects**:
- Reply's `is_solution` set to true
- Topic's `solved` set to true
- Notification sent to reply author
- Solution author's `solutions_provided` stat incremented

---

### 13. Subscribe to Topic

Subscribe to receive notifications for new replies.

**Endpoint**: `POST /forum/topics/{slug}/subscribe`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "subscribed": true
  },
  "message": "Subscribed to topic",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Note**: Users auto-subscribe to topics they create.

---

### 14. Upload Forum Attachment

Upload an image for forum post/reply.

**Endpoint**: `POST /forum/attachments`

**Authentication**: Required

**Request** (multipart/form-data):
```
file: File (required) - Image file (max 5MB)
```

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "file_id_123",
    "fileName": "plant_issue.jpg",
    "fileUrl": "https://storage.googleapis.com/...",
    "thumbnailUrl": "https://storage.googleapis.com/.../thumb_...",
    "width": 1920,
    "height": 1080
  },
  "message": "File uploaded successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Note**: Attachment is temporary until associated with a topic/reply.

---

### 15. Search Forum

Full-text search across forum topics and replies.

**Endpoint**: `GET /forum/search`

**Authentication**: Optional

**Query Parameters**:
```
q: string (required) - Search query
category: integer (optional) - Filter by category
author: string (optional) - Filter by username
tag: string (optional) - Filter by tag
solved: boolean (optional)
page: integer (default: 1)
limit: integer (default: 20)
```

**Example Request**:
```bash
GET /forum/search?q=monstera+yellowing&category=1
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "query": "monstera yellowing",
    "results": [
      {
        "type": "topic",
        "id": 123,
        "title": "Help with yellowing leaves on my Monstera",
        "slug": "help-yellowing-leaves-monstera",
        "excerpt": "My <mark>monstera</mark> has been getting <mark>yellowing</mark> leaves...",
        "category": { /* ... */ },
        "author": { /* ... */ },
        "createdAt": "2025-10-20T14:30:00Z",
        "relevance": 0.89
      },
      {
        "type": "reply",
        "id": 456,
        "topicTitle": "Common Monstera Problems",
        "topicSlug": "common-monstera-problems",
        "excerpt": "Yellow leaves on <mark>Monstera</mark> usually indicate...",
        "author": { /* ... */ },
        "createdAt": "2025-10-19T10:00:00Z",
        "relevance": 0.75
      }
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

## Blog APIs

### 1. List Blog Posts

Get published blog posts.

**Endpoint**: `GET /blog/posts`

**Authentication**: Optional

**Query Parameters**:
```
page: integer (default: 1)
limit: integer (default: 12, max: 50)
category: string (optional) - Filter by category slug
tag: string (optional) - Filter by tag slug
search: string (optional) - Full-text search
featured: boolean (optional) - Featured posts only
author: string (optional) - Filter by author username
sort: string (default: "-publishedAt")
```

**Example Request**:
```bash
GET /blog/posts?category=care-tips&page=1&limit=12
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 42,
        "title": "10 Essential Tips for Monstera Care",
        "slug": "10-essential-tips-monstera-care",
        "subtitle": "Everything you need to know",
        "excerpt": "Monstera deliciosa is one of the most popular houseplants...",
        "featuredImage": {
          "url": "https://...",
          "alt": "Monstera plant in modern home",
          "width": 1200,
          "height": 630
        },
        "author": {
          "username": "plantexpert",
          "displayName": "Dr. Green",
          "photoURL": "https://...",
          "bio": "Botanist and plant care expert"
        },
        "categories": ["Care Tips", "Houseplants"],
        "tags": ["monstera", "care", "houseplants"],
        "readTime": 8,
        "viewCount": 1542,
        "featured": true,
        "publishedAt": "2025-10-15T10:00:00Z",
        "updatedAt": "2025-10-16T14:30:00Z"
      }
      // ... more posts
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 2. Get Blog Post

Get a single blog post by slug.

**Endpoint**: `GET /blog/posts/{slug}`

**Authentication**: Optional

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": 42,
    "title": "10 Essential Tips for Monstera Care",
    "slug": "10-essential-tips-monstera-care",
    "subtitle": "Everything you need to know",
    "excerpt": "Monstera deliciosa is one of the most popular...",
    "body": [
      {
        "type": "paragraph",
        "value": "Monstera deliciosa is one of the most popular..."
      },
      {
        "type": "heading",
        "value": "1. Light Requirements",
        "level": 2
      },
      {
        "type": "paragraph",
        "value": "Monsteras thrive in bright, indirect light..."
      },
      {
        "type": "image",
        "value": {
          "url": "https://...",
          "alt": "Monstera near window",
          "caption": "Perfect lighting for Monstera"
        }
      },
      {
        "type": "quote",
        "value": "The best fertilizer is attention.",
        "attribution": "Old gardening proverb"
      }
      // ... more blocks (Wagtail StreamField)
    ],
    "featuredImage": { /* ... */ },
    "author": { /* ... */ },
    "categories": ["Care Tips", "Houseplants"],
    "tags": ["monstera", "care", "houseplants"],
    "readTime": 8,
    "viewCount": 1543,
    "featured": true,
    "seo": {
      "title": "10 Essential Monstera Care Tips | Plant ID Community",
      "description": "Learn everything about caring for Monstera...",
      "ogImage": "https://..."
    },
    "publishedAt": "2025-10-15T10:00:00Z",
    "updatedAt": "2025-10-16T14:30:00Z",
    "relatedPosts": [
      {
        "id": 43,
        "title": "Common Monstera Problems Solved",
        "slug": "common-monstera-problems-solved",
        "featuredImage": { /* ... */ }
      }
      // ... more related posts
    ],
    "tableOfContents": [
      {
        "title": "Light Requirements",
        "anchor": "light-requirements",
        "level": 2
      },
      {
        "title": "Watering Schedule",
        "anchor": "watering-schedule",
        "level": 2
      }
      // ... more TOC items
    ]
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Note**: This endpoint also increments `viewCount`.

---

### 3. Get Blog Categories

List all blog categories.

**Endpoint**: `GET /blog/categories`

**Authentication**: Optional

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Care Tips",
      "slug": "care-tips",
      "description": "Expert advice for keeping your plants healthy",
      "postCount": 42
    },
    {
      "id": 2,
      "name": "Houseplants",
      "slug": "houseplants",
      "description": "Everything about indoor plants",
      "postCount": 38
    }
  ],
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 4. Search Blog

Full-text search for blog posts.

**Endpoint**: `GET /blog/search`

**Authentication**: Optional

**Query Parameters**:
```
q: string (required) - Search query
page: integer (default: 1)
limit: integer (default: 12)
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "query": "monstera care",
    "results": [
      {
        "id": 42,
        "title": "10 Essential Tips for <mark>Monstera</mark> <mark>Care</mark>",
        "slug": "10-essential-tips-monstera-care",
        "excerpt": "Learn everything about <mark>caring</mark> for <mark>Monstera</mark>...",
        "featuredImage": { /* ... */ },
        "publishedAt": "2025-10-15T10:00:00Z",
        "relevance": 0.95
      }
      // ... more results
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

## Notification APIs

### 1. Get Notifications

Get user's notifications.

**Endpoint**: `GET /notifications`

**Authentication**: Required

**Query Parameters**:
```
page: integer (default: 1)
limit: integer (default: 20)
unread: boolean (optional) - Unread only
type: string (optional) - Filter by type
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "unreadCount": 5,
    "items": [
      {
        "id": "notif_123",
        "type": "forum_reply",
        "title": "New reply to your post",
        "message": "Marcus replied to 'Help with yellowing leaves'",
        "icon": "message-circle",
        "actionUrl": "/forum/topics/help-yellowing-leaves#reply-789",
        "actionData": {
          "topicSlug": "help-yellowing-leaves",
          "replyId": 789
        },
        "fromUser": {
          "username": "marcus",
          "displayName": "Marcus",
          "photoURL": "https://..."
        },
        "read": false,
        "clicked": false,
        "createdAt": "2025-10-21T11:30:00Z"
      }
      // ... more notifications
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 2. Mark Notification as Read

Mark a notification as read.

**Endpoint**: `PATCH /notifications/{notificationId}/read`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "read": true,
    "readAt": "2025-10-21T12:00:00Z"
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 3. Mark All as Read

Mark all notifications as read.

**Endpoint**: `POST /notifications/mark-all-read`

**Authentication**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "markedCount": 5
  },
  "message": "All notifications marked as read",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 4. Delete Notification

Delete a notification.

**Endpoint**: `DELETE /notifications/{notificationId}`

**Authentication**: Required

**Response** (204 No Content)

---

## Admin APIs

**Note**: All admin endpoints require `role == 'admin'` or `role == 'moderator'`.

### 1. Get Admin Dashboard Stats

Get overview statistics for admin dashboard.

**Endpoint**: `GET /admin/stats`

**Authentication**: Required (Admin/Moderator)

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "users": {
      "total": 5432,
      "newToday": 12,
      "newThisWeek": 87,
      "newThisMonth": 342,
      "activeToday": 234,
      "verified": 42
    },
    "identifications": {
      "total": 12543,
      "today": 45,
      "thisWeek": 312,
      "thisMonth": 1234,
      "successRate": 0.96,
      "avgProcessingTime": 2.3
    },
    "forum": {
      "totalTopics": 1234,
      "totalReplies": 5678,
      "topicsToday": 8,
      "repliesToday": 42,
      "pendingModeration": 3
    },
    "blog": {
      "totalPosts": 87,
      "totalViews": 54321,
      "drafts": 5,
      "scheduled": 2
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 2. Get Users List (Admin)

List all users with admin details.

**Endpoint**: `GET /admin/users`

**Authentication**: Required (Admin)

**Query Parameters**:
```
page: integer (default: 1)
limit: integer (default: 50)
search: string (optional) - Search by username/email
role: string (optional) - Filter by role
banned: boolean (optional)
verified: boolean (optional)
sort: string (default: "-createdAt")
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "uid": "firebase_uid",
        "username": "johndoe123",
        "email": "john@example.com",
        "displayName": "John Doe",
        "role": "user",
        "verified": false,
        "banned": false,
        "stats": {
          "plantsIdentified": 42,
          "forumPosts": 15
        },
        "createdAt": "2024-01-15T10:00:00Z",
        "lastLoginAt": "2025-10-21T09:00:00Z"
      }
      // ... more users
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 3. Update User (Admin)

Update user details or moderation status.

**Endpoint**: `PATCH /admin/users/{uid}`

**Authentication**: Required (Admin)

**Request Body**:
```json
{
  "role": "moderator",
  "verified": true,
  "banned": false
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    // Updated user object
  },
  "message": "User updated successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 4. Ban User

Ban a user from the platform.

**Endpoint**: `POST /admin/users/{uid}/ban`

**Authentication**: Required (Admin/Moderator)

**Request Body**:
```json
{
  "reason": "Spamming forum with promotional content",
  "duration": 7,
  "durationUnit": "days"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "banned": true,
    "banReason": "Spamming forum with promotional content",
    "banExpiresAt": "2025-10-28T12:00:00Z"
  },
  "message": "User banned successfully",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 5. Get Moderation Queue

Get content pending moderation.

**Endpoint**: `GET /admin/moderation/queue`

**Authentication**: Required (Moderator)

**Query Parameters**:
```
type: string (optional) - topic|reply|user
page: integer (default: 1)
limit: integer (default: 20)
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 123,
        "type": "topic",
        "title": "Suspicious spam post",
        "author": {
          "username": "spammer123",
          "displayName": "Spammer"
        },
        "content": "Click here for amazing deals...",
        "reportCount": 3,
        "reports": [
          {
            "reporter": "gooduser",
            "reason": "spam",
            "createdAt": "2025-10-21T11:00:00Z"
          }
        ],
        "createdAt": "2025-10-21T10:00:00Z"
      }
      // ... more items
    ],
    "pagination": { /* ... */ }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

### 6. Moderate Content

Take moderation action on content.

**Endpoint**: `POST /admin/moderation/action`

**Authentication**: Required (Moderator)

**Request Body**:
```json
{
  "contentType": "topic",
  "contentId": 123,
  "action": "delete",
  "reason": "Spam content violating community guidelines",
  "notifyUser": true
}
```

**Actions**: `approve`, `delete`, `lock`, `pin`, `unpublish`

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "actionTaken": "delete",
    "contentId": 123
  },
  "message": "Moderation action completed",
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

## Error Handling

### Standard Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `BAD_REQUEST` | Invalid request parameters |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource conflict (e.g., duplicate) |
| 413 | `PAYLOAD_TOO_LARGE` | Request body too large |
| 422 | `VALIDATION_ERROR` | Request validation failed |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### Error Response Examples

**Validation Error**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "fields": {
        "email": ["This field is required"],
        "password": ["Password must be at least 8 characters"]
      }
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Not Found**:
```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Topic not found",
    "details": {
      "resource": "ForumTopic",
      "identifier": "non-existent-slug"
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

**Rate Limit**:
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "details": {
      "limit": 100,
      "window": "1 hour",
      "retryAfter": 3600
    }
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

---

## Rate Limiting

### Rate Limits by Endpoint Type

| Endpoint Type | Authenticated | Anonymous |
|---------------|---------------|-----------|
| Read (GET) | 1000/hour | 100/hour |
| Write (POST/PATCH/DELETE) | 300/hour | N/A |
| Plant ID Submit | 50/day | N/A |
| Image Upload | 100/day | N/A |
| Forum Post | 20/hour | N/A |
| Forum Reply | 60/hour | N/A |

### Rate Limit Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1698073200
```

### Burst Handling

Short bursts allowed within rate limits:
- Up to 10 requests per second
- Maximum 50 requests in 10 seconds

---

## Webhooks

### Supported Events

Configure webhooks in admin panel to receive events:

**User Events**:
- `user.created`
- `user.updated`
- `user.deleted`

**Identification Events**:
- `identification.completed`
- `identification.failed`

**Forum Events**:
- `forum.topic.created`
- `forum.reply.created`
- `forum.topic.solved`

**Blog Events**:
- `blog.post.published`

### Webhook Payload

```json
{
  "event": "forum.topic.created",
  "timestamp": "2025-10-21T12:00:00Z",
  "data": {
    "id": 123,
    "title": "Help with yellowing leaves",
    "author": {
      "username": "sarah123"
    }
  },
  "signature": "sha256=..."
}
```

### Signature Verification

```python
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## API Versioning

Current version: **v1**

**URL Format**: `https://api.plantid.community/v1/...`

### Version Support Policy

- Current version (v1): Fully supported
- Previous version: Supported for 6 months after deprecation notice
- Breaking changes: New major version (v2, v3, etc.)
- Non-breaking changes: Added to current version

### Deprecation Process

1. Deprecation announced 3 months in advance
2. `Deprecation` header added to responses
3. Documentation updated with migration guide
4. Old version supported for 6 months
5. Old version shut down

---

## SDK Support

### Official SDKs

**Mobile (Flutter/Dart)**:
```dart
import 'package:plant_id_api/plant_id_api.dart';

final api = PlantIdApi(
  baseUrl: 'https://api.plantid.community/v1',
  auth: FirebaseAuth.instance,
);

// Submit identification
final result = await api.identifications.submit(imageFile);

// Get forum topics
final topics = await api.forum.getTopics(categoryId: 1);
```

**Web (JavaScript/TypeScript)**:
```typescript
import { PlantIdClient } from '@plantid/api-client';

const client = new PlantIdClient({
  baseUrl: 'https://api.plantid.community/v1',
  auth: firebase.auth(),
});

// Get blog posts
const posts = await client.blog.getPosts({ category: 'care-tips' });
```

---

## Testing

### Test Endpoints

Use separate test environment:

```
Test API: https://test-api.plantid.community/v1
```

### Test Users

```
Email: test@plantid.community
Password: TestPassword123!
Role: user

Email: admin@plantid.community
Password: AdminPassword123!
Role: admin
```

### Mock Data

Test endpoints return consistent mock data:
- Predictable IDs
- Fixed timestamps
- No external API calls
- Instant responses

---

## Best Practices

### Pagination

Always use pagination for list endpoints:
```
GET /forum/topics?page=1&limit=20
```

### Filtering

Combine filters for precise results:
```
GET /forum/topics?category=1&tag=monstera&solved=false
```

### Caching

Respect cache headers:
```http
Cache-Control: public, max-age=300
ETag: "abc123"
```

Use `If-None-Match` for conditional requests:
```http
If-None-Match: "abc123"
```

### Error Handling

Always check `success` field:
```typescript
if (response.success) {
  // Handle data
  const data = response.data;
} else {
  // Handle error
  const error = response.error;
  console.error(error.message);
}
```

### Real-time Updates

For real-time data, use Firestore listeners instead of polling:
```dart
// Instead of polling
// ❌ setInterval(() => api.getNotifications(), 5000);

// Use Firestore listener
// ✅ 
FirebaseFirestore.instance
  .collection('notifications')
  .where('userId', isEqualTo: currentUserId)
  .snapshots()
  .listen((snapshot) {
    // Real-time updates
  });
```

---

## OpenAPI Specification

Full OpenAPI 3.0 spec available at:
```
https://api.plantid.community/v1/openapi.json
https://api.plantid.community/v1/docs (Swagger UI)
https://api.plantid.community/v1/redoc (ReDoc)
```

---

**Document Status**: ✅ Complete v1.0  
**Last Updated**: October 21, 2025  
**Next Steps**: Implement API endpoints and deploy  
**Related Documents**: Database Schema, User Stories, Master Plan
