# Project Planning Documents - README

This folder contains all planning documents for the Plant ID Community project restructure.

## Overview

We are transforming the Plant ID Community from a Progressive Web App (PWA) into:
- **Mobile Apps**: Flutter-based iOS and Android apps with full plant identification features (camera, disease diagnosis)
- **Web App**: Django/Wagtail-based blog and forum platform with limited plant ID (upload only, no camera)

## Planning Documents

### 1. Technology Stack (`01_TECHNOLOGY_STACK.md`)
**Purpose**: Documents all technologies, frameworks, and their latest stable versions.

**Key Sections**:
- Flutter 3.35 + Dart 3.9
- Firebase 12.4.0 (JavaScript SDK)
- Django 5.2 + Wagtail 7.0 LTS
- React 19 + Vite + Tailwind CSS 4
- Riverpod state management
- Plant.id API
- Development tools and environment

**Status**: ✅ Complete

---

### 2. Firebase vs Supabase Comparison (`02_FIREBASE_VS_SUPABASE.md`)
**Purpose**: Comprehensive analysis to choose between Firebase and Supabase.

**Key Sections**:
- Feature-by-feature comparison
- Cost analysis
- Flutter integration comparison
- Use case analysis
- **Recommendation**: Firebase (with hybrid approach)

**Decision**: ✅ Firebase chosen

---

### 3. Master Plan (`03_MASTER_PLAN.md`)
**Purpose**: Complete project restructure plan with phases, timeline, and roadmap.

**Key Sections**:
- Current state analysis
- Target architecture (headless Wagtail + React frontend)
- 6-phase development roadmap (18-24 weeks)
- Risk assessment
- Success metrics
- Folder structure proposal

**Status**: ✅ Complete - Updated with all architecture decisions

---

### 4. Design System & UI Guidelines (`04_DESIGN_SYSTEM.md`)
**Purpose**: Document design tokens, themes, component library, and UI patterns.

**Key Sections**:
- Dual theme support (dark/light mode)
- Complete design token system extracted from Figma:
  * Colors (green/emerald brand palette + accent colors)
  * Typography (system fonts, sizes, weights)
  * Spacing (0.25rem base unit)
  * Border radius (0.625rem base)
  * Gradients and visual effects
- Screen designs documentation (all mobile screens)
- Component library (based on shadcn/ui)
- Accessibility guidelines
- Animation and transition standards
- Cross-platform implementation guide (Tailwind + Flutter)

**Status**: ✅ Complete - Design tokens extracted from repository

**Design Sources**:
- GitHub: https://github.com/Xertox1234/Plantidentificationapp
- Figma: https://www.figma.com/design/c4gvEaqEnNcDslZ1XcQBF2/Plant-Identification-App

---

### 5. User Stories (`05_USER_STORIES.md`)
**Purpose**: Comprehensive user stories for mobile and web platforms to guide UI/UX design and development.

**Key Sections**:
- 4 detailed user personas (beginner, enthusiast, expert, content creator)
- 16 epics covering all features:
  * Mobile: Onboarding, Plant ID, Collection, Forum (basic), Profile, Navigation
  * Web: Blog, Forum (full), Upload ID, Dashboard, Admin
  * Shared: Future features (reminders, social, wishlist)
- Admin and moderation stories
- Story mapping with MVP priorities
- Success metrics and KPIs
- 100+ detailed user stories with acceptance criteria

**Status**: ✅ Complete - Ready for database schema and development

---

### 6. Database Schema Design (`06_DATABASE_SCHEMA.md`)
**Purpose**: Complete database architecture using Firebase Firestore and PostgreSQL.

**Key Sections**:
- Hybrid database strategy (Firestore + PostgreSQL)
- **Firebase/Firestore Collections** (7 collections):
  * users - User profiles and settings
  * plantIdentifications - Plant ID requests and results
  * userPlantCollections - Saved plant library
  * notifications - Real-time user notifications
  * deviceTokens - Push notification tokens
  * forumTopics - Cached forum data for mobile
  * analytics - Usage tracking
- **PostgreSQL Tables** (13+ tables):
  * user_profiles - Extended user data
  * forum_categories, forum_topics, forum_replies
  * forum_tags, forum_likes, forum_attachments
  * blog_posts - Wagtail CMS content
  * moderation_logs, email_subscriptions
