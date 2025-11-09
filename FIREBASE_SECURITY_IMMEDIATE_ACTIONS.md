# 🚨 CRITICAL: Firebase Security - Immediate Actions Required

**Issue:** Firebase API keys and production project ID are committed to git repository.
**Priority:** P0 (CRITICAL)
**Action Required:** Within 2-3 hours

## ⚠️ IMPORTANT CONTEXT

Firebase client API keys are **NOT secret** - they're designed to be embedded in mobile apps. However:
- **Your database/storage are completely UNPROTECTED** without Security Rules
- The keys give anyone access to read/write your Firestore and Storage
- **Security Rules are the real fix**, not hiding the keys

## Immediate Actions (Within 2-3 Hours)

### 1. Add Firebase Security Rules (CRITICAL)

**Firestore Rules** - Deny all by default, allow only authenticated users:

```javascript
// Go to Firebase Console → Firestore Database → Rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Default: Deny all access (CRITICAL)
    match /{document=**} {
      allow read, write: if false;
    }

    // User data: Only authenticated users can read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Plant identifications: Only authenticated users can read/write their own
    match /plant_identifications/{docId} {
      allow read: if request.auth != null;
      allow create: if request.auth != null;
      allow update, delete: if request.auth != null
                            && request.auth.uid == resource.data.userId;
    }

    // Garden data: Only owner can access
    match /gardens/{gardenId} {
      allow read, write: if request.auth != null
                         && request.auth.uid == resource.data.userId;
    }
  }
}
```

**Storage Rules** - Authenticated only with file size limits:

```javascript
// Go to Firebase Console → Storage → Rules
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Default: Deny all access (CRITICAL)
    match /{allPaths=**} {
      allow read, write: if false;
    }

    // User uploads: Only authenticated users, 10MB limit
    match /users/{userId}/{allPaths=**} {
      allow read: if request.auth != null;
      allow write: if request.auth != null
                  && request.auth.uid == userId
                  && request.resource.size < 10 * 1024 * 1024;  // 10MB max
    }

    // Plant images: Authenticated read, owner write
    match /plant_images/{imageId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null;
    }
  }
}
```

### 2. Audit Firebase Activity

**Check for unauthorized access in the past 30 days:**

1. Go to Firebase Console → Analytics → DebugView
2. Review Usage & Billing → Usage
3. Check for:
   - Unusual read/write spikes
   - Unknown user agents
   - Unexpected data patterns
4. If suspicious activity found:
   - Review affected collections
   - Check for data exfiltration
   - Consider data breach notification requirements

### 3. Rotate API Keys (Optional but Recommended)

**Firebase Console:**
```
1. Go to Firebase Console → Project Settings → General
2. Under "Your apps" → Find Android/iOS app
3. Click "Regenerate API Key" for both platforms
4. Save new keys in secure password manager
5. Update local .env files (see below)
```

**Note:** Key rotation is **damage control**, not the fix. Security Rules are mandatory.

## Long-Term Fixes (Within 24-48 Hours)

### 4. Move Keys to Environment Variables

**Install flutter_dotenv:**
```bash
cd plant_community_mobile
flutter pub add flutter_dotenv
```

**Add to `.gitignore`:**
```
# Firebase sensitive files
lib/firebase_options.dart
lib/firebase_options_*.dart
.env
.env.*
!.env.example
```

**Create `.env` (gitignored):**
```bash
# .env (DO NOT COMMIT)
FIREBASE_ANDROID_API_KEY=AIzaSy...
FIREBASE_IOS_API_KEY=AIzaSy...
FIREBASE_PROJECT_ID=plant-community-prod
FIREBASE_STORAGE_BUCKET=plant-community-prod.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=190351417275
```

**Create `.env.example` (committed):**
```bash
# .env.example (TEMPLATE ONLY)
FIREBASE_ANDROID_API_KEY=your-android-api-key-here
FIREBASE_IOS_API_KEY=your-ios-api-key-here
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-bucket.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=your-sender-id
```

