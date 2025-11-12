---
status: pending
priority: p1
issue_id: "007"
tags: [code-review, security, django, authentication]
dependencies: []
---

# JWT Secret Key Separation - Development Fallback

## Problem Statement

Development environment allows JWT tokens to be signed with the same `SECRET_KEY` used for Django sessions/CSRF if `JWT_SECRET_KEY` is not set, creating security risk.

**Location:** `backend/plant_community_backend/settings.py:556-592`

## Findings

- Discovered during security audit by Security Sentinel agent
- **Current Configuration:**
  ```python
  # Development: Allow fallback to SECRET_KEY for convenience
  JWT_SECRET_KEY = config('JWT_SECRET_KEY', default=None)
  if JWT_SECRET_KEY:
      SIMPLE_JWT['SIGNING_KEY'] = JWT_SECRET_KEY
  else:
      SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY  # ⚠️ SECURITY RISK
  ```
- **Risk:** If `SECRET_KEY` leaks from error logs or config files:
  1. Attacker can forge valid JWT tokens (authentication bypass)
  2. Attacker can tamper with session cookies
  3. Attacker can generate valid CSRF tokens
- **Good Practice:** Production DOES enforce separation:
  ```python
  if not DEBUG:
      if JWT_SECRET_KEY == SECRET_KEY:
          raise ImproperlyConfigured(...)  # ✅ Enforces separation
  ```

## Proposed Solutions

### Option 1: Remove Development Fallback (RECOMMENDED)
```python
# Require JWT_SECRET_KEY in all environments
JWT_SECRET_KEY = config('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ImproperlyConfigured(
        "JWT_SECRET_KEY environment variable is required. "
        "Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

if JWT_SECRET_KEY == SECRET_KEY:
    raise ImproperlyConfigured(
        "JWT_SECRET_KEY must be different from SECRET_KEY. "
        "Generate a separate key for JWT signing."
    )

SIMPLE_JWT['SIGNING_KEY'] = JWT_SECRET_KEY
```

- **Pros**: Enforces security best practice in all environments, prevents accidental misconfiguration
- **Cons**: Requires `.env` setup for all developers (minor inconvenience)
- **Effort**: 1 hour (settings update + .env.example + documentation)
- **Risk**: Low (only affects new development setups)

### Option 2: Keep Fallback but Add Warning (Not Recommended)
```python
if not JWT_SECRET_KEY:
    logger.warning(
        "[SECURITY] JWT_SECRET_KEY not set - using SECRET_KEY as fallback. "
        "This is insecure and should only be used in development."
    )
    SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY
```

- **Pros**: No breaking changes
- **Cons**: Doesn't prevent the security issue, only warns
- **Effort**: 30 minutes
- **Risk**: Medium (developers may ignore warning)

## Recommended Action

**Implement Option 1** - Require JWT_SECRET_KEY in all environments.

Update `.env.example`:
```bash
# REQUIRED: Generate separate keys for security
SECRET_KEY=your-django-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Generate keys with:
# python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## Technical Details

- **Affected Files**:
  - `backend/plant_community_backend/settings.py` (JWT configuration)
  - `backend/.env.example` (environment template)
  - `CLAUDE.md` (documentation)
- **Related Components**: JWT authentication, token generation/validation
- **Environment Variables**: Requires `JWT_SECRET_KEY` in all `.env` files
- **Impact**: Developers must update local `.env` files

## Resources

- Security Sentinel audit report (Nov 3, 2025)
- JWT best practices: https://tools.ietf.org/html/rfc8725
- Django secret key management: https://docs.djangoproject.com/en/5.0/ref/settings/#secret-key

## Acceptance Criteria

- [ ] Settings.py requires JWT_SECRET_KEY (no fallback)
- [ ] Settings.py validates JWT_SECRET_KEY != SECRET_KEY
- [ ] .env.example updated with clear instructions
- [ ] CLAUDE.md updated with setup instructions
- [ ] All developers updated local .env files
- [ ] Tests pass with separate JWT_SECRET_KEY
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive security audit
- Analyzed by Security Sentinel agent
- Categorized as P1 (security best practice enforcement)

**Learnings:**
- Separate signing keys prevent cascade compromise
- Production enforcement is good, but development should match
- Documentation and .env.example should guide developers to secure configuration

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Security Sentinel
CWE: CWE-798 (Use of Hard-coded Credentials - in this case, shared credentials)
CVSS Score: 7.5 (High)
Current Risk: LOW (production is protected, only development affected)
