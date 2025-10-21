# Firebase Setup - Modern FlutterFire CLI Approach (2025)

**Date**: October 21, 2025  
**Estimated Time**: 15-20 minutes  
**Approach**: Use FlutterFire CLI to automate everything

---

## Why This Approach?

The **FlutterFire CLI** (released 2022, updated 2025) automates the entire Firebase setup process:
- ✅ Creates Firebase project automatically
- ✅ Registers iOS and Android apps
- ✅ Downloads all config files
- ✅ Generates platform-specific code
- ✅ No manual Console clicking required

---

## Prerequisites

- [ ] Google account
- [ ] Flutter project ready (✅ you have this!)
- [ ] Terminal access

---

## Quick Setup (Recommended - 15 minutes)

### Step 1: Install FlutterFire CLI

```bash
# Install FlutterFire CLI globally
dart pub global activate flutterfire_cli

# Verify installation
flutterfire --version

# Add to PATH if needed (add to ~/.zshrc)
export PATH="$PATH":"$HOME/.pub-cache/bin"
source ~/.zshrc
```

### Step 2: Login to Firebase

```bash
# Install Firebase CLI if not installed
npm install -g firebase-tools

# Login to Firebase
firebase login

# This opens browser for Google authentication
# Select your Google account
# Grant permissions
# Return to terminal when complete
```

### Step 3: Configure Firebase with FlutterFire CLI

```bash
# Navigate to Flutter project
cd /Users/williamtower/projects/plant_id_community/plant_community_mobile

# Run FlutterFire configuration wizard
flutterfire configure

# This interactive command will:
# 1. List your existing Firebase projects (or let you create a new one)
# 2. Detect your Flutter app platforms (iOS, Android)
# 3. Register your apps with Firebase
# 4. Download config files automatically
# 5. Generate firebase_options.dart
```

### Step 4: Follow the Interactive Prompts

**When asked to select/create project**:
```
? Select a Firebase project to configure your Flutter application with ›
  <create a new project>
  [existing-project-1]
  [existing-project-2]
```

**Choose**: `<create a new project>`

**Enter project ID**:
```
? Enter a project id for your new Firebase project (e.g. my-cool-project) ›
```

**Enter**: `plant-community-prod`

**Enter project name** (optional):
```
? Enter a name for your new Firebase project ›
```

**Enter**: `Plant Community Production`

**Select platforms**:
```
? Which platforms should your configuration support (use arrow keys & space to select)? ›
✔ android
✔ ios
  macos
  web
```

**Select**: `android` and `ios` (use spacebar)

**iOS bundle ID detection**:
```
? What is the bundle ID for your iOS app? ›
  com.plantcommunity.plant-community-mobile (detected from ios/Runner.xcodeproj)
```

**Press Enter** to accept detected bundle ID

**Android package detection**:
```
? What is the package name for your Android app? ›
  com.plantcommunity.plant_community_mobile (detected from android/app/build.gradle)
```

**Press Enter** to accept detected package name

**Wait for setup** (~2-3 minutes):
```
Firebase configuration file lib/firebase_options.dart generated successfully with the following Firebase apps:

Platform  Firebase App Id
android   1:123456789:android:abc123
ios       1:123456789:ios:def456

Learn more about using this file and next steps from the documentation:
 > https://firebase.google.com/docs/flutter/setup
```

✅ **Done!** Firebase is now configured!

### Step 5: Verify Generated Files

Check that these files were created:

```bash
# Firebase options file (generated)
ls -la lib/firebase_options.dart

# iOS config (downloaded automatically)
ls -la ios/Runner/GoogleService-Info.plist

# Android config (downloaded automatically)
ls -la android/app/google-services.json
```

All files should exist! ✅

---

## Step 6: Enable Firebase Services in Console

Now that the project exists, enable the services you need:

```bash
# Open your Firebase Console
open "https://console.firebase.google.com/project/plant-community-prod/overview"
```

### Enable Authentication

