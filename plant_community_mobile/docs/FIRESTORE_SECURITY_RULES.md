# Firestore Security Rules

**Date**: November 15, 2025
**Version**: 1.0.0
**Purpose**: Secure Firestore data access for plant identification app

---

## Overview

Firestore security rules ensure that users can only access their own data. These rules are enforced server-side by Firebase and cannot be bypassed by malicious clients.

## Security Principles

1. **User Isolation**: Users can only read/write their own data
2. **Authentication Required**: All operations require valid Firebase auth
3. **Least Privilege**: Users have minimal necessary permissions
4. **Server-Side Enforcement**: Rules enforced by Firebase, not client

---

## Security Rules Configuration

### How to Deploy

1. Open [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Navigate to **Firestore Database** → **Rules**
4. Copy the rules below into the editor
5. Click **Publish**

### Firestore Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Helper function: Check if user is authenticated
    function isAuthenticated() {
      return request.auth != null;
    }

    // Helper function: Check if user owns the resource
    function isOwner(userId) {
      return request.auth.uid == userId;
    }

    // Helper function: Validate plant data structure
    function isValidPlant() {
      let data = request.resource.data;
      return data.keys().hasAll([
        'id',
        'name',
        'scientificName',
        'description',
        'care',
        'timestamp'
      ]) &&
      data.id is string &&
      data.name is string &&
      data.scientificName is string &&
      data.description is string &&
      data.care is list &&
      data.timestamp is string &&
      (data.imageUrl == null || data.imageUrl is string);
    }

    // User data collection
    match /users/{userId} {
      // Users can read/write their own user document
      allow read, write: if isAuthenticated() && isOwner(userId);

      // Identified plants subcollection
      match /identified_plants/{plantId} {
        // Users can read their own plants
        allow read: if isAuthenticated() && isOwner(userId);

        // Users can create plants with valid data
        allow create: if isAuthenticated()
                      && isOwner(userId)
                      && isValidPlant();

        // Users can update their own plants with valid data
        allow update: if isAuthenticated()
                      && isOwner(userId)
                      && isValidPlant();

        // Users can delete their own plants
        allow delete: if isAuthenticated() && isOwner(userId);
      }

      // Future collections (garden beds, care tasks, etc.)
      match /garden_beds/{bedId} {
        allow read, write: if isAuthenticated() && isOwner(userId);
      }

      match /care_tasks/{taskId} {
        allow read, write: if isAuthenticated() && isOwner(userId);
      }
    }

    // Deny all other access
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

---

## Rule Breakdown

### 1. User Authentication Check

```javascript
function isAuthenticated() {
  return request.auth != null;
}
```

**Purpose**: Verify user has valid Firebase auth token
**Usage**: Required for ALL operations

### 2. Resource Ownership Check

```javascript
function isOwner(userId) {
  return request.auth.uid == userId;
}
```

**Purpose**: Ensure user can only access their own data
**Usage**: Required for ALL user-scoped operations

### 3. Data Validation

```javascript
function isValidPlant() {
  let data = request.resource.data;
  return data.keys().hasAll([...]) && /* type checks */
}
```

**Purpose**: Prevent malformed data from being written
**Benefits**:
- Schema enforcement
- Prevents injection attacks
- Data integrity

**Validates**:
- All required fields present (`id`, `name`, `scientificName`, etc.)
- Correct data types (strings, lists, etc.)
- Optional fields properly typed (`imageUrl` is string or null)

### 4. Collection-Specific Rules

#### Identified Plants Collection

```javascript
match /identified_plants/{plantId} {
  allow read: if isAuthenticated() && isOwner(userId);
  allow create: if isAuthenticated() && isOwner(userId) && isValidPlant();
  allow update: if isAuthenticated() && isOwner(userId) && isValidPlant();
  allow delete: if isAuthenticated() && isOwner(userId);
}
```

**Read**: User can read their own plants
**Create**: User can create plants with valid data structure
**Update**: User can update their plants (with validation)
**Delete**: User can delete their plants

---

## Testing Security Rules

### Firebase Console Testing

1. Open **Firestore Database** → **Rules** → **Rules Playground**
2. Select operation (read/write)
3. Enter path: `/users/{userId}/identified_plants/{plantId}`
4. Set auth UID to test user ID
5. Add sample data (for writes)
6. Click **Run**

### Flutter App Testing

```dart
// Test 1: Authenticated user can read own data ✅
final plants = await FirebaseFirestore.instance
  .collection('users')
  .doc(currentUserId)
  .collection('identified_plants')
  .get();

// Test 2: Authenticated user CANNOT read other users' data ❌
final otherPlants = await FirebaseFirestore.instance
  .collection('users')
  .doc(otherUserId)  // Different user
  .collection('identified_plants')
  .get();
// Throws: permission-denied

// Test 3: Unauthenticated user CANNOT read data ❌
await FirebaseAuth.instance.signOut();
final plants = await FirebaseFirestore.instance
  .collection('users')
  .doc(someUserId)
  .collection('identified_plants')
  .get();
// Throws: permission-denied

// Test 4: User can write valid data ✅
await FirebaseFirestore.instance
  .collection('users')
  .doc(currentUserId)
  .collection('identified_plants')
  .doc('plant-123')
  .set({
    'id': 'plant-123',
    'name': 'Rose',
    'scientificName': 'Rosa',
    'description': 'Beautiful flower',
    'care': ['Water daily', 'Full sun'],
    'imageUrl': 'https://example.com/image.jpg',
    'timestamp': DateTime.now().toIso8601String(),
  });

// Test 5: User CANNOT write invalid data ❌
await FirebaseFirestore.instance
  .collection('users')
  .doc(currentUserId)
  .collection('identified_plants')
  .doc('plant-456')
  .set({
    'name': 'Rose',  // Missing required fields!
  });
// Throws: permission-denied
```

---

## Common Error Messages

### `permission-denied`

**Cause**: User attempted unauthorized operation

**Common Reasons**:
1. User not authenticated (`await FirebaseAuth.instance.signIn...` first)
2. User trying to access another user's data (check `userId` matches `auth.uid`)
3. Invalid data structure (missing required fields, wrong types)
4. Security rules not deployed yet

**Solution**: Check auth state, verify ownership, validate data structure

### `unavailable`

**Cause**: Network error or Firestore temporarily unavailable

**Solution**: Check internet connection, retry with exponential backoff

---

## Offline Persistence

Firestore automatically caches data locally and syncs when online.

### How It Works

1. **Write Offline**: Data saved to local cache, queued for sync
2. **Read Offline**: Data read from local cache
3. **Sync Online**: Queued writes uploaded, local cache updated

### Configuration

```dart
// Enable offline persistence (done in FirestoreService)
FirebaseFirestore.instance.settings = const Settings(
  persistenceEnabled: true,
  cacheSizeBytes: Settings.CACHE_SIZE_UNLIMITED,
);
```

**Benefits**:
- App works without internet
- Instant reads from cache
- Automatic sync when online
- Conflict resolution handled by Firebase

**Cache Size**:
- `CACHE_SIZE_UNLIMITED`: No limit (recommended for mobile)
- Default: 40MB
- Custom: e.g., `100 * 1024 * 1024` (100MB)

---

## Security Best Practices

### ✅ DO

1. **Always authenticate users** before Firestore operations
2. **Use security rules** to enforce data access (never trust client)
3. **Validate data structure** in security rules
4. **Use user-scoped collections** (`/users/{userId}/...`)
5. **Test security rules** in Firebase Console before deploying
6. **Enable offline persistence** for better UX
7. **Handle permission errors** gracefully in UI

### ❌ DON'T

1. **Don't trust client-side validation** (always enforce server-side)
2. **Don't use global collections** for user data
3. **Don't store sensitive data** in Firestore (use Firebase Auth)
4. **Don't hardcode user IDs** (use `request.auth.uid`)
5. **Don't allow wildcard access** (`allow read, write: if true`)
6. **Don't skip authentication** for convenience
7. **Don't ignore permission errors** (user will be confused)

---

## Monitoring & Debugging

### Firebase Console Monitoring

1. **Firestore Usage**: Database → Usage tab
   - Reads/writes per day
   - Storage usage
   - Bandwidth usage

2. **Security Rule Evaluations**: Database → Rules tab
   - Recent denied requests
   - Rule evaluation metrics

3. **Audit Logs**: Project Settings → Audit Logs (Enterprise only)

### Debug Logging

Enable Firestore debug logging:

```dart
import 'package:firebase_core/firebase_core.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();

  // Enable debug logging (debug builds only)
  if (kDebugMode) {
    FirebaseFirestore.setLoggingEnabled(true);
  }

  runApp(const MyApp());
}
```

**Output**:
```
[FIRESTORE] Listen for Query(users/user-123/identified_plants order by timestamp) online
[FIRESTORE] Using prepopulated cache.
[FIRESTORE] Returning data from cache.
```

---

## Production Checklist

Before deploying to production:

- [ ] Security rules deployed to Firebase Console
- [ ] All helper functions tested (isAuthenticated, isOwner, isValidPlant)
- [ ] Tested authenticated user can read own data
- [ ] Tested authenticated user CANNOT read other users' data
- [ ] Tested unauthenticated user CANNOT read any data
- [ ] Tested valid data can be written
- [ ] Tested invalid data is rejected
- [ ] Offline persistence enabled in Flutter app
- [ ] Error handling implemented for permission-denied
- [ ] Debug logging disabled in production builds
- [ ] Firestore usage monitoring set up

---

## Future Enhancements

### Role-Based Access Control

```javascript
// Example: Moderators can read all plants
function isModerator() {
  return get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'moderator';
}

match /identified_plants/{plantId} {
  allow read: if isAuthenticated() && (isOwner(userId) || isModerator());
}
```

### Public Plant Database

```javascript
// Example: Public collection of verified plants
match /public_plants/{plantId} {
  allow read: if true;  // Anyone can read
  allow write: if isAuthenticated() && isModerator();  // Only moderators can write
}
```

### Rate Limiting

```javascript
// Example: Limit writes to 10 per hour
function rateLimited() {
  return request.time < resource.data.lastWrite + duration.value(1, 'h')
    && resource.data.writeCount >= 10;
}

match /identified_plants/{plantId} {
  allow create: if isAuthenticated() && isOwner(userId) && !rateLimited();
}
```

---

## Support

- **Firebase Documentation**: https://firebase.google.com/docs/firestore/security/get-started
- **Security Rules Reference**: https://firebase.google.com/docs/rules/rules-language
- **Testing Rules**: https://firebase.google.com/docs/rules/unit-tests

---

## Version History

- **v1.0.0** (Nov 15, 2025): Initial security rules implementation
  - User isolation
  - Data validation
  - Offline persistence support
