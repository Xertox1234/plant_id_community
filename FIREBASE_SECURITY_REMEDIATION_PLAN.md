# 🚨 Firebase Security Remediation Plan - Issue #142

**Date**: November 14, 2025
**Status**: CRITICAL - Immediate Action Required
**CVSS Score**: 7.5 (HIGH)
**Priority**: P0

---

## Executive Summary

Firebase API keys were exposed in git commit history (commit `e43a7e1`). While the code has been fixed to use environment variables, the keys remain in public git history and require immediate rotation.

### ✅ What's Already Fixed

1. **Code Remediation Complete** (commit `a81416c`):
   - `firebase_options.dart` now uses `flutter_dotenv` to load keys from `.env` file
   - Comprehensive validation added (throws exceptions if keys missing)
   - Clear security warnings in code comments

2. **Gitignore Configuration** ✅:
   - `.env` file properly excluded from git
   - `.env.*` files excluded (except `.env.example`)
   - `firebase_options.dart` excluded from future commits

3. **Security Rules** ✅:
   - **Firestore rules**: Authentication required, ownership checks, deny-all default
   - **Storage rules**: Authentication required, image validation, size limits (10MB), deny-all default

4. **Documentation** ✅:
   - `.env.example` created with clear instructions
   - Security notes included about Firebase client API keys

---

## 🔴 Critical Issues Requiring Immediate Action

### Issue 1: Exposed API Keys in Git History

**Severity**: CRITICAL
**Location**: Commit `e43a7e1` - Initial commit

**Exposed Credentials**:
```
Android API Key: AIzaSyDpRChSGfwYei1xfyjxcCNWjjnVJN2mBEA
iOS API Key: AIzaSyBKJCbHFQ4fQihCWXbAV1aX50mkSxo4oQM
Project ID: plant-community-prod
Messaging Sender ID: 190351417275
Android App ID: 1:190351417275:android:b0ff3bc42c952da769ae9e
iOS App ID: 1:190351417275:ios:cde2ebc37ca035de69ae9e
Storage Bucket: plant-community-prod.firebasestorage.app
iOS Bundle ID: com.plantcommunity.plantCommunityMobile
```

**Risk**: These keys are permanently in git history and publicly accessible on GitHub.

---

## 🎯 Immediate Action Plan

### Phase 1: Key Rotation (URGENT - Do First)

#### Step 1.1: Rotate Android API Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select project: `plant-community-prod`
3. Go to **Project Settings** (gear icon) → **General**
4. Under "Your apps", find the **Android app**
5. Click **"Regenerate Web API Key"** (or create new Android app)
6. Copy the new `apiKey` value
7. Update your local `.env` file:
   ```env
   FIREBASE_ANDROID_API_KEY=<new_key_here>
   ```

#### Step 1.2: Rotate iOS API Key

1. In Firebase Console, select the **iOS app**
2. Click **"Regenerate Web API Key"** (or create new iOS app)
3. Copy the new `apiKey` value
4. Update your local `.env` file:
   ```env
   FIREBASE_IOS_API_KEY=<new_key_here>
   ```

#### Step 1.3: Delete Old Apps (Recommended)

**Option A - Safer**: Create entirely new Android/iOS apps in Firebase:
1. Click **"Add app"** button
2. Register new Android app with same package name
3. Register new iOS app with same bundle ID
4. Download new `google-services.json` (Android) and `GoogleService-Info.plist` (iOS)
5. Update all app IDs and sender IDs in `.env`
6. **Delete the old apps** to revoke old API keys

**Option B - Simpler**: Just regenerate API keys (less secure, old keys may still work for some time)

---

### Phase 2: Security Rule Verification (After Key Rotation)

#### Step 2.1: Deploy Firestore Rules

```bash
cd /Users/williamtower/projects/plant_id_community
firebase deploy --only firestore:rules
```

**Expected Output**: ✅ Firestore rules deployed successfully

#### Step 2.2: Deploy Storage Rules

```bash
firebase deploy --only storage
```

**Expected Output**: ✅ Storage rules deployed successfully

#### Step 2.3: Verify Rules Are Active

1. Go to Firebase Console → **Firestore Database** → **Rules**
2. Confirm rules match `firebase/firestore.rules`
3. Check "Published" timestamp is recent

4. Go to **Storage** → **Rules**
5. Confirm rules match `firebase/storage.rules`
6. Check "Published" timestamp is recent

---

### Phase 3: Audit Firebase Logs (After Key Rotation)

#### Step 3.1: Check Firestore Activity Logs

1. Go to Firebase Console → **Firestore Database** → **Usage**
2. Review usage graph for past 30 days
3. Look for unusual spikes in:
   - Document reads
   - Document writes
   - Document deletes

**Red Flags**:
- Unusual spikes in read/write activity
- Activity during hours you weren't using the app
- Reads from unexpected geographic locations

#### Step 3.2: Check Storage Activity

1. Go to Firebase Console → **Storage** → **Usage**
2. Review bandwidth and storage over past 30 days
3. Look for unusual file uploads or downloads

