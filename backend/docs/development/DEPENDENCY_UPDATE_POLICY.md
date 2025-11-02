# Dependency Update Policy

**Last Updated**: November 2, 2025
**Owner**: Engineering Team
**Status**: Active

## Overview

This document defines the policy for managing dependency updates across all platforms (backend, web frontend, mobile) in the Plant ID Community project. Automated scanning and updates are handled by GitHub Actions and Dependabot.

## Automated Scanning Infrastructure

### GitHub Actions Security Scanning
- **Workflow**: `.github/workflows/security-scan.yml`
- **Triggers**:
  - Every push to `main` or `develop` branches
  - Every pull request to `main` or `develop`
  - Weekly schedule: Mondays at 9am UTC
- **Scans**:
  - Backend: Python Safety check on `requirements.txt`
  - Frontend: npm audit on `package.json`
  - Mobile: Flutter pub outdated check
- **Artifacts**: JSON reports stored for 30 days
- **Notifications**: Automatic PR comments on vulnerability detection

### Dependabot Configuration
- **Configuration**: `.github/dependabot.yml`
- **Schedule**: Weekly updates every Monday at 9am PST
- **Ecosystems Monitored**:
  - Python (pip) - `/backend`
  - npm - `/web`
  - Pub (Flutter) - `/plant_community_mobile`
  - GitHub Actions - `/`
- **PR Limits**: Maximum 10 open PRs per ecosystem
- **Grouping**: Related dependencies grouped to reduce PR noise
- **Labels**: Automatic labeling for dependency type and platform

## Update Priority Levels

### P0 - Critical Security (Action Required: Within 24 Hours)

**Criteria**:
- CVE with CVSS score >= 9.0
- Actively exploited vulnerabilities in the wild
- Direct dependency with no workaround available
- Authentication bypass or RCE vulnerabilities

**Examples**:
- Django SQL injection (CVE-2025-XXXXX, CVSS 9.8)
- JWT authentication bypass (CVE-2024-22513, CVSS 9.1)
- Pillow arbitrary code execution

**Required Actions**:
1. Immediate assessment of impact on production
2. Create emergency branch for hotfix
3. Update dependency and run full test suite
4. Manual security testing and code review
5. Deploy to staging environment
6. Deploy to production with monitoring
7. Document incident and mitigation

**Testing Requirements**:
- Full test suite (backend, frontend, mobile)
- Manual security testing
- Staging environment verification
- Production smoke tests post-deployment

**Approval Process**:
- Architecture lead approval required
- Security team notification
- Post-deployment incident report

### P1 - High Security (Action Required: Within 1 Week)

**Criteria**:
- CVE with CVSS score 7.0-8.9
- Security advisories from package maintainers
- Transitive dependencies with fixes available
- Known vulnerabilities with mitigations

**Examples**:
- Django XSS vulnerabilities (CVSS 7.5)
- DRF information disclosure
- React security updates
- Pillow DoS vulnerabilities

**Required Actions**:
1. Create update branch from `develop`
2. Update dependency in `requirements.txt` or `package.json`
3. Run full test suite locally
4. Manual testing of affected features
5. Create PR with security label
6. Request code review
7. Merge and deploy in next release

**Testing Requirements**:
- Full test suite (all platforms)
- Manual testing of security-related features
- Integration test verification

**Approval Process**:
- One senior engineer approval required
- Security team notification recommended

### P2 - Moderate Updates (Action Required: Within 2 Weeks)

**Criteria**:
- Minor version updates with bug fixes
- CVE with CVSS score < 7.0
- Performance improvements
- Compatibility updates for newer Python/Node versions

**Examples**:
- Django 5.2.6 -> 5.2.7 (bug fixes)
- React Router minor updates
- Wagtail CMS improvements
- Pytest updates

**Required Actions**:
1. Review Dependabot PR
2. Check CHANGELOG for breaking changes
3. Run full test suite via CI
4. Manual smoke testing if needed
5. Approve and merge PR

**Testing Requirements**:
- Full automated test suite
- CI pipeline must pass
- Optional: Manual smoke tests for major features

**Approval Process**:
- One engineer approval
- Can be auto-merged if all tests pass and no breaking changes

### P3 - Low Priority (Action Required: Monthly Batch)

