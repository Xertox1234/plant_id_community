---
status: resolved
priority: p3
issue_id: "017"
tags: [security, csp]
dependencies: []
resolved_date: 2025-10-28
---

# Add CSP Nonces to Templates

**CVSS**: 3.7 (Low)

## Problem

CSP config has nonces but templates don't use them.

## Solution

```django
<script nonce="{{ request.csp_nonce }}">
    // Inline script
</script>
```

**Effort**: 1 hour (Actual: ~45 minutes)

## Resolution Summary

Added CSP nonces to all inline scripts and styles in blog templates:

### Templates Updated:
1. `/backend/templates/blog/blog_post_page.html` - Added nonce to inline script (comments loading)
2. `/backend/templates/blog/admin/base.html` - Added nonce to inline style
3. `/backend/templates/blog/admin/ai_suggestions.html` - Added nonce to inline script
4. `/backend/templates/blog/admin/search.html` - Added nonce to inline script
5. `/backend/templates/blog/admin/comments.html` - Added nonce to inline script
6. `/backend/templates/blog/admin/featured.html` - Added nonce to inline script
7. `/backend/templates/emails/base.html` - Added nonce with default filter for email rendering

### Tests Created:
- Created comprehensive test suite: `/backend/apps/blog/tests/test_csp_nonces.py`
- 7 tests covering template syntax validation and nonce rendering
- All tests passing ✓

### Key Implementation Details:
- Used `{{ request.csp_nonce }}` template variable (provided by django-csp middleware)
- Email templates use `{{ request.csp_nonce|default:'' }}` to handle missing request context
- No `{% load csp %}` tag needed - nonce is automatically available in request context
- CSP configuration already enabled in production mode (settings.py line 893)

### Production Impact:
- Inline scripts and styles now comply with strict CSP policy in production
- No functional changes - purely security enhancement
- Backward compatible - works in both DEBUG=True and DEBUG=False modes