1. In Firebase Console sidebar: **Build** → **Authentication** → **Get started**
2. Click **"Sign-in method"** tab
3. Enable these providers:

**Email/Password**:
- Click "Email/Password" → Toggle ON → Save

**Google**:
- Click "Google" → Toggle ON → Select support email → Save

**Apple** (for iOS):
- Click "Apple" → Toggle ON → Save
- (Apple credentials configured later during iOS app submission)

✅ **Authentication enabled!**

### Enable Firestore Database

1. In Firebase Console sidebar: **Build** → **Firestore Database** → **Create database**
2. **Security rules**: Start in **production mode** (we'll deploy custom rules next)
3. **Location**: Select `us-central1` (or closest to your users)
   - ⚠️ Cannot change this later!
4. Click **Enable**
5. Wait 1-2 minutes

✅ **Firestore created!**

### Enable Firebase Storage

1. In Firebase Console sidebar: **Build** → **Storage** → **Get started**
2. **Security rules**: Start in **production mode**
3. **Location**: Should match Firestore (`us-central1`)
4. Click **Done**

✅ **Storage created!**

---

## Step 7: Deploy Security Rules & Indexes

Now deploy the pre-written security rules from your project:

```bash
# Navigate to project root
cd /Users/williamtower/projects/plant_id_community

# Initialize Firebase (one-time setup)
firebase init

# When prompted:
# ? Which Firebase features? → Select: Firestore, Storage
# ? Please select an option: → Use an existing project
# ? Select a default Firebase project → plant-community-prod
# ? What file should be used for Firestore Rules? → firebase/firestore.rules
# ? What file should be used for Firestore indexes? → firebase/firestore.indexes.json  
# ? What file should be used for Storage Rules? → firebase/storage.rules
# ? File firebase/firestore.rules already exists. Overwrite? → No
# ? File firebase/firestore.indexes.json already exists. Overwrite? → No
# ? File firebase/storage.rules already exists. Overwrite? → No

# Deploy everything
firebase deploy --only firestore:rules,firestore:indexes,storage
```

Expected output:
```
✔  Deploy complete!

Firestore Rules:    deployed
Firestore Indexes:  deployed  
Storage Rules:      deployed
```

✅ **Security rules deployed!**



---

## Step 8: Generate Service Account Key (for Django Backend)

In Firebase Console:

1. Click **⚙️ (Settings)** → **Project settings** → **Service accounts** tab
2. Click **"Generate new private key"**
3. Confirm by clicking **"Generate key"**
4. A JSON file downloads automatically

Secure the file:

```bash
# Create secrets directory
mkdir -p /Users/williamtower/projects/plant_id_community/existing_implementation/backend/secrets

# Move downloaded file (replace xxxxx with actual filename)
mv ~/Downloads/plant-community-prod-*-firebase-adminsdk-*.json \
   /Users/williamtower/projects/plant_id_community/existing_implementation/backend/secrets/firebase-adminsdk.json

# Set secure permissions  
chmod 600 /Users/williamtower/projects/plant_id_community/existing_implementation/backend/secrets/firebase-adminsdk.json
```

✅ **Service account secured!**

---

## Step 9: Initialize Firebase in Flutter App

Update `lib/main.dart` to initialize Firebase:

```dart
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  
  runApp(
    const ProviderScope(
      child: MyApp(),
    ),
  );
}
```

Test the app:

```bash
cd /Users/williamtower/projects/plant_id_community/plant_community_mobile

# Run on iOS simulator
flutter run -d ios

# Or Android emulator
flutter run -d android
```

Look for in console:
```
[Firebase] Initialized successfully
```

✅ **Firebase initialized in app!**

---

## Step 10: Verification Checklist ✅

Run through this checklist:

```bash
# Verify all files exist
ls -la /Users/williamtower/projects/plant_id_community/plant_community_mobile/lib/firebase_options.dart
ls -la /Users/williamtower/projects/plant_id_community/plant_community_mobile/ios/Runner/GoogleService-Info.plist
ls -la /Users/williamtower/projects/plant_id_community/plant_community_mobile/android/app/google-services.json
ls -la /Users/williamtower/projects/plant_id_community/existing_implementation/backend/secrets/firebase-adminsdk.json
```

**All files exist?** ✅ You're done!

**In Firebase Console**, verify:
- [ ] Authentication providers enabled (Email, Google, Apple)
- [ ] Firestore database created
- [ ] Storage bucket created
- [ ] Security rules deployed (check Rules tabs)
- [ ] iOS app registered
- [ ] Android app registered

---

## Troubleshooting

### Issue: "Firebase CLI not found"
```bash
npm install -g firebase-tools
firebase login
```

### Issue: "Permission denied" when deploying rules
```bash
firebase login --reauth
firebase use plant-community-prod-xxxxx
firebase deploy --only firestore:rules,storage
```

### Issue: "FlutterFire configure failed"
```bash
# Make sure you're in the Flutter project directory
cd /Users/williamtower/projects/plant_id_community/plant_community_mobile

# Re-run with explicit project
flutterfire configure --project=plant-community-prod-xxxxx
```

### Issue: "iOS build fails - GoogleService-Info.plist not found"
```bash
# Manually add the file to Xcode:
# 1. Open ios/Runner.xcworkspace in Xcode
# 2. Drag GoogleService-Info.plist into Runner folder
# 3. Check "Copy items if needed"
# 4. Ensure "Runner" target is selected
```

### Issue: "Android build fails - google-services.json not found"
```bash
# Manually copy the file:
cp ~/Downloads/google-services.json \
   plant_community_mobile/android/app/google-services.json
```

---

## Security Reminders

### ⚠️ NEVER Commit These Files to Git:
- `plant-community-firebase-adminsdk.json` (Service account key)
- Any `.env` files with API keys
- `GoogleService-Info.plist` and `google-services.json` are OK to commit (they're public config)

### ✅ Already in .gitignore:
```gitignore
# Backend secrets
backend/secrets/

# Service account keys
*-firebase-adminsdk-*.json
```

### 🔒 Production Security Checklist:
- [x] Firestore security rules deployed (read/write require authentication)
- [x] Storage security rules deployed (uploads require authentication, 10MB limit)
- [x] Service account key has restrictive file permissions (chmod 600)
- [ ] Enable App Check (recommended for production - prevents API abuse)
- [ ] Set up budget alerts in Google Cloud Console
- [ ] Review Firebase security rules regularly

---

## Estimated Costs (Blaze Plan)

### Free Tier (generous for development):
- **Authentication**: 10K phone auths/month (email/password unlimited)
- **Firestore**: 50K reads/day, 20K writes/day, 20K deletes/day
- **Storage**: 5GB stored, 1GB/day download
- **Hosting**: 10GB storage, 360MB/day bandwidth

### Beyond Free Tier:
- **Firestore**: $0.06 per 100K reads, $0.18 per 100K writes
- **Storage**: $0.026/GB/month stored, $0.12/GB downloaded
- **Typical monthly cost** (with moderate usage): $10-50/month

---

## Summary

**Time Spent**: ~45 minutes  
**Status**: ✅ Firebase Console fully configured  
**Next**: Run FlutterFire configure command  

You now have:
- ✅ Firebase project created and configured
- ✅ Authentication providers enabled (Email, Google, Apple)
- ✅ Firestore database with security rules deployed
- ✅ Firebase Storage with security rules deployed
- ✅ iOS and Android apps registered
- ✅ Service account key for Django backend
- ✅ Ready for Flutter app configuration

**Your Firebase Project URL**:  
https://console.firebase.google.com/project/plant-community-prod-xxxxx/overview

(Replace `xxxxx` with your actual project ID)

---

**Created**: October 21, 2025  
**Last Updated**: October 21, 2025  
**Document Owner**: Development Team
