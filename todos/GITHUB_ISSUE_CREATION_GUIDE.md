# GitHub Issue Creation Guide for Technical Projects

> Comprehensive guide for converting code audit findings into actionable GitHub issues for Django, React, and Flutter projects.

**Last Updated**: October 27, 2025
**Based on**: Research from Spearbit, GitHub Security Lab, industry best practices

---

## Table of Contents

1. [Overview](#overview)
2. [Issue Template Library](#issue-template-library)
3. [Django-Specific Issues](#django-specific-issues)
4. [React-Specific Issues](#react-specific-issues)
5. [Multi-Platform Issues](#multi-platform-issues)
6. [Security Issues](#security-issues)
7. [Technical Debt Issues](#technical-debt-issues)
8. [Compliance Issues](#compliance-issues)
9. [GitHub Features Best Practices](#github-features-best-practices)
10. [Label System](#label-system)
11. [Workflow Patterns](#workflow-patterns)

---

## Overview

### Purpose

This guide provides battle-tested templates and patterns for creating GitHub issues from code audit findings, optimized for:

- **Django Backend**: Security, performance, type hints, migrations
- **React Frontend**: Components, bundle size, performance, accessibility
- **Flutter Mobile**: Platform-specific issues, state management, offline features
- **Cross-Platform**: API integration, dependencies, compliance

### Philosophy

Good issues are:
- **Actionable**: Clear steps to reproduce and fix
- **Measurable**: Specific acceptance criteria
- **Traceable**: Links to code, docs, related issues
- **Prioritized**: CVSS scores, business impact, effort estimates

---

## Issue Template Library

### 1. Security Vulnerability Template

**Use for**: CVEs, exposed credentials, authentication bypass, XSS, CSRF

```markdown
## Summary

[1-2 sentence description of the vulnerability and its impact]

**CVSS Score**: 7.5 (High) - [Link to CVSS calculator](https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator)

**Severity**: Critical | High | Medium | Low
**Affected Versions**: [e.g., Django 5.2.6, React 18.x]
**Discovered By**: [Agent name, tool, or researcher]

## Product

- **Component**: [e.g., Backend Authentication, Frontend Cookie Handler]
- **File(s)**: `backend/apps/users/views.py:119-145`
- **Function**: `login(request: Request) -> Response`

## Vulnerability Details

### Description

[Detailed explanation of the vulnerability. Point to specific source code.]

**Root Cause**: [Technical explanation of why the vulnerability exists]

**Attack Vector**: [How an attacker could exploit this]

### Proof of Concept

```bash
# Step-by-step reproduction
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password123"}'

# Expected: Rate limiting after 5 attempts
# Actual: No rate limiting, brute force possible
```

**Screenshot**: [If applicable]

## Impact

**Technical Impact**:
- [e.g., Session hijacking, data exfiltration, privilege escalation]

**Business Impact**:
- [e.g., User data breach, compliance violation (GDPR), reputational damage]

**CVSS Vector**: `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`

## Affected Systems

- [ ] Backend (Django)
- [ ] Web Frontend (React)
- [ ] Mobile App (Flutter)
- [ ] Database (PostgreSQL)
- [ ] Infrastructure (Redis, CDN)

## Remediation

### Recommended Fix

```python
# backend/apps/users/views.py
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/15m', method='POST', block=True)
def login(request: Request) -> Response:
    """Rate-limited login endpoint"""
    # Existing login logic
    pass
```

**Pros**: Standard library, battle-tested, minimal overhead
**Cons**: IP-based (can be spoofed without IP validation)

### Alternative Solutions

**Option 2**: Account-based rate limiting
- **Pros**: More accurate, prevents credential stuffing
- **Cons**: Requires authentication check before rate limit

**Option 3**: CAPTCHA after 3 failed attempts
- **Pros**: User-friendly, prevents automated attacks
- **Cons**: UX friction, accessibility concerns

### Validation

```bash
# Test rate limiting
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "wrong"}'
  echo "Attempt $i"
done

# Expected: 5 attempts succeed, 6th returns 429 Too Many Requests
```

## References

- **OWASP**: [Broken Authentication](https://owasp.org/www-project-top-ten/2017/A2_2017-Broken_Authentication)
- **CWE**: [CWE-307: Improper Restriction of Excessive Authentication Attempts](https://cwe.mitre.org/data/definitions/307.html)
- **CVE**: CVE-2024-XXXXX (if applicable)
- **Related Issues**: #123 (IP spoofing protection), #124 (account lockout)

## Acceptance Criteria

- [ ] Rate limiting implemented (5 attempts per 15 minutes per IP)
- [ ] Rate limiting tested with automated script
- [ ] Returns HTTP 429 with `Retry-After` header
- [ ] Logs rate limit violations with `[SECURITY]` prefix
- [ ] Unit tests cover rate limit edge cases
- [ ] Integration tests verify end-to-end behavior
- [ ] Documentation updated (API docs, security policy)
- [ ] Security advisory published (if public vulnerability)

## Timeline

- **Discovery**: 2025-10-25
- **Initial Assessment**: 2025-10-25 (4 hours)
- **Fix Target**: 2025-10-27 (2 days)
- **Verification**: 2025-10-28 (1 day)
- **Public Disclosure**: 2025-11-24 (90 days from discovery)

## Labels

`security`, `vulnerability`, `high-severity`, `backend`, `authentication`, `needs-fix`

---

## Credit

**Discovered By**: security-sentinel agent (Claude Code Review System)
**Reported By**: @yourusername
**Contact**: security@yourproject.com
```

---

### 2. Django Performance Issue Template

**Use for**: Slow queries, N+1 problems, missing indexes, cache misses

```markdown
## Problem

[1-2 sentence description of the performance bottleneck]

**Severity**: Performance degradation - 300ms → 3ms possible (100x improvement)

## Findings

- **Discovered By**: performance-oracle agent
- **Location**: `backend/apps/blog/views.py:45-67`
- **Current Performance**: 300-800ms per request
- **Target Performance**: <50ms per request
- **Impact**: 85% of blog page load time

## Current Implementation

```python
# backend/apps/blog/views.py
def blog_list(request: Request) -> Response:
    # ❌ N+1 query problem
    posts = BlogPost.objects.all()
    for post in posts:
        post.author.name  # Queries database for each post!
        post.category.name  # Another query per post!
    return Response(serialize(posts))
```

**Issues**:
1. No `select_related()` for foreign keys (author, category)
2. No `prefetch_related()` for many-to-many (tags)
3. Missing database index on `published_date` (used in filtering)
4. No caching layer for frequently accessed posts

## Performance Metrics

**Before**:
- **Queries**: 1 + N (author) + N (category) + N (tags) = 1 + 3N queries
- **Time**: 300-800ms for 50 posts (15 queries per post × 50 = 750 queries!)
- **Database Load**: High (750 queries/request)

**After** (with optimizations):
- **Queries**: 3-5 queries (1 main + 2-4 prefetch)
- **Time**: <50ms (cached), ~100ms (cold)
- **Database Load**: Low (5 queries/request)

## Proposed Solutions

### Option 1: Query Optimization + Caching (Recommended)

```python
# backend/apps/blog/views.py
from django.db.models import Prefetch
from django.core.cache import cache

def blog_list(request: Request) -> Response:
    cache_key = "blog:list:recent"
    posts = cache.get(cache_key)

    if posts is None:
        posts = BlogPost.objects.select_related(
            'author',
            'category'
        ).prefetch_related(
            'tags'
        ).order_by('-published_date')[:50]

        # Cache for 15 minutes
        cache.set(cache_key, posts, 900)

    return Response(serialize(posts))
```

**Pros**:
- 100x query reduction (750 → 5 queries)
- <50ms response time (cached)
- Standard Django patterns
- Low risk, well-tested approach

**Cons**:
- Cache invalidation complexity (must bust on post update)
- Memory usage (Redis cache storage)

**Effort**: Medium (4-6 hours with testing and cache invalidation)
**Risk**: Low

### Option 2: Database Indexing Only

```python
# backend/apps/blog/migrations/0012_add_performance_indexes.py
class Migration(migrations.Migration):
    operations = [
        migrations.AddIndex(
            model_name='blogpost',
            index=models.Index(fields=['-published_date'], name='blog_pub_date_idx'),
        ),
        migrations.AddIndex(
            model_name='blogpost',
            index=models.Index(fields=['category', '-published_date'], name='blog_cat_pub_idx'),
        ),
    ]
```

**Pros**:
- 10-20x improvement without caching
- No cache invalidation complexity
- Zero application code changes

**Cons**:
- Still does N+1 queries (need select_related too)
- Slower than Option 1 (100ms vs 50ms)

**Effort**: Small (2 hours)
**Risk**: Low

## Recommended Action

**Implement Option 1** - Query optimization + caching

### Implementation Steps

1. **Add query optimization** (2 hours):
   ```bash
   cd backend
   # Update views.py with select_related/prefetch_related
   # Run tests: python manage.py test apps.blog --keepdb
   ```

2. **Add Redis caching** (2 hours):
   ```bash
   # Install redis: brew install redis (macOS)
   # Update settings.py with CACHES config
   # Add cache.set/cache.get to views
   ```

3. **Add cache invalidation** (2 hours):
   ```bash
   # Create signals.py for post_save/post_delete
   # Bust cache on BlogPost changes
   # Test with: python manage.py test apps.blog.tests.test_blog_cache_service
   ```

4. **Add database indexes** (1 hour):
   ```bash
   # Create migration for indexes
   # Run: python manage.py makemigrations
   # Apply: python manage.py migrate
   ```

5. **Verify performance** (1 hour):
   ```bash
   # Use Django Debug Toolbar to verify query count
   # Benchmark with: python manage.py test_performance
   # Target: <50ms (cached), <100ms (cold), 3-5 queries
   ```

## Technical Details

**Affected Files**:
- `backend/apps/blog/views.py` (query optimization)
- `backend/apps/blog/signals.py` (cache invalidation - NEW)
- `backend/apps/blog/migrations/0012_add_performance_indexes.py` (NEW)
- `backend/apps/blog/tests/test_blog_cache_service.py` (NEW)
- `backend/plant_community_backend/settings.py` (Redis config)

**Database Changes**:
- Add GIN index on `published_date` (PostgreSQL)
- Add composite index on `(category, published_date)`

**Configuration Changes**:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Blog cache timeouts
BLOG_LIST_CACHE_TIMEOUT = 900  # 15 minutes
BLOG_DETAIL_CACHE_TIMEOUT = 3600  # 1 hour
```

## Resources

- **Django Query Optimization**: https://docs.djangoproject.com/en/5.2/topics/db/optimization/
- **Django Caching**: https://docs.djangoproject.com/en/5.2/topics/cache/
- **PostgreSQL Indexes**: https://www.postgresql.org/docs/current/indexes.html
- **Reference Implementation**: `backend/apps/plant_identification/services/plant_id_service.py` (caching example)

## Acceptance Criteria

- [ ] Query count reduced to 3-5 queries (from 750)
- [ ] Response time <50ms (cached), <100ms (cold)
- [ ] Cache invalidation works on post create/update/delete
- [ ] Database indexes created and verified
- [ ] Unit tests pass (18/18 cache service tests)
- [ ] Integration tests verify end-to-end performance
- [ ] Django Debug Toolbar shows query count reduction
- [ ] Performance benchmarks documented

## Performance Benchmarks

### Before
```bash
# Django Debug Toolbar
Queries: 750 queries in 785ms
Cache: 0 hits, 0 misses
```

### After
```bash
# Django Debug Toolbar
Queries: 5 queries in 45ms (cached), 105ms (cold)
Cache: 95% hit rate (40% target exceeded)
```

## Labels

`performance`, `optimization`, `backend`, `django`, `database`, `caching`, `needs-fix`

---

## Work Log

### 2025-10-25 - Code Review Discovery
- Discovered N+1 query problem in blog listing endpoint
- Benchmarked current performance: 300-800ms per request
- Identified missing indexes on published_date
- Calculated potential improvement: 100x (750 → 5 queries)
```

---

### 3. React Performance Issue Template

**Use for**: Bundle size, re-rendering, code splitting, lazy loading

```markdown
## Problem

[1-2 sentence description of the frontend performance issue]

**Severity**: Bundle size bloat - 378 kB → 250 kB possible (34% reduction)

## Findings

- **Discovered By**: frontend-performance-analyst agent
- **Location**: `web/src/components/BlogDetailPage.jsx`
- **Current Bundle Size**: 378.15 kB (gzipped: 119.02 kB)
- **Target Bundle Size**: <250 kB (gzipped: <80 kB)
- **Impact**: 3-5 second load time on 3G networks

## Current Implementation

```javascript
// web/src/components/BlogDetailPage.jsx
import DOMPurify from 'dompurify';  // ❌ 45 kB (entire library)
import moment from 'moment';        // ❌ 72 kB (entire library + locales)
import lodash from 'lodash';        // ❌ 71 kB (entire library)

export default function BlogDetailPage() {
  const sanitized = DOMPurify.sanitize(content);
  const formatted = moment(date).format('MMMM Do, YYYY');
  const unique = lodash.uniq(tags);

  return <div>{sanitized}</div>;
}
```

**Issues**:
1. Importing entire libraries instead of specific functions
2. Moment.js is deprecated and heavy (72 kB)
3. Lodash full import when only using 1 function
4. DOMPurify full import when isomorphic-dompurify would be smaller

## Bundle Analysis

**Before**:
```bash
npm run build

# Bundle size breakdown
dist/assets/index-a1b2c3d4.js    378.15 kB │ gzip: 119.02 kB
  - DOMPurify:                    45 kB
  - Moment.js:                    72 kB
  - Lodash:                       71 kB
  - React:                        42 kB
  - App code:                     148 kB
```

**After** (with optimizations):
```bash
npm run build

# Bundle size breakdown
dist/assets/index-a1b2c3d4.js    250.45 kB │ gzip: 78.12 kB (-34%)
  - isomorphic-dompurify:         12 kB (-33 kB)
  - date-fns:                     8 kB (-64 kB)
  - lodash.uniq:                  2 kB (-69 kB)
  - React:                        42 kB (unchanged)
  - App code:                     148 kB (unchanged)
```

## Proposed Solutions

### Option 1: Library Replacement + Tree Shaking (Recommended)

```javascript
// web/src/components/BlogDetailPage.jsx
import { sanitize } from 'isomorphic-dompurify';  // 12 kB (smaller alternative)
import { format } from 'date-fns';                // 8 kB (tree-shakeable)
import uniq from 'lodash/uniq';                   // 2 kB (specific function)

export default function BlogDetailPage() {
  const sanitized = sanitize(content);
  const formatted = format(new Date(date), 'MMMM do, yyyy');
  const unique = uniq(tags);

  return <div>{sanitized}</div>;
}
```

**Bundle savings**:
- DOMPurify → isomorphic-dompurify: 45 kB → 12 kB (-33 kB)
- Moment.js → date-fns: 72 kB → 8 kB (-64 kB)
- Lodash → lodash/uniq: 71 kB → 2 kB (-69 kB)
- **Total**: -166 kB (-34% bundle reduction)

**Pros**:
- Massive bundle size reduction
- Modern, maintained libraries
- Better tree-shaking support
- Improved load times (3-5s → 1-2s on 3G)

**Cons**:
- API changes require code updates
- date-fns uses different format tokens than Moment.js
- Requires testing all date formatting

**Effort**: Medium (4-6 hours with testing)
**Risk**: Low (straightforward replacements)

### Option 2: Code Splitting Only

```javascript
// web/src/components/BlogDetailPage.jsx
import { lazy, Suspense } from 'react';

const DOMPurify = lazy(() => import('dompurify'));

export default function BlogDetailPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <BlogContent />
    </Suspense>
  );
}
```

**Pros**:
- Defers heavy library loading
- Smaller initial bundle
- No API changes

**Cons**:
- Still loads heavy libraries (eventually)
- Adds loading states (UX complexity)
- Only helps initial load, not total bundle size

**Effort**: Small (2 hours)
**Risk**: Low

## Recommended Action

**Implement Option 1** - Library replacement + tree shaking

### Implementation Steps

1. **Replace Moment.js with date-fns** (2 hours):
   ```bash
   npm uninstall moment
   npm install date-fns

   # Update all date formatting calls
   # Moment.js: moment(date).format('MMMM Do, YYYY')
   # date-fns:  format(new Date(date), 'MMMM do, yyyy')
   ```

2. **Replace Lodash with specific imports** (1 hour):
   ```bash
   # No uninstall needed, just update imports
   # Before: import lodash from 'lodash'
   # After:  import uniq from 'lodash/uniq'
   ```

3. **Replace DOMPurify with isomorphic-dompurify** (2 hours):
   ```bash
   npm uninstall dompurify
   npm install isomorphic-dompurify

   # Update imports
   # Before: import DOMPurify from 'dompurify'
   # After:  import { sanitize } from 'isomorphic-dompurify'
   ```

4. **Verify bundle size** (1 hour):
   ```bash
   npm run build
   # Check dist/ output for size reduction
   # Target: <250 kB (gzipped: <80 kB)

   # Analyze bundle composition
   npm run build -- --stats
   npx vite-bundle-visualizer
   ```

5. **Test functionality** (2 hours):
   ```bash
   npm run test
   npm run test:e2e
   # Verify date formatting displays correctly
   # Verify XSS protection still works (sanitize)
   # Verify all lodash functions replaced correctly
   ```

## Technical Details

**Affected Files**:
- `web/src/components/BlogDetailPage.jsx` (primary)
- `web/src/components/BlogCard.jsx` (date formatting)
- `web/src/utils/formatDate.js` (date utility)
- `web/src/utils/sanitize.js` (XSS protection)
- `web/package.json` (dependencies)

**Dependency Changes**:
```json
{
  "dependencies": {
    "dompurify": "^3.0.0",  // REMOVE
    "moment": "^2.29.4",    // REMOVE
    "lodash": "^4.17.21",   // KEEP (for other functions)

    "isomorphic-dompurify": "^2.0.0",  // ADD
    "date-fns": "^3.0.0"               // ADD
  }
}
```

**Configuration Changes**:
```javascript
// vite.config.js
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['react', 'react-dom'],
          'utils': ['date-fns', 'isomorphic-dompurify']
        }
      }
    }
  }
});
```

## Resources

- **Bundlephobia**: https://bundlephobia.com/ (check library sizes before adding)
- **Vite Bundle Visualizer**: https://www.npmjs.com/package/rollup-plugin-visualizer
- **date-fns Migration Guide**: https://date-fns.org/v3.0.0/docs/Moment.js
- **Lodash Individual Packages**: https://lodash.com/per-method-packages

## Acceptance Criteria

- [ ] Bundle size reduced to <250 kB (from 378 kB)
- [ ] Gzipped bundle <80 kB (from 119 kB)
- [ ] All date formatting displays correctly
- [ ] XSS protection still works (sanitize tests pass)
- [ ] All lodash functions replaced and tested
- [ ] Load time improved (3-5s → 1-2s on 3G)
- [ ] ESLint passes with no errors
- [ ] All tests pass (npm run test)
- [ ] Bundle visualizer shows size reduction

## Performance Benchmarks

### Before
```bash
# Lighthouse score
Performance: 72/100
First Contentful Paint: 2.8s
Total Bundle Size: 378 kB (gzipped: 119 kB)
```

### After
```bash
# Lighthouse score
Performance: 89/100 (+17 points)
First Contentful Paint: 1.6s (-1.2s)
Total Bundle Size: 250 kB (gzipped: 78 kB) (-34%)
```

## Labels

`performance`, `optimization`, `frontend`, `react`, `bundle-size`, `needs-fix`

---

## Work Log

### 2025-10-25 - Bundle Analysis
- Ran `npm run build` and analyzed bundle composition
- Identified heavy libraries: Moment.js (72 kB), Lodash (71 kB), DOMPurify (45 kB)
- Researched modern alternatives: date-fns, lodash/uniq, isomorphic-dompurify
- Calculated potential savings: -166 kB (-34% reduction)
```

---

### 4. Type Hints Technical Debt Template

**Use for**: Python type hints, mypy errors, TypeScript types

```markdown
## Problem

[1-2 sentence description of type hint coverage gap]

**Severity**: Type safety gap - 27/28 views lack type hints (3.6% coverage)

## Findings

- **Discovered By**: kieran-python-reviewer agent
- **Location**: `backend/apps/users/views.py`
- **Current Coverage**: 1/28 functions with return type hints (3.6%)
- **Target Coverage**: 28/28 functions (100%)
- **Impact**: No type checking on public API surface

## Current Implementation

```python
# backend/apps/users/views.py

# ❌ No type hints (27 functions like this)
@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def register(request):
    """User registration endpoint"""
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({"user": user.id}, status=201)
    return Response(serializer.errors, status=400)

# ✅ Good example (only 1 function has this)
def current_user(request: Request) -> Response:
    """Get current authenticated user"""
    return Response({"user": request.user.id})
```

**Issues**:
1. No type checking on request parameter (could pass wrong type)
2. No return type annotation (could return wrong type by mistake)
3. Inconsistent with service layer (98% type hint coverage)
4. mypy skips views.py (not in check scope)

## Type Coverage Analysis

**Service Layer** (excellent):
```python
# backend/apps/plant_identification/services/plant_id_service.py
def identify_plant(self, image_file) -> Optional[Dict[str, Any]]:  # ✅
def _call_plant_id_api(self, encoded_image: str) -> Optional[Dict[str, Any]]:  # ✅
def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:  # ✅
```
- **Coverage**: 98-100% on all service methods
- **Benefits**: Catches errors at development time, better IDE support

**Views Layer** (poor):
```python
# backend/apps/users/views.py
def register(request):  # ❌ No type hints
def login(request):  # ❌ No type hints
def logout(request):  # ❌ No type hints
```
- **Coverage**: 3.6% (1/28 functions)
- **Problem**: Public API has NO type safety while internal services do

## Proposed Solutions

### Option 1: Add Type Hints to All Views (Recommended)

```python
# backend/apps/users/views.py
from rest_framework.request import Request
from rest_framework.response import Response
from typing import Optional, Dict, Any

@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def register(request: Request) -> Response:  # ✅ Type safe
    """User registration endpoint"""
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({"user": user.id}, status=201)
    return Response(serializer.errors, status=400)
```

**Type Hint Patterns**:

1. **Simple view** (most common):
   ```python
   def view_name(request: Request) -> Response:
       return Response({"data": ...})
   ```

2. **View with decorators**:
   ```python
   @ratelimit(key='ip', rate='5/15m')
   def view_name(request: Request) -> Response:
       return Response({"data": ...})
   ```

3. **View with multiple return types** (rare):
   ```python
   from typing import Union
   from django.http import HttpResponse

   def view_name(request: Request) -> Union[Response, HttpResponse]:
       if special_case:
           return HttpResponse("text/plain")
       return Response({"data": ...})
   ```

**Pros**:
- Type checking on public API surface
- Catches errors at development time (not runtime)
- IDE autocomplete improvements
- Consistent with service layer standards
- Easier refactoring (type errors highlight breaking changes)

**Cons**:
- Requires 4-6 hours of work (28 functions)
- Must verify all return paths return correct type
- Requires mypy configuration update

**Effort**: Medium (4-6 hours for 28 functions)
**Risk**: Low (mechanical work, established patterns)

### Option 2: Gradual Type Hints

```python
# Add type hints to new/modified functions only
def new_view(request: Request) -> Response:  # ✅ Typed
def old_view(request):  # ❌ Not typed (legacy)
```

**Pros**: Lower initial effort
**Cons**: Inconsistent coverage, defeats purpose
**Verdict**: NOT RECOMMENDED - all-or-nothing for API surface

## Recommended Action

**Implement Option 1** - Add type hints to all 28 view functions

### Implementation Steps

1. **Add imports** (5 minutes):
   ```python
   # backend/apps/users/views.py (top of file)
   from rest_framework.request import Request
   from rest_framework.response import Response
   from typing import Optional, Dict, Any, Union
   ```

2. **Add type hints** (4 hours):
   ```bash
   # Update each function signature
   # Pattern: def view_name(request: Request) -> Response:

   # 28 functions to update:
   # - register (line 66)
   # - login (line 119)
   # - logout (line 252)
   # - refresh_token (line 299)
   # - current_user (line 204)
   # ... (23 more functions)
   ```

3. **Configure mypy** (30 minutes):
   ```toml
   # pyproject.toml
   [[tool.mypy.overrides]]
   module = "apps.users.views"
   disallow_untyped_defs = true  # Enforce type hints
   warn_return_any = true
   strict_optional = true
   ```

4. **Run mypy** (1 hour):
   ```bash
   mypy apps/users/views.py --strict

   # Fix any type errors discovered
   # Common issues:
   # - Missing return type on helper functions
   # - Union types for error responses
   # - Optional parameters need Optional[] annotation
   ```

5. **Verify tests** (30 minutes):
   ```bash
   python manage.py test apps.users --keepdb -v 2
   # Should pass: 18/18 authentication tests
   ```

## Technical Details

**Affected Files**:
- `backend/apps/users/views.py` (1,501 lines - primary change)
- `backend/pyproject.toml` (mypy configuration)
- `backend/apps/users/tests/*.py` (verify tests still pass)

**Functions Requiring Type Hints** (28 total):

| Function | Line | Current | Target |
|----------|------|---------|--------|
| `register` | 66 | `def register(request):` | `def register(request: Request) -> Response:` |
| `login` | 119 | `def login(request):` | `def login(request: Request) -> Response:` |
| `logout` | 252 | `def logout(request):` | `def logout(request: Request) -> Response:` |
| `refresh_token` | 299 | `def refresh_token(request):` | `def refresh_token(request: Request) -> Response:` |
| `current_user` | 204 | ✅ Already typed | ✅ Already typed |
| ... | ... | ... | ... |

**Reference Implementation**:
```python
# backend/apps/plant_identification/services/plant_id_service.py
# Excellent example of type hint coverage (98-100%)

def identify_plant(self, image_file) -> Optional[Dict[str, Any]]:
    """Identify plant from image with caching and circuit breaker."""
    pass

def _call_plant_id_api(self, encoded_image: str) -> Optional[Dict[str, Any]]:
    """Make API call to Plant.id service."""
    pass
```

**Database Changes**: None

**Configuration Changes**:
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Default: allow untyped

[[tool.mypy.overrides]]
module = "apps.users.views"
disallow_untyped_defs = true  # NEW: enforce on views
warn_return_any = true
strict_optional = true
```

## Resources

- **DRF Type Hints Guide**: https://www.django-rest-framework.org/community/3.12-announcement/#improved-type-hints
- **mypy Documentation**: https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html
- **Python Type Hints (PEP 484)**: https://www.python.org/dev/peps/pep-0484/
- **Reference Implementation**: `backend/apps/plant_identification/services/*.py`

## Acceptance Criteria

- [ ] All 28 view functions have type hints
- [ ] `Request` type annotation on all request parameters
- [ ] `Response` return type on all view functions
- [ ] mypy passes with `--strict` mode on views.py
- [ ] No new type errors introduced
- [ ] All 18/18 authentication tests still pass
- [ ] IDE autocomplete works correctly
- [ ] pyproject.toml enforces type hints on views module

## Type Coverage Report

### Before
```bash
mypy apps/users/views.py --strict
# Result: 85 errors (mostly missing return types)
# Coverage: 3.6% (1/28 functions)
```

### After
```bash
mypy apps/users/views.py --strict
# Result: Success: no issues found in 1 source file
# Coverage: 100% (28/28 functions)
```

## Labels

`technical-debt`, `type-hints`, `code-quality`, `backend`, `python`, `needs-fix`

---

## Work Log

### 2025-10-25 - Type Coverage Analysis
- Audited all view functions in apps/users/views.py
- Found 27/28 functions without return type hints
- Compared to service layer (98-100% coverage) - significant gap
- Identified as CRITICAL due to public API surface importance
```

---

## Django-Specific Issues

### Migration Safety

```markdown
## Problem

Database migration creates index without checking database vendor, will fail on SQLite (development).

## Findings

- **Location**: `backend/apps/blog/migrations/0013_add_search_gin_indexes.py:12`
- **Issue**: GIN index creation without PostgreSQL vendor check

## Proposed Solution

```python
# backend/apps/blog/migrations/0013_add_search_gin_indexes.py
from django.db import migrations, connection

class Migration(migrations.Migration):
    dependencies = [('blog', '0012_previous_migration')]

    def add_gin_indexes(apps, schema_editor):
        # Only run on PostgreSQL
        if connection.vendor == 'postgresql':
            schema_editor.execute("""
                CREATE INDEX blog_post_search_idx
                ON blog_blogpost
                USING GIN(to_tsvector('english', title || ' ' || content));
            """)

    operations = [
        migrations.RunPython(add_gin_indexes, reverse_code=migrations.RunPython.noop)
    ]
```

## Acceptance Criteria

- [ ] Migration runs successfully on PostgreSQL (production)
- [ ] Migration skips gracefully on SQLite (development)
- [ ] Tests pass on both databases
```

---

## React-Specific Issues

### Component Re-rendering

```markdown
## Problem

BlogCard component re-renders on every parent state change, even when props unchanged.

## Findings

- **Location**: `web/src/components/BlogCard.jsx:15`
- **Issue**: No memoization, heavy computations on every render

## Current Implementation

```javascript
// ❌ Re-renders on every parent change
export default function BlogCard({ post }) {
  const formattedDate = formatDate(post.date);  // Computed every render
  const sanitized = sanitize(post.content);     // Heavy operation!
  return <div>{sanitized}</div>;
}
```

## Proposed Solution

```javascript
import { memo, useMemo } from 'react';

// ✅ Only re-renders when post changes
export default memo(function BlogCard({ post }) {
  const sanitized = useMemo(
    () => sanitize(post.content),
    [post.content]
  );

  return <div>{sanitized}</div>;
});
```

## Acceptance Criteria

- [ ] BlogCard wrapped with React.memo()
- [ ] Heavy computations use useMemo()
- [ ] React DevTools Profiler shows reduced renders
- [ ] All tests pass
```

---

## Multi-Platform Issues

### API Integration Across Platforms

```markdown
## Problem

Django backend requires POST with `image` field, but Flutter app sends `file` field.

## Findings

- **Backend**: `backend/apps/plant_identification/api/serializers.py:25`
- **Web**: `web/src/services/plantIdService.js:45` (works ✅)
- **Mobile**: `plant_community_mobile/lib/services/plant_id_service.dart:67` (broken ❌)

## Affected Platforms

- [ ] Backend (Django) - API contract owner
- [x] Web Frontend (React) - already compliant
- [x] Mobile App (Flutter) - needs fix

## Proposed Solution

**Option 1**: Fix Flutter to match backend contract (recommended)

```dart
// plant_community_mobile/lib/services/plant_id_service.dart
Future<PlantIdentification> identifyPlant(File imageFile) async {
  var request = http.MultipartRequest('POST', Uri.parse('$apiUrl/api/plant-identification/identify/'));
  request.files.add(await http.MultipartFile.fromPath(
    'image',  // ✅ Changed from 'file' to 'image'
    imageFile.path,
  ));

  var response = await request.send();
  return PlantIdentification.fromJson(jsonDecode(response.body));
}
```

**Option 2**: Change backend to accept both `image` and `file` (breaks web)

```python
# backend/apps/plant_identification/api/serializers.py
class PlantIdentificationSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False)  # ❌ Breaks existing web
    file = serializers.ImageField(required=False)

    def validate(self, attrs):
        if not attrs.get('image') and not attrs.get('file'):
            raise ValidationError("Either 'image' or 'file' is required")
        attrs['image'] = attrs.get('image') or attrs.get('file')
        return attrs
```

## Recommended Action

**Option 1** - Fix Flutter to match backend contract

### Cross-Platform Testing Checklist

- [ ] Backend: `python manage.py test apps.plant_identification`
- [ ] Web: `curl -X POST -F "image=@test.jpg" http://localhost:8000/api/plant-identification/identify/`
- [ ] Mobile: `flutter test test/services/plant_id_service_test.dart`

## Labels

`api-integration`, `backend`, `mobile`, `flutter`, `cross-platform`, `needs-fix`
```

---

## Security Issues

### CVSS Scoring Quick Reference

```markdown
| Severity | CVSS Score | Example |
|----------|-----------|---------|
| Critical | 9.0-10.0 | Remote code execution, SQL injection |
| High | 7.0-8.9 | Authentication bypass, sensitive data exposure |
| Medium | 4.0-6.9 | CSRF, weak encryption, XSS (non-persistent) |
| Low | 0.1-3.9 | Information disclosure, weak password policy |
| None | 0.0 | No security impact |

**Calculate CVSS**: https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator
```

### Private Security Advisory Template

```markdown
## 🔒 PRIVATE SECURITY ADVISORY

**DO NOT make this issue public until 90 days after discovery or until patch is released**

## Summary

[Brief description of vulnerability - avoid technical details in title]

**Internal ID**: GHSA-xxxx-xxxx-xxxx
**CVSS Score**: 8.5 (High)
**Embargo Date**: 2025-11-24 (90 days from 2025-10-25)

## Affected Versions

- Django Backend: 5.2.0 - 5.2.6
- React Web: All versions with `authService.js` < v2.0
- Flutter Mobile: Not affected

## Disclosure Timeline

- **2025-10-25**: Vulnerability discovered (internal audit)
- **2025-10-25**: Security team notified
- **2025-10-26**: Patch developed and tested
- **2025-10-27**: Patch deployed to production
- **2025-10-28**: Security advisory published (GitHub Security Advisories)
- **2025-11-24**: Full public disclosure (90 days)

## Private Discussion

[Link to private discussion]

## Labels

`security`, `private`, `high-severity`, `embargo`
```

---

## Technical Debt Issues

### Dead Code Removal

```markdown
## Problem

Unused service methods and imports detected in `combined_identification_service.py`.

## Findings

- **Location**: `backend/apps/plant_identification/services/combined_identification_service.py:145-167`
- **Dead Code**: 3 unused methods (23 lines)
- **Impact**: Code maintenance burden, confusion for developers

## Dead Code Analysis

```python
# DEAD CODE - Never called
def _fallback_to_plantnet(self, image_file):  # Line 145 - NOT USED
    """Fallback to PlantNet if Plant.id fails"""
    # 8 lines of code
    pass

def _merge_partial_results(self, results):  # Line 158 - NOT USED
    """Merge partial results from multiple APIs"""
    # 9 lines of code
    pass

def validate_image_format(self, image_file):  # Line 167 - NOT USED (public method!)
    """Validate image format before API call"""
    # 6 lines of code
    pass
```

**Verification**:
```bash
# Grep for usage across codebase
cd backend
grep -r "_fallback_to_plantnet" apps/
# Result: 0 matches (only definition)

grep -r "_merge_partial_results" apps/
# Result: 0 matches (only definition)

grep -r "validate_image_format" apps/
# Result: 0 matches (only definition)
```

## Proposed Solution

```python
# Remove dead code (3 methods, 23 lines)
# Keep only actively used methods:
# - identify_plant()
# - _call_plant_id_api()
# - _call_plantnet_api()
# - _merge_results()
```

## Impact Analysis

**Before**:
- Lines of code: 245
- Methods: 8 (5 used, 3 unused)
- Complexity: High (unused code paths confuse readers)

**After**:
- Lines of code: 222 (-23 lines, -9%)
- Methods: 5 (5 used, 0 unused)
- Complexity: Lower (clearer code paths)

## Acceptance Criteria

- [ ] Dead methods removed (3 methods, 23 lines)
- [ ] All tests still pass (130+ tests)
- [ ] No grep matches for removed method names
- [ ] Code review confirms no hidden dependencies
- [ ] Git history preserves removed code (can restore if needed)

## Labels

`technical-debt`, `code-cleanup`, `refactoring`, `backend`, `needs-fix`
```

---

## Compliance Issues

### GDPR Data Access Audit Trail

```markdown
## Problem

No audit trail for sensitive data access. Cannot track who viewed user emails or plant identification results.

## Compliance Requirements

- **GDPR Article 30**: Requires "records of processing activities"
- **SOC 2**: Requires audit trails for data access
- **Impact**: Cannot answer "Who accessed user X's data?" for GDPR data subject requests

## Findings

- **Location**: `backend/apps/users/models.py` (User model)
- **Location**: `backend/apps/plant_identification/models.py` (PlantIdentificationResult model)
- **Issue**: No logging for model access (views, queries, exports)

## Proposed Solution

### Option 1: django-auditlog (Recommended)

```python
# backend/settings.py
INSTALLED_APPS += ['auditlog']

# backend/apps/users/models.py
from auditlog.registry import auditlog

class User(AbstractUser):
    # ... existing fields

# Register for audit logging
auditlog.register(User)
auditlog.register(PlantIdentificationResult)
```

**Audit Log Schema**:
```python
AuditLogEntry:
    - timestamp: When was data accessed?
    - user: Who accessed it?
    - action: view | create | update | delete
    - object_id: Which record?
    - changes: What changed? (JSON)
    - ip_address: From where?
```

**Retention Policy**:
- **90 days**: Operational audits (query in Django admin)
- **7 years**: Compliance archives (export to S3 cold storage)

## GDPR Compliance Checklist

- [ ] Audit logging implemented (django-auditlog)
- [ ] User model access logged
- [ ] PlantIdentificationResult access logged
- [ ] Admin panel access tracked
- [ ] Retention policy configured (90 days active, 7 years archived)
- [ ] Data access request procedure documented
- [ ] Privacy policy updated (mention audit logging)

## Resources

- **GDPR Article 30**: https://gdpr-info.eu/art-30-gdpr/
- **django-auditlog**: https://django-auditlog.readthedocs.io/
- **SOC 2 Requirements**: https://www.aicpa.org/soc4so
- **Log Retention**: NIST SP 800-92

## Acceptance Criteria

- [ ] All User model access logged
- [ ] All PlantIdentificationResult queries logged
- [ ] Audit logs queryable by user, date, action type
- [ ] Retention policy configured and automated
- [ ] Performance impact <5% on API endpoints
- [ ] Documentation for GDPR data access requests

## Labels

`compliance`, `gdpr`, `audit-trail`, `security`, `backend`, `needs-implementation`
```

---

## GitHub Features Best Practices

### 1. Task Lists

```markdown
## Implementation Checklist

**Phase 1: Core Changes** (2 days)
- [x] Add circuit breaker to PlantNet service
- [x] Update tests
- [ ] Verify performance improvement

**Phase 2: Documentation** (1 day)
- [ ] Update CLAUDE.md
- [ ] Add monitoring guide
- [ ] Document circuit breaker configuration

**Phase 3: Deployment** (1 day)
- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Deploy to production
```

### 2. Sub-Issues (Hierarchical Tasks)

```markdown
## Parent Issue: UI Modernization (Phase 1-7)

### Sub-Issues:
- #101 Phase 1: Layout Infrastructure
- #102 Phase 2: Responsive Navigation
- #103 Phase 3: Authentication System
- #104 Phase 4: Login/Signup Pages
- #105 Phase 5: Protected Routes
- #106 Phase 7: Design System

**Progress**: 6/6 complete (100%)
```

### 3. Milestones

```markdown
**Milestone**: [Phase 6.3 React Blog Interface](https://github.com/user/repo/milestone/12)

**Due Date**: 2025-10-30
**Progress**: 8/10 issues closed (80%)

**Issues**:
- [x] #110 BlogListPage component
- [x] #111 BlogDetailPage component
- [ ] #112 Comments system (deferred)
- [ ] #113 Social sharing (deferred)
```

### 4. Linked Issues

```markdown
## Related Issues

**Depends On**:
- #005 Verify API Key Rotation (blocker)
- #016 IP Spoofing Protection (blocker)

**Blocks**:
- #024 Audit Trail Implementation

**Related**:
- #012 CORS Debug Mode (same system)
```

### 5. Projects (Kanban Board)

```markdown
**Project**: [Code Audit Remediation](https://github.com/user/repo/projects/5)

**Columns**:
- Backlog: 15 issues
- In Progress: 3 issues
- In Review: 2 issues
- Done: 45 issues

**Filter by**:
- Priority: P1 (5), P2 (8), P3 (7)
- Platform: Backend (12), Frontend (5), Mobile (3)
```

---

## Label System

### Priority Labels

```markdown
priority:critical   # Red - Security vulnerabilities, data loss, service outage
priority:high       # Orange - Major bugs, performance issues, blocking features
priority:medium     # Yellow - Minor bugs, tech debt, nice-to-have features
priority:low        # Blue - Documentation, cleanup, future enhancements
```

### Component Labels

```markdown
backend:django      # Django backend issues
backend:database    # PostgreSQL, migrations, queries
backend:api         # REST API, serializers, endpoints

frontend:react      # React web application
frontend:ui         # UI components, styling
frontend:performance # Bundle size, rendering, lazy loading

mobile:flutter      # Flutter mobile app
mobile:ios          # iOS-specific issues
mobile:android      # Android-specific issues

infrastructure      # Docker, deployment, CI/CD
```

### Type Labels

```markdown
type:bug            # Something isn't working
type:feature        # New feature or request
type:enhancement    # Improvement to existing feature
type:refactor       # Code refactoring (no functional change)
type:documentation  # Documentation improvements
type:testing        # Test coverage, test improvements
```

### Severity Labels (Security)

```markdown
severity:critical   # CVSS 9.0-10.0 (RCE, SQL injection)
severity:high       # CVSS 7.0-8.9 (auth bypass, data exposure)
severity:medium     # CVSS 4.0-6.9 (CSRF, weak crypto)
severity:low        # CVSS 0.1-3.9 (info disclosure)
```

### Status Labels

```markdown
status:needs-triage      # New issue, needs priority/assignment
status:blocked           # Blocked by another issue/dependency
status:in-progress       # Actively being worked on
status:needs-review      # PR created, awaiting code review
status:needs-testing     # Fix implemented, needs verification
status:ready-to-deploy   # Approved and ready for production
```

---

## Workflow Patterns

### 1. Code Audit to GitHub Issues

```bash
# Step 1: Run code audit
claude-code "audit codebase and report back to me"

# Step 2: Review findings (24 todos generated)
cd /Users/williamtower/projects/plant_id_community/todos
ls -la *.md

# Step 3: Convert todos to GitHub issues
# Use templates from this guide

# Step 4: Create milestone
# e.g., "Code Audit Remediation - October 2025"

# Step 5: Add issues to milestone
# Bulk create with gh CLI:
for file in 001-*.md; do
  gh issue create --title "$(head -n 1 $file)" --body-file $file --milestone "Code Audit"
done

# Step 6: Create project board
gh project create --name "Code Audit Remediation" --owner @me

# Step 7: Link issues to project
gh project item-add <project-number> --owner @me --url https://github.com/user/repo/issues/101
```

### 2. Priority Triage Workflow

```markdown
**P1 (Critical)** - Fix within 24-48 hours:
- Security vulnerabilities (exposed keys, auth bypass)
- Data loss bugs
- Service outages
- Blocking issues (prevents deployment)

**P2 (High)** - Fix within 1 week:
- Major bugs (affects many users)
- Performance issues (slow endpoints)
- Missing features (blocks other work)

**P3 (Medium)** - Fix within 2-4 weeks:
- Minor bugs (affects few users)
- Technical debt (code quality)
- Nice-to-have features

**P4 (Low)** - Fix when time allows:
- Documentation improvements
- Code cleanup
- Future enhancements
```

### 3. Security Issue Workflow

```markdown
**Step 1: Private Advisory** (Day 0)
1. Create private security advisory (GitHub Security Advisories)
2. Assign CVE number
3. Calculate CVSS score
4. Notify security team

**Step 2: Patch Development** (Day 0-2)
1. Develop fix in private fork
2. Write tests
3. Review with security team

**Step 3: Deployment** (Day 2-3)
1. Deploy to staging
2. Verify fix
3. Deploy to production

**Step 4: Public Disclosure** (Day 90)
1. Publish security advisory
2. Update CHANGELOG
3. Notify users
```

### 4. Multi-Platform Issue Workflow

```markdown
**Step 1: Create Parent Issue**
Title: "API Integration: Plant Identification"
Body: Describes cross-platform issue

**Step 2: Create Sub-Issues**
- #101 Backend: API endpoint implementation
- #102 Web: React service integration
- #103 Mobile: Flutter service integration

**Step 3: Add Dependencies**
- #102 depends on #101 (backend must be ready)
- #103 depends on #101 (backend must be ready)

**Step 4: Coordinate Testing**
- [ ] Backend: Unit tests
- [ ] Web: Integration tests
- [ ] Mobile: Integration tests
- [ ] E2E: Cross-platform smoke tests
```

---

## Examples from This Project

### Example 1: Circuit Breaker Issue

```markdown
**Title**: Add Circuit Breaker to PlantNet Service

**Labels**: `priority:critical`, `backend:django`, `type:enhancement`, `performance`

**Milestone**: Code Audit Remediation - October 2025

**Body**: [Use "Django Performance Issue Template" above]

**Linked Issues**:
- Related to #012 (CORS Debug Mode)
- Blocks #024 (Audit Trail)
```

### Example 2: Type Hints Issue

```markdown
**Title**: Add Type Hints to Views Layer (28 functions)

**Labels**: `priority:high`, `backend:django`, `type:refactor`, `code-quality`

**Milestone**: Technical Debt - Q4 2025

**Body**: [Use "Type Hints Technical Debt Template" above]

**Sub-Issues**:
- #201 Add type hints to authentication views (8 functions)
- #202 Add type hints to user management views (12 functions)
- #203 Add type hints to plant ID views (8 functions)
```

### Example 3: Security Issue

```markdown
**Title**: 🔒 [PRIVATE] API Key Rotation Verification Required

**Labels**: `security`, `priority:critical`, `backend`, `incident-response`

**Milestone**: Security Remediation - October 2025

**Body**: [Use "Security Vulnerability Template" above]

**Timeline**:
- Oct 23: Keys exposed in git history
- Oct 23: Keys removed from code (commit ba256af)
- Oct 25: Rotation status unknown (this issue)
- Oct 27: Target verification complete
```

---

## Summary

This guide provides comprehensive templates and workflows for converting code audit findings into actionable GitHub issues. Key takeaways:

1. **Use templates** - Consistent structure improves clarity and actionability
2. **Add context** - Link to code, docs, related issues
3. **Be specific** - Concrete acceptance criteria, not vague descriptions
4. **Prioritize ruthlessly** - P1 fixes in 48 hours, P3 can wait weeks
5. **Track dependencies** - Use linked issues, sub-issues, milestones
6. **Measure success** - CVSS scores, performance metrics, test coverage

**Next Steps**:
1. Review existing todos in `/Users/williamtower/projects/plant_id_community/todos/`
2. Convert each todo to GitHub issue using appropriate template
3. Create milestone: "Code Audit Remediation - October 2025"
4. Triage by priority (P1: 5 issues, P2: 8 issues, P3: 11 issues)
5. Create project board with Kanban columns
6. Start with P1 critical issues first

---

**Resources**:
- [GitHub Issues Docs](https://docs.github.com/en/issues)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [CVSS Calculator](https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
