---
status: pending
priority: p1
issue_id: "014"
tags: [security, headers, csp, xss, clickjacking, django]
dependencies: []
---

# Missing Security Headers (CSP, X-Frame-Options, Permissions-Policy)

## Problem Statement

Content Security Policy (CSP) middleware is installed but not configured, and several important security headers are missing, leaving the application vulnerable to XSS, clickjacking, and other attacks.

**Location:** `backend/plant_community_backend/settings.py` (missing CSP directives)

**CVSS Score:** 5.3 (MEDIUM)

## Findings

- Discovered during comprehensive security audit by Security Sentinel agent
- **Current State:**
  ```python
  MIDDLEWARE = [
      # ...
      'csp.middleware.CSPMiddleware',  # ✅ Installed but not configured
  ]

  # ❌ Missing: No CSP directives configured
  # ❌ Missing: X-Frame-Options not explicitly set
  # ❌ Missing: Permissions-Policy not configured
  ```

- **Missing Protections:**
  1. **No Content Security Policy** - Allows any scripts, styles, images from any domain
  2. **No X-Frame-Options** - Application can be embedded in iframes (clickjacking risk)
  3. **No Permissions-Policy** - No restrictions on browser features (geolocation, camera, etc.)

- **Impact:**
  - XSS attacks easier to exploit (can load scripts from attacker domains)
  - Clickjacking attacks possible (embed site in malicious iframe)
  - Data exfiltration via unauthorized domains
  - No mixed content protection (HTTP resources on HTTPS)

## Proposed Solutions

### Solution: Configure Comprehensive Security Headers

**Step 1: Content Security Policy (CSP)**

```python
# backend/plant_community_backend/settings.py

# Content Security Policy
CSP_DEFAULT_SRC = ["'self'"]

CSP_SCRIPT_SRC = [
    "'self'",
    "'unsafe-inline'",  # Required for React inline scripts
    "https://cdn.jsdelivr.net",  # External scripts (if needed)
]

CSP_STYLE_SRC = [
    "'self'",
    "'unsafe-inline'",  # Required for Tailwind CSS
]

CSP_IMG_SRC = [
    "'self'",
    "data:",  # Allow data URIs for images
    "https:",  # Allow all HTTPS images (plant photos from external sources)
]

CSP_FONT_SRC = [
    "'self'",
    "data:",  # Allow data URIs for fonts
]

CSP_CONNECT_SRC = [
    "'self'",
    "https://api.plant.id",  # External Plant.id API
    "https://my-api.plantnet.org",  # External PlantNet API
]

CSP_FRAME_ANCESTORS = ["'none'"]  # Prevent embedding (anti-clickjacking)
CSP_BASE_URI = ["'self'"]
CSP_FORM_ACTION = ["'self'"]

# Force HTTPS for all resources in production
CSP_UPGRADE_INSECURE_REQUESTS = not DEBUG  # True in production

# Report violations (for monitoring)
CSP_REPORT_URI = '/api/v1/security/csp-report/' if not DEBUG else None
```

**Step 2: Additional Security Headers**

```python
# X-Frame-Options (anti-clickjacking)
X_FRAME_OPTIONS = 'DENY'  # Prevent embedding in any iframe

# Permissions Policy (browser feature restrictions)
PERMISSIONS_POLICY = {
    "geolocation": [],  # Deny geolocation
    "microphone": [],  # Deny microphone
    "camera": ["'self'"],  # Allow camera only for plant photos
    "payment": [],  # Deny payment API
    "usb": [],  # Deny USB access
}
```

**Step 3: Already Configured (Verify)**

```python
# These should already exist - verify they're set correctly
SECURE_BROWSER_XSS_FILTER = True  # ✅ Already set
SECURE_CONTENT_TYPE_NOSNIFF = True  # ✅ Already set
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'  # ✅ Already set
SECURE_SSL_REDIRECT = not DEBUG  # ✅ Already set
```

**Step 4: Create CSP Violation Report Endpoint**

```python
# backend/apps/core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt  # CSP reports are POST from browser, no CSRF token
def csp_report(request):
    """Receive and log CSP violation reports."""
    try:
        report = request.data.get('csp-report', {})

        logger.warning(
            f"[CSP] Violation detected",
            extra={
                'document_uri': report.get('document-uri'),
                'violated_directive': report.get('violated-directive'),
                'blocked_uri': report.get('blocked-uri'),
                'source_file': report.get('source-file'),
                'line_number': report.get('line-number'),
            }
        )

        # Could store in database for analysis
        # CSPViolation.objects.create(...)

        return Response(status=204)  # No content

    except Exception as e:
        logger.error(f"[CSP] Report parsing error: {e}")
        return Response(status=400)
```

