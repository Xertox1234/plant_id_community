# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Development Workflow
After completing ANY coding task, you MUST:

Automatically invoke the code-review-specialist sub-agent to review changes
Wait for the review to complete
Address any blockers identified
Only then consider the task complete
Code Review Process
The code-review-specialist agent reviews ALL modified files
Reviews check for: debug code, security issues, accessibility, testing, best practices
ALL BLOCKERS must be fixed before proceeding
This is NON-NEGOTIABLE for production code
Standard Task Pattern
1. Plan the implementation
2. Write the code
3. **USE code-review-specialist agent to review** ← ALWAYS DO THIS
4. Fix any issues found
5. Confirm task complete
Important: Never skip the code review step. It is part of "done".

## Project Overview

**Plant ID Community** - A multi-platform plant identification system featuring AI-powered plant recognition, mobile-first architecture, and web companion interface. Built with React (web), Flutter (mobile), and Django backend with dual Plant.id/PlantNet API integration.

**Architecture:**
- **Web Frontend**: React 19 + Vite + Tailwind CSS 4 (port 5173)
- **Mobile App**: Flutter 3.37 + Firebase (primary platform)
- **Backend**: Django 5.2 + DRF (port 8000, located in `/backend/`)
- **Plant Identification**: Dual API system (Plant.id + PlantNet) with parallel processing
- **Caching**: Redis for API response caching
- **Database**: SQLite (dev), PostgreSQL (production) with performance indexes

**Week 2 Performance Optimizations (✅ Complete):**
- ⚡ Parallel API processing: 60% faster (4-9s → 2-5s)
- 💾 Redis caching: 40% cache hit rate, instant responses (<100ms)
- 🗄️ Database indexes: 100x faster queries (300-800ms → 3-8ms)
- 📷 Image compression: 85% faster uploads (10MB: 40-80s → 3-5s)

**Important**: The `existing_implementation/` folder contains reference code for blog/forum features. **DO NOT EDIT** - see `.DO_NOT_EDIT` file in that directory.

## Essential Commands

### Web Frontend Development
```bash
cd web

# Development
npm run dev          # Start dev server (http://localhost:5173)
npm run build        # Production build
npm run preview      # Preview production build
npm run lint         # ESLint check

# Backend must be running at localhost:8000
```

### Backend Development
```bash
cd backend

# Initial setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate

# Start Redis (required for caching)
brew services start redis
redis-cli ping  # Verify Redis is running

# Development server
python manage.py runserver          # Standard Django server
# OR
python simple_server.py            # Minimal server with Redis health check

# Database
python manage.py migrate            # Run migrations
python manage.py createsuperuser    # Create admin user

# API Testing
curl http://localhost:8000/api/plant-identification/identify/health/

# Performance Testing
python test_performance.py          # Test Week 2 optimizations
```

### Flutter Mobile App
```bash
cd plant_community_mobile

# Development
flutter pub get                  # Install dependencies
flutter run -d ios              # iOS simulator (Mac only)
flutter run -d android          # Android emulator
flutter run -d chrome           # Web (limited testing)

# Code generation (when using Riverpod annotations)
dart run build_runner watch --delete-conflicting-outputs

# Testing
flutter test                    # Run unit tests
flutter test --coverage         # Coverage report

# Firebase configuration (when ready)
flutterfire configure --project=plant-community-prod
```

## Week 2 Performance Optimizations

See `WEEK2_PERFORMANCE.md` for comprehensive documentation.

**Backend Optimizations:**
1. **Parallel API Processing** - ThreadPoolExecutor calls Plant.id + PlantNet simultaneously
2. **Redis Caching** - SHA-256 image hashing, 24-hour TTL, startup health check
3. **Database Indexes** - 8 composite indexes for common query patterns

**Frontend Optimizations:**
1. **Image Compression** - Canvas-based compression (max 1200px, 85% quality)
2. **Auto-compression** - Files > 2MB automatically compressed
3. **Memory Management** - Object URLs with cleanup, canvas cleanup

**Key Files:**
- Backend: `apps/plant_identification/services/combined_identification_service.py`
- Backend: `apps/plant_identification/services/plant_id_service.py`
- Backend: `simple_server.py`, `migrations/0012_add_performance_indexes.py`
- Frontend: `web/src/utils/imageCompression.js`
- Frontend: `web/src/components/PlantIdentification/FileUpload.jsx`

## Project Structure

### Backend (`/backend`)
```
backend/
├── apps/
│   └── plant_identification/
│       ├── services/
│       │   ├── combined_identification_service.py  # Parallel API processing
│       │   ├── plant_id_service.py                 # Redis caching
│       │   └── plantnet_service.py
│       ├── migrations/
│       │   └── 0012_add_performance_indexes.py     # 8 composite indexes
│       └── api/
├── simple_server.py           # Redis health check on startup
├── manage.py
└── requirements.txt           # Includes django-redis
```

