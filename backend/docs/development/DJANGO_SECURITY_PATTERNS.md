# Django Security Patterns - Code Review Standards

**Last Updated:** 2025-10-23
**Source:** Code review feedback from SECRET_KEY security fix (Issue #2, PR #7)

## Overview

This document codifies security patterns extracted from comprehensive code reviews of Django settings and configuration. These patterns ensure production-ready security while maintaining development flexibility.

---

## 1. SECRET_KEY Configuration Pattern

### Security Requirements

Django's `SECRET_KEY` is used for cryptographic signing of:
- Session cookies (user authentication)
- CSRF tokens (security)
- Password reset tokens
- Signed cookies
- Any data requiring tamper-proof signatures

**Threat Model:**
- **Session Hijacking**: Weak SECRET_KEY allows attackers to forge session cookies
- **CSRF Attacks**: Predictable SECRET_KEY enables CSRF token forgery
- **Password Reset Exploits**: Known SECRET_KEY allows password reset token generation
- **Cookie Tampering**: Insecure SECRET_KEY permits signed cookie modification

### Implementation Pattern

**File:** `settings.py` (Django project settings)

#### Required Import

```python
from django.core.exceptions import ImproperlyConfigured
```

**BLOCKER:** Missing this import causes `NameError` at runtime when production validation fails.

#### Environment-Aware Configuration

```python
# Environment-aware SECRET_KEY configuration with production validation
if config('DEBUG', default=False, cast=bool):
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

### Validation Rules

1. **Production Enforcement (DEBUG=False)**
   - SECRET_KEY MUST be set via environment variable
   - No default value allowed in production
   - Fail-fast with `ImproperlyConfigured` exception

2. **Pattern Validation**
   - Reject common insecure patterns:
     - `django-insecure` (Django's development default prefix)
     - `change-me` (placeholder value)
     - `your-secret-key-here` (example value)
     - `secret` (too generic)
     - `password` (security anti-pattern)
     - `abc123` (weak test value)
   - Case-insensitive matching (`SECRET_KEY.lower()`)

3. **Length Validation**
   - Minimum 50 characters required
   - Django's `get_random_secret_key()` generates 50-character keys
   - Provides sufficient entropy for cryptographic operations

4. **Development Flexibility (DEBUG=True)**
   - Allow default value for local development
   - Clearly marked as insecure: `DO-NOT-USE-IN-PRODUCTION`
   - No production risk since DEBUG=True blocks production deployment

### Error Message Best Practices

**Characteristics of good error messages:**

1. **Clear Severity**: Use "CRITICAL:" prefix for security issues
2. **Explain Impact**: Document what SECRET_KEY protects
3. **Provide Solution**: Include exact command to generate secure key
4. **Multiple Remediation Paths**: Show both environment variable and .env file options
5. **Visual Separation**: Use separator lines (`=` * 70) for readability
6. **Context-Specific**: Different messages for missing vs insecure vs too-short keys

**Example from implementation:**

```python
raise ImproperlyConfigured(
    "\n"
    "=" * 70 + "\n"
    "CRITICAL: SECRET_KEY environment variable is not set!\n"
    "=" * 70 + "\n"
    "Django requires a unique SECRET_KEY for production security.\n"
    # ... explanation of impact ...
    "\n"
    "Generate a secure key with:\n"
    "  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'\n"
    # ... remediation steps ...
)
```

### Common Mistakes

#### BLOCKER Issues

1. **Missing Import**
   ```python
   # WRONG - Missing import
   # Later in file:
   raise ImproperlyConfigured("...")  # NameError at runtime!

   # CORRECT
   from django.core.exceptions import ImproperlyConfigured
   ```

2. **No Production Validation**
   ```python
   # WRONG - No environment check
   SECRET_KEY = config('SECRET_KEY', default='insecure-default')

   # CORRECT - Environment-aware
   if config('DEBUG', default=False, cast=bool):
       SECRET_KEY = config('SECRET_KEY', default='dev-only-key')
   else:
       try:
           SECRET_KEY = config('SECRET_KEY')
       except Exception:
           raise ImproperlyConfigured("SECRET_KEY not set!")
   ```

3. **Hardcoded Production Key**
   ```python
   # WRONG - Hardcoded in source control
   SECRET_KEY = 'actual-secret-key-value-here'

   # CORRECT - From environment
   SECRET_KEY = config('SECRET_KEY')
   ```

#### WARNING Issues

1. **Duplicate Validation**
   ```python
   # In settings.py at lines 35-95:
   # Comprehensive SECRET_KEY validation already exists

   # WRONG - Later in validate_environment() at line 876:
   if SECRET_KEY == 'some-default-value':  # Redundant!
       warnings.append("SECRET_KEY is using default value")

   # CORRECT - Document instead
   # Note: SECRET_KEY is validated earlier in settings.py (lines 35-95)
   # with comprehensive checks for pattern matching, length, and production requirements
   ```

2. **Print Statements in Settings**
   ```python
   # WRONG - Using print() in settings validation
   if not SECRET_KEY:
       print("WARNING: SECRET_KEY not set")

   # CORRECT - Use logger (if needed at all)
   import logging
   logger = logging.getLogger(__name__)

   # But prefer: Let ImproperlyConfigured crash the app
   # Settings errors should fail-fast, not log warnings
   ```

### Testing

**Development Mode (DEBUG=True):**
```bash
# Should work with default value
unset SECRET_KEY
python manage.py check
# Expected: No errors, uses development default
```

**Production Mode (DEBUG=False):**
```bash
# Should fail without SECRET_KEY
export DEBUG=False
unset SECRET_KEY
python manage.py check
# Expected: ImproperlyConfigured exception with detailed message

# Should fail with insecure pattern
export SECRET_KEY='change-me-please'
python manage.py check
# Expected: ImproperlyConfigured - contains 'change-me' pattern

# Should fail with short key
export SECRET_KEY='short'
python manage.py check
# Expected: ImproperlyConfigured - less than 50 characters

# Should succeed with valid key
export SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
python manage.py check
# Expected: No errors
```

### Documentation Requirements

When implementing SECRET_KEY validation, include comments explaining:

1. **Location of Validation**
   ```python
   # In validate_environment() function:
   # Note: SECRET_KEY is validated earlier in settings.py (lines 35-95)
   # with comprehensive checks for pattern matching, length, and production requirements
   ```

2. **Security Rationale**
   ```python
   # Environment-aware SECRET_KEY configuration with production validation
   # Protects against: session hijacking, CSRF attacks, password reset exploits, cookie tampering
   ```

3. **Development vs Production Behavior**
   ```python
   if config('DEBUG', default=False, cast=bool):
       # Development: Allow insecure default for local testing
       SECRET_KEY = config('SECRET_KEY', default='...')
   else:
       # Production: MUST have SECRET_KEY set - fail loudly if missing
       # ...
   ```

---

## 2. Environment Variable Validation Pattern

### Principle: Validate at Settings Load Time

**Why:** Fail-fast before the application starts serving requests.

**Pattern:**
```python
def validate_environment():
    """
    Validate critical environment variables and warn about missing configurations.
    This prevents silent failures and provides clear guidance for setup.
    """
    warnings = []
    critical_errors = []

    # Critical settings that MUST be set in production
    if not DEBUG:
        if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['localhost', '127.0.0.1']:
            critical_errors.append("ALLOWED_HOSTS must be configured for production domains")

        if not config('CSRF_TRUSTED_ORIGINS', default=''):
            critical_errors.append("CSRF_TRUSTED_ORIGINS must be set in production")

    # Log results
    if critical_errors:
        for error in critical_errors:
            logger.error(f"CRITICAL CONFIGURATION ERROR: {error}")
        if not DEBUG:
            raise Exception(f"Critical configuration errors detected: {'; '.join(critical_errors)}")

# Run validation on settings load
validate_environment()
```

### Best Practices

1. **Separate Concerns**
   - Validate each setting once, in the most appropriate location
   - Document cross-references if validation logic exists elsewhere

2. **Environment-Aware Strictness**
   - Development: Warnings are acceptable
   - Production: Critical errors must raise exceptions

3. **Actionable Messages**
   - Include exact steps to fix the issue
   - Provide example values or generation commands
   - Reference documentation when available

---

## 3. Django Exception Handling Pattern

### Use Django's Built-in Exceptions

**Pattern:**
```python
from django.core.exceptions import ImproperlyConfigured

# For configuration errors (settings, environment)
raise ImproperlyConfigured("Detailed error message")

# For validation errors (user input)
from django.core.exceptions import ValidationError
raise ValidationError("Invalid input")

# For permission errors
from django.core.exceptions import PermissionDenied
raise PermissionDenied("Access denied")
```

**Why Django exceptions instead of generic Python exceptions:**
- Consistent with Django conventions
- Better integration with Django's error handling
- Clear semantic meaning
- Proper HTTP status code mapping (for views)

---

## 4. Self-Documenting Security Code

### Principle: Code Should Explain the "Why"

**Good Example:**
```python
# Environment-aware SECRET_KEY configuration with production validation
# Protects against: session hijacking, CSRF attacks, password reset exploits, cookie tampering
if config('DEBUG', default=False, cast=bool):
    # Development: Allow insecure default for local testing
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-only-DO-NOT-USE-IN-PRODUCTION-abc123xyz')
else:
    # Production: MUST have SECRET_KEY set - fail loudly if missing
    try:
        SECRET_KEY = config('SECRET_KEY')
    except Exception:
        raise ImproperlyConfigured("...")
```

**Why this works:**
1. **Explains threat model** - Lists specific attacks prevented
2. **Documents behavior** - Clear development vs production distinction
3. **Justifies design** - "fail loudly" explains exception raising
4. **Guides usage** - "DO-NOT-USE-IN-PRODUCTION" prevents misuse

---

## Code Review Checklist

When reviewing Django settings.py changes:

### SECRET_KEY Validation

- [ ] `ImproperlyConfigured` import present
- [ ] Environment-aware configuration (DEBUG check)
- [ ] Production requires SECRET_KEY from environment (no default)
- [ ] Pattern validation against insecure strings
- [ ] Length validation (50+ characters)
- [ ] Clear error messages with remediation steps
- [ ] Development allows safe default for local testing
- [ ] No duplicate validation elsewhere in settings

### Error Messages

- [ ] Severity clearly indicated (CRITICAL, WARNING, ERROR)
- [ ] Impact explained (what does this setting protect)
- [ ] Solution provided (exact commands to fix)
- [ ] Multiple remediation paths shown
- [ ] Visually separated with formatting

### Documentation

- [ ] Inline comments explain "why" not just "what"
- [ ] Cross-references to other validation locations
- [ ] Threat model documented for security settings
- [ ] Development vs production behavior explained

### Exception Handling

- [ ] Django exceptions used (`ImproperlyConfigured`, not generic `Exception`)
- [ ] Type-safe exception handling
- [ ] Fail-fast for production errors
- [ ] Graceful warnings for development issues

---

## Related Documentation

1. **Django Official Docs:**
   - [SECRET_KEY Setting](https://docs.djangoproject.com/en/5.2/ref/settings/#secret-key)
   - [ImproperlyConfigured Exception](https://docs.djangoproject.com/en/5.2/ref/exceptions/#improperlyconfigured)

2. **Project Documentation:**
   - `/backend/docs/development/security-fixes-week1.md` - Security audit findings
   - `/backend/docs/development/quick-start-security.md` - Security quick reference
   - `/.claude/agents/code-review-specialist.md` - Automated review patterns

3. **Code Examples:**
   - `/backend/plant_community_backend/settings.py` (lines 15, 35-95) - Reference implementation
   - Commit `d2c9c2c` - SECRET_KEY security fix with comprehensive validation

---

## Conclusion

Django SECRET_KEY security is critical for production deployments. This pattern ensures:

1. **Production Safety** - Fail-fast with clear errors when misconfigured
2. **Development Flexibility** - Allow safe defaults for local testing
3. **Security Depth** - Multiple validation layers (existence, patterns, length)
4. **Developer Experience** - Actionable error messages with exact fix steps
5. **Maintainability** - Self-documenting code with clear threat model

**Golden Rule:** Security settings should fail loudly in production and guide gently in development.

---

**Codified From:** Code review of PR #7 (Security fix for SECRET_KEY configuration)
**Reviewed By:** code-review-specialist agent
**Approval Status:** APPROVED WITH NO BLOCKERS
**Date:** 2025-10-23
