---
status: ready
priority: p4
issue_id: "030"
tags: [security, api, headers]
dependencies: []
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

- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True` in settings.py
- [ ] API responses include `X-Content-Type-Options: nosniff`
- [ ] API responses include `X-Frame-Options: DENY`
- [ ] Test confirms headers present on `/api/v1/` endpoints
- [ ] API documentation lists expected security headers

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent

## Notes

**Priority rationale**: P4 (Low) - Defense in depth, but API is JSON (low XSS risk)
**Likely status**: Already implemented via SecurityMiddleware, just not verified
**Action**: Verification task more than implementation task
**False alarm probability**: High (SecurityMiddleware likely already adding headers)
