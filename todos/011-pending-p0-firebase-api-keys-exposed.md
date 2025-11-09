---
status: pending
priority: p0
issue_id: "011"
tags: [security, critical, firebase, mobile, api-keys]
dependencies: []
---

# Firebase API Keys Exposed in Git Repository

## Problem Statement

Production Firebase API keys are hardcoded and committed to the git repository, creating a critical security vulnerability that allows unauthorized access to Firebase services.

**Location:** `plant_community_mobile/lib/firebase_options.dart:53,61`

**CVSS Score:** 7.5 (HIGH)

## Findings

- Discovered during comprehensive security audit by Security Sentinel agent
- **Exposed Keys:**
  ```dart
  static const FirebaseOptions android = FirebaseOptions(
      apiKey: 'AIzaSyDpRChSGfwYei1xfyjxcCNWjjnVJN2mBEA',  // ⚠️ EXPOSED
      appId: '1:190351417275:android:b0ff3bc42c952da769ae9e',
      projectId: 'plant-community-prod',  // ⚠️ PRODUCTION
  );

  static const FirebaseOptions ios = FirebaseOptions(
      apiKey: 'AIzaSyBKJCbHFQ4fQihCWXbAV1aX50mkSxo4oQM',  // ⚠️ EXPOSED
      appId: '1:190351417275:ios:cde2ebc37ca035de69ae9e',
  );
  ```

- **Exploitation Scenario:**
  1. Attacker clones public repository
  2. Extracts API keys from `firebase_options.dart`
  3. Accesses Firebase Console or API directly
  4. Reads/writes to Firestore database
  5. Uploads malicious files to Storage
  6. Creates fake user accounts
  7. Exhausts quota (financial impact)

- **Current Risk Factors:**
  - ❌ Keys are publicly accessible in git history
  - ❌ No Firebase Security Rules visible (unprotected services)
  - ❌ Production project ID revealed
  - ❌ Keys have full access to Firebase services

## Proposed Solutions

### Step 1: Rotate API Keys (IMMEDIATE - within 2 hours)

**Firebase Console:**
```
1. Go to Firebase Console → Project Settings → General
2. Under "Your apps" → Find Android/iOS app
3. Click "Regenerate API Key" for both platforms
4. Save new keys securely (DO NOT commit)
```

### Step 2: Add Firebase Security Rules (IMMEDIATE - within 2 hours)

**Firestore Rules:**
```javascript
// firestore.rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Default: Deny all access
    match /{document=**} {
      allow read, write: if false;
    }

    // User data: Only authenticated users can read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Plant identifications: Only authenticated users
    match /plant_identifications/{docId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null && request.auth.uid == request.resource.data.userId;
    }
  }
}
```

**Storage Rules:**
```javascript
// storage.rules
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Default: Deny all access
    match /{allPaths=**} {
      allow read, write: if false;
    }

    // User uploads: Only authenticated users
    match /users/{userId}/{allPaths=**} {
      allow read: if request.auth != null;
      allow write: if request.auth != null
                  && request.auth.uid == userId
                  && request.resource.size < 10 * 1024 * 1024;  // 10MB limit
    }
  }
}
```

### Step 3: Use Environment-Based Configuration (within 24 hours)

**Option A: flutter_dotenv (Recommended)**
```bash
# Install package
flutter pub add flutter_dotenv

# Create .env file (gitignored)
# .env
FIREBASE_ANDROID_API_KEY=AIzaSy...
FIREBASE_IOS_API_KEY=AIzaSy...
```

```dart
// lib/main.dart
import 'package:flutter_dotenv/flutter_dotenv.dart';

Future<void> main() async {
  await dotenv.load(fileName: ".env");

  final androidApiKey = dotenv.env['FIREBASE_ANDROID_API_KEY']!;
  final iosApiKey = dotenv.env['FIREBASE_IOS_API_KEY']!;

  // Use keys from environment
  runApp(MyApp());
}
```

**Option B: Build-Time Configuration**
```dart
// lib/firebase_options.dart
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    // Keys injected at build time via --dart-define
    const androidKey = String.fromEnvironment('FIREBASE_ANDROID_KEY');
    const iosKey = String.fromEnvironment('FIREBASE_IOS_KEY');

    if (androidKey.isEmpty || iosKey.isEmpty) {
      throw Exception('Firebase keys not provided');
    }

    // Return config based on platform
  }
}
```

