---
status: pending
priority: p3
issue_id: "008"
tags: [code-review, security, jwt, cookies, frontend, audit]
dependencies: []
---

# Migrate JWT Storage from sessionStorage to HTTP-Only Cookies

## Problem Statement
The frontend currently uses `sessionStorage` for JWT token storage, which is vulnerable to XSS attacks. While the codebase has excellent XSS protection via DOMPurify, defense-in-depth security suggests using HTTP-only cookies for maximum protection. Interestingly, the backend already implements cookie-based JWT authentication, so this may just be a frontend cleanup task.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- **Frontend**: Uses `sessionStorage` for JWT tokens
  - Location: `web/src/services/authService.js`
  - Location: `web/src/contexts/AuthContext.jsx`
- **Backend**: Already implements HTTP-only cookie support!
  - Location: `backend/apps/users/authentication.py` (`set_jwt_cookies` function)

**Current state**:
```javascript
// Frontend (web/src/services/authService.js)
sessionStorage.setItem('access_token', tokens.access)
sessionStorage.setItem('refresh_token', tokens.refresh)
```

**Backend already has**:
```python
# backend/apps/users/authentication.py
def set_jwt_cookies(response: Response, tokens: dict) -> None:
    """Set JWT tokens as HTTP-only cookies."""
    response.set_cookie(
        key='access_token',
        value=tokens['access'],
        httponly=True,  # ✅ XSS protection
        secure=True,    # ✅ HTTPS only
        samesite='Lax'  # ✅ CSRF protection
    )
```

**XSS Protection status**:
- ✅ DOMPurify sanitization (6 files)
- ✅ No `dangerouslySetInnerHTML` without sanitization
- ✅ URL/error sanitization (Oct 31, 2025)
- ⚠️ sessionStorage still accessible to JavaScript (XSS risk if protection fails)

## Proposed Solutions

### Option 1: Full Migration to HTTP-Only Cookies (Recommended)
**Pros**:
- Maximum XSS protection (tokens inaccessible to JavaScript)
- Backend already supports this!
- Industry best practice
- Aligns with OWASP JWT guidelines

**Cons**:
- Requires frontend authentication flow changes
- Need to handle CSRF tokens properly
- More complex debugging (can't inspect tokens easily)

**Effort**: Medium (2-3 hours implementation + testing)
**Risk**: Medium (authentication flow changes)

**Implementation steps**:
1. Remove sessionStorage usage from `authService.js`
2. Rely on automatic cookie handling (axios/fetch includes cookies)
3. Update `AuthContext.jsx` to check authentication via API call instead of sessionStorage
4. Ensure CSRF token handling is correct
5. Update logout to clear cookies via API call

```javascript
// After: web/src/services/authService.js
export async function login(email, password) {
  const response = await httpClient.post('/api/v1/auth/login/', {
    email,
    password
  }, {
    withCredentials: true  // Include cookies in request
  })

  // No need to store tokens - backend sets HTTP-only cookies!
  return response.data
}

export async function logout() {
  // Backend clears cookies
  await httpClient.post('/api/v1/auth/logout/', {}, {
    withCredentials: true
  })
}

export async function getCurrentUser() {
  // Check if authenticated by calling API
  const response = await httpClient.get('/api/v1/auth/user/', {
    withCredentials: true
  })
  return response.data
}
```

### Option 2: Hybrid Approach (Keep sessionStorage for UX)
Keep sessionStorage for user data (not tokens):

```javascript
// Store user info for UX, not tokens
sessionStorage.setItem('user', JSON.stringify(user))
// Tokens are in HTTP-only cookies (can't be accessed by JS)
```

**Pros**:
- Best of both worlds
- Fast UX (no API call to check auth)
- Tokens still protected

**Cons**:
- More complex
- sessionStorage can get out of sync

**Effort**: Medium (2 hours)
**Risk**: Low

## Recommended Action
**Option 1** - Full migration to HTTP-only cookies.

Rationale:
1. Backend already supports it (authentication.py has `set_jwt_cookies`)
2. Frontend already uses cookie-based auth in some places (CLAUDE.md mentions it)
3. Maximum security with defense-in-depth
4. Aligns with OWASP recommendations

**Migration plan**:
1. **Week 1**: Audit current frontend auth flow
2. **Week 2**: Remove sessionStorage, rely on cookies
3. **Week 3**: Thorough testing (login, logout, token refresh)
4. **Week 4**: Documentation updates

## Technical Details
- **Affected Files**:
  - `web/src/services/authService.js` (main changes)
  - `web/src/contexts/AuthContext.jsx` (auth check logic)
  - `web/src/utils/httpClient.js` (ensure withCredentials: true)
  - `web/src/main.jsx` (initialization)

- **Backend Support** (already implemented):
  - `backend/apps/users/authentication.py` - `set_jwt_cookies()`, `clear_jwt_cookies()`
  - `backend/apps/users/views.py` - login/logout endpoints use cookies
  - Cookie settings: httponly=True, secure=True, samesite='Lax'

- **CSRF Handling**:
  - Already implemented: `/api/v1/auth/csrf/` endpoint
  - Frontend already fetches CSRF token

## Resources
- Backend cookie authentication: `apps/users/authentication.py:25-65`
- OWASP JWT storage: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- CLAUDE.md auth patterns: `REACT_DJANGO_AUTH_PATTERNS.md`
- Code review audit: October 31, 2025

## Acceptance Criteria
- [ ] Remove all sessionStorage JWT token usage from frontend
- [ ] Configure axios/httpClient with `withCredentials: true`
- [ ] Update AuthContext to check auth via API call (not sessionStorage)
- [ ] Verify login sets HTTP-only cookies correctly
- [ ] Verify logout clears cookies correctly
- [ ] Test token refresh flow works with cookies
- [ ] Test CSRF protection is intact
- [ ] Update documentation with new auth flow
- [ ] Test across browsers (Chrome, Firefox, Safari)

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered sessionStorage usage during codebase audit
- Found backend already implements HTTP-only cookies!
- Identified this as primarily a frontend cleanup task
- Categorized as P3 security enhancement (XSS defense-in-depth)

**Learnings:**
- Backend `set_jwt_cookies()` already exists (well done!)
- Frontend may be using sessionStorage unnecessarily
- CLAUDE.md mentions "cookie-based JWT authentication" as implemented
- Possible the frontend just needs to remove legacy sessionStorage code

**Questions to investigate**:
- Is sessionStorage usage legacy code from early development?
- Does frontend already use cookies in some auth flows?
- Why was sessionStorage kept if cookies already work?

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P3 (security enhancement, not critical)
Category: Security - Token Storage
Backend support: Already implemented!
