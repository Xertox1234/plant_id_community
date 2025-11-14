# Deployment Security Checklist

> **Version:** 1.0
> **Last Updated:** November 9, 2025
> **Based on:** Comprehensive Code Review Audit (6 specialized agents)

This checklist consolidates all critical security findings from the codebase audit. Use this before **every production deployment** to ensure security best practices are followed.

## 🚨 Critical (P0) - Must Fix Before Deployment

### 1. Firebase API Keys (Issue #142 / #011)

**Status:** [✅] Complete (Resolved November 11, 2025)

**Important Context:** Firebase client API keys are NOT secret - they're designed for client apps. Security is enforced by **Firebase Security Rules**, not key secrecy. The real vulnerability was missing Security Rules.

#### Completed Actions:
- [✅] **Firebase Security Rules deployed** (deny by default, authenticated access only)
- [✅] **flutter_dotenv implemented** for environment-based configuration
- [✅] **Keys moved to .env** (gitignored)
- [✅] **firebase_options.dart updated** to read from environment variables
- [✅] **Security scan passing** (`python scripts/check_flutter_security.py`)

#### Firebase Security Rules (Reference)

**Firestore Rules** - Deny by default, authenticated access only:
```javascript
// Firebase Console → Firestore Database → Rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Default: Deny all access (CRITICAL)
    match /{document=**} {
      allow read, write: if false;
    }

    // User data: Only authenticated users can access their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Plant identifications: Authenticated access only
    match /plant_identifications/{docId} {
      allow read: if request.auth != null;
      allow create: if request.auth != null;
      allow update, delete: if request.auth != null
                            && request.auth.uid == resource.data.userId;
    }

    // Garden data: Owner access only
    match /gardens/{gardenId} {
      allow read, write: if request.auth != null
                         && request.auth.uid == resource.data.userId;
    }
  }
}
```

**Storage Rules** - Authenticated only with 10MB file size limit:
```javascript
// Firebase Console → Storage → Rules
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Default: Deny all access (CRITICAL)
    match /{allPaths=**} {
      allow read, write: if false;
    }

    // User uploads: Authenticated only, 10MB max
    match /users/{userId}/{allPaths=**} {
      allow read: if request.auth != null;
      allow write: if request.auth != null
                  && request.auth.uid == userId
                  && request.resource.size < 10 * 1024 * 1024;  // 10MB
    }

    // Plant images: Authenticated read, owner write
    match /plant_images/{imageId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null;
    }
  }
}
```

#### Maintenance Checklist (Periodic Review):
- [ ] **Audit Firebase activity** monthly (Firebase Console → Analytics → Usage)
- [ ] **Review Security Rules** after schema changes
- [ ] **Monitor quota usage** (check for unusual spikes)
- [ ] **Verify .env exclusion** in .gitignore
- [ ] **Run security scan** before deployments

**Risk Assessment:**
- **Before fix:** CVSS 7.5 (HIGH) - Complete database/storage access by anyone
- **After fix:** CVSS 2.0 (LOW) - Normal Firebase security posture

**Reference:** `P0_FIREBASE_SECURITY_FIX_REPORT.md` (archived), Issue #011 resolved

---

### 2. SQL Injection in Migration (Issue #143)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Fix SQL injection** in `backend/apps/search/migrations/0003_simple_search_vectors.py:31-34`
  - [ ] Replace f-string concatenation with `psycopg2.sql.SQL()` and `sql.Identifier()`
  ```python
  # ❌ Current (vulnerable)
  cursor.execute(f"ALTER TABLE {table} ADD COLUMN ...")

  # ✅ Secure
  from psycopg2 import sql
  cursor.execute(
      sql.SQL("ALTER TABLE {} ADD COLUMN ...").format(
          sql.Identifier(table)
      )
  )
  ```
- [ ] **Review all migrations** for similar patterns
- [ ] **Test migration** on staging database
- [ ] **Add pre-commit hook** to detect SQL injection patterns

**Risk if skipped:** Database compromise, data exfiltration, privilege escalation

**Reference:** `todos/012-pending-p0-sql-injection-migration.md`

---

### 3. CSRF Token Readable by JavaScript (Issue #144)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Change CSRF cookie to HttpOnly** in `backend/plant_community_backend/settings.py:222`
  ```python
  CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access
  ```
