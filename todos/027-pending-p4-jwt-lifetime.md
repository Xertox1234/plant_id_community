---
status: ready
priority: p4
issue_id: "027"
tags: [security, authentication, jwt]
dependencies: []
---

# Review JWT Token Lifetime

## Problem

JWT access token lifetime is 24 hours. OWASP recommends ≤15 minutes for access tokens. Long-lived tokens increase session hijacking window.

## Findings

**security-sentinel**:
- ACCESS_TOKEN_LIFETIME = 24 hours (current setting)
- OWASP recommendation: 5-15 minutes for access tokens
- Current risk window: 24 hours if token stolen
- No token rotation mechanism

**best-practices-researcher**:
- Industry standard: 15-minute access tokens + 7-day refresh tokens
- Auth0: 10 minutes default
- Okta: 1 hour default
- AWS Cognito: 1 hour default

## Proposed Solutions

### Option 1: 15-Minute Access + 7-Day Refresh (Recommended)
```python
# settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Was: hours=24
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Keep existing
    'ROTATE_REFRESH_TOKENS': True,  # Issue new refresh token on use
    'BLACKLIST_AFTER_ROTATION': True,  # Invalidate old refresh token
}
```

**Pros**: OWASP compliant, limits hijacking window
**Cons**: More frequent token refreshes, UX impact if not handled smoothly
**Effort**: 2 hours (frontend + backend changes)
**Risk**: Medium (requires frontend auto-refresh logic)

### Option 2: 1-Hour Access Token (Compromise)
```python
'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
```

**Pros**: Better than 24 hours, less UX disruption
**Cons**: Still 4x longer than OWASP recommendation
**Effort**: 30 minutes (config change only)
**Risk**: Low

### Option 3: Keep 24-Hour Tokens
**Pros**: No changes needed, simpler UX
**Cons**: Non-compliant, higher security risk
**Risk**: Medium (session hijacking)

## Recommended Action

**Phased approach**:
1. **Phase 1** (now): Reduce to 1 hour (Option 2) - minimal UX impact
2. **Phase 2** (after auth UX testing): Implement 15-minute with auto-refresh (Option 1)

**Frontend changes required for Phase 2**:
```javascript
// authService.js
async function refreshAccessToken() {
  const refreshToken = getCookie('refresh_token');
  const response = await fetch('/api/auth/token/refresh/', {
    method: 'POST',
    body: JSON.stringify({ refresh: refreshToken })
  });
  const { access } = await response.json();
  setCookie('access_token', access);
}

// Auto-refresh 1 minute before expiration
setInterval(refreshAccessToken, 14 * 60 * 1000);
```

## Technical Details

**Current configuration**:
- Access token: 24 hours
- Refresh token: 7 days
- No rotation

**Target configuration**:
- Access token: 15 minutes
- Refresh token: 7 days
- Rotation: Enabled
- Blacklist: Enabled

**Impact analysis**:
- API calls: No change (token in header)
- User experience: Transparent (auto-refresh in background)
- Security: 96x smaller hijacking window (24h → 15m)

## Resources

- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- djangorestframework-simplejwt docs: https://django-rest-framework-simplejwt.readthedocs.io/
- Auth0 token best practices: https://auth0.com/docs/secure/tokens/token-best-practices
- RFC 6749 OAuth 2.0 (Section 1.5 - Refresh Tokens): https://tools.ietf.org/html/rfc6749#section-1.5

## Acceptance Criteria

- [ ] Access token lifetime ≤ 15 minutes (Phase 2) or ≤ 1 hour (Phase 1)
- [ ] Refresh token rotation enabled
- [ ] Token blacklist enabled
- [ ] Frontend auto-refresh implemented (Phase 2)
- [ ] No user-visible session timeouts during active use
- [ ] Token refresh fails gracefully (redirect to login)
- [ ] Security headers document updated

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent
- Current: 24-hour access tokens

## Notes

**Priority rationale**: P4 (Low) - Security improvement but not critical vulnerability
**User impact**: Phase 1 has zero UX impact, Phase 2 requires auto-refresh logic
**Testing**: Verify auto-refresh on slow connections (3G simulation)
**Related**: Token blacklist (issue #002 from Week 4 auth security)
