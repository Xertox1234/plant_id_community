# Firebase Security Deployment Guide

**CRITICAL P0 SECURITY ISSUE RESOLUTION**
**Created:** November 11, 2025
**Issue:** Firebase API keys exposed in git repository (CVSS 7.5)
**Status:** REQUIRES IMMEDIATE ACTION

## Overview

This guide provides step-by-step instructions to secure the Firebase backend after API keys were exposed in the git repository. The primary vulnerability is **missing Firebase Security Rules**, not the API key exposure itself.

**CRITICAL CONTEXT:**
Firebase client API keys are **designed to be embedded in mobile apps** and are not secret. The real security layer is **Firebase Security Rules** which control database and storage access. Without these rules, your database is completely open to the public.

## Immediate Actions Required (Next 2-3 Hours)

### Step 1: Verify Security Rules Are Deployed

**PRIORITY: CRITICAL**

Firebase Security Rules already exist in this repository but must be verified as deployed:

```bash
# Check if rules exist (they do)
ls -la firebase/firestore.rules
ls -la firebase/storage.rules
```

**Deploy Security Rules:**

```bash
# Install Firebase CLI if not already installed
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize Firebase in project (if not already done)
cd /path/to/plant_id_community
firebase init

# Select:
# - Firestore (Database rules)
# - Storage (Storage rules)
# - Use existing project: plant-community-prod

# Deploy security rules
firebase deploy --only firestore:rules
firebase deploy --only storage:rules
```

**Verify Rules Are Active:**

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select `plant-community-prod` project
3. Navigate to **Firestore Database** → **Rules**
4. Verify rules match `firebase/firestore.rules`
5. Navigate to **Storage** → **Rules**
6. Verify rules match `firebase/storage.rules`

### Step 2: Audit Firebase Logs for Unauthorized Access

**Check for suspicious activity in the past 30 days:**

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select `plant-community-prod` project
3. Navigate to **Analytics** → **DebugView**
4. Look for:
   - Unusual read/write patterns
   - Unknown user IDs
   - Excessive API calls
   - Failed authentication attempts
   - Storage uploads from unknown sources

**If suspicious activity detected:**
- Document all findings (timestamps, user IDs, operations)
- Check for data exfiltration (large read operations)
- Review Storage uploads for malicious files
- Consider rotating ALL credentials (see FIREBASE_KEY_ROTATION.md)

### Step 3: Rotate Firebase API Keys (If Audit Shows Compromise)

**ONLY rotate keys if audit reveals suspicious activity.**

See `FIREBASE_KEY_ROTATION.md` for detailed rotation procedures.

**Quick rotation checklist:**
1. Go to Firebase Console → Project Settings
2. Under "Your apps", select Android app
3. Click "Regenerate API Key"
4. Copy new key to `.env` file (see Step 4)
5. Repeat for iOS app
6. Rebuild and redeploy mobile apps

### Step 4: Create .env File with Firebase Credentials

**CRITICAL: This step is required for the app to run after code changes.**

```bash
# Navigate to mobile project
cd plant_community_mobile

# Copy template to .env
cp .env.example .env

# Edit .env with your actual Firebase credentials
# Open in your editor:
nano .env
# or
code .env
```

**Fill in values from Firebase Console:**

```bash
# Get these values from:
# Firebase Console → Project Settings → Your apps → Android/iOS

FIREBASE_ANDROID_API_KEY=AIzaSy...  # From Android app config
FIREBASE_ANDROID_APP_ID=1:...       # From Android app config
FIREBASE_ANDROID_MESSAGING_SENDER_ID=...
FIREBASE_ANDROID_PROJECT_ID=plant-community-prod
FIREBASE_ANDROID_STORAGE_BUCKET=plant-community-prod.firebasestorage.app

FIREBASE_IOS_API_KEY=AIzaSy...      # From iOS app config
FIREBASE_IOS_APP_ID=1:...           # From iOS app config
FIREBASE_IOS_MESSAGING_SENDER_ID=...
FIREBASE_IOS_PROJECT_ID=plant-community-prod
FIREBASE_IOS_STORAGE_BUCKET=plant-community-prod.firebasestorage.app
FIREBASE_IOS_BUNDLE_ID=com.plantcommunity.plantCommunityMobile
```

