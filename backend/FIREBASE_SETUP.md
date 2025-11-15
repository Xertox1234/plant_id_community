# Firebase Configuration for Django Backend

This document explains how to configure Firebase Admin SDK credentials for the Django backend to validate Firebase ID tokens from the Flutter mobile app.

## Overview

The Django backend uses the Firebase Admin SDK to:
1. Validate Firebase ID tokens sent by the mobile app
2. Extract user information (UID, email, display name)
3. Create or retrieve Django users based on Firebase credentials
4. Issue Django JWT tokens for authenticated API access

## Prerequisites

- Firebase project created at https://console.firebase.google.com/
- Firebase Authentication enabled (Email/Password, Google, Apple, etc.)
- Python package `firebase-admin==6.6.0` installed (already done)

## Setup Steps

### 1. Download Service Account Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Click the gear icon (⚙️) → **Project settings**
4. Navigate to **Service accounts** tab
5. Click **Generate new private key**
6. Download the JSON file (e.g., `plant-community-firebase-adminsdk.json`)

### 2. Store Credentials Securely

**IMPORTANT: Never commit this file to git!**

**Option A: Environment Variable (Recommended for Production)**
```bash
# Set environment variable pointing to the JSON file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/plant-community-firebase-adminsdk.json"
```

Add to your `.env` file:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/plant-community-firebase-adminsdk.json
```

**Option B: Direct JSON in Environment Variable**
```bash
# For deployment platforms like Heroku, Render, etc.
# Copy the entire JSON content and set as environment variable
export FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
```

### 3. Update Django Settings

The `firebase_auth_views.py` already includes initialization code:

```python
try:
    # Check if Firebase app is already initialized
    firebase_admin.get_app()
except ValueError:
    # Initialize Firebase app if not already done
    # This will use GOOGLE_APPLICATION_CREDENTIALS env variable
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
```

This code automatically looks for `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

### 4. Verify Configuration

Run this command to test Firebase initialization:

```bash
cd backend
source venv/bin/activate
python manage.py shell
```

Then in the Python shell:

```python
import firebase_admin
from firebase_admin import credentials

# Try to initialize (if not already initialized)
try:
    firebase_admin.get_app()
    print("✅ Firebase already initialized")
except ValueError:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized successfully")
```

If you see the success message, Firebase is configured correctly!

### 5. Test Token Exchange Endpoint

With the server running (`python manage.py runserver`), you can test the endpoint:

```bash
# You'll need a valid Firebase ID token from the Flutter app
curl -X POST http://localhost:8000/api/v1/auth/firebase-token-exchange/ \
  -H "Content-Type: application/json" \
  -d '{
    "firebase_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6...",
    "email": "user@example.com",
    "display_name": "John Doe"
  }'
```

Expected response (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "John Doe",
    "is_active": true
  }
}
```

## Security Best Practices

### ✅ DO:
- Store service account JSON file outside the project directory
- Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- Add `*.json` to `.gitignore` to prevent accidental commits
- Use different Firebase projects for dev/staging/production
- Rotate service account keys periodically
- Restrict service account permissions to minimum required

### ❌ DON'T:
- Commit service account JSON to version control
- Share service account credentials via email/Slack
- Use production credentials in development
- Hard-code credentials in source code
- Store credentials in frontend code

## Troubleshooting

### Error: "No credentials found"
**Solution**: Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### Error: "Invalid Firebase token"
**Causes**:
- Token expired (Firebase tokens expire after 1 hour)
- Token from wrong Firebase project
- Token format incorrect

**Solution**: Ensure Flutter app uses the same Firebase project and generates fresh tokens

### Error: "Firebase app already initialized"
**Solution**: This is normal - the app only needs to be initialized once. Ignore this error.

## Development vs Production

### Development
```bash
# .env file
GOOGLE_APPLICATION_CREDENTIALS=/Users/yourname/firebase/plant-community-dev-firebase.json
DEBUG=True
```

### Production (Example: Heroku)
```bash
# Use config vars (not files)
heroku config:set FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

Update `firebase_auth_views.py` to support JSON string:
```python
import os
import json

# Check if JSON is provided as string (production)
json_str = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
if json_str:
    cred = credentials.Certificate(json.loads(json_str))
else:
    # Fall back to file path (development)
    cred = credentials.ApplicationDefault()

firebase_admin.initialize_app(cred)
```

## Next Steps

1. ✅ Download service account key from Firebase Console
2. ✅ Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
3. ✅ Verify Firebase initialization
4. ✅ Test token exchange endpoint
5. ⏳ Create backend tests for authentication
6. ⏳ Test end-to-end authentication flow with Flutter app

## Resources

- [Firebase Admin SDK Setup](https://firebase.google.com/docs/admin/setup)
- [Verify ID Tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [Django REST Framework JWT](https://django-rest-framework-simplejwt.readthedocs.io/)
- [Environment Variables in Django](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/#environment-specific-settings)

## Support

If you encounter issues:
1. Check Firebase Console for project configuration
2. Verify environment variables are set correctly
3. Check Django logs for detailed error messages
4. Ensure `firebase-admin` package is installed: `pip list | grep firebase`
