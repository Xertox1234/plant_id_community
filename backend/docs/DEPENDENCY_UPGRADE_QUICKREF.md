# Dependency Upgrade Quick Reference - January 2025

**CRITICAL SECURITY UPDATES - IMMEDIATE ACTION REQUIRED**

## Quick Commands for Critical Updates

```bash
# Navigate to backend directory
cd /Users/williamtower/projects/plant_id_community/backend
source venv/bin/activate

# PHASE 1: CRITICAL SECURITY (Week 1)
pip install "Django>=5.2.7,<5.3"
pip install "Pillow>=11.3.0,<12.0"
pip install "djangorestframework-simplejwt>=5.5.0,<6.0"
pip install "djangorestframework>=3.16.0,<4.0"
pip install "requests>=2.32.5,<3.0"

# Test critical functionality
python manage.py migrate
python manage.py test apps.users.tests --keepdb -v 2
python manage.py test apps.plant_identification --keepdb -v 2

# PHASE 2: HIGH PRIORITY (Week 2)
pip install "django-allauth>=65.4.0,<66.0"  # BREAKING CHANGES - See migration notes below
pip install "psycopg2-binary>=2.9.11,<3.0"
pip install "django-celery-beat>=2.8.1,<3.0"
pip install "channels>=4.2.0,<5.0"
pip install "channels-redis>=4.3.0,<5.0"
pip install "whitenoise[brotli]>=6.11.0,<7.0"
pip install "django-imagekit>=6.0.0,<7.0"
pip install "wagtail>=7.1,<7.2"

# Test everything
python manage.py test --keepdb -v 2

# PHASE 3: MODERATE PRIORITY (Week 3)
pip install "pytest>=8.4.0,<9.0"
pip install "pytest-django>=4.11.1,<5.0"
pip install "bandit>=1.8.6,<2.0"
pip install "safety>=3.6.2,<4.0"  # BREAKING CHANGES - Update CI/CD scripts
pip install "sentry-sdk[django,celery]>=3.0.0,<4.0"  # BREAKING CHANGES - Review migration
pip install "django-cors-headers>=4.9.0,<5.0"
pip install "pybreaker>=1.4.1,<2.0"

# Regenerate requirements.txt
pip freeze > requirements.txt
```

---

## Critical Security Vulnerabilities Fixed

### 1. Django 5.2.7 (SQL Injection - HIGH)
- **CVE**: Multiple SQL injection vulnerabilities in QuerySet methods (MySQL/MariaDB)
- **Severity**: HIGH
- **Impact**: Database compromise
- **Action**: Update immediately

### 2. Pillow 11.3.0 (RCE + Heap Overflow)
- **CVE-2023-50447**: Arbitrary code execution via PIL.ImageMath.eval()
- **CVE-2025-48379**: Heap buffer overflow in DDS image handling
- **Severity**: CRITICAL / HIGH
- **Impact**: Remote code execution, system compromise
- **Action**: Update immediately, test image uploads

### 3. djangorestframework-simplejwt 5.5.0 (Information Disclosure)
- **CVE-2024-22513**: Disabled users can access resources
- **Severity**: MODERATE
- **Impact**: Authorization bypass, account lockout ineffective
- **Action**: Update immediately (critical for Week 4 auth security)

### 4. requests 2.32.5 (Credential Exposure)
- **CVE-2024-47081**: Credential exposure via malicious URLs
- **CVE-2024-35195**: SSL certificate bypass
- **CVE-2023-32681**: Proxy credential leakage
- **Severity**: MODERATE/HIGH
- **Impact**: API key exposure, man-in-the-middle attacks
- **Action**: Update immediately, consider rotating Plant.id/PlantNet keys

### 5. django-allauth 65.4.0 (XSS + Rate Limiting)
- **Multiple vulnerabilities**: XSS, rate limiting bypass, token exposure, TOTP reuse
- **Severity**: MODERATE
- **Impact**: Authentication bypass, session hijacking
- **Action**: Plan migration (breaking changes)

---

## Breaking Changes - Action Required

### django-allauth 0.58.2 → 65.4.0

**Settings Migration**:
```python
# OLD (Remove from settings.py)
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'

# NEW (Add to settings.py)
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
```

**Post-Upgrade**:
- Run migrations: `python manage.py migrate`
- Test registration, login, password reset
- Verify social authentication (if using OAuth)
- Check email normalization (all lowercase)

---

### safety 2.3.0 → 3.6.2

**CI/CD Updates Required**:
```bash
# OLD
safety check --json

# NEW (update CI/CD scripts)
safety scan --output json
```

---

### sentry-sdk 2.x → 3.x

**Configuration Review**:
- OpenTelemetry tracing enabled by default
- Review initialization: https://docs.sentry.io/platforms/python/migration/
- Test error capture and performance monitoring

---

## Python Version Compatibility

**IMPORTANT**: Django 5.2 requires Python 3.10+

```bash
# Check current Python version
python --version

# Must be 3.10, 3.11, 3.12, 3.13, or 3.14
# If using 3.8 or 3.9, upgrade Python first
```

---

## Testing Checklist

