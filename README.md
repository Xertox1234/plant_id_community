# 🌿 Plant ID Community

A multi-platform plant identification system featuring AI-powered plant recognition, mobile-first architecture, and web companion interface.

## 🚀 Quick Start

### Prerequisites
- **Web**: Node.js 24.x, npm 11.x
- **Mobile**: Flutter 3.35+, Dart 3.9.x
- **Backend**: Python 3.12.x, Django 5.2

### 3-Minute Setup

```bash
# 1. Start the backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# 2. Start the web frontend (new terminal)
cd web
npm install
npm run dev

# 3. Run the mobile app (new terminal)
cd plant_community_mobile
flutter pub get
flutter run
```

Visit:
- **Web**: http://localhost:5173
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs/ (Swagger UI)
- **Mobile**: Opens in simulator/emulator

## 📱 Architecture

### Multi-Platform Stack
- **Web Frontend**: React 19 + Vite + Tailwind CSS 4
- **Mobile App**: Flutter 3.35+ / Dart 3.9.x + Firebase (primary platform)
- **Backend**: Django 5.2 + Django REST Framework + Wagtail 7.0.3 CMS
- **Database**: SQLite (dev), PostgreSQL (production)
- **Cache**: Redis (40% hit rate, <50ms responses)
- **Plant ID**: Dual API (Plant.id + PlantNet)
- **CMS**: Wagtail headless CMS for blog content

### Project Structure
```
plant_id_community/
├── web/                          # React web frontend
│   ├── src/
│   │   ├── pages/               # Route components
│   │   ├── components/          # Reusable UI
│   │   └── services/            # API clients
│   └── package.json
│
├── plant_community_mobile/       # Flutter mobile app
│   ├── lib/
│   │   ├── config/              # App configuration
│   │   ├── core/                # Design system
│   │   ├── features/            # Feature modules
│   │   └── main.dart
│   └── pubspec.yaml
│
├── backend/                      # Django backend services
│   ├── apps/
│   │   ├── plant_identification/
│   │   ├── blog/
│   │   └── users/
│   └── requirements.txt
│
├── firebase/                     # Firebase config
│   ├── firestore.rules
│   └── storage.rules
│
└── PLANNING/                     # Architecture docs
```

## 🎨 Features

### Current
- ✅ AI plant identification (Plant.id + PlantNet)
- ✅ React web interface with plant ID workflow
- ✅ Flutter design system (colors, typography, spacing)
- ✅ Firebase authentication ready
- ✅ Django REST API backend
- ✅ **NEW: Wagtail CMS Blog** (Phase 2 Complete - Oct 24, 2025)
  - Headless CMS with rich StreamField editor
  - Redis caching (35%+ hit rate, <50ms cached responses)
  - Advanced filtering (categories, tags, authors, series)
  - SEO optimization (meta tags, OpenGraph, structured data)
  - Image rendition caching (1-year TTL)
  - Access CMS admin at: http://localhost:8000/cms/

### Planned
- 🚧 User authentication (Firebase Auth)
- 🚧 Plant collection management
- 🚧 Care tracking and reminders
- 🚧 Community forum (read-only in mobile)
- 🚧 Disease diagnosis
- 🚧 Garden calendar
- 🚧 Wagtail blog mobile integration (Phase 3)

## 🔧 Development

### Web Frontend
```bash
cd web
npm run dev          # Start dev server (port 5173)
npm run build        # Production build
npm run lint         # ESLint check
```

### Mobile App
```bash
cd plant_community_mobile
flutter run -d ios              # iOS simulator
flutter run -d android          # Android emulator
flutter test                    # Run tests
flutter analyze                 # Static analysis
```

### Backend
```bash
cd backend
source venv/bin/activate
python manage.py runserver      # Dev server (port 8000)
python manage.py migrate        # Run migrations
python manage.py test           # Run tests
```

## 🔑 Environment Setup

### Web (`web/.env`)
```bash
VITE_API_URL=http://localhost:8000
```

