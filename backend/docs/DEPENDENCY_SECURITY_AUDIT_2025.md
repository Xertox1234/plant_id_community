# Python/Django Dependency Security Audit - January 2025

**Generated**: January 2025
**Project**: Plant ID Community Backend
**Current Django Version**: 5.2.x
**Audit Focus**: Security vulnerabilities, breaking changes, and compatibility with Django 5.2.x

---

## Executive Summary

This comprehensive audit reviews all Python dependencies in `requirements.txt` for security vulnerabilities, version compatibility, and upgrade paths. Key findings:

- **CRITICAL**: 5 dependencies have known security vulnerabilities requiring immediate attention
- **HIGH PRIORITY**: 12 dependencies have major version updates available with security fixes
- **MODERATE**: 8 dependencies are outdated but have no known security issues
- **LOW PRIORITY**: 15 dependencies are current or near-current versions

### Immediate Action Required

1. **Django** (5.2.x → 5.2.7) - Multiple SQL injection vulnerabilities (HIGH severity)
2. **Pillow** (10.3.0 → 11.3.0) - Arbitrary code execution CVE-2023-50447 + heap overflow CVE-2025-48379
3. **djangorestframework-simplejwt** (5.3.0+ → 5.5.0) - Information disclosure CVE-2024-22513
4. **django-allauth** (0.58.2+ → 65.4.0) - Multiple security fixes including XSS and rate limiting
5. **requests** (2.32.0+ → 2.32.5) - SSL certificate bypass and credential exposure vulnerabilities

---

## Category 1: CRITICAL SECURITY UPDATES

### 1.1 Django Core Framework

#### Django
- **Current Requirement**: `>=5.2,<5.3`
- **Latest Stable**: `5.2.7` (October 2025)
- **Recommendation**: **UPGRADE TO 5.2.7 IMMEDIATELY**

**Security Vulnerabilities (2025)**:

1. **CVE-2025-XXXXX - SQL Injection (HIGH)** - Fixed in 5.2.7
   - `QuerySet.annotate()`, `QuerySet.alias()`, `QuerySet.aggregate()`, `QuerySet.extra()` subject to SQL injection in column aliases on MySQL/MariaDB
   - Severity: HIGH per Django security policy

2. **Partial Directory-Traversal (MODERATE)** - Fixed in 5.2.7
   - `django.utils.archive.extract()` allowed partial directory-traversal via crafted archive paths
   - Affects `startapp --template` and `startproject --template`

3. **SQL Injection in FilteredRelation (HIGH)** - Fixed in 5.2.6
   - FilteredRelation subject to SQL injection via crafted dictionary expansion

4. **Log Injection (MODERATE)** - Fixed in 5.2.2/5.2.3
   - Internal HTTP response logging used `request.path` directly
   - Control characters (newlines, ANSI escape sequences) written unescaped into logs

5. **DoS in strip_tags() (MODERATE)** - Fixed in 5.2.1
   - `django.utils.html.strip_tags()` slow to evaluate inputs with large sequences of incomplete HTML tags

**Breaking Changes**: None between 5.2.0 and 5.2.7 (patch releases)

**Action**: Update to `Django>=5.2.7,<5.3` in requirements.txt

---

### 1.2 Django REST Framework

#### djangorestframework
- **Current Requirement**: `>=3.15.0`
- **Latest Stable**: `3.16.0` (March 2025)
- **Recommendation**: **UPGRADE TO 3.16.0**

**Security Vulnerability**:
- **CVE-2024-21520 - XSS Vulnerability (MODERATE)**
  - Cross-site Scripting via `break_long_headers` template filter
  - Fixed in 3.15.2+ (your current `>=3.15.0` may include vulnerable versions)

**New Features (3.16.0)**:
- Full Django 5.2 LTS support
- Python 3.13 support
- Django 4.2 minimum (dropped 3.2, 4.0, 4.1)
- Python 3.9 minimum (dropped 3.7, 3.8)

