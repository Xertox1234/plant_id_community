# GitHub Issue Best Practices Research
## Comprehensive Guide for Django + React + Flutter Projects

**Research Date:** November 3, 2025
**Project Context:** plant_id_community (Django 5.2 + React 19 + Flutter 3.27)
**Purpose:** Convert pending todos to production-ready GitHub issues

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Issue Template Structure](#issue-template-structure)
3. [Acceptance Criteria Patterns](#acceptance-criteria-patterns)
4. [Security Issue Documentation](#security-issue-documentation)
5. [Full-Stack Testing Requirements](#full-stack-testing-requirements)
6. [Production Readiness Checklists](#production-readiness-checklists)
7. [Real-World Examples](#real-world-examples)
8. [Implementation Checklist](#implementation-checklist)

---

## Executive Summary

### Key Research Sources

1. **GitHub Official Documentation**
   - Modern approach: Use YAML-based issue forms (`.github/ISSUE_TEMPLATE/*.yml`)
   - Supports custom fields, dropdowns, checkboxes, markdown blocks
   - YAML frontmatter fields: `title`, `labels`, `assignees`, `projects`, `type`

2. **Django Project Standards**
   - Propose features in GitHub Projects (not ticket tracker)
   - Require: Clear descriptions, reproducible examples, use cases
   - Security issues: Report to security@djangoproject.com (NOT public)

3. **Industry Best Practices**
   - Mercari Production Readiness: Two-phase review (Design + Pre-production)
   - OWASP Security Criteria: Server-side enforcement, fail-secure patterns
   - Atlassian Acceptance Criteria: Given-When-Then format for user stories

### What Makes a Great Issue (TL;DR)

✅ **Must Have:**
- Clear problem statement with context
- Specific location in codebase (file paths + line numbers)
- Concrete acceptance criteria (testable, measurable)
- Testing requirements across all layers (backend, frontend, E2E)
- Implementation options with pros/cons analysis
- Security considerations (if applicable)

❌ **Avoid:**
- Vague descriptions ("improve performance")
- Missing technical details (no file paths)
- Untestable criteria ("make it better")
- Ignoring security implications
- Skipping testing requirements

---

## Issue Template Structure

### YAML Frontmatter (GitHub Official Format)

```yaml
---
name: Feature Request
description: Propose a new feature or enhancement
title: "[FEATURE] "
labels: ["enhancement", "needs-triage"]
assignees: []
projects: ["plant-id-community/main"]
---
```

**Supported Fields:**
- `name`: Template name shown in issue chooser
- `description`: Brief explanation of when to use
- `title`: Pre-filled issue title
- `labels`: Auto-applied tags (array)
- `assignees`: Auto-assign to users with read access
- `projects`: Link to GitHub Projects
- `type`: Template type (`bug`, `feature`, etc.)

### Configuration File (`.github/ISSUE_TEMPLATE/config.yml`)

```yaml
blank_issues_enabled: false  # Force template usage
contact_links:
  - name: Security Vulnerability
    url: mailto:security@example.com
    about: Report security issues privately
  - name: Community Forum
    url: https://example.com/forum
    about: Ask questions to the community
```

### Standard Issue Structure (Based on Research)

```markdown
## Problem Statement
[1-2 sentence description of what needs fixing/building]

**Location:** `path/to/file.py:123-456` (precise file paths)

## Context
- **Why this matters:** [Business/technical justification]
- **Current behavior:** [What happens now]
- **Desired behavior:** [What should happen]
- **Impact:** [Who/what is affected]

## Technical Details

### Affected Components
- `backend/apps/module/file.py` (Model/View/Service)
- `web/src/components/Component.jsx` (React component)
- `plant_community_mobile/lib/screens/screen.dart` (Flutter)

### Proposed Solution

#### Option 1: [Name] (RECOMMENDED)
```python
# Code example
```

**Pros:**
- Pro 1
- Pro 2

**Cons:**
- Con 1

**Effort:** X hours (breakdown)
**Risk:** Low/Medium/High (justification)

#### Option 2: [Alternative]
[Similar structure]

### Database Changes (if applicable)
```sql
-- Migration SQL
```
**Migration Risk:** LOW/MEDIUM/HIGH (data loss, performance impact)

## Acceptance Criteria

- [ ] Criterion 1 (testable, specific)
- [ ] Criterion 2 (measurable outcome)
- [ ] Unit tests pass (backend)
- [ ] Component tests pass (React)
- [ ] E2E tests pass (Playwright)
- [ ] Code review approved
- [ ] Documentation updated

## Testing Requirements

### Backend Tests
- Unit tests: `python manage.py test apps.module.tests --keepdb`
- Expected coverage: 80%+ on modified code

### Frontend Tests
- Component tests: `npm run test`
- E2E tests: `npm run test:e2e`

### Security Testing (if applicable)
- [ ] Input validation tests
- [ ] Authentication/authorization tests
- [ ] SQL injection prevention verified

## Security Considerations
[If applicable: OWASP CWE references, CVSS score, threat model]

## Resources
- Related issues: #123, #456
- Documentation: [Link to docs]
- External references: [Stack Overflow, Django docs, etc.]

## Work Log
### YYYY-MM-DD - Initial Creation
**By:** [Author]
**Actions:** [What was discovered/decided]
```

---

## Acceptance Criteria Patterns

### Format 1: Given-When-Then (Scenario-Oriented)

**Best for:** User stories, feature requests, UI changes

```markdown
## Acceptance Criteria

### Scenario 1: User uploads valid image
- **Given** user is authenticated and viewing forum post
- **When** user drags and drops a valid PNG image (< 5MB)
- **Then** image uploads successfully and displays in preview
- **And** success message shown: "Image uploaded successfully"

### Scenario 2: User uploads invalid file type
- **Given** user attempts to upload .exe file
- **When** file validation runs
- **Then** upload rejected with error: "Invalid file type. Allowed: .jpg, .png, .gif, .webp"
- **And** no database changes occur
```

**When to use:**
- ✅ Feature requests with user interaction
- ✅ UI/UX changes
- ✅ Workflows with multiple steps
- ❌ Low-level technical fixes (use Rule-Based instead)

### Format 2: Rule-Based (Technical Requirements)

**Best for:** Bug fixes, technical debt, performance improvements

```markdown
## Acceptance Criteria

**Functional Requirements:**
- [ ] `Post.save()` wrapped in `transaction.atomic()`
- [ ] Thread statistics updated using `F()` expressions (atomic)
- [ ] `is_new` flag determined before transaction starts
- [ ] `refresh_from_db()` called after F() expression updates

**Testing Requirements:**
- [ ] Unit test: Concurrent post creation (50 threads)
- [ ] Unit test: Verify no lost updates (race condition)
- [ ] Load test: 50 concurrent requests → correct final count
- [ ] All existing tests continue to pass

**Performance Requirements:**
- [ ] No measurable performance degradation (<5ms overhead)
- [ ] Transaction isolation level: READ COMMITTED (default)

**Documentation Requirements:**
- [ ] Inline comments explain F() expression usage
- [ ] Update `DJANGO_PATTERNS.md` with transaction pattern
```

**When to use:**
- ✅ Bug fixes with specific technical requirements
- ✅ Performance optimizations
- ✅ Security fixes
- ✅ Refactoring tasks
- ❌ User-facing features (use Given-When-Then instead)

### Format 3: Checklist (Production Readiness)

**Best for:** Deployment tasks, compliance, infrastructure

```markdown
## Acceptance Criteria

### Design Phase (Before Development)
- [ ] Architecture diagram approved
- [ ] Database schema reviewed
- [ ] Security review completed
- [ ] SLO/SLA defined (99.9% uptime)

### Pre-Production Phase (Before Deployment)
**Code Quality:**
- [ ] Unit tests: >80% coverage
- [ ] Integration tests pass
- [ ] E2E tests pass in staging
- [ ] Linting/type checking passes

**Security:**
- [ ] OWASP Top 10 checklist completed
- [ ] Secrets rotated and stored in env vars
- [ ] Rate limiting enabled (100 req/hour)
- [ ] Input validation on all endpoints

**Observability:**
- [ ] Logging with structured format (JSON)
- [ ] Error tracking (Sentry) configured
- [ ] APM tracing enabled
- [ ] Dashboards created for key metrics

**Deployment:**
- [ ] Rollback plan documented
- [ ] Health checks implemented (`/health`)
- [ ] Zero-downtime deployment tested
- [ ] Staging deployment successful
```

**When to use:**
- ✅ Production deployments
- ✅ Infrastructure changes
- ✅ Compliance requirements
- ✅ Multi-step migrations
- ❌ Single-feature development (too heavyweight)

### Characteristics of Good Acceptance Criteria

Based on Atlassian and industry research:

1. **Unambiguous:** No vague language ("improve", "better", "clean")
2. **Measurable:** Quantifiable outcomes (80% coverage, <50ms response time)
3. **Testable:** Can write automated test to verify
4. **Independent:** Each criterion can be verified separately
5. **Valuable:** Directly relates to business/technical goal
6. **Specific:** Precise file paths, function names, values

**Good Examples:**
- ✅ "Unit test verifies no race condition under 50 concurrent requests"
- ✅ "Migration adds `is_active` column to `forum_attachment` table"
- ✅ "Error message displays: 'Invalid file type. Allowed: .jpg, .png'"

**Bad Examples:**
- ❌ "Make upload faster" (not measurable)
- ❌ "Fix the bug" (not specific)
- ❌ "Improve security" (not testable)

---

## Security Issue Documentation

### OWASP Security Acceptance Criteria Patterns

Based on OWASP user-security-stories repository:

#### Authentication & Authorization

```markdown
## Security Acceptance Criteria

### Authentication
- [ ] All authentication controls enforced on **server-side** (not client-only)
- [ ] Authentication failures logged with user ID, timestamp, IP address
- [ ] Anti-automation in place: Rate limiting (10 attempts/hour per IP)
- [ ] Account lockout after 5 failed attempts (30-minute cooldown)
- [ ] Password reset tokens expire after 1 hour
- [ ] Credentials never pre-populated in forms (prevent plaintext storage)

### Authorization
- [ ] Authorization checks on **every request** (no client-side bypass)
- [ ] Fail securely: Default deny (whitelist approach)
- [ ] User can only access their own resources (tenant isolation)
- [ ] Admin actions require elevated permissions + audit log entry
```

#### Input Validation

```markdown
## Security Acceptance Criteria

### Input Validation
- [ ] All validation routines enforced on **server-side**
- [ ] Validation failures result in request rejection (4xx response)
- [ ] Validation failures logged: `[SECURITY] Invalid input rejected`
- [ ] SQL injection protection: Parameterized queries/ORM only
- [ ] XSS prevention: Output encoding with DOMPurify (React)
- [ ] Path traversal prevention: Whitelist allowed file paths
- [ ] Command injection prevention: Never pass user input to shell

### File Upload Security (Phase 6 Patterns)
- [ ] **Extension validation:** Block dangerous types (.php, .exe, .sh)
- [ ] **MIME type validation:** Check Content-Type header
- [ ] **Magic number validation:** Verify actual file content (Pillow)
- [ ] **Size validation:** Max 5MB per file, 30MB per request
- [ ] **Count validation:** Max 6 images per post
- [ ] **Decompression bomb protection:** Max 178M pixels
- [ ] Files stored outside web root (`/media`, not `/static`)
- [ ] Filenames sanitized: UUID-based (no user input)
```

#### Data Protection

```markdown
## Security Acceptance Criteria

### Data Protection
- [ ] Sensitive data sent in HTTP body/headers (NEVER in URL params)
- [ ] PII encrypted at rest (database-level encryption)
- [ ] Sensitive data in memory overwritten with zeros after use
- [ ] No sensitive data in logs (email → `e***@***.com`)
- [ ] HTTPS enforced (HSTS enabled with 1-year max-age)
- [ ] Secure cookies: `HttpOnly`, `Secure`, `SameSite=Lax`
```

#### Security Testing Requirements

```markdown
## Security Testing Criteria

### Automated Testing
- [ ] OWASP Top 10 automated scan (ZAP/Burp Suite)
- [ ] Dependency vulnerability scan (Snyk/Safety)
- [ ] Secret detection scan (pre-commit hooks)
- [ ] SQL injection tests (sqlmap)
- [ ] XSS tests (XSStrike)

### Manual Testing
- [ ] Penetration testing completed
- [ ] Threat modeling document updated
- [ ] Security review by 2+ engineers
- [ ] All critical/high vulnerabilities remediated before release
```

### Security Issue Template

```markdown
---
name: Security Issue
description: Report a security vulnerability (PRIVATE ONLY)
title: "[SECURITY] "
labels: ["security", "critical"]
assignees: ["security-team"]
---

⚠️ **STOP:** Do NOT file public security issues!
Report to: security@example.com

## Vulnerability Type
- [ ] Authentication bypass
- [ ] Authorization bypass
- [ ] SQL injection
- [ ] XSS (Cross-Site Scripting)
- [ ] CSRF (Cross-Site Request Forgery)
- [ ] File upload vulnerability
- [ ] Information disclosure
- [ ] Other: ___________

## Severity Assessment
**CVSS Score:** [Calculator](https://www.first.org/cvss/calculator/3.1)
- **CWE ID:** CWE-XXX
- **Impact:** Low / Medium / High / Critical
- **Exploitability:** Easy / Moderate / Difficult

## Vulnerability Details
**Location:** `path/to/file.py:123-456`

**Current Code:**
```python
# Vulnerable code
```

**Attack Scenario:**
```bash
# Exploitation steps
```

**Proof of Concept:**
[Screenshots, curl commands, reproduction steps]

## Proposed Fix

**Secure Implementation:**
```python
# Fixed code
```

**Why This Works:**
- Explanation of security improvement

## Acceptance Criteria
- [ ] Vulnerability patched in all affected versions
- [ ] Automated test prevents regression
- [ ] Security advisory published (after fix deployed)
- [ ] Related code audited for similar issues
- [ ] Penetration test confirms fix

## References
- OWASP Cheat Sheet: [Link]
- CWE Details: [Link]
- Security advisories: CVE-YYYY-XXXXX
```

---

## Full-Stack Testing Requirements

### Testing Pyramid for Django + React + Flutter

Based on React Native E2E testing guide and industry best practices:

```
        /\
       /  \  E2E Tests (Slow, Expensive)
      /    \  - Playwright (web)
     /      \ - Flutter integration tests (mobile)
    /--------\
   /          \
  / Integration \ (Medium Speed)
 /    Tests     \ - API integration tests
/________________\ - Component integration tests

━━━━━━━━━━━━━━━━━━
    Unit Tests     (Fast, Cheap)
    - Django unit tests
    - React component tests (Vitest)
    - Flutter widget tests
━━━━━━━━━━━━━━━━━━
```

### Backend Testing Requirements (Django)

```markdown
## Backend Testing Criteria

### Unit Tests (Required)
**Location:** `backend/apps/module/tests/test_feature.py`

**Coverage Requirements:**
- [ ] All new functions/methods have unit tests
- [ ] Code coverage ≥80% on modified files
- [ ] Edge cases covered (empty inputs, null values, max limits)
- [ ] Error paths tested (exceptions, validation failures)

**Test Execution:**
```bash
# Run specific app tests
python manage.py test apps.forum --keepdb -v 2

# Run with coverage
coverage run --source='.' manage.py test apps.forum
coverage report --show-missing
```

**Required Test Cases:**
- [ ] Happy path: Valid inputs → expected outputs
- [ ] Edge cases: Empty strings, null values, max integers
- [ ] Error cases: Invalid inputs → validation errors
- [ ] Concurrent access: Race conditions (if applicable)
- [ ] Database integrity: Foreign keys, constraints
- [ ] Permission checks: Authenticated, anonymous, admin
- [ ] Rate limiting: Exceeds limit → 429 response

### Integration Tests (If External APIs)
- [ ] Mock external API responses (Plant.id, PlantNet)
- [ ] Test circuit breaker logic
- [ ] Test retry logic with exponential backoff
- [ ] Test timeout handling

### Database Tests (Production Equivalence)
- [ ] PostgreSQL test database (NOT SQLite in prod)
- [ ] Migrations run cleanly (no errors)
- [ ] Indexes used (verify with EXPLAIN ANALYZE)
- [ ] No N+1 queries (verify with django-silk)
```

### Frontend Testing Requirements (React)

```markdown
## Frontend Testing Criteria

### Component Tests (Vitest)
**Location:** `web/src/components/__tests__/Component.test.jsx`

**Coverage Requirements:**
- [ ] All new components have tests
- [ ] User interactions covered (click, submit, input)
- [ ] Props variations tested
- [ ] Error states tested
- [ ] Loading states tested
- [ ] Accessibility tested (ARIA attributes, keyboard nav)

**Test Execution:**
```bash
# Run all tests
npm run test

# Watch mode (recommended during development)
npm run test:watch

# Coverage report
npm run test:coverage
```

**Required Test Cases:**
- [ ] Renders correctly with valid props
- [ ] Handles user interactions (fireEvent, userEvent)
- [ ] Displays error messages
- [ ] Shows loading states
- [ ] API calls mocked (MSW)
- [ ] Form validation works
- [ ] Accessibility: ARIA labels present
- [ ] Accessibility: Keyboard navigation works

### E2E Tests (Playwright)
**Location:** `web/tests/e2e/feature.spec.js`

**When Required:**
- ✅ Critical user flows (auth, checkout, data submission)
- ✅ Multi-step workflows
- ✅ Cross-component interactions
- ❌ Simple component behavior (use unit tests)

**Test Execution:**
```bash
# Run all E2E tests
npm run test:e2e

# UI mode (best for debugging)
npm run test:e2e:ui

# Specific test file
npx playwright test tests/e2e/forum.spec.js
```

**Required E2E Scenarios:**
- [ ] User login → Dashboard → Logout
- [ ] Form submission → Success message → Redirect
- [ ] Image upload → Preview → Submit → Display
- [ ] Search → Filter → Results → Detail view
- [ ] Error handling → User-friendly error message

### Performance Tests
- [ ] Lighthouse score ≥90 (performance)
- [ ] First Contentful Paint <1.5s
- [ ] Time to Interactive <3.5s
- [ ] No memory leaks (Chrome DevTools profiling)
```

### Mobile Testing Requirements (Flutter)

```markdown
## Mobile Testing Criteria

### Widget Tests
**Location:** `plant_community_mobile/test/widgets/widget_test.dart`

```dart
testWidgets('ImageUpload displays preview after selection', (tester) async {
  await tester.pumpWidget(MyApp());

  // Find and tap upload button
  final uploadButton = find.byKey(Key('upload_button'));
  await tester.tap(uploadButton);
  await tester.pumpAndSettle();

  // Verify preview shown
  expect(find.byType(ImagePreview), findsOneWidget);
});
```

### Integration Tests
**Location:** `plant_community_mobile/integration_test/app_test.dart`

- [ ] Navigation between screens
- [ ] API integration (mock responses)
- [ ] Local storage (SQLite)
- [ ] Camera/gallery integration

### Platform-Specific Tests
- [ ] iOS simulator tests pass
- [ ] Android emulator tests pass
- [ ] Orientation changes handled
- [ ] Different screen sizes (phone, tablet)
```

### Documentation Requirements

```markdown
## Testing Documentation

- [ ] README updated with test execution commands
- [ ] New test patterns documented in `TESTING_GUIDE.md`
- [ ] Mock data fixtures documented
- [ ] Test environment setup instructions
- [ ] CI/CD integration documented
```

---

## Production Readiness Checklists

### Mercari-Style Production Readiness Framework

Source: [mercari/production-readiness-checklist](https://github.com/mercari/production-readiness-checklist)

#### Service Levels

- **Level A (🌟):** Critical microservices (payment, auth, core features)
- **Level B (⭐):** Standard services (blog, forum, search)
- **Level C (💥):** Experimental features (A/B tests, prototypes)

#### Phase 1: Design Checklist (Before Development)

```markdown
## Design Phase Checklist

### General Architecture
- [ ] **Stateless server design:** No server-side sessions (JWT tokens)
- [ ] **Deploy order independence:** Services can deploy in any order
- [ ] **Exclusive data ownership:** Each service owns its tables

### Security
- [ ] **Authentication:** JWT tokens with 1-hour expiry
- [ ] **Authorization:** Role-based access control (RBAC)
- [ ] **Transport security:** TLS 1.3 for all external traffic

### Sustainability
- [ ] **Team ownership:** 2+ engineers familiar with codebase
- [ ] **OnCall readiness:** Runbooks for common issues
- [ ] **Dependency SLAs:** All dependencies have defined SLAs
- [ ] **Service SLOs:** Target: 99.9% uptime, <200ms p95 latency
```

#### Phase 2: Pre-Production Checklist (Before Deployment)

```markdown
## Pre-Production Checklist

### Maintainability (13 items)
- [ ] **Unit tests:** Run in CI/CD pipeline
- [ ] **Code coverage:** ≥80% reported to Codecov
- [ ] **Environment config:** All secrets in env vars (`.env` file)
- [ ] **Automated build:** CI builds on every commit
- [ ] **Automated deploy:** One-click deploy to staging
- [ ] **Automated rollback:** Revert to previous version <5 minutes
- [ ] **Feature flags:** Gradual rollout capability
- [ ] **Database migrations:** Backward compatible (zero-downtime)
- [ ] **Dependency updates:** Automated security patches (Dependabot)
- [ ] **Documentation:** API docs, architecture diagrams, runbooks
- [ ] **Code style:** Linting enforced (ESLint, Black, dartfmt)
- [ ] **Type checking:** TypeScript (React), mypy (Django), Dart (Flutter)
- [ ] **Pre-commit hooks:** Secret detection, linting, tests

### Observability (15 items)
- [ ] **APM tracing:** Distributed tracing enabled (Datadog, Sentry)
- [ ] **Dashboards:** Key metrics visualized (requests/sec, errors, latency)
- [ ] **Structured logging:** JSON format with correlation IDs
- [ ] **Log levels:** DEBUG in dev, INFO in prod
- [ ] **Error tracking:** Sentry/Rollbar configured
- [ ] **Metrics:** Prometheus/StatsD metrics exported
- [ ] **Alerts:** PagerDuty/Slack for critical errors
- [ ] **Health checks:** `/health` endpoint returns 200 when healthy
- [ ] **Request IDs:** Unique ID per request for tracing
- [ ] **Performance monitoring:** P50/P95/P99 latency tracked
- [ ] **Database query monitoring:** Slow query log enabled (>100ms)
- [ ] **Cache hit rate:** Redis cache metrics tracked
- [ ] **API response times:** Per-endpoint latency monitoring
- [ ] **User journey tracking:** Critical paths instrumented
- [ ] **Synthetic monitoring:** Automated health checks every 5 minutes

### Reliability (19 items)
- [ ] **Auto-scaling:** Horizontal scaling based on CPU/memory
- [ ] **Resource requests/limits:** CPU: 500m-1000m, Memory: 512Mi-1Gi
- [ ] **Capacity planning:** Load test to 2x expected peak traffic
- [ ] **Graceful shutdown:** SIGTERM handled, connections drained
- [ ] **Graceful degradation:** Core features work without dependencies
- [ ] **Health probes:** Kubernetes liveness/readiness probes
- [ ] **Timeouts:** All external calls have timeouts (3-30s)
- [ ] **Retry logic:** Exponential backoff with jitter
- [ ] **Circuit breakers:** Fail fast after 5 consecutive errors
- [ ] **Rate limiting:** 100 req/hour per user, 1000 req/hour per IP
- [ ] **Connection pooling:** Database connection pool (max 20)
- [ ] **Caching strategy:** Redis for hot data (40% hit rate target)
- [ ] **Database replicas:** Read replicas for query scaling
- [ ] **Backup/restore:** Automated daily backups, tested restore
- [ ] **Disaster recovery:** RTO <1 hour, RPO <15 minutes
- [ ] **Blue-green deployment:** Zero-downtime deployment tested
- [ ] **Canary releases:** Gradual rollout (10% → 50% → 100%)
- [ ] **Load testing:** Sustained 1000 req/sec without errors
- [ ] **Chaos testing:** Tested with 1 replica down

### Security (4 items)
- [ ] **Security review:** Completed by security team
- [ ] **Non-root containers:** Container runs as non-root user
- [ ] **Secrets management:** Kubernetes secrets/AWS Secrets Manager
- [ ] **Non-sensitive logging:** No PII in logs (emails redacted)

### Accessibility (6 items)
- [ ] **Design docs:** Architecture diagram, data flow diagram
- [ ] **API documentation:** OpenAPI/Swagger spec published
- [ ] **Runbooks:** Documented procedures for common incidents
- [ ] **Contact info:** Slack channel, email, PagerDuty escalation
- [ ] **Source repository:** Link to GitHub/GitLab repo
- [ ] **Onboarding docs:** New engineer setup guide (<1 hour)

### Data Storage (6+ specialized items)

**General:**
- [ ] **Backup retention:** 30-day retention, automated backups
- [ ] **Failover testing:** Tested automatic failover
- [ ] **Automatic backups:** Daily full backup, hourly incremental
- [ ] **Automatic storage increase:** Auto-expand when 80% full

**Cloud SQL MySQL:**
- [ ] **Read replicas:** 2+ replicas for query distribution
- [ ] **Connection pooling:** PgBouncer/ProxySQL configured

**Cloud Spanner:**
- [ ] **Multi-region:** Data replicated across 3+ regions
- [ ] **Node count:** Sufficient nodes for 60% CPU threshold
```

### Deployment Checklist Template

```markdown
## Deployment Readiness Checklist

### Pre-Deployment (T-1 week)
- [ ] **Staging deployment successful:** No errors in staging
- [ ] **Performance testing:** Load test passed (2x peak traffic)
- [ ] **Security scan:** No critical/high vulnerabilities
- [ ] **Database migration tested:** Tested on staging copy of prod data
- [ ] **Rollback plan documented:** Step-by-step rollback instructions
- [ ] **Feature flags configured:** New features behind flags
- [ ] **Monitoring configured:** Dashboards and alerts ready
- [ ] **Runbook updated:** Common issues and resolutions
- [ ] **Stakeholders notified:** Email sent to affected teams
- [ ] **Backup verified:** Recent backup exists and tested

### Deployment Day (T-0)
- [ ] **Deploy window scheduled:** Low-traffic window (e.g., 2 AM PST)
- [ ] **Team available:** 2+ engineers on call during deploy
- [ ] **Health checks pass:** `/health` returns 200 before deploy
- [ ] **Database migration runs:** Migration completes successfully
- [ ] **Application deploys:** New version rolled out
- [ ] **Smoke tests pass:** Critical paths tested manually
- [ ] **Metrics normal:** No spike in errors/latency
- [ ] **Rollback ready:** Rollback script tested and ready

### Post-Deployment (T+1 day)
- [ ] **No critical errors:** Error rate <0.1%
- [ ] **Performance within SLO:** P95 latency <200ms
- [ ] **User feedback positive:** No major complaints
- [ ] **Monitoring stable:** No anomalies in metrics
- [ ] **Documentation updated:** CHANGELOG.md updated
- [ ] **Team debriefing:** Retrospective scheduled

### Rollback Trigger Criteria
Rollback immediately if:
- Error rate >1%
- P95 latency >500ms (2.5x baseline)
- Database queries failing (>10% failure rate)
- Memory leak detected (>80% memory usage)
- Critical feature completely broken
```

---

## Real-World Examples

### Example 1: Django Race Condition Fix (From Project)

```markdown
# Race Condition in Post Statistics Updates

## Problem Statement

The `Post.save()` method updates thread statistics (post_count, last_activity) without transaction protection, causing potential race conditions and lost updates under concurrent access.

**Location:** `backend/apps/forum/models.py:348-357`

## Context

- **Discovery:** Data Integrity Guardian audit (Nov 3, 2025)
- **Severity:** P1 (Critical race condition)
- **Impact:** Post counts become inaccurate under load (50+ concurrent posts)

**Race Condition Scenario:**
```
User A creates Post 1 → Reads Thread.post_count (5)
User B creates Post 2 → Reads Thread.post_count (5)
User A commits post_count = 6
User B commits post_count = 6  ← Lost Post A's increment!
```

## Technical Details

### Current Code (Vulnerable)
```python
def save(self, *args, **kwargs):
    is_new = not self.pk
    super().save(*args, **kwargs)

    if is_new and self.is_active:
        # ❌ Race condition: Read-then-write without atomicity
        thread = Thread.objects.get(pk=self.thread_id)
        thread.post_count += 1
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=['post_count', 'last_activity_at'])
```

### Proposed Solution: Transaction + F() Expressions

```python
from django.db import transaction
from django.db.models import F

def save(self, *args, **kwargs):
    is_new = not self.pk

    with transaction.atomic():
        super().save(*args, **kwargs)

        if is_new and self.is_active:
            # ✅ Atomic update at database level
            Thread.objects.filter(pk=self.thread_id).update(
                post_count=F('post_count') + 1,
                last_activity_at=timezone.now()
            )
            self.thread.refresh_from_db(fields=['post_count', 'last_activity_at'])
```

**Why This Works:**
- `transaction.atomic()`: Ensures all-or-nothing execution
- `F('post_count') + 1`: Database-level increment (no read-then-write)
- `refresh_from_db()`: Sync Python object with DB state

**Performance:** <5ms overhead per post creation

### Affected Components
- `backend/apps/forum/models.py` (Post.save method)
- `backend/apps/forum/viewsets/post_viewset.py` (create action)
- `backend/apps/forum/api.py` (post creation endpoint)

### Database Impact
- **Schema changes:** None
- **Migration required:** No
- **Backward compatible:** Yes

## Acceptance Criteria

### Functional Requirements
- [ ] `Post.save()` wrapped in `transaction.atomic()`
- [ ] Thread.post_count uses `F('post_count') + 1` (atomic)
- [ ] Thread.last_activity_at updated in same query
- [ ] `refresh_from_db()` called after F() expression

### Testing Requirements

**Backend Unit Tests:**
- [ ] Test: Single post creation → post_count increments by 1
- [ ] Test: 50 concurrent posts → final count exactly 50
- [ ] Test: Transaction rollback → post_count unchanged
- [ ] Test: is_active=False post → post_count NOT incremented
- [ ] Test: Existing tests continue to pass

**Load Testing:**
```bash
# Locust load test: 50 concurrent users creating posts
locust -f tests/load/test_post_creation.py --users 50 --spawn-rate 10
```
- [ ] Load test: 500 posts created → post_count = 500 (no lost updates)
- [ ] Load test: Error rate <0.1%
- [ ] Load test: P95 latency <200ms

**Test Execution:**
```bash
# Run forum tests
python manage.py test apps.forum.tests.test_models --keepdb -v 2

# Run with race condition detection
python manage.py test apps.forum.tests.test_models --parallel 4
```

### Performance Requirements
- [ ] Transaction overhead <5ms per post creation
- [ ] No deadlocks under concurrent load
- [ ] Database CPU usage increase <10%

### Documentation Requirements
- [ ] Inline comments explain F() expression usage
- [ ] Update `DJANGO_PATTERNS.md` with transaction pattern
- [ ] Add to `KNOWN_ISSUES.md` under "Resolved"

## Resources

- Django F() expressions: https://docs.djangoproject.com/en/5.0/ref/models/expressions/#f-expressions
- Django transactions: https://docs.djangoproject.com/en/5.0/topics/db/transactions/
- Related issue: #004 (Reaction toggle race condition)
- Audit report: `docs/audit/2025-11-03-data-integrity-audit.md`

## Labels
`bug`, `django`, `race-condition`, `p1-critical`, `data-integrity`

## Assignees
@backend-team

## Milestone
v1.1 (Production Readiness)
```

### Example 2: React Image Upload Feature (Phase 6 Patterns)

```markdown
# Image Upload Widget with Drag-and-Drop

## Problem Statement

Forum posts need ability to upload images (max 6) with drag-and-drop interface, preview, validation, and delete functionality.

**Location:** `web/src/components/ImageUploadWidget.jsx` (new file)

## Context

- **Feature Request:** Phase 6 - Image Upload Support
- **Priority:** P1 (User-facing feature)
- **Design:** Material Design drag-and-drop pattern

## Technical Details

### Requirements

**Frontend (React):**
- Drag-and-drop zone with visual feedback
- File input fallback for browsers without drag-and-drop
- Image preview with thumbnails
- Delete button per image
- Validation: File type, size, count
- Loading states during upload
- Error handling with user-friendly messages

**Backend (Django):**
- Endpoint: `POST /api/forum/posts/{post_id}/upload_image/`
- Validation: Extension, MIME type, magic number (Pillow)
- Max 6 images per post, 5MB per image
- Store in `/media/forum/attachments/`
- UUID-based filenames (prevent path traversal)

### Component API

```jsx
<ImageUploadWidget
  postId={post.id}
  existingImages={post.attachments}
  maxImages={6}
  maxSizeMB={5}
  onUploadSuccess={(attachment) => { /* update state */ }}
  onUploadError={(error) => { /* show toast */ }}
  onDelete={(attachmentId) => { /* remove from list */ }}
/>
```

### Acceptance Criteria (Given-When-Then)

#### Scenario 1: User uploads valid image via drag-and-drop
- **Given** user is viewing forum post editor
- **And** post has 0 existing images
- **When** user drags and drops a valid PNG file (2MB)
- **Then** upload progress indicator shows
- **And** image uploads successfully within 2 seconds
- **And** thumbnail preview appears
- **And** success toast displays: "Image uploaded successfully"
- **And** image count shows "1 of 6 images"

#### Scenario 2: User uploads image via file input (fallback)
- **Given** drag-and-drop not supported (e.g., mobile browser)
- **When** user clicks "Choose File" button
- **And** selects valid JPEG file from file picker
- **Then** upload succeeds with same behavior as drag-and-drop

#### Scenario 3: User uploads invalid file type
- **Given** user drags and drops .exe file
- **When** file validation runs (client-side)
- **Then** upload immediately rejected (no API call)
- **And** error toast displays: "Invalid file type. Allowed: .jpg, .png, .gif, .webp"
- **And** no preview shown

#### Scenario 4: User exceeds image count limit
- **Given** post already has 6 images
- **When** user attempts to upload 7th image
- **Then** upload blocked (button disabled)
- **And** error message: "Maximum 6 images per post"

#### Scenario 5: User deletes uploaded image
- **Given** post has 3 uploaded images
- **When** user clicks delete button on 2nd image
- **Then** confirmation modal displays: "Delete this image?"
- **When** user confirms deletion
- **Then** API call: `DELETE /api/forum/attachments/{id}/`
- **And** image removed from preview
- **And** image count updates to "2 of 6 images"

### Testing Requirements

#### Frontend Unit Tests (Vitest)
**Location:** `web/src/components/__tests__/ImageUploadWidget.test.jsx`

```javascript
describe('ImageUploadWidget', () => {
  it('renders drag-and-drop zone with instructions', () => {
    render(<ImageUploadWidget postId="123" />);
    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
  });

  it('validates file type before upload', async () => {
    const { user } = setup();
    const file = new File(['content'], 'test.exe', { type: 'application/x-msdownload' });

    await user.upload(screen.getByLabelText(/choose file/i), file);

    expect(screen.getByText(/invalid file type/i)).toBeInTheDocument();
    expect(mockUploadAPI).not.toHaveBeenCalled();
  });

  it('shows preview after successful upload', async () => {
    mockUploadAPI.mockResolvedValue({ id: '123', url: '/media/test.jpg' });

    await uploadFile('test.jpg');

    expect(screen.getByAltText(/preview/i)).toBeInTheDocument();
    expect(screen.getByText(/1 of 6 images/i)).toBeInTheDocument();
  });

  it('disables upload when max images reached', () => {
    render(<ImageUploadWidget postId="123" existingImages={sixImages} />);

    expect(screen.getByLabelText(/choose file/i)).toBeDisabled();
    expect(screen.getByText(/maximum 6 images/i)).toBeInTheDocument();
  });
});
```

**Required Test Cases:**
- [ ] Renders drag-and-drop zone
- [ ] File input fallback works
- [ ] Validates file type (client-side)
- [ ] Validates file size (client-side)
- [ ] Validates image count (max 6)
- [ ] Shows upload progress indicator
- [ ] Displays preview after upload
- [ ] Shows error toast on upload failure
- [ ] Delete button triggers confirmation modal
- [ ] Confirms deletion removes image
- [ ] Accessibility: Keyboard navigation works
- [ ] Accessibility: Screen reader announces upload status

#### Backend Unit Tests (Django)
**Location:** `backend/apps/forum/tests/test_attachment.py`

```python
class AttachmentUploadTests(TestCase):
    def test_upload_valid_image(self):
        """Test uploading valid PNG image succeeds."""
        image = create_test_image('test.png', size=(800, 600))
        response = self.client.post(
            f'/api/forum/posts/{self.post.id}/upload_image/',
            {'image': image},
            format='multipart'
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertTrue(Attachment.objects.filter(post=self.post).exists())

    def test_reject_non_image_file(self):
        """Test rejection of .exe file disguised as image."""
        fake_image = SimpleUploadedFile('shell.jpg', b'MZ\x90\x00')  # .exe header
        response = self.client.post(
            f'/api/forum/posts/{self.post.id}/upload_image/',
            {'image': fake_image}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('not a valid image', response.data['error'])

    def test_reject_decompression_bomb(self):
        """Test rejection of extremely large image (decompression bomb)."""
        # Create 20000x20000 image (400M pixels, exceeds 178M limit)
        large_image = create_test_image('bomb.png', size=(20000, 20000))
        response = self.client.post(
            f'/api/forum/posts/{self.post.id}/upload_image/',
            {'image': large_image}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Image too large', response.data['error'])

    def test_enforce_max_images_per_post(self):
        """Test rejection when post already has 6 images."""
        # Create 6 existing attachments
        for i in range(6):
            Attachment.objects.create(post=self.post, image=f'existing{i}.jpg')

        image = create_test_image('extra.jpg')
        response = self.client.post(
            f'/api/forum/posts/{self.post.id}/upload_image/',
            {'image': image}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Maximum 6 images', response.data['error'])
```

**Required Test Cases:**
- [ ] Upload valid image (PNG, JPEG, GIF, WebP)
- [ ] Reject invalid extension (.exe, .php, .sh)
- [ ] Reject invalid MIME type
- [ ] Reject non-image content (magic number validation)
- [ ] Reject oversized file (>5MB)
- [ ] Reject decompression bomb (>178M pixels)
- [ ] Enforce max 6 images per post
- [ ] Delete attachment removes file from disk
- [ ] Authenticated user can upload to own post
- [ ] Unauthenticated user receives 401
- [ ] User cannot upload to another user's post

#### E2E Tests (Playwright)
**Location:** `web/tests/e2e/image-upload.spec.js`

```javascript
test('complete image upload workflow', async ({ page }) => {
  await page.goto('/forum/posts/123/edit');

  // Upload first image
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('fixtures/test-image.jpg');

  // Wait for upload to complete
  await expect(page.locator('.image-preview')).toBeVisible();
  await expect(page.getByText('1 of 6 images')).toBeVisible();

  // Upload second image via drag-and-drop
  const dropzone = page.locator('.dropzone');
  await dropzone.dragAndDrop('fixtures/test-image-2.png');
  await expect(page.getByText('2 of 6 images')).toBeVisible();

  // Delete first image
  await page.locator('.image-preview').first().locator('button[aria-label="Delete"]').click();
  await page.getByRole('button', { name: 'Confirm' }).click();
  await expect(page.getByText('1 of 6 images')).toBeVisible();

  // Submit post with image
  await page.getByRole('button', { name: 'Publish' }).click();
  await expect(page).toHaveURL(/\/forum\/posts\/\d+/);

  // Verify image displays in published post
  await expect(page.locator('article img')).toBeVisible();
});

test('handles upload errors gracefully', async ({ page }) => {
  await page.goto('/forum/posts/123/edit');

  // Upload invalid file type
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('fixtures/invalid.exe');

  // Verify error message
  await expect(page.getByText(/invalid file type/i)).toBeVisible();
  await expect(page.locator('.image-preview')).not.toBeVisible();
});
```

### Security Requirements

**File Upload Security (Phase 6 Patterns):**
- [ ] Extension validation: Block .php, .exe, .sh, .jsp, .asp
- [ ] MIME type validation: Check Content-Type header
- [ ] Magic number validation: Pillow Image.verify()
- [ ] Size validation: Max 5MB per file
- [ ] Count validation: Max 6 images per post
- [ ] Decompression bomb protection: Max 178M pixels
- [ ] Path traversal prevention: UUID-based filenames only
- [ ] Files stored outside web root: `/media/forum/attachments/`
- [ ] Content Security Policy: `img-src 'self'`

### Performance Requirements
- [ ] Upload <2 seconds for 1MB image on 3G connection
- [ ] Preview thumbnail generation <500ms
- [ ] Client-side validation <100ms (no blocking)
- [ ] Multiple uploads supported (parallelized)

### Accessibility Requirements
- [ ] Drag-and-drop zone keyboard accessible
- [ ] File input has proper label
- [ ] Upload status announced to screen readers
- [ ] Error messages associated with form field (aria-describedby)
- [ ] Delete buttons have descriptive aria-labels
- [ ] Focus management during upload/delete
- [ ] High contrast mode supported

### Documentation Requirements
- [ ] Component API documented in Storybook
- [ ] Usage examples in `web/docs/components/ImageUploadWidget.md`
- [ ] Backend API documented in OpenAPI spec
- [ ] Security considerations documented
- [ ] Update Phase 6 completion doc

## Resources

- Design mockups: Figma link
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- Pillow Image.verify(): https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify
- Related: `CLAUDE.md` Phase 6 security patterns (line 289-347)

## Labels
`feature`, `react`, `django`, `file-upload`, `p1-critical`, `phase-6`

## Milestone
Phase 6: Search & Image Upload
```

---

## Implementation Checklist

Use this checklist when creating GitHub issues from todos:

### Pre-Conversion Review
- [ ] Todo priority is P1 or P2 (defer P3/P4)
- [ ] Technical details are complete and accurate
- [ ] File paths and line numbers are current
- [ ] Proposed solutions are still valid
- [ ] No security concerns require private handling

### Issue Structure (Required Sections)
- [ ] **Problem Statement:** 1-2 sentences, specific location
- [ ] **Context:** Why it matters, current vs desired behavior
- [ ] **Technical Details:** Affected files, proposed solution, database changes
- [ ] **Acceptance Criteria:** Testable, specific, measurable
- [ ] **Testing Requirements:** Backend, frontend, E2E (if applicable)
- [ ] **Security Considerations:** If security-related
- [ ] **Resources:** Links to docs, related issues, external references

### Acceptance Criteria Quality
- [ ] Use appropriate format (Given-When-Then, Rule-Based, or Checklist)
- [ ] Every criterion is testable (can write automated test)
- [ ] Every criterion is measurable (numeric values where applicable)
- [ ] Backend testing requirements specified
- [ ] Frontend testing requirements specified (if UI change)
- [ ] E2E testing requirements specified (if critical flow)
- [ ] Security testing specified (if security-related)

### Testing Requirements Completeness
- [ ] Backend: Unit test execution command provided
- [ ] Backend: Expected coverage percentage specified
- [ ] Frontend: Component test requirements listed
- [ ] Frontend: E2E test scenarios described
- [ ] Load testing requirements (if performance-critical)
- [ ] Concurrent access testing (if race condition)
- [ ] Security testing (if security fix)

### Metadata
- [ ] Labels assigned (bug/feature, django/react/flutter, priority, area)
- [ ] Milestone assigned (version/phase)
- [ ] Assignees suggested (if known)
- [ ] Related issues linked (#123, #456)
- [ ] Estimate provided (hours/story points)

### Security-Specific Checklist
For security issues only:
- [ ] ⚠️ **STOP:** Is this a vulnerability? (Report privately)
- [ ] CWE ID identified
- [ ] CVSS score calculated
- [ ] Attack scenario documented
- [ ] Proof of concept included (if safe to share)
- [ ] Proposed fix validated
- [ ] Related code audited for similar issues

### Final Quality Check
- [ ] Issue title is clear and specific (not vague)
- [ ] All code blocks have syntax highlighting
- [ ] All file paths are absolute (not relative)
- [ ] All links are valid and accessible
- [ ] Markdown formatting is correct
- [ ] Issue can be implemented by another engineer (not just you)

---

## Recommended Next Steps

1. **Create GitHub Issue Templates**
   - Create `.github/ISSUE_TEMPLATE/` directory
   - Add templates: `bug_report.yml`, `feature_request.yml`, `security.yml`
   - Add `config.yml` to customize issue chooser

2. **Convert High-Priority Todos**
   - Start with P1 issues (critical bugs, security fixes)
   - Use this guide to structure each issue
   - Link related issues together

3. **Update Project Documentation**
   - Add `CONTRIBUTING.md` with issue creation guidelines
   - Update `README.md` with link to issue templates
   - Document testing requirements in `TESTING_GUIDE.md`

4. **Automate Quality Checks**
   - GitHub Actions workflow to validate issue structure
   - Require acceptance criteria checkbox
   - Auto-label based on file paths

5. **Train Team**
   - Share this guide with all contributors
   - Code review checklist includes acceptance criteria
   - Regular retrospectives on issue quality

---

## Appendix: Quick Reference

### Issue Format Cheat Sheet

```markdown
# [Clear, Specific Title]

## Problem Statement
[1-2 sentences, file:line]

## Technical Details
[Affected files, proposed solution, DB changes]

## Acceptance Criteria
- [ ] Criterion 1 (testable)
- [ ] Criterion 2 (measurable)
- [ ] Tests pass (backend, frontend, E2E)

## Testing Requirements
**Backend:** [Commands, coverage]
**Frontend:** [Component tests, E2E scenarios]

## Resources
- [Links to docs, related issues]
```

### Label Taxonomy

```
Type:
  - bug
  - feature
  - enhancement
  - documentation
  - security

Priority:
  - p1-critical
  - p2-high
  - p3-medium
  - p4-low

Area:
  - django
  - react
  - flutter
  - database
  - api
  - ui/ux

Status:
  - needs-triage
  - in-progress
  - blocked
  - ready-for-review
```

### Useful Links

- **GitHub Docs:** https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests
- **OWASP Cheat Sheets:** https://cheatsheetseries.owasp.org/
- **Django Best Practices:** https://docs.djangoproject.com/en/dev/internals/contributing/
- **React Testing Library:** https://testing-library.com/docs/react-testing-library/intro/
- **Playwright Docs:** https://playwright.dev/

---

**End of Research Document**

This guide synthesizes best practices from:
- GitHub official documentation
- Django project standards
- OWASP security acceptance criteria
- Mercari production readiness framework
- Atlassian acceptance criteria guidelines
- Real-world examples from this project
