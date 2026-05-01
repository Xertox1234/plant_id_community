---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, security, performance, rate-limiting, forum]
dependencies: []
---

# Missing Rate Limiting on File Upload Endpoints

## Problem Statement

The `upload_image` endpoint has NO rate limiting, allowing users to spam file uploads and potentially exhaust disk space or bandwidth.

**Location:** `backend/apps/forum/viewsets/post_viewset.py:239-355`

## Findings

- Discovered during security audit by Security Sentinel agent
- **Current State:**
  ```python
  @action(detail=True, methods=['POST'], permission_classes=[IsAuthorOrModerator])
  def upload_image(self, request: Request, pk=None) -> Response:
      # ❌ NO @ratelimit decorator
      # Attacker could rapidly upload 6 images × 10MB = 60MB per post
  ```
- **Exploitation Scenario:**
  ```python
  # Attacker script:
  for i in range(1000):
      for post_id in post_ids:
          upload_10mb_image(post_id)
  # Result: 60GB uploaded, exhausts disk space
  ```
- **Existing Mitigations:**
  1. ✅ Per-post limit: Max 6 attachments per post
  2. ✅ File size limit: 10MB per file (MAX_ATTACHMENT_SIZE_BYTES)
  3. ✅ Authentication required: Must be post author or moderator

## Proposed Solutions

### Option 1: django-ratelimit (RECOMMENDED)
```python
from django_ratelimit.decorators import ratelimit

@action(detail=True, methods=['POST'], permission_classes=[IsAuthorOrModerator])
@ratelimit(key='user', rate='10/h', method='POST', block=True)
def upload_image(self, request: Request, pk=None) -> Response:
    """Upload image to post. Limited to 10 uploads per hour per user."""
    # Existing validation code...
```

Add to requirements.txt:
```
django-ratelimit==4.1.0
```

- **Pros**: Simple, well-tested library, configurable rates
- **Cons**: Requires new dependency
- **Effort**: 1 hour (install + configure + tests)
- **Risk**: Low (widely used, stable library)

### Option 2: Custom Redis-Based Rate Limiting
```python
from django.core.cache import cache

def check_upload_rate_limit(user_id: int, limit: int = 10, window: int = 3600) -> bool:
    """Check if user exceeded upload rate limit."""
    cache_key = f"upload_rate_limit:user:{user_id}"
    count = cache.get(cache_key, 0)

    if count >= limit:
        return False  # Rate limit exceeded

    cache.set(cache_key, count + 1, window)
    return True

@action(detail=True, methods=['POST'], permission_classes=[IsAuthorOrModerator])
def upload_image(self, request: Request, pk=None) -> Response:
    if not check_upload_rate_limit(request.user.id):
        return Response(
            {"error": "Upload rate limit exceeded. Try again later."},
            status=429
        )
    # Existing validation code...
```

- **Pros**: No new dependencies, customizable logic
- **Cons**: More code to maintain, need to implement testing
- **Effort**: 3 hours
- **Risk**: Medium (custom implementation needs thorough testing)

## Recommended Action

**Implement Option 1** - Use django-ratelimit for simplicity and reliability.

Configuration in settings.py:
```python
RATELIMIT_ENABLE = True  # Can disable for testing
RATELIMIT_USE_CACHE = 'default'  # Use Redis cache
RATELIMIT_VIEW = 'apps.forum.views.rate_limit_exceeded'  # Custom error view
```

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/viewsets/post_viewset.py` (upload_image, delete_image)
  - `backend/requirements.txt` (add django-ratelimit)
  - `backend/plant_community_backend/settings.py` (configure ratelimit)
- **Related Components**: Attachment upload/delete endpoints
- **Rate Limits Recommended:**
  - Image upload: 10 per hour per user
  - Image delete: 20 per hour per user (allow cleanup)
- **Cache Backend**: Redis (already configured)

## Resources

- Security Sentinel audit report (Nov 3, 2025)
- CWE-770: Allocation of Resources Without Limits or Throttling
- CVSS Score: 5.0 (Medium)
- django-ratelimit docs: https://django-ratelimit.readthedocs.io/
- OWASP: https://owasp.org/www-community/controls/Blocking_Brute_Force_Attacks

## Acceptance Criteria

- [ ] django-ratelimit installed and configured
- [ ] upload_image decorated with @ratelimit(rate='10/h')
- [ ] delete_image decorated with @ratelimit(rate='20/h')
- [ ] Rate limit errors return 429 status code
- [ ] Error messages explain when user can retry
- [ ] Tests verify rate limiting works
- [ ] Tests verify rate limit resets after window
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive security audit
- Analyzed by Security Sentinel agent
- Categorized as P2 (medium priority - DOS prevention)

**Learnings:**
- File upload endpoints need rate limiting for DOS prevention
- Per-post limits don't prevent cross-post abuse
- Redis-backed rate limiting is production-ready pattern

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Security Sentinel
Attack vector: Authenticated users can exhaust disk space/bandwidth
Mitigation: Rate limiting at user level (10 uploads/hour)
