# security: Fix insecure SECRET_KEY default in Django settings

## Overview

🔴 **CRITICAL** - Django SECRET_KEY has an insecure default fallback that allows the application to run in production with a predictable key, enabling session hijacking, CSRF bypass, and complete authentication bypass.

**Severity:** CRITICAL (CVSS 10.0 - CRITICAL)
**Category:** Security / CWE-798 (Hard-coded Credentials)
**Impact:** Session hijacking, authentication bypass, CSRF token forgery, password reset exploitation
**Timeline:** Fix within 24-48 hours (CISA BOD 19-02)

## Problem Statement / Motivation

**Current State:**
```python
# File: /backend/plant_community_backend/settings.py:34
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
```

The configuration allows Django to start with a default SECRET_KEY even in production. While the default includes "insecure" in the name, it's still predictable and allows the application to run.

**Attack Scenario:**
1. Developer deploys to production without setting `SECRET_KEY` environment variable
2. Django uses default `'django-insecure-change-me-in-production'`
3. Attacker finds default key (publicly documented in codebase)
4. Attacker can:
   - Forge session cookies → Impersonate any user
   - Bypass CSRF protection → Execute unauthorized actions
   - Generate password reset tokens → Take over any account
   - Read signed cookie data → Access sensitive information

**CVSS 3.1 Score: 10.0 (CRITICAL)**
```
Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
- Attack Vector: Network (N)
- Attack Complexity: Low (L) - Default key is public
- Privileges Required: None (N)
- User Interaction: None (N)
- Scope: Changed (C) - Affects all users
- Confidentiality: High (H) - Session data exposed
- Integrity: High (H) - Can modify any data
- Availability: High (H) - Can lock out users
```

**Why This Matters:**
- Django SECRET_KEY is used for cryptographic signing of:
  - Session cookies
  - CSRF tokens
  - Password reset tokens
  - Signed cookies and URL-safe serialization
- Compromise = Complete application takeover

## Proposed Solution

**Option 1: Fail Fast in Production (RECOMMENDED)**

Make SECRET_KEY required in production, with helpful error message:

```python
# File: /backend/plant_community_backend/settings.py

from django.core.exceptions import ImproperlyConfigured

# Environment-aware SECRET_KEY configuration
if DEBUG:
    # Development: Allow insecure default for local testing
    SECRET_KEY = config(
        'SECRET_KEY',
        default='django-insecure-dev-only-DO-NOT-USE-IN-PRODUCTION-abc123xyz'
    )
else:
    # Production: MUST have SECRET_KEY set - fail loudly if missing
    try:
        SECRET_KEY = config('SECRET_KEY')  # Raises Exception if not set
    except Exception:
        raise ImproperlyConfigured(
            "\n"
            "=" * 70 + "\n"
            "CRITICAL: SECRET_KEY environment variable is not set!\n"
            "=" * 70 + "\n"
            "Django requires a unique SECRET_KEY for production security.\n"
            "This key is used for cryptographic signing of:\n"
            "  - Session cookies (authentication)\n"
            "  - CSRF tokens (security)\n"
            "  - Password reset tokens\n"
            "  - Signed cookies\n"
            "\n"
            "Generate a secure key with:\n"
            "  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'\n"
            "\n"
            "Then set in environment:\n"
            "  export SECRET_KEY='your-generated-key-here'\n"
            "\n"
            "Or add to .env file (do NOT commit):\n"
            "  SECRET_KEY=your-generated-key-here\n"
            "=" * 70 + "\n"
        )

    # Validate it's not a default/example value
    INSECURE_PATTERNS = [
        'django-insecure',
        'change-me',
        'your-secret-key-here',
        'secret',
        'password',
        'abc123',
    ]

    for pattern in INSECURE_PATTERNS:
        if pattern in SECRET_KEY.lower():
            raise ImproperlyConfigured(
                f"Production SECRET_KEY contains insecure pattern: '{pattern}'\n"
                f"Generate a new key with:\n"
                f"  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
            )

    # Validate minimum length
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            f"Production SECRET_KEY is too short ({len(SECRET_KEY)} characters).\n"
            f"Django recommends at least 50 characters for security.\n"
            f"Generate a new key with:\n"
            f"  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )
```

**Option 2: Environment Variable with Validation**

```python
# Simpler version with basic validation
SECRET_KEY = config('SECRET_KEY', default=None)

if SECRET_KEY is None:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key'
    else:
        raise ImproperlyConfigured("SECRET_KEY environment variable not set in production")

# Validate length and patterns
if not DEBUG:
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(f"SECRET_KEY too short: {len(SECRET_KEY)} chars (need 50+)")
    if 'django-insecure' in SECRET_KEY.lower():
        raise ImproperlyConfigured("SECRET_KEY cannot contain 'django-insecure' in production")
```

## Technical Considerations

**Security:**
- Failing fast is better than silent failures with insecure defaults
- Error message guides developer to proper resolution
- Prevents accidental production deployment with default key

