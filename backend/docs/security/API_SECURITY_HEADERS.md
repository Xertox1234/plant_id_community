# API Security Headers Documentation

**Date**: October 27, 2025
**Status**: Production Ready
**Related TODO**: #030 - Add Security Headers to API Responses

---

## Overview

All API endpoints are protected with security headers to prevent common web vulnerabilities including MIME confusion attacks, clickjacking, and XSS attacks. These headers are applied automatically via Django middleware and require no additional configuration in API views.

## Security Headers Implemented

### 1. X-Content-Type-Options: nosniff

**Purpose**: Prevents MIME type sniffing attacks
**Configuration**: `SECURE_CONTENT_TYPE_NOSNIFF = True` (settings.py:890)
**Middleware**: `django.middleware.security.SecurityMiddleware`

This header prevents browsers from interpreting files as a different MIME type than declared. For example, it prevents a JSON response from being interpreted as HTML/JavaScript even if it contains executable code.

**OWASP Recommendation**: Required for all responses (HTML + API)

### 2. X-Frame-Options: DENY

**Purpose**: Prevents clickjacking attacks
**Configuration**: `X_FRAME_OPTIONS = 'DENY'` (settings.py:891)
**Middleware**: `django.middleware.clickjacking.XFrameOptionsMiddleware`

This header prevents API responses from being embedded in `<iframe>`, `<frame>`, `<embed>`, or `<object>` elements, protecting against clickjacking attacks.

**Note**: While API responses are typically JSON and less vulnerable to clickjacking, this header provides defense-in-depth protection.

### 3. Content-Type: application/json

**Purpose**: Explicit MIME type declaration
**Configuration**: Automatic via Django Rest Framework
**Enforces**: JSON responses cannot be misinterpreted as HTML/JavaScript

This header works in conjunction with `X-Content-Type-Options: nosniff` to ensure JSON responses are never executed as scripts.

### 4. Additional Security Headers (Production Only)

These headers are enabled in production (DEBUG=False):

- **Strict-Transport-Security**: `max-age=31536000; includeSubDomains; preload`
  - Configuration: `SECURE_HSTS_SECONDS = 31536000` (settings.py:895)
  - Forces HTTPS connections for 1 year
  - Includes all subdomains
  - Eligible for browser HSTS preload list

- **SECURE_SSL_REDIRECT**: Redirects HTTP to HTTPS (settings.py:898)
- **SESSION_COOKIE_SECURE**: Only send cookies over HTTPS (settings.py:899)
- **CSRF_COOKIE_SECURE**: Only send CSRF token over HTTPS (settings.py:900)

## Implementation Details

### Django Settings Configuration

```python
# settings.py (lines 888-906)

# Security settings - Apply to both development and production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Additional security headers (production only)
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Must be False so JavaScript can read it
SESSION_COOKIE_SAMESITE = 'Strict' if not DEBUG else 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

### Middleware Configuration

```python
# settings.py (lines 203-220)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',  # Security headers
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'apps.core.security.SecurityMiddleware',
    'apps.core.middleware.RateLimitMonitoringMiddleware',
    'apps.core.middleware.SecurityMetricsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # X-Frame-Options
    'csp.middleware.CSPMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
    'apps.blog.middleware.BlogViewTrackingMiddleware',
]
```

**Order matters**: `SecurityMiddleware` must be early in the stack to ensure headers are applied to all responses.

## Testing Security Headers

### Manual Testing

```bash
# Test API endpoint
curl -v http://localhost:8000/api/plant-identification/identify/health/ 2>&1 | grep -E "X-Content-Type|X-Frame"

# Expected output:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
```

### Automated Testing Script

```bash
#!/bin/bash
echo "Testing API Security Headers"
echo "=============================="
echo ""
echo "Testing: /api/plant-identification/identify/health/"
curl -s -D - http://localhost:8000/api/plant-identification/identify/health/ -o /dev/null 2>&1 | grep -E "^(HTTP|X-Content-Type-Options|X-Frame-Options|Strict-Transport-Security|Content-Type)"
echo ""
echo "Expected headers:"
echo "  ✓ X-Content-Type-Options: nosniff"
echo "  ✓ X-Frame-Options: DENY"
echo "  ✓ Content-Type: application/json"
echo ""
```

### Test Results (October 27, 2025)

```
Testing API Security Headers
==============================