**Red Flags**:
- Large unexpected file uploads
- Bandwidth spikes
- Unusual file access patterns

#### Step 3.3: Check Authentication Logs

1. Go to Firebase Console → **Authentication** → **Users**
2. Review user creation dates
3. Check for suspicious accounts

**Red Flags**:
- Multiple accounts created in short time
- Accounts with suspicious email patterns
- Accounts created during odd hours

#### Step 3.4: Review Cloud Functions Logs (if applicable)

1. Go to Firebase Console → **Functions** → **Logs**
2. Look for unusual invocations or errors

---

### Phase 4: Test Application (After All Changes)

#### Step 4.1: Test Android App

```bash
cd plant_community_mobile
flutter run -d android
```

1. Test user registration
2. Test plant identification
3. Test data sync
4. Verify no Firebase errors in console

#### Step 4.2: Test iOS App

```bash
flutter run -d ios
```

1. Test user registration
2. Test plant identification
3. Test data sync
4. Verify no Firebase errors in console

---

## 📋 Acceptance Criteria Checklist

- [ ] **Firebase API keys rotated** (both Android and iOS)
- [ ] **New keys added to .env file** (NOT committed to git)
- [ ] **Firestore security rules deployed** and verified active
- [ ] **Storage security rules deployed** and verified active
- [ ] **Firebase logs audited** for past 30 days
- [ ] **No unauthorized access detected** in audit
- [ ] **Android app tested** with new keys
- [ ] **iOS app tested** with new keys
- [ ] **GitHub Issue #142 updated** with completion status
- [ ] **Optional: Git history cleaned** (see below)

---

## 🔧 Optional: Git History Cleanup

**⚠️ WARNING**: Git history cleanup is complex and may not be fully effective if repository is public.

### Why This Is Optional

Firebase client API keys are **meant to be embedded in apps**. Security comes from **Firebase Security Rules**, not key secrecy. Once rules are properly configured (which they are), the main risk is:

1. **Quota exhaustion**: Malicious users could spam API calls to exhaust Firebase quotas
2. **Cost attacks**: Generate unexpected Firebase costs
3. **App impersonation**: Create fake instances of your app

**Mitigation**: Firebase quotas and billing alerts + proper security rules (already in place)

### If You Want to Clean Git History

**Step 1**: Backup repository:
```bash
git clone https://github.com/Xertox1234/plant_id_community.git plant_id_backup
```

**Step 2**: Use BFG Repo-Cleaner:
```bash
# Install BFG
brew install bfg

# Remove firebase_options.dart from history
bfg --delete-files firebase_options.dart plant_id_community

# Clean up
cd plant_id_community
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (DANGEROUS - coordinate with team)
git push --force --all
```

**Step 3**: Notify all contributors to re-clone repository

**Risks**:
- Breaks all forks
- Requires all developers to re-clone
- May not remove data from GitHub's cache immediately
- Previous commits may still be accessible via direct links

**Recommendation**: Given that:
1. Security rules are properly configured
2. Keys are rotated
3. Firebase client keys are meant to be public anyway

**Skip git history cleanup** and focus on monitoring + rate limiting instead.

---

## 📊 Post-Remediation Monitoring

### Week 1: Daily Monitoring
- Check Firebase usage dashboard daily
- Review authentication logs
- Monitor for unusual activity

### Week 2-4: Weekly Monitoring
- Weekly Firebase usage review
- Check for quota approaching limits
- Review any new security alerts

### Ongoing: Monthly Audits
- Monthly Firebase security audit
- Review and update security rules as needed
- Monitor Firebase SDK updates

---

## 🔗 Resources

- [Firebase Security Rules Documentation](https://firebase.google.com/docs/rules)
- [Firebase API Key Best Practices](https://firebase.google.com/docs/projects/api-keys)
- [Flutter dotenv Package](https://pub.dev/packages/flutter_dotenv)
- [Firebase Console](https://console.firebase.google.com/)
- [GitHub Issue #142](https://github.com/Xertox1234/plant_id_community/issues/142)

---

## 📝 Notes

### Why Firebase Client API Keys Can Be Public

From Firebase documentation:
> "Unlike how API keys are typically used, API keys for Firebase services are not used to control access to backend resources; that can only be done with Firebase Security Rules. Usually, you need to fastidiously guard API keys (for example, by using a vault service or setting the keys as environment variables); however, API keys for Firebase services are ok to include in code or checked-in config files."

**Source**: https://firebase.google.com/docs/projects/api-keys

The **real security** comes from:
1. ✅ **Security Rules** (properly configured)
2. ✅ **Authentication** (Firebase Auth)
3. ✅ **Authorization** (ownership checks in rules)

### Key Takeaways

1. **Code is now secure** - Uses environment variables
2. **Security rules are excellent** - Proper authentication and ownership checks
3. **Main action needed**: Rotate keys as precaution
4. **Git history**: Optional to clean (Firebase keys are meant to be in apps anyway)

---

**Next Steps**: Follow Phase 1 (Key Rotation) immediately, then proceed through phases 2-4.

**Generated**: November 14, 2025
**Author**: Claude Code Security Audit
**Issue**: #142
