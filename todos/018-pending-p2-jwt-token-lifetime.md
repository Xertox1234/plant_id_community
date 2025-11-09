---
status: pending
priority: p2
issue_id: "018"
tags: [security, authentication, jwt, owasp, medium]
dependencies: []
---

# JWT Access Token Lifetime Too Long (OWASP Violation)

## Problem Statement

JWT access tokens have a 60-minute (1 hour) lifetime, which exceeds the OWASP recommendation of 15 minutes or less. This increases the window for token theft and replay attacks.

**Location:** `backend/plant_community_backend/settings.py:527`

**OWASP Recommendation:** "Access tokens should have a short lifetime of 15 minutes or less"

## Findings

- Discovered during comprehensive security audit by Security Sentinel agent
- **Current Configuration:**
  ```python
  SIMPLE_JWT = {
      'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
      # Default: 60 minutes (1 hour)
      'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME', default=7, cast=int)),
  }
  ```

- **Risk Factors:**
  - 1-hour access tokens increase window for token theft/replay
  - Stolen tokens remain valid for 60 minutes
  - Violates OWASP security best practices
  - Token rotation happens less frequently

- **Current Mitigation:**
  - httpOnly cookies (reduces XSS theft risk) ✅
  - Token rotation on refresh ✅
  - Token blacklisting after rotation ✅

## OWASP Best Practice

> "Access tokens should have a short lifetime of 15 minutes or less"
> — [OWASP JWT Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)

**Why 15 minutes?**
- Limits exposure time if token is stolen
- Forces regular token refresh (detect compromised sessions)
- Reduces replay attack window
- Balances security with user experience

## Proposed Solution

### Option 1: 15 Minutes (OWASP Compliant)

```python
# backend/plant_community_backend/settings.py
SIMPLE_JWT = {
    # Phase 1: Reduce to 15 minutes (OWASP compliant)
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=15, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

**Frontend Changes:**
```typescript
// web/src/services/authService.ts
const TOKEN_REFRESH_INTERVAL = 10 * 60 * 1000; // 10 minutes (before 15min expiry)

// Implement automatic token refresh
setInterval(async () => {
  if (isAuthenticated) {
    try {
      await refreshAccessToken();
    } catch (error) {
      // Token refresh failed - log out user
      logout();
    }
  }
}, TOKEN_REFRESH_INTERVAL);
```

**Pros:**
- OWASP compliant
- Maximum security
- Stolen tokens expire quickly

**Cons:**
- Increased refresh API load (4x more requests)
- More complex frontend logic
- Potential UX impact if refresh fails

### Option 2: 20 Minutes (Compromise)

Middle ground between security and practicality:

```python
'ACCESS_TOKEN_LIFETIME': timedelta(minutes=20),
```

**Frontend:**
```typescript
const TOKEN_REFRESH_INTERVAL = 15 * 60 * 1000; // 15 minutes
```

**Pros:**
- Better than current 60 minutes
- Lower refresh frequency than 15 minutes
- Still reasonably secure

**Cons:**
- Not fully OWASP compliant
- Longer exposure window

### Option 3: Sliding Window (Advanced)

Keep 60 minutes but implement sliding window expiration:

```python
# Custom token claim
def get_token_claims(user):
    claims = {
        'user_id': user.id,
        'last_activity': datetime.now().timestamp()
    }
    return claims

# Middleware to check last activity
class TokenActivityMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.auth.get('last_activity')
            if time.time() - last_activity > 900:  # 15 min inactivity
                raise AuthenticationFailed('Token expired due to inactivity')
