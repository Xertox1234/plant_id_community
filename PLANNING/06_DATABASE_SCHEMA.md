# Database Schema Design

**Version**: 1.0  
**Last Updated**: October 21, 2025  
**Purpose**: Complete database architecture for Plant ID Community using Firebase Firestore and PostgreSQL

---

## Table of Contents

1. [Database Strategy Overview](#database-strategy-overview)
2. [Firebase/Firestore Schema](#firebasefirestore-schema)
3. [PostgreSQL Schema](#postgresql-schema)
4. [Data Synchronization](#data-synchronization)
5. [Security Rules](#security-rules)
6. [Indexes & Performance](#indexes--performance)
7. [Migration Strategy](#migration-strategy)

---

## Database Strategy Overview

### Hybrid Database Approach

We use two databases to leverage the best tool for each job:

#### **Firebase/Firestore** - Mobile & Real-time Data
- **Purpose**: Mobile app primary database
- **Use Cases**:
  - User authentication (Firebase Auth)
  - Plant identifications and results
  - User plant collections
  - User profiles (mobile-specific data)
  - Real-time notifications
  - Image metadata and references
- **Advantages**:
  - Offline support for mobile
  - Real-time synchronization
  - Built-in authentication
  - Automatic scaling
  - Mobile SDK optimization

#### **PostgreSQL** - Web & Content Management
- **Purpose**: Web platform and CMS database
- **Use Cases**:
  - Blog posts and pages (Wagtail CMS)
  - Forum topics and replies
  - User profiles (web-specific data)
  - Comments and moderation
  - Analytics and reporting
- **Advantages**:
  - Complex queries and joins
  - Wagtail/Django ORM compatibility
  - Full-text search
  - Relational integrity
  - Better for content management

### Data Flow

```
Mobile App → Firestore ←→ Cloud Functions ←→ PostgreSQL ← Web App
                ↓                                    ↑
         Firebase Auth  ←────────────────────────────┘
         (Shared Authentication)
```

---

## Firebase/Firestore Schema

### Collection Structure

Firestore uses a NoSQL document model with collections and subcollections.

---

### 1. **users** Collection

Stores user profile information synchronized with Firebase Auth.

**Document ID**: Firebase Auth UID

```javascript
{
  // Document ID: {firebaseAuthUID}
  
  // Basic Info
  "uid": "firebase_auth_uid",
  "email": "user@example.com",
  "displayName": "John Doe",
  "username": "johndoe123",           // Unique, lowercase
  "photoURL": "https://...",          // Profile picture
  "bio": "Plant enthusiast...",
  
  // Timestamps
  "createdAt": Timestamp,
  "updatedAt": Timestamp,
  "lastLoginAt": Timestamp,
  
  // Settings
  "settings": {
    "theme": "dark",                  // light|dark|system
    "language": "en",
    "notifications": {
      "push": true,
      "email": true,
      "forumReplies": true,
      "likes": true,
      "mentions": true
    },
    "privacy": {
      "profilePublic": true,
      "showEmail": false,
      "showCollection": true
    }
  },
  
  // Stats (denormalized for quick access)
  "stats": {
    "plantsIdentified": 42,
    "collectionSize": 28,
    "forumPosts": 15,
    "forumReplies": 67,
    "likesReceived": 234,
    "solutionsProvided": 8
  },
  
  // Platform-specific
  "platform": "mobile",               // mobile|web|both
  "deviceTokens": ["fcm_token_1"],   // For push notifications
  
  // Moderation
  "role": "user",                     // user|moderator|admin
  "verified": false,                  // Verified expert badge
  "banned": false,
  "banReason": null,
  "banExpiresAt": null
}
```

**Indexes**:
- `username` (unique)
- `email` (unique)
- `createdAt` (descending)
- Composite: `banned == false`, `role`, `stats.plantsIdentified`

---

### 2. **plantIdentifications** Collection

Stores all plant identification requests and results.

**Document ID**: Auto-generated

```javascript
{
  // Document ID: auto-generated
  
  // User Reference
  "userId": "firebase_auth_uid",
  "userDisplayName": "John Doe",     // Denormalized
  
  // Image Data
  "imageUrl": "gs://bucket/path",    // Cloud Storage path
  "imageThumbnail": "gs://...",      // Thumbnail for lists
  "imageMetadata": {
    "width": 1920,
    "height": 1080,
    "size": 2048576,                 // bytes
    "mimeType": "image/jpeg"
  },
  
  // Identification Request
  "status": "completed",              // pending|processing|completed|failed
  "requestedAt": Timestamp,
  "completedAt": Timestamp,
  
  // Plant.id API Response
  "apiProvider": "plant.id",
  "apiRequestId": "external_id",
  "apiCreditsUsed": 1,
  
  // Primary Result
  "plant": {
    "name": "Monstera deliciosa",
    "scientificName": "Monstera deliciosa",
    "commonNames": ["Swiss Cheese Plant", "Split-leaf Philodendron"],
    "confidence": 0.95,
    "family": "Araceae",
    "genus": "Monstera",
    "species": "deliciosa"
  },
  
  // Alternative Matches
  "alternatives": [
    {
      "name": "Monstera adansonii",
      "scientificName": "Monstera adansonii",
      "confidence": 0.78
    }
  ],
  
  // Plant Information
  "description": "A species of flowering plant...",
  "nativeRegion": "Central America",
  "category": "houseplant",           // houseplant|outdoor|succulent|tree|etc
  
  // Care Instructions
  "care": {
    "watering": {
      "frequency": "weekly",
      "amount": "moderate",
      "instructions": "Water when top 2 inches of soil are dry..."
    },
    "sunlight": {
      "requirement": "indirect",      // direct|indirect|shade
      "hours": "4-6",
      "instructions": "Bright indirect light is ideal..."
    },
    "temperature": {
      "min": 65,                      // Fahrenheit
      "max": 85,
      "optimal": 75,
      "instructions": "Keep above 65°F..."
    },
    "humidity": {
      "level": "high",                // low|medium|high
      "percentage": "60-80",
      "instructions": "Mist regularly or use humidifier..."
    },
    "soil": {
      "type": "well-draining",
      "ph": "5.5-7.0",
      "instructions": "Use peat-based potting mix..."
    },
    "fertilizer": {
      "frequency": "monthly",
      "type": "balanced",
      "instructions": "Feed monthly during growing season..."
    },
    "difficulty": "easy"              // easy|medium|hard
  },
  
  // Disease Detection (optional)
  "healthCheck": {
    "healthy": true,
    "issues": [],
    "confidence": 0.92
  },
  
  // User Actions
  "saved": true,                      // Saved to collection
  "shared": false,
  "notes": "",                        // User's personal notes
  
  // Metadata
  "platform": "mobile",               // mobile|web
  "appVersion": "1.0.0",
  "location": {                       // Optional, if user grants permission
    "latitude": 37.7749,
    "longitude": -122.4194,
    "city": "San Francisco",
    "country": "US"
  }
}
```

**Indexes**:
- `userId`, `requestedAt` (descending) - User's history
- `userId`, `saved == true`, `requestedAt` - Saved collection
- `plant.name` - Search by plant name
- `status`, `requestedAt` - Failed identifications
- Composite: `userId`, `plant.category`, `requestedAt`

**Subcollections**:
- None (flat structure for simpler queries)

---

### 3. **userPlantCollections** Collection

Organized collections of saved plants (alternative to filtering plantIdentifications).

**Document ID**: Auto-generated

```javascript
{
  // Document ID: auto-generated
  
  "userId": "firebase_auth_uid",
  "plantIdentificationId": "plant_id_ref",  // Reference to plantIdentifications doc
  
  // Denormalized for quick display
  "plantName": "Monstera deliciosa",
  "scientificName": "Monstera deliciosa",
  "thumbnailUrl": "gs://...",
  "category": "houseplant",
  
  // User customization
  "customName": "My Monstera Baby",   // User's nickname for this plant
  "location": "Living Room",          // Where they keep it
  "acquiredDate": Timestamp,
  "notes": "Birthday gift from mom",
  
  // Care tracking (future feature)
  "lastWatered": Timestamp,
  "lastFertilized": Timestamp,
  "careReminders": {
    "watering": {
      "enabled": true,
      "frequency": "weekly",
      "nextDue": Timestamp
    }
  },
  
  // Organization
  "tags": ["favorite", "indoor"],
  "archived": false,
  
  // Timestamps
  "addedAt": Timestamp,
  "updatedAt": Timestamp
}
```

**Indexes**:
- `userId`, `addedAt` (descending)
- `userId`, `archived == false`, `addedAt`
- `userId`, `category`
- `userId`, `tags` (array-contains)

---

### 4. **notifications** Collection

User notifications for real-time updates.

**Document ID**: Auto-generated

```javascript
{
  // Document ID: auto-generated
  
  "userId": "firebase_auth_uid",
  "type": "forum_reply",              // forum_reply|like|mention|follow|system
  
  // Content
  "title": "New reply to your post",
  "message": "Marcus replied to 'Help with yellowing leaves'",
  "icon": "reply",
  
  // Action
  "actionUrl": "/forum/topic/xyz",    // Deep link
  "actionData": {
    "topicId": "xyz",
    "replyId": "abc"
  },
  
  // Related User (if applicable)
  "fromUserId": "other_user_uid",
  "fromUserName": "Marcus",
  "fromUserPhoto": "https://...",
  
  // State
  "read": false,
  "clicked": false,
  
  // Timestamps
  "createdAt": Timestamp,
  "readAt": null,
  "expiresAt": Timestamp              // Auto-delete after 30 days
}
```

**Indexes**:
- `userId`, `read == false`, `createdAt` (descending)
- `userId`, `type`, `createdAt`
- `expiresAt` (for TTL cleanup)

---

### 5. **deviceTokens** Collection

FCM tokens for push notifications (separate for better management).

**Document ID**: Token hash or user-device combo

```javascript
{
  // Document ID: hash of token or userId_deviceId
  
  "userId": "firebase_auth_uid",
  "token": "fcm_device_token",
  "platform": "ios",                  // ios|android
  "deviceId": "unique_device_id",
  "appVersion": "1.0.0",
  
  // Timestamps
  "createdAt": Timestamp,
  "lastUsedAt": Timestamp,
  "expiresAt": Timestamp
}
```

**Indexes**:
- `userId`
- `token` (unique)
- `expiresAt`

---

### 6. **forumTopics** Collection (Mobile Cache)

Cached forum topics for offline browsing on mobile.

**Document ID**: Same as PostgreSQL topic ID

```javascript
{
  // Document ID: postgres_topic_id
  
  // Synchronized from PostgreSQL
  "id": 123,                          // PostgreSQL ID
  "title": "Help with yellowing leaves",
  "slug": "help-with-yellowing-leaves",
  "categoryId": 1,
  "categoryName": "Plant Care",
  
  // Author (denormalized)
  "authorId": "firebase_uid",
  "authorName": "Sarah",
  "authorPhoto": "https://...",
  "authorVerified": false,
  
  // Content
  "content": "My monstera has yellowing...",  // First 200 chars
  "contentPreview": "My monstera has...",     // 100 chars
  "hasImages": true,
  
  // Metadata
  "tags": ["monstera", "yellowing", "help"],
  "createdAt": Timestamp,
  "updatedAt": Timestamp,
  "lastActivityAt": Timestamp,
  
  // Stats
  "viewCount": 234,
  "replyCount": 12,
  "likeCount": 5,
  
  // State
  "pinned": false,
  "locked": false,
  "solved": false,
  
  // Sync
  "syncedAt": Timestamp,
  "syncVersion": 1
}
```

**Indexes**:
- `categoryId`, `lastActivityAt` (descending)
- `authorId`, `createdAt`
- `tags` (array-contains)
- `pinned == true`, `lastActivityAt`

**Note**: This is a read-only cache. All writes go to PostgreSQL and sync back.

---

### 7. **analytics** Collection

Anonymous usage analytics for insights.

**Document ID**: Auto-generated or date-based

```javascript
{
  // Document ID: YYYY-MM-DD or auto
  
  "eventType": "identification",      // identification|forum_view|share|etc
  "userId": "firebase_uid",           // Anonymous if not logged in
  "sessionId": "session_uuid",
  
  // Event data (flexible)
  "data": {
    "plantName": "Monstera deliciosa",
    "confidence": 0.95,
    "processingTime": 2.3             // seconds
  },
  
  // Context
  "platform": "mobile",
  "appVersion": "1.0.0",
  "osVersion": "iOS 17",
  "deviceModel": "iPhone 14",
  "country": "US",
  
  "timestamp": Timestamp
}
```

**Indexes**:
- `eventType`, `timestamp`
- `userId`, `timestamp`
- `timestamp` (for time-series queries)

---

## PostgreSQL Schema

Django/Wagtail models with standard Django ORM conventions.

### Schema Diagram

```
┌─────────────────┐
│  auth_user      │ (Django built-in)
│  ─────────────  │
│  id (PK)        │
│  username       │
│  email          │
│  password       │
│  ...            │
└────────┬────────┘
         │
         ├──────────────────────────────┐
         │                              │
┌────────┴────────┐            ┌────────┴────────┐
│  UserProfile    │            │  ForumTopic     │
│  ─────────────  │            │  ─────────────  │
│  id (PK)        │            │  id (PK)        │
│  user_id (FK)   │            │  author_id (FK) │
│  firebase_uid   │            │  category_id    │
│  display_name   │            │  title          │
│  bio            │            │  slug           │
│  ...            │            │  content        │
└─────────────────┘            │  ...            │
                               └────────┬────────┘
                                        │
                               ┌────────┴────────┐
                               │  ForumReply     │
                               │  ─────────────  │
                               │  id (PK)        │
                               │  topic_id (FK)  │
                               │  author_id (FK) │
                               │  parent_id (FK) │
                               │  content        │
                               │  ...            │
                               └─────────────────┘
```

---

### 1. **auth_user** (Django Built-in)

Django's default user model (extended via UserProfile).

```python
# Django default fields:
# id, username, email, password, first_name, last_name,
# is_staff, is_active, is_superuser, date_joined, last_login
```

---

### 2. **user_profiles** Table

Extended user information for web platform.

```sql
CREATE TABLE user_profiles (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Foreign Key to Django User
    user_id INTEGER UNIQUE NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    
    -- Firebase Sync
    firebase_uid VARCHAR(128) UNIQUE,  -- Links to Firebase Auth
    firebase_sync_enabled BOOLEAN DEFAULT TRUE,
    last_firebase_sync TIMESTAMP,
    
    -- Profile Information
    display_name VARCHAR(50) NOT NULL,
    username VARCHAR(30) UNIQUE NOT NULL,  -- Lowercase, URL-safe
    bio TEXT,
    avatar_url VARCHAR(500),
    location VARCHAR(100),
    website_url VARCHAR(200),
    
    -- Social Links
    twitter_handle VARCHAR(50),
    instagram_handle VARCHAR(50),
    
    -- Verification
    verified_expert BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,
    verification_type VARCHAR(20),  -- botanist|horticulturist|educator
    
    -- Stats (cached from activity)
    forum_posts_count INTEGER DEFAULT 0,
    forum_replies_count INTEGER DEFAULT 0,
    likes_received_count INTEGER DEFAULT 0,
    solutions_provided_count INTEGER DEFAULT 0,
    reputation_score INTEGER DEFAULT 0,
    
    -- Settings
    email_notifications BOOLEAN DEFAULT TRUE,
    forum_notifications BOOLEAN DEFAULT TRUE,
    newsletter_subscribed BOOLEAN DEFAULT FALSE,
    profile_public BOOLEAN DEFAULT TRUE,
    show_email BOOLEAN DEFAULT FALSE,
    
    -- Moderation
    role VARCHAR(20) DEFAULT 'user',  -- user|moderator|admin
    banned BOOLEAN DEFAULT FALSE,
    ban_reason TEXT,
    ban_expires_at TIMESTAMP,
    moderation_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_user_profiles_firebase_uid ON user_profiles(firebase_uid);
CREATE INDEX idx_user_profiles_username ON user_profiles(username);
CREATE INDEX idx_user_profiles_role ON user_profiles(role);
CREATE INDEX idx_user_profiles_verified ON user_profiles(verified_expert);
CREATE INDEX idx_user_profiles_reputation ON user_profiles(reputation_score DESC);
```

---

### 3. **forum_categories** Table

Forum topic categories.

```sql
CREATE TABLE forum_categories (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Category Info
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    icon VARCHAR(50),  -- Icon name or emoji
    color VARCHAR(7),  -- Hex color code
    
    -- Ordering & Organization
    display_order INTEGER DEFAULT 0,
    parent_id INTEGER REFERENCES forum_categories(id) ON DELETE CASCADE,
    
    -- Stats (cached)
    topic_count INTEGER DEFAULT 0,
    post_count INTEGER DEFAULT 0,
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    require_approval BOOLEAN DEFAULT FALSE,
    moderators_only BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_forum_categories_slug ON forum_categories(slug);
CREATE INDEX idx_forum_categories_parent ON forum_categories(parent_id);
CREATE INDEX idx_forum_categories_order ON forum_categories(display_order);

-- Sample Data
INSERT INTO forum_categories (name, slug, description, color, display_order) VALUES
('Plant Care', 'plant-care', 'General plant care questions and tips', '#4CAF50', 1),
('Plant Problems', 'plant-problems', 'Diagnose and solve plant issues', '#F44336', 2),
('Beginner Guide', 'beginner-guide', 'New to plants? Start here!', '#2196F3', 3),
('Show & Tell', 'show-and-tell', 'Share your plant photos and stories', '#9C27B0', 4),
('Plant Identification', 'plant-identification', 'Help identifying plants', '#FF9800', 5);
```

---

### 4. **forum_topics** Table

Forum discussion threads.

```sql
CREATE TABLE forum_topics (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Relationships
    category_id INTEGER NOT NULL REFERENCES forum_categories(id) ON DELETE RESTRICT,
    author_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    
    -- Content
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(250) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    content_html TEXT,  -- Rendered HTML from markdown
    
    -- Status
    status VARCHAR(20) DEFAULT 'published',  -- draft|published|locked|archived
    pinned BOOLEAN DEFAULT FALSE,
    locked BOOLEAN DEFAULT FALSE,
    solved BOOLEAN DEFAULT FALSE,
    featured BOOLEAN DEFAULT FALSE,
    
    -- Stats (cached for performance)
    view_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    
    -- Activity tracking
    last_reply_at TIMESTAMP,
    last_reply_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    
    -- Moderation
    requires_approval BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP,
    approved_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    deleted_at TIMESTAMP,
    deleted_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    
    -- SEO
    meta_description TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_forum_topics_category ON forum_topics(category_id, last_reply_at DESC);
CREATE INDEX idx_forum_topics_author ON forum_topics(author_id, created_at DESC);
CREATE INDEX idx_forum_topics_slug ON forum_topics(slug);
CREATE INDEX idx_forum_topics_status ON forum_topics(status);
CREATE INDEX idx_forum_topics_pinned ON forum_topics(pinned, last_reply_at DESC);
CREATE INDEX idx_forum_topics_solved ON forum_topics(solved);
CREATE INDEX idx_forum_topics_activity ON forum_topics(last_reply_at DESC);

-- Full-text search
CREATE INDEX idx_forum_topics_search ON forum_topics USING GIN (to_tsvector('english', title || ' ' || content));
```

---

### 5. **forum_replies** Table

Replies to forum topics.

```sql
CREATE TABLE forum_replies (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Relationships
    topic_id INTEGER NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES forum_replies(id) ON DELETE CASCADE,  -- For nested replies
    
    -- Content
    content TEXT NOT NULL,
    content_html TEXT,  -- Rendered HTML
    
    -- Status
    is_solution BOOLEAN DEFAULT FALSE,  -- Marked as solution by topic author
    marked_solution_at TIMESTAMP,
    
    -- Stats
    like_count INTEGER DEFAULT 0,
    
    -- Moderation
    edited BOOLEAN DEFAULT FALSE,
    edited_at TIMESTAMP,
    edited_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    deleted_at TIMESTAMP,
    deleted_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_forum_replies_topic ON forum_replies(topic_id, created_at);
CREATE INDEX idx_forum_replies_author ON forum_replies(author_id, created_at DESC);
CREATE INDEX idx_forum_replies_parent ON forum_replies(parent_id);
CREATE INDEX idx_forum_replies_solution ON forum_replies(is_solution);

-- Full-text search
CREATE INDEX idx_forum_replies_search ON forum_replies USING GIN (to_tsvector('english', content));
```

---

### 6. **forum_tags** Table

Tags for categorizing topics.

```sql
CREATE TABLE forum_tags (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Tag Info
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    
    -- Stats
    usage_count INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_forum_tags_slug ON forum_tags(slug);
CREATE INDEX idx_forum_tags_usage ON forum_tags(usage_count DESC);
```

---

### 7. **forum_topic_tags** Table (Many-to-Many)

Links topics to tags.

```sql
CREATE TABLE forum_topic_tags (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES forum_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(topic_id, tag_id)
);

-- Indexes
CREATE INDEX idx_forum_topic_tags_topic ON forum_topic_tags(topic_id);
CREATE INDEX idx_forum_topic_tags_tag ON forum_topic_tags(tag_id);
```

---

### 8. **forum_likes** Table

Track likes on topics and replies.

```sql
CREATE TABLE forum_likes (
    id SERIAL PRIMARY KEY,
    
    -- User who liked
    user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    
    -- Polymorphic: either topic or reply
    content_type VARCHAR(10) NOT NULL,  -- 'topic' or 'reply'
    object_id INTEGER NOT NULL,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, content_type, object_id)
);

-- Indexes
CREATE INDEX idx_forum_likes_user ON forum_likes(user_id);
CREATE INDEX idx_forum_likes_object ON forum_likes(content_type, object_id);
```

---

### 9. **forum_attachments** Table

File attachments for forum posts.

```sql
CREATE TABLE forum_attachments (
    id SERIAL PRIMARY KEY,
    
    -- User who uploaded
    user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    
    -- Attached to (polymorphic)
    content_type VARCHAR(10) NOT NULL,  -- 'topic' or 'reply'
    object_id INTEGER NOT NULL,
    
    -- File info
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,  -- bytes
    file_type VARCHAR(100) NOT NULL,  -- MIME type
    file_url VARCHAR(500) NOT NULL,  -- Cloud Storage URL
    thumbnail_url VARCHAR(500),
    
    -- Image metadata (if image)
    width INTEGER,
    height INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_forum_attachments_object ON forum_attachments(content_type, object_id);
CREATE INDEX idx_forum_attachments_user ON forum_attachments(user_id);
```

---

### 10. **forum_subscriptions** Table

User subscriptions to topics (for notifications).

```sql
CREATE TABLE forum_subscriptions (
    id SERIAL PRIMARY KEY,
    
    user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
    
    -- Settings
    notify_on_reply BOOLEAN DEFAULT TRUE,
    notify_on_solution BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, topic_id)
);

-- Indexes
CREATE INDEX idx_forum_subscriptions_user ON forum_subscriptions(user_id);
CREATE INDEX idx_forum_subscriptions_topic ON forum_subscriptions(topic_id);
```

---

### 11. **blog_posts** Table (Wagtail)

Blog posts managed by Wagtail CMS.

```sql
-- Note: Wagtail creates its own tables (wagtailcore_page, etc.)
-- This is a simplified representation of the final published data

CREATE TABLE blog_posts (
    -- Primary Key (Wagtail Page)
    id SERIAL PRIMARY KEY,
    
    -- Wagtail Page fields
    page_ptr_id INTEGER UNIQUE NOT NULL,  -- Links to wagtailcore_page
    
    -- Content
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    subtitle VARCHAR(255),
    excerpt TEXT,
    body TEXT,  -- StreamField JSON representation
    
    -- Author
    author_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    
    -- Media
    featured_image_id INTEGER,  -- Wagtail Image FK
    
    -- Categories/Tags
    categories TEXT[],  -- Array of category names
    tags TEXT[],
    
    -- SEO
    seo_title VARCHAR(255),
    seo_description TEXT,
    og_image_id INTEGER,
    
    -- Stats
    view_count INTEGER DEFAULT 0,
    read_time INTEGER,  -- Estimated minutes
    
    -- Publishing
    status VARCHAR(20) DEFAULT 'draft',  -- draft|review|published
    published_at TIMESTAMP,
    featured BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Search
    search_vector tsvector
);

-- Indexes
CREATE INDEX idx_blog_posts_slug ON blog_posts(slug);
CREATE INDEX idx_blog_posts_author ON blog_posts(author_id);
CREATE INDEX idx_blog_posts_published ON blog_posts(published_at DESC) WHERE status = 'published';
CREATE INDEX idx_blog_posts_featured ON blog_posts(featured, published_at DESC);
CREATE INDEX idx_blog_posts_search ON blog_posts USING GIN (search_vector);
CREATE INDEX idx_blog_posts_categories ON blog_posts USING GIN (categories);
CREATE INDEX idx_blog_posts_tags ON blog_posts USING GIN (tags);
```

---

### 12. **moderation_logs** Table

Track all moderation actions.

```sql
CREATE TABLE moderation_logs (
    id SERIAL PRIMARY KEY,
    
    -- Who performed the action
    moderator_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    
    -- What was moderated
    content_type VARCHAR(20) NOT NULL,  -- topic|reply|user|post
    object_id INTEGER NOT NULL,
    
    -- Action details
    action VARCHAR(50) NOT NULL,  -- delete|lock|pin|ban|approve|etc
    reason TEXT,
    details JSONB,  -- Additional context
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_moderation_logs_moderator ON moderation_logs(moderator_id);
CREATE INDEX idx_moderation_logs_object ON moderation_logs(content_type, object_id);
CREATE INDEX idx_moderation_logs_action ON moderation_logs(action);
CREATE INDEX idx_moderation_logs_created ON moderation_logs(created_at DESC);
```

---

### 13. **email_subscriptions** Table

Newsletter and notification subscriptions.

```sql
CREATE TABLE email_subscriptions (
    id SERIAL PRIMARY KEY,
    
    -- Subscriber
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,  -- Null if not registered
    email VARCHAR(255) UNIQUE NOT NULL,
    
    -- Subscription types
    newsletter BOOLEAN DEFAULT TRUE,
    blog_updates BOOLEAN DEFAULT TRUE,
    forum_digest BOOLEAN DEFAULT FALSE,
    
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(100),
    verified_at TIMESTAMP,
    
    -- Management
    unsubscribe_token VARCHAR(100) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_email_subscriptions_email ON email_subscriptions(email);
CREATE INDEX idx_email_subscriptions_token ON email_subscriptions(unsubscribe_token);
CREATE INDEX idx_email_subscriptions_active ON email_subscriptions(active);
```

---

## Data Synchronization

### Firebase ↔ PostgreSQL Sync Strategy

#### User Profile Sync

**Direction**: Bidirectional  
**Trigger**: Cloud Functions

**Flow**:
1. User signs up via Firebase Auth → Creates Firestore user → Cloud Function creates PostgreSQL user
2. User updates profile on mobile → Firestore update → Cloud Function syncs to PostgreSQL
3. User updates profile on web → PostgreSQL update → Cloud Function syncs to Firestore

**Implementation**:
```javascript
// Cloud Function: onUserCreate
exports.onUserCreate = functions.auth.user().onCreate(async (user) => {
  // Create Firestore document
  await db.collection('users').doc(user.uid).set({
    uid: user.uid,
    email: user.email,
    displayName: user.displayName,
    photoURL: user.photoURL,
    createdAt: FieldValue.serverTimestamp()
  });
  
  // Create PostgreSQL record via API
  await axios.post(`${API_URL}/api/users/sync`, {
    firebase_uid: user.uid,
    email: user.email,
    display_name: user.displayName
  });
});

// Cloud Function: onUserProfileUpdate (Firestore → PostgreSQL)
exports.onUserProfileUpdate = functions.firestore
  .document('users/{uid}')
  .onUpdate(async (change, context) => {
    const newData = change.after.data();
    await axios.put(`${API_URL}/api/users/${context.params.uid}/sync`, newData);
  });
```

---

#### Forum Topic Cache Sync

**Direction**: PostgreSQL → Firestore (one-way)  
**Trigger**: Django signals or scheduled task

**Flow**:
1. User creates/updates topic on web → PostgreSQL update
2. Django signal triggers → Pushes to Firestore for mobile cache
3. Mobile app reads from Firestore cache (fast, offline-capable)
4. Mobile app writes go to PostgreSQL API endpoint

**Implementation**:
```python
# Django signal
from django.db.models.signals import post_save
from django.dispatch import receiver
from firebase_admin import firestore

@receiver(post_save, sender=ForumTopic)
def sync_topic_to_firestore(sender, instance, **kwargs):
    db = firestore.client()
    db.collection('forumTopics').document(str(instance.id)).set({
        'id': instance.id,
        'title': instance.title,
        'slug': instance.slug,
        'categoryId': instance.category_id,
        'categoryName': instance.category.name,
        'authorId': instance.author.profile.firebase_uid,
        'authorName': instance.author.profile.display_name,
        'content': instance.content[:200],  # Preview
        'createdAt': instance.created_at,
        'replyCount': instance.reply_count,
        'syncedAt': firestore.SERVER_TIMESTAMP
    }, merge=True)
```

---

#### Analytics Aggregation

**Direction**: Firestore → PostgreSQL (batch)  
**Frequency**: Daily/Weekly batch jobs

**Flow**:
1. Mobile app logs events to Firestore (fast, offline)
2. Scheduled Cloud Function aggregates daily
3. Pushes summary data to PostgreSQL for reporting

---

## Security Rules

### Firebase Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Helper functions
    function isSignedIn() {
      return request.auth != null;
    }
    
    function isOwner(userId) {
      return request.auth.uid == userId;
    }
    
    function isAdmin() {
      return isSignedIn() && 
             get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    // Users collection
    match /users/{userId} {
      // Anyone can read public profiles
      allow read: if true;
      
      // Users can only write their own profile
      allow create: if isSignedIn() && isOwner(userId);
      allow update: if isSignedIn() && isOwner(userId);
      allow delete: if isAdmin();
    }
    
    // Plant identifications
    match /plantIdentifications/{identificationId} {
      // Users can read their own identifications
      allow read: if isSignedIn() && resource.data.userId == request.auth.uid;
      
      // Users can create identifications
      allow create: if isSignedIn() && request.resource.data.userId == request.auth.uid;
      
      // Users can update their own (for notes, saved status)
      allow update: if isSignedIn() && resource.data.userId == request.auth.uid;
      
      // Users can delete their own
      allow delete: if isSignedIn() && resource.data.userId == request.auth.uid;
    }
    
    // User plant collections
    match /userPlantCollections/{collectionId} {
      allow read: if isSignedIn() && resource.data.userId == request.auth.uid;
      allow create: if isSignedIn() && request.resource.data.userId == request.auth.uid;
      allow update: if isSignedIn() && resource.data.userId == request.auth.uid;
      allow delete: if isSignedIn() && resource.data.userId == request.auth.uid;
    }
    
    // Notifications
    match /notifications/{notificationId} {
      // Users can read their own notifications
      allow read: if isSignedIn() && resource.data.userId == request.auth.uid;
      
      // Only system/cloud functions can create notifications
      allow create: if false;  // Use Cloud Functions
      
      // Users can mark as read
      allow update: if isSignedIn() && 
                      resource.data.userId == request.auth.uid &&
                      request.resource.data.diff(resource.data).affectedKeys().hasOnly(['read', 'readAt', 'clicked']);
      
      allow delete: if isSignedIn() && resource.data.userId == request.auth.uid;
    }
    
    // Forum topics cache (read-only for mobile)
    match /forumTopics/{topicId} {
      allow read: if true;  // Public forum
      allow write: if false;  // Synced from PostgreSQL only
    }
    
    // Device tokens
    match /deviceTokens/{tokenId} {
      allow read: if isSignedIn() && resource.data.userId == request.auth.uid;
      allow create, update: if isSignedIn() && request.resource.data.userId == request.auth.uid;
      allow delete: if isSignedIn() && resource.data.userId == request.auth.uid;
    }
    
    // Analytics (write-only for users)
    match /analytics/{eventId} {
      allow read: if isAdmin();
      allow create: if true;  // Anyone can log events
      allow update, delete: if false;
    }
  }
}
```

---

### PostgreSQL Row-Level Security (RLS)

```sql
-- Enable RLS on sensitive tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_replies ENABLE ROW LEVEL SECURITY;

-- User can view their own profile
CREATE POLICY user_profile_select ON user_profiles
    FOR SELECT
    USING (user_id = current_user_id() OR profile_public = TRUE);

-- User can update their own profile
CREATE POLICY user_profile_update ON user_profiles
    FOR UPDATE
    USING (user_id = current_user_id());

-- Anyone can view published forum content
CREATE POLICY forum_topic_select ON forum_topics
    FOR SELECT
    USING (status = 'published' OR author_id = current_user_id());

-- Users can create topics
CREATE POLICY forum_topic_insert ON forum_topics
    FOR INSERT
    WITH CHECK (author_id = current_user_id());

-- Users can update their own topics
CREATE POLICY forum_topic_update ON forum_topics
    FOR UPDATE
    USING (author_id = current_user_id());
```

---

## Indexes & Performance

### Firestore Composite Indexes

Required composite indexes for complex queries:

```yaml
# firestore.indexes.json
{
  "indexes": [
    {
      "collectionGroup": "plantIdentifications",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "userId", "order": "ASCENDING" },
        { "fieldPath": "saved", "order": "ASCENDING" },
        { "fieldPath": "requestedAt", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "plantIdentifications",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "userId", "order": "ASCENDING" },
        { "fieldPath": "plant.category", "order": "ASCENDING" },
        { "fieldPath": "requestedAt", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "notifications",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "userId", "order": "ASCENDING" },
        { "fieldPath": "read", "order": "ASCENDING" },
        { "fieldPath": "createdAt", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "forumTopics",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "categoryId", "order": "ASCENDING" },
        { "fieldPath": "pinned", "order": "DESCENDING" },
        { "fieldPath": "lastActivityAt", "order": "DESCENDING" }
      ]
    }
  ]
}
```

### PostgreSQL Indexes Summary

Key indexes for performance:

```sql
-- Full-text search indexes
CREATE INDEX idx_forum_topics_fulltext ON forum_topics 
    USING GIN (to_tsvector('english', title || ' ' || content));

CREATE INDEX idx_forum_replies_fulltext ON forum_replies 
    USING GIN (to_tsvector('english', content));

CREATE INDEX idx_blog_posts_fulltext ON blog_posts 
    USING GIN (search_vector);

-- Activity indexes (hot paths)
CREATE INDEX idx_forum_topics_hot ON forum_topics(last_reply_at DESC, view_count DESC) 
    WHERE status = 'published';

CREATE INDEX idx_forum_topics_unanswered ON forum_topics(created_at DESC) 
    WHERE reply_count = 0 AND status = 'published';

-- User activity
CREATE INDEX idx_forum_replies_user_activity ON forum_replies(author_id, created_at DESC) 
    WHERE deleted_at IS NULL;
```

---

## Migration Strategy

### Phase 1: Initial Setup

1. **Create Firebase project**
   - Enable Authentication (Email, Google, Apple)
   - Create Firestore database
   - Set up Cloud Storage buckets
   - Deploy security rules

2. **Create PostgreSQL database**
   - Set up Django project
   - Run migrations for auth and profiles
   - Create forum tables
   - Set up Wagtail

3. **Link Firebase ↔ PostgreSQL**
   - Deploy Cloud Functions for sync
   - Set up webhook endpoints
   - Test bidirectional sync

### Phase 2: Data Population

1. **Seed initial data**
   - Forum categories
   - Sample tags
   - Admin users
   - Sample blog posts

2. **Set up indexes**
   - Create all indexes
   - Analyze query performance
   - Optimize as needed

### Phase 3: Existing Data Migration (If Applicable)

If migrating from existing Plant ID Community:

1. **Export from current database**
2. **Transform to new schema**
3. **Import to PostgreSQL**
4. **Sync initial data to Firestore**
5. **Verify data integrity**

---

## Data Retention & Cleanup

### Firestore TTL Policies

```javascript
// Cloud Function: Daily cleanup
exports.dailyCleanup = functions.pubsub
  .schedule('0 2 * * *')  // 2 AM daily
  .onRun(async (context) => {
    const db = admin.firestore();
    const now = admin.firestore.Timestamp.now();
    const thirtyDaysAgo = new Date(now.toDate() - 30 * 24 * 60 * 60 * 1000);
    
    // Delete old notifications
    const expiredNotifications = await db.collection('notifications')
      .where('expiresAt', '<', thirtyDaysAgo)
      .get();
    
    const batch = db.batch();
    expiredNotifications.forEach(doc => batch.delete(doc.ref));
    await batch.commit();
    
    // Delete expired device tokens
    // Archive old analytics
    // etc.
  });
```

### PostgreSQL Archival

```sql
-- Archive old forum topics (>1 year inactive)
CREATE TABLE forum_topics_archive (LIKE forum_topics INCLUDING ALL);

-- Move to archive
INSERT INTO forum_topics_archive 
SELECT * FROM forum_topics 
WHERE last_reply_at < CURRENT_DATE - INTERVAL '1 year' 
  AND view_count < 10;

DELETE FROM forum_topics 
WHERE id IN (SELECT id FROM forum_topics_archive);
```

---

## Backup Strategy

### Firebase Backups

```bash
# Automated daily backups via Cloud Functions
gcloud firestore export gs://plant-id-backups/$(date +%Y%m%d)
```

### PostgreSQL Backups

```bash
# Daily automated backups
pg_dump -Fc plant_id_db > backup_$(date +%Y%m%d).dump

# Restore
pg_restore -d plant_id_db backup_20251021.dump
```

---

## Summary

### Database Distribution

| Feature | Database | Reason |
|---------|----------|--------|
| User Authentication | Firebase Auth | Cross-platform, easy integration |
| Plant Identifications | Firestore | Offline support, real-time sync |
| User Collections | Firestore | Offline support, user-specific |
| Forum Content | PostgreSQL | Complex queries, relational data |
| Blog Content | PostgreSQL | Wagtail CMS integration |
| User Profiles | Both | Synced via Cloud Functions |
| Notifications | Firestore | Real-time push notifications |
| Analytics | Both | Events in Firestore, reports in PostgreSQL |

### Key Design Decisions

1. ✅ **Hybrid approach** balances mobile-first (Firestore) with web CMS (PostgreSQL)
2. ✅ **Denormalization in Firestore** for query performance
3. ✅ **Cache forum data in Firestore** for offline mobile browsing
4. ✅ **Cloud Functions handle sync** between databases
5. ✅ **Security rules** enforce data access control
6. ✅ **Comprehensive indexes** for performance
7. ✅ **Clear separation of concerns** between mobile and web data

---

**Document Status**: ✅ Complete v1.0  
**Last Updated**: October 21, 2025  
**Next Steps**: Create API documentation and implement database setup  
**Related Documents**: User Stories, Master Plan, Technology Stack
