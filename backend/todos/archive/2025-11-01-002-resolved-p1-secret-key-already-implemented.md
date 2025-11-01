---
status: pending
priority: p1
issue_id: "002"
tags: [security, django, critical]
dependencies: []
---

# Fix Insecure SECRET_KEY Default (CRITICAL)

## Problem Statement

Django SECRET_KEY has insecure default value that allows application to run in production:

```python
# settings.py:34
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
```

The default fallback is predictable and includes "insecure" in the name, but still allows the application to run.

**Impact:**
- Session hijacking via forged session cookies
- CSRF token bypass
- Password reset token forgery
- Complete authentication bypass
- Exploitability: HIGH if SECRET_KEY not set in production

## Findings

- Discovered during security audit by security-sentinel agent
- Location: `/backend/plant_community_backend/settings.py:34`
- Current: Uses python-decouple with insecure default
- Risk Level: CRITICAL

## Proposed Solutions

### Option 1: Fail Fast in Production (RECOMMENDED)
- **Pros**: Forces proper configuration, no silent failures
- **Cons**: Application won't start if misconfigured (this is good!)
- **Effort**: Small (15 minutes)
- **Risk**: Low (production deployment checklist will catch this)

**Implementation:**
```python
# settings.py - NO DEFAULT for SECRET_KEY in production
if DEBUG:
    # Development: Allow insecure default for local testing
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-only-key-DO-NOT-USE-IN-PRODUCTION')
else:
    # Production: MUST have SECRET_KEY set - fail loudly if missing
    try:
        SECRET_KEY = config('SECRET_KEY')  # Raises error if not set
    except Exception:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set in production environment. "
            "Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )

    # Validate it's not a default/example value
    if 'django-insecure' in SECRET_KEY or SECRET_KEY == 'your-secret-key-here':
        raise ImproperlyConfigured(
            "Production SECRET_KEY must be changed from default! "
            "Current value contains 'django-insecure' or is placeholder."
        )
```

### Option 2: Enhanced Validation (Alternative)
- **Pros**: More robust validation, detects weak keys
- **Cons**: More complex validation logic
- **Effort**: Medium (30 minutes)
- **Risk**: Low

**Implementation:**
```python
import re
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = config('SECRET_KEY', default=None)

if SECRET_KEY is None:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key'
    else:
        raise ImproperlyConfigured("SECRET_KEY environment variable not set")

# Validate SECRET_KEY strength
if not DEBUG:
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("SECRET_KEY must be at least 50 characters")

    if 'django-insecure' in SECRET_KEY.lower():
        raise ImproperlyConfigured("SECRET_KEY cannot contain 'django-insecure'")

    if SECRET_KEY in ['your-secret-key-here', 'change-me', 'secret']:
        raise ImproperlyConfigured("SECRET_KEY is a common placeholder value")
```

## Recommended Action

**Implement Option 1** - Fail fast in production with clear error message

## Technical Details

- **Affected Files**:
  - `/backend/plant_community_backend/settings.py:34`
  - `.env` (must contain SECRET_KEY for production)
  - `.env.example` (update with generation instructions)

- **Related Components**:
  - Django session management
  - CSRF protection
  - Password reset tokens
  - Signed cookies

- **Database Changes**: No

## Resources

- Security audit report: `/backend/docs/development/SECURITY_AUDIT_REPORT.md`
- Agent report: security-sentinel (Finding #2)
- Django SECRET_KEY docs: https://docs.djangoproject.com/en/5.2/ref/settings/#secret-key

## Acceptance Criteria

- [ ] SECRET_KEY validation added to settings.py
- [ ] Application fails to start if SECRET_KEY not set in production
- [ ] Application fails to start if SECRET_KEY contains 'django-insecure'
- [ ] Development mode still works with default key
- [ ] Clear error message guides developer to generate proper key
- [ ] .env.example updated with SECRET_KEY generation instructions
- [ ] Production deployment checklist includes SECRET_KEY verification

## Work Log

### 2025-10-22 - Code Review Discovery
**By:** security-sentinel agent
**Actions:**
- Discovered insecure default SECRET_KEY during security audit
- Analyzed impact of predictable secret key
- Categorized as CRITICAL priority (A02:2021 - Cryptographic Failures)

**Learnings:**
- Never provide default values for sensitive configuration in production
- Fail fast > silent failures with insecure defaults
- Include helpful error messages with remediation instructions
- Use DEBUG flag to allow convenient local development

## Notes

**Urgency:** CRITICAL - Fix before production deployment
**Deployment:** Requires SECRET_KEY in production environment variables
**Testing:** Test that app fails to start without SECRET_KEY when DEBUG=False

**Example SECRET_KEY generation:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```
