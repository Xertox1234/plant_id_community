# Firebase Configuration Files

**IMPORTANT: Security Notice**

This directory contains Firebase configuration files for the Plant ID Community project.

## Files

- `firestore.rules` - Security rules for Firestore database
- `storage.rules` - Security rules for Firebase Storage
- `firestore.indexes.json` - Composite indexes for Firestore queries
- `firebase-adminsdk-credentials.json` - **DO NOT COMMIT** (add to .gitignore)

## Setup Instructions

1. **Complete Firebase Console Setup** (see `/PLANNING/FIREBASE_SETUP.md`)

2. **Place Service Account Key**:
   ```bash
   # Download from Firebase Console → Project Settings → Service Accounts
   # Save as: firebase-adminsdk-credentials.json
   # This file should NEVER be committed to Git!
   ```

3. **Initialize Firebase CLI**:
   ```bash
   npm install -g firebase-tools
   firebase login
   firebase init
   ```

4. **Deploy Rules and Indexes**:
   ```bash
   # Deploy Firestore rules
   firebase deploy --only firestore:rules
   
   # Deploy Storage rules
   firebase deploy --only storage
   
   # Deploy Firestore indexes
   firebase deploy --only firestore:indexes
   ```

## Security

- ✅ `firestore.rules` - Committed (safe)
- ✅ `storage.rules` - Committed (safe)
- ✅ `firestore.indexes.json` - Committed (safe)
- ❌ `firebase-adminsdk-credentials.json` - **NEVER COMMIT**

## Testing Rules Locally

```bash
# Install Firebase emulators
firebase init emulators

# Start emulators
firebase emulators:start

# Access Emulator UI
open http://localhost:4000
```

## Documentation

For complete setup instructions, see:
- `/PLANNING/FIREBASE_SETUP.md` - Detailed setup guide
- `/PLANNING/DATABASE_SCHEMA.md` - Database architecture