Build command:
```bash
flutter build apk --dart-define=FIREBASE_ANDROID_KEY=AIza...
```

### Step 4: Update .gitignore (within 1 hour)

```
# .gitignore additions
lib/firebase_options.dart
lib/firebase_options_*.dart
.env
.env.*
!.env.example
```

### Step 5: Audit Firebase Logs (within 24 hours)

**Firebase Console → Analytics → DebugView:**
- Check for unauthorized access in past 30 days
- Look for suspicious read/write patterns
- Verify no data exfiltration occurred

## Recommended Action

**IMMEDIATE (next 2-3 hours):**
1. ✅ Rotate Firebase API keys in console
2. ✅ Add Firestore security rules (deny all by default, allow authenticated)
3. ✅ Add Storage security rules (authenticated only, 10MB limit)
4. ✅ Update .gitignore to exclude firebase_options.dart
5. ✅ Audit Firebase logs for suspicious activity

**Within 24 hours:**
6. ✅ Implement flutter_dotenv for environment-based config
7. ✅ Create .env.example with placeholder values
8. ✅ Update CI/CD to inject keys at build time
9. ✅ Document key rotation procedure

**Within 1 week:**
10. ✅ Add monitoring alerts for unusual Firebase activity
11. ✅ Implement Firebase App Check (anti-abuse)
12. ✅ Review all Firebase service usage

## Technical Details

- **Affected Files**:
  - `plant_community_mobile/lib/firebase_options.dart` (remove from git)
  - `plant_community_mobile/.gitignore` (add exclusions)
  - `plant_community_mobile/.env.example` (create template)
  - `firestore.rules` (create security rules)
  - `storage.rules` (create security rules)

- **Related Components**: Flutter mobile app, Firebase backend, CI/CD pipeline

- **Dependencies**:
  - flutter_dotenv package
  - Firebase Console access
  - Git history cleanup (optional but recommended)

- **Performance Impact**: None

## Resources

- Security Sentinel audit report (November 9, 2025)
- CWE-798: Use of Hard-coded Credentials
- CVSS Score: 7.5 (HIGH)
- Firebase Security Rules: https://firebase.google.com/docs/rules
- flutter_dotenv: https://pub.dev/packages/flutter_dotenv
- Firebase App Check: https://firebase.google.com/docs/app-check

## Acceptance Criteria

- [ ] Firebase API keys rotated in console
- [ ] Firestore security rules deployed (deny by default)
- [ ] Storage security rules deployed (authenticated only)
- [ ] firebase_options.dart removed from git tracking
- [ ] .env file created with new keys (gitignored)
- [ ] .env.example created with placeholders
- [ ] CI/CD updated to inject keys at build time
- [ ] Firebase logs audited for past 30 days
- [ ] No unauthorized access detected
- [ ] Monitoring alerts configured
- [ ] Key rotation procedure documented
- [ ] All tests pass with new configuration

## Work Log

### 2025-11-09 - Security Audit Discovery
**By:** Claude Code Review System (Security Sentinel Agent)
**Actions:**
- Discovered during comprehensive codebase audit
- Identified as CRITICAL (P0) security vulnerability
- CVSS 7.5 - Allows unauthorized Firebase access
- Immediate action required

**Learnings:**
- Firebase client API keys are designed to be embedded in apps
- **Security relies on Firebase Security Rules, NOT key secrecy**
- Missing security rules = public database access
- Production and development keys should be separated
- Git history cleanup may be needed (BFG Repo-Cleaner)

## Notes

**CRITICAL CONTEXT:**
Firebase client API keys are **not secret** - they're meant to be included in client apps. The vulnerability is the **lack of Firebase Security Rules**, which means the database/storage are completely open.

**Priority justification:**
- P0 (CRITICAL) because production database is currently unprotected
- Even after key rotation, security rules MUST be implemented
- Without rules, new keys are equally vulnerable

**Security Rules are the actual fix, key rotation is damage control.**

Source: Comprehensive security audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Security Sentinel