- Data synchronization strategy (bidirectional sync)
- Security rules (Firestore & PostgreSQL RLS)
- Indexes and performance optimization
- Migration and backup strategies

**Status**: ✅ Complete - Ready for API documentation and implementation

---

### 7. API Documentation (`07_API_DOCUMENTATION.md`)
**Purpose**: Complete REST API documentation for all platform endpoints.

**Key Sections**:
- **Plant Identification APIs**: Submit, retrieve, save plant IDs (5 endpoints)
- **User APIs**: Profile management, settings, collections (5 endpoints)
- **Forum APIs**: Topics, replies, likes, search, moderation (15 endpoints)
- **Blog APIs**: Posts, categories, search via headless Wagtail (4 endpoints)
- **Notification APIs**: Get, mark read, manage notifications (4 endpoints)
- **Admin APIs**: Dashboard stats, user management, moderation queue (6 endpoints)
- Authentication flow (Firebase Auth + JWT tokens)
- Error handling with standard error codes
- Rate limiting (1000/hour reads, 300/hour writes)
- Webhooks for real-time events
- OpenAPI 3.0 specification support
- SDK examples for Flutter and React

**API Architecture**:
- Mobile apps → Firebase SDK (direct) + Django REST API
- Web app → Django REST API (headless Wagtail consumer)
- Standard JSON response format
- Request/response examples for all endpoints

**Status**: ✅ Complete - Ready for implementation

---

### 8. Wagtail & Forum Implementation Audit (`08_WAGTAIL_FORUM_AUDIT.md`)
**Purpose**: Document existing Wagtail and Django Machina forum customizations to preserve during migration.

**Key Sections**:
- **Current Stack Analysis**: Django 5.2 LTS, Wagtail 7.0 LTS, Django Machina 1.3.0, React 19, PostgreSQL, 72+ models
- **Wagtail Implementation**: 4 custom page types wrapping Machina forums with flat StreamField blocks (no nesting)
- **StreamField Blocks**: Custom PlantMentionBlock linking to plant species pages, forum announcements, rules, statistics
- **Django Machina Integration**: Fully integrated hierarchical forum with topics, posts, moderation, permissions, search (Haystack)
- **Custom Apps Overview**: 7 Django apps totaling ~57 custom models + ~15 Machina models
- **PlantSpecies Model**: Massive 2,854-line model with comprehensive botanical data
- **External APIs**: PlantNet (AI plant ID), Trefle (plant database), OpenAI (wagtail-ai content generation)
- **Real-time Features**: WebSocket support via Django Channels for live plant identification updates
- **Security Implementation**: UUID references, rate limiting, CSP, CORS, file validation, IDOR prevention
- **Background Processing**: Celery tasks for async plant ID, disease diagnosis, image processing, emails

**Migration Strategy**:
- **Preserve All Code**: 783 commits of mature, production-ready code - extend, don't rewrite
- **Hybrid Database**: Keep PostgreSQL for web (Wagtail/forums), add Firestore for mobile, sync via Cloud Functions
- **Dual Authentication**: Keep Django auth for web, add Firebase auth for mobile, link via firebase_uid field
- **Keep Django Machina**: Add custom REST API layer, cache forum data in Firestore for mobile offline access
- **Headless Wagtail**: Use Wagtail API v2 for React consumption, preserve all StreamField structures
- **Data Sync**: Bidirectional user profile sync (PostgreSQL ↔ Firestore), one-way forum cache (PostgreSQL → Firestore)

**Preservation Checklist**:
- 72 database models, all Wagtail pages, StreamField blocks, custom serializers, templates, admin customizations
- Forum data (topics, posts, categories), plant database, user collections, identification history
- API integrations, OAuth providers, WebSocket consumers, Celery tasks, security middleware

**Status**: ✅ Complete - Comprehensive 300+ line audit with full implementation details

---

## Current Status

### All Planning Documents Complete! 🎉

**Completed (8 documents)**:
1. ✅ Technology Stack Research
2. ✅ Firebase vs Supabase Comparison  
3. ✅ Master Plan & Roadmap
4. ✅ Design System Extraction
5. ✅ User Stories (100+)
6. ✅ Database Schema (Hybrid)
7. ✅ API Documentation (39 endpoints)
8. ✅ Wagtail/Forum Audit (783 commits analyzed)

