# Technology Stack - Latest Versions (October 2025)

## Overview
This document outlines the latest stable versions of all technologies we'll be using in the restructured Plant ID Community project.

---

## Mobile - Flutter

### Flutter SDK
- **Latest Stable Version**: Flutter 3.35 (August 2025)
- **Dart Version**: 3.9
- **Key Features**:
  - Hot reload now available on web (no longer experimental)
  - Widget Previewer support
  - Enhanced platform integration
  - Improved performance optimizations
  - Support for latest iOS and Android versions

### Platform Support
- **iOS**: iOS 12.0+ (with specific features for iOS 13+)
- **Android**: API 21+ (Android 5.0+)
- **Platform Detection**: Built-in support for OS detection and platform-specific features

### Key Flutter Packages (to be determined)
- `firebase_core`: Firebase initialization
- `firebase_auth`: Authentication
- `cloud_firestore`: Database
- `firebase_storage`: File storage
- `camera`: Camera functionality for plant ID
- `image_picker`: Image selection
- Platform-specific permissions handling

---

## Backend - Firebase vs Supabase

### Firebase (JavaScript SDK)
- **Latest Version**: 12.4.0 (October 9, 2025)
- **Key Services**:
  - **Authentication**: Multi-provider, phone auth, custom tokens
  - **Firestore**: Real-time NoSQL database
  - **Cloud Storage**: File storage with CDN
  - **Cloud Functions**: Serverless functions
  - **Hosting**: Static site hosting
  - **AI Logic**: Gemini API integration (new in v11.8.0)
  - **App Check**: Security and abuse prevention

- **Node.js Requirement**: Node 20+ (as of v12.0.0)
- **ES Version**: ES2020
- **TypeScript**: 5.5.4+

### Supabase (Alternative - to be evaluated)
- **Version**: Latest stable
- **Key Services**:
  - PostgreSQL database (instead of NoSQL)
  - Row-level security
  - Real-time subscriptions
  - Built-in authentication
  - Storage
  - Edge functions
  - RESTful API auto-generated

### Decision Point
**We need to decide**: Firebase vs Supabase based on:
1. Cost structure for expected usage
2. Real-time capabilities requirements
3. SQL vs NoSQL preference
4. Vendor lock-in considerations
5. Developer experience

---

## Web - Django + Wagtail CMS

### Django
- **Latest Version**: 5.2 (compatible with Wagtail 7.x)
- **Python Version**: 3.10+ recommended
- **Key Features**:
  - Async support
  - Enhanced ORM
  - Modern security features

### Wagtail CMS
- **Latest LTS Version**: Wagtail 7.0 LTS
  - Released as LTS (Long Term Support)
  - Django 4.2+ and Django 5.2 compatible
  - Support until 2027

- **Previous LTS**: Wagtail 6.3 LTS (if conservative approach preferred)

- **Key Features**:
  - StreamField for flexible content
  - Rich text editing
  - Image management
  - SEO features
  - Multi-site support
  - API support (for headless if needed)

**CRITICAL**: We are preserving your custom forum modifications from the current setup.

### Forum System
- **Current**: Custom forum built with Wagtail (to be documented)
- **Approach**: Extract and preserve forum code, potentially as Django app
- **Alternative**: Consider integrating with Discourse API if needed

---

## Web Frontend (Optional - for enhanced web experience)

### React (if needed for dynamic web features)
- **Version**: 19.x (latest)
- **Build Tool**: Vite 5.x
- **Styling**: Tailwind CSS 4.x

**Note**: May not be necessary if Wagtail templates are sufficient for web blog/forum.

---

## External APIs

### Plant.id API
- **Current Integration**: Maintain existing implementation
- **Features**:
  - Plant identification
  - Disease diagnosis
  - Health assessment
- **Cost**: Review current plan, optimize for mobile-only premium features

---

## Development Tools

### Version Control
- **Git**: Latest
- **Platform**: GitHub (existing repo)

### Code Quality
- **Python**: Black, flake8, mypy
- **Dart/Flutter**: Built-in formatter and analyzer
- **JavaScript** (if needed): ESLint, Prettier

### Testing
- **Flutter**: Built-in testing framework
- **Django**: pytest, pytest-django
- **Wagtail**: Wagtail's testing utilities

---

## Infrastructure & Deployment

### Firebase Hosting (if using Firebase)
- Static site hosting
- CDN included
- SSL certificates
- Custom domain support

### Alternative Hosting (if using Supabase)
- Vercel/Netlify for web frontend
- DigitalOcean/Railway for Django backend
- Supabase for database and auth

---

## Development Environment

### Recommended Setup
- **Python**: 3.11 or 3.12
- **Node.js**: 20.x LTS
- **Flutter**: 3.35
- **IDE**: VS Code with extensions:
  - Flutter
  - Python
  - Wagtail Snippets
  - Firebase

---

## Next Steps

1. **Decision Required**: Firebase vs Supabase
2. **Audit**: Document current Wagtail/forum customizations
3. **Plan**: Database schema design
4. **Prototype**: Test Firebase/Supabase with Flutter
5. **Extract**: Preserve forum code as separate module

---

## Version Compatibility Matrix

| Component | Version | Compatible With |
|-----------|---------|-----------------|
| Flutter | 3.35 | Dart 3.9, iOS 12+, Android 5.0+ |
| Firebase JS SDK | 12.4.0 | Node 20+, ES2020+ |
| Django | 5.2 | Python 3.10+, Wagtail 7.x |
| Wagtail | 7.0 LTS | Django 4.2-5.2, Python 3.10+ |
| Python | 3.11/3.12 | Django 5.2, Latest packages |
| Node.js | 20.x LTS | Firebase 12.x, Modern tooling |

---

**Document Status**: Draft v1.0
**Last Updated**: October 21, 2025
**Next Review**: After Firebase vs Supabase decision
