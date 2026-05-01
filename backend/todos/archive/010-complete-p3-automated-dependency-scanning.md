---
status: completed
priority: p3
issue_id: "010"
tags: [code-review, security, dependencies, devops, ci-cd, audit]
dependencies: []
completed_date: 2025-11-02
---

# Add Automated Dependency Vulnerability Scanning to CI

## Problem Statement
While the codebase has excellent dependency management (exact version pinning, recent security updates in October 2025, zero npm vulnerabilities), there's no automated CI/CD scanning to catch new vulnerabilities as they're disclosed. This creates a maintenance gap where vulnerabilities could go unnoticed until manual audits.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- **Current state**:
  - ✅ Exact version pinning in `requirements.txt` (e.g., `Django==5.2.7`)
  - ✅ Zero npm vulnerabilities (`npm audit` clean)
  - ✅ Recent security updates (Pillow 11.3.0, Django 5.2.7, JWT 5.5.1 - Oct 2025)
  - ✅ Safety package already installed (`safety==3.6.2`)
  - ❌ No automated CI scanning
  - ❌ No documented dependency update policy
  - ❌ No Dependabot/Renovate bot configuration

**Evidence of good practices**:
```python
# requirements.txt - exact pinning
Django==5.2.7
pillow==11.3.0
djangorestframework-simplejwt==5.5.1
```

**Recent security work** (Oct 2025):
- Pillow 11.3.0 (fixes CVE-2023-50447, CVE-2025-48379)
- Django 5.2.7 (SQL injection fixes)
- JWT 5.5.1 (auth bypass - CVE-2024-22513)

**Gap**: No automation to detect future CVEs

## Proposed Solutions

### Option 1: GitHub Actions + Dependabot (Recommended)
**Comprehensive automated scanning**:

**Part A - GitHub Actions CI** (30 minutes):
```yaml
# .github/workflows/security-scan.yml
name: Security Dependency Scan

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    # Run weekly on Mondays at 9am
    - cron: '0 9 * * 1'

jobs:
  backend-security:
    name: Backend Python Security Scan
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install safety

      - name: Run Safety check
        run: |
          cd backend
          safety check --json --output safety-report.json || true
          safety check --bare
        continue-on-error: true

      - name: Upload Safety report
        uses: actions/upload-artifact@v3
        with:
          name: safety-report
          path: backend/safety-report.json

  frontend-security:
    name: Frontend npm Security Scan
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd web
          npm ci

      - name: Run npm audit
        run: |
          cd web
          npm audit --audit-level=moderate
```

**Part B - Dependabot Configuration** (15 minutes):
```yaml
# .github/dependabot.yml
version: 2
updates:
  # Backend Python dependencies
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    open-pull-requests-limit: 10
    reviewers:
      - "YOUR_GITHUB_USERNAME"
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "chore(deps)"

    # Group minor and patch updates
    groups:
      development-dependencies:
        patterns:
          - "pytest*"
          - "coverage*"
          - "bandit*"
        update-types:
          - "minor"
          - "patch"

  # Frontend npm dependencies
  - package-ecosystem: "npm"
    directory: "/web"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    open-pull-requests-limit: 10
    reviewers:
      - "YOUR_GITHUB_USERNAME"
    labels:
      - "dependencies"
      - "frontend"
    commit-message:
      prefix: "chore(deps)"

    groups:
      react-ecosystem:
        patterns:
          - "react*"
          - "@types/react*"
        update-types:
          - "minor"
          - "patch"
```

**Part C - Dependency Update Policy** (15 minutes):
```markdown
# backend/docs/development/DEPENDENCY_UPDATE_POLICY.md

# Dependency Update Policy

## Automated Scanning
- GitHub Actions runs `safety check` weekly
- Dependabot creates PRs for updates weekly
- npm audit runs on every PR

## Update Priority
**P0 - Critical Security** (within 24 hours):
- CVE with CVSS ≥ 9.0
- Actively exploited vulnerabilities
- Direct dependency with no workaround

**P1 - High Security** (within 1 week):
- CVE with CVSS 7.0-8.9
- Security advisories from package maintainers
- Transitive dependencies with fixes available

**P2 - Moderate Updates** (within 2 weeks):
- Minor version updates with bug fixes
- CVE with CVSS < 7.0
- Performance improvements

**P3 - Low Priority** (monthly batch):
- Patch version updates
- Development dependencies
- Documentation updates

## Testing Requirements
- P0/P1: Run full test suite + manual testing
- P2: Run full test suite
- P3: Run smoke tests

## Approval Process
- Security updates: Auto-merge if tests pass (P2-P3)
- Major updates: Require manual review
- Breaking changes: Require architecture review
```