### Ready for Phase 1 Implementation

**Next Steps**:
1. Set up Firebase project (Authentication, Firestore, Storage, Functions)
2. Extend Django CustomUser model with firebase_uid field
3. Create Firebase admin backend for dual authentication
4. Implement Cloud Functions for user profile sync
5. Create mobile-specific API endpoints
6. Begin Flutter app development

---

### 6. Wagtail & Forum Audit (Coming Soon)
**Purpose**: Document existing Wagtail setup and custom forum modifications to ensure preservation.

**Will Include**:
- Wagtail page models
- Forum database structure
- Custom forum features
- StreamField configurations
- Templates and views
- Any custom Django apps

**Status**: ⏳ Not started

---

## Current Status

### Latest Stable Versions (as of October 2025)
- **Flutter**: 3.35
- **Dart**: 3.9
- **Firebase JS SDK**: 12.4.0
- **Django**: 5.2
- **Wagtail**: 7.0 LTS
- **Python**: 3.11-3.12
- **Node.js**: 20.x LTS

### Key Decisions Made
1. ✅ **Firebase** over Supabase for auth and mobile database
2. ✅ **Keep Wagtail** and preserve custom forum work
3. ✅ **Hybrid approach**: Firebase for auth/mobile, PostgreSQL for web content
4. ✅ **Mobile-first** plant ID with camera features
5. ✅ **Web simplified** to blog/forum with upload-only plant ID

### Pending Decisions
- State management choice for Flutter (Provider, Riverpod, Bloc)
- Keep React on web or simplify to Wagtail templates
- Forum posting from mobile (read-only vs full posting)
- Internationalization from day 1?

---

## How to Use These Documents

### For Development
1. Read documents in order (01 → 02 → 03)
2. Reference as needed during development
3. Update when decisions change
4. Keep synchronized with actual implementation

### For Planning
- Use Master Plan phases as sprint planning guide
- Track progress against roadmap
- Update estimates as you learn
- Add new documents as needed

---

## Next Steps

### Immediate (This Week)
1. Review and approve all planning documents
2. Create database schema document
3. Start Wagtail/forum audit
4. Set up Firebase project
5. Create first GitHub issues

### Short Term (Next 2-3 Weeks)
1. Complete Pre-Phase discovery
2. Document all existing customizations
3. Set up development environments
4. Start Phase 1 (Foundation & Setup)

---

## Questions & Answers

### Q: Why not keep the PWA?
**A**: We want native mobile apps for better camera integration, offline support, and platform-specific features. The web will focus on blog/forum where it excels.

### Q: Will we lose any existing features?
**A**: No. All features will be preserved. Some will move to mobile (camera plant ID), others stay on web (blog/forum).

### Q: Why Firebase if it has vendor lock-in?
**A**: Superior Flutter support, mature technology, and we're using a hybrid approach to minimize lock-in. Blog/forum data stays in PostgreSQL.

### Q: Can I change these plans?
**A**: Absolutely! These are living documents. Update them as you learn and make better decisions.

### Q: What if I want to use Supabase instead?
**A**: You can! The architecture supports it. You'd need to use community Flutter packages and adjust the auth integration.

---

## Document Maintenance

### Update Frequency
- **Technology Stack**: Update when versions change
- **Master Plan**: Update weekly during active development
- **API Docs**: Update with each API change
- **Database Schema**: Update when schema changes

### Version Control
All documents are version controlled in Git. Major changes should:
1. Be documented in commit messages
2. Update the "Last Updated" date
3. Increment version number (e.g., v1.0 → v1.1)

---

## Resources

### Official Documentation
- [Flutter Docs](https://docs.flutter.dev/)
- [Firebase Docs](https://firebase.google.com/docs)
- [Django Docs](https://docs.djangoproject.com/)
- [Wagtail Docs](https://docs.wagtail.org/)
- [Plant.id API Docs](https://web.plant.id/plant-identification-api/)

### Community
- [Flutter Community](https://flutter.dev/community)
- [Wagtail Community](https://wagtail.org/community/)
- [Django Community](https://www.djangoproject.com/community/)

---

## Contact

**Project Owner**: William Tower
**Repository**: https://github.com/Xertox1234/plant_id_community
**Status**: Planning Phase

---

**Last Updated**: October 21, 2025
**Next Review**: After Wagtail audit completion
