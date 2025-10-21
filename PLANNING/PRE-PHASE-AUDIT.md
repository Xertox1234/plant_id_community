# Pre-Phase Audit: Existing Codebase Analysis

**Date**: October 21, 2025  
**Status**: 🔄 In Progress  
**Purpose**: Complete audit of existing implementation before restructure begins

---

## Executive Summary

The existing Plant ID Community platform is a **fully-functional Progressive Web App (PWA)** with:
- ✅ Django 5.2 + Wagtail 7.0 LTS backend
- ✅ React 19 + Tailwind CSS 4 frontend
- ✅ React Native mobile app (Expo)
- ✅ Custom forum implementation (Django Machina + Wagtail)
- ✅ Enhanced disease diagnosis system (25+ categories)
- ✅ Plant.id API integration for AI identification
- ✅ Docker-based deployment infrastructure
- ✅ Google Analytics 4 integration

**Key Finding**: The codebase is production-ready and well-documented. Our restructure will **preserve** the backend CMS/forum functionality while **transforming** the frontend and adding native Flutter mobile apps.

---

## 1. Backend Architecture Analysis

### 1.1 Django Applications Structure

```
backend/apps/
├── users/                      # Custom user management
├── plant_identification/       # Core plant ID functionality
├── forum_integration/          # Wagtail + Machina forum
├── blog/                       # Wagtail blog system
├── garden_calendar/            # Plant tracking/calendar
├── search/                     # Search functionality
└── core/                       # Shared utilities
```

### 1.2 Forum Integration (`forum_integration` app)

**Architecture**: Wagtail page types wrapping Django Machina forums

#### Key Models (from `models.py`):

1. **ForumBasePage** (Abstract)
   - Base class for all forum-related Wagtail pages
   - **CRITICAL**: Uses FLAT StreamField blocks (NO NESTING) - user requirement
   - Includes SEO metadata, breadcrumbs, social sharing settings

2. **ForumIndexPage**
   - Main forum landing page
   - Lists all forum categories
   - Wagtail CMS integration

3. **ForumStreamBlocks** (StreamField blocks):
   - `heading` - Title blocks
   - `paragraph` - Rich text content
   - `forum_announcement` - Pinned announcements with dates
   - `forum_rules` - Forum rules display
   - `moderator_info` - Moderator profiles
   - `image` - Image embeds
   - `call_to_action` - CTA buttons
   - `statistics` - Forum stats display
   - `plant_mention` - References to plant species pages

#### Files & Structure:
```
forum_integration/
├── models.py              # Wagtail page models (826 lines)
├── views.py               # Forum views
├── api_views.py           # REST API endpoints
├── serializers.py         # DRF serializers
├── admin.py               # Django admin
├── wagtail_hooks.py       # Wagtail customizations
├── context_processors.py  # Template context
├── templates/             # Forum templates
├── static/                # Forum static assets
└── tests/                 # Test suite
```

#### Custom Features:
- ✅ Wagtail CMS pages for forum categories
- ✅ Flat StreamField content blocks (no nesting)
- ✅ Plant mention blocks (reference plant species)
- ✅ Forum announcements with expiration dates
- ✅ Moderator information blocks
- ✅ SEO optimization
- ✅ Social sharing integration
- ✅ REST API for mobile access

**Migration Impact**: 
- **Keep**: All Django Machina + Wagtail forum code
- **Add**: REST API endpoints for Flutter app (read-only forum access)
- **Modify**: Authentication to work with Firebase

---

### 1.3 Plant Identification (`plant_identification` app)

#### Key Models (from `models.py` - 2854 lines):

1. **PlantSpecies**
   - Scientific name, common names, family, genus, species
   - External API IDs (Trefle, PlantNet)
   - Plant characteristics (type, growth habit)
   - **UUID for secure references** (prevents IDOR attacks)

2. **PlantIdentificationRequest** (implied from structure)
   - Image uploads
   - AI processing with Plant.id API
   - Results storage
   - User collection management

#### Files & Structure:
```
plant_identification/
├── models.py              # Plant data models (2854 lines!)
├── services/              # External API integrations
│   ├── plantnet_service.py
│   └── trefle_service.py
├── api/                   # REST API
├── consumers.py           # WebSocket handlers
├── tasks.py               # Celery async tasks
├── views.py               # Django views
├── admin.py               # Admin interface
└── tests/                 # Comprehensive tests
```

#### Features:
- ✅ Plant.id API integration for AI identification
- ✅ Enhanced disease diagnosis (25+ categories)
- ✅ Image upload and processing (ImageKit)
- ✅ Real-time updates via WebSocket
- ✅ GPS location data for identification
- ✅ User plant collections
- ✅ Community voting on identifications
- ✅ PWA offline capabilities

**Migration Impact**:
- **Keep**: All backend models and API logic
- **Move**: Primary plant ID interface to Flutter mobile app
- **Simplify**: Web app gets upload-only (no camera)
- **Add**: Firestore for mobile plant ID records
- **Preserve**: PostgreSQL for species database

---

### 1.4 Users App (`users` app)

