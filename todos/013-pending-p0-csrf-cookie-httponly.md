---
status: pending
priority: p0
issue_id: "013"
tags: [security, critical, csrf, xss, authentication, django]
dependencies: []
---

# CSRF Token Readable by JavaScript (XSS Risk)

## Problem Statement

CSRF cookie has `HttpOnly=False`, allowing JavaScript to read the token. This defeats CSRF protection if an XSS vulnerability is discovered, as attackers can steal the token and perform state-changing requests.

**Location:** `backend/plant_community_backend/settings.py:222`

**CVSS Score:** 6.5 (MEDIUM-HIGH)

## Findings

- Discovered during comprehensive security audit by Security Sentinel agent
- **Current Configuration:**
  ```python
  # settings.py line 222
  CSRF_COOKIE_HTTPONLY = False  # Must be False so JavaScript can read it
  ```

- **Why This Exists:**
  Frontend reads CSRF token from cookies:
  ```typescript
  // web/src/utils/csrf.ts
  function getCsrfToken(): string | null {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
  }
  ```

- **Security Issue:**
  - CSRF token accessible to any JavaScript on the domain ❌
  - **XSS attacks can steal CSRF tokens** and perform authenticated requests ❌
  - Violates defense-in-depth principle ❌
  - Single XSS bypass defeats CSRF protection ❌

- **Current Mitigation:**
  - DOMPurify sanitization in frontend (`web/src/utils/sanitize.ts`) ✅
  - No `dangerouslySetInnerHTML` without sanitization ✅
  - But: Single XSS bypass defeats CSRF protection ❌

## Proposed Solutions

### Option 1: Meta Tag Pattern (RECOMMENDED - Django Standard)

This is the **official Django recommendation** for SPA applications.

**Backend Changes:**
```python
# settings.py
CSRF_COOKIE_HTTPONLY = True  # ✅ SECURE - JavaScript cannot read

# Optional: Add custom middleware to ensure CSRF cookie is set
# (Not needed if using SessionMiddleware)
```

**Template Changes:**
```django
<!-- backend/templates/base.html -->
<!DOCTYPE html>
<html>
<head>
    <meta name="csrf-token" content="{{ csrf_token }}">
    <!-- ... -->
</head>
```

**Frontend Changes:**
```typescript
// web/src/utils/csrf.ts
export function getCsrfToken(): string | null {
    // Read from meta tag instead of cookie
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : null;
}

// No other changes needed - services already use getCsrfToken()
```

**Benefits:**
- Django-standard approach ✅
- CSRF token not accessible to JavaScript ✅
- XSS cannot steal CSRF tokens ✅
- Simple implementation ✅

**Effort:** 2-3 hours (template + frontend + testing)

### Option 2: Double-Submit Cookie Pattern

**Backend Changes:**
```python
# settings.py
CSRF_COOKIE_HTTPONLY = True  # Main token (secure)
CSRF_USE_SESSIONS = False
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'

# Django automatically validates token in header against cookie
```

**Frontend Changes:**
```typescript
// Django DRF automatically reads CSRF token from cookie
// and validates against header - no manual reading needed

// Services just need to ensure credentials: 'include'
fetch(url, {
    credentials: 'include',  // Sends CSRF cookie automatically
    headers: {
        // Django middleware adds X-CSRFToken from cookie
    }
})
```

**Benefits:**
- No JavaScript access to token ✅
- Automatic validation by Django ✅

**Drawbacks:**
- Requires CORS configuration adjustments
- More complex to debug

### Option 3: Separate JS-Readable Cookie (Not Recommended)

```python
# Custom middleware to set separate cookie
class CSRFTokenMiddleware:
    def process_response(self, request, response):
        response.set_cookie(
            'csrf-token-readable',
            get_token(request),
            httponly=False,  # Only this one is readable
            samesite='Strict'
        )
        return response
```

**Drawbacks:**
- Two CSRF tokens to manage
- More complex
- Still vulnerable if XSS steals readable token

## Recommended Action

**Implement Option 1: Meta Tag Pattern (Django Standard)**

**Step 1: Update Backend (15 minutes)**
```python
# backend/plant_community_backend/settings.py
CSRF_COOKIE_HTTPONLY = True  # Change from False
```

**Step 2: Add Meta Tag to Templates (15 minutes)**
```django
<!-- Create if doesn't exist: backend/templates/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token }}">
    <title>Plant ID Community</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/static/js/main.jsx"></script>
</body>
</html>
```