- [ ] **Implement meta tag pattern** for CSRF token
  ```html
  <!-- In base template -->
  <meta name="csrf-token" content="{{ csrf_token }}">
  ```
- [ ] **Update frontend** to read from meta tag instead of cookie
  ```typescript
  function getCsrfToken(): string | null {
    return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || null;
  }
  ```
- [ ] **Test all forms** still submit correctly
- [ ] **Verify registration/login** work with HttpOnly cookie

**Risk if skipped:** XSS attacks can steal CSRF tokens, enabling CSRF attacks

**Reference:** `todos/013-pending-p0-csrf-cookie-httponly.md`

---

## ⚠️ High Priority (P1) - Fix Before Production

### 4. Missing Security Headers (Issue #145)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Configure Content-Security-Policy** in `backend/plant_community_backend/settings.py`
  ```python
  SECURE_CONTENT_TYPE_NOSNIFF = True
  X_FRAME_OPTIONS = 'DENY'

  CSP_DEFAULT_SRC = ("'self'",)
  CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
  CSP_IMG_SRC = ("'self'", "data:", "https:")
  CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
  CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
  ```
- [ ] **Add django-csp** to requirements.txt
  ```bash
  pip install django-csp
  ```
- [ ] **Configure middleware** in settings.py
  ```python
  MIDDLEWARE = [
      'csp.middleware.CSPMiddleware',  # Add this
      # ... existing middleware
  ]
  ```
- [ ] **Set Permissions-Policy** header
  ```python
  SECURE_PERMISSIONS_POLICY = {
      'geolocation': [],
      'camera': [],
      'microphone': [],
  }
  ```
- [ ] **Test CSP** doesn't break functionality
  - [ ] Check browser console for CSP violations
  - [ ] Verify all resources load correctly
  - [ ] Test third-party scripts (if any)

**Risk if skipped:** XSS attacks, clickjacking, MIME-type confusion

**Reference:** `todos/014-pending-p1-missing-security-headers.md`

---

### 5. TipTap Memory Leak (Issue #146)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Add cleanup** to `web/src/components/forum/TipTapEditor.tsx:28-55`
  ```tsx
  useEffect(() => {
    if (!editor) return;

    return () => {
      editor.destroy();  // ✅ Cleanup on unmount
    };
  }, [editor]);
  ```
- [ ] **Test editor** in forum post creation
- [ ] **Monitor memory** in Chrome DevTools
  - [ ] Create 10 posts, navigate away
  - [ ] Check memory usage doesn't increase by 50MB+
- [ ] **Verify no warnings** in console

**Risk if skipped:** Browser memory leaks (5-10MB per editor instance), poor UX

**Reference:** `todos/015-pending-p1-tiptap-memory-leak.md`

---

### 6. Moderation Dashboard Performance (Issue #147)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Replace 10 COUNT queries** with single aggregation in `backend/apps/forum/viewsets/moderation_queue_viewset.py`
  ```python
  stats = FlaggedContent.objects.aggregate(
      total_flags=Count('id'),
      pending_count=Count('id', filter=Q(status=MODERATION_STATUS_PENDING)),
      # ... other conditional counts
  )
  ```
- [ ] **Verify cache warming** still works
  ```bash
  python manage.py warm_moderation_cache
  ```
- [ ] **Add performance test** with `assertNumQueries(2)`
- [ ] **Measure improvement** (should be 500ms → 50ms)

**Risk if skipped:** Slow moderation response, 10x query load, scalability issues

**Reference:** `todos/016-pending-p1-moderation-dashboard-performance.md`

---

## 📋 Medium Priority (P2) - Fix Soon

### 7. Registration CSRF Bypass (Issue #148)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Remove @csrf_exempt** from `backend/apps/users/views.py:65-76`
- [ ] **Add CSRF token endpoint** for registration flow
- [ ] **Update frontend** to fetch CSRF token before registration
- [ ] **Test registration** with and without CSRF token
- [ ] **Verify 403** returned without CSRF token

**Reference:** `todos/017-pending-p2-registration-csrf-bypass.md`

---