**Criteria**:
- Patch version updates (no breaking changes)
- Development and testing dependencies
- Documentation updates
- Code quality tools (linters, formatters)

**Examples**:
- pytest 8.0.1 -> 8.0.2
- black 24.1.0 -> 24.1.1
- coverage minor updates
- ESLint configuration updates

**Required Actions**:
1. Batch multiple P3 updates into single PR
2. Review Dependabot grouped updates
3. Run automated test suite
4. Merge if tests pass

**Testing Requirements**:
- Automated test suite only
- Smoke tests for development tools

**Approval Process**:
- Auto-merge enabled for grouped P3 updates
- Manual review only if tests fail

## Dependency Categories and Grouping

### Backend (Python/pip)

**Security-Critical Dependencies** (Always P0/P1):
- `Django` - Web framework (CVEs common)
- `djangorestframework-simplejwt` - JWT authentication
- `Pillow` - Image processing (frequent CVEs)
- `cryptography` - Encryption library
- `requests` - HTTP client
- `urllib3` - HTTP library

**Framework Dependencies** (P1/P2):
- `wagtail` - CMS framework
- `djangorestframework` - REST API
- `django-cors-headers` - CORS handling
- `django-filter` - Filtering
- `psycopg2-binary` - PostgreSQL driver

**Development Dependencies** (P3):
- `pytest`, `pytest-django` - Testing
- `coverage` - Code coverage
- `mypy` - Type checking
- `black`, `flake8`, `isort` - Code quality

### Frontend (npm)

**Security-Critical Dependencies** (Always P0/P1):
- `react`, `react-dom` - UI framework
- `react-router-dom` - Routing (auth-related)
- `axios` - HTTP client
- Any package handling authentication or user input

**Framework Dependencies** (P1/P2):
- `vite` - Build tool
- `@vitejs/*` - Vite plugins
- `tailwindcss` - CSS framework
- `dompurify` - XSS prevention

**Development Dependencies** (P3):
- `vitest` - Testing
- `playwright` - E2E testing
- `@testing-library/*` - Testing utilities
- `eslint`, `prettier` - Code quality

### Mobile (Flutter/pub)

**Security-Critical Dependencies** (Always P0/P1):
- `firebase_auth` - Authentication
- `firebase_core` - Firebase core
- Any package handling user data or API calls

**Framework Dependencies** (P1/P2):
- `flutter` - Flutter SDK
- `cupertino_icons` - iOS icons
- State management packages

**Development Dependencies** (P3):
- Testing packages
- Code generation tools

## Testing Requirements by Priority

### P0 - Critical Security
```bash
# Backend
cd backend
python manage.py test --keepdb -v 2
python manage.py test apps.plant_identification --keepdb
python manage.py test apps.users --keepdb
python manage.py test apps.blog --keepdb
python manage.py test apps.forum --keepdb

# Manual security testing
- Test authentication flows
- Test authorization boundaries
- Test input validation
- Check for XSS/CSRF vulnerabilities

# Frontend
cd web
npm run test
npm run test:e2e

# Staging deployment
- Full feature testing
- Security scanner (OWASP ZAP)
- Load testing if performance-related

# Production deployment
- Smoke tests
- Monitor error rates for 24 hours
```

### P1 - High Security
```bash
# Automated tests
cd backend && python manage.py test --keepdb
cd web && npm run test

# Manual testing
- Test affected features
- Verify security advisory is resolved
- Check integration points
```

### P2 - Moderate Updates
```bash
# Automated tests only
cd backend && python manage.py test --keepdb
cd web && npm run test

# Optional smoke testing
- Quick verification of major features
```

### P3 - Low Priority
```bash
# CI automated tests only
# Smoke tests for development tools
```

## Approval Workflows

### Auto-Merge Criteria
Dependabot PRs can be auto-merged if ALL of the following are true:
- Update is P3 (patch updates, dev dependencies)
- All CI checks pass (tests, linting, security scans)
- No breaking changes mentioned in CHANGELOG
- Grouped updates with no conflicts
- Dependency is in the development-dependencies group

### Manual Review Required
Manual review is required for:
- P0/P1 security updates (always)
- P2 updates affecting core features
- Major version updates (e.g., React 18 -> 19)
- Updates with breaking changes
- Updates to authentication/authorization packages
- Updates that modify database interactions

