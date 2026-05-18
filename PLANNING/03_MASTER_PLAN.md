# Project Restructure - Master Plan
## Plant ID Community: PWA to Flutter Mobile + Web

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Phased Development Roadmap](#phased-development-roadmap)
5. [Key Decisions](#key-decisions)
6. [Risk Assessment](#risk-assessment)
7. [Success Metrics](#success-metrics)

---

## Project Overview

### Vision Statement
Transform Plant ID Community from a Progressive Web App (PWA) into a dual-platform solution:
- **Web App**: Blog and forum-focused, limited plant ID (upload only, no camera)
- **Flutter Mobile Apps**: Full-featured plant ID with camera, disease diagnosis, blog/forum reading

### Core Principles
- ✅ Preserve existing Wagtail CMS and custom forum modifications
- ✅ Use latest stable versions of all technologies
- ✅ Firebase for authentication and mobile data
- ✅ Django/Wagtail/PostgreSQL for web content
- ✅ Shared authentication across platforms
- ✅ No deadlines - thorough, quality-focused development

---

## Current State Analysis

### Existing Tech Stack (from GitHub)
```
Frontend (PWA):
├── React 19
├── Vite
├── Tailwind CSS 4
└── Service Worker (PWA capabilities)

Backend:
├── Django 5.2
├── Wagtail 7.x
├── DRF (Django REST Framework)
├── PostgreSQL
└── Redis

Mobile:
└── Mobile folder exists (legacy)

Infrastructure:
├── Nginx
└── WebSocket support
```

### Key Existing Features to Preserve
1. **Custom Forum Implementation**
   - Built with Wagtail
   - Significant customizations (need to document)
   - Community features

2. **Blog System**
   - Wagtail CMS
   - Rich content editing
   - StreamFields

3. **Plant Identification**
   - Plant.id API integration
   - Enhanced Disease Diagnosis (25+ categories)
   - Image upload/processing

4. **Authentication System**
   - Current implementation (to be replaced with Firebase)

### What Changes
- ❌ Remove PWA functionality
- ❌ Replace React frontend (or simplify to Wagtail templates)
- ❌ Remove camera features from web
- ➕ Add Flutter mobile apps (iOS + Android)
- ➕ Add Firebase Auth
- ➕ Keep Django/Wagtail for web
- 🔄 Refactor plant ID to be mobile-primary

---

## Target Architecture

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        USERS                                   │
│                    Web + Mobile                                │
└──────────────┬────────────────────────────┬───────────────────┘
               │                            │
        ┌──────▼──────┐            ┌───────▼────────┐
        │  WEB USERS  │            │  MOBILE USERS  │
        │  (Browser)  │            │  (iOS/Android) │
        └──────┬──────┘            └────────┬───────┘
               │                            │
┌──────────────▼─────────────┐   ┌─────────▼────────────────────┐
│   WEB APP (Headless CMS)   │   │   FLUTTER APP (Riverpod)     │
│  ┌──────────────────────┐  │   │  ┌───────────────────────┐  │
│  │  React 19 Frontend   │  │   │  │  Plant ID Features    │  │
│  │  (Tailwind CSS 4)    │  │   │  │  ├─ Camera            │  │
│  │  ├─ Blog UI          │  │   │  │  ├─ Gallery           │  │
│  │  ├─ Forum UI         │  │   │  │  ├─ Diagnosis         │  │
│  │  ├─ User Profiles    │  │   │  │  └─ History           │  │
│  │  └─ Simple Upload    │  │   │  ├─ Blog Reader          │  │
│  │     (no camera)      │  │   │  ├─ Basic Forum (Post)   │  │
│  └──────────┬───────────┘  │   │  ├─ User Profile         │  │
│             │ REST API     │   │  └─ Dark/Light Theme     │  │
│  ┌──────────▼───────────┐  │   │     (Figma Design)       │  │
│  │  Django/Wagtail API  │  │   └───────────────────────┘
│  │  (Headless Backend)  │  │              │
│  │  ├─ Blog Content     │  │              │
│  │  ├─ Forum Content    │  │              │
│  │  └─ Content API      │  │              │
│  └──────────────────────┘  │              │
│                            │              │
│   PostgreSQL Database     │              │
│   (Blog + Forum Content)  │              │
└──────────────┬─────────────┘              │
               │                            │
               │      ┌─────────────────────▼─────────┐
               └──────►     FIREBASE                  │
                      │  ┌─────────────────────────┐  │
                      │  │  Authentication         │  │
                      │  │  (Shared Web + Mobile)  │  │
                      │  └─────────────────────────┘  │
                      │  ┌─────────────────────────┐  │
                      │  │  Firestore              │  │
                      │  │  (Plant ID Records)     │  │
                      │  └─────────────────────────┘  │
                      │  ┌─────────────────────────┐  │
                      │  │  Cloud Storage          │  │
                      │  │  (Plant Images)         │  │
                      │  └─────────────────────────┘  │
                      └────────────────────────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │   External APIs           │
                      │  ├─ Plant.id API          │
                      │  └─ Disease Detection     │
                      └───────────────────────────┘
```

### Technology Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Mobile** | Flutter 3.35 + Dart 3.9 | iOS & Android apps |
| **Mobile State** | Riverpod | State management |
| **Mobile Design** | Figma Design System | Dark/Light themes |
| **Web Frontend** | React 19 + Tailwind CSS 4 | Headless CMS UI |
| **Web Backend** | Django 5.2 + Wagtail 7.0 LTS (Headless) | CMS API, Blog, Forum |
| **Web Database** | PostgreSQL 15+ | Blog/Forum content |
| **Shared Auth** | Firebase Authentication | Web + Mobile users |
| **Mobile Database** | Cloud Firestore | Plant ID records |
| **File Storage** | Firebase Cloud Storage | Plant images |
| **External API** | Plant.id API | Plant identification |

---

## Phased Development Roadmap

### Pre-Phase: Discovery & Documentation (2-3 weeks)

**Objectives:**
- Document all existing Wagtail customizations
- Document forum functionality and modifications
- Export any critical data
- Create detailed database schema
- Set up development environments

**Deliverables:**
- [ ] Complete audit of existing codebase
- [ ] Documentation of forum customizations
- [ ] Database schema document
- [ ] Firebase project setup
- [ ] Flutter development environment
- [ ] Git branch strategy

---

### Phase 1: Foundation & Setup (3-4 weeks)

**Objective**: Set up core infrastructure

#### Week 1-2: Firebase & Authentication
- [ ] Create Firebase project
- [ ] Configure Firebase Authentication
  - Email/password
  - Google Sign-In
  - Phone auth (optional)
- [ ] Set up Firestore database structure
- [ ] Set up Firebase Cloud Storage
- [ ] Create security rules
- [ ] Install Firebase Admin SDK in Django

#### Week 2-3: Django/Wagtail Modernization
- [ ] Update Django to 5.2 (if not already)
- [ ] Update Wagtail to 7.0 LTS
- [ ] Configure Wagtail as Headless CMS
  - Enable Wagtail API v2
  - Configure CORS for React frontend
  - Set up API endpoints for blog and forum
- [ ] Integrate Firebase Auth with Django
  - Custom authentication backend
  - User model mapping
- [ ] Extract forum code as Django app
- [ ] Set up React 19 + Vite + Tailwind CSS 4
  - Modern build setup
  - Hot module replacement
  - Tailwind configuration
  - Dark/light mode setup

#### Week 3-4: Database & API
- [ ] Design unified database schema
- [ ] Set up PostgreSQL for blog/forum
- [ ] Set up Firestore for plant ID
- [ ] Create REST API endpoints (Django REST Framework)
  - Blog posts (read-only for mobile)
  - Forum topics (read-only for mobile)
  - User profiles
- [ ] Document API for Flutter team (you!)

**Deliverables:**
- Firebase project configured
- Django/Wagtail running with Firebase Auth
- REST API documented
- Forum extracted as Django app

---

### Phase 2: Flutter Mobile App - Foundation (4-5 weeks)

**Objective**: Build core Flutter app structure

#### Week 1: Project Setup
- [ ] Create Flutter project structure
- [ ] Set up Firebase Flutter plugins
- [ ] Configure iOS and Android projects
- [ ] Set up Riverpod state management
  - Create provider structure
  - Set up dependency injection
- [ ] Implement Figma design system
  - Extract colors, typography, spacing from Figma
  - Create theme configuration (dark/light)
  - Set up custom widgets matching design
- [ ] Create app architecture (clean architecture)
- [ ] Set up routing

#### Week 2: Authentication
- [ ] Implement Firebase Auth UI
- [ ] Sign up flow
- [ ] Login flow
- [ ] Password reset
- [ ] Profile management
- [ ] Persist auth state

#### Week 3-4: Camera & Image Handling
- [ ] Camera integration
  - Platform-specific permissions
  - Camera preview
  - Image capture
- [ ] Image picker (gallery)
- [ ] Image preprocessing
- [ ] Upload to Firebase Storage
- [ ] Progress indicators

#### Week 5: Plant ID Integration
- [ ] Integrate Plant.id API
- [ ] Send images to API
- [ ] Parse API responses
- [ ] Display plant identification results
- [ ] Save results to Firestore
- [ ] History/saved plants screen

**Deliverables:**
- Flutter app with auth
- Camera functionality
- Basic plant ID working
- Data saved to Firestore

---

### Phase 3: Flutter Mobile App - Features (4-5 weeks)

**Objective**: Complete mobile app features

#### Week 1-2: Plant ID Features
- [ ] Plant details screen
- [ ] Disease diagnosis screen
- [ ] Health assessment
- [ ] Care recommendations
- [ ] Similar plants
- [ ] Share functionality

#### Week 2-3: Blog & Forum Integration
- [ ] Connect to Wagtail Headless API
- [ ] Blog list screen (matches Figma design)
- [ ] Blog detail screen
- [ ] Basic forum features (mobile simplified)
  - Forum topics list
  - Topic detail/reading
  - Basic posting capability
  - Reply to topics
- [ ] Pull-to-refresh
- [ ] Implement dark/light theme toggle

#### Week 3-4: User Profile & History
- [ ] User profile screen
- [ ] Edit profile
- [ ] Plant identification history
- [ ] Favorite plants
- [ ] Settings screen
- [ ] Dark mode support

#### Week 4-5: Offline Support
- [ ] Offline plant ID history
- [ ] Cached blog posts
- [ ] Sync when online
- [ ] Network status detection
- [ ] Offline indicators

**Deliverables:**
- Complete feature set
- Blog/forum reading
- User profiles
- Offline support

---

### Phase 4: Web App Refinement (2-3 weeks)

**Objective**: Complete web-specific features

#### Week 1: Image Upload (No Camera)
- [ ] Simple file upload form (Tailwind styled)
- [ ] Upload to Firebase Storage
- [ ] Submit to Plant.id API
- [ ] Display results (matching mobile design system)
- [ ] Save to Firestore
- [ ] Link to user account

#### Week 2: Blog & Forum Polish
- [ ] Build React components with Tailwind CSS 4
  - Blog listing page
  - Blog detail page
  - Forum categories
  - Forum topics
  - Topic detail with replies
- [ ] Implement dark/light mode toggle
- [ ] User profiles on web
- [ ] Comments system
- [ ] Search functionality
- [ ] Responsive design (mobile, tablet, desktop)

#### Week 3: Admin & Moderation
- [ ] Admin dashboard
- [ ] Content moderation
- [ ] User management
- [ ] Analytics dashboard
- [ ] Export tools

**Deliverables:**
- Web app fully functional
- Upload-only plant ID
- Complete blog/forum
- Admin tools

---

### Phase 5: Testing & Polish (3-4 weeks)

**Objective**: Ensure quality and fix bugs

#### Week 1-2: Testing
- [ ] Unit tests (Flutter)
- [ ] Integration tests (Flutter)
- [ ] Widget tests (Flutter)
- [ ] Django tests
- [ ] API tests
- [ ] End-to-end tests
- [ ] Performance testing
- [ ] Security audit

#### Week 2-3: Polish
- [ ] UI/UX improvements
- [ ] Animations and transitions
- [ ] Loading states
- [ ] Error handling
- [ ] Empty states
- [ ] Accessibility
- [ ] Internationalization prep

#### Week 3-4: Beta Testing
- [ ] TestFlight setup (iOS)
- [ ] Google Play Internal Testing (Android)
- [ ] Recruit beta testers
- [ ] Gather feedback
- [ ] Fix bugs
- [ ] Iterate

**Deliverables:**
- Tested applications
- Beta feedback incorporated
- Bug fixes completed
- Documentation updated

---

### Phase 6: Deployment & Launch (2 weeks)

**Objective**: Deploy to production

#### Week 1: Pre-launch
- [ ] Production Firebase project
- [ ] Production Django deployment
- [ ] Domain setup
- [ ] SSL certificates
- [ ] Database migration
- [ ] Environment variables
- [ ] Monitoring setup
- [ ] Backup strategy

#### Week 2: Launch
- [ ] App Store submission (iOS)
- [ ] Google Play submission (Android)
- [ ] Web deployment
- [ ] Launch communications
- [ ] Monitor for issues
- [ ] Hotfix preparation

**Deliverables:**
- Apps in stores
- Web app live
- Monitoring active
- Support ready

---

## Key Decisions

### Decisions Made
1. ✅ **Firebase over Supabase**: Better Flutter support, proven technology
2. ✅ **Keep Wagtail**: Preserve your custom forum work
3. ✅ **Latest versions**: Flutter 3.35, Django 5.2, Wagtail 7.0 LTS, React 19, Tailwind 4
4. ✅ **Hybrid architecture**: Firebase for auth/mobile data, PostgreSQL for web content
5. ✅ **Mobile-first plant ID**: Camera features only on mobile
6. ✅ **Headless Wagtail + React 19**: Modern JAMstack approach with Tailwind CSS 4
7. ✅ **Riverpod**: State management for Flutter
8. ✅ **Design System**: Figma design with dark/light mode themes (from Plantidentificationapp repo)
9. ✅ **Mobile Forum**: Basic functionality, simplified compared to web

### Decisions Pending
1. ⏳ **Internationalization**: Support multiple languages from day 1?
2. ⏳ **Mobile forum features**: Which specific features to include in "basic" version?

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Firebase Auth integration with Django | Medium | High | Use Firebase Admin SDK, thorough testing |
| Data migration from current DB | Low | High | Careful planning, backups, test migration |
| Flutter learning curve | Medium | Medium | Ample time, good documentation, community |
| API rate limits (Plant.id) | Medium | Medium | Implement caching, monitor usage |
| Cross-platform bugs | High | Medium | Extensive testing, beta program |
| Forum code extraction | Low | High | Careful documentation, gradual refactoring |

### Project Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Scope creep | Medium | High | Clear phases, stick to MVP |
| Solo developer burnout | Medium | High | No deadlines, take breaks, enjoy the process |
| Technology changes mid-project | Low | Medium | Use stable LTS versions |
| Loss of existing features | Low | High | Comprehensive feature audit before starting |

---

## Success Metrics

### Phase Completion Metrics
- [ ] All tests passing
- [ ] No critical bugs
- [ ] Documentation complete
- [ ] Code reviewed (self-review with checklist)

### Launch Metrics
- **Technical**:
  - App load time < 2 seconds
  - API response time < 1 second
  - Crash rate < 1%
  - Test coverage > 70%

- **User Experience**:
  - Plant ID accuracy (Plant.id API dependent)
  - User can complete signup in < 2 minutes
  - Clear error messages
  - Intuitive navigation

- **Business** (If applicable):
  - Cost within budget
  - All original features preserved
  - Forum users satisfied
  - Mobile adoption growing

---

## Next Steps

### Immediate Actions (This Week)
1. Review and approve this plan
2. Create detailed current state documentation
3. Set up Firebase project
4. Audit Wagtail/forum customizations
5. Create GitHub issues for Phase 1 tasks

### Questions to Answer
1. Do you want to keep React on web or simplify to Wagtail templates?
2. Should mobile users be able to post to forums, or read-only?
3. Any specific forum features that are critical to preserve?
4. Do you have design preferences for the Flutter app?

---

## Appendices

### A. Folder Structure (Proposed)

```
plant_id_community/
├── PLANNING/                    # This folder
│   ├── 01_TECHNOLOGY_STACK.md
│   ├── 02_FIREBASE_VS_SUPABASE.md
│   ├── 03_MASTER_PLAN.md        # This document
│   ├── 04_DATABASE_SCHEMA.md    # To be created
│   ├── 05_API_DOCUMENTATION.md  # To be created
│   ├── 06_WAGTAIL_AUDIT.md      # To be created
│   └── 07_DESIGN_SYSTEM.md      # Figma design documentation
│
├── backend/                     # Django/Wagtail Headless CMS
│   ├── config/                  # Django settings
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── blog/                # Wagtail blog (headless)
│   │   ├── forum/               # Custom forum (extracted, headless API)
│   │   ├── users/               # User management
│   │   └── api/                 # REST API configurations
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── development.txt
│   │   └── production.txt
│   └── manage.py
│
├── frontend/                    # React 19 + Tailwind CSS 4
│   ├── src/
│   │   ├── components/
│   │   │   ├── blog/
│   │   │   ├── forum/
│   │   │   ├── auth/
│   │   │   ├── plant-id/
│   │   │   └── ui/              # Shared UI components
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/            # API clients
│   │   ├── store/               # State management
│   │   ├── styles/
│   │   │   └── tailwind.css
│   │   ├── utils/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   ├── package.json
│   └── tsconfig.json
│
├── mobile/                      # Flutter app (Riverpod)
│   ├── lib/
│   │   ├── core/
│   │   │   ├── router/
│   │   │   ├── theme/           # Dark/Light theme from Figma
│   │   │   │   ├── colors.dart
│   │   │   │   ├── typography.dart
│   │   │   │   ├── theme_data.dart
│   │   │   │   └── theme_provider.dart
│   │   │   └── constants/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   │   ├── data/
│   │   │   │   ├── domain/
│   │   │   │   └── presentation/
│   │   │   ├── plant_id/
│   │   │   │   ├── data/
│   │   │   │   ├── domain/
│   │   │   │   └── presentation/
│   │   │   ├── blog/
│   │   │   ├── forum/           # Basic mobile forum
│   │   │   └── profile/
│   │   ├── shared/
│   │   │   ├── widgets/         # Reusable widgets from Figma
│   │   │   ├── providers/       # Riverpod providers
│   │   │   └── utils/
│   │   └── main.dart
│   ├── assets/
│   │   ├── images/
│   │   ├── icons/
│   │   └── fonts/
│   ├── android/
│   ├── ios/
│   ├── pubspec.yaml
│   └── test/
│
├── shared/                      # Shared resources
│   ├── firebase-config/
│   ├── design/                  # Figma exports, design tokens
│   │   ├── colors.json
│   │   ├── typography.json
│   │   └── spacing.json
│   └── docs/
│
├── scripts/                     # Utility scripts
├── .env.example
├── .gitignore
├── README.md
```

### B. Timeline Summary

**Total Estimated Time**: 18-24 weeks (4.5-6 months)

Remember: **No deadlines!** This is your pace.

- Pre-Phase: 2-3 weeks
- Phase 1: 3-4 weeks
- Phase 2: 4-5 weeks
- Phase 3: 4-5 weeks
- Phase 4: 2-3 weeks
- Phase 5: 3-4 weeks
- Phase 6: 2 weeks

---

**Document Status**: Draft v1.0
**Last Updated**: October 21, 2025
**Owner**: William Tower
**Next Review**: After stakeholder approval