```

**Pros:**
- Balances security with UX
- Tokens expire after 15 min inactivity
- Active users not interrupted

**Cons:**
- More complex implementation
- Custom middleware required
- Harder to debug

## Recommended Action

**Implement Option 1: 15 Minutes (OWASP Compliant)**

**Phase 1: Backend (30 minutes)**
1. ✅ Update `ACCESS_TOKEN_LIFETIME` to 15 minutes
2. ✅ Ensure `ROTATE_REFRESH_TOKENS = True`
3. ✅ Ensure `BLACKLIST_AFTER_ROTATION = True`
4. ✅ Deploy to development environment

**Phase 2: Frontend (2 hours)**
5. ✅ Implement automatic token refresh (10-minute interval)
6. ✅ Handle refresh failures gracefully (logout)
7. ✅ Test in development
8. ✅ Monitor refresh API load

**Phase 3: Monitoring (1 hour)**
9. ✅ Monitor refresh API endpoint for load
10. ✅ Set up alerts for high failure rates
11. ✅ Track user session durations

**Phase 4: Tuning (ongoing)**
12. ✅ Adjust if needed (can increase to 20 min if 15 causes issues)
13. ✅ Monitor user complaints/session interruptions
14. ✅ A/B test if necessary

## Migration Plan

**Week 1: Development**
- Deploy 15-minute tokens to development
- Test all authentication flows
- Monitor for issues

**Week 2: Staging**
- Deploy to staging with real user behavior
- Monitor refresh API load
- Verify no UX degradation

**Week 3: Production (Gradual Rollout)**
- Deploy to 10% of users
- Monitor metrics (session duration, refresh failures)
- Increase to 50%, then 100%

**Rollback Plan:**
```python
# If issues occur, revert to 30 minutes (interim)
'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30)
```

## Technical Details

- **Affected Files**:
  - `backend/plant_community_backend/settings.py` (update token lifetime)
  - `web/src/services/authService.ts` (add auto-refresh)
  - `web/src/contexts/AuthContext.tsx` (handle refresh logic)

- **Related Components**: Authentication, session management

- **Dependencies**: None (uses existing JWT infrastructure)

- **API Impact**:
  - Current: Refresh every 60 minutes (1 request/hour)
  - After fix: Refresh every 15 minutes (4 requests/hour)
  - At 1000 active users: +3000 requests/hour

- **Database Impact**: Token blacklist table grows 4x faster (mitigated by TTL cleanup)

- **Testing Required**:
  ```bash
  # Test token expiration
  # 1. Get access token
  curl -X POST /api/v1/users/login/ -d '{"email":"test@example.com","password":"test"}'

  # 2. Wait 16 minutes
  sleep 960

  # 3. Try authenticated request (should fail)
  curl -H "Authorization: Bearer <token>" /api/v1/users/me/
  # Expected: 401 Unauthorized (token expired)

  # 4. Refresh token
  curl -X POST /api/v1/users/token/refresh/ -d '{"refresh":"<refresh_token>"}'
  # Expected: 200 OK with new access token
  ```

## Resources

- Security Sentinel audit report (November 9, 2025)
- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- Django Simple JWT: https://django-rest-framework-simplejwt.readthedocs.io/
- JWT Security Best Practices: https://tools.ietf.org/html/rfc8725

## Acceptance Criteria

- [ ] ACCESS_TOKEN_LIFETIME set to 15 minutes
- [ ] ROTATE_REFRESH_TOKENS enabled
- [ ] BLACKLIST_AFTER_ROTATION enabled
- [ ] Frontend implements auto-refresh (10-minute interval)
- [ ] Refresh failures handled gracefully (logout)
- [ ] Token expiration tested (wait 16 min → 401)
- [ ] Refresh endpoint tested
- [ ] API load monitoring configured
- [ ] No UX degradation observed
- [ ] Documentation updated

## Work Log

### 2025-11-09 - Security Audit Discovery
**By:** Claude Code Review System (Security Sentinel Agent)
**Actions:**
- Discovered during comprehensive codebase audit
- Identified as MEDIUM (P2) - OWASP violation
- Current: 60 minutes vs. OWASP: 15 minutes
- Security vs. UX trade-off

**Learnings:**
- OWASP recommends 15-minute access tokens
- Shorter tokens = smaller attack window
- Requires frontend auto-refresh implementation
- httpOnly cookies already mitigate XSS theft
- Token rotation + blacklisting already implemented (good!)

**Trade-offs:**
- **Security:** 15 min = 4x less exposure time
- **UX:** More frequent refreshes (usually transparent)
- **API Load:** 4x more refresh requests
- **Complexity:** Frontend auto-refresh logic

**Next Steps:**
- Start with 15 minutes (OWASP compliant)
- Monitor API load and UX
- Adjust to 20-30 min if needed
- Document decision in architecture docs

## Notes

**Why not 5 minutes?**
- Too aggressive for typical web app
- Would cause UX issues (frequent interruptions)
- 15 minutes is industry standard for web apps

**Why not keep 60 minutes?**
- OWASP violation
- Larger attack window if token stolen
- Industry best practice is moving to shorter tokens
- Modern SPAs handle auto-refresh seamlessly

**Comparison:**
- GitHub: 8 hours (very long, but uses additional factors)
- Google: 60 minutes (similar to current)
- Auth0 default: 10 minutes (stricter than OWASP)
- AWS Cognito: 60 minutes (configurable)
- **Recommendation:** 15 minutes (OWASP standard)

**Priority Justification:**
- P2 (MEDIUM) because current setup is functional
- Not immediately exploitable (requires token theft first)
- But violates security best practices
- Should be fixed to align with industry standards

Source: Comprehensive security audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Security Sentinel
