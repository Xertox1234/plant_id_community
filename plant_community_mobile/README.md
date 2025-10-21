# Plant Community Mobile - Flutter App

This is the Flutter mobile application for the Plant Community platform, providing native iOS and Android experiences for plant identification, garden management, and community engagement.

## 📱 Project Structure

```
lib/
├── config/              # App-wide configuration
│   └── theme_provider.dart   # Theme state management
├── core/                # Core utilities and constants
│   ├── constants/
│   │   └── app_spacing.dart  # Spacing scale & dimensions
│   └── theme/
│       ├── app_colors.dart   # Color palette
│       ├── app_typography.dart   # Text styles
│       └── app_theme.dart    # Theme configuration
├── features/            # Feature modules (to be created)
├── models/              # Data models (to be created)
├── services/            # API & Firebase services (to be created)
├── widgets/             # Reusable UI components (to be created)
└── main.dart            # App entry point
```

## 🎨 Design System

The app implements a comprehensive design system extracted from Figma specifications:

### Colors
- **Brand Colors**: Green (10 shades), Emerald (7 shades)
- **Accent Colors**: Blue, Purple, Amber
- **Theme Support**: Full light and dark mode support
- **Color Space**: OKLCH-inspired with Flutter ARGB conversion

### Typography
- **Font Family**: System font stack (SF Pro, Roboto, Segoe UI)
- **Font Sizes**: xs (12px) to 2xl (24px)
- **Font Weights**: Regular (400), Medium (500)
- **Text Styles**: Display, H1-H3, Body, Labels, Buttons, Captions

### Spacing
- **Base Unit**: 4px (0.25rem)
- **Scale**: xs, sm, md, lg, xl, 2xl, 3xl
- **Border Radius**: 4px to 16px, plus full (9999px for pills)
- **Elevation**: 2dp to 16dp for shadows

## 🔧 Dependencies

### Core
- **Flutter SDK**: 3.37.0-0.1.pre (beta)
- **Dart**: 3.10.0

### State Management
- `flutter_riverpod: ^2.6.1` - State management
- `riverpod_annotation: ^2.6.1` - Code generation annotations
- `riverpod_generator: ^2.6.5` (dev) - Code generation
- `build_runner: ^2.5.4` (dev) - Build system

### Firebase
- `firebase_core: ^3.8.1` - Firebase initialization
- `firebase_auth: ^5.3.3` - Authentication
- `cloud_firestore: ^5.5.2` - NoSQL database
- `firebase_storage: ^12.3.6` - File storage

### Navigation
- `go_router: ^15.1.3` - Declarative routing

### Image Handling
- `image_picker: ^1.2.0` - Camera/gallery access
- `cached_network_image: ^3.4.1` - Image caching

### HTTP & Utils
- `dio: ^5.9.0` - HTTP client
- `intl: ^0.20.2` - Internationalization
- `uuid: ^4.5.1` - UUID generation
- `logger: ^2.6.2` - Logging

## 🚀 Getting Started

### Prerequisites
- Flutter 3.37.0 or later
- Xcode 26.0.1+ (for iOS)
- Android SDK 36.1.0+ (for Android)
- Firebase project configured

### Installation

1. **Install dependencies**
   ```bash
   cd plant_community_mobile
   flutter pub get
   ```

2. **Configure Firebase** (when Firebase Console is set up)
   ```bash
   # Install FlutterFire CLI
   dart pub global activate flutterfire_cli
   
   # Configure Firebase for this project
   flutterfire configure --project=plant-community-prod
   ```

3. **Run the app**
   ```bash
   # iOS
   flutter run -d ios
   
   # Android
   flutter run -d android
   
   # Chrome (for testing)
   flutter run -d chrome
   ```

## 🎯 Current Status

### ✅ Completed
- Flutter project created with proper org ID (`com.plantcommunity`)
- Clean architecture folder structure established
- Design system implemented:
  - ✅ Color palette (`app_colors.dart`)
  - ✅ Typography system (`app_typography.dart`)
  - ✅ Spacing constants (`app_spacing.dart`)
  - ✅ Theme configuration (`app_theme.dart`)
