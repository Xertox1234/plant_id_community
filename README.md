# 🌿 Plant ID Community

A multi-platform plant identification system featuring AI-powered plant recognition, mobile-first architecture, and web companion interface.

## 🚀 Quick Start

### Prerequisites
- **Web**: Node.js 18+, npm
- **Mobile**: Flutter 3.37+, Dart 3.10+
- **Backend**: Python 3.10+, Django 5.2

### 3-Minute Setup

```bash
# 1. Start the backend
cd existing_implementation/backend
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
- **Mobile**: Opens in simulator/emulator

## 📱 Architecture

### Multi-Platform Stack
- **Web Frontend**: React 19 + Vite + Tailwind CSS 4
- **Mobile App**: Flutter 3.37 + Firebase (primary platform)
- **Backend**: Django 5.2 + Django REST Framework
- **Database**: SQLite (dev), PostgreSQL (production)
- **Plant ID**: Dual API (Plant.id + PlantNet)

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
├── existing_implementation/      # Reference (Django backend)
│   └── backend/                 # Backend services
│       ├── apps/
│       │   ├── plant_identification/
│       │   ├── blog/
│       │   └── users/
│       └── requirements.txt
│
├── firebase/                     # Firebase config
│   ├── firestore.rules
│   └── storage.rules
│
├── PLANNING/                     # Architecture docs
└── CLAUDE.md                     # Development guide
```

## 🎨 Features

### Current
- ✅ AI plant identification (Plant.id + PlantNet)
- ✅ React web interface with plant ID workflow
- ✅ Flutter design system (colors, typography, spacing)
- ✅ Firebase authentication ready
- ✅ Django REST API backend

### Planned
- 🚧 User authentication (Firebase Auth)
- 🚧 Plant collection management
- 🚧 Care tracking and reminders
- 🚧 Community forum (read-only in mobile)
- 🚧 Disease diagnosis
- 🚧 Garden calendar

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
cd existing_implementation/backend
source venv/bin/activate
python manage.py runserver      # Dev server (port 8000)
python manage.py migrate        # Run migrations
python manage.py test           # Run tests
```

## 🔑 Environment Setup

### Web (`.env` in `/web`)
```bash
VITE_API_URL=http://localhost:8000
```

### Backend (`.env` in `/existing_implementation/backend`)
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

- **[CLAUDE.md](CLAUDE.md)** - Complete development guide for Claude Code
- **[QUICK_START.md](QUICK_START.md)** - Fast setup guide
- **[PLANNING/](PLANNING/)** - Architecture decisions and technical specs
- **[Web README](web/README.md)** - React frontend docs
- **[Mobile README](plant_community_mobile/README.md)** - Flutter app docs

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
cd existing_implementation/backend
python manage.py test apps.plant_identification
```

## 🌐 API Endpoints

### Plant Identification
```bash
# Health check
GET /api/plant-identification/identify/health/

# Identify plant
POST /api/plant-identification/identify/
Content-Type: multipart/form-data
Body: { image: <file> }
```

See `CLAUDE.md` for complete API documentation.

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

**For detailed setup and development instructions, see [CLAUDE.md](CLAUDE.md)**