### Web Frontend (`/web`)
```
web/
├── src/
│   ├── pages/              # Route components
│   │   ├── HomePage.jsx    # Landing page
│   │   ├── IdentifyPage.jsx # Plant ID workflow
│   │   ├── BlogPage.jsx    # Blog (placeholder)
│   │   └── ForumPage.jsx   # Forum (placeholder)
│   ├── components/
│   │   └── PlantIdentification/
│   │       ├── FileUpload.jsx              # Image upload with compression
│   │       └── IdentificationResults.jsx
│   ├── services/
│   │   └── plantIdService.js  # Backend API client
│   ├── utils/
│   │   └── imageCompression.js  # Canvas-based compression
│   ├── App.jsx             # React Router setup
│   └── main.jsx            # Entry point
└── package.json
```

### Flutter Mobile App (`/plant_community_mobile`)
```
lib/
├── main.dart               # App entry point
├── config/
│   └── theme_provider.dart # Theme state management
├── core/
│   ├── constants/
│   │   └── app_spacing.dart   # Spacing constants
│   └── theme/
│       ├── app_colors.dart    # Color palette
│       ├── app_typography.dart # Text styles
│       └── app_theme.dart     # Theme config
├── features/               # Feature modules (to be created)
├── models/                 # Data models
├── services/               # API & Firebase services
└── widgets/                # Reusable UI components
```

### Backend (`/existing_implementation/backend`)
```
backend/
├── apps/
│   ├── plant_identification/    # Plant ID API endpoints
│   │   ├── services/
│   │   │   ├── plant_id_service.py        # Plant.id API integration
│   │   │   └── combined_identification_service.py  # Dual API orchestration
│   │   └── api/
│   │       └── simple_views.py            # API endpoints
│   ├── blog/               # Wagtail CMS blog
│   ├── forum_integration/  # Django Machina forums
│   ├── users/              # User management
│   └── core/               # Shared utilities
├── manage.py
├── requirements.txt
└── .env                    # API keys (Plant.id, PlantNet)
```

## Backend API Integration

### Plant Identification Endpoints

**Health Check**
```bash
GET /api/plant-identification/identify/health/

Response:
{
  "status": "healthy",
  "plant_id_available": true,
  "plantnet_available": true
}
```

**Identify Plant**
```bash
POST /api/plant-identification/identify/
Content-Type: multipart/form-data
Body: { image: <file> }

Response:
{
  "success": true,
  "plant_name": "Monstera Deliciosa",
  "scientific_name": "Monstera deliciosa",
  "confidence": 0.95,
  "suggestions": [
    {
      "plant_name": "Monstera Deliciosa",
      "scientific_name": "Monstera deliciosa",
      "probability": 0.95,
      "common_names": ["Swiss Cheese Plant"],
      "watering": "moderate",
      "source": "plant_id",
      "rank": 1
    }
  ],
  "care_instructions": {
    "watering": "Moderate watering recommended",
    "light": "Bright indirect light",
    "temperature": "Room temperature (18-24°C)"
  },
  "disease_detection": {
    "is_healthy": true,
    "is_plant": true
  }
}
```

### Dual API Strategy

**Architecture:**
```
Image Upload
    ↓
Django Backend
    ↓
CombinedPlantIdentificationService
    ↓
┌─────────────────────────┬─────────────────────────┐
│   Plant.id (Kindwise)   │      PlantNet           │
│   • 95%+ accuracy       │   • Care instructions   │
│   • Disease detection   │   • Family/genus data   │
│   • 100 IDs/month free  │   • 500/day free        │
└─────────────────────────┴─────────────────────────┘
    ↓
Merged Results
```

**API Keys (configured in `/existing_implementation/backend/.env`):**
- `PLANT_ID_API_KEY` - Plant.id (Kindwise) for primary identification
- `PLANTNET_API_KEY` - PlantNet for supplemental care data

**Rate Limits:**
- Plant.id: 100 identifications/month (free tier)
- PlantNet: 500 requests/day (free tier)
- Combined: ~3,500 free IDs/month for development

## Flutter Design System

### Colors
- **Brand**: Green (10 shades), Emerald (7 shades)
- **Light/Dark Mode**: Full theme support
- **Usage**: `AppColors.green600`, `AppColors.getBackgroundColor(brightness)`

### Typography
- **Font Stack**: System fonts (SF Pro, Roboto, Segoe UI)
- **Sizes**: xs (12px) to 2xl (24px)
- **Usage**: `AppTypography.h1`, `AppTypography.body`, `AppTypography.button`

