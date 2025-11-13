---
status: pending
priority: p2
issue_id: "017"
tags: [security, csrf, authentication, django, medium]
dependencies: [013]
---

# Registration Endpoint Bypasses CSRF Protection

## Problem Statement

The user registration endpoint uses `@csrf_exempt` decorator, completely disabling CSRF protection. This allows attackers to create accounts from their sites with victim's IP address.

**Location:** `backend/apps/users/views.py:65-76`

**CVSS Score:** 5.3 (MEDIUM)

## Findings

- Discovered during comprehensive security audit by Security Sentinel agent
- **Current Code:**
  ```python
  @api_view(['POST'])
  @permission_classes([permissions.AllowAny])
  @csrf_exempt  # ⚠️ DANGEROUS - Disables CSRF protection
  @ratelimit(key='ip', rate=RATE_LIMITS['auth_endpoints']['register'], method='POST', block=True)
  def register(request: Request) -> Response:
      """Register a new user account."""
  ```

- **Impact:**
  - **CSRF protection completely disabled** for registration
  - Attacker can create accounts from their site with victim's IP
  - Could be used for:
    - Spam account creation
    - Email harassment (if email verification enabled)
    - Resource exhaustion (database bloat)
    - Reputation damage

- **Current Mitigation:**
  - Rate limiting: 5 requests/hour per IP (helps but doesn't prevent CSRF)

## Exploitation Scenario

```html
<!-- evil.com -->
<form action="https://plantcommunity.com/api/v1/users/register/" method="POST">
  <input name="username" value="spam123">
  <input name="email" value="victim@example.com">
  <input name="password" value="randompass">
</form>
<script>document.forms[0].submit();</script>
<!-- Victim visits evil.com → account created without consent -->
```

## Proposed Solution

### Remove @csrf_exempt and Use Standard CSRF Protection

```python
# backend/apps/users/views.py
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
# @csrf_exempt  # ❌ REMOVE THIS
@ensure_csrf_cookie  # ✅ ADD THIS (sets CSRF cookie for GET /csrf/)
@ratelimit(key='ip', rate=RATE_LIMITS['auth_endpoints']['register'], method='POST', block=True)
def register(request: Request) -> Response:
    """
    Register a new user account.

    Requires CSRF token in X-CSRFToken header.
    Get CSRF token from GET /api/v1/users/csrf/ first.
    """
    serializer = UserRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'user': UserSerializer(user).data,
            'message': 'Registration successful'
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

### Frontend Changes

```typescript
// web/src/services/authService.ts
async function register(userData: RegisterData): Promise<User> {
  // 1. Get CSRF token first (if not already set)
  if (!getCsrfToken()) {
    await fetch('/api/v1/users/csrf/', { credentials: 'include' });
  }

  // 2. Include CSRF token in registration
  const csrfToken = getCsrfToken();

  const response = await fetch('/api/v1/users/register/', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken || '',
    },
    body: JSON.stringify(userData),
  });

  if (!response.ok) {
    throw new Error('Registration failed');
  }

  return response.json();
}
```

### Add CSRF Endpoint (if not exists)

```python
# backend/apps/users/views.py
from django.views.decorators.csrf import ensure_csrf_cookie

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def csrf_token_view(request: Request) -> Response:
    """
    Get CSRF token for use in registration/login.

    Sets csrftoken cookie that can be read by JavaScript
    (or use meta tag pattern from issue #144).
    """
    return Response({'detail': 'CSRF cookie set'})
