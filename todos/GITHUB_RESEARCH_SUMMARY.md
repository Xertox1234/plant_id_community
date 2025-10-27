# GitHub Issue Research Summary

> Research findings for converting code audit findings into actionable GitHub issues

**Research Date**: October 27, 2025
**Researcher**: Framework Documentation Researcher (Claude Code)
**Project**: Plant ID Community (Django + React + Flutter)

---

## Research Overview

This document summarizes research into GitHub issue creation best practices for technical projects, with focus on:
- Django backend issues (migrations, security, performance)
- React frontend issues (components, bundle size, performance)
- Multi-platform coordination (backend/frontend/mobile)
- Technical debt and code quality
- Security vulnerabilities and compliance

---

## Key Findings

### 1. Django Project Issues

**Best Practices Discovered**:
- Use bracketed logging prefixes for filtering: `[CACHE]`, `[CIRCUIT]`, `[PERF]`
- Document database changes explicitly (migrations, indexes, triggers)
- Include performance metrics (before/after benchmarks)
- Reference specific file locations with line numbers
- Link to related documentation in project docs

**Common Django Issue Patterns**:
1. **N+1 Query Problems**:
   - Show query count: "750 queries → 5 queries"
   - Include Django Debug Toolbar screenshots
   - Reference `select_related()` and `prefetch_related()` solutions

2. **Migration Safety**:
   - Check database vendor with `connection.vendor == 'postgresql'`
   - Provide graceful fallback for SQLite (development)
   - Test on both PostgreSQL and SQLite

3. **Security Issues**:
   - Use CVSS scoring (Critical: 9.0-10.0, High: 7.0-8.9)
   - Reference OWASP and CWE classifications
   - Include 90-day disclosure timeline

**Tools Mentioned**:
- django-auditlog (audit trail)
- django-security (security hardening)
- bandit + safety (SAST)
- mypy (type checking)

### 2. React Frontend Issues

**Bundle Size Optimization Patterns**:
- Always include before/after size comparison
- Use bundlephobia.com to check library sizes before adding
- Recommend modern alternatives:
  - Moment.js (72 kB) → date-fns (8 kB)
  - Lodash (71 kB) → lodash/specific-function (2 kB)
  - DOMPurify (45 kB) → isomorphic-dompurify (12 kB)

**Performance Metrics to Include**:
- Bundle size (minified + gzipped)
- First Contentful Paint (FCP)
- Lighthouse scores
- Load time on 3G networks

**Code Splitting Strategies**:
1. Route-based splitting (React.lazy)
2. Component-based splitting (Suspense)
3. Manual chunks (Vite/Webpack config)

**Tools Mentioned**:
- vite-bundle-visualizer
- bundlephobia.com
- Lighthouse
- ESLint

### 3. Multi-Platform Project Organization

**Repository Structure**:
- **Monorepo**: Single repo with `/backend`, `/web`, `/mobile` folders
- **Pros**: Simpler coordination, single issue tracker
- **Cons**: Larger repo, mixed dependencies

**GitHub Features for Coordination**:
1. **Projects**: Organize issues across multiple repos
2. **Milestones**: Group issues by release/sprint
3. **Labels**: Platform-specific (`backend:django`, `frontend:react`, `mobile:flutter`)
4. **Sub-issues**: Break down cross-platform features

**Dependency Management**:
- Use "Depends On" and "Blocks" relationships
- Create parent issue for cross-platform features
- Link backend API changes to frontend/mobile implementations

### 4. Technical Debt Issues

**Key Patterns**:
1. **Dead Code Removal**:
   - Show grep results proving code is unused
   - Calculate lines saved and complexity reduction
   - Note git history preserves deleted code

2. **Type Hints**:
   - Show coverage percentage: "3.6% (1/28 functions) → 100%"
   - Reference service layer as good example
   - Include mypy configuration

3. **Refactoring**:
   - Label as `priority:p3` (lower priority)
   - Show before/after code comparison
   - Include performance/maintainability benefits

**Gradual vs All-At-Once**:
- **API surface** (views, controllers): All-at-once (consistency critical)
- **Internal code** (utils, helpers): Gradual OK

### 5. Security Vulnerability Issues

