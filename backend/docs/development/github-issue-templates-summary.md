# GitHub Issue Templates - Quick Reference

**Quick access to templates from the full best practices guide**

See full documentation: [`github-issue-best-practices.md`](./github-issue-best-practices.md)

---

## Security Vulnerability Template

```markdown
## Security Classification

**Severity:** [CRITICAL | HIGH | MEDIUM | LOW]
**CVSS v3.1 Vector:** CVSS:3.1/AV:_/AC:_/PR:_/UI:_/S:_/C:_/I:_/A:_
**CVSS Score:** [0.0-10.0]

## Vulnerability Summary

[1-2 sentence overview - describe WHAT without exposing HOW to exploit]

## Affected Components

- **File(s):** `/path/to/file.py` (lines X-Y)
- **Endpoint(s):** `/api/endpoint/`
- **Environment:** [Production | Staging | Development]

## Impact Assessment

**Confidentiality:** [None | Low | High]
**Integrity:** [None | Low | High]
**Availability:** [None | Low | High]

**Scope:**
- [ ] Affects user data
- [ ] Allows privilege escalation
- [ ] Exposes credentials/secrets

## Problem Statement

**Current Behavior:**
```python
# Show problematic pattern (sanitized)
SECRET_KEY = "hardcoded-key"  # INSECURE
```

**Why This Is Vulnerable:**
1. [Reason 1]
2. [Reason 2]

## Remediation Requirements

**Timeline:** [CRITICAL: 24-48h | HIGH: 7 days | MEDIUM: 30 days | LOW: 60 days]

### Acceptance Criteria
- [ ] Remove hardcoded secrets
- [ ] Implement environment variables
- [ ] Add validation on startup
- [ ] Document rotation procedure
- [ ] Update deployment docs
- [ ] Add security checks to CI/CD

### Recommended Solution
```python
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set")
```

## Testing Requirements
- [ ] Unit tests for validation
- [ ] Security scan (bandit)
- [ ] Manual penetration test
- [ ] Verify fix in staging

## References
- [CWE/CVE link]
- [Django/OWASP docs]
```

---

## Technical Debt Template

```markdown
## Technical Debt Classification

**Category:** [Code Quality | Architecture | Documentation | Testing | Performance]
**Priority:** [No-brainer | Worthy Investment | Quick Win | Backlog]

**Scoring:**
- Knowledge: X/5 - [Team familiarity]
- Severity: Y/5 - [Impact on maintainability]
- Dependency: Z/5 - [Blocks other work]
- Cost: W/5 - [Effort estimate]
- **Total Score:** (X+Y+Z) - 3×W = [Score]

## Problem Statement

[Clear description and why it matters]

## Current State

**Affected Files:**
- `/path/to/file1.py`
- `/path/to/file2.py`

**Example:**
```python
# Current implementation
def method(self, param):  # No type hints
    return result
```

## Impact

**Maintainability:** [Low | Medium | High]
- [Specific impact on development]

**Dependency Risk:**
- Blocks: [Other work blocked]
- Affects: [Areas impacted]

## Proposed Solution

**Desired State:**
```python
from typing import Optional, Dict, Any

def method(self, param: str) -> Optional[Dict[str, Any]]:
    """Documentation."""
    return result
```

**Estimated Effort:** X-Y hours

## Acceptance Criteria
- [ ] [Specific outcome 1]
- [ ] [Specific outcome 2]
- [ ] All tests pass
- [ ] Documentation updated

## Testing Strategy
- [ ] mypy/type checking passes
- [ ] Existing tests still pass
- [ ] No runtime changes

## References
- [PEP/RFC links]
- [Related docs]
```

---

## CVSS Scoring Quick Reference

### Common Django Vulnerabilities

| Vulnerability | CVSS Score | Vector |
|--------------|------------|--------|
| **Hardcoded SECRET_KEY** | 10.0 (CRITICAL) | `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H` |
| **Exposed API Keys** | 5.8 (MEDIUM) | `AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:N/A:N` |
| **Missing File Validation** | 6.4 (MEDIUM) | `AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:L/A:N` |
| **DEBUG=True in Prod** | 5.3 (MEDIUM) | `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` |
| **Unauthenticated Redis** | 8.8 (HIGH) | `AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` |