### Review Checklist
When reviewing dependency updates:
- [ ] Check CHANGELOG for breaking changes
- [ ] Verify all tests pass in CI
- [ ] Check for deprecation warnings
- [ ] Review security advisory details (if applicable)
- [ ] Verify compatibility with Python/Node version
- [ ] Check for transitive dependency updates
- [ ] Test locally if high-risk change
- [ ] Update documentation if API changes

## Monitoring and Alerting

### GitHub Actions Notifications
- **Success**: Workflow badge in README
- **Failure**: PR comment with vulnerability details
- **Artifacts**: JSON reports available for 30 days

### Dependabot Notifications
- **New PRs**: GitHub notification to repository maintainers
- **Security updates**: GitHub Security Advisory notification
- **Grouped updates**: Single PR with multiple updates

### Weekly Security Reports
Every Monday at 9am UTC:
- Automated security scan runs
- Report artifacts uploaded
- Email digest of open Dependabot PRs (if configured)

## Incident Response

### Security Vulnerability Detected

1. **Triage** (within 1 hour):
   - Assess CVSS score and priority level
   - Check if production is affected
   - Determine if immediate action required

2. **Investigation** (P0: 2 hours, P1: 24 hours):
   - Review security advisory details
   - Identify affected code paths
   - Determine mitigation options

3. **Remediation** (per priority timeline):
   - Update dependency
   - Run tests
   - Deploy fix

4. **Documentation**:
   - Update `SECURITY.md` if needed
   - Document incident in work log
   - Share learnings with team

### Rollback Procedure
If an update causes issues in production:

1. **Immediate**: Revert PR and redeploy previous version
2. **Investigation**: Identify root cause of failure
3. **Resolution**: Fix issue or wait for upstream fix
4. **Retry**: Re-apply update with additional testing

## Tools and Resources

### Installed Tools
- **Backend**: `safety==3.6.2` (Python vulnerability scanner)
- **Frontend**: `npm audit` (built-in npm tool)
- **Mobile**: `flutter pub outdated` (built-in Flutter tool)

### External Resources
- GitHub Security Advisories: https://github.com/advisories
- National Vulnerability Database: https://nvd.nist.gov
- Python Security Advisories: https://pypi.org/project/safety/
- npm Security Advisories: https://www.npmjs.com/advisories
- Django Security: https://docs.djangoproject.com/en/5.2/releases/security/

### Documentation
- Safety documentation: https://docs.pyup.io/docs
- Dependabot documentation: https://docs.github.com/en/code-security/dependabot
- Internal security docs: `/backend/docs/security/`

## Maintenance Schedule

### Daily
- Monitor CI/CD security scans on PRs
- Review critical security alerts

### Weekly (Mondays 9am UTC)
- Automated security scan runs
- Dependabot creates update PRs
- Review and triage new Dependabot PRs

### Monthly
- Batch review of P3 updates
- Review open Dependabot PRs
- Update this policy if needed

### Quarterly
- Review dependency update trends
- Audit pinned versions for staleness
- Update security tooling

### Annually
- Major framework updates (Django, React)
- Comprehensive security audit
- Policy review and updates

## Exceptions and Special Cases

### Pinned Dependencies
Some dependencies are intentionally pinned and should NOT be auto-updated:
- **None currently** - All dependencies use exact pinning but can be updated

### Known Incompatibilities
Document any known incompatibilities:
- **None currently**

### Vendor-Specific Issues
- **Plant.id API**: Changes to SDK require manual testing of identification flow
- **PlantNet API**: API changes require service layer updates
- **Firebase**: Mobile updates require Firebase console configuration changes

## Metrics and KPIs

Track the following metrics:
- Time to patch critical vulnerabilities (Target: <24 hours)
- Number of open Dependabot PRs (Target: <5)
- Security scan pass rate (Target: 100%)
- Dependency freshness (Target: <3 months behind latest)

## Policy Updates

This policy should be reviewed and updated:
- When new tools are added to the stack
- After security incidents
- When team structure changes
- At least annually

**Version History**:
- v1.0 (2025-11-02): Initial policy created with GitHub Actions + Dependabot