**Update `firebase_options.dart`:**
```dart
// lib/firebase_options.dart
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return FirebaseOptions(
          apiKey: dotenv.env['FIREBASE_ANDROID_API_KEY']!,
          appId: '1:190351417275:android:b0ff3bc42c952da769ae9e',
          messagingSenderId: dotenv.env['FIREBASE_MESSAGING_SENDER_ID']!,
          projectId: dotenv.env['FIREBASE_PROJECT_ID']!,
          storageBucket: dotenv.env['FIREBASE_STORAGE_BUCKET']!,
        );
      case TargetPlatform.iOS:
        return FirebaseOptions(
          apiKey: dotenv.env['FIREBASE_IOS_API_KEY']!,
          appId: '1:190351417275:ios:cde2ebc37ca035de69ae9e',
          messagingSenderId: dotenv.env['FIREBASE_MESSAGING_SENDER_ID']!,
          projectId: dotenv.env['FIREBASE_PROJECT_ID']!,
          storageBucket: dotenv.env['FIREBASE_STORAGE_BUCKET']!,
          iosBundleId: 'com.plantcommunity.plantCommunityMobile',
        );
      default:
        throw UnsupportedError('Platform not supported');
    }
  }
}
```

**Update `main.dart`:**
```dart
import 'package:flutter_dotenv/flutter_dotenv.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load environment variables
  await dotenv.load(fileName: ".env");

  // Initialize Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  runApp(const MyApp());
}
```

### 5. Remove Keys from Git History (Optional)

**If you want to clean git history:**
```bash
# WARNING: Rewrites git history - coordinate with team
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch plant_community_mobile/lib/firebase_options.dart" \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all
git push origin --force --tags
```

**Or use BFG Repo-Cleaner (faster):**
```bash
brew install bfg
bfg --delete-files firebase_options.dart
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push origin --force --all
```

## Additional Security Measures

### 6. Enable Firebase App Check (Recommended)

Prevents unauthorized clients from accessing your backend:
```
1. Go to Firebase Console → App Check
2. Enable for Android/iOS apps
3. Configure reCAPTCHA or SafetyNet
4. Enforce App Check for all services
```

### 7. Set Up Monitoring Alerts

**Firebase Console → Alerts:**
- Unusual read/write activity
- Quota approaching limits
- Authentication failures
- Rule violations

## Verification Checklist

- [ ] Firestore security rules deployed (deny by default)
- [ ] Storage security rules deployed (authenticated only)
- [ ] Firebase activity audited for past 30 days
- [ ] No unauthorized access detected
- [ ] API keys rotated (if desired)
- [ ] .env file created with keys (gitignored)
- [ ] .env.example created with placeholders
- [ ] firebase_options.dart updated to read from .env
- [ ] .gitignore excludes firebase_options.dart
- [ ] App tested with new configuration
- [ ] Firebase App Check enabled (optional but recommended)
- [ ] Monitoring alerts configured

## Risk Assessment

**Current Risk (WITHOUT Security Rules):**
- CVSS 7.5 (HIGH)
- Complete database read/write access by anyone
- Storage read/write access by anyone
- Quota exhaustion risk
- Data exfiltration risk

**After Security Rules:**
- CVSS 2.0 (LOW)
- Only authenticated users can access data
- User data isolation enforced
- File size limits prevent abuse
- Normal Firebase security posture

## Resources

- [Firebase Security Rules Documentation](https://firebase.google.com/docs/rules)
- [Firebase App Check](https://firebase.google.com/docs/app-check)
- [flutter_dotenv Package](https://pub.dev/packages/flutter_dotenv)
- [Firebase Security Best Practices](https://firebase.google.com/docs/rules/basics)

## Notes

**Why Firebase client keys can be public:**
- Firebase client SDKs use these keys for API routing, not authentication
- Authentication happens via Firebase Auth (email/password, OAuth, etc.)
- Security is enforced by Security Rules, NOT key secrecy
- Apple/Google require API keys to be in client apps

**The real vulnerability:**
- Missing or permissive Security Rules
- Without rules, anyone can access your database
- Keys in git are not the problem - open database is

---

**Created:** November 9, 2025
**Priority:** P0 (CRITICAL)
**Estimated Time:** 2-3 hours (rules + audit + env setup)
**Related Issue:** #142
