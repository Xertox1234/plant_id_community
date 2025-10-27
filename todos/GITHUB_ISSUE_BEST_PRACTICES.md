# GitHub Issue Best Practices for Plant ID Community

**Research Date:** October 27, 2025
**Context:** Converting 34 audit findings into GitHub issues for a Django + React + Flutter multi-platform project

---

## Table of Contents

1. [Issue Title Best Practices](#1-issue-title-best-practices)
2. [Issue Body Structure](#2-issue-body-structure)
3. [Label Strategy](#3-label-strategy)
4. [Issue Templates](#4-issue-templates)
5. [AI-Assisted Development Considerations](#5-ai-assisted-development-considerations)
6. [Security Issue Handling](#6-security-issue-handling)
7. [Project Organization](#7-project-organization)
8. [Examples for Our Audit Findings](#8-examples-for-our-audit-findings)

---

## 1. Issue Title Best Practices

### Conventional Commit Prefixes (Recommended)

Use conventional commit prefixes in issue titles for consistency and searchability:

| Prefix | Usage | Example |
|--------|-------|---------|
| `feat:` | New feature or enhancement | `feat: Add JWT token rotation mechanism` |
| `fix:` | Bug fix or correction | `fix: Prevent cache stampede in PlantNet API` |
| `security:` | Security vulnerability or improvement | `security: Implement rate limiting on login endpoint` |
| `perf:` | Performance improvement | `perf: Add database index for blog post queries` |
| `refactor:` | Code restructuring without feature changes | `refactor: Extract authentication logic to service layer` |
| `test:` | Test additions or improvements | `test: Add unit tests for JWT refresh flow` |
| `docs:` | Documentation updates | `docs: Document Redis caching strategy` |
| `chore:` | Maintenance tasks, dependency updates | `chore: Update Django to 5.2.7` |

### Character Length Guidelines

**Key Research Findings:**
- **Optimal:** 50-70 characters (aligns with git commit conventions)
- **Hard limit:** Keep under 72 characters when possible
- **GitHub search API limit:** 256 characters (affects searchability)
- **Practical recommendation:** Aim for 50-60 characters for best readability

**Format Pattern:**
```
[prefix]: [clear action verb] [specific component/area] [optional context]
```

**Good Examples:**
```
security: Implement account lockout after 10 failed login attempts (57 chars)
perf: Add GIN index to blog_post.search_vector field (54 chars)
fix: Handle JSON parsing error in BlogDetailPage content_blocks (63 chars)
```

**Bad Examples:**
```
Fix bug (too vague)
Security issue with the authentication system that needs to be addressed soon (too long, 76 chars)
Update code (no context)
```

### Writing Effective Titles

1. **Use imperative mood** - Write as if giving a command
   - Good: "Add rate limiting to API endpoints"
   - Bad: "Added rate limiting" or "Adds rate limiting"

2. **Be specific about the component/area**
   - Good: "security: Add rate limiting to login endpoint"
   - Bad: "security: Add rate limiting"

3. **Start with capital letter**
   - Good: "Fix cache invalidation in BlogCacheService"
   - Bad: "fix cache invalidation in BlogCacheService"

4. **No trailing punctuation**
   - Good: "Update Django REST Framework to 3.15.0"
   - Bad: "Update Django REST Framework to 3.15.0."

5. **Make it searchable**
   - Include key terms developers would search for
   - Example: "security: Implement JWT token blacklist on logout" (includes "JWT", "token", "blacklist", "logout")

---

## 2. Issue Body Structure

### Essential Sections for All Issues

```markdown
## Problem Statement
[Clear, concise description of the issue - 2-3 sentences]

## Current Behavior
[What currently happens - bullet points preferred]

## Expected Behavior
[What should happen instead]

## Proposed Solution
[Technical approach to solving the problem]

## Acceptance Criteria
- [ ] Specific, testable outcome 1
- [ ] Specific, testable outcome 2
- [ ] Specific, testable outcome 3
- [ ] All existing tests pass
- [ ] New tests added with >80% coverage

## Implementation Details
### Files to Modify
- `backend/apps/users/views.py` - Add rate limiting decorator
- `backend/apps/users/tests/test_rate_limiting.py` - Add test cases

### Technical Context
[Any relevant technical details, patterns to follow, constraints]

## Testing Strategy
[How this should be tested]

## Related Issues/PRs
- Related to #123
- Blocks #456
- Depends on #789

## Additional Context
[Optional: Screenshots, logs, research links, etc.]
```

### Bug Report Structure

```markdown
## Bug Description
[Clear description of the bug]

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- Platform: [Backend/Web/Mobile]
- OS: [e.g., macOS 14.0, Ubuntu 22.04]
- Browser: [if applicable, e.g., Chrome 118]
- Django version: [e.g., 5.2.7]
- Python version: [e.g., 3.12.1]

## Error Messages/Logs
```python
[Paste relevant error messages or stack traces]
```

## Screenshots
[If applicable]

## Possible Solution
[Optional: Your ideas on how to fix it]

## Related Issues
[Any related issues]
```

### Technical Debt Structure

```markdown
## Technical Debt Description
[Clear description of what needs improvement and WHY it matters]

## Current Impact
- [ ] Slows development velocity
- [ ] Increases bug risk
- [ ] Reduces code maintainability
- [ ] Creates security risk
- [ ] Impacts performance
- [ ] Other: [specify]

## Severity
[Low/Medium/High/Critical] - [Brief justification]

## Current State
[Description of current implementation]

## Desired State
[How it should be implemented]

## Refactoring Approach
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Benefits
- [Benefit 1]
- [Benefit 2]
- [Benefit 3]

## Risks
- [Risk 1 and mitigation]
- [Risk 2 and mitigation]

## Effort Estimate
[Small (<2 hours) / Medium (2-8 hours) / Large (1-3 days) / X-Large (>3 days)]

## Acceptance Criteria
- [ ] [Specific outcome 1]
- [ ] [Specific outcome 2]
- [ ] Tests remain passing
- [ ] No breaking changes to public APIs
```

---

## 3. Label Strategy

### Research-Backed Recommendations

**Key Principle:** Don't use too many labels per issue (3-5 max) - browsing issues with 5-10 colored labels is hard on eyes and reduces focus.

### Core Label Categories

#### 1. Priority Labels (Color: Red/Orange shades)

| Label | Color | Usage | SLA |
|-------|-------|-------|-----|
| `priority: P1 - critical` | `#d73a4a` (red) | Security vulnerabilities, production down, data loss | Fix within 24-48 hours |
| `priority: P2 - high` | `#d93f0b` (orange) | Significant bugs, important features, blocks other work | Fix within 1 week |
| `priority: P3 - medium` | `#fbca04` (yellow) | Standard features, non-critical bugs, improvements | Fix within 2-4 weeks |
| `priority: P4 - low` | `#0e8a16` (green) | Nice-to-have, optimizations, minor improvements | Backlog |

#### 2. Type Labels (Color: Blue shades)

| Label | Color | Usage |
|-------|-------|-------|
| `type: bug` | `#d73a4a` (red) | Something isn't working correctly |
| `type: feature` | `#0075ca` (blue) | New functionality or enhancement |
| `type: security` | `#b60205` (dark red) | Security vulnerability or improvement |
| `type: performance` | `#5319e7` (purple) | Performance optimization |
| `type: refactor` | `#fbca04` (yellow) | Code quality improvement, no functional change |
| `type: documentation` | `#0075ca` (blue) | Documentation updates |
| `type: test` | `#1d76db` (light blue) | Test coverage or test improvements |
| `type: tech-debt` | `#fbca04` (yellow) | Technical debt that needs addressing |

#### 3. Platform Labels (Color: Gray shades)

| Label | Color | Usage |
|-------|-------|-------|
| `platform: backend` | `#c5def5` (light blue) | Django/Python backend changes |
| `platform: web` | `#bfdadc` (light teal) | React web frontend changes |
| `platform: mobile` | `#d4c5f9` (light purple) | Flutter mobile app changes |
| `platform: infrastructure` | `#e4e669` (light yellow) | DevOps, deployment, CI/CD |

#### 4. Technology Labels (Color: Consistent with platform)

| Label | Color | Usage |
|-------|-------|-------|
| `tech: django` | `#0e8a16` (green) | Django-specific issues |
| `tech: react` | `#61dafb` (cyan) | React-specific issues |
| `tech: flutter` | `#02569B` (blue) | Flutter-specific issues |
| `tech: postgresql` | `#336791` (blue) | Database-related issues |
| `tech: redis` | `#d82c20` (red) | Cache-related issues |
| `tech: jwt` | `#000000` (black) | JWT authentication issues |
| `tech: wagtail` | `#43b1b0` (teal) | Wagtail CMS issues |

#### 5. Status Labels (Color: Purple shades)

| Label | Color | Usage |
|-------|-------|-------|
| `status: to-triage` | `#d876e3` (purple) | New issue, needs review |
| `status: needs-info` | `#d876e3` (purple) | Waiting for more information |
| `status: blocked` | `#b60205` (dark red) | Cannot proceed, dependency issue |
| `status: in-progress` | `#0052cc` (dark blue) | Currently being worked on |
| `status: ready` | `#0e8a16` (green) | Ready to be worked on |
| `status: needs-discussion` | `#d876e3` (purple) | Requires team discussion |

#### 6. Contribution Labels (Color: Green shades)

| Label | Color | Usage |
|-------|-------|-------|
| `good first issue` | `#7057ff` (purple) | Good for newcomers (GitHub special label) |
| `help wanted` | `#008672` (teal) | Extra attention needed (GitHub special label) |
| `needs-review` | `#0e8a16` (green) | Ready for code review |

#### 7. Effort Labels (Color: Teal shades)

| Label | Color | Usage |
|-------|-------|-------|
| `effort: small` | `#c2e0c6` (light green) | <2 hours |
| `effort: medium` | `#bfdadc` (light teal) | 2-8 hours |
| `effort: large` | `#f9d0c4` (light orange) | 1-3 days |
| `effort: x-large` | `#e99695` (light red) | >3 days |

### Label Usage Patterns

**For Our Audit Findings:**

```
P1 Critical Security (5 issues):
- priority: P1 - critical
- type: security
- platform: backend (or web/mobile)
- tech: [specific tech]
Example: security: P1, platform: backend, tech: django, tech: jwt

P2 High Priority (8 issues):
- priority: P2 - high
- type: security / type: performance
- platform: [specific platform]
- tech: [specific tech]

P3 Medium Priority (12 issues):
- priority: P3 - medium
- type: [bug/feature/refactor]
- platform: [specific platform]

P4 Low Priority (9 issues):
- priority: P4 - low
- type: [documentation/test/tech-debt]
- platform: [specific platform]
```

---

## 4. Issue Templates

### Template Location

Create templates in `.github/ISSUE_TEMPLATE/` directory:

```
.github/
└── ISSUE_TEMPLATE/
    ├── config.yml
    ├── 1-bug-report.yml
    ├── 2-feature-request.yml
    ├── 3-security-vulnerability.yml
    ├── 4-technical-debt.yml
    └── 5-documentation.yml
```

### Template: config.yml

```yaml
blank_issues_enabled: false
contact_links:
  - name: Security Vulnerability (Private)
    url: https://github.com/[username]/[repo]/security/advisories/new
    about: Report security vulnerabilities privately (90-day disclosure window)
  - name: Community Discussions
    url: https://github.com/[username]/[repo]/discussions
    about: Ask questions and discuss with the community
```

### Template: 1-bug-report.yml

```yaml
name: Bug Report
description: Report a bug or unexpected behavior
title: "fix: [Brief description of the bug]"
labels: ["type: bug", "status: to-triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thank you for reporting a bug! Please fill out this form to help us investigate.

  - type: textarea
    id: description
    attributes:
      label: Bug Description
      description: A clear and concise description of what the bug is
      placeholder: Tell us what you see!
    validations:
      required: true

  - type: textarea
    id: reproduction
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior
      placeholder: |
        1. Go to '...'
        2. Click on '...'
        3. Scroll down to '...'
        4. See error
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What did you expect to happen?
    validations:
      required: true

  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
      description: What actually happened?
    validations:
      required: true

  - type: dropdown
    id: platform
    attributes:
      label: Platform
      description: Which platform is affected?
      options:
        - Backend (Django)
        - Web Frontend (React)
        - Mobile (Flutter)
        - Multiple Platforms
        - Not Sure
    validations:
      required: true

  - type: textarea
    id: environment
    attributes:
      label: Environment Details
      description: |
        Please provide relevant environment details:
        - OS: [e.g., macOS 14.0, Ubuntu 22.04]
        - Browser: [if applicable]
        - Django version: [from requirements.txt]
        - Python version: [e.g., 3.12.1]
      placeholder: |
        OS: macOS 14.0
        Browser: Chrome 118
        Django: 5.2.7
        Python: 3.12.1

  - type: textarea
    id: logs
    attributes:
      label: Error Messages / Logs
      description: Paste any relevant error messages or stack traces
      render: python

  - type: textarea
    id: solution
    attributes:
      label: Possible Solution
      description: If you have ideas on how to fix this, share them here
      placeholder: Optional

  - type: textarea
    id: context
    attributes:
      label: Additional Context
      description: Add any other context, screenshots, or related issues
      placeholder: |
        Related issues: #123
        Screenshots: [attach files]
```

### Template: 2-feature-request.yml

```yaml
name: Feature Request
description: Suggest a new feature or enhancement
title: "feat: [Brief description of the feature]"
labels: ["type: feature", "status: needs-discussion"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for suggesting a new feature! Please provide details to help us evaluate it.

  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
      description: What problem does this feature solve? Who benefits from it?
      placeholder: As a [type of user], I want [goal] so that [benefit]
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How would you like this feature to work?
      placeholder: Describe your ideal solution
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: What other approaches have you thought about?
      placeholder: Describe alternative solutions or features

  - type: dropdown
    id: platform
    attributes:
      label: Platform
      description: Which platform should this feature be on?
      options:
        - Backend (Django)
        - Web Frontend (React)
        - Mobile (Flutter)
        - Multiple Platforms
        - Not Sure
    validations:
      required: true

  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance Criteria
      description: How do we know this feature is complete?
      placeholder: |
        - [ ] User can do X
        - [ ] System responds with Y
        - [ ] Tests cover Z scenario
    validations:
      required: true

  - type: dropdown
    id: priority
    attributes:
      label: Suggested Priority
      description: How important is this feature?
      options:
        - Critical (P1) - Blocks major functionality
        - High (P2) - Important for user experience
        - Medium (P3) - Nice to have
        - Low (P4) - Future consideration
    validations:
      required: true

  - type: textarea
    id: context
    attributes:
      label: Additional Context
      description: Mockups, examples from other apps, related issues
      placeholder: |
        Related issues: #123
        Example: [link to similar feature]
```

### Template: 3-security-vulnerability.yml

```yaml
name: Security Vulnerability (Public)
description: Report a security issue (use private advisories for critical issues)
title: "security: [Brief description without sensitive details]"
labels: ["type: security", "priority: P1 - critical", "status: to-triage"]
body:
  - type: markdown
    attributes:
      value: |
        ⚠️ **IMPORTANT**: For critical security vulnerabilities, please use [GitHub Private Security Advisories](https://github.com/[username]/[repo]/security/advisories/new) instead.

        This template is for non-critical security improvements or already-patched issues.

  - type: textarea
    id: vulnerability
    attributes:
      label: Vulnerability Description
      description: Describe the security issue without exposing exploitation details
      placeholder: Avoid including exploit code or sensitive implementation details
    validations:
      required: true

  - type: dropdown
    id: severity
    attributes:
      label: Severity Assessment
      description: Your assessment of severity (CVSS scale)
      options:
        - Critical (9.0-10.0) - Use private advisories instead
        - High (7.0-8.9)
        - Medium (4.0-6.9)
        - Low (0.1-3.9)
        - Informational
    validations:
      required: true

  - type: dropdown
    id: category
    attributes:
      label: Vulnerability Category
      description: What type of security issue is this?
      options:
        - Authentication/Authorization
        - Injection (SQL, XSS, etc.)
        - Cryptography
        - Session Management
        - Input Validation
        - Rate Limiting
        - Data Exposure
        - CSRF/CORS
        - Other
    validations:
      required: true

  - type: dropdown
    id: platform
    attributes:
      label: Affected Platform
      description: Which platform is vulnerable?
      options:
        - Backend (Django)
        - Web Frontend (React)
        - Mobile (Flutter)
        - Multiple Platforms
    validations:
      required: true

  - type: textarea
    id: impact
    attributes:
      label: Potential Impact
      description: What could an attacker achieve?
      placeholder: Describe potential harm without revealing exploitation steps
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How should this be fixed?
      placeholder: Suggest mitigation strategies
    validations:
      required: true

  - type: textarea
    id: references
    attributes:
      label: References
      description: Links to CVEs, OWASP guidelines, or security research
      placeholder: |
        - OWASP: [link]
        - Related CVE: [CVE-XXXX-XXXXX]
        - Research: [link]
```

### Template: 4-technical-debt.yml

```yaml
name: Technical Debt
description: Report code quality issues, refactoring needs, or architectural improvements
title: "refactor: [Brief description of technical debt]"
labels: ["type: tech-debt", "status: to-triage"]
body:
  - type: markdown
    attributes:
      value: |
        Technical debt includes code that works but could be improved for maintainability, performance, or clarity.

  - type: textarea
    id: description
    attributes:
      label: Technical Debt Description
      description: What needs improvement and why?
      placeholder: Describe the current state and why it's problematic
    validations:
      required: true

  - type: checkboxes
    id: impact
    attributes:
      label: Current Impact
      description: How does this debt affect the project?
      options:
        - label: Slows development velocity
        - label: Increases bug risk
        - label: Reduces code maintainability
        - label: Creates security risk
        - label: Impacts performance
        - label: Makes testing difficult
        - label: Other (describe below)

  - type: dropdown
    id: severity
    attributes:
      label: Severity
      description: How critical is this debt?
      options:
        - Critical - Actively causing problems
        - High - Will cause problems soon
        - Medium - Should be addressed
        - Low - Nice to have
    validations:
      required: true

  - type: textarea
    id: current-state
    attributes:
      label: Current State
      description: How is it currently implemented?
      placeholder: Describe the existing code or approach
    validations:
      required: true

  - type: textarea
    id: desired-state
    attributes:
      label: Desired State
      description: How should it be implemented?
      placeholder: Describe the ideal solution
    validations:
      required: true

  - type: textarea
    id: approach
    attributes:
      label: Refactoring Approach
      description: Step-by-step plan to address this debt
      placeholder: |
        1. Step one
        2. Step two
        3. Step three

  - type: textarea
    id: benefits
    attributes:
      label: Benefits of Addressing
      description: What improvements will result?
      placeholder: |
        - Benefit 1
        - Benefit 2

  - type: textarea
    id: risks
    attributes:
      label: Risks and Mitigations
      description: What could go wrong, and how do we prevent it?
      placeholder: |
        - Risk 1: [mitigation strategy]
        - Risk 2: [mitigation strategy]

  - type: dropdown
    id: effort
    attributes:
      label: Effort Estimate
      description: How long will this take?
      options:
        - Small (<2 hours)
        - Medium (2-8 hours)
        - Large (1-3 days)
        - X-Large (>3 days)
    validations:
      required: true

  - type: dropdown
    id: platform
    attributes:
      label: Platform
      description: Which platform does this affect?
      options:
        - Backend (Django)
        - Web Frontend (React)
        - Mobile (Flutter)
        - Multiple Platforms
        - Infrastructure
    validations:
      required: true

  - type: textarea
    id: files
    attributes:
      label: Files to Modify
      description: List the files that need changes
      placeholder: |
        - backend/apps/users/views.py
        - backend/apps/users/services/auth_service.py
```

---

## 5. AI-Assisted Development Considerations

### Research Findings (2024-2025)

**Key Insight from GitHub Copilot:** "AI failures are usually context failures, not model failures."

When GitHub assigns an issue to an AI coding agent:
1. It incorporates context from related issue/PR discussions
2. Follows custom repository instructions
3. Clones the repository and analyzes the codebase
4. Uses advanced RAG (Retrieval Augmented Generation) with GitHub code search

### Structuring Issues for AI Implementation

#### 1. Provide Explicit File Paths

```markdown
## Implementation Details

### Files to Create
- `backend/apps/users/services/rate_limiter.py` (new file)
- `backend/apps/users/tests/test_rate_limiter.py` (new file)

### Files to Modify
- `backend/apps/users/views.py` (lines 45-67: add rate limiting decorator)
- `backend/apps/users/serializers.py` (add rate limit exceeded error response)
- `backend/plant_community_backend/settings.py` (add RATE_LIMIT_* constants)
- `backend/requirements.txt` (add django-ratelimit==4.1.0)
```

#### 2. Include Code Context Examples

```markdown
## Code Context

### Current Implementation (views.py, lines 45-50)
```python
@api_view(['POST'])
@permission_classes([IsAuthenticatedOrAnonymousWithStrictRateLimit])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        # ... authentication logic
```

### Desired Implementation Pattern
Follow the pattern in `apps/plant_identification/services/plant_id_service.py` (lines 89-102)
for error handling and logging.
```

#### 3. Reference Existing Patterns

```markdown
## Patterns to Follow

1. **Service Layer Pattern**: Follow `apps/plant_identification/services/combined_identification_service.py`
   - All business logic in service methods
   - Type hints required (PEP 484)
   - Bracketed logging: `logger.info("[SERVICE_NAME] message")`

2. **Testing Pattern**: Follow `apps/users/tests/test_account_lockout.py`
   - Use `@override_settings` for configuration
   - Mock external dependencies
   - Arrange-Act-Assert structure

3. **Constants Pattern**: Add to `apps/users/constants.py`
   - NO magic numbers in code
   - Centralized configuration
   - Clear, uppercase names
```

#### 4. Specify Dependencies and Configuration

```markdown
## Dependencies Required

```python
# requirements.txt additions
django-ratelimit==4.1.0  # Rate limiting decorator
python-redis-lock==4.0.0  # Already installed, use for distributed locks
```

## Configuration Changes

```python
# settings.py additions (add to line ~450, after REDIS_URL config)
# Rate Limiting Configuration
RATE_LIMIT_LOGIN_ATTEMPTS = env.int('RATE_LIMIT_LOGIN_ATTEMPTS', default=5)
RATE_LIMIT_LOGIN_WINDOW = env.int('RATE_LIMIT_LOGIN_WINDOW', default=900)  # 15 minutes
RATE_LIMIT_REGISTRATION_ATTEMPTS = env.int('RATE_LIMIT_REGISTRATION_ATTEMPTS', default=3)
RATE_LIMIT_REGISTRATION_WINDOW = env.int('RATE_LIMIT_REGISTRATION_WINDOW', default=3600)  # 1 hour
```
```

#### 5. Clear Acceptance Criteria for Testing

```markdown
## Acceptance Criteria (AI-Testable)

### Functional Requirements
- [ ] After 5 failed login attempts from same IP, endpoint returns 429 status
- [ ] Rate limit window is 15 minutes (900 seconds)
- [ ] Successful login resets the rate limit counter
- [ ] Rate limit is per IP address, not per username
- [ ] Error response includes `Retry-After` header with seconds until reset

### Test Requirements
- [ ] Test case: 5 failures, 6th attempt returns 429
- [ ] Test case: 4 failures + 1 success + 4 failures = no rate limit (counter reset)
- [ ] Test case: IP1 hits limit, IP2 can still authenticate (isolation)
- [ ] Test case: Wait 15 minutes after limit, can authenticate again
- [ ] Test case: Verify Retry-After header calculation
- [ ] All existing tests still pass (`python manage.py test apps.users --keepdb`)
- [ ] Coverage >80% for new code (`coverage run -m pytest && coverage report`)

### Code Quality Requirements
- [ ] Type hints on all new functions (mypy passes)
- [ ] Logging uses bracketed prefix: `[RATE_LIMIT]`
- [ ] Constants defined in `apps/users/constants.py`, not hardcoded
- [ ] Follows existing error response format (DRF standard)
```

#### 6. Link to Related Code

```markdown
## Related Code References

### Similar Implementation (Reference)
See how circuit breakers are implemented in:
- `apps/plant_identification/services/combined_identification_service.py` (lines 78-95)
- Uses pybreaker library with Redis storage
- Pattern: module-level singleton with thread-safe initialization

### Error Handling Pattern (Follow)
See `apps/users/views.py` (lines 134-156):
- Standardized error responses
- Logging with request context
- IP address extraction from headers (X-Forwarded-For support)

### Testing Pattern (Follow)
See `apps/users/tests/test_account_lockout.py`:
- Mock Redis cache
- Test time-based behavior with freezegun
- Verify email notifications
```

---

## 6. Security Issue Handling

### GitHub's Coordinated Disclosure Process

**Standard Timeline:**
- **Day 0:** Private report received
- **Day 1-7:** Maintainer acknowledges and confirms vulnerability
- **Day 7-30:** Develop and test patch
- **Day 30:** Release patch publicly
- **Day 90:** Full disclosure deadline (if not resolved, researcher can publish)

### Security Issue Workflow

#### For Critical/High Severity (P1/P2)

1. **Use GitHub Private Security Advisories**
   - Location: `https://github.com/[username]/[repo]/security/advisories/new`
   - Only repository maintainers and reporter can see
   - Allows for discussion and patch development in private
   - Can invite collaborators to help fix

2. **Avoid Public Issues** until patched

3. **After Patch Released:**
   - Create public issue for tracking (without exploit details)
   - Link to published CVE (if applicable)
   - Document in security changelog

#### For Medium/Low Severity (P3/P4)

1. **Can use public issues** but:
   - Don't include exploit code
   - Don't include step-by-step attack instructions
   - Focus on the fix, not the attack

2. **Label appropriately:**
   - `type: security`
   - `priority: P2 - high` or `priority: P3 - medium`
   - `status: to-triage`

### Security Issue Template Features

```yaml
# Key sections from 3-security-vulnerability.yml
- Warning about using private advisories for critical issues
- Severity assessment (CVSS-based)
- Vulnerability category (Authentication, Injection, etc.)
- Potential impact (without revealing exploitation)
- Proposed solution (mitigation strategies)
- References to security standards (OWASP, CVEs)
```

### Security Labeling Strategy

```
Critical Security (Use Private Advisories):
- type: security
- priority: P1 - critical
- [DO NOT create public issue until patched]

High Security (Can be public, limit details):
- type: security
- priority: P2 - high
- status: to-triage
- platform: [specific]

Security Improvements (Public):
- type: security
- priority: P3 - medium
- [For hardening, not active vulnerabilities]
```

### SECURITY.md File

Create `.github/SECURITY.md`:

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**For critical security vulnerabilities, please use GitHub's private security advisories:**
1. Go to https://github.com/[username]/[repo]/security/advisories/new
2. Provide detailed information about the vulnerability
3. We will respond within 48 hours

**For security improvements or low-severity issues:**
1. Open a public issue using the "Security Vulnerability" template
2. Avoid including exploit code or detailed attack vectors
3. We will triage and respond within 1 week

## Disclosure Timeline

We follow a 90-day coordinated disclosure policy:
- **0-7 days:** Acknowledge and validate report
- **7-30 days:** Develop and test patch
- **30 days:** Release patch publicly
- **90 days:** Full disclosure deadline

## Security Best Practices

This project follows these security standards:
- OWASP Top 10 guidelines
- Django Security Best Practices
- JWT authentication with rotation
- Rate limiting on authentication endpoints
- HTTPS enforcement in production
- Regular dependency audits

## Hall of Fame

Contributors who responsibly disclose security issues:
[Will be listed here after disclosure]
```

---

## 7. Project Organization

### Milestones vs. Project Boards

Based on research, here's when to use each:

#### Milestones (Best for time-based releases)

**Use for:**
- Version releases (e.g., "v1.0 - Production Launch")
- Sprint planning (e.g., "Sprint 8 - Security Hardening")
- Deadline-focused work (e.g., "Q4 2025 Performance Goals")

**Features:**
- Due dates (track % completion)
- Issues from one or many repositories
- Sort by due date
- Automatic progress tracking

**Example Milestones for Our Audit:**
```
Milestone: Security Critical Fixes (P1)
Due Date: November 10, 2025
Issues: 5 (security vulnerabilities)
Progress: [====      ] 40% (2/5 complete)

Milestone: Authentication Hardening (P2)
Due Date: November 24, 2025
Issues: 8 (high priority security improvements)
Progress: [==        ] 25% (2/8 complete)
```

#### Project Boards (Best for workflow visualization)

**Use for:**
- Kanban workflow (To Do → In Progress → Done)
- Cross-repository work
- Flexible prioritization
- Team collaboration

**Recommended Columns:**
1. **Backlog** - Not yet ready to work on
2. **To Triage** - New issues needing assessment
3. **Ready** - Prioritized and ready to start
4. **In Progress** - Currently being worked on
5. **In Review** - PR submitted, awaiting review
6. **Done** - Completed and merged

**Example Project Board for Our Audit:**
```
Project: Security & Performance Audit Implementation

Backlog (9)          To Triage (5)        Ready (8)          In Progress (3)     In Review (2)       Done (7)
- P4 issues          - New security       - P2 issues        - JWT rotation      - Rate limiting     - Account lockout
- Documentation      - findings           - P3 issues        - Cache stampede    - Input validation  - CSRF hardening
- Future features    - Need discussion    - Prioritized      - Type hints        [PR #234]           - Secret validation
                                                             [3 assigned]        [PR #235]           [Completed: 7/34]
```

### Recommended Organization for Audit Findings

```markdown
## Phase 1: Setup (Week 1)
1. Create all 34 issues from audit findings
2. Apply labels: priority, type, platform, tech
3. Create milestones for each priority level
4. Create project board with columns
5. Add issues to project board (Backlog column)

## Phase 2: Triage (Week 1-2)
1. Move P1 (5 issues) to "Ready" column
2. Assign P1 issues to milestone "Security Critical Fixes"
3. Set milestone due date (2 weeks from now)
4. Create dependencies between related issues
5. Start work on P1 issues (move to "In Progress")

## Phase 3: Execution (Week 2-6)
1. Work through P1 → P2 → P3 → P4
2. Move issues through project board as they progress
3. Link PRs to issues in commit messages
4. Close issues via PR merge (use "Closes #123" in PR description)
5. Update milestones as priorities change

## Phase 4: Review (Ongoing)
1. Weekly review of project board
2. Re-triage new issues
3. Adjust priorities based on discoveries
4. Update documentation with lessons learned
```

---

## 8. Examples for Our Audit Findings

### Example 1: P1 Security Issue

```markdown
Title: security: Implement JWT token blacklist on logout

Labels:
- priority: P1 - critical
- type: security
- platform: backend
- tech: django
- tech: jwt
- effort: medium

## Problem Statement

Currently, JWT tokens remain valid until expiration even after user logout. This creates a security risk: if a token is compromised or stolen, an attacker can continue using it until expiration (24 hours). This violates the principle of least privilege and fails to invalidate sessions on logout.

## Current Behavior

1. User logs in → receives JWT access + refresh tokens
2. User logs out → frontend deletes tokens, but backend doesn't track logout
3. If attacker has copied token before logout, they can still use it for up to 24 hours
4. No mechanism to revoke compromised tokens

## Expected Behavior

1. User logs out → tokens are blacklisted immediately
2. Any request with blacklisted token receives 401 Unauthorized
3. Blacklisted tokens automatically expire from blacklist after natural expiration
4. Admin can manually blacklist tokens (e.g., after security incident)

## Proposed Solution

Implement Redis-based token blacklist using django-rest-framework-simplejwt's built-in BlacklistApp:

1. Add `rest_framework_simplejwt.token_blacklist` to INSTALLED_APPS
2. Run migration to create blacklist tables
3. Update logout endpoint to blacklist refresh token
4. Configure automatic cleanup of expired blacklisted tokens
5. Add monitoring for blacklist size (alert if grows too large)

## Acceptance Criteria

### Functional Requirements
- [ ] After logout, refresh token is added to blacklist
- [ ] Any API call with blacklisted token returns 401 status
- [ ] Blacklisted tokens are automatically removed after natural expiration
- [ ] Admin can manually blacklist tokens via Django admin
- [ ] Blacklist uses Redis for performance (no DB queries on every request)

### Test Requirements
- [ ] Test case: Logout blacklists token, subsequent use fails
- [ ] Test case: Access token expires naturally, removed from blacklist
- [ ] Test case: Blacklist survives server restart (persisted in Redis)
- [ ] Test case: Performance test - blacklist check <10ms
- [ ] All existing authentication tests pass
- [ ] Coverage >80% for new blacklist code

### Security Requirements
- [ ] Blacklist is write-only (no public endpoint to query blacklist)
- [ ] Blacklist entries include jti (JWT ID) only, not full token
- [ ] Logging includes attempt to use blacklisted token (security monitoring)

## Implementation Details

### Files to Modify
- `backend/apps/users/views.py` (add blacklist logic to logout view)
- `backend/apps/users/serializers.py` (add blacklist error response)
- `backend/apps/users/tests/test_authentication.py` (add blacklist tests)
- `backend/plant_community_backend/settings.py` (add token_blacklist app, configure)
- `backend/requirements.txt` (already has simplejwt, no changes needed)

### Files to Create
- Migration: `backend/apps/users/migrations/000X_add_token_blacklist.py` (auto-generated)

### Technical Context

**Pattern to Follow:**
- Use djangorestframework-simplejwt's built-in BlacklistApp (already in dependencies)
- Configure `BLACKLIST_AFTER_ROTATION = True` for automatic blacklist on refresh
- Use Redis backend for OutstandingToken model (faster than PostgreSQL)

**Reference Implementation:**
```python
# apps/users/views.py
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Blacklist the refresh token
        token = RefreshToken(refresh_token)
        token.blacklist()

        logger.info(f"[AUTH] Token blacklisted for user {request.user.id}")
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)

    except TokenError as e:
        logger.warning(f"[AUTH] Token blacklist failed: {e}")
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )
```

**Settings Configuration:**
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'rest_framework_simplejwt.token_blacklist',
]

SIMPLE_JWT = {
    # ... existing config ...
    'BLACKLIST_AFTER_ROTATION': True,  # Auto-blacklist on refresh
    'ROTATE_REFRESH_TOKENS': True,
}

# Redis cache for outstanding tokens (performance optimization)
CACHES['token_blacklist'] = {
    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    'LOCATION': REDIS_URL,
    'KEY_PREFIX': 'token_blacklist',
    'TIMEOUT': None,  # Tokens manage their own expiration
}
```

## Testing Strategy

```bash
# Run authentication tests
python manage.py test apps.users.tests.test_authentication --keepdb -v 2

# Verify blacklist table created
python manage.py migrate --plan | grep blacklist

# Check Redis for blacklisted tokens
redis-cli keys "token_blacklist:*"

# Performance test (should be <10ms)
# See apps/users/tests/test_token_blacklist_performance.py
```

## Security Impact

**Before:**
- Compromised tokens valid for 24 hours post-logout
- No way to revoke stolen tokens
- Security incident response time: 24 hours (wait for expiration)

**After:**
- Tokens immediately invalid on logout
- Manual revocation possible via admin
- Security incident response time: <1 minute (immediate blacklist)

## Related Issues/PRs

- Related to #234 (JWT rotation mechanism)
- Blocks #235 (Forced logout of all sessions)
- Depends on #236 (Redis cache configuration complete)

## Additional Context

**References:**
- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- djangorestframework-simplejwt docs: https://django-rest-framework-simplejwt.readthedocs.io/en/latest/blacklist_app.html
- NIST SP 800-63B (Authentication): https://pages.nist.gov/800-63-3/sp800-63b.html

**Effort Estimate:**
- Implementation: 4-6 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- **Total: Medium (1 day)**
```

---

### Example 2: P2 Performance Issue

```markdown
Title: perf: Add database index for blog post full-text search

Labels:
- priority: P2 - high
- type: performance
- platform: backend
- tech: django
- tech: postgresql
- effort: small

## Problem Statement

Blog post search queries are slow (300-800ms) due to sequential scans on the `search_vector` field. With 100+ blog posts, search performance will degrade linearly. Users expect search results in <100ms.

## Current Behavior

```sql
-- Current query plan (no index)
EXPLAIN ANALYZE SELECT * FROM blog_blogpostpage
WHERE search_vector @@ to_tsquery('plant care');

Seq Scan on blog_blogpostpage (cost=0.00..142.50 rows=1 width=1024) (actual time=387.234..387.456 rows=12 loops=1)
  Filter: (search_vector @@ to_tsquery('plant care'::text))
Planning Time: 2.134 ms
Execution Time: 387.567 ms
```

Query performance: **300-800ms** (unacceptable for search)

## Expected Behavior

```sql
-- With GIN index
Bitmap Heap Scan on blog_blogpostpage (cost=12.34..38.67 rows=12 width=1024) (actual time=3.456..3.789 rows=12 loops=1)
  Recheck Cond: (search_vector @@ to_tsquery('plant care'::text))
  ->  Bitmap Index Scan on idx_blog_post_search_vector (cost=0.00..12.34 rows=12 width=0) (actual time=2.987..2.987 rows=12 loops=1)
        Index Cond: (search_vector @@ to_tsquery('plant care'::text))
Planning Time: 0.567 ms
Execution Time: 3.892 ms
```

Query performance: **<10ms** (100x faster)

## Proposed Solution

Add PostgreSQL GIN (Generalized Inverted Index) index to `search_vector` field in BlogPostPage model:

1. Create migration with GIN index
2. Run migration on development database
3. Verify query plan uses index
4. Benchmark before/after performance
5. Add similar indexes to other searchable models (BlogAuthor, BlogCategory)

## Acceptance Criteria

### Functional Requirements
- [ ] GIN index created on `blog_blogpostpage.search_vector` field
- [ ] PostgreSQL query planner uses index for full-text search queries
- [ ] Index is only created on PostgreSQL (graceful skip on SQLite for tests)
- [ ] Index creation doesn't block database writes (use CONCURRENTLY)

### Performance Requirements
- [ ] Search queries complete in <10ms (90th percentile)
- [ ] Search queries complete in <50ms (99th percentile)
- [ ] Index size <100MB for 10,000 blog posts
- [ ] No performance regression on write operations

### Test Requirements
- [ ] Test case: Query plan verification (uses index scan, not seq scan)
- [ ] Test case: Performance benchmark (before/after comparison)
- [ ] Test case: Migration runs successfully on PostgreSQL
- [ ] Test case: Migration skips gracefully on SQLite (dev environment)
- [ ] All existing blog tests pass

## Implementation Details

### Files to Create
- `backend/apps/blog/migrations/000X_add_search_gin_index.py` (new migration)

### Files to Modify
- None (this is a database-only change)

### Technical Context

**Pattern to Follow:**
See existing GIN index migration in `apps/plant_identification/migrations/0012_add_performance_indexes.py`:

```python
# Reference: apps/plant_identification/migrations/0012_add_performance_indexes.py
from django.db import migrations, models
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY

    dependencies = [
        ('blog', '000X_previous_migration'),
    ]

    operations = [
        # Check if PostgreSQL before creating GIN index
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
                ) THEN
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_blog_post_search_vector
                    ON blog_blogpostpage USING GIN (search_vector);
                END IF;
            END
            $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS idx_blog_post_search_vector;",
            # Graceful skip on SQLite
            state_operations=[
                migrations.RunSQL.noop if 'sqlite' in connection.vendor else migrations.RunSQL(...)
            ]
        ),
    ]
```

**Key Points:**
1. Use `CONCURRENTLY` to avoid blocking writes during index creation
2. Check for `pg_trgm` extension (required for GIN on tsvector)
3. Use `IF NOT EXISTS` to make migration idempotent
4. Gracefully skip on SQLite (raises warning, doesn't fail)
5. Set `atomic = False` (required for CONCURRENTLY)

### Index Naming Convention
Follow existing pattern: `idx_[table]_[column]_[type]`
- Example: `idx_blog_post_search_vector_gin`

## Testing Strategy

```bash
# 1. Create migration
python manage.py makemigrations blog --name add_search_gin_index

# 2. Verify migration syntax
python manage.py sqlmigrate blog 000X

# 3. Run migration
python manage.py migrate blog

# 4. Verify index created
psql plant_community -c "\d+ blog_blogpostpage"
# Should show: idx_blog_post_search_vector | gin | search_vector

# 5. Test query plan
psql plant_community -c "EXPLAIN ANALYZE SELECT * FROM blog_blogpostpage WHERE search_vector @@ to_tsquery('plant');"
# Should show: Bitmap Index Scan on idx_blog_post_search_vector

# 6. Benchmark performance
python manage.py shell
>>> from django.test.utils import CaptureQueriesContext
>>> from django.db import connection
>>> from apps.blog.models import BlogPostPage
>>>
>>> with CaptureQueriesContext(connection) as queries:
...     list(BlogPostPage.objects.filter(search_vector='plant'))
>>>
>>> print(f"Query time: {queries[0]['time']}s")
# Should be: <0.010s (10ms)

# 7. Run all tests
python manage.py test apps.blog --keepdb -v 2
```

## Performance Impact

**Current Performance:**
```
Search Query Time (100 blog posts):
- Average: 450ms
- 90th percentile: 687ms
- 99th percentile: 798ms
Database Load: High (sequential scans)
```

**Expected Performance (After GIN Index):**
```
Search Query Time (100 blog posts):
- Average: 5ms (90x faster)
- 90th percentile: 8ms (85x faster)
- 99th percentile: 12ms (65x faster)
Database Load: Low (index scans)
```

**At Scale (10,000 blog posts):**
```
Without Index:
- Sequential scan: 30-50 seconds (unusable)

With GIN Index:
- Index scan: 10-20ms (constant time)
```

## Related Issues/PRs

- Related to #245 (Blog search UI improvements) - This unblocks that
- Similar to #189 (GIN indexes for plant identification) - Same pattern
- Part of milestone "Performance Optimization Sprint" (Due: Nov 24, 2025)

## Additional Context

**References:**
- PostgreSQL GIN Indexes: https://www.postgresql.org/docs/current/textsearch-indexes.html
- Django Full-Text Search: https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/
- Existing implementation: `backend/apps/plant_identification/migrations/0012_add_performance_indexes.py`

**Effort Estimate:**
- Migration creation: 30 minutes
- Testing and verification: 1 hour
- Documentation: 30 minutes
- **Total: Small (2 hours)**

**Index Size Estimation:**
For 10,000 blog posts (avg 1,000 words each):
- Uncompressed tsvector: ~50MB
- GIN index: ~75MB (1.5x tsvector size)
- Acceptable for performance gain (100x faster queries)
```

---

### Example 3: P3 Technical Debt Issue

```markdown
Title: refactor: Extract authentication logic to service layer

Labels:
- priority: P3 - medium
- type: tech-debt
- platform: backend
- tech: django
- effort: large

## Technical Debt Description

Authentication logic is currently mixed into view functions, violating separation of concerns and making testing difficult. Business logic (account lockout, rate limiting, JWT generation) is tightly coupled to request handling, preventing reuse across different interfaces (API, GraphQL, CLI).

## Current Impact

- [x] Slows development velocity (duplicate code across views)
- [x] Increases bug risk (logic changes require updates in multiple places)
- [x] Reduces code maintainability (views are 300+ lines, hard to read)
- [ ] Creates security risk
- [ ] Impacts performance
- [x] Makes testing difficult (require request mocking for unit tests)

## Severity

**Medium** - Not causing immediate problems, but will slow future development. As we add more authentication features (OAuth, 2FA), this debt will compound.

## Current State

Authentication logic is scattered across:
1. `apps/users/views.py` (450 lines, includes business logic)
2. `apps/users/serializers.py` (validation + JWT generation mixed)
3. `apps/users/models.py` (some account lockout logic)

Example of current coupling:
```python
# apps/users/views.py (lines 67-124)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # Business logic mixed with view logic:
        user = authenticate(request, username=username, password=password)
        if user is None:
            # Account lockout logic here (should be in service)
            failed_attempts = cache.get(f'login_attempts:{username}', 0)
            failed_attempts += 1
            cache.set(f'login_attempts:{username}', failed_attempts, timeout=900)

            if failed_attempts >= 10:
                # Email notification logic here (should be in service)
                send_lockout_email.delay(user_id=...)

            return Response({'error': 'Invalid credentials'}, status=401)

        # JWT generation logic here (should be in service)
        refresh = RefreshToken.for_user(user)
        # ... 30 more lines of JWT logic ...
```

**Problems:**
1. View function does too much (100+ lines)
2. Can't unit test authentication logic without mocking Django request
3. Can't reuse authentication logic in other contexts (GraphQL, CLI)
4. Difficult to add new features (OAuth, 2FA) without bloating views further

## Desired State

Service layer handles all authentication business logic:

```python
# apps/users/services/auth_service.py (new file)
from typing import Optional, Dict, Any
from django.contrib.auth.models import User
from apps.users.services.lockout_service import AccountLockoutService
from apps.users.services.jwt_service import JWTService

class AuthenticationService:
    """Service for handling authentication business logic."""

    def __init__(self):
        self.lockout_service = AccountLockoutService()
        self.jwt_service = JWTService()

    def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticate user with username/password.

        Returns dict with 'user' and 'tokens' keys on success,
        or 'error' key on failure.
        """
        # Check if account is locked
        if self.lockout_service.is_locked(username):
            logger.warning(f"[AUTH] Login attempt for locked account: {username}")
            return {
                'error': 'Account locked',
                'lockout_duration': self.lockout_service.get_remaining_lockout(username)
            }

        # Authenticate
        user = authenticate(username=username, password=password)

        if user is None:
            # Handle failed attempt
            self.lockout_service.record_failed_attempt(username, ip_address)
            logger.info(f"[AUTH] Failed login attempt for {username}")
            return {'error': 'Invalid credentials'}

        # Generate tokens
        tokens = self.jwt_service.generate_tokens(user)

        # Clear failed attempts on success
        self.lockout_service.clear_failed_attempts(username)

        logger.info(f"[AUTH] Successful login for {username}")
        return {'user': user, 'tokens': tokens}
```

```python
# apps/users/views.py (simplified)
from apps.users.services.auth_service import AuthenticationService

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Handle login API endpoint."""
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    # Extract IP address
    ip_address = get_client_ip(request)

    # Delegate to service layer
    auth_service = AuthenticationService()
    result = auth_service.authenticate_user(
        username=serializer.validated_data['username'],
        password=serializer.validated_data['password'],
        ip_address=ip_address
    )

    if 'error' in result:
        return Response({'error': result['error']}, status=401)

    # Return success response
    return Response({
        'user': UserSerializer(result['user']).data,
        'access_token': result['tokens']['access'],
        'refresh_token': result['tokens']['refresh'],
    })
```

**Benefits:**
1. View is 20 lines instead of 100+ lines
2. Business logic is testable without HTTP mocking
3. Logic is reusable in other contexts (GraphQL, CLI, webhooks)
4. Easier to add new features (OAuth, 2FA) to service layer
5. Follows existing project pattern (plant_identification uses service layer)

## Refactoring Approach

### Phase 1: Create Service Layer (Week 1)
1. Create `apps/users/services/` directory
2. Create `AuthenticationService` class (main orchestrator)
3. Create `AccountLockoutService` class (extract from views)
4. Create `JWTService` class (extract from serializers)
5. Add type hints to all service methods
6. Add comprehensive docstrings
7. Add unit tests for each service (no HTTP dependencies)

### Phase 2: Migrate Views (Week 2)
1. Update `login_view` to use `AuthenticationService`
2. Update `logout_view` to use `JWTService`
3. Update `refresh_token_view` to use `JWTService`
4. Update `registration_view` to use `AuthenticationService`
5. Remove duplicated logic from views
6. Verify all integration tests still pass

### Phase 3: Cleanup (Week 2)
1. Remove old authentication logic from serializers
2. Update documentation with service layer patterns
3. Add constants to `apps/users/constants.py`
4. Update tests to use services directly where appropriate

## Benefits of Addressing

1. **Development Velocity:** New auth features take hours instead of days
   - Example: Adding OAuth would touch 1 file (service) instead of 5 files (views, serializers, models, etc.)

2. **Testing:** Unit tests are 3x faster without HTTP mocking
   - Current: 0.3s per test (with Django test client)
   - After: 0.1s per test (pure Python, no HTTP)

3. **Code Reusability:** Can add GraphQL/gRPC APIs without rewriting auth logic

4. **Maintainability:** Follows Single Responsibility Principle
   - Views handle HTTP → Business logic separated
   - Easier onboarding for new developers

5. **Bug Risk Reduction:** Logic in one place
   - Current: Bug fixes require changes in 3-5 files
   - After: Bug fixes require changes in 1 file

## Risks and Mitigations

1. **Risk:** Breaking existing API endpoints during refactor
   - **Mitigation:**
     - Keep integration tests running throughout refactor
     - Refactor one endpoint at a time, not all at once
     - Use feature flags to toggle between old/new implementation

2. **Risk:** Performance regression from extra abstraction layer
   - **Mitigation:**
     - Services are simple orchestrators, no significant overhead
     - Benchmark before/after (target: <5% difference)
     - Profile hot paths with django-silk

3. **Risk:** Increased complexity for simple cases
   - **Mitigation:**
     - Services provide high-level methods for common cases
     - Optional low-level methods for advanced use cases
     - Clear documentation with examples

## Effort Estimate

**Large (3 days)** - Broken down:
- Phase 1 (Service creation): 1.5 days
  - AuthenticationService: 4 hours
  - AccountLockoutService: 3 hours
  - JWTService: 3 hours
  - Unit tests: 4 hours
- Phase 2 (View migration): 1 day
  - Migrate 4 views: 6 hours
  - Integration tests: 2 hours
- Phase 3 (Cleanup): 0.5 days
  - Remove old code: 2 hours
  - Documentation: 2 hours

## Acceptance Criteria

### Code Quality
- [ ] All authentication logic moved to service layer
- [ ] Views are <50 lines each (just HTTP handling)
- [ ] Type hints on all service methods (mypy passes)
- [ ] Docstrings on all public methods (Google style)
- [ ] Constants extracted to `apps/users/constants.py`
- [ ] Logging uses bracketed prefix: `[AUTH]`

### Testing
- [ ] 20+ unit tests for services (no HTTP dependencies)
- [ ] All integration tests pass (API endpoints work)
- [ ] Coverage >85% for service layer
- [ ] Test execution time improves (faster without HTTP mocking)

### Functionality
- [ ] No breaking changes to API endpoints
- [ ] All existing features work identically
- [ ] Response formats unchanged
- [ ] Error messages unchanged

### Documentation
- [ ] Service layer documented in `backend/docs/architecture/`
- [ ] Examples added to `backend/docs/development/`
- [ ] Updated CLAUDE.md with service layer patterns

## Platform

**Backend (Django)**

## Files to Create

```
backend/apps/users/services/
├── __init__.py
├── auth_service.py (AuthenticationService - 200 lines)
├── lockout_service.py (AccountLockoutService - 150 lines)
├── jwt_service.py (JWTService - 100 lines)
└── rate_limit_service.py (RateLimitService - 100 lines)

backend/apps/users/tests/
├── test_auth_service.py (unit tests - 300 lines)
├── test_lockout_service.py (unit tests - 250 lines)
├── test_jwt_service.py (unit tests - 150 lines)
└── test_rate_limit_service.py (unit tests - 150 lines)
```

## Files to Modify

```
backend/apps/users/
├── views.py (reduce from 450 lines → 200 lines)
├── serializers.py (reduce from 300 lines → 150 lines)
└── constants.py (add service-layer constants)
```

## Related Issues/PRs

- Related to #234 (JWT token blacklist) - Will integrate with JWTService
- Related to #235 (Account lockout email) - Will integrate with AccountLockoutService
- Follows pattern from #189 (Plant ID service layer refactor) - Same approach
- Part of milestone "Code Quality Sprint" (Due: Dec 15, 2025)

## Additional Context

**References:**
- **Existing Pattern:** `apps/plant_identification/services/` - Follow this structure
- **Django Service Layer Pattern:** https://www.dabapps.com/insights/django-models-and-encapsulation/
- **Type Hints Guide:** https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html
- **Project Documentation:** `backend/docs/architecture/analysis.md` (Service Layer Pattern section)

**Similar Refactoring Success:**
When we refactored plant identification to service layer (commit f4c8fc3):
- Views reduced from 600 lines → 250 lines (58% reduction)
- Test execution time improved 40% (no HTTP mocking)
- Added 3 new features in 2 weeks (would have taken 4 weeks before)

**Team Discussion:**
This is a significant refactor. Please review the approach before I start implementation. Questions:
1. Do we want to introduce dependency injection for services?
2. Should services be singletons or instantiated per request?
3. Any additional services needed (e.g., PermissionService, SessionService)?
```

---

## Summary: Quick Reference

### Issue Title Format
```
[prefix]: [action verb] [component] [optional context]
Length: 50-70 characters (max 72)
```

### Labels to Create (34 total)
**Priority (4):** P1-critical, P2-high, P3-medium, P4-low
**Type (8):** bug, feature, security, performance, refactor, documentation, test, tech-debt
**Platform (4):** backend, web, mobile, infrastructure
**Technology (7):** django, react, flutter, postgresql, redis, jwt, wagtail
**Status (6):** to-triage, needs-info, blocked, in-progress, ready, needs-discussion
**Contribution (3):** good first issue, help wanted, needs-review
**Effort (4):** small, medium, large, x-large

### Issue Templates to Create (5)
1. Bug Report (1-bug-report.yml)
2. Feature Request (2-feature-request.yml)
3. Security Vulnerability (3-security-vulnerability.yml)
4. Technical Debt (4-technical-debt.yml)
5. Documentation (5-documentation.yml)

### For AI-Assisted Development
1. Include explicit file paths
2. Provide code context examples
3. Reference existing patterns
4. Specify dependencies and configuration
5. Clear, testable acceptance criteria
6. Link to related code

### For Security Issues
- **Critical:** Use private advisories
- **High/Medium:** Public with limited details
- **90-day disclosure timeline**
- Create SECURITY.md policy file

### Project Organization
- **Milestones:** Time-based releases (e.g., "Security Critical Fixes - Due Nov 10")
- **Project Boards:** Workflow visualization (Backlog → To Triage → Ready → In Progress → Review → Done)
- **Link issues to PRs:** Use "Closes #123" in PR descriptions

---

## Next Steps for Our Audit

1. **Create label set** (34 labels defined above)
2. **Create issue templates** (5 YAML files)
3. **Create SECURITY.md** policy file
4. **Convert audit findings** to 34 issues using patterns above
5. **Create milestones** for each priority level
6. **Create project board** for tracking progress
7. **Start with P1 issues** (5 critical security fixes)

---

**Document Version:** 1.0
**Last Updated:** October 27, 2025
**Maintained by:** William Tower
**Project:** Plant ID Community (Django + React + Flutter)