### After Phase 1 (Critical Security)
- [ ] `python manage.py migrate` (no errors)
- [ ] `python manage.py test apps.users.tests --keepdb -v 2` (all pass)
- [ ] `python manage.py test apps.plant_identification --keepdb -v 2` (all pass)
- [ ] Manual: JWT login/logout
- [ ] Manual: Plant identification with image upload
- [ ] Manual: Account lockout after 10 failed logins
- [ ] Check logs: No deprecation warnings

### After Phase 2 (High Priority)
- [ ] `python manage.py test --keepdb -v 2` (all 83+ tests pass)
- [ ] Manual: User registration
- [ ] Manual: Password reset
- [ ] Manual: Social authentication (if configured)
- [ ] Manual: Image upload with Pillow 11.3 + django-imagekit 6.0
- [ ] Manual: Static file serving with whitenoise 6.11
- [ ] Redis cache: `redis-cli keys "plant_id:*"` (verify caching)
- [ ] Circuit breakers: Check logs for [CIRCUIT] events

### After Phase 3 (Moderate Priority)
- [ ] `pytest` (all tests pass)
- [ ] `bandit -r apps/` (no high-severity issues)
- [ ] `safety scan` (no known vulnerabilities)
- [ ] Sentry test event: Verify error capture
- [ ] Load testing: 100 concurrent plant ID requests
- [ ] Check Sentry performance monitoring

---

## Production Deployment

### Pre-Deployment
```bash
# 1. Backup database
pg_dump plant_community_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Deploy to staging first
git checkout staging
git pull origin main
# (Deploy staging environment)

# 3. Staging smoke tests
curl -X POST https://staging.example.com/api/v1/auth/login/
# (Test all critical endpoints)

# 4. Production deployment
git checkout production
git pull origin main
# (Deploy production)
```

### Post-Deployment Monitoring
```bash
# Check application logs
tail -f logs/django.log | grep "\[ERROR\]"

# Monitor Sentry for new exceptions
# (Check Sentry dashboard)

# Verify Redis cache
redis-cli info stats
redis-cli keys "plant_id:*" | wc -l

# Test critical flows
curl -X POST https://api.example.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'
```

---

## Rollback Plan

If issues occur post-upgrade:

```bash
# 1. Rollback code
git revert <commit_hash>
git push origin main

# 2. Restore database (if migrations ran)
psql plant_community_db < backup_YYYYMMDD_HHMMSS.sql

# 3. Downgrade dependencies
pip install -r requirements.txt.backup

# 4. Restart services
sudo systemctl restart gunicorn
sudo systemctl restart celery
sudo systemctl restart redis
```

---

## Verification Commands

```bash
# Verify installed versions
pip list | grep -E "Django|Pillow|djangorestframework|requests|django-allauth"

# Expected output:
# Django                   5.2.7
# Pillow                   11.3.0
# djangorestframework      3.16.0
# djangorestframework-simplejwt 5.5.0
# django-allauth           65.4.0
# requests                 2.32.5

# Check for security vulnerabilities
safety scan

# Static analysis
bandit -r apps/ -ll

# Type checking
mypy apps/plant_identification/services/

# Run full test suite
python manage.py test --keepdb -v 2 --parallel 4
```

---

## Troubleshooting

### Django migrations fail
```bash
# Check migration status
python manage.py showmigrations

# Fake problematic migration if needed
python manage.py migrate --fake app_name migration_name

# Re-run
python manage.py migrate
```

### Pillow image processing errors
```bash
# Verify Pillow installation
python -c "from PIL import Image; print(Image.__version__)"

# Test image processing
python manage.py shell
>>> from PIL import Image
>>> img = Image.open('test_image.jpg')
>>> img.thumbnail((1200, 1200))
>>> img.save('test_output.jpg')
```

### django-allauth authentication fails
```bash
# Check configuration
python manage.py shell
>>> from django.conf import settings
>>> print(settings.ACCOUNT_LOGIN_METHODS)
# Should be: {'username', 'email'}

# Run migrations
python manage.py migrate allauth

# Clear sessions
python manage.py clearsessions
```

### Redis cache not working
```bash
# Test Redis connection
redis-cli ping
# Should return: PONG

# Test Django cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'ok', 60)
>>> print(cache.get('test'))
# Should return: 'ok'

# Check Redis keys
redis-cli keys "*"
```

---

## Contact & References

**Full Audit Report**: `/backend/docs/DEPENDENCY_SECURITY_AUDIT_2025.md`

**Project Documentation**:
- Architecture: `/backend/docs/README.md`
- Authentication Security: `/backend/docs/security/AUTHENTICATION_SECURITY.md`
- Testing Guide: `/backend/docs/testing/AUTHENTICATION_TESTS.md`
- API Key Rotation: `/KEY_ROTATION_INSTRUCTIONS.md`

**External Resources**:
- Django Security Releases: https://www.djangoproject.com/weblog/
- CVE Details: https://www.cvedetails.com/
- Snyk Vulnerability DB: https://security.snyk.io/

---

**Last Updated**: January 2025
**Status**: IMMEDIATE ACTION REQUIRED - CRITICAL SECURITY UPDATES