**CVSS Scoring System**:
| Severity | CVSS Score | Example |
|----------|-----------|---------|
| Critical | 9.0-10.0 | Remote code execution, SQL injection |
| High | 7.0-8.9 | Authentication bypass, sensitive data exposure |
| Medium | 4.0-6.9 | CSRF, weak encryption, XSS (non-persistent) |
| Low | 0.1-3.9 | Information disclosure, weak password policy |

**GitHub Security Advisories**:
- Use private advisories for responsible disclosure
- 90-day embargo before public disclosure
- Include CVE number if applicable
- Calculate CVSS score with official calculator

**Security Issue Structure** (from GitHub Security Lab):
1. Summary (clear impact and severity)
2. Product (affected component)
3. Tested Version (specific versions)
4. Details (technical explanation + PoC)
5. Impact (technical + business)
6. Remediation (recommended fix + alternatives)
7. Credit (researchers/tools)
8. Disclosure Policy (90-day deadline)

**Best Practices**:
- Never include sensitive data in public issues
- Use `[SECURITY]` logging prefix
- Reference OWASP and CWE classifications
- Include remediation validation steps

### 6. Compliance Issues (GDPR, SOC 2)

**GDPR Checklist Structure** (from privacyradius/gdpr-checklist):
- Centralized in single file (`src/data.js` for web)
- Git-based tracking for audit trail
- Modular checklist items
- Community-driven updates (47 PRs, 9 contributors)

**Compliance Issue Patterns**:
1. **Audit Trail** (GDPR Article 30):
   - Who accessed what data when?
   - Retention policy (90 days active, 7 years archived)
   - Query interface for data access requests

2. **Privacy Policy**:
   - User consent mechanisms
   - Data export/deletion capabilities
   - Third-party data sharing disclosure

**Tools Mentioned**:
- django-auditlog (audit trail)
- GDPR compliance checklist (gdprchecklist.io)
- SOC 2 audit frameworks

### 7. GitHub Features Best Practices

**Task Lists**:
- Use hierarchical task lists for multi-step issues
- Check off items as work progresses
- Show progress in issue at a glance

**Sub-Issues** (up to 100 per parent, 8 levels deep):
- Break large features into smaller tasks
- Track dependencies visually
- Show progress on parent issue

**Milestones**:
- Group issues by sprint/release
- Show progress bar
- Set due dates
- Filter issues by milestone

**Projects** (Kanban boards):
- Columns: Backlog, In Progress, In Review, Done
- Drag-and-drop issue management
- Filter by label, assignee, milestone
- Track velocity and burndown

**Linking Issues**:
- `Depends On`: Blocker issues
- `Blocks`: Dependent issues
- `Related`: Similar issues
- Use keywords in PRs: "Fixes #123", "Closes #123"

---

## Research Sources

### Primary Sources