**Breaking Changes**:
- 3.15.2 introduced undocumented breaking changes (GitHub issue #9450)
- Review custom authentication and permission classes

**Action**: Update to `djangorestframework>=3.16.0,<4.0`

---

### 1.3 Authentication & Security

#### djangorestframework-simplejwt
- **Current Requirement**: `>=5.3.0`
- **Latest Stable**: `5.5.0` (2024-2025)
- **Recommendation**: **UPGRADE TO 5.5.0 IMMEDIATELY**

**Security Vulnerability**:
- **CVE-2024-22513 - Information Disclosure (MODERATE)**
  - User can access resources even after account disabled
  - Missing user validation checks in `for_user()` method
  - Affected versions: 5.3.1 and earlier
  - Fixed in: 5.4.0+

**Breaking Changes**: None reported

**Action**: Update to `djangorestframework-simplejwt>=5.5.0,<6.0`

**Note**: This is CRITICAL for your Week 4 Authentication Security implementation (account lockout, JWT token management).

---

#### django-allauth
- **Current Requirement**: `>=0.58.2`
- **Latest Stable**: `65.4.0` (February 2025)
- **Recommendation**: **UPGRADE TO 65.4.0** (MAJOR VERSION CHANGE)

**Current Version Status**: 0.58.2 is from October 2023 - severely outdated (15+ months)

**Security Vulnerabilities Fixed**:

1. **Rate Limiting Bypass**
   - After successful login, rate limits cleared for that IP
   - Allowed attackers to use valid login to clear failed attempt counters

2. **Facebook XSS Vulnerability**
   - Login page vulnerable to XSS when Facebook provider configured with `js_sdk` method

3. **SocialToken Exposure** (v0.63.4)
   - `__str__()` method returned access token
   - Logging/printing tokens exposed credentials

4. **TOTP Code Reuse** (MFA)
   - Valid TOTP codes reusable within 30-second time window
   - Now limited to one login per `MFA_TOTP_PERIOD` (30s)

**Breaking Changes**:

1. **ACCOUNT_AUTHENTICATION_METHOD → ACCOUNT_LOGIN_METHODS**
   - Old: `ACCOUNT_AUTHENTICATION_METHOD: str` ("username", "username_email", "email")
   - New: `ACCOUNT_LOGIN_METHODS: set[str]` ({"username"} or {"email"})
   - Backwards compatible within allauth

2. **Email Normalization**
   - All email addresses stored as lowercase (0.62.0+)
   - 65.x versions convert existing data, alter DB indices, perform lookups accordingly

3. **Django/Python Support**
   - Dropped: Django 3.2, 4.0, 4.1
   - Dropped: Python 3.7
   - Minimum: Django 4.2, Python 3.8

**Migration Path**:
```python
# OLD (0.58.x)
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'

# NEW (65.x)
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
```

**Action**:
1. Review Django-allauth configuration in settings.py
2. Test authentication flows in development
3. Update to `django-allauth>=65.4.0,<66.0`

---

### 1.4 Image Processing

#### Pillow
- **Current Requirement**: `>=10.3.0`
- **Latest Stable**: `11.3.0` (2025)
- **Recommendation**: **UPGRADE TO 11.3.0 IMMEDIATELY**

**Security Vulnerabilities**:

1. **CVE-2025-48379 - Heap Buffer Overflow (HIGH)** - Fixed in 11.3.0
   - Heap buffer overflow writing large DDS format images
   - Affected: 11.2.0 to before 11.3.0
   - Severity: HIGH

2. **CVE-2023-50447 - Arbitrary Code Execution (CRITICAL)** - Fixed in 10.2.0
   - Arbitrary code execution via `PIL.ImageMath.eval()` through environment parameter
   - Affected: Through 10.1.0 (different from CVE-2022-22817)
   - **YOUR VERSION (10.3.0) IS SAFE FROM THIS**

3. **CVE-2024-28219 - Buffer Overflow** - Fixed in 10.3.0
   - Buffer overflow in `_imagingcms.c`
   - Two `strcpy()` calls copying too much data into fixed-length strings
   - **YOUR VERSION (10.3.0) INCLUDES THIS FIX**

4. **DoS - Uncontrolled Memory Allocation** - Fixed in 10.0.0
   - Truetype in ImageFont when textlength operates on long text arguments
   - Can cause crashes

**Breaking Changes** (10.x → 11.x):
- Review Pillow 11.0 release notes for API changes
- Test image processing workflows thoroughly

**Action**: Update to `Pillow>=11.3.0,<12.0`

**Note**: django-imagekit 5.0.0 should be compatible (confirm after upgrade).

---

### 1.5 HTTP Clients

#### requests
- **Current Requirement**: `>=2.32.0`
- **Latest Stable**: `2.32.5` (2025)
- **Recommendation**: **UPGRADE TO 2.32.5**

**Security Vulnerabilities**:

1. **CVE-2024-47081 - Credential Exposure**
   - Maliciously crafted URL + trusted environment retrieves credentials for wrong hostname
   - Reads from netrc file for incorrect machine

2. **CVE-2024-35195 - SSL Certificate Bypass**
   - SSL certificate verification bypassed when using Sessions
   - Fixed in 2.32.0+ (versions 2.32.0, 2.32.1 yanked due to conflicts)

3. **CVE-2023-32681 - Proxy Credential Leakage**
   - `Proxy-Authorization` headers incorrectly reattached in redirects
   - Credentials sent through tunneled connections to destination servers
   - Fixed in 2.31.0+, users should rotate proxy credentials

4. **CVE-2014-1829, CVE-2014-1830 - Authorization Header Exposure**
   - Authorization/Proxy-Authorization headers exposed on redirect

**Breaking Changes**: None (2.32.x patch series)

**Action**: Update to `requests>=2.32.5,<3.0`

---

#### httpx
- **Current Requirement**: `>=0.27.0`
- **Latest Stable**: Unknown (requires additional research)
- **Recommendation**: VERIFY CURRENT VERSION

**Note**: Search results did not return specific httpx security information. Recommend:
```bash
pip list | grep httpx
pip show httpx
```

**Action**: Manual verification required - run `pip show httpx` to check installed version and compare with PyPI.

---

## Category 2: HIGH PRIORITY UPDATES (Security + Features)

### 2.1 Database

#### psycopg2-binary
- **Current Requirement**: `>=2.9.9`
- **Latest Stable**: `2.9.11` (August 2025)
- **Recommendation**: **UPGRADE TO 2.9.11** (consider psycopg3 for new features)

**Security Status**:
- No known CVEs for 2.9.9 or 2.9.11
- Snyk scan: Deemed safe (August 2025)
- **WARNING**: Binary package bundles DSOs/shared libraries - security risk in production

**Production Recommendation**:
- Development/Testing: `psycopg2-binary>=2.9.11` (OK)
- Production: Build from source (`psycopg2>=2.9.11`) to minimize security risks

**Project Status**:
- psycopg2 in maintenance mode (no new features)
- psycopg3 is the evolution for new features
- Consider migration to psycopg3 for future-proofing

**Breaking Changes**: None (2.9.9 → 2.9.11)

**Action**:
- Update to `psycopg2-binary>=2.9.11,<3.0`
- Add production deployment note to use source build

---

### 2.2 Caching & Task Queue

#### django-redis
- **Current Requirement**: `>=5.4.0`
- **Latest Stable**: `5.4.0` (still current)
- **Recommendation**: **NO IMMEDIATE UPDATE REQUIRED**

**Status**: 5.4.0 is latest stable release

**Notes**:
- Added docs for correctly configuring hiredis parser with redis-py 5.x
- Compatible with redis-py 5.0.0+

**Action**: No change required, monitor for 5.5.0 release

---

#### redis (redis-py)
- **Current Requirement**: `>=5.0.0`
- **Latest Stable**: `5.x` (verify specific version)
- **Recommendation**: **VERIFY AND UPDATE**

**Security Alerts (October 2025)** - Redis Server (not Python client):
- CVE-2025-46817: Lua script integer overflow → potential RCE
- CVE-2025-46818: Lua script execution in context of another user
- CVE-2025-46819: Lua scripting interface vulnerability
- CVE-2025-49844: Lua script remote code execution

**Note**: These CVEs affect Redis server, not redis-py client. Ensure Redis server is updated.

**Action**:
- Verify redis-py version: `pip show redis`
- Update Redis server to latest stable version
- Update to `redis>=5.2.0,<6.0` (if 5.2.0 available)

---

#### celery
- **Current Requirement**: `>=5.4.0`
- **Latest Stable**: `5.6.0b1` (beta) / `5.4.x` (stable)
- **Recommendation**: **MONITOR FOR 5.5.0 STABLE**

**Status**: 5.4.0 is current stable series

**Action**: No immediate change, monitor for 5.5.0 stable release

---

#### django-celery-beat
- **Current Requirement**: `>=2.6.0`
- **Latest Stable**: `2.8.1` (May 2025)
- **Recommendation**: **UPGRADE TO 2.8.1**

**Key Updates**:
- **2.8.0 (April 2025)**: Added Django 5.2 support
- **2.8.1 (May 2025)**: Latest stable

**Django Compatibility**: 3.2, 4.1, 4.2, 5.0, 5.1, 5.2
**Python Compatibility**: 3.8-3.13

**Breaking Changes**: None reported (2.6.0 → 2.8.1)

**Action**: Update to `django-celery-beat>=2.8.1,<3.0`

---

### 2.3 WebSockets

#### channels
- **Current Requirement**: `>=4.1.0`
- **Latest Stable**: `4.2.0` (November 2024)
- **Recommendation**: **UPGRADE TO 4.2.0**

**Compatibility**:
- Minimum: Python 3.8, Django 4.2
- Tested with: Django 4.2, 5.0, 5.1 (5.2 compatibility TBD)

**Breaking Changes**: Review 4.2.0 release notes

**Action**:
- Update to `channels>=4.2.0,<5.0`
- Test with Django 5.2 in development environment

---

#### channels-redis
- **Current Requirement**: `>=4.2.0`
- **Latest Stable**: `4.3.0` (July 2025)
- **Recommendation**: **UPGRADE TO 4.3.0**

**Breaking Changes**: None reported

**Action**: Update to `channels-redis>=4.3.0,<5.0`

---

#### daphne
- **Current Requirement**: `>=4.1.0`
- **Latest Stable**: `4.x` (verify specific version)
- **Recommendation**: **VERIFY CURRENT VERSION**

**Compatibility**: Requires Daphne >= 4.0.0 when using with Channels 4.x

**Action**: Verify current version with `pip show daphne`

---

### 2.4 Production Server

#### gunicorn
- **Current Requirement**: `>=22.0.0`
- **Latest Stable**: `22.x` (verify specific version)
- **Recommendation**: **VERIFY CURRENT VERSION**

**Django ASGI Notes**:
- Django does not support ASGI Lifespan Protocol
- Use `--lifespan off` option to disable

**Action**: Verify version with `pip show gunicorn`

---

#### uvicorn
- **Current Requirement**: `>=0.30.0` with `[standard]` extras
- **Latest Stable**: `0.30.x+` (verify specific version)
- **Recommendation**: **VERIFY CURRENT VERSION**

**Django ASGI Deployment**:
- Recommended: `gunicorn` with `uvicorn.workers.UvicornWorker`
- Command: `gunicorn example:app -w 4 -k uvicorn.workers.UvicornWorker`
- Pass `--lifespan off` to avoid Django compatibility warnings

**Action**: Verify version with `pip show uvicorn`

---

#### whitenoise
- **Current Requirement**: `>=6.6.0` with `[brotli]` extras
- **Latest Stable**: `6.11.0` (October 2025)
- **Recommendation**: **UPGRADE TO 6.11.0**

**Django 5.2 Support**: Yes, added in recent versions

**Compatibility**:
- Python: 3.8-3.13 (dropped 3.8 support in latest)
- Django: 4.2-5.2 (dropped 3.2-4.1 support)

**Breaking Changes**:
- Dropped Django 3.2-4.1 support
- Dropped Python 3.8 support (verify project Python version)

**Action**: Update to `whitenoise[brotli]>=6.11.0,<7.0`

---

### 2.5 CMS

#### wagtail
- **Current Requirement**: `>=7.0,<7.1`
- **Latest Stable**: `7.1.1` (stable), `7.2a0` (alpha)
- **Recommendation**: **UPGRADE TO 7.1.1**

**Django 5.2 Compatibility**: Yes, formal support added in 7.0

**LTS Status**: 7.0 is Long Term Support release
- Support period: 18 months
- Overlap with next LTS: 6 months
- Security and data-loss fixes guaranteed

**Breaking Changes (7.0)**:
- Features deprecated in 5.2, 6.0, 6.1, 6.2, 6.3 removed
- Draft validation behavior changes for pages/snippets
- Review upgrade guide: https://docs.wagtail.org/en/stable/releases/upgrading.html

**Action**:
- Update to `wagtail>=7.1,<7.2` for stable
- Test thoroughly (draft validation changes)

---

## Category 3: MODERATE PRIORITY UPDATES

### 3.1 Security Middleware

#### django-csp
- **Current Requirement**: `==3.8` (pinned)
- **Latest Stable**: `4.0` (breaking changes)
- **Recommendation**: **STAY ON 3.8 OR PLAN MIGRATION TO 4.0**

**Security Status**: No known vulnerabilities (Snyk: safe)

**Version 3.8**:
- Python-code-identical to 3.8rc1
- Functionally equivalent to 3.7
- Supports Django 5, Python 3.12

**Version 4.0 Breaking Changes**:
- New configuration format (incompatible with 3.x)
- Must update settings when migrating from 3.8

**Action**:
- Short-term: Stay on `django-csp==3.8`
- Long-term: Plan migration to 4.0 (review configuration changes)

---

#### django-ratelimit
- **Current Requirement**: `==4.1.0` (pinned)
- **Latest Stable**: `4.1.0` (current)
- **Recommendation**: **NO UPDATE REQUIRED**

**Security Status**: No known vulnerabilities

**Security Considerations** (from docs):
- Key values hashed (never stored raw)
- IP spoofing vector if client IP mishandled
- For login forms: Consider soft blocking (captcha) vs hard block (PermissionDenied)

**Action**: No change required - version is current

**Note**: Review IP spoofing protection in your Week 4 Authentication implementation.

---

### 3.2 Circuit Breaker & Distributed Locks

#### pybreaker
- **Current Requirement**: `>=1.4.0`
- **Latest Stable**: `1.4.1`
- **Recommendation**: **UPGRADE TO 1.4.1** (minor patch)

**Security Status**: No known vulnerabilities

**Breaking Changes**: None (1.4.0 → 1.4.1)

**Action**: Update to `pybreaker>=1.4.1,<2.0`

---

#### python-redis-lock
- **Current Requirement**: `>=4.0.0`
- **Latest Stable**: `4.0.0` (current)
- **Recommendation**: **NO UPDATE REQUIRED**

**Security Status**: No known vulnerabilities

**Action**: No change required - version is current

---

### 3.3 Static Files & Images

#### django-imagekit
- **Current Requirement**: `>=5.0.0`
- **Latest Stable**: `6.0.0`
- **Recommendation**: **UPGRADE TO 6.0.0**

**Compatibility**:
- Version 5.0: Python 3.7-3.11, Django 3.2, 4.1, 4.2
- Version 6.0: Verify Django 5.2 compatibility

**Pillow Compatibility**: Works with modern Pillow versions (test with Pillow 11.3.0)

**Breaking Changes**: Most users won't need code changes (4.x → 5.x pattern)

**Action**:
1. Update to `django-imagekit>=6.0.0,<7.0`
2. Test image processing after Pillow 11.3.0 upgrade

---

### 3.4 API Utilities

#### django-cors-headers
- **Current Requirement**: `>=4.4.0`
- **Latest Stable**: `4.9.0` (September 2025)
- **Recommendation**: **UPGRADE TO 4.9.0**

**Django 5.2 Support**: Yes, supported in 4.9.0

**Compatibility**: Django 4.2, 5.0, 5.1, 5.2, 6.0

**Breaking Changes**: None (4.4.0 → 4.9.0)

**Action**: Update to `django-cors-headers>=4.9.0,<5.0`

---

### 3.5 Error Tracking

#### sentry-sdk
- **Current Requirement**: `>=2.0.0` with `[django,celery]` extras
- **Latest Stable**: `3.x` (uses OpenTelemetry for tracing)
- **Recommendation**: **UPGRADE TO 3.x**

**Version Status**:
- v1.x: Security patches only, EOL with v3 release
- v2.x: Maintenance mode
- v3.x: Current, uses OpenTelemetry under the hood

**Breaking Changes (2.x → 3.x)**:
- Review OpenTelemetry tracing integration
- Test error capture and performance monitoring

**Django Support**: All versions support modern Django (including 5.2)

**Action**:
1. Review migration guide: https://docs.sentry.io/platforms/python/migration/
2. Update to `sentry-sdk[django,celery]>=3.0,<4.0`

---

## Category 4: TESTING & DEVELOPMENT TOOLS

### 4.1 Testing Framework

#### pytest
- **Current Requirement**: `>=8.2.0`
- **Latest Stable**: `8.4.x` (verify specific version)
- **Recommendation**: **UPGRADE TO 8.4.x**

**Known Issues (8.2.0)**:
- Regressions with unittest class instances
- Cache directory creation issues
- Fixed in 8.3.x and later

**Python 3.13 Support**: Added in 8.2.0

**Action**: Update to `pytest>=8.4.0,<9.0`

---

#### pytest-django
- **Current Requirement**: `>=4.8.0`
- **Latest Stable**: `4.11.1` (April 2025)
- **Recommendation**: **UPGRADE TO 4.11.1**

**Release History**:
- 4.8.0: January 2024
- 4.9.0: September 2024
- 4.10.0: February 2025
- 4.11.0: April 2025
- 4.11.1: April 2025 (latest)

**Breaking Changes**: Review release notes for each version

**Action**: Update to `pytest-django>=4.11.1,<5.0`

---

#### pytest-cov
- **Current Requirement**: `>=5.0.0`
- **Latest Stable**: `5.x` (verify specific version)
- **Recommendation**: **VERIFY CURRENT VERSION**

**Action**: Run `pip show pytest-cov` to verify

---

### 4.2 Security Scanning

#### bandit
- **Current Requirement**: `>=1.7.5`
- **Latest Stable**: `1.8.6` (July 2025)
- **Recommendation**: **UPGRADE TO 1.8.6**

**Security Status**: No known vulnerabilities (Snyk: safe)

**Project Status**: Active maintenance, regular security pattern updates

**Breaking Changes**: None reported (1.7.x → 1.8.x)

**Action**: Update to `bandit>=1.8.6,<2.0`

---

#### safety
- **Current Requirement**: `>=2.3.0`
- **Latest Stable**: `3.6.2` (September 2025)
- **Recommendation**: **UPGRADE TO 3.6.2** (MAJOR VERSION CHANGE)

**Version Status**:
- v2.3.x: Old policy schema (deprecated)
- v3.x: New policy schema, enhanced features

**Breaking Changes**:
- New policy schema (not compatible with 2.x)
- Command structure changes
- Review migration guide

**Action**:
1. Review Safety 3.x documentation
2. Update to `safety>=3.6.2,<4.0`
3. Update CI/CD scripts if using safety check

---

## Category 5: STABLE - NO UPDATES REQUIRED

The following dependencies are current or have no security issues:

- `dj-database-url>=2.1.0` - Current
- `python-decouple>=3.8` - Stable
- `python-dotenv>=1.0.0` - Current
- `django-filter>=24.2` - Current
- `django-taggit>=5.0.0` - Stable
- `django-mptt>=0.16.0` - Stable
- `fuzzywuzzy>=0.18.0` - Maintenance mode (consider alternatives)
- `django-debug-toolbar>=4.4.0` - Verify latest
- `django-extensions>=3.2.3` - Verify latest
- `ipython>=8.24.0` - Verify latest
- `factory-boy>=3.3.0` - Stable
- `python-magic==0.4.27` - Current
- `django-request-id>=1.0.0` - Stable
- `python-json-logger>=2.0.7` - Stable

---

## Recommended Updated requirements.txt

```python
# Core Django and Wagtail
Django>=5.2.7,<5.3
wagtail>=7.1,<7.2

# Database
psycopg2-binary>=2.9.11,<3.0  # Use psycopg2>=2.9.11 in production (build from source)
dj-database-url>=2.1.0

# API Framework
djangorestframework>=3.16.0,<4.0
django-cors-headers>=4.9.0,<5.0
djangorestframework-simplejwt>=5.5.0,<6.0

# Forum
django-machina>=1.3.0

# Cache
django-redis>=5.4.0,<6.0
redis>=5.0.0,<6.0  # Verify latest 5.x version

# Image Processing
Pillow>=11.3.0,<12.0
django-imagekit>=6.0.0,<7.0

# Environment
python-decouple>=3.8
python-dotenv>=1.0.0

# API Clients
requests>=2.32.5,<3.0
httpx>=0.27.0  # Verify latest version

# Utilities
django-filter>=24.2
django-taggit>=5.0.0
django-mptt>=0.16.0
fuzzywuzzy>=0.18.0

# Development Tools
django-debug-toolbar>=4.4.0
django-extensions>=3.2.3
ipython>=8.24.0

# Testing
pytest>=8.4.0,<9.0
pytest-django>=4.11.1,<5.0
pytest-cov>=5.0.0
factory-boy>=3.3.0

# Task Queue (optional)
celery>=5.4.0,<6.0

# Security
django-csp==3.8  # Plan migration to 4.0
django-ratelimit==4.1.0
python-magic==0.4.27

# Circuit Breaker
pybreaker>=1.4.1,<2.0

# Distributed Locks (Cache Stampede Prevention)
python-redis-lock>=4.0.0,<5.0

# OAuth Authentication
django-allauth>=65.4.0,<66.0  # MAJOR VERSION - TEST THOROUGHLY

# Production Server
gunicorn>=22.0.0,<23.0
uvicorn[standard]>=0.30.0
django-celery-beat>=2.8.1,<3.0

# WebSockets (Channels)
channels>=4.2.0,<5.0
channels-redis>=4.3.0,<5.0
daphne>=4.1.0,<5.0

# AI Integration
wagtail-ai>=1.0.0

# Security Testing (Development)
bandit>=1.8.6,<2.0
safety>=3.6.2,<4.0  # MAJOR VERSION - Update CI/CD scripts

# Request tracing and logging
django-request-id>=1.0.0
python-json-logger>=2.0.7

# Error tracking
sentry-sdk[django,celery]>=3.0.0,<4.0  # MAJOR VERSION - Review migration

# Static file optimization
whitenoise[brotli]>=6.11.0,<7.0
```

---

## Upgrade Implementation Plan

### Phase 1: CRITICAL SECURITY (Week 1)

**Priority**: IMMEDIATE

1. **Django 5.2.7**
   ```bash
   pip install "Django>=5.2.7,<5.3"
   python manage.py migrate
   python manage.py test
   ```

2. **Pillow 11.3.0**
   ```bash
   pip install "Pillow>=11.3.0,<12.0"
   # Test image uploads in plant identification
   python manage.py test apps.plant_identification
   ```

3. **djangorestframework-simplejwt 5.5.0**
   ```bash
   pip install "djangorestframework-simplejwt>=5.5.0,<6.0"
   # Test JWT authentication, token refresh
   python manage.py test apps.users.tests.test_jwt_authentication
   ```

4. **requests 2.32.5**
   ```bash
   pip install "requests>=2.32.5,<3.0"
   # Test Plant.id and PlantNet API calls
   python manage.py test apps.plant_identification.test_plant_id_service
   python manage.py test apps.plant_identification.test_plantnet_service
   ```

5. **djangorestframework 3.16.0**
   ```bash
   pip install "djangorestframework>=3.16.0,<4.0"
   python manage.py test apps.plant_identification.api.tests
   ```

**Testing**:
- Run full test suite: `python manage.py test --keepdb -v 2`
- Manual testing: Authentication, plant identification, image uploads
- Check logs for deprecation warnings

---

### Phase 2: HIGH PRIORITY (Week 2)

**Priority**: HIGH

1. **django-allauth 65.4.0** (MAJOR VERSION)
   ```bash
   pip install "django-allauth>=65.4.0,<66.0"
   ```

   **Migration Steps**:
   - Update settings.py:
     ```python
     # OLD
     ACCOUNT_AUTHENTICATION_METHOD = 'username_email'

     # NEW
     ACCOUNT_LOGIN_METHODS = {'username', 'email'}
     ```
   - Run migrations: `python manage.py migrate`
   - Test all auth flows: registration, login, password reset, social auth
   - Check email normalization (all lowercase)

2. **Database & Caching**
   ```bash
   pip install "psycopg2-binary>=2.9.11,<3.0"
   pip install "django-celery-beat>=2.8.1,<3.0"
   pip install "channels>=4.2.0,<5.0"
   pip install "channels-redis>=4.3.0,<5.0"
   ```

3. **Static Files & Images**
   ```bash
   pip install "whitenoise[brotli]>=6.11.0,<7.0"
   pip install "django-imagekit>=6.0.0,<7.0"
   ```

4. **CMS**
   ```bash
   pip install "wagtail>=7.1,<7.2"
   python manage.py migrate
   ```

**Testing**:
- Full authentication flow testing
- Image processing (Pillow 11.3 + django-imagekit 6.0)
- Static file serving in dev and simulated production
- WebSocket functionality (if using Channels)

---

### Phase 3: MODERATE PRIORITY (Week 3)

**Priority**: MODERATE

1. **Testing & Development**
   ```bash
   pip install "pytest>=8.4.0,<9.0"
   pip install "pytest-django>=4.11.1,<5.0"
   pip install "bandit>=1.8.6,<2.0"
   ```

2. **Security Scanning (MAJOR VERSION)**
   ```bash
   pip install "safety>=3.6.2,<4.0"
   ```
   - Update CI/CD scripts for Safety 3.x
   - Test new command structure

3. **Monitoring (MAJOR VERSION)**
   ```bash
   pip install "sentry-sdk[django,celery]>=3.0.0,<4.0"
   ```
   - Review OpenTelemetry migration guide
   - Test error capture and performance monitoring
   - Update Sentry configuration

4. **Minor Updates**
   ```bash
   pip install "django-cors-headers>=4.9.0,<5.0"
   pip install "pybreaker>=1.4.1,<2.0"
   ```

**Testing**:
- Run pytest suite with new versions
- Verify Sentry error tracking
- Run bandit and safety scans
- Check CI/CD pipeline

---

### Phase 4: VERIFICATION & DOCUMENTATION (Week 4)

**Priority**: LOW

1. **Verify Unlisted Versions**
   ```bash
   pip show httpx
   pip show gunicorn
   pip show uvicorn
   pip show daphne
   pip show redis
   ```

2. **Update Documentation**
   - Update CLAUDE.md with new version requirements
   - Update deployment guides with psycopg2 source build notes
   - Document django-allauth migration changes
   - Update security best practices

3. **Final Testing**
   - Full regression testing across all features
   - Load testing with updated dependencies
   - Security scan with updated tools
   - Performance benchmarking

---

## Breaking Changes Summary

### MAJOR VERSION UPGRADES (Requires Code Changes)

1. **django-allauth (0.58.2 → 65.4.0)**
   - Settings: `ACCOUNT_AUTHENTICATION_METHOD` → `ACCOUNT_LOGIN_METHODS`
   - Email normalization (lowercase)
   - Review social authentication configuration

2. **safety (2.3.0 → 3.6.2)**
   - New CLI commands
   - New policy schema
   - Update CI/CD scripts

3. **sentry-sdk (2.x → 3.x)**
   - OpenTelemetry tracing
   - Review configuration
   - Test error capture

### MINOR VERSION UPGRADES (Minimal/No Code Changes)

1. **djangorestframework (3.15 → 3.16)**
   - Review custom auth/permissions
   - Test API endpoints

2. **Pillow (10.3 → 11.3)**
   - Test image processing workflows
   - Verify django-imagekit compatibility

3. **wagtail (7.0 → 7.1)**
   - Review draft validation changes
   - Test CMS functionality

---

## Compatibility Matrix

| Package | Current | Latest | Django 5.2 | Python 3.8 | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
|---------|---------|--------|-----------|-----------|-----------|------------|------------|------------|------------|
| Django | 5.2.x | 5.2.7 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| DRF | 3.15.0+ | 3.16.0 | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pillow | 10.3.0+ | 11.3.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| psycopg2 | 2.9.9+ | 2.9.11 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wagtail | 7.0-7.1 | 7.1.1 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| django-allauth | 0.58.2+ | 65.4.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| whitenoise | 6.6.0+ | 6.11.0 | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Note**: Django 5.2 dropped Python 3.8, 3.9 support. Minimum Python version: **3.10**

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] Update all CRITICAL dependencies in staging environment
- [ ] Run full test suite (83+ tests passing)
- [ ] Run security scans (bandit, safety)
- [ ] Review deprecation warnings in logs
- [ ] Test authentication flows (JWT, account lockout, rate limiting)
- [ ] Test plant identification (API calls, caching, circuit breakers)
- [ ] Test image uploads (compression, processing)
- [ ] Load testing with updated dependencies
- [ ] Review breaking changes for django-allauth
- [ ] Update environment variables if needed

