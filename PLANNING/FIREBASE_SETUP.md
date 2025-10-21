# Firebase Project Setup Guide

**Date**: October 21, 2025  
**Project**: Plant ID Community  
**Purpose**: Step-by-step Firebase project configuration

---

## Table of Contents

1. [Firebase Console Setup](#firebase-console-setup)
2. [Firebase Configuration Files](#firebase-configuration-files)
3. [Security Rules](#security-rules)
4. [Firebase CLI Setup](#firebase-cli-setup)
5. [Environment Configuration](#environment-configuration)
6. [Testing & Validation](#testing--validation)

---

## Firebase Console Setup

### Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **"Add project"**
3. Enter project details:
   - **Project name**: `plant-id-community` (or your preferred name)
   - **Project ID**: Will be auto-generated (e.g., `plant-id-community-abc123`)
   - **Google Analytics**: Enable (recommended for tracking)
   - **Analytics account**: Create new or use existing

4. Click **"Create project"** and wait for completion

---

### Step 2: Enable Authentication

1. In Firebase Console, go to **Build → Authentication**
2. Click **"Get started"**
3. Enable the following sign-in methods:

   **Email/Password**
   - Click "Email/Password"
   - Toggle "Enable"
   - Save

   **Google**
   - Click "Google"
   - Toggle "Enable"
   - Enter support email
   - Save

   **Apple** (Optional for iOS)
   - Click "Apple"
   - Toggle "Enable"
   - Configure Apple Developer settings
   - Save

   **Phone** (Optional)
   - Click "Phone"
   - Toggle "Enable"
   - Save

---

### Step 3: Create Firestore Database

1. Go to **Build → Firestore Database**
2. Click **"Create database"**
3. Choose location:
   - **Production mode** (we'll add rules later)
   - **Region**: Choose closest to your users (e.g., `us-central1`)
4. Click **"Enable"**

5. Create collections (optional - will be created automatically by app):
   ```
   users
   plant_identifications
   user_plants
   disease_diagnoses
   user_preferences
   sync_queue
   ```

---

### Step 4: Set Up Cloud Storage

1. Go to **Build → Storage**
2. Click **"Get started"**
3. Choose security rules:
   - **Production mode** (we'll customize rules)
4. Choose location (same as Firestore)
5. Click **"Done"**

6. Create folder structure:
   ```
   /plant-identifications/
   /disease-diagnoses/
   /user-plants/
   /avatars/
   ```

---

### Step 5: Add Apps to Firebase Project

#### Add Web App (for Django backend)

1. In Firebase Console, click the **Web icon** (</>) 
2. Register app:
   - **App nickname**: `Plant Community Web`
   - **Firebase Hosting**: No (we use Django/Nginx)
3. Copy the Firebase config object (save for later)
4. Click **"Continue to console"**

#### Add Flutter/iOS App

1. Click the **iOS icon**
2. Register app:
   - **iOS bundle ID**: `com.plantcommunity.app` (or your bundle ID)
   - **App nickname**: `Plant Community iOS`
   - **App Store ID**: (leave empty for now)
3. Download `GoogleService-Info.plist`
4. Click **"Next"** through the steps

#### Add Flutter/Android App

1. Click the **Android icon**
2. Register app:
   - **Android package name**: `com.plantcommunity.app` (same as iOS)
   - **App nickname**: `Plant Community Android`
   - **SHA-1**: (optional, for Google Sign-In)
3. Download `google-services.json`
4. Click **"Next"** through the steps

---

### Step 6: Generate Service Account Key (for Django)

1. Go to **Project Settings** (gear icon)
2. Click **"Service accounts"** tab
3. Click **"Generate new private key"**
4. Confirm and download the JSON file
5. **IMPORTANT**: Keep this file secure! Never commit to Git
6. Save as `firebase-adminsdk-credentials.json`

---

## Firebase Configuration Files

### 1. Firebase Config for Flutter

Create file structure:
```
mobile_app/
├── android/
│   └── app/
│       └── google-services.json        # Place downloaded file here
├── ios/
│   └── Runner/
│       └── GoogleService-Info.plist    # Place downloaded file here
└── lib/
    └── config/
        └── firebase_config.dart        # Configuration code
```

**firebase_config.dart**:
```dart
// lib/config/firebase_config.dart
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

class FirebaseConfig {
  static Future<void> initialize() async {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  }
}
```

**Generate firebase_options.dart** using Firebase CLI:
```bash
# Install FlutterFire CLI
dart pub global activate flutterfire_cli

# Run from Flutter project root
flutterfire configure \
  --project=plant-id-community-abc123 \
  --out=lib/config/firebase_options.dart \
  --ios-bundle-id=com.plantcommunity.app \
  --android-package-name=com.plantcommunity.app
```

---

### 2. Firebase Config for Django Backend

**Backend configuration** (`backend/.env`):
```bash
# Firebase Admin SDK
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-adminsdk-credentials.json
FIREBASE_PROJECT_ID=plant-id-community-abc123
FIREBASE_STORAGE_BUCKET=plant-id-community-abc123.appspot.com

# Firebase Web Config (for frontend if needed)
FIREBASE_API_KEY=AIzaSy...
FIREBASE_AUTH_DOMAIN=plant-id-community-abc123.firebaseapp.com
FIREBASE_DATABASE_URL=https://plant-id-community-abc123.firebaseio.com
```

**Django settings** (`plant_community_backend/settings.py`):
```python
import firebase_admin
from firebase_admin import credentials
import os

# Initialize Firebase Admin SDK
FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH')
if FIREBASE_CREDENTIALS_PATH and os.path.exists(FIREBASE_CREDENTIALS_PATH):
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
    })
    FIREBASE_ENABLED = True
else:
    FIREBASE_ENABLED = False
    print("Warning: Firebase credentials not found. Firebase features disabled.")

# Firebase configuration
FIREBASE_CONFIG = {
    'apiKey': os.getenv('FIREBASE_API_KEY'),
    'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN'),
    'projectId': os.getenv('FIREBASE_PROJECT_ID'),
    'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET'),
    'databaseURL': os.getenv('FIREBASE_DATABASE_URL'),
}
```

---

## Security Rules

### 1. Firestore Security Rules

Create file: `firebase/firestore.rules`

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function isOwner(userId) {
      return isAuthenticated() && request.auth.uid == userId;
    }
    
    // Users collection
    match /users/{userId} {
      allow read: if isOwner(userId);
      allow create: if isOwner(userId);
      allow update: if isOwner(userId);
      allow delete: if false; // Users can't delete their own document
    }
    
    // Plant identifications
    match /plant_identifications/{identificationId} {
      allow read: if isOwner(resource.data.user_id);
      allow create: if isAuthenticated() 
                    && request.resource.data.user_id == request.auth.uid;
      allow update: if isOwner(resource.data.user_id);
      allow delete: if isOwner(resource.data.user_id);
    }
    
    // User plants
    match /user_plants/{plantId} {
      allow read: if isOwner(resource.data.user_id) 
                  || resource.data.is_public == true;
      allow create: if isAuthenticated() 
                    && request.resource.data.user_id == request.auth.uid;
      allow update: if isOwner(resource.data.user_id);
      allow delete: if isOwner(resource.data.user_id);
    }
    
    // Disease diagnoses
    match /disease_diagnoses/{diagnosisId} {
      allow read: if isOwner(resource.data.user_id);
      allow create: if isAuthenticated() 
                    && request.resource.data.user_id == request.auth.uid;
      allow update: if isOwner(resource.data.user_id);
      allow delete: if isOwner(resource.data.user_id);
    }
    
    // User preferences
    match /user_preferences/{userId} {
      allow read: if isOwner(userId);
      allow write: if isOwner(userId);
    }
    
    // Sync queue (only backend can write)
    match /sync_queue/{syncId} {
      allow read: if isOwner(resource.data.user_id);
      allow create: if isAuthenticated();
      allow update: if false; // Only cloud functions update
      allow delete: if false; // Only cloud functions delete
    }
    
    // Deny all other paths
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

**Deploy rules**:
```bash
firebase deploy --only firestore:rules
```

---

### 2. Storage Security Rules

Create file: `firebase/storage.rules`

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    
    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function isOwner(userId) {
      return request.auth.uid == userId;
    }
    
    function isImage() {
      return request.resource.contentType.matches('image/.*');
    }
    
    function isValidSize() {
      return request.resource.size < 10 * 1024 * 1024; // 10MB
    }
    
    // Plant identification images
    match /plant-identifications/{userId}/{imageId} {
      allow read: if isAuthenticated();
      allow write: if isOwner(userId) 
                   && isImage() 
                   && isValidSize();
      allow delete: if isOwner(userId);
    }
    
    // Disease diagnosis images
    match /disease-diagnoses/{userId}/{imageId} {
      allow read: if isAuthenticated();
      allow write: if isOwner(userId) 
                   && isImage() 
                   && isValidSize();
      allow delete: if isOwner(userId);
    }
    
    // User plant photos
    match /user-plants/{userId}/{imageId} {
      allow read: if isAuthenticated();
      allow write: if isOwner(userId) 
                   && isImage() 
                   && isValidSize();
      allow delete: if isOwner(userId);
    }
    
    // User avatars
    match /avatars/{userId}/{imageId} {
      allow read: if true; // Public avatars
      allow write: if isOwner(userId) 
                   && isImage() 
                   && isValidSize();
      allow delete: if isOwner(userId);
    }
    
    // Deny all other paths
    match /{allPaths=**} {
      allow read, write: if false;
    }
  }
}
```

**Deploy rules**:
```bash
firebase deploy --only storage
```

---

### 3. Firestore Indexes

Create file: `firebase/firestore.indexes.json`

```json
{
  "indexes": [
    {
      "collectionGroup": "plant_identifications",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "plant_identifications",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "user_plants",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "collection_name", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "user_plants",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "is_alive", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "disease_diagnoses",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "sync_queue",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "ASCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

**Deploy indexes**:
```bash
firebase deploy --only firestore:indexes
```

---

## Firebase CLI Setup

### Install Firebase CLI

```bash
# Install globally
npm install -g firebase-tools

# Verify installation
firebase --version
```

### Login to Firebase

```bash
firebase login
```

### Initialize Firebase in Project

```bash
# Navigate to project root
cd /Users/williamtower/projects/plant_id_community

# Initialize Firebase
firebase init

# Select:
# - Firestore
# - Storage
# - Functions (optional, for Cloud Functions)

# Follow prompts:
# - Use existing project: plant-id-community-abc123
# - Firestore rules: firebase/firestore.rules
# - Firestore indexes: firebase/firestore.indexes.json
# - Storage rules: firebase/storage.rules
```

---

## Environment Configuration

### 1. Django Backend Environment

Create/update `existing_implementation/backend/.env`:

```bash
# ============================================
# FIREBASE CONFIGURATION
# ============================================

# Firebase Admin SDK Credentials
FIREBASE_CREDENTIALS_PATH=../firebase/firebase-adminsdk-credentials.json
FIREBASE_PROJECT_ID=plant-id-community-abc123
FIREBASE_STORAGE_BUCKET=plant-id-community-abc123.appspot.com

# Firebase Web SDK Config (for frontend integration)
FIREBASE_API_KEY=AIzaSy...
FIREBASE_AUTH_DOMAIN=plant-id-community-abc123.firebaseapp.com
FIREBASE_DATABASE_URL=https://plant-id-community-abc123.firebaseio.com
FIREBASE_MESSAGING_SENDER_ID=123456789

# ============================================
# EXISTING CONFIGURATION (keep these)
# ============================================
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
# ... etc
```

### 2. Flutter App Environment

Create `mobile_app/.env`:

```bash
# Firebase Project
FIREBASE_PROJECT_ID=plant-id-community-abc123

# API Endpoints
API_BASE_URL=https://api.plantcommunity.com
API_BASE_URL_DEV=http://localhost:8000

# Plant.id API
PLANT_ID_API_KEY=your-plant-id-api-key

# Feature Flags
ENABLE_ANALYTICS=true
ENABLE_CRASHLYTICS=true
```

---

## Django Firebase Integration

### 1. Install Firebase Admin SDK

```bash
cd existing_implementation/backend
source .venv/bin/activate
pip install firebase-admin
pip freeze > requirements.txt
```

### 2. Create Firebase Authentication Backend

Create file: `backend/apps/users/firebase_backend.py`

```python
"""
Firebase Authentication Backend for Django.
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from firebase_admin import auth
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class FirebaseAuthenticationBackend(BaseBackend):
    """
    Authenticate users using Firebase ID tokens.
    """
    
    def authenticate(self, request, firebase_token=None, **kwargs):
        """
        Authenticate user with Firebase token.
        
        Args:
            request: Django request object
            firebase_token: Firebase ID token from client
            
        Returns:
            User object if authentication successful, None otherwise
        """
        if not firebase_token:
            return None
        
        try:
            # Verify the Firebase token
            decoded_token = auth.verify_id_token(firebase_token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email', '')
            
            # Get or create user
            user, created = User.objects.get_or_create(
                firebase_uid=firebase_uid,
                defaults={
                    'username': email.split('@')[0] if email else firebase_uid[:30],
                    'email': email,
                    'is_active': True,
                }
            )
            
            if created:
                logger.info(f"Created new user from Firebase: {firebase_uid}")
            
            # Update email if changed in Firebase
            if email and user.email != email:
                user.email = email
                user.save(update_fields=['email'])
            
            return user
            
        except auth.InvalidIdTokenError:
            logger.warning("Invalid Firebase ID token")
            return None
        except auth.ExpiredIdTokenError:
            logger.warning("Expired Firebase ID token")
            return None
        except Exception as e:
            logger.error(f"Firebase authentication error: {str(e)}")
            return None
    
    def get_user(self, user_id):
        """
        Get user by ID.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
```

### 3. Create Firebase Token Authentication for DRF

Create file: `backend/apps/users/firebase_authentication.py`

```python
"""
Firebase Token Authentication for Django REST Framework.
"""
from rest_framework import authentication, exceptions
from django.contrib.auth import get_user_model
from .firebase_backend import FirebaseAuthenticationBackend

User = get_user_model()


class FirebaseTokenAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication class for DRF using Firebase tokens.
    """
    
    keyword = 'Bearer'
    backend = FirebaseAuthenticationBackend()
    
    def authenticate(self, request):
        """
        Authenticate request using Firebase token.
        
        Returns:
            (user, token) tuple if successful
            None if no authentication attempted
            
        Raises:
            AuthenticationFailed if authentication fails
        """
        auth_header = authentication.get_authorization_header(request).decode('utf-8')
        
        if not auth_header:
            return None
        
        try:
            # Parse header: "Bearer <token>"
            parts = auth_header.split()
            
            if len(parts) == 0:
                return None
            
            if parts[0].lower() != self.keyword.lower():
                return None
            
            if len(parts) == 1:
                raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
            elif len(parts) > 2:
                raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')
            
            firebase_token = parts[1]
            
        except UnicodeError:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain invalid characters.')
        
        # Authenticate with Firebase backend
        user = self.backend.authenticate(request, firebase_token=firebase_token)
        
        if not user:
            raise exceptions.AuthenticationFailed('Invalid or expired token.')
        
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is disabled.')
        
        return (user, firebase_token)
    
    def authenticate_header(self, request):
        """
        Return authentication header.
        """
        return self.keyword
```

### 4. Update Django Settings

Add to `backend/plant_community_backend/settings.py`:

```python
# Authentication backends
AUTHENTICATION_BACKENDS = [
    'apps.users.firebase_backend.FirebaseAuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',  # Keep for admin
]

# DRF Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.users.firebase_authentication.FirebaseTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Keep for browsable API
    ],
    # ... other settings
}
```

---

## Testing & Validation

### 1. Test Firebase Authentication

Create test script: `backend/test_firebase_auth.py`

```python
"""
Test Firebase authentication integration.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from firebase_admin import auth
from apps.users.models import User

def test_firebase_connection():
    """Test Firebase Admin SDK connection."""
    try:
        # List first 10 users (will be empty initially)
        users = auth.list_users(max_results=10)
        print(f"✅ Firebase connection successful!")
        print(f"   Found {len(users.users)} Firebase users")
        return True
    except Exception as e:
        print(f"❌ Firebase connection failed: {str(e)}")
        return False

def test_create_test_user():
    """Create a test Firebase user."""
    try:
        # Create test user
        test_user = auth.create_user(
            email='test@plantcommunity.com',
            password='TestPassword123!',
            display_name='Test User'
        )
        print(f"✅ Created test Firebase user: {test_user.uid}")
        
        # Clean up
        auth.delete_user(test_user.uid)
        print(f"✅ Cleaned up test user")
        return True
    except Exception as e:
        print(f"❌ Test user creation failed: {str(e)}")
        return False

if __name__ == '__main__':
    print("Testing Firebase Integration...\n")
    test_firebase_connection()
    print()
    test_create_test_user()
```

Run test:
```bash
cd backend
python test_firebase_auth.py
```

---

### 2. Test Firestore Connection

Create test script: `backend/test_firestore.py`

```python
"""
Test Firestore database connection.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from firebase_admin import firestore
from datetime import datetime

def test_firestore_write():
    """Test writing to Firestore."""
    try:
        db = firestore.client()
        
        # Write test document
        doc_ref = db.collection('test').document('test_doc')
        doc_ref.set({
            'message': 'Hello from Django!',
            'timestamp': datetime.now()
        })
        print("✅ Firestore write successful!")
        
        # Read test document
        doc = doc_ref.get()
        if doc.exists:
            print(f"✅ Firestore read successful: {doc.to_dict()}")
        
        # Clean up
        doc_ref.delete()
        print("✅ Cleaned up test document")
        return True
    except Exception as e:
        print(f"❌ Firestore test failed: {str(e)}")
        return False

if __name__ == '__main__':
    print("Testing Firestore Connection...\n")
    test_firestore_write()
```

Run test:
```bash
python test_firestore.py
```

---

### 3. Test Firebase Storage

Create test script: `backend/test_storage.py`

```python
"""
Test Firebase Storage connection.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from firebase_admin import storage
import io

def test_storage_upload():
    """Test uploading to Firebase Storage."""
    try:
        bucket = storage.bucket()
        
        # Create test file
        test_data = b"Test image data"
        blob = bucket.blob('test/test_image.txt')
        
        # Upload
        blob.upload_from_string(test_data, content_type='text/plain')
        print("✅ Storage upload successful!")
        
        # Download
        downloaded_data = blob.download_as_bytes()
        if downloaded_data == test_data:
            print("✅ Storage download successful!")
        
        # Clean up
        blob.delete()
        print("✅ Cleaned up test file")
        return True
    except Exception as e:
        print(f"❌ Storage test failed: {str(e)}")
        return False

if __name__ == '__main__':
    print("Testing Firebase Storage...\n")
    test_storage_upload()
```

Run test:
```bash
python test_storage.py
```

---

## Summary Checklist

### Firebase Console Setup
- [ ] Create Firebase project
- [ ] Enable Authentication (Email/Password, Google)
- [ ] Create Firestore database
- [ ] Set up Cloud Storage
- [ ] Add Web app
- [ ] Add iOS app (download GoogleService-Info.plist)
- [ ] Add Android app (download google-services.json)
- [ ] Generate service account key

### Configuration Files
- [ ] Create `firebase/firestore.rules`
- [ ] Create `firebase/storage.rules`
- [ ] Create `firebase/firestore.indexes.json`
- [ ] Place `firebase-adminsdk-credentials.json` (DO NOT COMMIT!)
- [ ] Update backend `.env` with Firebase config
- [ ] Create mobile app `.env`

### Django Integration
- [ ] Install `firebase-admin` package
- [ ] Add `firebase_uid` field to User model
- [ ] Create and run migration
- [ ] Create `firebase_backend.py`
- [ ] Create `firebase_authentication.py`
- [ ] Update Django settings
- [ ] Test Firebase connection

### Security Rules
- [ ] Deploy Firestore rules
- [ ] Deploy Storage rules
- [ ] Deploy Firestore indexes

### Testing
- [ ] Test Firebase authentication
- [ ] Test Firestore read/write
- [ ] Test Storage upload/download
- [ ] Test API endpoints with Firebase token

---

## Next Steps

After Firebase setup is complete:

1. ✅ Initialize Flutter project with Firebase
2. ✅ Implement authentication flow in Flutter
3. ✅ Create API endpoints for mobile sync
4. ✅ Test end-to-end authentication (Flutter → Firebase → Django)

**Status**: Firebase Setup Guide Complete ✅  
**Next**: Flutter Development Environment Setup 📱