**Custom User Model**: Django's AbstractUser with plant-specific fields

Expected features:
- Profile management
- Plant collections
- Social following system
- Authentication (currently Django sessions/JWT)

**Migration Impact**:
- **Replace**: Django authentication with Firebase Authentication
- **Keep**: User profile data in PostgreSQL
- **Add**: Firebase UID → Django User mapping
- **Implement**: Custom authentication backend for Firebase tokens

---

### 1.5 Blog System (`blog` app)

- Wagtail CMS for blog posts
- StreamFields for rich content
- Category management
- SEO optimization

**Migration Impact**:
- **Keep**: All Wagtail blog functionality
- **Add**: REST API for Flutter app (read-only blog access)
- **Consider**: Headless Wagtail API v2

---

## 2. Frontend Architecture Analysis

### 2.1 Web Frontend (React 19)

```
frontend/src/
├── components/            # Reusable UI components
├── pages/                 # Application pages
├── hooks/                 # Custom React hooks
├── services/              # API integration
├── context/               # State management
└── styles/                # Tailwind CSS 4
```

**Key Technologies**:
- React 19.1.1 with modern hooks
- Vite for fast builds
- Tailwind CSS 4.0 (plant-themed design)
- Context API for state management
- Axios for HTTP requests
- PWA features (service worker, offline support)

**Features**:
- ✅ Enhanced disease diagnosis UI
- ✅ Plant identification interface with camera
- ✅ Forum browsing and posting
- ✅ Blog reading
- ✅ User profiles and collections
- ✅ Real-time updates (WebSocket)
- ✅ Touch-optimized swipe navigation
- ✅ Mobile-first responsive design

**Migration Impact**:
- **Remove**: PWA functionality
- **Remove**: Camera features from web
- **Simplify**: Convert to headless Wagtail + React or pure Wagtail templates
- **Decision Needed**: Keep React frontend or use Wagtail templates?
- **Remove**: Mobile-specific features (swipe navigation, etc.)

---

### 2.2 Mobile App (React Native + Expo)

```
mobile/
├── src/
│   ├── screens/           # App screens
│   ├── components/        # UI components
│   ├── navigation/        # React Navigation
│   └── services/          # API integration
├── App.js                 # Entry point
├── app.json               # Expo config
└── TESTING_GUIDE.md       # Mobile testing docs
```

**Status**: Legacy/incomplete React Native implementation

**Migration Impact**:
- **Replace Entirely**: New Flutter app will replace React Native
- **Preserve**: Lessons learned from mobile UX
- **Reference**: Design patterns and navigation flow

---

## 3. Deployment & Infrastructure

### 3.1 Docker Setup

**Files**:
- `docker-compose.yml` - Development environment
- `docker-compose.prod.yml` - Production setup
- `backend/Dockerfile` - Django container
- `frontend/Dockerfile` - React container
- `nginx/nginx.prod.conf` - Nginx reverse proxy

**Services**:
- Django + Gunicorn (port 8000)
- React + Vite (port 3000 in dev)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Nginx (ports 80/443 in prod)

**Migration Impact**:
- **Keep**: Docker setup for Django/Wagtail
- **Simplify**: Remove React build if using Wagtail templates
- **Add**: Firebase emulators for local development
- **Update**: Nginx config for new frontend

---

### 3.2 Database Schema

**PostgreSQL Tables** (estimated):
- User accounts and profiles
- Plant species data
- Plant identification requests and results
- Forum posts, topics, categories (Django Machina)
- Blog posts and pages (Wagtail)
- User plant collections
- Social connections
- Analytics data

**Migration Impact**:
- **Keep**: All PostgreSQL schema for blog/forum/users
- **Add**: Firebase UID field to User model
- **Design**: Firestore schema for mobile plant ID records
- **Document**: Complete schema mapping needed

---

## 4. External Integrations

### 4.1 APIs

1. **Plant.id API**
   - AI plant identification
   - Disease diagnosis
   - Currently integrated in backend

2. **PlantNet API**
   - Alternative plant identification
   - Species database

3. **Trefle API**
   - Plant species information
   - Botanical data

4. **Google Analytics 4**
   - User tracking
   - Plant-specific events

**Migration Impact**:
- **Keep**: All API integrations in Django backend
- **Add**: Firebase Analytics for mobile app
- **Consider**: Rate limiting for mobile app API access

---

### 4.2 Authentication

**Current**: Django sessions + JWT tokens + OAuth (Google/GitHub)

**Migration Plan**:
1. Add Firebase Authentication
2. Create custom Django authentication backend for Firebase tokens
3. Map Firebase UIDs to Django User models
4. Keep OAuth providers (migrate to Firebase)
5. Shared authentication across web and mobile

---

## 5. Key Files to Preserve

### Backend (Django/Wagtail)
- ✅ `backend/apps/forum_integration/` - Entire app
- ✅ `backend/apps/plant_identification/models.py` - Plant species database
- ✅ `backend/apps/plant_identification/services/` - API integrations
- ✅ `backend/apps/blog/` - Entire blog system
- ✅ `backend/plant_community_backend/settings.py` - Django settings
- ✅ All migrations

