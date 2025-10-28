---
status: resolved
priority: p4
issue_id: "030"
tags: [security, api, headers]
dependencies: []
resolved_date: 2025-10-27
---

# Add Security Headers to API Responses

## Problem

API responses lack security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection). Frontend is protected but API endpoints are not.

## Findings

**security-sentinel**:
- No `X-Content-Type-Options: nosniff` on API responses
- No `X-Frame-Options: DENY` on API responses
- No `X-XSS-Protection: 1; mode=block` on API responses
- Frontend (React) properly configured via Vite
- API returns JSON but lacks MIME type enforcement

**best-practices-researcher**:
- OWASP recommends security headers on all responses (HTML + API)
- X-Content-Type-Options prevents MIME confusion attacks
- API responses can still be vulnerable to clickjacking if embedded in iframe

## Proposed Solutions

### Option 1: Django SecurityMiddleware for All Responses (Recommended)
```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',  # Already present
    # ...
]

# These settings apply to ALL responses (HTML + API)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Add if missing
X_FRAME_OPTIONS = 'DENY'  # Already set
```

**Pros**: Single configuration, covers all endpoints
**Cons**: None
**Effort**: 15 minutes (verify settings)
**Risk**: Very low

### Option 2: Custom API Middleware
```python
class APISecurityHeadersMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
        return response
```

**Pros**: API-specific control
**Cons**: Redundant with SecurityMiddleware
**Effort**: 2 hours
**Risk**: Low

## Recommended Action

**Option 1** - Verify Django SecurityMiddleware:
1. Check if `SECURE_CONTENT_TYPE_NOSNIFF = True` is set
2. Verify `X_FRAME_OPTIONS = 'DENY'` is set (already present)
3. Test API response headers: `curl -I https://localhost:8000/api/v1/plant-identification/`
4. Document expected headers in API documentation

**Expected headers on API responses**:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000
Content-Type: application/json
```

## Technical Details

**Django SecurityMiddleware** (already in MIDDLEWARE):
- Automatically adds security headers to ALL responses
- Configuration via settings.py

**Settings to verify**:
```python
# settings.py (lines to check)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Check if present
X_FRAME_OPTIONS = 'DENY'  # Already at line 570
SECURE_HSTS_SECONDS = 31536000  # Already set
```

**Test command**:
```bash
curl -I http://localhost:8000/api/v1/plant-identification/identify/ | grep -E "X-Content-Type|X-Frame"
```

**Expected output**:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

## Resources

- Django SecurityMiddleware: https://docs.djangoproject.com/en/5.2/ref/middleware/#django.middleware.security.SecurityMiddleware
- OWASP Secure Headers: https://owasp.org/www-project-secure-headers/
- Mozilla Observatory: https://observatory.mozilla.org/

## Acceptance Criteria

- [x] `SECURE_CONTENT_TYPE_NOSNIFF = True` in settings.py
- [x] API responses include `X-Content-Type-Options: nosniff`
- [x] API responses include `X-Frame-Options: DENY`
- [x] Test confirms headers present on `/api/v1/` endpoints
- [x] API documentation lists expected security headers

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent
- 2025-10-27: **RESOLVED** - Security headers verified and documented
  - Verified `SECURE_CONTENT_TYPE_NOSNIFF = True` in settings.py (line 890)
  - Verified `X_FRAME_OPTIONS = 'DENY'` in settings.py (line 891)
  - Added `XFrameOptionsMiddleware` to simple_server.py (line 63)
  - Tested headers on API endpoints - all present ✅
  - Created comprehensive documentation: `/backend/docs/security/API_SECURITY_HEADERS.md`
  - Test results confirm:
    - `X-Content-Type-Options: nosniff` ✅
    - `X-Frame-Options: DENY` ✅
    - `Content-Type: application/json` ✅

## Resolution Summary

**Status**: RESOLVED ✅
**Changes Made**:
1. **simple_server.py** - Added `django.middleware.clickjacking.XFrameOptionsMiddleware` to MIDDLEWARE list
2. **Documentation** - Created `/backend/docs/security/API_SECURITY_HEADERS.md` (comprehensive guide)
3. **Testing** - Verified headers present on all API endpoints

**Main Settings (plant_community_backend/settings.py)**:
- Already had `SECURE_CONTENT_TYPE_NOSNIFF = True` (line 890)
- Already had `X_FRAME_OPTIONS = 'DENY'` (line 891)
- Already had `SecurityMiddleware` and `XFrameOptionsMiddleware` in MIDDLEWARE (lines 204, 216)

**Simple Server (simple_server.py)**:
- Already had `SECURE_CONTENT_TYPE_NOSNIFF = True` (line 110)
- Already had `X_FRAME_OPTIONS = 'DENY'` (line 112)
- **ADDED**: `django.middleware.clickjacking.XFrameOptionsMiddleware` to MIDDLEWARE (line 63)

**Test Results**:
```
HTTP/1.1 200 OK
Content-Type: application/json
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
```

All acceptance criteria met. Production ready.

## Notes

**Priority rationale**: P4 (Low) - Defense in depth, but API is JSON (low XSS risk)
**Actual status**: Mostly implemented, required minor fix to simple_server.py
**Action taken**: Verification + minor middleware addition + comprehensive documentation
**False alarm**: Partially - main settings were correct, simple_server needed XFrameOptionsMiddleware