### 8. JWT Token Lifetime (Issue #149)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Reduce token lifetime** to 15 minutes (OWASP compliant)
  ```python
  SIMPLE_JWT = {
      'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Was 60
  }
  ```
- [ ] **Implement auto-refresh** in frontend (10-minute interval)
- [ ] **Monitor API load** for refresh endpoint
- [ ] **Test token expiration** behavior

**Reference:** `todos/018-pending-p2-jwt-token-lifetime.md`

---

### 9. TypeScript any Types (Issue #150)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Replace 15 `any` types** in `web/src/components/StreamFieldRenderer.tsx`
- [ ] **Create discriminated union types** for StreamField blocks
- [ ] **Run type check:** `npx tsc --noEmit`
- [ ] **Verify zero errors**

**Reference:** `todos/019-pending-p2-typescript-any-types.md`

---

### 10. Missing GIN Index (Issue #151)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Create migration** with GIN indexes for `Post.content_raw`
- [ ] **Test migration** on development
- [ ] **Run EXPLAIN ANALYZE** to verify index usage
- [ ] **Measure performance** (should be <50ms for 100k posts)

**Reference:** `todos/020-pending-p2-post-search-gin-index.md`

---

### 11. Code Duplication - CSRF (Issue #152)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Create `web/src/utils/csrf.ts`** with centralized functions
- [ ] **Update all service files** to import from utils
- [ ] **Remove duplicate implementations**
- [ ] **Add unit tests** for CSRF utilities

---

### 12. Missing AbortController (Issue #153)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Add AbortController** to all fetch calls in useEffect
- [ ] **Verify no warnings** in console
- [ ] **Test navigation** during pending requests

---

### 13. View Count Race Condition (Issue #154)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Replace non-atomic update** with `Thread.objects.filter(pk=pk).update(view_count=F('view_count') + 1)`
- [ ] **Add test** for concurrent increments
- [ ] **Verify accuracy** under load

---

### 14. Account Enumeration (Issue #155)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Return generic error** for duplicate username/email
- [ ] **Add rate limiting** (3 attempts/hour)
- [ ] **Test enumeration** is prevented

---

### 15. Environment Validation (Issue #156)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Complete

- [ ] **Add `validate_environment()`** to settings.py
- [ ] **Validate all critical variables** on startup
- [ ] **Test Redis connection** on startup
- [ ] **Verify server fails** with clear error messages

---

## 🔒 General Security Configuration

### Django Settings (Production)

- [ ] **DEBUG = False**
  ```python
  DEBUG = config('DEBUG', default=False, cast=bool)
  ```
- [ ] **SECRET_KEY is production-grade**
  - [ ] Minimum 50 characters
  - [ ] Generated with: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
  - [ ] NOT containing: `django-insecure`, `change-me`, `test`, `dev`, `local`
- [ ] **ALLOWED_HOSTS configured**
  ```python
  ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())
  # Example: yourdomain.com,www.yourdomain.com
  ```
- [ ] **CORS_ALLOWED_ORIGINS configured**
  ```python
  CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
  # Example: https://yourdomain.com,https://www.yourdomain.com
  ```
- [ ] **SECURE_SSL_REDIRECT = True** (forces HTTPS)
- [ ] **SESSION_COOKIE_SECURE = True**
- [ ] **CSRF_COOKIE_SECURE = True**
- [ ] **SECURE_HSTS_SECONDS = 31536000** (1 year)
- [ ] **SECURE_HSTS_INCLUDE_SUBDOMAINS = True**
- [ ] **SECURE_BROWSER_XSS_FILTER = True**

### Database

- [ ] **PostgreSQL with SSL** connection
  ```python
  DATABASE_URL = "postgres://user:pass@host:5432/db?sslmode=require"
  ```
- [ ] **Database user** has minimum privileges (not superuser)
- [ ] **Backups configured** (daily minimum)
- [ ] **GIN indexes created** for full-text search
  ```bash
  python manage.py migrate
  ```

### Redis Cache

- [ ] **Redis is running**
  ```bash
  redis-cli ping  # Should return "PONG"
  ```
- [ ] **Redis URL configured**
  ```python
  REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/1')
  ```
- [ ] **Redis password** set (if production)
- [ ] **Cache warming** runs on deployment
  ```bash
  python manage.py warm_moderation_cache
  ```

