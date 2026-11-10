# Firestore Security Rules Patterns

---

## Authentication Required for All User Data

All user-specific resources must require authentication:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // User documents — only readable/writable by the owner
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Plant identifications — owner only
    match /identifications/{docId} {
      allow read, write: if request.auth != null
        && request.auth.uid == resource.data.userId;
      allow create: if request.auth != null
        && request.auth.uid == request.resource.data.userId;
    }

    // Public read, authenticated write
    match /plantSpecies/{speciesId} {
      allow read: if true;
      allow write: if request.auth != null && request.auth.token.admin == true;
    }
  }
}
```

---

## Owner-Only Pattern

```javascript
function isOwner(userId) {
  return request.auth != null && request.auth.uid == userId;
}

match /gardens/{gardenId} {
  allow read, write: if isOwner(resource.data.ownerId);
}
```

---

## Rate Limiting Via Rules

Prevent rapid writes using create timestamp checks:

```javascript
match /posts/{postId} {
  allow create: if request.auth != null
    && request.resource.data.userId == request.auth.uid
    // At most one write per second
    && request.resource.data.createdAt > request.time - duration.value(1, 's');
}
```

---

## Never Allow Open Read/Write

Avoid rules that allow unrestricted access:

```javascript
// ❌ Never in production
allow read, write: if true;
```

---

## Testing Rules

Test Firestore rules with the Firebase Emulator Suite before deploying:

```bash
firebase emulators:start --only firestore
firebase emulators:exec "npm test" --only firestore
```

---

## Verified Owner Only, And Test In The Emulator (2026-11-10)

"Signed in" is not a trust level: anyone can create a Firebase login with no
consent and no app account. The shipped rules open one path, to the account's
own verified sign-in, and deny everything else:

```javascript
function isVerifiedOwner(userId) {
  return request.auth != null
      && request.auth.uid == userId
      && request.auth.token.email_verified == true;
}

match /users/{userId}/identified_plants/{plantId} {
  allow read, write: if isVerifiedOwner(userId);
}

match /{document=**} {
  allow read, write: if false;
}
```

- Do not add a rule for a collection no client uses. Five such collections
  were writable by any signed-in account until the 2026-11-10 audit (M15).
- A client must then handle `permission-denied` for an unverified account
  (`collection_screen.dart` says "Verify your email", not "check your
  connection").
- Every rule change gets a case in `scripts/test_firebase_rules_emulator.py`,
  including a guard case proving the emulator can deny at all. Run:
  `firebase emulators:exec --only firestore,storage --project demo-rules
  "python3 scripts/test_firebase_rules_emulator.py"`. CI runs it in
  `firebase-rules-emulator.yml`.
- The examples earlier in this file show rule shapes, not the shipped rules.