**Tool:** [CVSS v3.1 Calculator](https://www.first.org/cvss/calculator/3-1)

---

## Remediation Timeline Standards

**Source:** CISA BOD 19-02

| Severity | CVSS | Timeline | Use Case |
|----------|------|----------|----------|
| **CRITICAL** | 9.0-10.0 | 24-48 hours | Hardcoded secrets, auth bypass |
| **HIGH** | 7.0-8.9 | 7 days | API key exposure, file upload |
| **MEDIUM** | 4.0-6.9 | 30 days | DEBUG=True, weak validation |
| **LOW** | 0.1-3.9 | 60-90 days | Code quality, documentation |

**Factors:**
- Active exploitation: Cut timeline by 50%
- Internet-accessible: Use CISA timelines
- Compensating controls: Can extend by 1.5x

---

## Code Example Formatting

### Pattern 1: Current vs. Desired

````markdown
**Current (Insecure):**
```python
SECRET_KEY = "hardcoded"
```

**Desired (Secure):**
```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY required")
```
````

### Pattern 2: Multiple Options

````markdown
### Option 1: Environment Variables (Recommended)
```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
```
**Pros:** Simple, standard
**Cons:** Manual setup

### Option 2: AWS Secrets Manager
```python
secrets = get_secret('prod/django/secrets')
SECRET_KEY = secrets['SECRET_KEY']
```
**Pros:** Rotation, audit logs
**Cons:** AWS dependency
````

---

## Acceptance Criteria Patterns

### Checklist Format (Technical Tasks)

```markdown
## Acceptance Criteria

### Functional Requirements
- [ ] SECRET_KEY from environment
- [ ] Validation on startup
- [ ] No hardcoded secrets

### Testing Requirements
- [ ] Unit test: Fails without SECRET_KEY
- [ ] Unit test: Succeeds with valid key
- [ ] Security scan passes

### Documentation
- [ ] Deployment docs updated
- [ ] README includes setup
```

### Given-When-Then (User Features)

```markdown
## Scenario 1: Invalid File Type

**Given** user uploads .exe renamed to .jpg
**When** server validates with python-magic
**Then** it should reject with 400 Bad Request
**And** log security event
```

---

## Django-Specific Checklists

### Django SECRET_KEY Security
- [ ] Loaded from environment variable
- [ ] Not in version control
- [ ] 50+ characters minimum
- [ ] Different per environment (dev/staging/prod)
- [ ] Rotation procedure documented
- [ ] `SECRET_KEY_FALLBACKS` for zero-downtime rotation
- [ ] Git history cleaned (if previously committed)

### File Upload Security
- [ ] Magic byte validation (python-magic)
- [ ] PIL image integrity check
- [ ] File size limits enforced
- [ ] Dimension limits enforced
- [ ] XBM/XPM formats blocked
- [ ] Files stored outside webroot
- [ ] Filenames sanitized
- [ ] Content-Type header ignored

### API Key Security
- [ ] Keys in environment variables
- [ ] Never logged/printed
- [ ] Different per environment
- [ ] `.env` in `.gitignore`
- [ ] `.env.example` has placeholders only
- [ ] Git history clean
- [ ] Rotation procedure documented
- [ ] Usage monitoring enabled

### Redis Security
- [ ] Password configured (`requirepass`)
- [ ] Bound to localhost only
- [ ] Dangerous commands disabled
- [ ] Django uses REDIS_PASSWORD
- [ ] Locks have expiration timeout
- [ ] Lock release in finally block
- [ ] Auto-renewal for long operations

---

## AI-Friendly Issue Guidelines

### Required Elements

```markdown
## For Claude Code / GitHub Copilot

**Affected Files (absolute paths):**
- `/backend/apps/plant_identification/services/plant_id_service.py`

**Current Code:**
```python
def identify_plant(self, image_file):
    return self._call_api(image_file)
```

**Change To:**
```python
from typing import Optional, Dict, Any
from django.core.files.uploadedfile import UploadedFile

def identify_plant(self, image_file: UploadedFile) -> Optional[Dict[str, Any]]:
    return self._call_api(image_file)
```

**Testing Commands:**
- [ ] `python manage.py test apps.plant_identification`
- [ ] `mypy apps/plant_identification/`

**Context Files to Review:**
- `/backend/apps/plant_identification/constants.py`
- `/backend/docs/performance/week2-performance.md`
```

### Detail Level by Complexity

| Complexity | Files | Lines | Detail Level |
|------------|-------|-------|--------------|
| **Simple** | 1 | <20 | Medium - Show outcome |
| **Moderate** | 2-5 | <100 | High - Code examples |
| **Complex** | 5+ | >100 | Very High - Subtasks |
| **Architecture** | Many | Many | Extreme - Design docs |

---

## Quick Decision Tree

### Is This a Security Issue?

```
Exposes credentials? → YES → CRITICAL (24-48h)
Allows auth bypass? → YES → CRITICAL/HIGH (24h-7d)
File upload vulnerability? → YES → HIGH (7d)
Info disclosure (DEBUG)? → YES → MEDIUM (30d)
Code quality issue? → NO → Technical Debt
```

### Should I Create Private Advisory?

```
CVSS ≥ 9.0? → YES → Private Security Advisory
CVSS 7.0-8.9? → MAYBE → Private if active exploits exist
CVSS < 7.0? → NO → Public issue OK
```

### What Priority for Technical Debt?

```
Score = (Knowledge + Severity + Dependency) - 3×Cost

Score ≥ 10? → No-brainer (do immediately)
Score 5-9? → Worthy investment (schedule soon)
Score 3-4 AND Cost ≤ 2? → Quick win (fill spare time)
Score < 3? → Backlog (defer or accept)
```

---

## Essential Testing Requirements

Every issue must include:

```markdown
## Testing Requirements

### Unit Tests
- [ ] Happy path: Valid input → expected output
- [ ] Error cases: Invalid input → exception
- [ ] Edge cases: Null, empty, boundary values
- [ ] 90%+ code coverage

### Security Tests (for security fixes)
- [ ] `bandit -r apps/plant_identification/`
- [ ] `safety check`
- [ ] Manual penetration test

### Verification
- [ ] All tests pass
- [ ] Code review by human
- [ ] Manual test in dev
- [ ] Verify in staging
```

---

## References

**Full Guide:** [`github-issue-best-practices.md`](./github-issue-best-practices.md)

**Key Tools:**
- [CVSS Calculator](https://www.first.org/cvss/calculator/3-1)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [Django Security Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)

**Standards:**
- [CISA BOD 19-02](https://www.cisa.gov/news-events/directives/bod-19-02-vulnerability-remediation-requirements-internet-accessible-systems)
- [OWASP Top 10](https://owasp.org/Top10/)
- [CWE Top 25](https://cwe.mitre.org/top25/)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-22