### API Keys

- [ ] **Plant.id API key** is valid (50 characters)
  - [ ] Free tier: 3 identifications/day
  - [ ] Upgrade for production: https://admin.kindwise.com/
- [ ] **PlantNet API key** is valid (optional fallback)
- [ ] **Firebase API keys** rotated (see Issue #142)
- [ ] **All keys** in environment variables (NOT in code)
- [ ] **All keys** excluded from git (.env in .gitignore)

### HTTPS/SSL

- [ ] **SSL certificate** installed and valid
- [ ] **HTTPS redirect** enabled (SECURE_SSL_REDIRECT)
- [ ] **HSTS header** configured (SECURE_HSTS_SECONDS)
- [ ] **Mixed content** warnings resolved
- [ ] **Test SSL:** https://www.ssllabs.com/ssltest/

### Authentication

- [ ] **JWT secret key** is production-grade
  ```python
  JWT_SECRET_KEY = config('JWT_SECRET_KEY')  # Different from SECRET_KEY
  ```
- [ ] **Token lifetime** configured (15 minutes recommended)
- [ ] **Refresh token rotation** enabled
  ```python
  SIMPLE_JWT = {
      'ROTATE_REFRESH_TOKENS': True,
      'BLACKLIST_AFTER_ROTATION': True,
  }
  ```
- [ ] **Account lockout** enabled (5 failed attempts)
- [ ] **Rate limiting** configured
  ```python
  RATE_LIMITS = {
      'auth_endpoints': {
          'login': '5/h',
          'register': '5/h',
      }
  }
  ```

### File Uploads

- [ ] **File size limits** enforced (5MB default)
  ```python
  MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
  ```
- [ ] **File extension validation** (whitelist only)
  ```python
  ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
  ```
- [ ] **MIME type validation** (defense in depth)
  ```python
  ALLOWED_IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  ```
- [ ] **Upload directory** outside web root
- [ ] **Virus scanning** configured (if handling user uploads)

### Logging & Monitoring

- [ ] **PII-safe logging** enabled
  - [ ] No passwords in logs
  - [ ] No API keys in logs
  - [ ] User emails redacted in production
- [ ] **Error tracking** configured (Sentry, etc.)
- [ ] **Performance monitoring** enabled (APM)
- [ ] **Security events** logged
  - [ ] Failed login attempts
  - [ ] Account lockouts
  - [ ] Spam detection triggers
  - [ ] Moderation actions
- [ ] **Log retention** policy configured (90 days minimum)

### Deployment

- [ ] **Static files** collected
  ```bash
  python manage.py collectstatic --noinput
  ```
- [ ] **Database migrations** applied
  ```bash
  python manage.py migrate --noinput
  ```
- [ ] **Cache warmed**
  ```bash
  python manage.py warm_moderation_cache
  ```
- [ ] **Gunicorn/Daphne** configured with workers
  ```bash
  gunicorn plant_community_backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 60
  ```
- [ ] **Process manager** configured (systemd, supervisor)
- [ ] **Health check** endpoint responding
  ```bash
  curl https://yourdomain.com/api/health/
  ```

### Web Frontend

- [ ] **Production build** created
  ```bash
  cd web && npm run build
  ```
- [ ] **TypeScript compilation** passes
  ```bash
  npx tsc --noEmit  # Should show 0 errors
  ```
- [ ] **Environment variables** set
  ```bash
  VITE_API_URL=https://api.yourdomain.com
  ```
- [ ] **CDN configured** for static assets (optional)
- [ ] **Compression enabled** (gzip, brotli)

### Mobile (Flutter)

- [ ] **Firebase production project** configured
- [ ] **Firebase Security Rules** deployed
  ```bash
  firebase deploy --only firestore:rules
  ```
- [ ] **API keys** loaded from environment
  ```dart
  await dotenv.load(fileName: ".env");
  ```
- [ ] **Production build** tested
  ```bash
  flutter build apk --release
  flutter build ios --release
  ```
- [ ] **Security scan** passes
  ```bash
  python scripts/check_flutter_security.py --fail-on-warning
  ```

---

## 📊 Verification Tests

### Security Tests

Run these commands to verify security configuration:

```bash
# 1. Test HTTPS redirect
curl -I http://yourdomain.com
# Should return: 301 Moved Permanently → https://

# 2. Test security headers
curl -I https://yourdomain.com
# Should include:
# - Content-Security-Policy
# - X-Frame-Options: DENY
# - X-Content-Type-Options: nosniff
# - Strict-Transport-Security

# 3. Test CSRF protection
curl -X POST https://yourdomain.com/api/v1/users/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"pass123"}'
# Should return: 403 Forbidden (CSRF token missing)

# 4. Test rate limiting
for i in {1..6}; do
  curl -X POST https://yourdomain.com/api/v1/users/login/ \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
done
# 6th request should return: 429 Too Many Requests

# 5. Test authentication required (production only)
curl https://yourdomain.com/api/v1/plant-identification/identify/
# Should return: 401 Unauthorized (unless DEBUG=True)

# 6. Check for exposed secrets
git log --all --full-history --source -- \
  '**/.*env*' '**/*secret*' '**/*key*' '**/*password*'
# Should return: empty (no secrets in history)

# 7. Test SQL injection (safe query)
curl "https://yourdomain.com/api/v1/forum/search/?q=test%25OR%251=1"
# Should return: escaped query results (no SQL injection)

# 8. Test Redis connection
redis-cli ping
# Should return: PONG
```

### Performance Tests

```bash
# 1. Test moderation dashboard (should be <50ms cached)
curl -w "@curl-format.txt" https://yourdomain.com/api/v1/forum/moderation-queue/
# time_total should be <0.050s (cached)

# 2. Test search with GIN index (should be <50ms for 100k posts)
curl -w "@curl-format.txt" "https://yourdomain.com/api/v1/forum/search/?q=plant"
# time_total should be <0.050s

# curl-format.txt:
# time_total: %{time_total}s\n
```

### Database Tests

```sql
-- 1. Verify GIN indexes exist
\di+ forum_post_content_search_idx
\di+ forum_post_content_trgm_idx

-- 2. Test index usage
EXPLAIN ANALYZE
SELECT * FROM forum_post
WHERE to_tsvector('english', content_raw) @@ to_tsquery('english', 'plant');
-- Should show: Bitmap Index Scan on forum_post_content_search_idx

-- 3. Check database user privileges
\du
-- Your app user should NOT be superuser
```

---

## 🎯 Final Checklist

Before going live, verify:

- [ ] All **P0 Critical** issues resolved (3 items)
- [ ] All **P1 High** issues resolved (3 items)
- [ ] **Security headers** configured and tested
- [ ] **HTTPS** enforced (no mixed content)
- [ ] **Environment variables** validated
- [ ] **Database migrations** applied
- [ ] **Redis cache** working
- [ ] **Static files** served correctly
- [ ] **API keys** valid and secret
- [ ] **Error tracking** configured
- [ ] **Backups** configured
- [ ] **Health check** passing
- [ ] **Performance tests** passing (<50ms cached)
- [ ] **Security tests** passing (CSRF, rate limiting, auth)
- [ ] **TypeScript compilation** zero errors
- [ ] **Django tests** passing (232+ tests)
- [ ] **React tests** passing (492 tests)
- [ ] **Documentation** updated

---

## 📚 References

- **Security Audit Report**: Comprehensive code review (November 9, 2025)
- **Todo Files**: `/todos/011-020-pending-*.md` (10 detailed issues)
- **GitHub Issues**: #142-#156 (15 tracking issues)
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **Django Security**: https://docs.djangoproject.com/en/5.2/topics/security/
- **CSP Guide**: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP

---

## 🆘 Emergency Rollback

If critical issues are discovered post-deployment:

1. **Revert deployment** immediately
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Rotate compromised secrets**
   ```bash
   # Generate new SECRET_KEY
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

   # Update in production environment
   heroku config:set SECRET_KEY="new-key-here"
   ```

3. **Check for data breach**
   ```bash
   # Review logs for suspicious activity
   tail -f /var/log/django/security.log | grep "WARN\|ERROR"
   ```

4. **Notify team** via incident response protocol

---

**Last Review:** November 9, 2025
**Next Review:** Before every production deployment
**Contact:** Development team security lead

