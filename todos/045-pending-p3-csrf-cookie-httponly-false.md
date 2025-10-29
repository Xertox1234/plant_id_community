---
status: pending
priority: p3
issue_id: "045"
tags: [code-review, security, csrf, documentation]
dependencies: []
---

# Document CSRF Cookie HttpOnly=False Security Tradeoff

## Problem Statement
CSRF cookie is accessible to JavaScript (HttpOnly=False), which creates XSS risk if XSS vulnerability exists. However, this is required for SPA architecture and mitigated by strong XSS protection.

## Findings
- Discovered during comprehensive code review by security-sentinel agent
- **Location**: `backend/plant_community_backend/settings.py:900`
- **Severity**: MEDIUM (Acceptable risk with mitigations)
- **Rating**: HIGH in audit, but actually ACCEPTABLE given context

**Current configuration**:
```python
CSRF_COOKIE_HTTPONLY = False  # Must be False so JavaScript can read it
```

**Risk**:
If XSS vulnerability exists, attacker can steal CSRF token.

**Existing mitigations** (STRONG ✅):
1. **XSS Protection**:
   - DOMPurify sanitization (5 presets)
   - 105 passing component tests including XSS tests
   - No `dangerouslySetInnerHTML` without sanitization

2. **Additional CSRF Protection**:
   - `CSRF_COOKIE_SAMESITE = 'Lax'` (line 901)
   - CSRF middleware enabled
   - HTTPS enforcement in production

3. **Code Quality**:
   - Security grade: 95/100
   - Comprehensive security audit passed

## Proposed Solutions

### Option 1: Document Security Tradeoff (RECOMMENDED)
Add security policy documentation:

```markdown
# Security Policy

## CSRF Cookie Configuration

**Setting**: `CSRF_COOKIE_HTTPONLY = False`

**Rationale**: Required for Single Page Application (SPA) architecture where JavaScript must read the CSRF token.

**Risk**: If XSS vulnerability exists, attacker could steal CSRF token.

**Mitigations**:
1. **XSS Prevention** (PRIMARY DEFENSE):
   - DOMPurify sanitization on all rich text content
   - 5 sanitization presets (MINIMAL, BASIC, STANDARD, FULL, STREAMFIELD)
   - 105 component tests including XSS scenarios
   - No unsafe HTML rendering

2. **CSRF Protection** (DEFENSE IN DEPTH):
   - SameSite=Lax cookie attribute
   - HTTPS enforcement in production
   - CSRF middleware verification

3. **Monitoring**:
   - Sentry error tracking for XSS attempts
   - Django Auditlog for suspicious activities

**Alternative Considered**: Double-submit cookie pattern with httpOnly CSRF token. Rejected due to complexity and marginal security benefit given strong XSS mitigations.

**Risk Assessment**: LOW - XSS protection is comprehensive and tested.

**Review Schedule**: Quarterly security audit includes XSS testing.
```

**Pros**:
- Documents the decision rationale
- Acknowledges the risk and mitigations
- Provides context for future developers
- No code changes needed

**Cons**:
- None (documentation only)

**Effort**: Small (30 minutes)
**Risk**: None

### Option 2: Implement Double-Submit Cookie Pattern (OVERKILL)
Alternative approach with httpOnly CSRF token:

**How it works**:
1. Server sends two cookies:
   - httpOnly CSRF token (secure)
   - Non-httpOnly session cookie
2. JavaScript sends session cookie in requests
3. Server compares both tokens

**Pros**:
- Protects CSRF token from XSS
- Defense-in-depth approach

**Cons**:
- Significant complexity (20+ hours implementation)
- Requires custom middleware
- Breaks standard Django CSRF
- Marginal security benefit given existing XSS protection

**Effort**: Large (20 hours)
**Risk**: High (breaking change)

## Recommended Action
Implement **Option 1** (documentation only). Current configuration is ACCEPTABLE given:
- Strong XSS protection (DOMPurify)
- Comprehensive testing (105 tests)
- Additional mitigations (SameSite=Lax, HTTPS)

## Technical Details
- **Affected Files**:
  - `backend/plant_community_backend/settings.py:900`
  - New file: `backend/docs/security/CSRF_COOKIE_POLICY.md`
  - Update: `backend/docs/security/AUTHENTICATION_SECURITY.md`

- **Related Components**:
  - Django CSRF middleware
  - React authentication (reads cookie)
  - XSS protection (DOMPurify)

- **Security Assessment**:
  - Current risk: LOW
  - Mitigation effectiveness: HIGH
  - Acceptable for production: YES

## Resources
- Django CSRF: https://docs.djangoproject.com/en/5.2/ref/csrf/
- SameSite cookies: https://web.dev/samesite-cookies-explained/
- XSS prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Security policy document created
- [ ] CSRF configuration rationale documented
- [ ] Mitigations listed and verified
- [ ] Alternative approaches documented
- [ ] Risk assessment included
- [ ] Review schedule established
- [ ] Team briefed on security tradeoff

## Work Log

### 2025-10-28 - Code Review Discovery
**By:** Security Sentinel (Multi-Agent Review)
**Actions:**
- Found HttpOnly=False configuration
- Flagged as HIGH severity initially
- Re-assessed as ACCEPTABLE given mitigations
- Recommended documentation instead of code changes

**Learnings:**
- SPA architecture requires JavaScript access to CSRF token
- Strong XSS protection makes this configuration acceptable
- Documentation prevents future questioning
- Risk is theoretical, not practical (given mitigations)

## Notes
- This is NOT a bug, it's an architectural choice
- Current security grade: 95/100
- XSS protection is comprehensive and tested
- Part of comprehensive code review findings (Finding #11 of 26)
- Downgraded from HIGH to MEDIUM priority (documentation only)