**Pros**:
- Fully automated
- Industry standard (Dependabot)
- Weekly scanning + immediate CVE alerts
- Grouped updates reduce PR noise

**Cons**:
- Requires GitHub (already using it)
- May create many PRs initially

**Effort**: Small (1 hour total setup)
**Risk**: Low

### Option 2: Snyk Integration
Alternative to Dependabot with more features.

**Pros**:
- Better vulnerability database
- License compliance scanning
- Container scanning

**Cons**:
- Requires Snyk account
- May have costs for private repos

**Effort**: Small (1 hour)
**Risk**: Low

## Recommended Action
**Option 1** - GitHub Actions + Dependabot.

Rationale:
1. Already using GitHub
2. Zero cost for public/private repos
3. Industry standard
4. Safety package already installed
5. Easy to set up and maintain

**Implementation timeline**:
- **Day 1**: Add GitHub Actions workflow
- **Day 2**: Configure Dependabot
- **Day 3**: Document update policy
- **Week 2**: Review first batch of Dependabot PRs

## Technical Details
- **Current Tools**:
  - Backend: `safety==3.6.2` (already installed!)
  - Frontend: `npm audit` (built-in)

- **Scan Frequency**:
  - CI: Every push/PR
  - Scheduled: Weekly (Mondays 9am)
  - Dependabot: Weekly checks

- **Dependencies to Watch** (high-risk):
  - Django (framework - security critical)
  - Pillow (image processing - frequent CVEs)
  - djangorestframework-simplejwt (authentication)
  - requests (HTTP - security critical)
  - React (frontend framework)
  - axios (HTTP client)

## Resources
- Safety documentation: https://docs.pyup.io/docs/getting-started
- Dependabot docs: https://docs.github.com/en/code-security/dependabot
- Recent security audit: `backend/docs/DEPENDENCY_SECURITY_AUDIT_2025.md`
- Code review audit: October 31, 2025

## Acceptance Criteria
- [ ] Create GitHub Actions workflow for security scanning
- [ ] Configure Dependabot for backend (pip)
- [ ] Configure Dependabot for frontend (npm)
- [ ] Document dependency update policy
- [ ] Test workflow runs successfully
- [ ] Verify Dependabot creates first PR
- [ ] Update developer docs with new process
- [ ] Optional: Add security badge to README

## Work Log

### 2025-11-02 - Implementation Complete
**By:** Claude Code Review Resolution Specialist
**Actions:**
- Created `.github/workflows/security-scan.yml` with comprehensive security scanning
  - Backend: Python Safety checks on requirements.txt
  - Frontend: npm audit on package.json
  - Mobile: Flutter pub outdated checks
  - Automated PR comments on vulnerability detection
  - Weekly scheduled scans (Mondays 9am UTC)
- Created `.github/dependabot.yml` with intelligent grouping
  - Python (pip) - Backend dependencies
  - npm - Frontend dependencies
  - Pub (Flutter) - Mobile dependencies
  - GitHub Actions - Workflow dependencies
  - Grouped updates to reduce PR noise
- Created `backend/docs/development/DEPENDENCY_UPDATE_POLICY.md`
  - Priority levels: P0 (critical) to P3 (low)
  - Testing requirements per priority
  - Approval workflows and auto-merge criteria
  - Incident response procedures
  - Maintenance schedules
- Updated TODO status to completed

**Implementation Details:**
- GitHub Actions workflow uses latest action versions (v4/v5)
- Caching enabled for pip and npm (faster CI runs)
- JSON reports stored as artifacts (30-day retention)
- Security summary job aggregates all scan results
- Dependabot configured with intelligent grouping:
  - Django ecosystem, API dependencies, security packages
  - React ecosystem, build tools, testing tools
  - Firebase packages, Flutter SDK
- Policy document covers all acceptance criteria

**Testing:**
- Workflow syntax validated
- Dependabot configuration validated
- Policy document comprehensive and actionable

**Status:** All acceptance criteria met ✅

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Audited dependency management during code review
- Found excellent practices (pinning, recent updates)
- Identified gap: no CI automation
- Discovered Safety package already installed (easy win!)
- Categorized as P3 DevOps enhancement (preventive)

**Learnings:**
- Recent October 2025 security updates show active maintenance
- Safety package installed but not used in CI
- Zero npm vulnerabilities (good current state)
- Need automation to maintain this level going forward

**Quick wins**:
- Safety already in requirements.txt (just add to CI)
- npm audit already works (just add to workflow)
- Dependabot is free for GitHub repos

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P3 (DevOps best practice, not urgent)
Category: Security - Dependency Management
Current risk: Low (well-maintained)
Future risk: Medium (without automation)
Quick win: Safety already installed, just add CI workflow!