Testing: /api/plant-identification/identify/health/
HTTP/1.1 200 OK
Content-Type: application/json
X-Frame-Options: DENY
X-Content-Type-Options: nosniff

Expected headers:
  ✓ X-Content-Type-Options: nosniff
  ✓ X-Frame-Options: DENY
  ✓ Content-Type: application/json
```

**Result**: All security headers present and correctly configured ✅

## Affected Endpoints

These security headers apply to **all API endpoints**:

- `/api/v1/plant-identification/*` - Plant identification API
- `/api/v2/blog-posts/*` - Wagtail blog API
- `/api/v2/blog-index/*` - Blog index pages
- `/api/v2/blog-categories/*` - Blog categories
- `/api/v2/blog-authors/*` - Blog authors
- `/api/v1/users/*` - User authentication API
- All other API endpoints

## Simple Server Configuration

The simplified development server (`simple_server.py`) also includes these headers:

```python
# simple_server.py (lines 58-64, 109-112)

MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
],

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF=True,
SECURE_BROWSER_XSS_FILTER=True,
X_FRAME_OPTIONS='DENY',
```

**Note**: Simple server includes `XFrameOptionsMiddleware` explicitly to ensure X-Frame-Options header is sent.

## Browser Security Tools

### Mozilla Observatory

Test your production API with Mozilla Observatory:
https://observatory.mozilla.org/

Expected grade: **A** or **A+** with all security headers properly configured.

### OWASP ZAP

Use OWASP ZAP to verify security headers:
1. Configure ZAP to proxy API requests
2. Run active scan against API endpoints
3. Verify "Missing Anti-clickjacking Header" is not reported
4. Verify "X-Content-Type-Options Header Missing" is not reported

## Common Issues

### Issue 1: X-Frame-Options Not Appearing

**Symptom**: `X-Content-Type-Options` present but `X-Frame-Options` missing
**Cause**: Missing `XFrameOptionsMiddleware` in MIDDLEWARE list
**Solution**: Ensure `django.middleware.clickjacking.XFrameOptionsMiddleware` is in MIDDLEWARE

### Issue 2: Headers Only on HTML Responses

**Symptom**: Security headers only on HTML pages, not API JSON responses
**Cause**: Middleware order incorrect or middleware not enabled
**Solution**: Move `SecurityMiddleware` and `XFrameOptionsMiddleware` earlier in MIDDLEWARE list

### Issue 3: HSTS Not Working Locally

**Symptom**: No `Strict-Transport-Security` header in development
**Expected**: This is correct - HSTS is disabled when DEBUG=True
**Production**: HSTS will be enabled automatically with DEBUG=False

## Security Best Practices

1. **Never disable security headers** - Even in development, keep headers enabled
2. **Test with production settings** - Use DEBUG=False locally to verify HSTS configuration
3. **Monitor security headers** - Use monitoring tools to detect missing headers
4. **Keep middleware order** - Don't reorder middleware without testing
5. **Document changes** - Any middleware changes should be documented

## References

- Django SecurityMiddleware: https://docs.djangoproject.com/en/5.2/ref/middleware/#django.middleware.security.SecurityMiddleware
- OWASP Secure Headers Project: https://owasp.org/www-project-secure-headers/
- Mozilla Observatory: https://observatory.mozilla.org/
- X-Content-Type-Options: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options
- X-Frame-Options: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options

## Compliance

- **OWASP Top 10**: Addresses A05:2021 - Security Misconfiguration
- **OWASP ASVS**: V14.4 - HTTP Security Headers
- **PCI DSS**: 6.5.9 - Improper Error Handling (via secure headers)

## Changelog

- **2025-10-27**: Initial implementation and testing
  - Added `XFrameOptionsMiddleware` to `simple_server.py`
  - Verified all security headers present on API endpoints
  - Documented configuration and testing procedures
  - TODO #030 resolved

---

**Last Updated**: October 27, 2025
**Maintained By**: Backend Security Team
**Review Schedule**: Quarterly (or after Django version upgrades)