**Development Workflow:**
- Development mode (DEBUG=True) still works with insecure default
- Local testing unaffected
- Staging/production environments must set SECRET_KEY explicitly

**Django SECRET_KEY Requirements:**
- **Length:** At least 50 characters (Django recommendation)
- **Randomness:** Cryptographically secure random string
- **Uniqueness:** Different for each environment (dev, staging, prod)
- **Storage:** Environment variables only, never in version control

**Key Rotation (Django 4.1+):**
```python
# Zero-downtime key rotation with SECRET_KEY_FALLBACKS
SECRET_KEY = config('SECRET_KEY')
SECRET_KEY_FALLBACKS = [
    config('OLD_SECRET_KEY')  # Users with old sessions can still authenticate
] if config('OLD_SECRET_KEY', default=None) else []

# Remove OLD_SECRET_KEY after 24-48 hours (all sessions expired/renewed)
```

## Acceptance Criteria

**Code Changes:**
- [ ] SECRET_KEY validation added to `/backend/plant_community_backend/settings.py`
- [ ] Application fails to start if SECRET_KEY not set and DEBUG=False
- [ ] Application fails to start if SECRET_KEY contains insecure patterns
- [ ] Application fails to start if SECRET_KEY < 50 characters
- [ ] Clear error message with generation instructions displayed
- [ ] Development mode (DEBUG=True) still works with default key

**Testing:**
- [ ] Test 1: App starts with SECRET_KEY set in production mode
  ```bash
  export DEBUG=False
  export SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
  python manage.py check --deploy
  # Expected: Success
  ```

- [ ] Test 2: App fails without SECRET_KEY in production mode
  ```bash
  export DEBUG=False
  unset SECRET_KEY
  python manage.py check --deploy
  # Expected: ImproperlyConfigured exception with helpful message
  ```

- [ ] Test 3: App fails with insecure SECRET_KEY patterns
  ```bash
  export DEBUG=False
  export SECRET_KEY="django-insecure-test"
  python manage.py check --deploy
  # Expected: ImproperlyConfigured exception
  ```

- [ ] Test 4: App fails with short SECRET_KEY
  ```bash
  export DEBUG=False
  export SECRET_KEY="short"
  python manage.py check --deploy
  # Expected: ImproperlyConfigured exception
  ```

- [ ] Test 5: Development mode works without SECRET_KEY
  ```bash
  export DEBUG=True
  unset SECRET_KEY
  python manage.py runserver
  # Expected: Success with insecure default key
  ```

**Documentation:**
- [ ] `.env.example` updated with SECRET_KEY generation instructions
- [ ] Production deployment checklist includes SECRET_KEY verification
- [ ] README.md includes SECRET_KEY setup instructions
- [ ] Security documentation updated with key rotation procedure

## Success Metrics

**Immediate (Within 24 hours):**
- ✅ No production deployments possible without explicit SECRET_KEY
- ✅ Clear error messages guide developers to correct resolution
- ✅ Development workflow unaffected

**Long-term (Within 30 days):**
- 📋 Quarterly SECRET_KEY rotation policy established
- 📋 Monitoring for authentication anomalies (unusual session patterns)
- 📋 Secret management system integrated (AWS Secrets Manager, HashiCorp Vault)

## Dependencies & Risks

**Dependencies:**
- None - pure configuration change
- Compatible with Django 5.2 and python-decouple

**Risks:**
- **Low:** Existing deployments without SECRET_KEY will fail to start
  - **Mitigation:** This is intentional - fail fast is the goal
  - **Mitigation:** Clear error message guides to resolution
  - **Mitigation:** Document in deployment checklist

- **Low:** Team members need to generate SECRET_KEY for first deployment
  - **Mitigation:** Provide generation command in error message
  - **Mitigation:** Update documentation with setup instructions

## References & Research

### Internal References
- **Code Review Finding:** security-sentinel agent (Finding #2)
- **Security Audit:** `/backend/docs/development/SECURITY_AUDIT_REPORT.md`
- **Settings File:** `/backend/plant_community_backend/settings.py:34`
- **Environment Config:** `/backend/.env.example`

### External References
- **Django SECRET_KEY Docs:** https://docs.djangoproject.com/en/5.2/ref/settings/#secret-key
- **Django Deployment Checklist:** https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- **Adam Johnson Secret Key Rotation:** https://adamj.eu/tech/2023/06/12/django-secret-key-rotation/
- **OWASP Django Security:** https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html
- **CWE-798 Hard-coded Credentials:** https://cwe.mitre.org/data/definitions/798.html

### Related Work
- **Issue #001:** Rotate exposed API keys (SECRET_KEY rotation)
- **Git commit:** b4819df (Week 3 Quick Wins)
- **Security incident:** SECURITY_INCIDENT_API_KEYS.md

---

**Created:** 2025-10-22
**Priority:** 🔴 CRITICAL
**Assignee:** @williamtower
**Labels:** `priority: critical`, `type: security`, `area: backend`, `week-3`, `code-review`
**Estimated Effort:** 15 minutes (code changes) + 15 minutes (testing)