### Backend (`backend/.env`)
```bash
SECRET_KEY=your-secret-key
DEBUG=True
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Plant ID APIs
PLANT_ID_API_KEY=your-plant-id-key
PLANTNET_API_KEY=your-plantnet-key
```

### Mobile
- Firebase configuration via FlutterFire CLI
- See `plant_community_mobile/README.md`

## 📖 Documentation

- **[PLANNING/](PLANNING/)** - Architecture decisions and technical specs
- **[API Documentation](PLANNING/07_API_DOCUMENTATION.md)** - Endpoint and schema reference
- **[Web README](web/README.md)** - React frontend docs
- **[Mobile README](plant_community_mobile/README.md)** - Flutter app docs
- **[Archive](docs/archive/)** - Historical documentation and audit reports

## 🧪 Testing

### Web
```bash
cd web
npm run test         # Run tests (when implemented)
npm run lint         # ESLint check
```

### Mobile
```bash
cd plant_community_mobile
flutter test                    # Unit tests
flutter test --coverage         # With coverage
```

### Backend
```bash
cd backend
python manage.py test apps.plant_identification
```

## 🌐 API Endpoints

### Interactive API Documentation

**NEW:** Interactive OpenAPI 3.0 documentation is now available!

- **Swagger UI**: http://localhost:8000/api/docs/
  - Interactive API explorer with "Try it out" functionality
  - Auto-generated from code (always up-to-date)
  - JWT authentication support built-in

- **ReDoc**: http://localhost:8000/api/redoc/
  - Clean, responsive documentation interface
  - Better for browsing and learning the API

- **OpenAPI Schema**: http://localhost:8000/api/schema/
  - Download the raw OpenAPI 3.0 schema (YAML)
  - Use with Postman, Insomnia, or other API clients

All `/api/v1/*` endpoints are automatically documented. The documentation includes:
- Request/response schemas
- Authentication requirements (JWT tokens)
- Query parameters and filters
- Example requests
- Error responses

### Plant Identification
```bash
# Health check
GET /api/v1/plant-identification/identify/health/

# Identify plant
POST /api/v1/plant-identification/identify/
Content-Type: multipart/form-data
Body: { image: <file> }
```

See [PLANNING/07_API_DOCUMENTATION.md](PLANNING/07_API_DOCUMENTATION.md) for complete API documentation.

## 🤝 Architecture Decisions

### Why Mobile-First?
- Primary platform is native mobile (Flutter)
- Web serves as companion for desktop access
- No PWA complexity (simpler deployment)

### Why Dual Plant ID APIs?
- **Plant.id**: 95%+ accuracy, disease detection (100 IDs/month free)
- **PlantNet**: Care data, generous limits (500/day free)
- **Combined**: ~3,500 free IDs/month for development
- **Fallback**: If one fails, other provides results

### Why Flutter?
- Better performance for image-heavy workflows
- Rich UI toolkit for botanical interfaces
- Strong offline-first capabilities
- Excellent Firebase integration

## 📝 Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and commit
git add .
git commit -m "feat: your feature description"

# Push to remote
git push origin feature/your-feature
```

## 🚀 Deployment

### Web Frontend
- Build: `npm run build`
- Deploy to: Vercel, Netlify, or Firebase Hosting
- Set production `VITE_API_URL`

### Backend
- Server: Gunicorn/Daphne
- Database: PostgreSQL
- Static: `python manage.py collectstatic`
- Use environment variables for secrets

### Mobile
- **iOS**: Xcode → TestFlight → App Store
- **Android**: `flutter build apk --release` → Google Play
- Configure Firebase production project

## 📄 License

Copyright © 2025 Plant Community. All rights reserved.

## 🙏 Acknowledgments

- **Plant.id (Kindwise)** - AI plant identification API
- **PlantNet** - Open-source plant database
- **Firebase** - Backend services
- **Django** - Web framework
- **Flutter** - Mobile framework

---

**For detailed setup and development instructions, see [PLANNING/](PLANNING/) and component README files.**
