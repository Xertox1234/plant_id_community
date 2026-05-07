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