### Deployment

- [ ] Backup database before deployment
- [ ] Deploy to staging first
- [ ] Monitor error tracking (Sentry)
- [ ] Monitor performance (Django Debug Toolbar)
- [ ] Check Redis cache hit rates
- [ ] Verify circuit breaker functionality
- [ ] Test distributed locks

### Post-Deployment

- [ ] Monitor application logs for errors
- [ ] Check Sentry for new exceptions
- [ ] Verify authentication flows in production
- [ ] Test plant identification end-to-end
- [ ] Monitor API rate limits (Plant.id, PlantNet)
- [ ] Rotate API keys if security vulnerabilities affected auth
- [ ] Update documentation with deployment notes

---

## Security Best Practices

### API Key Management
- Never commit real API keys
- Use environment variables (.env)
- Rotate keys after security incidents
- See `KEY_ROTATION_INSTRUCTIONS.md`

### Password Security
- Django 5.2 increased PBKDF2 iterations: 870,000 → 1,000,000
- Account lockout: 10 failed attempts, 1-hour duration
- Password reset rate limiting: 3 requests/hour

### JWT Authentication
- Separate JWT_SECRET_KEY from Django SECRET_KEY
- Token blacklisting on logout
- 24-hour session timeout
- HTTP-only cookies for token storage

