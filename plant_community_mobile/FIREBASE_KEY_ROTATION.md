# Firebase API Key Rotation Procedure

**Created:** November 11, 2025
**Purpose:** Step-by-step guide for rotating Firebase API keys after exposure
**Related:** FIREBASE_SECURITY_DEPLOYMENT.md, Issue #011

## When to Rotate Keys

**Rotate Firebase API keys immediately if:**
- Keys committed to public git repository (DONE - Issue #011)
- Keys posted in public forums, Stack Overflow, etc.
- Unauthorized access detected in Firebase logs
- Employee/contractor with key access leaves team
- Security audit recommends rotation
- Scheduled rotation policy (every 90 days recommended)

**IMPORTANT CONTEXT:**
Firebase client API keys are **not secret** - they're designed to be embedded in apps. However, if you suspect compromise (unauthorized access in logs), rotation is recommended as defense-in-depth.

## Pre-Rotation Checklist

Before rotating keys, ensure:

- [ ] Firebase Security Rules are deployed (see FIREBASE_SECURITY_DEPLOYMENT.md)
- [ ] You have Firebase Console access with Owner/Editor role
- [ ] You have audited Firebase logs for suspicious activity
- [ ] You have documented any unauthorized access
- [ ] You have a rollback plan (keep old keys for 24-48 hours)
- [ ] You can rebuild and redeploy mobile apps
- [ ] You have tested the .env configuration locally

## Step-by-Step Rotation Procedure

### Phase 1: Audit and Document (15 minutes)

**1.1 Review Firebase Analytics**

```
Firebase Console → Project: plant-community-prod → Analytics
```

**Check for suspicious activity:**
- Unusual spike in API calls
- Unknown user IDs or authentication methods
- Failed authentication attempts
- Excessive read/write operations
- Storage uploads from unknown sources

**Document findings:**
```
Date: [DATE]
Suspicious Activity: [YES/NO]
Details:
- Unusual read/write patterns: [YES/NO]
- Unknown user IDs: [YES/NO]
- Excessive API calls: [YES/NO]
- Data exfiltration suspected: [YES/NO]
```

**1.2 Check Firestore Usage**

```
Firebase Console → Firestore Database → Usage
```

**Look for:**
- Unusual document read/write spikes
- Operations outside normal hours
- Operations from unexpected regions

**1.3 Check Storage Usage**

```
Firebase Console → Storage → Usage
```

**Look for:**
- Unexpected file uploads
- Large bandwidth usage
- Unknown file names or paths

**1.4 Check Authentication Logs**

```
Firebase Console → Authentication → Users
```

**Look for:**
- Unknown user accounts
- Mass account creation
- Suspicious email patterns

### Phase 2: Rotate Android API Key (10 minutes)

**2.1 Access Android App Settings**

```
Firebase Console → Project Settings (gear icon) → General
Scroll to "Your apps" section → Find Android app
```

**2.2 Regenerate Android API Key**

**IMPORTANT:** Firebase doesn't provide a UI button for key regeneration. You need to:

**Option A: Create new Android app (Recommended)**
1. In Firebase Console → Project Settings
2. Click "Add app" → Select Android
3. Enter package name: `com.plantcommunity.plantCommunityMobile`
4. Register app and download new `google-services.json`
5. Copy new API key from JSON file

**Option B: Use Firebase CLI**
```bash
# Get current configuration
firebase apps:list ANDROID

# Create new Android app configuration
firebase apps:create ANDROID com.plantcommunity.plantCommunityMobile
```

**Option C: Delete and recreate app (DANGER - only if necessary)**
1. Delete existing Android app from Firebase Console
2. Re-register Android app with same package name
3. Download new `google-services.json`
4. Extract new API key

**2.3 Extract New Android API Key**

From `google-services.json`:
```json
{
  "client": [
    {
      "client_info": {
        "mobilesdk_app_id": "1:...:android:...",
      },
      "api_key": [
        {
          "current_key": "AIzaSy..."  // <-- NEW ANDROID API KEY
        }
      ]
    }
  ]
}
```

**2.4 Update .env File**

```bash
cd plant_community_mobile

# Backup old .env
cp .env .env.backup.$(date +%Y%m%d)

# Edit .env with new Android key
nano .env
```

Update:
```bash
FIREBASE_ANDROID_API_KEY=AIzaSy_NEW_ANDROID_KEY_HERE
FIREBASE_ANDROID_APP_ID=1:...:android:...  # May change if new app
```

### Phase 3: Rotate iOS API Key (10 minutes)

**3.1 Access iOS App Settings**

```
Firebase Console → Project Settings (gear icon) → General
Scroll to "Your apps" section → Find iOS app
```

**3.2 Regenerate iOS API Key**

**Option A: Create new iOS app (Recommended)**
1. In Firebase Console → Project Settings
2. Click "Add app" → Select iOS
3. Enter bundle ID: `com.plantcommunity.plantCommunityMobile`
4. Register app and download new `GoogleService-Info.plist`
5. Copy new API key from plist file

**Option B: Use Firebase CLI**
```bash
# Create new iOS app configuration
firebase apps:create IOS com.plantcommunity.plantCommunityMobile
```

**3.3 Extract New iOS API Key**

From `GoogleService-Info.plist`:
```xml
<key>API_KEY</key>
<string>AIzaSy...</string>  <!-- NEW iOS API KEY -->
<key>GOOGLE_APP_ID</key>
<string>1:...:ios:...</string>
```

**3.4 Update .env File**

```bash
# Edit .env with new iOS key
nano .env
```

Update:
```bash
FIREBASE_IOS_API_KEY=AIzaSy_NEW_IOS_KEY_HERE
FIREBASE_IOS_APP_ID=1:...:ios:...  # May change if new app
```

### Phase 4: Test Locally (15 minutes)

**4.1 Verify .env Configuration**

```bash
cd plant_community_mobile

# View .env (verify new keys are present)
cat .env

# Ensure .env is gitignored
git status  # .env should NOT appear
```

**4.2 Clean and Rebuild**

```bash
# Clean Flutter build cache
flutter clean

# Get dependencies
flutter pub get

# Verify flutter_dotenv is installed
flutter pub deps | grep flutter_dotenv
```

**4.3 Test on iOS Simulator**

```bash
# Start iOS simulator
open -a Simulator

# Run app
flutter run -d ios

# Expected: App starts without Firebase errors
# Test:
# - App launches successfully
# - Firebase connection established
# - Authentication works (if applicable)
# - Firestore read/write works (if authenticated)
```

**4.4 Test on Android Emulator**

```bash
# Start Android emulator
# (or use Android Studio AVD Manager)

# Run app
flutter run -d android

# Expected: App starts without Firebase errors
# Test:
# - App launches successfully
# - Firebase connection established
# - Authentication works (if applicable)
# - Firestore read/write works (if authenticated)
```

**4.5 Verify Firebase Console Logs**

```
Firebase Console → Analytics → DebugView
```

**Look for:**
- App connection events from new keys
- Successful authentication events
- Firestore read/write operations
- No errors or permission denied messages

### Phase 5: Update CI/CD (if applicable) (20 minutes)

**5.1 Identify CI/CD Systems**

**Common systems:**
- GitHub Actions (`.github/workflows/`)
- GitLab CI (`.gitlab-ci.yml`)
- Bitbucket Pipelines (`bitbucket-pipelines.yml`)
- CircleCI (`.circleci/config.yml`)
- Travis CI (`.travis.yml`)

**5.2 Update CI/CD Secrets**

**For GitHub Actions:**
```bash
# Go to: GitHub repo → Settings → Secrets and variables → Actions
# Update secrets:
# - FIREBASE_ANDROID_API_KEY (new key)
# - FIREBASE_IOS_API_KEY (new key)
# - FIREBASE_ANDROID_APP_ID (if changed)
# - FIREBASE_IOS_APP_ID (if changed)
```

**For GitLab CI:**
```bash
# Go to: GitLab repo → Settings → CI/CD → Variables
# Update variables with new keys
```

**5.3 Test CI/CD Pipeline**

```bash
# Trigger a test build
git commit --allow-empty -m "Test CI/CD with rotated Firebase keys"
git push

# Monitor build logs for Firebase errors
```

### Phase 6: Deploy to Production (30 minutes)

**6.1 Build Production Apps**

**Android:**
```bash
cd plant_community_mobile

# Build release APK
flutter build apk --release

# Or build App Bundle (for Google Play)
flutter build appbundle --release

# Output: build/app/outputs/flutter-apk/app-release.apk
# or: build/app/outputs/bundle/release/app-release.aab
```

**iOS:**
```bash
# Build iOS release
flutter build ios --release

# Archive in Xcode:
# 1. Open ios/Runner.xcworkspace in Xcode
# 2. Product → Archive
# 3. Distribute App → App Store Connect
# 4. Upload to TestFlight
```

**6.2 Deploy to App Stores**

**Google Play Store:**
1. Go to [Google Play Console](https://play.google.com/console/)
2. Select app
3. Production → Create new release
4. Upload app-release.aab
5. Review and rollout (staged rollout recommended: 10% → 50% → 100%)

**Apple App Store:**
1. App uploaded to TestFlight via Xcode
2. Go to [App Store Connect](https://appstoreconnect.apple.com/)
3. TestFlight → Test with internal testers (24 hours)
4. If successful, submit for App Store review
5. Phased release recommended (7-day rollout)

**6.3 Monitor Rollout**

**First 24 hours:**
- Check Firebase Analytics for new app versions
- Monitor crash reports (Firebase Crashlytics)
- Check Authentication success rates
- Monitor Firestore/Storage operations
- Watch for increased error rates

**If issues detected:**
1. Pause rollout in app stores
2. Review Firebase Console logs
3. Check for API key errors
4. Verify security rules haven't changed
5. Consider rollback to previous version

### Phase 7: Revoke Old Keys (48 hours after deployment)

**IMPORTANT:** Wait 48 hours to ensure all users have updated apps before revoking old keys.

**7.1 Verify New Key Adoption**

```
Firebase Console → Analytics → App versions
```

**Check:**
- Majority of users on new app version (>95%)
- No spike in errors from old versions
- Authentication working for new versions

**7.2 Delete Old Firebase Apps (Optional)**

**If you created NEW Android/iOS apps in Firebase:**

```
Firebase Console → Project Settings → Your apps
```

**For OLD apps:**
1. Click three dots (⋮) next to old app
2. Select "Delete app"
3. Confirm deletion

**WARNING:** Only delete old apps after verifying:
- New app versions deployed to >95% of users
- No errors from old app versions
- Old .env.backup files saved securely (for emergency rollback)

**7.3 Update Documentation**

```bash
# Update this file with rotation date
echo "Last rotated: $(date)" >> FIREBASE_KEY_ROTATION.md

# Document in CHANGELOG
echo "$(date): Rotated Firebase API keys (Android + iOS)" >> CHANGELOG.md
```

## Rollback Procedure (Emergency)

**If rotation causes production issues:**

**8.1 Restore Old .env**

```bash
cd plant_community_mobile

# List backups
ls -la .env.backup.*

# Restore most recent backup
cp .env.backup.YYYYMMDD .env
```

**8.2 Rebuild and Redeploy**

```bash
# Clean build
flutter clean && flutter pub get

# Build and deploy with old keys
flutter build apk --release
flutter build ios --release

# Emergency deploy to app stores
```

**8.3 Keep Old Firebase Apps Active**

**Do NOT delete old Firebase apps in Console** - they're still active

## Post-Rotation Checklist

After completing rotation, verify:

- [ ] New Android API key generated and tested
- [ ] New iOS API key generated and tested
- [ ] `.env` file updated with new keys
- [ ] `.env.backup` created with old keys (for emergency rollback)
- [ ] App tested on iOS simulator (successful)
- [ ] App tested on Android emulator (successful)
- [ ] Firebase Console shows successful connections with new keys
- [ ] CI/CD secrets updated (if applicable)
- [ ] Production builds created with new keys
- [ ] Apps deployed to TestFlight/Google Play (staged rollout)
- [ ] Monitoring in place for first 48 hours
- [ ] Old Firebase apps deleted after 48 hours (optional)
- [ ] Documentation updated with rotation date
- [ ] Team notified of key rotation

## Automation Recommendations

**For future rotations, consider:**

**1. Scheduled Key Rotation**
```bash
# Create a reminder to rotate keys every 90 days
echo "0 0 1 */3 * /path/to/rotate-firebase-keys.sh" | crontab -
```

**2. Monitoring Script**
```bash
#!/bin/bash
# monitor-firebase-usage.sh
# Check for unusual Firebase activity and alert

FIREBASE_PROJECT="plant-community-prod"

# Check API calls (example)
firebase projects:list | grep $FIREBASE_PROJECT

# Alert if unusual patterns detected
# (implement your own logic)
```

**3. Automated CI/CD Secret Updates**
```bash
# Use tools like:
# - GitHub CLI (gh secret set)
# - GitLab CLI (glab variable set)
# - Vault/AWS Secrets Manager integration
```

## Security Best Practices

**1. Separate Development and Production Keys**

Create separate Firebase projects:
- `plant-community-dev` (development)
- `plant-community-prod` (production)

Use different `.env` files:
```bash
.env.development  # Dev keys
.env.production   # Prod keys

# Build with specific environment
flutter build apk --dart-define-from-file=.env.production
```

**2. Key Rotation Schedule**

- **High security:** Rotate every 30 days
- **Standard:** Rotate every 90 days
- **Minimum:** Rotate yearly or after exposure

**3. Access Control**

- Limit Firebase Console access to essential team members
- Use Google Cloud IAM roles (not Owner for everyone)
- Enable 2FA for all Firebase Console accounts
- Audit Firebase Console access logs quarterly

**4. Monitoring and Alerts**

Set up alerts for:
- Unusual API call spikes (>2x normal)
- Failed authentication attempts (>100/hour)
- New user registrations (>50/hour)
- Storage quota approaching limits (>80%)

## Troubleshooting

### Error: "API key not valid"

**Cause:** New key not activated yet or typo in .env

**Solution:**
1. Wait 5-10 minutes for Firebase to activate new key
2. Verify `.env` has correct key (no spaces, complete key)
3. Verify `pubspec.yaml` has `assets: [.env]`
4. Run: `flutter clean && flutter pub get`

### Error: "Permission denied" after rotation

**Cause:** Security rules blocking access

**Solution:**
1. Verify Firebase Security Rules are deployed
2. Check user is authenticated
3. Test rules in Firebase Rules Playground
4. Redeploy rules: `firebase deploy --only firestore:rules,storage:rules`

### Old app version still works after key rotation

**Expected behavior:** Firebase client API keys are not revoked immediately

**Explanation:**
- Firebase API keys are per-app identifiers, not secrets
- Old keys may remain valid for 24-48 hours
- Security comes from Firebase Security Rules, not key secrecy
- Users must update to new app version to use new keys

**If you need immediate revocation:**
1. Delete old Firebase apps in Console (breaks old app versions)
2. Deploy updated security rules that check app version
3. Force app update via Play Store/App Store

## Resources

- [Firebase Console](https://console.firebase.google.com/)
- [Firebase CLI Documentation](https://firebase.google.com/docs/cli)
- [Google Cloud IAM](https://console.cloud.google.com/iam-admin)
- [Firebase Security Rules](https://firebase.google.com/docs/rules)
- `FIREBASE_SECURITY_DEPLOYMENT.md` - Initial setup guide
- Issue #011 - Security audit findings

## Support

**Emergency key rotation support:**
- Firebase Support: https://firebase.google.com/support
- Google Cloud Support: https://cloud.google.com/support

**Document all incidents:**
- Date/time of exposure
- Scope of compromise (if any)
- Actions taken
- Timeline of rotation
- Lessons learned