**VERIFY .env is gitignored:**
```bash
# This should show .env is ignored
git status

# .env should NOT appear in untracked files
# If it does, check .gitignore has:
# .env
# .env.*
# !.env.example
```

### Step 5: Update pubspec.yaml and Install Dependencies

**Install flutter_dotenv package:**

```bash
cd plant_community_mobile

# Get dependencies (flutter_dotenv is already added to pubspec.yaml)
flutter pub get

# Verify installation
flutter pub deps | grep flutter_dotenv
```

### Step 6: Update Assets in pubspec.yaml

**Add .env to assets so it can be loaded:**

Edit `pubspec.yaml`:

```yaml
flutter:
  uses-material-design: true

  # Add this section
  assets:
    - .env
```

### Step 7: Update main.dart to Load .env

**The main.dart file needs to load .env before Firebase initialization:**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // CRITICAL: Load .env before Firebase initialization
  await dotenv.load(fileName: ".env");

  // Initialize Firebase with environment-based config
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  runApp(const MyApp());
}
```

### Step 8: Test the Application

**Verify everything works:**

```bash
cd plant_community_mobile

# Run on iOS simulator
flutter run -d ios

# Run on Android emulator
flutter run -d android

# If you get errors about missing .env:
# 1. Verify .env exists in plant_community_mobile/.env
# 2. Verify pubspec.yaml has assets: [.env]
# 3. Run: flutter clean && flutter pub get
```

**Expected behavior:**
- App starts without Firebase errors
- No "API key not found" exceptions
- Firebase authentication works
- Firestore read/write operations succeed (if authenticated)

## Security Rules Overview

### Firestore Rules (`firebase/firestore.rules`)

**Security model:**
- **Default: Deny all access** (secure by default)
- **Authenticated users only** for most operations
- **User data isolation** (users can only access their own data)
- **Public read for shared content** (user_plants with is_public=true)

**Protected collections:**
- `users` - User profiles (owner read/write only)
- `plant_identifications` - Plant ID results (owner read/write only)
- `user_plants` - User's plant collection (owner read/write, public if is_public=true)
- `disease_diagnoses` - Disease diagnoses (owner read/write only)
- `user_preferences` - User settings (owner read/write only)
- `sync_queue` - Offline sync (authenticated read, cloud functions write)

### Storage Rules (`firebase/storage.rules`)

**Security model:**
- **Default: Deny all access** (secure by default)
- **Authenticated users only** for uploads
- **Image validation** (must be image/* MIME type)
- **Size limits** (10MB max per file)
- **User isolation** (users can only upload to their own folders)

**Protected paths:**
- `plant-identifications/{userId}/` - Plant ID images (owner write, authenticated read)
- `disease-diagnoses/{userId}/` - Disease diagnosis images (owner write, authenticated read)
- `user-plants/{userId}/` - User plant photos (owner write, authenticated read)
- `avatars/{userId}/` - User avatars (owner write, public read)

## Verification Checklist

After completing all steps, verify:

- [ ] Firebase Security Rules deployed (Firestore + Storage)
- [ ] Firebase logs audited (no suspicious activity)
- [ ] `.env` file created with valid credentials
- [ ] `.env` is gitignored (not tracked by git)
- [ ] `firebase_options.dart` is gitignored (not tracked by git)
- [ ] `flutter_dotenv` installed (`flutter pub get`)
- [ ] `.env` added to assets in `pubspec.yaml`
- [ ] `main.dart` loads `.env` before Firebase initialization
- [ ] App runs successfully on iOS simulator
- [ ] App runs successfully on Android emulator
- [ ] Firebase authentication works
- [ ] Firestore read/write operations work (when authenticated)
- [ ] Storage uploads work (when authenticated)
- [ ] No API key errors or exceptions

## Ongoing Security Practices

### 1. Never Commit Sensitive Files

**Always gitignored:**
- `.env` (contains API keys)
- `firebase_options.dart` (now generated from .env)
- Any file with credentials, tokens, or secrets

**Verify before committing:**
```bash
# Check what will be committed
git status