```

```python
# backend/plant_community_backend/urls.py
urlpatterns = [
    path('api/v1/users/csrf/', csrf_token_view, name='csrf-token'),
    # ...
]
```

## Why @csrf_exempt Was Used

Likely to avoid CORS preflight complexity. But the fix (CORS headers + CSRF token) is standard Django practice.

**CORS is already configured** in settings.py, so this should work seamlessly.

## Recommended Action

**Phase 1: Backend Changes (1 hour)**
1. ✅ Remove `@csrf_exempt` from register view
2. ✅ Add `@ensure_csrf_cookie` decorator
3. ✅ Create CSRF token endpoint (if not exists)
4. ✅ Test with Postman/curl

**Phase 2: Frontend Changes (1 hour)**
5. ✅ Update register function to fetch CSRF token first
6. ✅ Include X-CSRFToken header in request
7. ✅ Test registration flow

**Phase 3: Testing (1 hour)**
8. ✅ Test registration without CSRF token (should fail with 403)
9. ✅ Test registration with CSRF token (should succeed)
10. ✅ Test CSRF attack scenario (should be blocked)

## Technical Details

- **Affected Files**:
  - `backend/apps/users/views.py` (remove @csrf_exempt)
  - `web/src/services/authService.ts` (add CSRF token)
  - `backend/plant_community_backend/urls.py` (add CSRF endpoint if needed)

- **Related Components**: Authentication, user registration

- **Dependencies**: Issue #144 (CSRF cookie HttpOnly fix)

- **Testing Required**:
  ```bash
  # Test CSRF protection is enforced
  curl -X POST http://localhost:8000/api/v1/users/register/ \
    -H "Content-Type: application/json" \
    -d '{"username":"test","email":"test@example.com","password":"pass123"}'
  # Expected: 403 Forbidden (CSRF token missing)

  # Test with CSRF token
  # 1. Get CSRF token
  curl -c cookies.txt http://localhost:8000/api/v1/users/csrf/

  # 2. Extract token and register
  curl -b cookies.txt -X POST http://localhost:8000/api/v1/users/register/ \
    -H "Content-Type: application/json" \
    -H "X-CSRFToken: <token>" \
    -d '{"username":"test","email":"test@example.com","password":"pass123"}'
  # Expected: 201 Created
  ```

- **Performance Impact**: Negligible (+1 request to get CSRF token, cached)

## Resources

- Security Sentinel audit report (November 9, 2025)
- CWE-352: Cross-Site Request Forgery (CSRF)
- CVSS Score: 5.3 (MEDIUM)
- Django CSRF Documentation: https://docs.djangoproject.com/en/5.2/ref/csrf/
- OWASP CSRF Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

## Acceptance Criteria

- [ ] `@csrf_exempt` removed from register view
- [ ] `@ensure_csrf_cookie` added
- [ ] CSRF token endpoint created
- [ ] Frontend fetches CSRF token before registration
- [ ] X-CSRFToken header included in registration request
- [ ] Registration without CSRF token fails (403)
- [ ] Registration with CSRF token succeeds (201)
- [ ] CSRF attack scenario blocked
- [ ] Tests pass
- [ ] Documentation updated

## Work Log

### 2025-11-09 - Security Audit Discovery
**By:** Claude Code Review System (Security Sentinel Agent)
**Actions:**
- Discovered during comprehensive codebase audit
- Identified as MEDIUM (P2) - CSRF protection bypassed
- CVSS 5.3 - Allows account creation via CSRF
- Anti-pattern flagged

**Learnings:**
- `@csrf_exempt` should NEVER be used on public endpoints
- CSRF protection is critical for state-changing operations
- Rate limiting alone doesn't prevent CSRF
- Standard pattern: CSRF token endpoint + X-CSRFToken header
- CORS complexity is not a valid reason to skip CSRF

**Next Steps:**
- Remove @csrf_exempt
- Add CSRF token endpoint
- Update frontend to use CSRF token
- Test CSRF protection enforcement

## Notes

**Why P2 (Medium) not P0:**
- Rate limiting provides some protection (5/hour per IP)
- Requires attacker to set up malicious site
- Impact is limited (spam accounts, not data breach)
- But still a security vulnerability that should be fixed

**Related to Issue #144:**
This fix should be done AFTER issue #144 (CSRF cookie HttpOnly) is resolved, as it depends on the meta tag pattern for CSRF token retrieval.

**Alternative Solutions:**
1. Keep `@csrf_exempt` but require email verification (reduces impact)
2. Use reCAPTCHA instead of CSRF (different protection model)
3. Both CSRF + reCAPTCHA (defense in depth)

**Recommended:** Remove @csrf_exempt (standard Django security)

Source: Comprehensive security audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Security Sentinel