### Documentation
- ✅ `docs/` - Complete documentation folder
- ✅ `README.md`, `CLAUDE.md`, `PROJECT_SUMMARY.md`
- ✅ All guide files (DEPLOYMENT, EMAIL, SECURITY, etc.)

### Infrastructure
- ✅ Docker configuration files
- ✅ Nginx configuration
- ✅ Scripts (backup, deploy, restore)

---

## 6. Custom Features to Document Further

### 6.1 Forum Customizations

**Need to document**:
1. How Django Machina integrates with Wagtail pages
2. Custom forum features beyond standard Machina
3. Moderation tools and workflows
4. User permissions and roles
5. Forum API endpoints for mobile access

**Action**: Create detailed forum documentation in next step

---

### 6.2 Disease Diagnosis System

**Enhanced System (25+ categories)**:
- Offline-first functionality
- Regional intelligence
- Mock services for development

**Need to document**:
1. Complete category list
2. API request/response format
3. Image preprocessing steps
4. Result storage structure
5. Mobile app integration points

**Action**: Read disease diagnosis documentation

---

## 7. Testing Infrastructure

### Backend Tests
- Django test suite
- pytest configuration
- Service mocking patterns
- API endpoint tests

### Frontend Tests
- Vitest for unit tests
- Playwright for E2E tests
- Component tests

**Migration Impact**:
- **Keep**: All backend tests
- **Add**: Flutter widget tests
- **Add**: Flutter integration tests
- **Update**: API tests for new endpoints

---

## 8. Next Steps

### Immediate Actions

1. ✅ **Complete this audit document**
2. ⏳ **Document forum customizations in detail**
   - Create `FORUM_CUSTOMIZATIONS.md`
   - List all custom features
   - Document Machina + Wagtail integration points
   
3. ⏳ **Create database schema documentation**
   - Export current PostgreSQL schema
   - Design Firestore schema for mobile
   - Map relationships between databases
   
4. ⏳ **Set up Firebase project**
   - Create Firebase project
   - Configure Authentication
   - Set up Firestore
   - Configure Cloud Storage
   - Create security rules

5. ⏳ **Initialize Flutter project**
   - Create Flutter project structure
   - Implement design system from Figma
   - Set up Riverpod state management
   - Configure Firebase Flutter plugins

6. ⏳ **Define Git branching strategy**
   - Main branch protection
   - Feature branch workflow
   - Release management

---

## 9. Risks & Considerations

### High Priority Risks

1. **Forum Customizations**
   - Risk: Losing custom features during migration
   - Mitigation: Complete documentation before changes

2. **Authentication Migration**
   - Risk: Breaking existing user authentication
   - Mitigation: Gradual rollout, keep Django auth initially

3. **Data Migration**
   - Risk: Losing user data or plant records
   - Mitigation: Comprehensive backup and testing

4. **API Compatibility**
   - Risk: Breaking mobile app during backend changes
   - Mitigation: Versioned API endpoints

### Medium Priority Risks

5. **External API Dependencies**
   - Risk: Plant.id/PlantNet API changes
   - Mitigation: Abstract API layer, error handling

6. **Design System Consistency**
   - Risk: Flutter app looks different from design
   - Mitigation: Extract complete design tokens, regular design reviews

---

## 10. Technology Versions

### Current Versions (Existing Implementation)

**Backend**:
- Django: 5.2 LTS
- Wagtail: 7.0 LTS
- Django REST Framework: Latest
- PostgreSQL: 15+
- Redis: Latest
- Python: 3.11+

**Frontend (Web)**:
- React: 19.1.1
- Vite: Latest
- Tailwind CSS: 4.0
- Node.js: 18+

**Mobile (Legacy)**:
- React Native: Latest
- Expo: Latest

### Target Versions (Migration)

**Backend** (No Changes):
- Keep all current versions

**Web Frontend** (TBD):
- Option A: Keep React 19 + Tailwind 4 (headless)
- Option B: Use Wagtail templates only

**Mobile (New)**:
- Flutter: 3.35
- Dart: 3.9
- Firebase: 12.4.0 (JS SDK)
- Riverpod: Latest stable

---

## 11. Codebase Metrics

**Backend**:
- `forum_integration/models.py`: 826 lines
- `plant_identification/models.py`: 2854 lines
- Total Django apps: 7
- Documentation files: 15+

**Frontend**:
- React components: 50+ (estimated)
- Pages: 15+ (estimated)
- Tailwind custom theme: Yes

**Mobile**:
- React Native screens: 10+ (estimated)
- Status: Incomplete/legacy

---

## Conclusion

The existing codebase is **well-structured and production-ready**. The forum integration is sophisticated with Wagtail + Django Machina, and the plant identification system is comprehensive with enhanced disease diagnosis.

**Key Takeaway**: We are not rebuilding from scratch—we are **transforming the architecture** to better serve web and mobile use cases while preserving the valuable CMS and forum functionality.

**Status**: Audit Phase 1 Complete ✅  
**Next**: Forum Customizations Deep Dive 📋
