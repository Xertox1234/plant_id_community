---
status: ready
priority: p4
issue_id: "026"
tags: [security, https, headers]
dependencies: []
---

# Enable HSTS Preload

**CVSS**: 3.7 (Low) - AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N

## Problem

HSTS header lacks `preload` directive. Users could be vulnerable to SSL-stripping attacks on first visit.

## Findings

**security-sentinel**:
- `Strict-Transport-Security` header missing `preload`
- Site not submitted to HSTS preload list
- First-time visitors can be downgraded to HTTP
- Chrome, Firefox, Safari preload list provides zero-visit protection

## Proposed Solutions

### Option 1: Enable HSTS Preload (Recommended)
```python
# settings.py
SECURE_HSTS_SECONDS = 31536000  # 1 year (already set)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # Required for preload
SECURE_HSTS_PRELOAD = True  # Add preload directive
```

Then submit to: https://hstspreload.org/

**Pros**: Maximum security, zero-visit protection
**Cons**: Irreversible for 1 year, requires HTTPS on all subdomains
**Effort**: 30 minutes (config + submission)
**Risk**: Low (if HTTPS already stable)

### Option 2: Keep Current HSTS (No Preload)
**Pros**: Reversible, no subdomain constraints
**Cons**: First visit vulnerable to SSL stripping
**Risk**: Medium (MitM attack on first visit)

## Recommended Action

**Option 1** - Enable preload:
1. Verify HTTPS working on all subdomains (www, api, cms)
2. Set `SECURE_HSTS_PRELOAD = True`
3. Deploy and verify header: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
4. Submit domain to https://hstspreload.org/
5. Monitor for 6-8 weeks for Chrome/Firefox inclusion

## Technical Details

**Current header**:
```
Strict-Transport-Security: max-age=31536000
```

**Target header**:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

**Requirements for preload list**:
- Valid certificate
- Redirect HTTP → HTTPS (port 80 → 443)
- HTTPS on base domain and all subdomains
- max-age ≥ 31536000 (1 year)
- includeSubDomains directive
- preload directive

**Verification**:
```bash
curl -I https://yourdomain.com | grep Strict-Transport-Security
```

## Resources

- HSTS preload list: https://hstspreload.org/
- Chrome HSTS preload: https://www.chromium.org/hsts/
- Mozilla Observatory: https://observatory.mozilla.org/
- Security Headers checker: https://securityheaders.com/

## Acceptance Criteria

- [ ] `SECURE_HSTS_PRELOAD = True` in production settings
- [ ] Header includes `includeSubDomains` and `preload`
- [ ] All subdomains accessible via HTTPS
- [ ] Domain submitted to HSTS preload list
- [ ] Preload status "pending" on hstspreload.org
- [ ] Documented rollback plan (if needed within 1 year)

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent

## Notes

**Priority rationale**: P4 (Low) - Security enhancement but not critical
**Irreversibility**: Once on preload list, cannot remove for 1+ year
**Testing**: Test on staging domain first before production submission
**Related**: Ensure HTTPS enforced (issue #004 from Phase 1)
