# Database Schema Documentation

**Date**: October 21, 2025  
**Purpose**: Complete database schema for Plant ID Community platform  
**Databases**: PostgreSQL (Django/Wagtail) + Firestore (Firebase for mobile)

---

## Table of Contents

1. [Overview](#overview)
2. [PostgreSQL Schema (Django/Wagtail)](#postgresql-schema)
3. [Firestore Schema (Firebase/Mobile)](#firestore-schema)
4. [Database Architecture](#database-architecture)
5. [Data Flow & Synchronization](#data-flow--synchronization)
6. [Migration Strategy](#migration-strategy)
7. [Indexes & Performance](#indexes--performance)

---

## Overview

### Dual Database Strategy

The Plant ID Community uses a **hybrid database architecture**:

```
┌─────────────────────────────────────────────────────┐
│                    WEB APP                          │
│          (Django + Wagtail + React)                 │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │         PostgreSQL Database                  │  │
│  │  ├─ Blog & CMS Content (Wagtail)            │  │
│  │  ├─ Forum (Django Machina)                  │  │
│  │  ├─ User Profiles & Authentication          │  │
│  │  ├─ Plant Species Database (reference)      │  │
│  │  └─ Community Features                      │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                          ↕
                   Firebase Auth
                   (Shared Users)
                          ↕
┌─────────────────────────────────────────────────────┐
│              FLUTTER MOBILE APP                     │
│               (iOS + Android)                       │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │      Cloud Firestore Database                │  │
│  │  ├─ Plant Identification Records            │  │
│  │  ├─ User Plant Collections (mobile)         │  │
│  │  ├─ Disease Diagnosis Results               │  │
│  │  ├─ Image Metadata                          │  │
│  │  └─ User Preferences & Settings             │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │      Firebase Cloud Storage                  │  │
│  │  └─ Plant Identification Images             │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Database Purpose Division

| Database | Purpose | Access |
|----------|---------|--------|
| **PostgreSQL** | CMS content, forum, blog, user profiles, reference data | Web app (primary), Mobile app (read-only via API) |
| **Firestore** | Mobile plant ID records, user collections, real-time data | Mobile app (primary), Web app (optional sync) |
| **Firebase Storage** | Plant images uploaded from mobile | Mobile app (primary) |
| **Firebase Auth** | Unified authentication | Both web and mobile |

---

## PostgreSQL Schema

### Schema Overview

The PostgreSQL database contains **7 Django apps** with multiple models:

1. **users** - User accounts and social features
2. **plant_identification** - Plant species database and identification requests
3. **forum_integration** - Forum system (Django Machina + Wagtail)
4. **blog** - Blog posts (Wagtail CMS)
5. **garden_calendar** - Community events and calendar
6. **search** - Search functionality and saved searches
7. **core** - Shared utilities

### 1. Users App (`auth_user` table + related)

#### 1.1 User Model (extends `AbstractUser`)

**Table**: `auth_user`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `uuid` | UUID | UNIQUE, NOT NULL | Secure reference ID |
| `username` | VARCHAR(150) | UNIQUE, NOT NULL | Username |
| `email` | VARCHAR(254) | UNIQUE | Email address |
| `password` | VARCHAR(128) | NOT NULL | Hashed password |
| `first_name` | VARCHAR(150) | | First name |
| `last_name` | VARCHAR(150) | | Last name |
| `is_staff` | BOOLEAN | DEFAULT FALSE | Django admin access |
| `is_superuser` | BOOLEAN | DEFAULT FALSE | Superuser status |
| `is_active` | BOOLEAN | DEFAULT TRUE | Account active |
| `date_joined` | TIMESTAMP | NOT NULL | Account creation |
| **Profile Fields** | | | |
| `bio` | TEXT | | User bio (max 500 chars) |
| `location` | VARCHAR(100) | | City/Country |
| `hardiness_zone` | VARCHAR(5) | | USDA zone (e.g., '7a') |
| `zip_code` | VARCHAR(10) | | ZIP/postal code |
| `latitude` | DECIMAL(9,6) | | GPS latitude |
| `longitude` | DECIMAL(9,6) | | GPS longitude |
| `location_privacy` | VARCHAR(20) | DEFAULT 'zone_only' | Location sharing level |
| `microclimate_offset` | SMALLINT | DEFAULT 0 | Temperature adjustment |
| `website` | VARCHAR(200) | | Personal website |
| `avatar` | VARCHAR(100) | | Avatar image path |
| **Plant-related** | | | |
| `gardening_experience` | VARCHAR(20) | | Experience level |
| `favorite_plant_types` | M2M (TaggableManager) | | Tagged plant types |
| **Social** | | | |
| `following` | M2M (self) | | Users followed |
| **Privacy** | | | |
| `profile_visibility` | VARCHAR(10) | DEFAULT 'public' | Profile privacy |
| `show_email` | BOOLEAN | DEFAULT FALSE | Show email publicly |
| `show_location` | BOOLEAN | DEFAULT TRUE | Show location |
| **Notifications** | | | |
| `email_notifications` | BOOLEAN | DEFAULT TRUE | Email notifications |
| `plant_id_notifications` | BOOLEAN | DEFAULT TRUE | Plant ID alerts |
| `forum_notifications` | BOOLEAN | DEFAULT TRUE | Forum alerts |
| `care_reminder_notifications` | BOOLEAN | DEFAULT TRUE | Push reminders |
| `care_reminder_email` | BOOLEAN | DEFAULT FALSE | Email reminders |
| **Statistics** | | | |
| `plants_identified` | INTEGER | DEFAULT 0 | Plants identified count |
| `identifications_helped` | INTEGER | DEFAULT 0 | Help given count |
| `forum_posts_count` | INTEGER | DEFAULT 0 | Forum posts count |
| **Trust System** | | | |
| `trust_level` | VARCHAR(10) | DEFAULT 'new' | Trust level (new/basic/trusted/veteran) |
| `posts_count_verified` | INTEGER | DEFAULT 0 | Verified posts count |
| `trust_level_updated` | TIMESTAMP | | Last trust update |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Account created |
| `updated_at` | TIMESTAMP | AUTO NOW | Last updated |

**Indexes**:
- Primary: `id`
- Unique: `uuid`, `username`, `email`
- Index: `trust_level`, `created_at`

**New Field for Migration**:
```sql
ALTER TABLE auth_user ADD COLUMN firebase_uid VARCHAR(128) UNIQUE;
```
This will map Firebase Authentication UID to Django User.

---

#### 1.2 UserPlantCollection Model

**Table**: `users_userplantcollection`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `uuid` | UUID | UNIQUE, NOT NULL | Secure reference |
| `user_id` | INTEGER | FK → auth_user | Collection owner |
| `name` | VARCHAR(100) | NOT NULL | Collection name |
| `description` | TEXT | | Collection description |
| `is_public` | BOOLEAN | DEFAULT TRUE | Public visibility |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

**Constraints**:
- UNIQUE (`user_id`, `name`)

---

#### 1.3 UserMessage Model

**Table**: `users_usermessage`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `sender_id` | INTEGER | FK → auth_user | Message sender |
| `recipient_id` | INTEGER | FK → auth_user | Message recipient |
| `subject` | VARCHAR(200) | | Message subject |
| `message` | TEXT | | Message content |
| `is_read` | BOOLEAN | DEFAULT FALSE | Read status |
| `parent_message_id` | INTEGER | FK → self (nullable) | Reply parent |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Sent time |
| `read_at` | TIMESTAMP | NULLABLE | Read time |

**Indexes**:
- Index: `sender_id`, `recipient_id`, `created_at`
- Index: `is_read` (for unread count queries)

---

#### 1.4 ActivityLog Model

**Table**: `users_activitylog`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `user_id` | INTEGER | FK → auth_user | User who performed action |
| `activity_type` | VARCHAR(30) | NOT NULL | Activity type |
| `description` | TEXT | | Activity description |
| `is_public` | BOOLEAN | DEFAULT TRUE | Public visibility |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Activity time |

**Activity Types**:
- `plant_identified`, `plant_added`, `user_followed`, `forum_post`, `forum_reply`, `profile_updated`, `trust_level_upgrade`

---

### 2. Plant Identification App

#### 2.1 PlantSpecies Model

**Table**: `plant_identification_plantspecies`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `uuid` | UUID | UNIQUE, NOT NULL | Secure reference |
| **Basic Info** | | | |
| `scientific_name` | VARCHAR(200) | UNIQUE, NOT NULL | Scientific name |
| `common_names` | TEXT | | Comma-separated common names |
| `family` | VARCHAR(100) | | Plant family |
| `genus` | VARCHAR(100) | | Genus |
| `species` | VARCHAR(100) | | Species name |
| **External IDs** | | | |
| `trefle_id` | VARCHAR(50) | | Trefle API ID |
| `plantnet_id` | VARCHAR(50) | | PlantNet API ID |
| **Characteristics** | | | |
| `plant_type` | VARCHAR(50) | | Type (tree/shrub/herb/etc) |
| `growth_habit` | VARCHAR(100) | | Growth pattern |
| `mature_height_min` | FLOAT | | Min height (meters) |
| `mature_height_max` | FLOAT | | Max height (meters) |
| **Care Info** | | | |
| `light_requirements` | VARCHAR(20) | | Light needs |
| `water_requirements` | VARCHAR(20) | | Water needs |
| `soil_ph_min` | FLOAT | | Min soil pH |
| `soil_ph_max` | FLOAT | | Max soil pH |
| `hardiness_zone_min` | INTEGER | | Min USDA zone |
| `hardiness_zone_max` | INTEGER | | Max USDA zone |
| **Additional** | | | |
| `description` | TEXT | | Plant description |
| `native_regions` | TEXT | | Native regions |
| `bloom_time` | VARCHAR(100) | | Blooming period |
| `flower_color` | VARCHAR(100) | | Flower colors |
| `primary_image` | VARCHAR(100) | | Image path |
| `tags` | M2M (TaggableManager) | | Classification tags |
| **Verification** | | | |
| `is_verified` | BOOLEAN | DEFAULT FALSE | Expert verified |
| `verification_source` | VARCHAR(200) | | Verification source |
| `auto_stored` | BOOLEAN | DEFAULT FALSE | Auto-stored from ID |
| `confidence_score` | FLOAT | | Highest confidence |
| `identification_count` | INTEGER | DEFAULT 0 | ID count |
| `api_source` | VARCHAR(50) | DEFAULT 'manual' | Data source |
| `community_confirmed` | BOOLEAN | DEFAULT FALSE | Community verified |
| `expert_reviewed` | BOOLEAN | DEFAULT FALSE | Expert reviewed |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

**Indexes**:
- Primary: `id`
- Unique: `uuid`, `scientific_name`
- Index: `plant_type`, `is_verified`, `created_at`

---

#### 2.2 PlantIdentificationRequest Model

**Table**: `plant_identification_plantidentificationrequest`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `request_id` | UUID | UNIQUE, NOT NULL | Request identifier |
| `user_id` | INTEGER | FK → auth_user | Requesting user |
| **Images** | | | |
| `image_1` | VARCHAR(100) | NOT NULL | Primary image |
| `image_2` | VARCHAR(100) | NULLABLE | Optional image 2 |
| `image_3` | VARCHAR(100) | NULLABLE | Optional image 3 |
| **Location** | | | |
| `location` | VARCHAR(200) | | Location description |
| `latitude` | FLOAT | | GPS latitude |
| `longitude` | FLOAT | | GPS longitude |
| **Description** | | | |
| `description` | TEXT | | User description |
| `plant_size` | VARCHAR(50) | | Size category |
| `habitat` | VARCHAR(100) | | Habitat type |
| **Status** | | | |
| `status` | VARCHAR(20) | DEFAULT 'pending' | Request status |
| `processed_by_ai` | BOOLEAN | DEFAULT FALSE | AI processed |
| `ai_processing_date` | TIMESTAMP | NULLABLE | Processing date |
| **Collection** | | | |
| `assigned_to_collection_id` | INTEGER | FK → UserPlantCollection | Assigned collection |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

**Indexes**:
- Primary: `id`
- Unique: `request_id`
- Index: `user_id, created_at`, `status`

---

#### 2.3 PlantIdentificationResult Model

**Table**: `plant_identification_plantidentificationresult`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `uuid` | UUID | UNIQUE, NOT NULL | Secure reference |
| `request_id` | INTEGER | FK → PlantIdentificationRequest | Parent request |
| **Identification** | | | |
| `identified_species_id` | INTEGER | FK → PlantSpecies (nullable) | Matched species |
| `suggested_scientific_name` | VARCHAR(200) | | Alternative name |
| `suggested_common_name` | VARCHAR(200) | | Alternative common |
| **Confidence** | | | |
| `confidence_score` | FLOAT | NOT NULL | Confidence (0.0-1.0) |
| `identification_source` | VARCHAR(20) | NOT NULL | Source type |
| `identified_by_id` | INTEGER | FK → auth_user (nullable) | Community ID user |
| **Details** | | | |
| `notes` | TEXT | | Additional notes |
| `api_response_data` | JSONB | | Raw API response |
| **Voting** | | | |
| `upvotes` | INTEGER | DEFAULT 0 | Agreement votes |
| `downvotes` | INTEGER | DEFAULT 0 | Disagreement votes |
| **Status** | | | |
| `is_accepted` | BOOLEAN | DEFAULT FALSE | User accepted |
| `is_primary` | BOOLEAN | DEFAULT FALSE | Primary result |
| **AI Care** | | | |
| `ai_care_instructions` | JSONB | | Care instructions JSON |
| `care_instructions_generated_at` | TIMESTAMP | NULLABLE | Generated time |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

**Indexes**:
- Primary: `id`
- Unique: `uuid`
- Index: `request_id, confidence_score`, `identified_species_id`

---

#### 2.4 UserPlant Model

**Table**: `plant_identification_userplant`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `uuid` | UUID | UNIQUE, NOT NULL | Secure reference |
| `user_id` | INTEGER | FK → auth_user | Plant owner |
| `collection_id` | INTEGER | FK → UserPlantCollection | Collection |
| `species_id` | INTEGER | FK → PlantSpecies (nullable) | Plant species |
| **Custom** | | | |
| `nickname` | VARCHAR(100) | | User's name for plant |
| `acquisition_date` | DATE | NULLABLE | When acquired |
| `location_in_home` | VARCHAR(100) | | Location description |
| `notes` | TEXT | | Personal notes |
| **Status** | | | |
| `is_alive` | BOOLEAN | DEFAULT TRUE | Alive status |
| `is_public` | BOOLEAN | DEFAULT TRUE | Public visibility |
| **Links** | | | |
| `from_identification_request_id` | INTEGER | FK → PlantIdentificationRequest | Source request |
| `from_identification_result_id` | INTEGER | FK → PlantIdentificationResult | Source result |
| **Care** | | | |
| `care_instructions_json` | JSONB | DEFAULT {} | Care instructions |
| **Image** | | | |
| `image` | VARCHAR(100) | NULLABLE | Current photo |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

**Constraints**:
- UNIQUE (`user_id`, `collection_id`, `species_id`, `nickname`)

---

#### 2.5 PlantDiseaseRequest Model

**Table**: `plant_identification_plantdiseaserequest`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `request_id` | UUID | UNIQUE, NOT NULL | Request identifier |
| `user_id` | INTEGER | FK → auth_user | Requesting user |
| `original_identification_id` | INTEGER | FK → PlantIdentificationRequest | Original plant ID |
| **Images** | | | |
| `disease_image` | VARCHAR(100) | NOT NULL | Disease photo |
| **Description** | | | |
| `symptoms_description` | TEXT | | Symptom description |
| `affected_parts` | VARCHAR(200) | | Affected plant parts |
| **Status** | | | |
| `status` | VARCHAR(20) | DEFAULT 'pending' | Request status |
| `processed_by_ai` | BOOLEAN | DEFAULT FALSE | AI processed |
| **Results** | | | |
| `diagnosis_results` | JSONB | | Diagnosis results (25+ categories) |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

---

### 3. Forum Integration App (Django Machina + Wagtail)

#### 3.1 Forum Models (from Django Machina)

**Note**: Django Machina includes many built-in models. Key ones:

**Table**: `machina_forum`
- `id`, `name`, `description`, `type`, `parent_id`, etc.

**Table**: `machina_topic`
- `id`, `subject`, `forum_id`, `poster_id`, `approved`, `posts_count`, `views_count`, `last_post_on`, etc.

**Table**: `machina_post`
- `id`, `topic_id`, `poster_id`, `content`, `approved`, `created`, `updated`, etc.

#### 3.2 Custom Forum Models

##### ForumPageMapping Model

**Table**: `forum_integration_forumpagemapping`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `wagtail_page_id` | INTEGER | FK → Wagtail Page | Wagtail page |
| `machina_forum_id` | INTEGER | FK → machina_forum | Machina forum |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |

---

##### RichPost Model

**Table**: `forum_integration_richpost`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `post_id` | INTEGER | FK → machina_post | Machina post |
| `rich_content` | JSONB | | StreamField content |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

---

##### PostTemplate Model

**Table**: `forum_integration_posttemplate`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `name` | VARCHAR(100) | | Template name |
| `description` | TEXT | | Template description |
| `content_template` | TEXT | | Template content |
| `category` | VARCHAR(50) | | Template category |
| `created_by_id` | INTEGER | FK → auth_user | Creator |
| `is_public` | BOOLEAN | DEFAULT TRUE | Public access |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

---

##### ForumAIUsage Model

**Table**: `forum_integration_forumaiusage`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `user_id` | INTEGER | FK → auth_user | User |
| `post_id` | INTEGER | FK → machina_post | Post |
| `ai_provider` | VARCHAR(50) | | AI provider |
| `usage_type` | VARCHAR(50) | | Usage type |
| `token_count` | INTEGER | | Tokens used |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |

---

##### ForumPostImage Model

**Table**: `forum_integration_forumpostimage`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `post_id` | INTEGER | FK → machina_post | Post |
| `image` | VARCHAR(100) | | Image path |
| `caption` | TEXT | | Image caption |
| `order` | INTEGER | DEFAULT 0 | Display order |
| `uploaded_by_id` | INTEGER | FK → auth_user | Uploader |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |

---

##### PostReaction Model

**Table**: `forum_integration_postreaction`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `post_id` | INTEGER | FK → machina_post | Post |
| `user_id` | INTEGER | FK → auth_user | User who reacted |
| `reaction_type` | VARCHAR(20) | | Reaction (like/helpful/insightful) |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |

**Constraints**:
- UNIQUE (`post_id`, `user_id`, `reaction_type`)

---

### 4. Garden Calendar App

#### 4.1 CommunityEvent Model

**Table**: `garden_calendar_communityevent`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `uuid` | UUID | UNIQUE, NOT NULL | Secure reference |
| `organizer_id` | INTEGER | FK → auth_user | Event organizer |
| **Event Info** | | | |
| `title` | VARCHAR(200) | | Event title |
| `description` | TEXT | | Event description |
| `event_type` | VARCHAR(20) | | Event type |
| **Date/Time** | | | |
| `start_datetime` | TIMESTAMP | | Start time |
| `end_datetime` | TIMESTAMP | NULLABLE | End time |
| `is_all_day` | BOOLEAN | DEFAULT FALSE | All-day event |
| **Location** | | | |
| `location_name` | VARCHAR(200) | | Venue name |
| `address` | TEXT | | Full address |
| `city` | VARCHAR(100) | | City |
| `hardiness_zone` | VARCHAR(5) | | USDA zone |
| `latitude` | DECIMAL(9,6) | | GPS latitude |
| `longitude` | DECIMAL(9,6) | | GPS longitude |
| **Settings** | | | |
| `privacy_level` | VARCHAR(10) | DEFAULT 'local' | Visibility |
| `max_attendees` | INTEGER | NULLABLE | Max attendees |
| `requires_rsvp` | BOOLEAN | DEFAULT FALSE | RSVP required |
| `is_recurring` | BOOLEAN | DEFAULT FALSE | Recurring event |
| `recurrence_rule` | JSONB | NULLABLE | RRULE format |
| **Contact** | | | |
| `contact_email` | VARCHAR(254) | | Contact email |
| `contact_phone` | VARCHAR(20) | | Contact phone |
| `external_url` | VARCHAR(200) | | External link |
| **Weather** | | | |
| `weather_dependent` | BOOLEAN | DEFAULT FALSE | Weather-dependent |
| `weather_backup_plan` | TEXT | | Backup plan |
| **Forum Link** | | | |
| `forum_topic_id` | INTEGER | NULLABLE | Associated forum topic |
| **Timestamps** | | | |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

---

### 5. Search App

#### 5.1 SearchQuery Model

**Table**: `search_searchquery`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `user_id` | INTEGER | FK → auth_user (nullable) | User (if logged in) |
| `query_text` | VARCHAR(500) | | Search query |
| `search_type` | VARCHAR(20) | | Search type (plant/forum/user) |
| `results_count` | INTEGER | DEFAULT 0 | Results returned |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Search time |

**Indexes**:
- Index: `query_text`, `search_type`, `created_at`

---

#### 5.2 SavedSearch Model

**Table**: `search_savedsearch`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | INTEGER | PK | Primary key |
| `user_id` | INTEGER | FK → auth_user | User |
| `name` | VARCHAR(100) | | Search name |
| `query_text` | VARCHAR(500) | | Search query |
| `filters` | JSONB | | Search filters |
| `notification_enabled` | BOOLEAN | DEFAULT FALSE | Alert on new results |
| `created_at` | TIMESTAMP | AUTO NOW ADD | Created |
| `updated_at` | TIMESTAMP | AUTO NOW | Updated |

---

### 6. Blog App (Wagtail)

Wagtail includes many built-in tables for pages, images, etc. Key custom blog models would be in `wagtailcore_page` with specific page types.

---

## Firestore Schema

### Database Structure

Firestore is a **NoSQL document database** organized into collections and documents.

### Collections Overview

```
firestore/
├── users/                          # User profiles (Firebase Auth synced)
│   └── {firebase_uid}/
├── plant_identifications/          # Plant ID records (mobile)
│   └── {identification_id}/
├── user_plants/                    # User plant collections (mobile)
│   └── {plant_id}/
├── disease_diagnoses/              # Disease diagnosis records
│   └── {diagnosis_id}/
├── user_preferences/               # User settings (mobile-specific)
│   └── {firebase_uid}/
└── sync_queue/                     # Data sync queue
    └── {sync_id}/
```

---

### 1. Users Collection

**Collection**: `users`  
**Document ID**: `{firebase_uid}` (Firebase Auth UID)

```typescript
interface UserDocument {
  // Firebase Auth Info
  firebase_uid: string;           // Firebase UID (document ID)
  email: string;                  // User email
  display_name: string;           // Display name
  photo_url?: string;             // Profile photo URL
  
  // Django User Mapping
  django_user_id?: number;        // Mapped Django user ID
  django_username?: string;       // Django username (cached)
  
  // Mobile App Preferences
  theme: 'light' | 'dark' | 'system';
  language: string;               // Preferred language
  notifications_enabled: boolean;
  
  // Plant ID Settings
  auto_save_identifications: boolean;
  identification_confidence_threshold: number;  // Min confidence to auto-save
  
  // Timestamps
  created_at: Timestamp;
  updated_at: Timestamp;
  last_seen_at: Timestamp;
}
```

**Security Rules**:
```javascript
match /users/{userId} {
  allow read: if request.auth.uid == userId;
  allow write: if request.auth.uid == userId;
}
```

---

### 2. Plant Identifications Collection

**Collection**: `plant_identifications`  
**Document ID**: Auto-generated

```typescript
interface PlantIdentification {
  // Document ID
  id: string;                     // Firestore document ID
  
  // User Info
  user_id: string;                // Firebase UID
  django_user_id?: number;        // Django user ID (if synced)
  
  // Images
  images: {
    image_1: {
      storage_path: string;       // Firebase Storage path
      thumbnail_url?: string;     // Generated thumbnail
      width: number;
      height: number;
    };
    image_2?: { /* same structure */ };
    image_3?: { /* same structure */ };
  };
  
  // Location
  location?: {
    description?: string;
    coordinates?: {
      latitude: number;
      longitude: number;
    };
    city?: string;
    country?: string;
  };
  
  // User Input
  description?: string;
  plant_size?: 'small' | 'medium' | 'large' | 'very_large';
  habitat?: string;
  
  // Identification Results
  results: Array<{
    species_name: string;         // Scientific name
    common_name?: string;
    confidence_score: number;     // 0.0 to 1.0
    source: 'plant_id' | 'plantnet' | 'community';
    api_response?: any;           // Raw API response
    
    // Care Instructions (if available)
    care_instructions?: {
      light: string;
      water: string;
      soil: string;
      temperature: string;
      humidity: string;
      fertilizer: string;
    };
  }>;
  
  // Status
  status: 'pending' | 'processing' | 'completed' | 'failed';
  processed_by_ai: boolean;
  ai_processing_date?: Timestamp;
  
  // Collection Assignment
  assigned_to_collection_id?: string;
  saved_to_collection: boolean;
  
  // Timestamps
  created_at: Timestamp;
  updated_at: Timestamp;
  
  // Sync Status
  synced_to_django: boolean;
  django_request_id?: string;     // UUID from Django if synced
}
```

**Indexes**:
- `user_id` (for user's plant IDs)
- `created_at` (for sorting)
- `status` (for filtering)

**Security Rules**:
```javascript
match /plant_identifications/{identificationId} {
  allow read: if request.auth.uid == resource.data.user_id;
  allow create: if request.auth.uid == request.resource.data.user_id;
  allow update: if request.auth.uid == resource.data.user_id;
  allow delete: if request.auth.uid == resource.data.user_id;
}
```

---

### 3. User Plants Collection

**Collection**: `user_plants`  
**Document ID**: Auto-generated

```typescript
interface UserPlant {
  // Document ID
  id: string;                     // Firestore document ID
  
  // User Info
  user_id: string;                // Firebase UID
  collection_name: string;        // Collection name (e.g., "Indoor Plants")
  
  // Plant Info
  species: {
    scientific_name: string;
    common_name?: string;
    plant_type?: string;
  };
  
  // Custom Fields
  nickname?: string;              // User's name for this plant
  acquisition_date?: Timestamp;
  location_in_home?: string;
  notes?: string;
  
  // Image
  current_photo?: {
    storage_path: string;
    thumbnail_url?: string;
    taken_at: Timestamp;
  };
  
  // Care Instructions
  care_instructions?: {
    light: string;
    water: string;
    fertilizer: string;
    custom_notes?: string;
  };
  
  // Care Schedule
  care_reminders?: Array<{
    type: 'water' | 'fertilize' | 'prune' | 'repot' | 'custom';
    frequency_days: number;
    last_done_at?: Timestamp;
    next_due_at?: Timestamp;
    notification_enabled: boolean;
  }>;
  
  // Status
  is_alive: boolean;
  is_public: boolean;
  
  // Source
  from_identification_id?: string;  // Link to PlantIdentification
  
  // Timestamps
  created_at: Timestamp;
  updated_at: Timestamp;
  
  // Sync Status
  synced_to_django: boolean;
  django_plant_id?: number;
}
```

**Indexes**:
- `user_id` (for user's plants)
- `collection_name` (for filtering by collection)
- `is_alive` (for active plants)

**Security Rules**:
```javascript
match /user_plants/{plantId} {
  allow read: if request.auth.uid == resource.data.user_id 
              || resource.data.is_public == true;
  allow create: if request.auth.uid == request.resource.data.user_id;
  allow update: if request.auth.uid == resource.data.user_id;
  allow delete: if request.auth.uid == resource.data.user_id;
}
```

---

### 4. Disease Diagnoses Collection

**Collection**: `disease_diagnoses`  
**Document ID**: Auto-generated

```typescript
interface DiseaseDiagnosis {
  // Document ID
  id: string;
  
  // User Info
  user_id: string;                // Firebase UID
  
  // Link to Plant
  plant_identification_id?: string;  // Original plant ID
  user_plant_id?: string;            // User's plant
  
  // Disease Image
  disease_image: {
    storage_path: string;
    thumbnail_url?: string;
    width: number;
    height: number;
  };
  
  // Symptoms
  symptoms_description: string;
  affected_parts: string[];       // ['leaves', 'stem', 'roots', etc.]
  
  // Diagnosis Results (25+ categories)
  diagnosis: {
    disease_name: string;
    confidence_score: number;
    category: string;             // From 25+ categories
    severity: 'low' | 'medium' | 'high' | 'critical';
    
    // Treatment Recommendations
    treatment: {
      immediate_actions: string[];
      long_term_care: string[];
      products_recommended?: string[];
      organic_options?: string[];
    };
    
    // Prevention
    prevention_tips: string[];
  };
  
  // API Data
  api_response?: any;
  source: 'plant_id' | 'manual';
  
  // Status
  status: 'pending' | 'processing' | 'completed' | 'failed';
  
  // Follow-up
  follow_up_photos?: Array<{
    storage_path: string;
    taken_at: Timestamp;
    notes?: string;
  }>;
  
  // Timestamps
  created_at: Timestamp;
  updated_at: Timestamp;
  
  // Sync Status
  synced_to_django: boolean;
  django_diagnosis_id?: string;
}
```

**Indexes**:
- `user_id`
- `plant_identification_id`
- `created_at`

---

### 5. User Preferences Collection

**Collection**: `user_preferences`  
**Document ID**: `{firebase_uid}`

```typescript
interface UserPreferences {
  // User ID
  user_id: string;                // Firebase UID (document ID)
  
  // App Settings
  theme: 'light' | 'dark' | 'system';
  language: string;
  
  // Notifications
  notifications: {
    enabled: boolean;
    care_reminders: boolean;
    identification_complete: boolean;
    community_updates: boolean;
    forum_replies: boolean;
  };
  
  // Plant ID Settings
  plant_identification: {
    auto_save_threshold: number;  // Min confidence (0.0-1.0)
    include_location: boolean;
    default_collection: string;
    image_quality: 'low' | 'medium' | 'high';
  };
  
  // Camera Settings
  camera: {
    flash_mode: 'auto' | 'on' | 'off';
    grid_overlay: boolean;
    save_to_gallery: boolean;
  };
  
  // Privacy
  privacy: {
    share_location: boolean;
    public_profile: boolean;
    show_collections: boolean;
  };
  
  // Timestamps
  created_at: Timestamp;
  updated_at: Timestamp;
}
```

---

### 6. Sync Queue Collection

**Collection**: `sync_queue`  
**Document ID**: Auto-generated

```typescript
interface SyncQueueItem {
  id: string;
  
  // Sync Info
  user_id: string;
  entity_type: 'plant_identification' | 'user_plant' | 'disease_diagnosis';
  entity_id: string;              // Firestore document ID
  operation: 'create' | 'update' | 'delete';
  
  // Sync Status
  status: 'pending' | 'processing' | 'completed' | 'failed';
  attempts: number;
  last_attempt_at?: Timestamp;
  error_message?: string;
  
  // Data
  data: any;                      // Serialized entity data
  
  // Timestamps
  created_at: Timestamp;
  completed_at?: Timestamp;
}
```

**Purpose**: Queue for syncing mobile data to Django backend when needed.

---

## Database Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                    USER ACTION                           │
└──────────────────────────────────────────────────────────┘
                          │
                          ├─ Web App → PostgreSQL (direct)
                          │
                          └─ Mobile App → Firestore (primary)
                                         │
                                         ├─ Immediate storage
                                         │
                                         └─ Optional sync to PostgreSQL
                                            via sync_queue or API calls
```

### Authentication Flow

```
1. User signs up/logs in via Firebase Auth
   ↓
2. Firebase UID is created
   ↓
3a. Web App: Django creates User record with firebase_uid field
3b. Mobile App: Firestore creates user document
   ↓
4. Both systems use Firebase UID as primary identifier
```

### Data Sync Strategy

#### Mobile → Django Sync (Optional)

**When to sync**:
- User requests export of their data
- User wants to view plant history on web
- Community features require Django access

**How to sync**:
1. Mobile app adds item to `sync_queue` collection
2. Cloud Function triggers on `sync_queue` write
3. Function calls Django REST API with Firebase token
4. Django validates token and creates/updates records
5. Function marks sync item as complete

**Example Cloud Function**:
```typescript
exports.syncTodjango = functions.firestore
  .document('sync_queue/{syncId}')
  .onCreate(async (snap, context) => {
    const syncItem = snap.data();
    
    // Call Django API
    const response = await fetch('https://api.plantcommunity.com/sync/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${syncItem.firebase_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(syncItem.data)
    });
    
    // Update sync status
    if (response.ok) {
      await snap.ref.update({ 
        status: 'completed',
        completed_at: admin.firestore.FieldValue.serverTimestamp()
      });
    } else {
      await snap.ref.update({ 
        status: 'failed',
        attempts: syncItem.attempts + 1,
        error_message: await response.text()
      });
    }
  });
```

---

## Migration Strategy

### Phase 1: Add Firebase Support to Django

1. **Add Firebase Admin SDK**
   ```bash
   pip install firebase-admin
   ```

2. **Add `firebase_uid` field to User model**
   ```python
   # users/models.py
   firebase_uid = models.CharField(
       max_length=128, 
       unique=True, 
       null=True, 
       blank=True
   )
   ```

3. **Create migration**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Create custom authentication backend**
   ```python
   # users/backends.py
   from firebase_admin import auth
   from django.contrib.auth.backends import BaseBackend
   from .models import User
   
   class FirebaseAuthenticationBackend(BaseBackend):
       def authenticate(self, request, firebase_token=None):
           if firebase_token:
               try:
                   decoded_token = auth.verify_id_token(firebase_token)
                   firebase_uid = decoded_token['uid']
                   
                   # Get or create user
                   user, created = User.objects.get_or_create(
                       firebase_uid=firebase_uid,
                       defaults={
                           'username': decoded_token.get('email', firebase_uid),
                           'email': decoded_token.get('email', ''),
                       }
                   )
                   return user
               except Exception:
                   return None
           return None
   ```

5. **Update Django settings**
   ```python
   AUTHENTICATION_BACKENDS = [
       'apps.users.backends.FirebaseAuthenticationBackend',
       'django.contrib.auth.backends.ModelBackend',
   ]
   ```

---

### Phase 2: Create Firestore Database

1. **Initialize Firebase project**
   - Create project in Firebase Console
   - Enable Firestore Database
   - Set up security rules

2. **Create indexes**
   ```json
   {
     "indexes": [
       {
         "collectionGroup": "plant_identifications",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "user_id", "order": "ASCENDING" },
           { "fieldPath": "created_at", "order": "DESCENDING" }
         ]
       },
       {
         "collectionGroup": "user_plants",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "user_id", "order": "ASCENDING" },
           { "fieldPath": "is_alive", "order": "ASCENDING" },
           { "fieldPath": "created_at", "order": "DESCENDING" }
         ]
       }
     ]
   }
   ```

3. **Deploy security rules**
   ```bash
   firebase deploy --only firestore:rules
   ```

---

### Phase 3: Set Up Firebase Storage

1. **Configure storage buckets**
   - `{project-id}.appspot.com/plant-identifications/` - Plant ID images
   - `{project-id}.appspot.com/disease-diagnoses/` - Disease images
   - `{project-id}.appspot.com/user-plants/` - User plant photos

2. **Set up storage rules**
   ```javascript
   service firebase.storage {
     match /b/{bucket}/o {
       match /plant-identifications/{userId}/{imageId} {
         allow read: if request.auth != null;
         allow write: if request.auth.uid == userId
                      && request.resource.size < 10 * 1024 * 1024  // 10MB
                      && request.resource.contentType.matches('image/.*');
       }
       
       match /user-plants/{userId}/{imageId} {
         allow read: if request.auth != null;
         allow write: if request.auth.uid == userId
                      && request.resource.size < 10 * 1024 * 1024;
       }
     }
   }
   ```

---

### Phase 4: Create Sync API Endpoints

**Django REST API for syncing mobile data**:

```python
# plant_identification/api/sync_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.users.backends import FirebaseAuthenticationBackend

class SyncPlantIdentificationView(APIView):
    """Sync plant identification from mobile to Django."""
    
    authentication_classes = [FirebaseAuthenticationBackend]
    
    def post(self, request):
        firebase_data = request.data
        
        # Create PlantIdentificationRequest
        plant_request = PlantIdentificationRequest.objects.create(
            user=request.user,
            # Map Firestore data to Django fields
            location=firebase_data.get('location', {}).get('description'),
            latitude=firebase_data.get('location', {}).get('coordinates', {}).get('latitude'),
            # ... etc
        )
        
        return Response({
            'django_request_id': str(plant_request.request_id),
            'status': 'synced'
        }, status=status.HTTP_201_CREATED)
```

---

## Indexes & Performance

### PostgreSQL Indexes

**Critical indexes for performance**:

```sql
-- User lookups
CREATE INDEX idx_user_firebase_uid ON auth_user(firebase_uid);
CREATE INDEX idx_user_trust_level ON auth_user(trust_level);

-- Plant identification queries
CREATE INDEX idx_plant_request_user_date ON plant_identification_plantidentificationrequest(user_id, created_at DESC);
CREATE INDEX idx_plant_request_status ON plant_identification_plantidentificationrequest(status);

-- Plant species searches
CREATE INDEX idx_plant_species_name ON plant_identification_plantspecies(scientific_name);
CREATE INDEX idx_plant_species_verified ON plant_identification_plantspecies(is_verified, identification_count DESC);

-- Forum queries
CREATE INDEX idx_topic_forum_date ON machina_topic(forum_id, last_post_on DESC);
CREATE INDEX idx_post_topic_date ON machina_post(topic_id, created);

-- User plants
CREATE INDEX idx_user_plant_user_collection ON plant_identification_userplant(user_id, collection_id);
CREATE INDEX idx_user_plant_alive ON plant_identification_userplant(user_id, is_alive);
```

### Firestore Composite Indexes

**Required composite indexes**:

1. **Plant Identifications by user and date**
   - Fields: `user_id` (ASC), `created_at` (DESC)
   
2. **User Plants by collection**
   - Fields: `user_id` (ASC), `collection_name` (ASC), `created_at` (DESC)
   
3. **Active plants**
   - Fields: `user_id` (ASC), `is_alive` (ASC), `created_at` (DESC)

---

## Conclusion

The dual-database architecture provides:

✅ **Separation of Concerns**: CMS/forum in PostgreSQL, mobile data in Firestore  
✅ **Scalability**: Firestore handles mobile app growth independently  
✅ **Performance**: Each database optimized for its use case  
✅ **Flexibility**: Optional syncing between databases  
✅ **Unified Auth**: Firebase Auth works across both platforms

**Next Steps**:
1. ✅ PostgreSQL schema documented
2. ✅ Firestore schema designed
3. ⏳ Implement Firebase authentication in Django
4. ⏳ Create sync API endpoints
5. ⏳ Set up Firestore security rules
6. ⏳ Initialize Flutter app with Firestore integration

**Status**: Database Schema Documentation Complete ✅  
**Next**: Firebase Project Setup 🔥