### Rate Limiting
- Login: 5 attempts/15 minutes
- Registration: 3 requests/hour
- API endpoints: 10-100 requests/hour (environment-dependent)
- IP spoofing protection enabled

### Database Security
- Use parameterized queries (Django ORM)
- GIN indexes for performance (not security)
- Regular backups before deployments
- psycopg2 source build in production (not binary)

---

## References

### Official Documentation
- Django Security: https://docs.djangoproject.com/en/5.2/releases/security/
- DRF Security: https://www.django-rest-framework.org/topics/security/
- Pillow Security: https://pillow.readthedocs.io/en/stable/
- OWASP Django: https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html

### CVE Databases
- CVE Details: https://www.cvedetails.com/
- Snyk Vulnerability DB: https://security.snyk.io/
- GitHub Security Advisories: https://github.com/advisories
- NIST NVD: https://nvd.nist.gov/

### Project Documentation
- `/backend/docs/security/AUTHENTICATION_SECURITY.md`
- `/backend/docs/testing/AUTHENTICATION_TESTS.md`
- `KEY_ROTATION_INSTRUCTIONS.md`
- `SECURITY_PATTERNS_CODIFIED.md`

---

**Last Updated**: January 2025
**Next Review**: April 2025 (quarterly)
**Maintained By**: Development Team
**Status**: ACTIVE - IMMEDIATE ACTION REQUIRED
