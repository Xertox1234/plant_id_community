# CORS Troubleshooting Pattern

**Date**: October 28, 2025
**Context**: React frontend (port 5174) failing to fetch from Django backend (port 8000)

## Problem Pattern

When the frontend shows CORS errors like:
```
Access to fetch at 'http://localhost:8000/api/v2/blog-posts/' from origin 'http://localhost:5174'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Root Cause

The Django backend server was started **before** CORS settings were active or was running from a previous session with stale configuration.

## Solution Pattern

### 1. Verify CORS Configuration Exists

Check `backend/plant_community_backend/settings.py`:

```python
# Line 143: Ensure corsheaders is in INSTALLED_APPS
THIRD_PARTY_APPS = [
    'corsheaders',  # Must be present
    # ...
]

# Line 211: Ensure middleware is properly ordered
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Must be BEFORE CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ...
]

# Lines 592-614: Verify allowed origins include your frontend port
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:5174',  # React blog dev server
        'http://127.0.0.1:5174',
        # ...
    ]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # NEVER set to True, even in DEBUG
```

### 2. Kill and Restart Backend Server

Django servers can run in the background and persist across terminal sessions:

```bash
# Kill any process using port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Restart Django backend
cd backend
source venv/bin/activate
python manage.py runserver
```

### 3. Verify CORS Headers with curl

Test that the backend is sending proper headers:

```bash
curl -I -X OPTIONS \
  -H "Origin: http://localhost:5174" \
  -H "Access-Control-Request-Method: GET" \
  http://localhost:8000/api/v2/blog-posts/ 2>&1 | grep -i "access-control"
```

Expected output:
```
access-control-allow-origin: http://localhost:5174
access-control-allow-credentials: true
access-control-allow-headers: accept, accept-encoding, authorization, content-type, dnt, origin, user-agent, x-csrftoken, x-requested-with
access-control-allow-methods: DELETE, GET, OPTIONS, PATCH, POST, PUT
access-control-max-age: 86400
```

### 4. Hard Refresh Frontend

Browsers cache CORS preflight responses for up to 24 hours (CORS_MAX_AGE):

```
Mac: Cmd + Shift + R
Windows/Linux: Ctrl + Shift + R
```

Or clear browser cache entirely.

## Common Mistakes

1. **Wrong middleware order**: `CorsMiddleware` must come BEFORE `CommonMiddleware`
2. **Missing port in CORS_ALLOWED_ORIGINS**: Both `localhost` and `127.0.0.1` needed
3. **Stale server process**: Django runserver from previous session still running
4. **Browser cache**: Old CORS preflight responses cached (24h TTL)
5. **Using wrong port**: Frontend on 5174, but CORS only allows 5173

## Prevention

When changing CORS settings:
1. Always restart the Django server
2. Use a fresh browser tab or hard refresh
3. Verify with curl before testing in browser
4. Check Django startup logs for configuration warnings

## Related Files

- `backend/plant_community_backend/settings.py` (lines 143, 211, 592-614)
- `backend/requirements.txt` (django-cors-headers==4.9.0)
- `CLAUDE.md` (CORS section at line 598)

## Testing Checklist

- [ ] `corsheaders` in INSTALLED_APPS
- [ ] `CorsMiddleware` before `CommonMiddleware`
- [ ] Frontend port in CORS_ALLOWED_ORIGINS
- [ ] Backend server restarted
- [ ] curl test shows correct headers
- [ ] Browser hard refresh or cache cleared
- [ ] Frontend successfully fetching data

## See Also

- Django CORS headers docs: https://github.com/adamchainz/django-cors-headers
- CORS specification: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- Preflight request caching: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Max-Age
