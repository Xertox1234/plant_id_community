# GitHub Issue Setup Implementation Checklist

**Goal:** Convert 34 audit findings into well-structured GitHub issues
**Estimated Time:** 6.5 hours total
**Project:** Plant ID Community

---

## Phase 1: Label Creation (30 minutes)

### Create Label CSV File

Create `labels.csv`:

```csv
name,color,description
priority: P1 - critical,d73a4a,Critical security vulnerabilities or production-breaking issues
priority: P2 - high,d93f0b,Important features or significant bugs
priority: P3 - medium,fbca04,Standard features or non-critical improvements
priority: P4 - low,0e8a16,Nice-to-have or minor improvements
type: bug,d73a4a,Something isn't working correctly
type: feature,0075ca,New functionality or enhancement
type: security,b60205,Security vulnerability or improvement
type: performance,5319e7,Performance optimization
type: refactor,fbca04,Code quality improvement without functional changes
type: documentation,0075ca,Documentation updates
type: test,1d76db,Test coverage or test improvements
type: tech-debt,fbca04,Technical debt that needs addressing
platform: backend,c5def5,Django/Python backend changes
platform: web,bfdadc,React web frontend changes
platform: mobile,d4c5f9,Flutter mobile app changes
platform: infrastructure,e4e669,DevOps deployment CI/CD
tech: django,0e8a16,Django-specific issues
tech: react,61dafb,React-specific issues
tech: flutter,02569B,Flutter-specific issues
tech: postgresql,336791,Database-related issues
tech: redis,d82c20,Cache-related issues
tech: jwt,000000,JWT authentication issues
tech: wagtail,43b1b0,Wagtail CMS issues
status: to-triage,d876e3,New issue needs review
status: needs-info,d876e3,Waiting for more information
status: blocked,b60205,Cannot proceed dependency issue
status: in-progress,0052cc,Currently being worked on
status: ready,0e8a16,Ready to be worked on
status: needs-discussion,d876e3,Requires team discussion
good first issue,7057ff,Good for newcomers
help wanted,008672,Extra attention needed
needs-review,0e8a16,Ready for code review
effort: small,c2e0c6,Less than 2 hours
effort: medium,bfdadc,2-8 hours
effort: large,f9d0c4,1-3 days
effort: x-large,e99695,More than 3 days
```

### Create Labels with GitHub CLI

```bash
# Install GitHub CLI (if not already installed)
brew install gh  # macOS
# or: sudo apt install gh  # Linux
# or: Download from https://cli.github.com/

# Authenticate
gh auth login

# Navigate to project directory
cd /Users/williamtower/projects/plant_id_community

# Create labels from CSV
tail -n +2 labels.csv | while IFS=, read -r name color description; do
  gh label create "$name" --color "$color" --description "$description" --force
done

# Verify labels created
gh label list
```

**Checkpoint:** You should see 36 labels in your repository.

---

## Phase 2: Issue Template Creation (1 hour)

### Create Directory Structure

```bash
cd /Users/williamtower/projects/plant_id_community
mkdir -p .github/ISSUE_TEMPLATE
```

### Create config.yml

File: `.github/ISSUE_TEMPLATE/config.yml`

```yaml
blank_issues_enabled: false
contact_links:
  - name: Security Vulnerability (Private)
    url: https://github.com/Xertox1234/plant_id_community/security/advisories/new
    about: Report critical security vulnerabilities privately (90-day disclosure)
  - name: Community Discussions
    url: https://github.com/Xertox1234/plant_id_community/discussions
    about: Ask questions and discuss with the community
```

### Create 1-bug-report.yml

File: `.github/ISSUE_TEMPLATE/1-bug-report.yml`

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

### Create 2-feature-request.yml

File: `.github/ISSUE_TEMPLATE/2-feature-request.yml`

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

### Create 3-security-vulnerability.yml

File: `.github/ISSUE_TEMPLATE/3-security-vulnerability.yml`

```yaml
name: Security Vulnerability (Public)
description: Report a non-critical security issue (use private advisories for critical)
title: "security: [Brief description without sensitive details]"
labels: ["type: security", "priority: P2 - high", "status: to-triage"]
body:
  - type: markdown
    attributes:
      value: |
        ⚠️ **IMPORTANT**: For critical security vulnerabilities (CVSS ≥7.0), please use [GitHub Private Security Advisories](https://github.com/Xertox1234/plant_id_community/security/advisories/new) instead.

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
        - High (7.0-8.9) - Consider private advisories
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
        - Dependency Vulnerability
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

### Create 4-technical-debt.yml

File: `.github/ISSUE_TEMPLATE/4-technical-debt.yml`

```yaml
name: Technical Debt
description: Report code quality issues or refactoring needs
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