```python
# backend/plant_community_backend/urls.py
urlpatterns = [
    # ...
    path('api/v1/security/csp-report/', csp_report, name='csp-report'),
]
```

## Recommended Action

**Phase 1: Basic Headers (1-2 hours)**
1. ✅ Configure CSP directives in settings.py
2. ✅ Set X-Frame-Options = 'DENY'
3. ✅ Configure Permissions-Policy
4. ✅ Test application (verify no broken functionality)

**Phase 2: CSP Reporting (1 hour)**
5. ✅ Create CSP violation report endpoint
6. ✅ Test CSP violations are logged
7. ✅ Monitor for unexpected violations

**Phase 3: Refinement (ongoing)**
8. ✅ Review CSP violation logs
9. ✅ Tighten CSP rules based on actual usage
10. ✅ Remove 'unsafe-inline' if possible (requires build changes)

## Technical Details

- **Affected Files**:
  - `backend/plant_community_backend/settings.py` (add CSP directives)
  - `backend/apps/core/views.py` (create CSP report endpoint)
  - `backend/plant_community_backend/urls.py` (add CSP report route)

- **Related Components**: Security middleware, Django settings

- **Dependencies**: django-csp (already installed)

- **Testing Required**:
  ```bash
  # Verify headers are sent
  curl -I http://localhost:8000/api/v1/plant-identification/identify/

  # Should include:
  # Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...
  # X-Frame-Options: DENY
  # X-Content-Type-Options: nosniff
  # Permissions-Policy: geolocation=(), microphone=(), camera=(self)
  ```

- **Performance Impact**: Negligible (~100 bytes of headers per response)

## Resources

- Security Sentinel audit report (November 9, 2025)
- CWE-693: Protection Mechanism Failure
- CVSS Score: 5.3 (MEDIUM)
- CSP Documentation: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
- django-csp: https://django-csp.readthedocs.io/
- OWASP Security Headers: https://owasp.org/www-project-secure-headers/

## Acceptance Criteria

- [ ] CSP directives configured for all resource types
- [ ] X-Frame-Options set to DENY
- [ ] Permissions-Policy configured
- [ ] CSP report endpoint created
- [ ] Headers verified in production environment
- [ ] React app loads correctly (no CSP violations)
- [ ] Blog loads correctly
- [ ] Forum loads correctly
- [ ] Plant identification works
- [ ] External API calls allowed (Plant.id, PlantNet)
- [ ] CSP violations logged for monitoring
- [ ] Documentation updated

## Work Log

### 2025-11-09 - Security Audit Discovery
**By:** Claude Code Review System (Security Sentinel Agent)
**Actions:**
- Discovered during comprehensive codebase audit
- Identified as HIGH (P1) - Missing defense-in-depth layers
- CVSS 5.3 - Multiple security headers missing
- CSP middleware installed but not configured

**Learnings:**
- CSP prevents XSS by restricting resource origins
- X-Frame-Options prevents clickjacking attacks
- Permissions-Policy restricts browser feature access
- Headers are defense-in-depth (multiple layers)
- CSP reporting helps identify violations and refine policy

**Next Steps:**
- Configure CSP with realistic directives
- Test thoroughly to avoid breaking app
- Monitor CSP violation reports
- Gradually tighten policy (remove unsafe-inline)

## Notes

**CSP Strategy:**
1. Start permissive (allow what's needed)
2. Monitor violations
3. Gradually restrict
4. Goal: Remove 'unsafe-inline' (requires build changes)

**Unsafe-Inline:**
- Required for React inline scripts (current setup)
- Required for Tailwind CSS inline styles
- Can be removed by:
  - Moving all scripts to external files
  - Using nonces for inline scripts
  - Using hashes for inline scripts

**Priority Justification:**
- P1 (HIGH) because headers are missing, not misconfigured
- Defense-in-depth layer missing
- Not immediately exploitable (requires other vulnerabilities)
- But makes exploitation easier if vulnerabilities exist

Source: Comprehensive security audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Security Sentinel
