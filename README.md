# 🌿 Plant ID Community

A multi-platform plant identification system featuring AI-powered plant recognition, mobile-first architecture, and web companion interface.

**🌐 Live site:** [houseplant-md.com](https://houseplant-md.com)

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
- **Web**: http://localhost:5174
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs/ (Swagger UI)
- **Mobile**: Opens in simulator/emulator

## 📱 Architecture

### Multi-Platform Stack
- **Web Frontend**: React 19 + Vite + Tailwind CSS 4
- **Mobile App**: Flutter 3.35+ / Dart 3.9.x + Firebase (primary platform)
- **Backend**: Django 5.2 + Django REST Framework + Wagtail 7.1.2 LTS CMS
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
- ✅ React web interface with plant ID workflow (TypeScript, 669 tests passing)
- ✅ Flutter mobile app (Firebase Auth, Riverpod state management, go_router)
- ✅ Django REST API backend (427+ tests passing)
- ✅ Wagtail CMS Blog with AI content generation
  - Headless CMS with rich StreamField editor
  - Redis caching (80-95% hit rate, <50ms cached responses)
  - AI-powered title/introduction/meta generation (GPT-4o-mini)
  - Access CMS admin at: http://localhost:8000/cms/
- ✅ Community Forum (full CRUD, trust levels, spam detection, moderation)
- ✅ Disease Diagnosis (cards, reminders, CRUD workflow)
- ✅ Garden Calendar (beds, plants, care tasks, harvests, 149 tests)
- ✅ Firebase Authentication (email/password, Google, Apple → Django JWT)

### Planned
- 🚧 Offline-first data sync (mobile)
- 🚧 Plant collection care reminders (mobile)
- 🚧 Garden calendar mobile integration

## 🔧 Development

### Web Frontend
```bash
cd web
npm run dev          # Start dev server (port 5174)
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
CORS_ALLOWED_ORIGINS=http://localhost:5174

# Plant ID APIs
PLANT_ID_API_KEY=your-plant-id-key
PLANTNET_API_KEY=your-plantnet-key
```

### Mobile
- Firebase values are passed via `--dart-define` (no FlutterFire CLI needed).
- See `plant_community_mobile/README.md` for the full list of required keys.

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

### Production (live)
- **Web**: [https://houseplant-md.com](https://houseplant-md.com) — React frontend on Cloudflare Workers (`www.houseplant-md.com` 301-redirects to the apex)
- **Backend / API**: Django on Railway — see [backend/docs/deployment/railway.md](backend/docs/deployment/railway.md)

### Web Frontend
- Build: `npm run build`
- Deploy to: Cloudflare Workers (production: [houseplant-md.com](https://houseplant-md.com))
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