1. **Spearbit Audit Template** (https://github.com/spearbit-audits/audit-template)
   - Security audit finding structure
   - Risk matrix (likelihood × impact)
   - Severity labels: Critical, High, Medium, Low, Gas Optimization, Informational
   - Status labels: Acknowledged, Fixed, ReadyForReport
   - Python script for label automation

2. **GitHub Security Lab** (https://github.com/github/securitylab/blob/main/docs/report-template.md)
   - Vulnerability report template
   - 11 standard sections (Summary, Product, Details, PoC, Impact, Remediation)
   - 90-day disclosure policy
   - Emphasis on clear impact and severity

3. **GDPR Checklist** (https://github.com/privacyradius/gdpr-checklist)
   - Gatsby-based static site
   - Centralized data structure (`src/data.js`)
   - Git-based version control
   - Community contribution workflow

### Secondary Sources

4. **Django Best Practices**:
   - Security tools: bandit, safety, django-security
   - Performance: caching, select_related/prefetch_related, database indexing
   - CI/CD: Git hooks for pre-commit checks

5. **React Bundle Size Optimization**:
   - Developers achieved 30-50% bundle size reductions
   - Tree shaking with ES6 modules
   - Lazy loading with React.lazy and Suspense
   - Tools: vite-bundle-visualizer, bundlephobia, BundleWatch

6. **Multi-Platform Repository Organization**:
   - Monorepo preferred for coordinated releases
   - GitHub Projects for cross-repo organization
   - Avoid Git submodules (too complex)

7. **Technical Debt Management**:
   - Label as `technical-debt` or `enhancement`
   - Priority P3 (lower than bugs and features)
   - Track with Jira or GitHub Issues
   - Allocate dedicated time for refactoring

### Industry Standards Referenced

8. **CVSS v3.1 / v4.0**: Common Vulnerability Scoring System
9. **OWASP Top 10**: Web application security risks
10. **CWE**: Common Weakness Enumeration
11. **GDPR Article 30**: Records of processing activities
12. **SOC 2**: Security and compliance audit framework
13. **NIST SP 800-92**: Log retention best practices

---

## Patterns Extracted

### Issue Structure Pattern

```markdown
# Standard Issue Structure

## Summary
[1-2 sentence description]

## Findings
- Discovered by: [Tool/Agent]
- Location: [File:line]
- Current state: [Metrics]
- Target state: [Metrics]

## Current Implementation
[Code snippet showing problem]

## Proposed Solutions
### Option 1: [Name] (Recommended)
- Implementation: [Code snippet]
- Pros: [List]
- Cons: [List]
- Effort: [Time estimate]
- Risk: [Low/Medium/High]

### Option 2: [Alternative]
[Same structure]

## Recommended Action
[Clear recommendation with implementation steps]

## Technical Details
- Affected files: [List]
- Related components: [List]
- Database changes: [Yes/No + description]
- Configuration changes: [Yes/No + description]

## Resources
- [Links to docs, examples, tools]

## Acceptance Criteria
- [ ] [Specific, measurable criteria]
- [ ] [All must be checked before closing]

## Labels
[priority], [platform], [type], [status]
```

### Label Taxonomy Pattern

```markdown
# Three-Dimensional Label System

1. **Priority** (urgency):
   - priority:critical (P1)
   - priority:high (P2)
   - priority:medium (P3)
   - priority:low (P4)

2. **Platform** (scope):
   - backend:django
   - frontend:react
   - mobile:flutter
   - infrastructure

3. **Type** (category):
   - type:bug
   - type:feature
   - type:enhancement
   - type:refactor
   - type:security
   - type:performance
   - type:documentation
```

### Security Issue Pattern

```markdown
# Security Issue Workflow

1. **Discovery** (Day 0):
   - Create private security advisory
   - Calculate CVSS score
   - Assign CVE number

2. **Patch Development** (Day 0-2):
   - Develop fix in private fork
   - Write tests
   - Review with security team

3. **Deployment** (Day 2-3):
   - Deploy to staging
   - Verify fix
   - Deploy to production

4. **Public Disclosure** (Day 90):
   - Publish security advisory
   - Update CHANGELOG
   - Notify users
```

### Multi-Platform Issue Pattern

```markdown
# Cross-Platform Feature Workflow

1. **Parent Issue**: High-level feature description
   - Title: "Feature: Plant Identification API"
   - Body: Cross-platform requirements

2. **Sub-Issues**:
   - #101 Backend: API endpoint
   - #102 Web: React service integration
   - #103 Mobile: Flutter service integration

3. **Dependencies**:
   - #102 depends on #101 (backend must be ready)
   - #103 depends on #101 (backend must be ready)

4. **Testing**:
   - Backend: Unit tests
   - Web: Integration tests
   - Mobile: Integration tests
   - E2E: Cross-platform smoke tests
```

---

## Recommendations for Plant ID Community

Based on research findings, here are specific recommendations:

### 1. Issue Template Structure

**Use the comprehensive templates** in `GITHUB_ISSUE_CREATION_GUIDE.md`:
- Security Vulnerability Template (for #005, #014, #016)
- Django Performance Template (for #001, #008, #013)
- React Performance Template (for #006, #007, #011)
- Type Hints Technical Debt Template (for #002)

### 2. Label System

**Create these labels** in your repository:
```bash
# Priority (4 labels)
priority:critical, priority:high, priority:medium, priority:low

# Platform (3 labels)
backend:django, frontend:react, mobile:flutter

# Type (7 labels)
type:bug, type:security, type:performance, type:refactor,
type:technical-debt, type:feature, type:documentation

# Status (4 labels)
needs-fix, needs-review, needs-testing, ready-to-deploy
```

### 3. Milestone Structure

**Create milestone**: "Code Audit Remediation - October 2025"
- Due date: 2025-11-30
- Description: "Comprehensive codebase audit findings from October 25, 2025"
- Issues: All 24 todos

### 4. Project Board

**Create project**: "Code Audit Remediation"
- Columns: Backlog, In Progress, In Review, Done
- Add all 24 issues
- Filter by priority to focus on P1 first

### 5. Workflow

**Recommended workflow**:
1. Convert all 24 todos to GitHub issues (use script)
2. Triage P1 issues (5 issues) - assign and start immediately
3. Schedule P2 issues (8 issues) - plan for next sprint
4. Backlog P3 issues (11 issues) - address as time allows

---

## Tools and Resources

### GitHub CLI Commands

```bash
# Create issue
gh issue create --title "..." --body "..." --label "..." --milestone "..."

# Create milestone
gh milestone create "Milestone Name" --due-date "YYYY-MM-DD"

# Create project
gh project create --title "Project Name" --owner @me

# List issues
gh issue list --label "priority:critical"

# Create labels
gh label create "priority:critical" --color "d73a4a" --description "..."
```

### Analysis Tools

**Django**:
- Django Debug Toolbar (query analysis)
- mypy (type checking)
- bandit (security analysis)
- safety (dependency scanning)

**React**:
- vite-bundle-visualizer (bundle analysis)
- bundlephobia.com (library size checker)
- Lighthouse (performance audit)
- ESLint (code quality)

**Security**:
- CVSS Calculator (https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator)
- OWASP Top 10 (https://owasp.org/www-project-top-ten/)
- GitHub Security Advisories

### Documentation Resources

**Django**:
- https://docs.djangoproject.com/en/5.2/topics/db/optimization/
- https://docs.djangoproject.com/en/5.2/topics/security/
- https://docs.djangoproject.com/en/5.2/topics/cache/

**React**:
- https://react.dev/learn/render-and-commit
- https://create-react-app.dev/docs/analyzing-the-bundle-size/
- https://vitejs.dev/guide/build.html

**Security**:
- https://owasp.org/www-project-top-ten/
- https://cwe.mitre.org/
- https://www.first.org/cvss/

---

## Next Steps

1. **Review comprehensive guide**:
   - Read `GITHUB_ISSUE_CREATION_GUIDE.md` (17,000+ words)
   - Review templates for each issue type
   - Understand label taxonomy

2. **Set up GitHub infrastructure**:
   - Create labels (run script)
   - Create milestone
   - Create project board

3. **Convert todos to issues**:
   - Use `convert_todos_to_issues.sh` script (automated)
   - OR manually create issues (use templates)
   - Verify all 24 issues created

4. **Triage and assign**:
   - P1 issues (5): Assign to developers, start immediately
   - P2 issues (8): Schedule for next sprint
   - P3 issues (11): Backlog for future work

5. **Track progress**:
   - Daily: Review project board
   - Weekly: Update milestone progress
   - Biweekly: Triage new issues

---

## Research Deliverables

1. **GITHUB_ISSUE_CREATION_GUIDE.md** (17,000+ words)
   - Comprehensive templates for all issue types
   - Django, React, Flutter-specific patterns
   - Security vulnerability templates
   - Compliance issue templates
   - GitHub features best practices

2. **QUICK_REFERENCE_ISSUE_CONVERSION.md** (5,000+ words)
   - Fast conversion guide for 24 todos
   - Bash script for bulk conversion
   - Label creation commands
   - Verification checklist

3. **GITHUB_RESEARCH_SUMMARY.md** (this document)
   - Research findings summary
   - Key patterns extracted
   - Tools and resources
   - Recommendations for Plant ID Community

---

## Conclusion

This research provides comprehensive guidance for converting code audit findings into actionable GitHub issues. Key takeaways:

1. **Use templates** for consistency and completeness
2. **Add context** with links to code, docs, and related issues
3. **Be specific** with concrete acceptance criteria
4. **Prioritize ruthlessly** using P1/P2/P3 classification
5. **Track dependencies** with linked issues and sub-issues
6. **Measure success** with metrics (CVSS, performance, coverage)

The provided templates and scripts should enable efficient conversion of all 24 todos into well-structured GitHub issues, ready for triaging and implementation.

---

**Research Completed**: October 27, 2025
**Total Research Time**: 2 hours
**Deliverables**: 3 documents (27,000+ words)
**Ready for**: Production use in Plant ID Community project