### Create SECURITY.md

File: `.github/SECURITY.md`

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

### For Critical Security Vulnerabilities (CVSS ≥7.0)

**Please use GitHub's private security advisories:**

1. Go to https://github.com/Xertox1234/plant_id_community/security/advisories/new
2. Provide detailed information about the vulnerability:
   - Description of the issue
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested fix (if you have one)
3. We will respond within **48 hours**

### For Security Improvements or Low-Severity Issues (CVSS <7.0)

1. Open a public issue using the "Security Vulnerability" template
2. Avoid including exploit code or detailed attack vectors
3. We will triage and respond within **1 week**

## Disclosure Timeline

We follow a **90-day coordinated disclosure policy**:

- **0-7 days:** Acknowledge and validate report
- **7-30 days:** Develop and test patch
- **30 days:** Release patch publicly (target)
- **90 days:** Full disclosure deadline (if not resolved, researcher may publish)

## Security Best Practices

This project follows these security standards:

- **OWASP Top 10 Guidelines**
- **Django Security Best Practices**
- **JWT Authentication** with token rotation and blacklisting
- **Rate Limiting** on authentication endpoints
- **Account Lockout** after failed login attempts
- **HTTPS Enforcement** in production
- **CSRF Protection** on all state-changing operations
- **XSS Prevention** with DOMPurify sanitization
- **Regular Dependency Audits** (automated with Dependabot)

## Security Features Implemented

### Backend (Django)
- JWT authentication with refresh token rotation
- Token blacklist on logout
- Account lockout after 10 failed login attempts
- Rate limiting: 5 attempts per 15 minutes (login), 3 attempts per hour (registration)
- IP spoofing protection (X-Forwarded-For validation)
- Circuit breakers on external API calls
- Secret key validation (50+ characters, no insecure patterns)
- Environment-aware authentication (strict in production)

### Web Frontend (React)
- HTTPS enforcement in production
- CSRF token on all API calls
- XSS prevention with DOMPurify
- Secure cookie handling (httpOnly, secure, sameSite)
- Input validation and sanitization
- Sentry error tracking with privacy settings

### Mobile (Flutter)
- (Implementation in progress)

## Vulnerability Disclosure History

No vulnerabilities have been publicly disclosed for this project yet.

## Hall of Fame

We appreciate responsible security researchers who help us keep this project secure. Contributors who responsibly disclose vulnerabilities will be acknowledged here (with permission):

- (None yet)

## Contact