**Step 3: Update Frontend CSRF Utility (15 minutes)**
```typescript
// web/src/utils/csrf.ts
export function getCsrfToken(): string | null {
    // Try meta tag first (new pattern)
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) {
        return meta.getAttribute('content');
    }

    // Fallback to cookie (for backward compatibility during migration)
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
}
```

**Step 4: Update Django View to Serve React App (30 minutes)**
```python
# backend/apps/core/views.py
from django.views.generic import TemplateView
from django.middleware.csrf import get_token

class ReactAppView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure CSRF token is generated
        get_token(self.request)
        return context
```

```python
# backend/plant_community_backend/urls.py
from apps.core.views import ReactAppView

urlpatterns = [
    # API routes first
    path('api/', include('apps.core.urls')),

    # Catch-all for React app (must be last)
    path('', ReactAppView.as_view(), name='react-app'),
]
```

**Step 5: Test (1 hour)**
```bash
# 1. Start Django server
cd backend
python manage.py runserver

# 2. Visit http://localhost:8000/
# 3. Inspect page source - verify <meta name="csrf-token"> exists
# 4. Test login/logout
# 5. Test forum post creation
# 6. Test plant identification
# 7. Verify all CSRF-protected endpoints work
```

## Technical Details

- **Affected Files**:
  - `backend/plant_community_backend/settings.py` (change HTTPONLY)
  - `backend/templates/index.html` (add meta tag)
  - `backend/apps/core/views.py` (add ReactAppView)
  - `backend/plant_community_backend/urls.py` (route to template)
  - `web/src/utils/csrf.ts` (read from meta tag)

- **Related Components**: Authentication, CSRF middleware, React app

- **Dependencies**: None (uses Django built-in features)

- **Performance Impact**: None (meta tag is 50 bytes)

- **Breaking Changes**: None (backward compatible with fallback)

## Resources

- Security Sentinel audit report (November 9, 2025)
- CWE-352: Cross-Site Request Forgery (CSRF)
- CVSS Score: 6.5 (MEDIUM-HIGH)
- Django CSRF Documentation: https://docs.djangoproject.com/en/5.2/ref/csrf/
- Django + React CSRF: https://docs.djangoproject.com/en/5.2/howto/csrf/#ajax
- OWASP CSRF Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

## Acceptance Criteria

- [ ] `CSRF_COOKIE_HTTPONLY = True` in settings.py
- [ ] Meta tag `<meta name="csrf-token">` in base template
- [ ] Frontend reads token from meta tag
- [ ] Fallback to cookie for backward compatibility
- [ ] All CSRF-protected endpoints tested
- [ ] Login/logout flow works
- [ ] Forum post creation works
- [ ] Plant identification works
- [ ] JavaScript cannot read CSRF cookie (verify in DevTools)
- [ ] Tests pass
- [ ] Documentation updated

## Work Log

### 2025-11-09 - Security Audit Discovery
**By:** Claude Code Review System (Security Sentinel Agent)
**Actions:**
- Discovered during comprehensive codebase audit
- Identified as CRITICAL (P0) - Weakens CSRF protection
- CVSS 6.5 - XSS can bypass CSRF protection
- Violates defense-in-depth principle

**Learnings:**
- `HttpOnly=False` allows JavaScript to read cookie
- XSS + readable CSRF token = full CSRF bypass
- Meta tag pattern is Django-recommended for SPAs
- Defense in depth: HttpOnly cookie + XSS prevention
- Current XSS protection (DOMPurify) is good but not perfect

**Next Steps:**
- Implement meta tag pattern
- Update frontend to read from meta tag
- Test all CSRF-protected endpoints
- Document pattern in CLAUDE.md

## Notes

**Why Meta Tag Pattern?**
- **Official Django recommendation** for SPA applications
- Balances security and functionality
- CSRF token needed by frontend but not accessible to scripts
- Meta tags are read-once on page load (not persistent like cookies)

**Defense in Depth:**
This fix is part of a multi-layer security approach:
1. CSRF token validation (Django middleware)
2. HttpOnly cookie (prevents JS access) ← **This fix**
3. XSS prevention (DOMPurify sanitization) ← Already implemented
4. SameSite cookies (prevents cross-site attacks) ← Already implemented

**Priority Justification:**
- P0 because it's a defense-in-depth gap
- Not immediately exploitable (requires XSS first)
- But XSS vulnerabilities are common in web apps
- Fixing this makes XSS exploitation much harder

Source: Comprehensive security audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Security Sentinel
