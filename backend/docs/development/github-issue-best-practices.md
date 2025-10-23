# GitHub Issue Best Practices: Security Vulnerabilities & Technical Debt

**Research Date:** 2025-10-22
**Context:** Django 5.2 backend with Plant.id/PlantNet APIs, Redis caching, circuit breakers, React 19 web + Flutter mobile

---

## Table of Contents

1. [Security Issue Templates](#security-issue-templates)
2. [Technical Debt Templates](#technical-debt-templates)
3. [CVSS Scoring Guidelines](#cvss-scoring-guidelines)
4. [Remediation Timeline Standards](#remediation-timeline-standards)
5. [Code Example Formatting](#code-example-formatting)
6. [Acceptance Criteria Patterns](#acceptance-criteria-patterns)
7. [Django-Specific Security Practices](#django-specific-security-practices)
8. [AI-Era Development Considerations](#ai-era-development-considerations)

---

## 1. Security Issue Templates

### 1.1 Industry Standards (GitHub Official)

**Key Principles:**
- **Private First:** Report vulnerabilities privately to maintainers before public disclosure
- **Coordinated Disclosure:** Only publish full details after maintainer acknowledgment and patch availability
- **Standardized Format:** Use consistent structure for ecosystem, package, and version information

**Source:** [GitHub Security Advisories Best Practices](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/best-practices-for-writing-repository-security-advisories)

### 1.2 Security Issue Template

```markdown
## Security Classification

**Severity:** [CRITICAL | HIGH | MEDIUM | LOW]
**CVSS v3.1 Vector:** [Vector string - see CVSS Guidelines section]
**CVSS Score:** [0.0-10.0]

## Vulnerability Summary

[1-2 sentence overview - describe WHAT without exposing HOW to exploit]

**Example:**
> The application accepts hardcoded API credentials in production settings, allowing unauthorized access to third-party services if source code is exposed.

## Affected Components

- **File(s):** `path/to/file.py` (lines X-Y)
- **Endpoint(s):** `/api/endpoint/` (if applicable)
- **Dependencies:** package==version (if applicable)
- **Environment:** [Production | Staging | Development]

## Impact Assessment

**Confidentiality:** [None | Low | High]
- [Describe what information could be exposed]

**Integrity:** [None | Low | High]
- [Describe what data could be modified]

**Availability:** [None | Low | High]
- [Describe what services could be disrupted]

**Scope:**
- [ ] Affects user data
- [ ] Affects system availability
- [ ] Allows privilege escalation
- [ ] Exposes credentials/secrets
- [ ] Bypasses authentication

## Problem Statement

[Detailed technical description without exploit code]

**Current Behavior:**
```python
# Show problematic pattern (sanitized)
SECRET_KEY = "django-insecure-hardcoded-key-example"  # INSECURE
```

**Why This Is Vulnerable:**
1. [Reason 1: e.g., Secret exposed in version control]
2. [Reason 2: e.g., No rotation mechanism]
3. [Reason 3: e.g., Shared across environments]

## Remediation Requirements

**Timeline:** [Based on severity - see Remediation Timeline Standards]
- CRITICAL: 24-48 hours
- HIGH: 7 days
- MEDIUM: 30 days
- LOW: 60 days

### Acceptance Criteria

- [ ] Remove hardcoded secrets from codebase
- [ ] Implement environment variable loading
- [ ] Add secret validation on startup
- [ ] Document rotation procedure
- [ ] Update deployment documentation
- [ ] Add automated security checks (pre-commit hooks, CI/CD)

### Recommended Solution

**Secure Pattern:**
```python
import os
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable must be set")
```

**Alternative Approaches:**
1. [Option 1: django-environ library]
2. [Option 2: python-decouple]
3. [Option 3: AWS Secrets Manager / HashiCorp Vault]

## Testing Requirements

- [ ] Unit tests for configuration validation
- [ ] Integration tests with environment variables
- [ ] Security scan (e.g., bandit, safety)
- [ ] Manual penetration testing (if CRITICAL)
- [ ] Verify fix doesn't break existing functionality

## References

- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [Django Security Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [OWASP A07:2021 - Identification and Authentication Failures](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)

## Disclosure Policy

**Do NOT:**
- Publicly share exploit code
- Expose attack vectors before fix is deployed
- Share vulnerability details with third parties

**Timeline:**
1. **Day 0:** Private issue created
2. **Day 1-7:** Development and testing
3. **Day 7:** Deploy fix to production
4. **Day 14:** Publish security advisory (after verification)

---

## Related Issues

- #XXX - [Related security issue]
- #YYY - [Related technical debt]
```

### 1.3 Critical Security Disclosure Pattern

For **CRITICAL** vulnerabilities (CVSS 9.0-10.0):

1. **Create Private Security Advisory** (not public issue)
   - Use GitHub Security > Advisories > "New draft security advisory"
   - Collaborate with maintainers in private fork
2. **Limited Distribution:** Only share with:
   - Repository maintainers
   - Security team leads
   - Required third-party vendors (under NDA)
3. **Coordinated Patch & Disclosure:**
   - Develop fix in private repository
   - Test thoroughly in isolated environment
   - Deploy to production immediately
   - Publish advisory 7-14 days after fix deployment

**Source:** [GitHub Coordinated Disclosure](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/about-coordinated-disclosure-of-security-vulnerabilities)

---

## 2. Technical Debt Templates

### 2.1 Prioritization Framework

**Scoring Formula:**
```
Total Score = (Knowledge + Severity + Dependency) - (3 × Cost)

Where:
- Knowledge: 1-5 (team familiarity with codebase area)
- Severity: 1-5 (impact on system quality/maintainability)
- Dependency: 1-5 (blocks other work or affects multiple areas)
- Cost: 1-5 (effort required to fix)
```

**Categories:**
- **No-brainer:** Score ≥ 10 (critical, high knowledge, low cost)
- **Worthy investment:** Score 5-9 (important, moderate effort)
- **Quick wins:** Score 3-4, Cost ≤ 2 (easy fixes, immediate value)
- **Backlog:** Score < 3 (defer or accept risk)

**Source:** [Ducalis Technical Debt Prioritization](https://help.ducalis.io/knowledge-base/technical-debt-prioritization/)

### 2.2 Technical Debt Issue Template

```markdown
## Technical Debt Classification

**Category:** [Code Quality | Architecture | Documentation | Testing | Performance]
**Priority:** [No-brainer | Worthy Investment | Quick Win | Backlog]
**Score:** [Total score from framework above]

**Scoring Breakdown:**
- Knowledge: X/5 - [Justification]
- Severity: Y/5 - [Justification]
- Dependency: Z/5 - [Justification]
- Cost: W/5 - [Effort estimate]

## Problem Statement

[Clear description of the technical debt and why it matters]

**Example:**
> Service methods in `plant_identification/services/` lack type hints, making code harder to maintain and preventing static type checking with mypy/pyright.

## Current State

**Affected Files:**
- `apps/plant_identification/services/combined_identification_service.py` (15 methods)
- `apps/plant_identification/services/plant_id_service.py` (8 methods)
- `apps/plant_identification/services/plantnet_service.py` (6 methods)

**Example:**
```python
# Current implementation (no type hints)
def identify_plant(self, image_file):
    result = self._call_api(image_file)
    return result
```

## Impact

**Maintainability:** [Low | Medium | High impact]
- Harder for new developers to understand expected input/output types
- IDE autocomplete and type checking unavailable
- Runtime type errors only caught in production

**Dependency Risk:**
- Blocks adoption of mypy in CI/CD pipeline
- Affects 5+ service classes, 30+ methods
- Makes refactoring riskier (no compiler assistance)

**Long-term Cost:**
- Estimated 2-3 hours debugging type-related bugs per month
- 20% slower onboarding for new developers

## Proposed Solution

**Desired State:**
```python
# With type hints (following PEP 484)
from typing import Optional, Dict, Any
from django.core.files.uploadedfile import UploadedFile

def identify_plant(
    self,
    image_file: UploadedFile
) -> Optional[Dict[str, Any]]:
    """
    Identify plant from uploaded image.

    Args:
        image_file: Django uploaded file object containing plant image

    Returns:
        Dictionary with identification results, or None if identification fails
    """
    result = self._call_api(image_file)
    return result
```

**Implementation Approach:**
1. Install `django-stubs` or `django-types` for Django type support
2. Add type hints to service method signatures (30 methods)
3. Configure mypy with `mypy.ini`
4. Add mypy check to CI/CD pipeline
5. Document type hint standards in contributing guide

**Estimated Effort:** 4-6 hours
- 2 hours: Add type hints to all service methods
- 1 hour: Configure mypy, create mypy.ini
- 1 hour: Update CI/CD and documentation
- 1-2 hours: Fix any type errors discovered

## Acceptance Criteria

- [ ] All service methods have complete type hints (arguments + return)
- [ ] Use typing module for complex types (Optional, Dict, List, etc.)
- [ ] All type hints use Django-specific types where applicable (UploadedFile, QuerySet, etc.)
- [ ] mypy runs in CI/CD pipeline with no errors
- [ ] Documentation updated with type hint standards
- [ ] At least 2 team members review type hint patterns

## Testing Strategy

- [ ] mypy static analysis passes with strict mode
- [ ] All existing unit tests still pass
- [ ] IDE type checking works correctly (VSCode Pylance, PyCharm)
- [ ] No runtime behavior changes

## References

- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [django-stubs for Django type support](https://github.com/typeddjango/django-stubs)
- [Python Type Hints Best Practices 2025](https://betterstack.com/community/guides/scaling-python/python-type-hints/)
- [mypy Documentation](https://mypy.readthedocs.io/)

## Dependencies

**Blocks:**
- #XXX - CI/CD type checking automation
- #YYY - API client SDK generation (requires typed interfaces)

**Blocked By:**
- None (can start immediately)

## Alternative Approaches

1. **Gradual typing:** Add type hints incrementally per service (lower upfront cost)
2. **Skip stubs:** Use basic type hints without django-stubs (faster but less accurate)
3. **Accept debt:** Document decision to skip type hints (lowest cost, highest long-term risk)

**Recommended:** Full implementation (Option 1 above) - best ROI for maintainability
```

### 2.3 Pareto Principle (80/20 Rule)

When prioritizing technical debt, focus on the **20% of issues** that cause **80% of problems**:

**High-Impact Areas (Prioritize First):**
- Core service layer (business logic)
- Authentication/authorization
- Data validation and security
- Public APIs and contracts
- Critical path code (affects all users)

**Lower-Impact Areas (Defer or Accept):**
- Internal utilities with single caller
- Deprecated features
- Code covered by comprehensive tests
- Cosmetic issues (formatting, naming)

**Source:** [Technical Debt Tracking & Prioritization](https://www.tiny.cloud/blog/technical-debt-tracking/)

---

## 3. CVSS Scoring Guidelines

### 3.1 CVSS v3.1 Metric Definitions

**Base Metrics:**

| Metric | Values | Description |
|--------|--------|-------------|
| **Attack Vector (AV)** | Network (N), Adjacent (A), Local (L), Physical (P) | How attacker accesses vulnerability |
| **Attack Complexity (AC)** | Low (L), High (H) | Difficulty of exploitation |
| **Privileges Required (PR)** | None (N), Low (L), High (H) | Authentication level needed |
| **User Interaction (UI)** | None (N), Required (R) | Requires user action? |
| **Scope (S)** | Unchanged (U), Changed (C) | Affects resources beyond vulnerable component? |
| **Confidentiality (C)** | None (N), Low (L), High (H) | Information disclosure impact |
| **Integrity (I)** | None (N), Low (L), High (H) | Data modification impact |
| **Availability (A)** | None (N), Low (L), High (H) | Service disruption impact |

### 3.2 CVSS Scoring Examples for Django Project

#### Example 1: Hardcoded Django SECRET_KEY

**Vulnerability:** Production SECRET_KEY committed to version control

**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H`

**CVSS Score:** **10.0 (CRITICAL)**

**Justification:**
- **AV:N** - Public GitHub repository accessible globally
- **AC:L** - No special conditions required (just clone repo)
- **PR:N** - No authentication needed to access repository
- **UI:N** - Attacker acts independently
- **S:C** - Secret controls entire Django application (scope change)
- **C:H** - All session data, signed cookies exposed
- **I:H** - Can forge sessions, modify user data
- **A:H** - Can disrupt all application functionality

**Source:** [CVSS v3.1 Examples - Heartbleed](https://www.first.org/cvss/v3-1/examples) (similar credential exposure)

#### Example 2: Missing File Upload Validation

**Vulnerability:** No magic byte validation on uploaded images, accepts files based only on extension

**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:L/A:N`

**CVSS Score:** **6.4 (MEDIUM)**

**Justification:**
- **AV:N** - Attack via network (file upload endpoint)
- **AC:L** - Simple file upload with renamed extension
- **PR:L** - Requires authenticated user account
- **UI:N** - No user interaction beyond attacker
- **S:C** - Uploaded file could affect other users/services
- **C:L** - Potential XSS or information disclosure
- **I:L** - Can upload malicious content
- **A:N** - No direct availability impact

**Real-World Example:** [Joomla Directory Traversal CVE-2010-0467](https://www.first.org/cvss/v3-1/examples) scored 5.8 for file access issues

#### Example 3: Exposed API Keys in Settings

**Vulnerability:** Plant.id and PlantNet API keys in committed `.env` file

**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:N/A:N`

**CVSS Score:** **5.8 (MEDIUM)**

**Justification:**
- **AV:N** - Public repository access
- **AC:L** - Direct file access, no exploitation needed
- **PR:N** - No authentication required
- **UI:N** - Attacker acts independently
- **S:C** - API keys affect external third-party services
- **C:L** - Limited to API quota/data, not full system
- **I:N** - Cannot modify application data directly
- **A:N** - Can exhaust API quota but doesn't stop application

**Industry Example:** [Acunetix Sensitive Data Exposure](https://www.acunetix.com/vulnerabilities/web/sensitive-data-exposure/) rates API key leakage as `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:N/A:N`

#### Example 4: Weak DEBUG=True in Production

**Vulnerability:** Django DEBUG mode enabled in production, exposing stack traces with sensitive paths

**CVSS Vector:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`

**CVSS Score:** **5.3 (MEDIUM)**

**Justification:**
- **AV:N** - Network accessible error pages
- **AC:L** - Trigger error by invalid request
- **PR:N** - No authentication needed
- **UI:N** - Direct exploitation
- **S:U** - Scope unchanged (only affects Django app)
- **C:L** - Reveals file paths, library versions, SQL queries
- **I:N** - No data modification
- **A:N** - No service disruption

#### Example 5: Missing Redis Authentication

**Vulnerability:** Redis accessible without authentication on localhost

**CVSS Vector:** `CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`

**CVSS Score:** **8.8 (HIGH)**

**Justification:**
- **AV:A** - Adjacent network (localhost or VPN)
- **AC:L** - Direct Redis connection, no exploit needed
- **PR:N** - No authentication configured
- **UI:N** - Direct exploitation
- **S:U** - Affects only Redis data store
- **C:H** - All cached data exposed (plant IDs, user sessions)
- **I:H** - Can modify/delete cache entries
- **A:H** - Can flush entire cache, causing service degradation

### 3.3 CVSS Scoring Quick Reference

| Vulnerability Type | Typical Score | Example Vector |
|-------------------|---------------|----------------|
| Hardcoded production secrets | 9.0-10.0 (CRITICAL) | `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H` |
| Exposed API keys | 5.3-7.5 (MEDIUM-HIGH) | `AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:N/A:N` |
| Missing file validation | 6.1-7.5 (MEDIUM) | `AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:L/A:N` |
| DEBUG=True in production | 5.3-6.5 (MEDIUM) | `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` |
| SQL Injection | 8.0-9.8 (HIGH-CRITICAL) | `AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H` |
| Missing authentication | 7.3-9.8 (HIGH-CRITICAL) | `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` |
| Unauthenticated Redis | 8.8 (HIGH) | `AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` |

**Tools:**
- [CVSS v3.1 Calculator](https://www.first.org/cvss/calculator/3-1)
- [GitLab CVSS Calculator](https://gitlab-com.gitlab.io/gl-security/product-security/appsec/cvss-calculator/)

---

## 4. Remediation Timeline Standards

### 4.1 Industry Standards (CISA & NIST)

**Source:** [CISA BOD 19-02](https://www.cisa.gov/news-events/directives/bod-19-02-vulnerability-remediation-requirements-internet-accessible-systems)

| Severity | CVSS Score | Remediation Timeline | Justification |
|----------|------------|---------------------|---------------|
| **CRITICAL** | 9.0-10.0 | **15 days** (CISA) / **24-48 hours** (private sector) | Active exploitation likely, high impact |
| **HIGH** | 7.0-8.9 | **30 days** | Significant risk, requires urgent attention |
| **MEDIUM** | 4.0-6.9 | **60-90 days** | Moderate risk, plan remediation |
| **LOW** | 0.1-3.9 | **90-120 days** or accept risk | Limited impact, balance with other priorities |

**Factors Affecting Timeline:**
- **Active exploitation:** Reduce timeline by 50% if exploits exist in the wild
- **Internet-accessible systems:** Use CISA timelines (more aggressive)
- **Internal systems:** Can extend by 1.5x if compensating controls exist
- **Critical infrastructure:** Follow CISA guidelines strictly

### 4.2 Django Project Remediation SLAs

**Recommended Timelines for Plant ID Community Project:**

| Finding Type | Severity | Timeline | Rationale |
|--------------|----------|----------|-----------|
| Hardcoded SECRET_KEY in production | CRITICAL | **24 hours** | Immediate compromise risk |
| Exposed API keys (Plant.id/PlantNet) | HIGH | **7 days** | Limited blast radius (API quota only) |
| Missing file upload validation | HIGH | **7 days** | User-facing attack vector |
| DEBUG=True in production | HIGH | **7 days** | Information disclosure to attackers |
| Missing type hints on services | LOW | **90 days** | Code quality, not security |
| Code duplication in services | LOW | **120 days** or backlog | Maintainability, not urgent |

### 4.3 Remediation Workflow

```markdown
## Remediation Phases

### Phase 1: Triage (Day 0)
- [ ] Assign CVSS score
- [ ] Determine remediation timeline
- [ ] Assign owner
- [ ] Create private issue (if CRITICAL/HIGH security)

### Phase 2: Analysis (Day 0-1)
- [ ] Identify all affected components
- [ ] Document attack vectors (privately)
- [ ] Assess compensating controls
- [ ] Design remediation approach

### Phase 3: Development (Day 1-X)
- [ ] Implement fix in development environment
- [ ] Write tests to prevent regression
- [ ] Code review by security-aware developer
- [ ] Test in staging environment

### Phase 4: Deployment (Day X)
- [ ] Deploy to production during maintenance window
- [ ] Verify fix in production
- [ ] Monitor for issues (24-48 hours)
- [ ] Document in changelog

### Phase 5: Post-Remediation (Day X+14)
- [ ] Publish security advisory (if applicable)
- [ ] Update security documentation
- [ ] Add preventive measures (linters, CI/CD checks)
- [ ] Conduct retrospective (if CRITICAL)
```

**Source:** [Vulnerability Remediation Best Practices - NinjaOne](https://www.ninjaone.com/blog/vulnerability-remediation-timelines-best-practices/)

---

## 5. Code Example Formatting

### 5.1 GitHub Markdown Standards

**Official Source:** [GitHub Creating Code Blocks](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-and-highlighting-code-blocks)

#### Inline Code
Use single backticks for inline code:
```markdown
Install package with `pip install django-redis`
```

#### Fenced Code Blocks
Use triple backticks with language identifier:

````markdown
```python
from django.conf import settings

SECRET_KEY = settings.SECRET_KEY
```
````

**Best Practices:**
- **Always use language identifier** for syntax highlighting (`python`, `bash`, `javascript`, `json`, `yaml`)
- **Blank lines:** Place blank line before and after code blocks for readability
- **Lowercase identifiers:** Use `python` not `Python` for consistency
- **Context:** Add comment explaining what code demonstrates

### 5.2 Code Example Patterns for Issues

#### Pattern 1: Current vs. Desired State

````markdown
**Current Implementation (Insecure):**
```python
# settings.py - INSECURE: Hardcoded secret
SECRET_KEY = "django-insecure-7x8y9z-hardcoded-key"
```

**Desired Implementation (Secure):**
```python
# settings.py - SECURE: Environment variable
import os
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set")
```
````

#### Pattern 2: Before/After with Explanation

````markdown
## Problem

The service method lacks type hints, causing IDE autocomplete failures:

```python
# apps/plant_identification/services/plant_id_service.py
def identify_plant(self, image_file):  # What type is image_file?
    result = self._call_api(image_file)
    return result  # What type is returned?
```

## Solution

Add PEP 484 type hints with Django-specific types:

```python
# apps/plant_identification/services/plant_id_service.py
from typing import Optional, Dict, Any
from django.core.files.uploadedfile import UploadedFile

def identify_plant(
    self,
    image_file: UploadedFile
) -> Optional[Dict[str, Any]]:
    """
    Identify plant from uploaded image.

    Args:
        image_file: Django UploadedFile containing plant photo

    Returns:
        Dict with identification results, or None if API fails

    Raises:
        ValueError: If image_file is not valid image format
    """
    result = self._call_api(image_file)
    return result
```

**Benefits:**
- IDE autocomplete now works
- Static type checking with mypy
- Self-documenting code
````

#### Pattern 3: Multiple Approaches

````markdown
## Remediation Options

### Option 1: Environment Variables (Recommended)

```python
# settings.py
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
```

```bash
# .env (never commit this file)
DJANGO_SECRET_KEY=your-secret-key-here
```

**Pros:** Simple, standard practice
**Cons:** Manual setup on each server

### Option 2: django-environ Library

```python
# settings.py
import environ

env = environ.Env()
environ.Env.read_env()  # reads from .env file

SECRET_KEY = env('DJANGO_SECRET_KEY')
```

**Pros:** Type validation, default values
**Cons:** Extra dependency

### Option 3: AWS Secrets Manager

```python
# settings.py
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

secrets = get_secret('prod/django/secrets')
SECRET_KEY = secrets['SECRET_KEY']
```

**Pros:** Centralized rotation, audit logs
**Cons:** AWS dependency, complexity
````

### 5.3 File Path References

**Use Absolute Paths from Repository Root:**

```markdown
**Affected Files:**
- `/backend/apps/plant_identification/services/combined_identification_service.py`
- `/backend/apps/plant_identification/views.py`
- `/backend/config/settings/production.py`

**NOT:**
- `combined_identification_service.py` (ambiguous)
- `../services/plant_id_service.py` (relative)
```

**Link to Lines on GitHub:**
```markdown
See hardcoded API key on [line 45 of plant_id_service.py](https://github.com/user/repo/blob/main/backend/apps/plant_identification/services/plant_id_service.py#L45-L48)
```

---

## 6. Acceptance Criteria Patterns

### 6.1 Checklist Format (Recommended for Technical Tasks)

**Source:** [GitHub Issue Template Examples](https://github.com/stevemao/github-issue-templates)

```markdown
## Acceptance Criteria

### Functional Requirements
- [ ] SECRET_KEY loaded from environment variable
- [ ] Application raises `ImproperlyConfigured` if SECRET_KEY missing
- [ ] SECRET_KEY validation runs on Django startup
- [ ] No hardcoded secrets remain in codebase (verified with grep)

### Security Requirements
- [ ] SECRET_KEY minimum length enforced (50+ characters)
- [ ] SECRET_KEY rotation procedure documented
- [ ] `.env.example` created with placeholder (never real secrets)
- [ ] `.env` added to `.gitignore` (verified not in git history)

### Testing Requirements
- [ ] Unit test: Application fails to start without SECRET_KEY
- [ ] Unit test: Application starts successfully with valid SECRET_KEY
- [ ] Integration test: All features work with environment-based config
- [ ] Security scan: No secrets detected by `detect-secrets` tool

### Documentation Requirements
- [ ] Deployment docs updated with environment variable setup
- [ ] README.md includes `.env` configuration example
- [ ] SECURITY.md updated with secret rotation process
- [ ] Code comments explain why environment variables are required

### DevOps Requirements
- [ ] CI/CD pipeline configured with test SECRET_KEY
- [ ] Production environment variables configured (Heroku/AWS/etc.)
- [ ] Staging environment mirrors production config
- [ ] Secret rotation tested in staging environment
```

**Why Checklists?**
- **Visual Progress:** GitHub renders checkboxes, shows completion percentage
- **Unambiguous:** Clear definition of "done"
- **Reviewable:** Easy for code reviewers to verify all criteria met
- **AI-Friendly:** Claude Code can systematically work through checklist

### 6.2 Given-When-Then Format (For User-Facing Features)

**Source:** [User Story Template - Mozilla Developer Network](https://github.com/mdn/sprints/blob/master/.github/ISSUE_TEMPLATE/user-story-template.md)

```markdown
## Acceptance Criteria

### Scenario 1: Missing Environment Variable

**Given** the Django application is starting
**And** the `DJANGO_SECRET_KEY` environment variable is not set
**When** Django reads settings.py
**Then** it should raise `ImproperlyConfigured` exception
**And** the error message should say "DJANGO_SECRET_KEY must be set"
**And** the application should not start

### Scenario 2: Valid Environment Variable

**Given** the Django application is starting
**And** the `DJANGO_SECRET_KEY` environment variable is set to a valid 50-character key
**When** Django reads settings.py
**Then** the application should start successfully
**And** all session signing should use the environment-provided key
**And** no warnings or errors should appear in logs

### Scenario 3: Secret Rotation

**Given** the application is running with SECRET_KEY "old-key"
**And** I want to rotate to SECRET_KEY "new-key" without downtime
**When** I set `SECRET_KEY_FALLBACKS = ["old-key"]` in settings
**And** I set `SECRET_KEY = "new-key"`
**And** I restart the application
**Then** existing sessions signed with "old-key" should remain valid
**And** new sessions should be signed with "new-key"
**And** no users should be logged out
```

**When to Use:**
- User-facing features
- Authentication/authorization flows
- Multi-step processes
- Edge cases and error handling

### 6.3 Hybrid Format (Recommended for Complex Issues)

Combine checklist for implementation with scenarios for behavior:

```markdown
## Acceptance Criteria

### Implementation Checklist
- [ ] Add python-magic to requirements.txt
- [ ] Implement MIME type validation in FileUploadView
- [ ] Add file size limit (10MB max)
- [ ] Add image dimension validation (max 4000x4000px)

### Behavior Scenarios

#### Scenario 1: Valid Image Upload
**Given** user uploads a valid JPEG image (2MB, 1200x1200px)
**When** the server validates the file
**Then** it should accept the upload
**And** return 200 OK with plant identification results

#### Scenario 2: Invalid File Type (Malicious Upload)
**Given** attacker uploads a .exe file renamed to .jpg
**When** the server validates the file with python-magic
**Then** it should detect the true MIME type as application/x-executable
**And** reject the upload with 400 Bad Request
**And** log the security event with user IP address

#### Scenario 3: File Too Large
**Given** user uploads a 15MB image
**When** the server checks file size
**Then** it should reject with 413 Payload Too Large
**And** suggest compressing the image
```

---

## 7. Django-Specific Security Practices

### 7.1 Django SECRET_KEY Security

**Critical Finding:** Django SECRET_KEY is used for cryptographic signing of:
- Session cookies
- CSRF tokens
- Password reset tokens
- `django.contrib.messages` framework
- Any use of `signing.Signer` API

**Source:** [Django Security Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)

#### Best Practices

**1. Environment Variable Storage (Required)**

```python
# settings.py
import os
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# Validate on startup
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable is required. "
        "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

# Enforce minimum length (Django default is 50 characters)
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters")
```

**2. Secret Rotation (Django 4.1+)**

**Source:** [Django Secret Key Rotation](https://adamj.eu/tech/2024/08/30/django-rotate-secret-key/)

```python
# settings.py
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')  # New key
SECRET_KEY_FALLBACKS = [
    os.environ.get('DJANGO_SECRET_KEY_OLD'),  # Previous key
]

# Rotation procedure:
# 1. Generate new key
# 2. Set DJANGO_SECRET_KEY=new-key, DJANGO_SECRET_KEY_OLD=old-key
# 3. Restart application (users stay logged in)
# 4. Wait SESSION_COOKIE_AGE duration (default: 2 weeks)
# 5. Remove old key from fallbacks
```

**3. Secret Generation**

```bash
# Generate cryptographically secure SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Example output:
# django-insecure-7x8y9z_a!b@c#d$e%f^g&h*i(j)k-l=m+n~o`p[q]r{s}t
```

**4. Git History Cleanup (If Secret Was Committed)**

```bash
# WARNING: This rewrites git history - coordinate with team first
# Install git-filter-repo
pip install git-filter-repo

# Remove secret from all commits
git filter-repo --replace-text <(echo "old-secret-key==>REDACTED")

# Force push (requires team coordination)
git push origin --force --all

# IMPORTANT: Rotate the exposed secret immediately
# The old secret is now public and must be considered compromised
```

#### Security Checklist

- [ ] SECRET_KEY is loaded from environment variable
- [ ] SECRET_KEY is not committed to version control
- [ ] SECRET_KEY is at least 50 characters long
- [ ] SECRET_KEY is different between production, staging, and development
- [ ] SECRET_KEY rotation procedure is documented
- [ ] `SECRET_KEY_FALLBACKS` configured for zero-downtime rotation
- [ ] Git history does not contain any previous SECRET_KEY values
- [ ] Deployment scripts inject SECRET_KEY securely (no logs/console output)

### 7.2 File Upload Security (Django + Plant ID Use Case)

**Vulnerability:** Django `ImageField` only validates file type when uploaded via ModelForm, not when saved directly via API.

**Source:** [Django Image Validation Vulnerability](https://insinuator.net/2014/05/django-image-validation-vulnerability/)

#### Secure File Upload Implementation

```python
# apps/plant_identification/validators.py
import magic
from django.core.exceptions import ValidationError
from django.conf import settings
from PIL import Image

ALLOWED_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/heif',  # iPhone photos
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DIMENSIONS = (4000, 4000)  # 4000x4000px

def validate_image_file(file):
    """
    Validate uploaded image using magic byte detection and PIL.

    Protects against:
    - Malicious files with fake extensions (.exe renamed to .jpg)
    - Oversized files causing memory exhaustion
    - Image bombs (decompression attacks)
    - XBM/XPM code injection vulnerabilities

    Raises:
        ValidationError: If file fails any validation check
    """
    # Check file size before reading
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024)}MB. "
            f"Your file is {file.size / (1024*1024):.1f}MB."
        )

    # Read file header to detect true MIME type
    file.seek(0)
    mime_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)  # Reset for Django processing

    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"Invalid file type: {mime_type}. "
            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # Verify file is actually an image and check dimensions
    try:
        img = Image.open(file)
        img.verify()  # Verify it's an image

        # Reopen for dimension check (verify() closes file)
        file.seek(0)
        img = Image.open(file)

        width, height = img.size
        if width > MAX_DIMENSIONS[0] or height > MAX_DIMENSIONS[1]:
            raise ValidationError(
                f"Image dimensions too large: {width}x{height}px. "
                f"Maximum: {MAX_DIMENSIONS[0]}x{MAX_DIMENSIONS[1]}px"
            )

        # Protect against XBM/XPM code injection
        if img.format in ['XBM', 'XPM']:
            raise ValidationError(
                f"Unsupported image format: {img.format}. "
                f"XBM and XPM formats are not allowed for security reasons."
            )

    except (IOError, SyntaxError) as e:
        raise ValidationError(f"Invalid or corrupted image file: {str(e)}")

    finally:
        file.seek(0)  # Reset for Django processing

# Usage in serializer
from rest_framework import serializers

class PlantIdentificationSerializer(serializers.Serializer):
    image = serializers.ImageField(validators=[validate_image_file])
```

**Installation Requirements:**

```bash
# Install python-magic
pip install python-magic

# Install libmagic (system dependency)
# macOS:
brew install libmagic

# Ubuntu/Debian:
sudo apt-get install libmagic1

# Windows:
# Download from https://github.com/pidydx/libmagicwin64
```

#### File Upload Security Checklist

- [ ] Magic byte validation (python-magic) enforced
- [ ] PIL validation for image integrity
- [ ] File size limits enforced (before reading entire file)
- [ ] Image dimension limits enforced
- [ ] XBM/XPM formats blocked (code injection risk)
- [ ] Uploaded files stored outside webroot (not directly accessible)
- [ ] Uploaded filenames sanitized (no path traversal)
- [ ] Content-Type header ignored (only trust magic bytes)
- [ ] Validation happens even when not using ModelForm

### 7.3 API Key Security (Plant.id & PlantNet)

**Risk:** Exposed API keys allow attackers to:
- Exhaust monthly quota (100 Plant.id calls/month)
- Access identification history
- Incur charges if upgraded to paid tier

#### Best Practices

**1. Environment Variable Storage**

```python
# settings.py
import os
from django.core.exceptions import ImproperlyConfigured

# Required API keys
PLANT_ID_API_KEY = os.environ.get('PLANT_ID_API_KEY')
PLANTNET_API_KEY = os.environ.get('PLANTNET_API_KEY')

# Validate on startup
if not PLANT_ID_API_KEY:
    raise ImproperlyConfigured("PLANT_ID_API_KEY environment variable is required")

if not PLANTNET_API_KEY:
    raise ImproperlyConfigured("PLANTNET_API_KEY environment variable is required")
```

**2. Never Log API Keys**

```python
# BAD: Logs expose API key
import logging
logger = logging.getLogger(__name__)

def call_plant_id_api(image):
    logger.info(f"Calling Plant.id API with key: {settings.PLANT_ID_API_KEY}")  # INSECURE!
    ...

# GOOD: Redact sensitive data
def call_plant_id_api(image):
    # Show only last 4 characters
    key_preview = f"...{settings.PLANT_ID_API_KEY[-4:]}"
    logger.info(f"[PLANT_ID] Calling API (key: {key_preview})")
    ...
```

**3. API Key Rotation Procedure**

```markdown
## API Key Rotation Process

1. **Generate New Keys:**
   - Plant.id: Log into https://web.plant.id/api-keys → Create new key
   - PlantNet: Contact support or regenerate via dashboard

2. **Test in Staging:**
   ```bash
   # Update staging environment
   export PLANT_ID_API_KEY=new-key-here

   # Test identification
   curl -X POST http://staging.example.com/api/identify/ \
        -F "image=@test_plant.jpg"
   ```

3. **Update Production:**
   ```bash
   # Heroku example
   heroku config:set PLANT_ID_API_KEY=new-key-here --app prod-app

   # AWS ECS example
   aws ecs update-service --cluster prod --service django \
       --force-new-deployment
   ```

4. **Verify & Revoke Old Key:**
   - Check production logs for successful API calls
   - Wait 24 hours to catch any stale configs
   - Revoke old key via Plant.id/PlantNet dashboard

5. **Update Documentation:**
   - Update `.env.example` with placeholder
   - Document rotation date in CHANGELOG.md
```

#### API Key Security Checklist

- [ ] API keys stored in environment variables
- [ ] API keys never logged or printed
- [ ] API keys different between dev/staging/prod
- [ ] `.env` file in `.gitignore`
- [ ] `.env.example` contains placeholders only
- [ ] Git history does not contain real API keys
- [ ] API key rotation procedure documented
- [ ] API usage monitoring enabled (detect quota exhaustion)

### 7.4 Redis Security (Distributed Locks & Caching)

**Vulnerability:** Redis running without authentication allows anyone with network access to:
- Read/modify cached data
- Delete cache entries (denial of service)
- Acquire distributed locks (bypass rate limiting)

#### Secure Redis Configuration

**1. Enable Authentication**

```bash
# redis.conf
requirepass your-strong-redis-password-here

# Restart Redis
brew services restart redis  # macOS
sudo systemctl restart redis  # Linux
```

**2. Django Settings**

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PASSWORD': os.environ.get('REDIS_PASSWORD'),  # Required in production
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        }
    }
}

# Validate Redis password in production
if not settings.DEBUG and not os.environ.get('REDIS_PASSWORD'):
    raise ImproperlyConfigured("REDIS_PASSWORD required in production")
```

**3. Network Isolation**

```bash
# redis.conf - Bind to localhost only (not 0.0.0.0)
bind 127.0.0.1 ::1

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
```

**4. Distributed Lock Security**

```python
# Secure distributed lock usage with timeout
from redis import Redis
from redis_lock import Lock

redis_client = Redis(
    host='localhost',
    port=6379,
    password=settings.REDIS_PASSWORD,
    socket_timeout=5,
    socket_connect_timeout=5,
)

def process_with_lock(image_hash):
    lock_key = f"plant_id:lock:{image_hash}"

    # IMPORTANT: Always use timeout to prevent deadlocks
    lock = Lock(redis_client, lock_key, expire=300, auto_renewal=True)

    if lock.acquire(blocking=False):
        try:
            # Critical section: Call API
            result = call_plant_id_api(image)
            return result
        finally:
            # ALWAYS release lock, even if exception occurs
            try:
                lock.release()
            except Exception as e:
                logger.error(f"[LOCK] Failed to release lock {lock_key}: {e}")
    else:
        # Lock already held - return cached result or wait
        logger.info(f"[LOCK] Lock already held for {lock_key}")
        return get_cached_result(image_hash)
```

#### Redis Security Checklist

- [ ] Redis password configured (`requirepass` in redis.conf)
- [ ] Redis bound to localhost only (not 0.0.0.0)
- [ ] Dangerous commands disabled (FLUSHDB, CONFIG, SHUTDOWN)
- [ ] Django configured with REDIS_PASSWORD from environment
- [ ] Distributed locks always have expiration timeout
- [ ] Lock release in finally block (even if error occurs)
- [ ] Lock auto-renewal enabled for long operations
- [ ] Redis monitoring enabled (detect unusual activity)

---

## 8. AI-Era Development Considerations

### 8.1 Optimizing Issues for AI Pair Programming

**Context:** Claude Code, GitHub Copilot, and other AI coding assistants work best with detailed, structured issues.

**Source:** [Solving GitHub Issues with Claude Code](https://coder.com/blog/coding-with-claude-code)

#### What Makes a Good AI-Friendly Issue?

**1. Explicit File Paths**

```markdown
# GOOD: Specific paths from repository root
**Affected Files:**
- `/backend/apps/plant_identification/services/plant_id_service.py`
- `/backend/apps/plant_identification/constants.py`
- `/backend/requirements.txt`

# BAD: Vague or relative
**Affected Files:**
- "The Plant ID service file"
- `../services/plant_id_service.py`
```

**2. Code Examples Over Descriptions**

```markdown
# GOOD: Show exactly what to change
**Current:**
```python
def identify_plant(self, image_file):
    return self._call_api(image_file)
```

**Change to:**
```python
from typing import Optional, Dict, Any
from django.core.files.uploadedfile import UploadedFile

def identify_plant(self, image_file: UploadedFile) -> Optional[Dict[str, Any]]:
    return self._call_api(image_file)
```

# BAD: Vague instruction
"Add type hints to the identify_plant method"
```

**3. Testing Criteria**

```markdown
# GOOD: Specific test requirements
**Testing Requirements:**
- [ ] Add unit test: `test_identify_plant_with_valid_image()` should return dict
- [ ] Add unit test: `test_identify_plant_with_invalid_file()` should raise ValueError
- [ ] Add unit test: `test_identify_plant_api_failure()` should return None
- [ ] Run mypy: `mypy apps/plant_identification/services/` should pass with no errors
- [ ] Run existing tests: `python manage.py test apps.plant_identification` should pass

# BAD: Vague requirement
"Make sure tests pass"
```

**4. Acceptance Criteria as Implementation Checklist**

AI assistants work well with step-by-step checklists:

```markdown
## Implementation Steps (for Claude Code)

- [ ] Step 1: Install `python-magic` in requirements.txt
- [ ] Step 2: Create `apps/plant_identification/validators.py` with `validate_image_file()` function
- [ ] Step 3: Import validator in `apps/plant_identification/serializers.py`
- [ ] Step 4: Add validator to `PlantIdentificationSerializer.image` field
- [ ] Step 5: Create unit test file `apps/plant_identification/tests/test_validators.py`
- [ ] Step 6: Add test cases for valid JPEG, invalid file type, oversized file
- [ ] Step 7: Update documentation in `README.md` with validation rules
```

### 8.2 Detail Level Balance

**Finding:** Claude Code performs well on "small, well-defined tasks in familiar frameworks" but struggles with "deeper reasoning, system complexity, or poorly documented APIs."

**Source:** [Solving GitHub Issues with Claude Code](https://coder.com/blog/coding-with-claude-code)

#### Issue Complexity Guidelines

| Issue Type | Detail Level | Example |
|------------|--------------|---------|
| **Simple Fix** (1 file, <20 lines) | Medium - Show desired outcome | "Add type hint to method X, return type should be `Optional[Dict[str, Any]]`" |
| **Moderate Change** (2-5 files, <100 lines) | High - Provide code examples | Show before/after for each file, specify imports needed |
| **Complex Feature** (5+ files, >100 lines) | Very High - Break into subtasks | Create separate issues for each component, link dependencies |
| **Architecture Change** | Extreme - Include design doc | Provide architecture diagram, sequence diagrams, interface contracts |

#### Too Little Detail (AI Will Struggle)

```markdown
# BAD: Underspecified
**Issue:** Add file validation

**Tasks:**
- Validate uploaded files
- Make it secure
```

**Problem:** AI doesn't know:
- Which files to modify
- What validation rules to implement
- How to handle errors
- What libraries to use

#### Too Much Detail (Wastes Time)

```markdown
# BAD: Overspecified
**Issue:** Add type hint to line 45 of plant_id_service.py

**Implementation:**
1. Open /backend/apps/plant_identification/services/plant_id_service.py
2. Navigate to line 45
3. Change `def identify_plant(self, image_file):` to `def identify_plant(self, image_file: UploadedFile) -> Optional[Dict[str, Any]]:`
4. Add import: from typing import Optional, Dict, Any
5. Add import: from django.core.files.uploadedfile import UploadedFile
6. Save file
```

**Problem:**
- Could just submit a PR instead of writing issue
- AI doesn't need line-by-line instructions
- Wastes time writing issue

#### Goldilocks Detail (Just Right)

```markdown
# GOOD: Balanced detail
**Issue:** Add type hints to Plant ID service methods

**Scope:**
- File: `/backend/apps/plant_identification/services/plant_id_service.py`
- Methods: `identify_plant()`, `_call_api()`, `_parse_response()`

**Requirements:**
- Use PEP 484 type hints (typing module)
- Use Django types: `UploadedFile`, `QuerySet`
- Return types should be `Optional[Dict[str, Any]]` for API methods
- Add docstrings with Args/Returns/Raises sections

**Example Pattern:**
```python
from typing import Optional, Dict, Any
from django.core.files.uploadedfile import UploadedFile

def identify_plant(self, image_file: UploadedFile) -> Optional[Dict[str, Any]]:
    """Identify plant from image."""
    ...
```

**Testing:**
- [ ] mypy passes with zero errors: `mypy apps/plant_identification/`
- [ ] All existing tests pass: `python manage.py test`
```

### 8.3 Testing Emphasis for AI-Generated Code

**Critical:** AI-generated code requires rigorous testing to catch:
- Hallucinated API calls (AI invents non-existent functions)
- Logic errors in edge cases
- Security vulnerabilities
- Performance issues

#### Mandatory Testing Requirements

Every issue should include:

```markdown
## Testing Requirements

### Unit Tests (Required)
- [ ] Create `test_[feature_name].py` in appropriate tests/ directory
- [ ] Test happy path: Valid inputs return expected outputs
- [ ] Test error cases: Invalid inputs raise appropriate exceptions
- [ ] Test edge cases: Empty inputs, null values, boundary conditions
- [ ] Achieve 90%+ code coverage for new/modified code

### Integration Tests (For API/Service Changes)
- [ ] Test with real Django test client
- [ ] Test database interactions with PostgreSQL test DB
- [ ] Test Redis caching with test Redis instance
- [ ] Test external API mocking (Plant.id, PlantNet)

### Security Tests (For Security Fixes)
- [ ] Run static analysis: `bandit -r apps/plant_identification/`
- [ ] Run dependency scan: `safety check`
- [ ] Manual penetration test: Attempt to exploit vulnerability
- [ ] Verify fix doesn't introduce new vulnerabilities

### Performance Tests (For Optimization Changes)
- [ ] Benchmark before/after: `python test_performance.py`
- [ ] Profile memory usage: No memory leaks
- [ ] Test concurrent requests: No race conditions
- [ ] Monitor resource usage: CPU/memory within limits

### Verification Steps (Before Closing Issue)
- [ ] All tests pass: `python manage.py test --keepdb`
- [ ] Code review by human developer
- [ ] Manual testing in development environment
- [ ] Deploy to staging and verify
```

### 8.4 Claude Code Specific Tips

**Based on:** [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)

#### 1. Use Slash Commands in Issue Descriptions

```markdown
## Implementation Instructions for Claude Code

Run these commands to implement the fix:

1. `/read /backend/apps/plant_identification/services/plant_id_service.py` - Review current implementation
2. `/search "def identify_plant"` - Find all usages
3. Edit the file to add type hints (see example above)
4. `/test python manage.py test apps.plant_identification` - Run tests
5. `/lint mypy apps/plant_identification/` - Verify type hints
```

#### 2. Provide Context Files

```markdown
## Context for Claude Code

**Related Files to Review:**
- `/backend/apps/plant_identification/services/combined_identification_service.py` - Shows parallel API pattern
- `/backend/apps/plant_identification/constants.py` - Constants used in service
- `/backend/apps/plant_identification/tests/test_services.py` - Existing test patterns

**Documentation:**
- `/backend/docs/performance/week2-performance.md` - Performance optimization context
- `/backend/docs/development/LOGGING_STANDARDS.md` - Logging conventions
```

#### 3. Specify Expected Behavior

```markdown
## Expected Behavior After Fix

**Before:**
```bash
$ mypy apps/plant_identification/services/plant_id_service.py
apps/plant_identification/services/plant_id_service.py:45: error: Function is missing a return type annotation
Found 1 error in 1 file (checked 1 source file)
```

**After:**
```bash
$ mypy apps/plant_identification/services/plant_id_service.py
Success: no issues found in 1 source file
```

**User-Visible Changes:**
- None (internal code quality improvement only)

**Breaking Changes:**
- None (backward compatible)
```

---

## 9. Summary & Quick Reference

### Security Issue Quick Checklist

```markdown
- [ ] CVSS score calculated and documented
- [ ] Remediation timeline assigned based on severity
- [ ] Private disclosure for CRITICAL/HIGH vulnerabilities
- [ ] No exploit code in public issue
- [ ] Affected files listed with absolute paths
- [ ] Secure code examples provided
- [ ] Testing requirements specified
- [ ] References to CWE, OWASP, or CVE included
- [ ] Coordinated disclosure timeline planned
```

### Technical Debt Quick Checklist

```markdown
- [ ] Prioritization score calculated (Knowledge + Severity + Dependency - 3×Cost)
- [ ] Category assigned (No-brainer, Worthy Investment, Quick Win, Backlog)
- [ ] Current vs. desired state shown with code examples
- [ ] Impact on maintainability quantified
- [ ] Effort estimate provided (hours or story points)
- [ ] Acceptance criteria as checklist
- [ ] Testing strategy defined
- [ ] Dependencies and blockers identified
```

### AI-Friendly Issue Checklist

```markdown
- [ ] Absolute file paths from repository root
- [ ] Code examples for current and desired state
- [ ] Step-by-step implementation checklist
- [ ] Specific testing commands
- [ ] Context files listed for AI to review
- [ ] Expected before/after behavior shown
- [ ] Language identifiers on all code blocks (```python)
- [ ] Acceptance criteria as checkboxes
```

---

## 10. References & Further Reading

### Official Documentation
- [GitHub Security Advisories Best Practices](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/best-practices-for-writing-repository-security-advisories)
- [GitHub Coordinated Disclosure](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/about-coordinated-disclosure-of-security-vulnerabilities)
- [CISA BOD 19-02 Remediation Requirements](https://www.cisa.gov/news-events/directives/bod-19-02-vulnerability-remediation-requirements-internet-accessible-systems)
- [CVSS v3.1 Calculator](https://www.first.org/cvss/calculator/3-1)
- [CVSS v3.1 Examples](https://www.first.org/cvss/v3-1/examples)

### Django Security
- [Django Security Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Django Secret Key Rotation](https://adamj.eu/tech/2024/08/30/django-rotate-secret-key/)
- [GitGuardian Django Secret Key Remediation](https://www.gitguardian.com/remediation/django-secret-key)
- [Django Image Validation Vulnerability](https://insinuator.net/2014/05/django-image-validation-vulnerability/)

### Technical Debt Management
- [Ducalis Technical Debt Prioritization Framework](https://help.ducalis.io/knowledge-base/technical-debt-prioritization/)
- [Technical Debt Tracking & Tools](https://www.tiny.cloud/blog/technical-debt-tracking/)
- [5 Practical Tips for Prioritizing Technical Debt](https://help.ducalis.io/knowledge-base/5-tip-prioritizing-technical-debt/)

### Python Type Hints
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [django-stubs for Type Checking](https://github.com/typeddjango/django-stubs)
- [Python Type Hints Best Practices 2025](https://betterstack.com/community/guides/scaling-python/python-type-hints/)

### AI-Era Development
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Solving GitHub Issues with Claude Code](https://coder.com/blog/coding-with-claude-code/)
- [GitHub Copilot AI Pair Programming](https://github.com/features/copilot)

### Security Standards
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [NIST Common Vulnerability Scoring System](https://nvd.nist.gov/vuln-metrics/cvss)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-22
**Maintained By:** Plant ID Community Backend Team