# If you see .env or firebase_options.dart, DO NOT COMMIT
# Verify .gitignore is correct
```

### 2. Rotate Keys After Exposure

**If .env is ever committed to git:**
1. Immediately rotate ALL Firebase API keys
2. Follow `FIREBASE_KEY_ROTATION.md` procedures
3. Update `.env` with new keys
4. Rebuild and redeploy mobile apps
5. Consider using `git-filter-repo` to remove from history

### 3. Monitor Firebase Usage

**Set up alerts in Firebase Console:**
- Unusual read/write patterns
- Excessive API calls (quota exhaustion)
- Failed authentication attempts
- Storage quota approaching limits

**Weekly review:**
- Check Firebase Analytics for anomalies
- Review Authentication logs
- Check Firestore usage metrics
- Monitor Storage usage

### 4. Keep Security Rules Updated

**When adding new features:**
1. Update `firebase/firestore.rules` for new collections
2. Update `firebase/storage.rules` for new storage paths
3. Test rules with Firebase Rules Playground
4. Deploy rules: `firebase deploy --only firestore:rules,storage:rules`

**Test security rules:**
```bash
# Firebase provides a rules simulator
firebase emulators:start --only firestore,storage

# Run security rules tests (if you create them)
firebase emulators:exec --only firestore "npm test"
```

### 5. Separate Development and Production

**Best practice: Use separate Firebase projects**

**Development project:**
- Less restrictive rules (for testing)
- Lower quota limits
- Separate API keys
- Test data only

**Production project:**
- Strict security rules
- Production quota limits
- Separate API keys
- Real user data

**Implementation:**
```bash
# Create .env.development and .env.production
cp .env.example .env.development
cp .env.example .env.production

# Build with different environments
flutter build apk --dart-define-from-file=.env.production
```

## Troubleshooting

### Error: "FIREBASE_ANDROID_API_KEY not found in .env file"

**Cause:** `.env` file missing or not loaded

**Solution:**
1. Verify `.env` exists: `ls -la plant_community_mobile/.env`
2. Verify `pubspec.yaml` has `assets: [.env]`
3. Run: `flutter clean && flutter pub get`
4. Rebuild: `flutter run`

### Error: "Permission denied" in Firestore/Storage

**Cause:** Security rules are blocking the operation

**Solution:**
1. Verify user is authenticated
2. Check Firebase Console → Rules
3. Test rules in Firebase Rules Playground
4. Verify rules match `firebase/*.rules` files
5. Redeploy rules: `firebase deploy --only firestore:rules,storage:rules`

### Error: "Firebase app not initialized"

**Cause:** `dotenv.load()` called after `Firebase.initializeApp()`

**Solution:**
1. Check `main.dart` order of operations:
   ```dart
   await dotenv.load(fileName: ".env");  // MUST come first
   await Firebase.initializeApp(...);     // Then Firebase
   ```

### .env file appears in git status

**Cause:** `.gitignore` not configured correctly

**Solution:**
```bash
# Verify .gitignore has these lines:
# .env
# .env.*
# !.env.example

# If .env is already tracked, remove it:
git rm --cached .env
git commit -m "Remove .env from git tracking"
```

## Resources

- [Firebase Security Rules Documentation](https://firebase.google.com/docs/rules)
- [flutter_dotenv Package](https://pub.dev/packages/flutter_dotenv)
- [Firebase App Check](https://firebase.google.com/docs/app-check) (anti-abuse)
- [OWASP Mobile Security](https://owasp.org/www-project-mobile-security/)
- `FIREBASE_KEY_ROTATION.md` - Key rotation procedures
- Issue #011 - Original security audit findings

## Support

**If you encounter issues:**
1. Check this guide's Troubleshooting section
2. Review Firebase Console logs
3. Test security rules in Firebase Rules Playground
4. Check `flutter doctor` for environment issues
5. Verify all steps completed in Verification Checklist

**Emergency contacts:**
- Firebase Support: https://firebase.google.com/support
- Security incidents: Document and rotate keys immediately