For security questions or concerns not related to vulnerabilities, contact:
- Email: [your-email@example.com]
- GitHub: [@Xertox1234](https://github.com/Xertox1234)

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security Documentation](https://docs.djangoproject.com/en/stable/topics/security/)
- [React Security Best Practices](https://react.dev/learn/reacting-to-input-with-state#security)
- [NIST SP 800-63B (Authentication)](https://pages.nist.gov/800-63-3/sp800-63b.html)
```

### Commit Templates

```bash
cd /Users/williamtower/projects/plant_id_community
git add .github/
git commit -m "chore: Add GitHub issue templates and security policy

- Add 36 labels (priority, type, platform, tech, status, effort)
- Add 4 YAML issue templates (bug, feature, security, tech-debt)
- Add SECURITY.md with coordinated disclosure policy
- Configure issue template selection (config.yml)

Follows GitHub best practices research (Oct 2025)
"
```

**Checkpoint:** Issue templates should now appear when creating new issues.

---

## Phase 3: Milestone Creation (15 minutes)

### Create Milestones

```bash
cd /Users/williamtower/projects/plant_id_community

# P1 - Critical Security Fixes
gh milestone create "P1: Critical Security Fixes" \
  --due 2025-11-10 \
  --description "Critical security vulnerabilities that must be fixed immediately. Includes JWT token blacklist, rate limiting enforcement, and account lockout mechanisms."

# P2 - High Priority Security & Performance
gh milestone create "P2: High Priority Security & Performance" \
  --due 2025-11-24 \
  --description "High-priority security hardening and performance optimizations. Includes input validation, CSRF enforcement, and database indexing."

# P3 - Medium Priority Improvements
gh milestone create "P3: Medium Priority Improvements" \
  --due 2025-12-15 \
  --description "Medium-priority code quality improvements, refactoring, and feature enhancements."

# P4 - Low Priority & Future Work
gh milestone create "P4: Low Priority & Future Work" \
  --due 2026-03-31 \
  --description "Low-priority improvements, documentation updates, and nice-to-have features for Q1 2026."

# Verify milestones
gh milestone list
```

**Checkpoint:** You should see 4 milestones with due dates.

---

## Phase 4: Project Board Creation (15 minutes)

### Create Project Board

```bash
# Create project
gh project create --title "Security & Performance Audit" --body "Tracking implementation of 34 audit findings"

# Get project number (will be displayed after creation, e.g., #1)
gh project list

# Note: GitHub Projects v2 uses a different structure
# You'll need to configure columns via the web UI
```

### Configure Columns via Web UI

1. Go to https://github.com/Xertox1234/plant_id_community/projects
2. Click on "Security & Performance Audit" project
3. Add columns:
   - **Backlog** - "Not yet ready to work on"
   - **To Triage** - "New issues needing assessment"
   - **Ready** - "Prioritized and ready to start"
   - **In Progress** - "Currently being worked on" (WIP limit: 3)
   - **In Review** - "PR submitted, awaiting review" (WIP limit: 2)
   - **Done** - "Completed and merged"

**Checkpoint:** Project board should have 6 columns.

---

## Phase 5: Issue Creation from Audit Findings (4 hours)

### Issue Template for Each Audit Finding

Use this format (based on priority level):

#### P1 Example: JWT Token Blacklist

```bash
gh issue create \
  --title "security: Implement JWT token blacklist on logout" \
  --label "priority: P1 - critical" \
  --label "type: security" \
  --label "platform: backend" \
  --label "tech: django" \
  --label "tech: jwt" \
  --label "effort: medium" \
  --milestone "P1: Critical Security Fixes" \
  --body "$(cat <<'EOF'
## Problem Statement

Currently, JWT tokens remain valid until expiration even after user logout. This creates a security risk: if a token is compromised, an attacker can continue using it for up to 24 hours.

## Current Behavior

1. User logs in → receives JWT tokens
2. User logs out → frontend deletes tokens
3. Backend doesn't track logout
4. Compromised token still works for 24 hours

## Expected Behavior

1. User logs out → tokens blacklisted immediately
2. Any request with blacklisted token receives 401
3. Tokens auto-expire from blacklist after natural expiration
4. Admin can manually blacklist tokens

## Proposed Solution

Implement Redis-based token blacklist using djangorestframework-simplejwt's BlacklistApp:

1. Add `rest_framework_simplejwt.token_blacklist` to INSTALLED_APPS
2. Run migration to create blacklist tables
3. Update logout endpoint to blacklist refresh token
4. Configure automatic cleanup of expired blacklisted tokens
5. Add monitoring for blacklist size

## Acceptance Criteria

### Functional Requirements
- [ ] After logout, refresh token is blacklisted
- [ ] API calls with blacklisted token return 401
- [ ] Blacklisted tokens auto-removed after expiration
- [ ] Admin can manually blacklist tokens
- [ ] Blacklist uses Redis for performance

### Test Requirements
- [ ] Test: Logout blacklists token, subsequent use fails
- [ ] Test: Token expires naturally, removed from blacklist
- [ ] Test: Blacklist survives server restart (Redis)
- [ ] Test: Blacklist check performance <10ms
- [ ] All existing authentication tests pass
- [ ] Coverage >80% for blacklist code

### Security Requirements
- [ ] Blacklist is write-only (no public query endpoint)
- [ ] Entries include jti (JWT ID) only, not full token
- [ ] Logging includes attempts to use blacklisted tokens

## Implementation Details

### Files to Modify
- `backend/apps/users/views.py` (add blacklist logic to logout)
- `backend/apps/users/serializers.py` (add blacklist error response)
- `backend/apps/users/tests/test_authentication.py` (add tests)
- `backend/plant_community_backend/settings.py` (configure blacklist app)

### Files to Create
- Migration: `backend/apps/users/migrations/000X_add_token_blacklist.py`

### Technical Context

**Pattern to Follow:**
Use djangorestframework-simplejwt's built-in BlacklistApp (already in dependencies)

**Reference Implementation:**
```python
# apps/users/views.py
from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return Response({'error': 'Refresh token required'}, status=400)

        token = RefreshToken(refresh_token)
        token.blacklist()

        logger.info(f"[AUTH] Token blacklisted for user {request.user.id}")
        return Response({'message': 'Logout successful'}, status=200)
    except TokenError as e:
        return Response({'error': 'Invalid token'}, status=400)
```

**Settings Configuration:**
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'rest_framework_simplejwt.token_blacklist',
]

SIMPLE_JWT = {
    'BLACKLIST_AFTER_ROTATION': True,
    'ROTATE_REFRESH_TOKENS': True,
}
```

## Testing Strategy

```bash
python manage.py test apps.users.tests.test_authentication --keepdb -v 2
python manage.py migrate --plan | grep blacklist
redis-cli keys "token_blacklist:*"
```

## Security Impact

**Before:** Compromised tokens valid 24 hours post-logout
**After:** Tokens immediately invalid on logout

## Related Issues

- Related to #234 (JWT rotation)
- Blocks #235 (Forced logout of all sessions)

## References

- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- simplejwt docs: https://django-rest-framework-simplejwt.readthedocs.io/en/latest/blacklist_app.html

**Effort:** Medium (6-9 hours total)
EOF
)"
```

### Bulk Creation Script

Create `create_audit_issues.sh`:

```bash
#!/bin/bash

# Set repository
REPO="Xertox1234/plant_id_community"

# P1 Issues (5 total)
echo "Creating P1 issues..."

# Issue 1: JWT Token Blacklist
gh issue create --title "security: Implement JWT token blacklist on logout" \
  --label "priority: P1 - critical,type: security,platform: backend,tech: django,tech: jwt,effort: medium" \
  --milestone "P1: Critical Security Fixes" \
  --body-file issues/p1-jwt-blacklist.md

# Issue 2: Rate Limiting Enforcement
gh issue create --title "security: Enforce rate limiting on all authentication endpoints" \
  --label "priority: P1 - critical,type: security,platform: backend,tech: django,effort: medium" \
  --milestone "P1: Critical Security Fixes" \
  --body-file issues/p1-rate-limiting.md

# ... (repeat for remaining 32 issues)

echo "All issues created!"
```

**Note:** Create individual markdown files for each issue body in `issues/` directory for better organization.

**Time Estimate:** 7 minutes per issue × 34 issues = 4 hours

---

## Phase 6: Organization & Prioritization (30 minutes)

### Add Issues to Project Board

```bash
# Get project ID (from earlier step)
PROJECT_ID=1  # Replace with actual project number

# Add all P1 issues to project and move to "Ready"
gh issue list --label "priority: P1 - critical" --json number --jq '.[].number' | \
  while read issue_number; do
    gh project item-add $PROJECT_ID --owner Xertox1234 --url "https://github.com/Xertox1234/plant_id_community/issues/$issue_number"
  done

# Add P2 issues to "To Triage"
gh issue list --label "priority: P2 - high" --json number --jq '.[].number' | \
  while read issue_number; do
    gh project item-add $PROJECT_ID --owner Xertox1234 --url "https://github.com/Xertox1234/plant_id_community/issues/$issue_number"
  done

# Add P3/P4 issues to "Backlog"
gh issue list --label "priority: P3 - medium,priority: P4 - low" --json number --jq '.[].number' | \
  while read issue_number; do
    gh project item-add $PROJECT_ID --owner Xertox1234 --url "https://github.com/Xertox1234/plant_id_community/issues/$issue_number"
  done
```

### Link Related Issues

For issues with dependencies, add comments:

```bash
# Example: Issue #2 depends on Issue #1
gh issue comment 2 --body "Depends on #1 (JWT token blacklist must be implemented first)"

# Example: Issue #5 is related to Issue #3
gh issue comment 5 --body "Related to #3 (uses similar rate limiting pattern)"

# Example: Issue #10 blocks Issue #15
gh issue comment 10 --body "Blocks #15 (required before implementing password reset flow)"
```

**Checkpoint:** All 34 issues should be visible on project board.

---

## Phase 7: Documentation & Communication (30 minutes)

### Create Summary Issue

Create a master tracking issue:

```bash
gh issue create \
  --title "docs: Security & Performance Audit Implementation Tracking" \
  --label "type: documentation,priority: P2 - high" \
  --pin \
  --body "$(cat <<'EOF'
# Security & Performance Audit Implementation

This issue tracks the implementation of 34 audit findings identified in October 2025.

## Progress Overview

- **Total Issues:** 34
- **Completed:** 0 (0%)
- **In Progress:** 0
- **Blocked:** 0

## Priority Breakdown

### P1 - Critical Security Fixes (5 issues)
Due: November 10, 2025

- [ ] #1 - JWT token blacklist on logout
- [ ] #2 - Rate limiting on authentication endpoints
- [ ] #3 - Account lockout after failed attempts
- [ ] #4 - CSRF token enforcement
- [ ] #5 - Input validation on user inputs

### P2 - High Priority (8 issues)
Due: November 24, 2025

- [ ] #6 - Add database indexes for performance
- [ ] #7 - Implement password strength validation
- [ ] #8 - Add security logging and monitoring
- [ ] #9 - Fix cache stampede in PlantNet API
- [ ] #10 - Implement type hints on all services
- [ ] #11 - Add error handling for external APIs
- [ ] #12 - Implement IP spoofing protection
- [ ] #13 - Add session timeout configuration

### P3 - Medium Priority (12 issues)
Due: December 15, 2025

[List P3 issues with checkboxes]

### P4 - Low Priority (9 issues)
Due: Q1 2026

[List P4 issues with checkboxes]

## Milestones

- 📅 [P1: Critical Security Fixes](link-to-milestone) - Due: Nov 10, 2025
- 📅 [P2: High Priority](link-to-milestone) - Due: Nov 24, 2025
- 📅 [P3: Medium Priority](link-to-milestone) - Due: Dec 15, 2025
- 📅 [P4: Low Priority](link-to-milestone) - Due: Q1 2026

## Project Board

Track progress on the [Security & Performance Audit Project Board](link-to-board).

## Documentation

- [Audit Report](link-to-audit.md)
- [Implementation Guidelines](link-to-guidelines.md)
- [GitHub Issue Best Practices](link-to-best-practices.md)

## Weekly Updates

Updates will be posted here every Friday summarizing progress, blockers, and next steps.

---

**Last Updated:** October 27, 2025
EOF
)"

# Pin the tracking issue
gh issue pin <issue-number>
```

### Update Project README

Add a section to your main `README.md`:

```markdown
## Security & Performance Audit

We are actively addressing security and performance improvements identified in our October 2025 audit. Track progress:

- 📊 [Project Board](https://github.com/Xertox1234/plant_id_community/projects/1)
- 📋 [Tracking Issue](#X) (replace with actual issue number)
- 📅 [Milestones](https://github.com/Xertox1234/plant_id_community/milestones)

**Current Status:** 0/34 issues completed (0%)

See our [Security Policy](.github/SECURITY.md) for reporting vulnerabilities.
```

---

## Phase 8: Team Communication (15 minutes)

### Notify Team

Create a team announcement (GitHub Discussion or Slack):

```markdown
# Security & Performance Audit Implementation Kickoff

Hi team! 👋

We've completed a comprehensive security and performance audit of our codebase and identified **34 areas for improvement**. All findings have been converted into GitHub issues with proper labels, milestones, and documentation.

## What's Been Set Up

✅ **36 labels** for organization (priority, type, platform, tech, status, effort)
✅ **4 issue templates** (bug report, feature request, security, tech debt)
✅ **Security policy** (SECURITY.md with disclosure guidelines)
✅ **4 milestones** (one per priority level with due dates)
✅ **Project board** for tracking progress
✅ **34 issues** created from audit findings

## Priority Levels

- **P1 (5 issues):** Critical security fixes - Due Nov 10
- **P2 (8 issues):** High priority - Due Nov 24
- **P3 (12 issues):** Medium priority - Due Dec 15
- **P4 (9 issues):** Low priority - Q1 2026

## How to Contribute

1. Check the [Project Board](link) for available issues
2. Look for issues labeled `status: ready`
3. Self-assign an issue before starting work
4. Move issue to "In Progress" column
5. Create PR linking to issue (use "Closes #123")
6. Request review and move to "In Review"

## Good First Issues

New to the project? Look for issues with the `good first issue` label - these are great starting points!

## Questions?

See the [Tracking Issue](#X) for more details or ask in #dev-security channel.

Let's ship these improvements! 🚀

---

[Your Name]
```

---

## Completion Checklist

### Phase 1: Labels ✅
- [ ] Created `labels.csv` with 36 labels
- [ ] Ran GitHub CLI command to create labels
- [ ] Verified labels in repository settings
- [ ] Confirmed color coding and descriptions

### Phase 2: Templates ✅
- [ ] Created `.github/ISSUE_TEMPLATE/` directory
- [ ] Created `config.yml` with links
- [ ] Created `1-bug-report.yml`
- [ ] Created `2-feature-request.yml`
- [ ] Created `3-security-vulnerability.yml`
- [ ] Created `4-technical-debt.yml`
- [ ] Created `.github/SECURITY.md`
- [ ] Committed and pushed templates
- [ ] Verified templates appear when creating issues

### Phase 3: Milestones ✅
- [ ] Created "P1: Critical Security Fixes" (Due: Nov 10)
- [ ] Created "P2: High Priority" (Due: Nov 24)
- [ ] Created "P3: Medium Priority" (Due: Dec 15)
- [ ] Created "P4: Low Priority" (Due: Q1 2026)
- [ ] Verified milestones show due dates

### Phase 4: Project Board ✅
- [ ] Created "Security & Performance Audit" project
- [ ] Added 6 columns (Backlog, To Triage, Ready, In Progress, Review, Done)
- [ ] Set WIP limits (In Progress: 3, Review: 2)
- [ ] Configured automation (optional)

### Phase 5: Issues ✅
- [ ] Created 5 P1 issues (critical security)
- [ ] Created 8 P2 issues (high priority)
- [ ] Created 12 P3 issues (medium priority)
- [ ] Created 9 P4 issues (low priority)
- [ ] Applied appropriate labels to all issues
- [ ] Assigned issues to milestones
- [ ] Linked related issues with comments

### Phase 6: Organization ✅
- [ ] Added all issues to project board
- [ ] Moved P1 issues to "Ready" column
- [ ] Moved P2 issues to "To Triage" column
- [ ] Moved P3/P4 issues to "Backlog" column
- [ ] Verified issue relationships (depends on, blocks, related to)

### Phase 7: Documentation ✅
- [ ] Created tracking issue (#X)
- [ ] Pinned tracking issue
- [ ] Updated project README.md
- [ ] Documented label strategy
- [ ] Documented workflow process

### Phase 8: Communication ✅
- [ ] Posted team announcement
- [ ] Shared project board link
- [ ] Explained priority system
- [ ] Provided contribution guidelines

---

## Maintenance & Next Steps

### Weekly Tasks
- [ ] Review project board every Friday
- [ ] Update tracking issue with progress
- [ ] Triage new issues (apply labels, assign milestones)
- [ ] Move completed issues to "Done"
- [ ] Close completed milestones

### As Issues Progress
- [ ] Update issue status (to-triage → ready → in-progress → needs-review)
- [ ] Link PRs to issues (use "Closes #123" in PR description)
- [ ] Check off acceptance criteria as completed
- [ ] Request reviews when PR is ready
- [ ] Merge and close issues

### Monthly Review
- [ ] Audit label usage (are labels being applied correctly?)
- [ ] Review milestone progress (on track for due dates?)
- [ ] Identify blockers and dependencies
- [ ] Adjust priorities if needed
- [ ] Celebrate completed work! 🎉

---

## Time Investment Summary

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Label Creation | 30 min | ⏳ Pending |
| 2 | Template Creation | 1 hour | ⏳ Pending |
| 3 | Milestone Creation | 15 min | ⏳ Pending |
| 4 | Project Board Setup | 15 min | ⏳ Pending |
| 5 | Issue Creation (34 issues) | 4 hours | ⏳ Pending |
| 6 | Organization | 30 min | ⏳ Pending |
| 7 | Documentation | 30 min | ⏳ Pending |
| 8 | Communication | 15 min | ⏳ Pending |
| **Total** | **Setup Complete** | **7 hours** | **0%** |

---

## Success Metrics (Track These!)

### Issue Quality
- [ ] <10% of issues need "needs-info" label
- [ ] >75% of PRs accepted on first review
- [ ] <24 hour triage time for new issues

### Project Health
- [ ] P1 milestone: 100% complete by Nov 10
- [ ] P2 milestone: 100% complete by Nov 24
- [ ] WIP limits respected (≤3 in progress, ≤2 in review)
- [ ] Weekly velocity: 3-5 issues moved to "Done"

### Code Quality
- [ ] >80% test coverage on new code
- [ ] 100% type hints on service methods
- [ ] 0 critical security vulnerabilities

---

**Document Created:** October 27, 2025
**Last Updated:** October 27, 2025
**Status:** Ready for implementation
**Estimated Completion:** 7 hours total setup time