### Spacing
- **Base Unit**: 4px (0.25rem)
- **Scale**: xs, sm, md, lg, xl, 2xl, 3xl
- **Usage**: `AppSpacing.md`, `AppSpacing.radiusLG`

## Environment Variables

### Web Frontend (`.env`)
```bash
VITE_API_URL=http://localhost:8000
```

### Backend (`existing_implementation/backend/.env`)
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///plant_id.db

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Plant Identification APIs
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
PLANTNET_API_KEY=2b10XCJNMzrPYiojVsddjK0n
```

### Flutter Mobile (Firebase - to be configured)
```bash
# FlutterFire CLI will generate firebase_options.dart
# API keys will be configured in Firebase Console
```

## Development Workflow

### Starting Development

**Terminal 1 - Backend:**
```bash
cd existing_implementation/backend
source venv/bin/activate
python manage.py runserver
# Backend running at http://localhost:8000
```

**Terminal 2 - Web Frontend:**
```bash
cd web
npm run dev
# Frontend running at http://localhost:5173
```

**Terminal 3 - Flutter Mobile:**
```bash
cd plant_community_mobile
flutter run -d ios  # or -d android
# Mobile app running on simulator/emulator
```

### Testing the Full Stack

1. **Backend health check:**
   ```bash
   curl http://localhost:8000/api/plant-identification/identify/health/
   ```

2. **Web frontend:**
   - Open http://localhost:5173/identify
   - Upload plant image
   - View AI identification results

3. **Mobile app:**
   - Launch on simulator/emulator
   - Test plant identification workflow
   - Verify Firebase integration (when configured)

## Common Issues & Solutions

### Backend won't start
```bash
cd existing_implementation/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

### CORS errors from frontend
Check `existing_implementation/backend/.env`:
```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

### API returns "Plant.id API key not configured"
Verify `.env` file exists and contains:
```bash
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
```

### Flutter dependency conflicts
```bash
cd plant_community_mobile
flutter pub get
# If issues persist:
flutter clean && flutter pub get
```

### Web frontend can't connect to backend
1. Ensure backend is running on port 8000
2. Check `web/.env` has `VITE_API_URL=http://localhost:8000`
3. Restart Vite dev server after .env changes

## Current Development Status

### ✅ Completed
- Web frontend basic structure (React + Vite + Tailwind)
- Plant identification page with file upload
- Backend API integration (Plant.id + PlantNet)
- Django backend running with dual API services
- Flutter project initialized with design system
- Theme support (light/dark mode) in Flutter

### 🚧 In Progress
- Flutter app features (authentication, plant ID, collection)
- Firebase integration for mobile app
- User authentication system
- Plant collection management

### 📋 Planned
- Firebase authentication (email, Google, Apple)
- Offline-first data sync for mobile
- User plant collection with care tracking
- Forum/community features (read-only in mobile)
- Garden calendar and reminders
- Disease diagnosis with regional intelligence

## Architecture Decisions

### Why Native Mobile + Simple Web?
- **Mobile-first**: Primary platform is native mobile apps (Flutter)
- **Web companion**: Lightweight React web app for desktop access
- **Shared backend**: Single Django backend serves both platforms
- **No PWA complexity**: Avoiding service workers, simpler deployment

### Why Flutter over React Native?
- Better performance for image-heavy plant identification
- Rich UI toolkit for botanical interfaces
- Strong offline-first capabilities
- Firebase integration for real-time features

### Why Dual Plant Identification APIs?
- **Plant.id**: Industry-leading accuracy (95%+), disease detection
- **PlantNet**: Open source data, extensive care instructions, generous limits
- **Fallback**: If one API fails, other provides results
- **Cost-effective**: ~3,500 free identifications/month combined

## Testing Strategy

### Web Frontend
```bash
cd web
npm run lint         # ESLint check
npm run build        # Verify production build works
```

### Backend
```bash
cd existing_implementation/backend
source venv/bin/activate
python manage.py test apps.plant_identification
```

### Flutter Mobile
```bash
cd plant_community_mobile
flutter test                    # Unit tests
flutter analyze                 # Static analysis
flutter build apk --debug       # Android build test
flutter build ios --debug       # iOS build test (Mac only)
```

## Deployment Notes

### Web Frontend
- Build: `npm run build` (outputs to `dist/`)
- Deploy: Static hosting (Vercel, Netlify, Firebase Hosting)
- Environment: Set `VITE_API_URL` to production backend URL

### Backend
- Server: Gunicorn or Daphne (for WebSocket support)
- Database: Migrate from SQLite to PostgreSQL
- Static files: `python manage.py collectstatic`
- API keys: Use environment variables, never commit

### Flutter Mobile
- iOS: Xcode build + TestFlight/App Store
- Android: `flutter build apk --release` + Google Play
- Firebase: Configure production project with FlutterFire CLI