- Theme provider with Riverpod (`theme_provider.dart`)
- All dependencies installed
- Light/Dark mode support configured
- Main app entry point updated

### ⏳ Next Steps
1. Configure Firebase with FlutterFire CLI
2. Create Firebase options file
3. Implement authentication UI (login, signup, password reset)
4. Create navigation structure with go_router
5. Implement feature modules:
   - Plant identification with camera
   - User plant collection
   - Forum read-only access
   - Garden calendar
   - Disease diagnosis
6. Set up API services for Django backend
7. Implement offline-first data sync

## 🏗️ Architecture

### State Management
Using **Riverpod** for state management with the following patterns:
- `StateNotifierProvider` for mutable state (e.g., theme mode)
- `FutureProvider` for async data fetching
- `StreamProvider` for real-time Firebase data
- Code generation for boilerplate reduction (to be configured)

### Data Layer
- **Firebase Firestore**: User data, plant collections, preferences
- **Django REST API**: Forum content, plant species database, blog posts
- **Local Storage**: Offline caching, user preferences
- **Firebase Storage**: User-uploaded images

### Navigation
- **go_router** for type-safe, declarative routing
- Deep linking support for sharing plants/posts
- Guards for authentication-required routes

## 📖 Design System Usage

### Using Colors
```dart
import 'package:plant_community_mobile/core/theme/app_colors.dart';

// Primary CTA button
Container(
  color: AppColors.green600,
  child: Text('Action', style: TextStyle(color: AppColors.lightPrimaryForeground)),
)

// Gradient backgrounds
Container(
  decoration: BoxDecoration(
    gradient: LinearGradient(
      colors: AppColors.splashGradientLight,
    ),
  ),
)

// Theme-aware colors
Container(
  color: AppColors.getBackgroundColor(Theme.of(context).brightness),
)
```

### Using Typography
```dart
import 'package:plant_community_mobile/core/theme/app_typography.dart';

Text('Heading', style: AppTypography.h1)
Text('Body text', style: AppTypography.body)
Text('Button', style: AppTypography.button)
```

### Using Spacing
```dart
import 'package:plant_community_mobile/core/constants/app_spacing.dart';

Padding(
  padding: EdgeInsets.all(AppSpacing.md),
  child: Column(
    spacing: AppSpacing.lg,
    children: [...],
  ),
)

Container(
  decoration: BoxDecoration(
    borderRadius: BorderRadius.circular(AppSpacing.radiusLG),
  ),
)
```

### Theme Switching
```dart
import 'package:plant_community_mobile/config/theme_provider.dart';

// In a widget
final themeModeNotifier = ref.read(themeModeProvider.notifier);

// Switch to dark mode
themeModeNotifier.setDark();

// Toggle based on current brightness
themeModeNotifier.toggle(Theme.of(context).brightness);
```

## 🔥 Firebase Integration

### Collections (Firestore)
- `users` - User profiles and preferences
- `plant_identifications` - Identified plants
- `user_plants` - User's plant collection
- `disease_diagnoses` - Disease diagnosis history
- `user_preferences` - App settings
- `sync_queue` - Offline sync queue

### Authentication
- Email/password authentication
- Google Sign-In (to be configured)
- Apple Sign-In (iOS, to be configured)
- Firebase UID mapping with Django backend

### Storage
- User profile images
- Plant identification photos
- Disease diagnosis photos
- Image optimization and thumbnails

## 📱 Platform Support

- ✅ iOS 12.0+
- ✅ Android SDK 21+ (Android 5.0 Lollipop)
- 🚧 Web (limited features)

## 🧪 Testing

```bash
# Run unit tests
flutter test

# Run integration tests
flutter test integration_test

# Generate coverage
flutter test --coverage
```

## 📝 Code Generation

When using Riverpod annotations:

```bash
# Watch for changes and generate code
dart run build_runner watch --delete-conflicting-outputs

# One-time generation
dart run build_runner build --delete-conflicting-outputs
```

## 📄 License

Copyright © 2025 Plant Community. All rights reserved.
