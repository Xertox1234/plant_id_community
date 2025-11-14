# Quick Guide: Converting Todos to GitHub Issues

**Purpose:** Fast reference for converting pending todos to production-ready GitHub issues
**Full Research:** See `GITHUB_ISSUE_BEST_PRACTICES_RESEARCH.md` for comprehensive guide

---

## 5-Minute Conversion Checklist

### 1. Copy Existing Todo Structure (Already Good!)

Your todos already have excellent structure:
- ✅ Problem statement with location
- ✅ Proposed solutions with pros/cons
- ✅ Acceptance criteria
- ✅ Technical details
- ✅ Work log

**What to Add:**

```diff
+ ## Labels
+ `bug`, `django`, `race-condition`, `p1-critical`, `data-integrity`

+ ## Milestone
+ v1.1 (Production Readiness)

+ ## Assignees
+ @backend-team

+ ## Testing Requirements (EXPAND THIS SECTION)
+ **Backend Unit Tests:**
+ ```bash
+ python manage.py test apps.forum.tests.test_models --keepdb -v 2
+ ```
+ - [ ] Test: Single post creation → post_count increments by 1
+ - [ ] Test: 50 concurrent posts → final count exactly 50
+ - [ ] Test: Transaction rollback → post_count unchanged
+
+ **Load Testing:**
+ - [ ] Load test: 500 posts created → post_count = 500 (no lost updates)
+ - [ ] Load test: Error rate <0.1%
```

### 2. Update Acceptance Criteria Format

**Your Current Format (Good):**
```markdown
## Acceptance Criteria
- [ ] Post.save() wrapped in transaction.atomic()
- [ ] Thread statistics use F() expressions
- [ ] Unit tests pass
```

**Enhanced Format (Better):**
```markdown
## Acceptance Criteria

### Functional Requirements
- [ ] `Post.save()` wrapped in `transaction.atomic()`
- [ ] Thread.post_count uses `F('post_count') + 1` (atomic)
- [ ] `refresh_from_db()` called after F() expression

### Testing Requirements
- [ ] Unit test: Concurrent post creation (50 threads)
- [ ] Unit test: Verify no lost updates (race condition)
- [ ] Load test: 50 concurrent requests → correct final count
- [ ] All existing tests continue to pass

### Performance Requirements
- [ ] Transaction overhead <5ms per post creation
- [ ] No deadlocks under concurrent load

### Documentation Requirements
- [ ] Inline comments explain F() expression usage
- [ ] Update `DJANGO_PATTERNS.md` with transaction pattern
```

### 3. Add Testing Commands

Every issue needs executable test commands:

```markdown
## Testing Requirements

### Backend Unit Tests
```bash
# Run specific test file
python manage.py test apps.forum.tests.test_models --keepdb -v 2

# Run with coverage
coverage run --source='apps.forum' manage.py test apps.forum
coverage report --show-missing

# Run in parallel (race condition detection)
python manage.py test apps.forum.tests.test_models --parallel 4
```

**Required Test Cases:**
- [ ] Test case 1 (specific scenario)
- [ ] Test case 2 (edge case)
- [ ] Test case 3 (error handling)

**Expected Results:**
- [ ] All tests pass (green)
- [ ] Coverage ≥80% on modified files
- [ ] No new warnings or errors
```

### 4. Specify Exact Files to Modify

Be extremely specific about what changes:

```markdown
## Affected Files

**Primary Changes:**
- `backend/apps/forum/models.py:348-357` (Post.save method)
  - Wrap in transaction.atomic()
  - Use F() expressions for counter updates

**Related Changes:**
- `backend/apps/forum/tests/test_models.py` (add concurrency tests)
- `backend/apps/forum/tests/test_race_conditions.py` (new file)

**Documentation Updates:**
- `backend/docs/patterns/DJANGO_PATTERNS.md` (add F() expression pattern)
- `CHANGELOG.md` (add entry under v1.1)
```

### 5. Add Security Considerations (If Applicable)

For security-related issues:

```markdown
## Security Considerations

**CWE Reference:** CWE-434 (Unrestricted Upload of File with Dangerous Type)
**CVSS Score:** 6.5 (Medium)

**Threat Model:**
- Attacker uploads .php file disguised as .jpg
- If server misconfigured, PHP code executes
- Potential for remote code execution

**Mitigation Layers:**
1. Extension validation (client-side, easy to bypass)
2. MIME type validation (header check, can be spoofed)
3. **Magic number validation (content verification)** ← THIS FIX
4. Files stored outside web root (defense-in-depth)

**Related Security Patterns:**
- See `CLAUDE.md` Phase 6 security patterns (line 289-347)
- OWASP File Upload Cheat Sheet: [link]
```

---

## Conversion Template

Use this template for all P1/P2 issues:

```markdown
# [Clear Title from Todo]

## Problem Statement
[Copy from todo - already good]

**Location:** `file/path.py:123-456`

## Context
[Copy from todo "Findings" section]

- **Discovery:** [When/how found]
- **Severity:** P1/P2 (justification)
- **Impact:** [Who/what affected]

## Technical Details

### Current Code (Vulnerable/Broken)
```python
# Copy vulnerable code from todo
```

### Proposed Solution (RECOMMENDED)
```python
# Copy recommended solution from todo
```

**Why This Works:**
- [Explanation]

**Performance Impact:** [Quantified]

### Affected Files
**Primary Changes:**
- `path/to/file.py:123-456` (what changes)

**Related Changes:**
- `path/to/test.py` (add tests)

**Documentation Updates:**
- `CHANGELOG.md`

### Database Changes (if applicable)
```sql
-- Migration SQL
```
**Migration Risk:** LOW/MEDIUM/HIGH

## Acceptance Criteria

### Functional Requirements
[Convert todo acceptance criteria to specific checklist]

### Testing Requirements

**Backend Unit Tests:**
```bash
# Exact command to run tests
python manage.py test apps.module.tests --keepdb -v 2
```

**Required Test Cases:**
- [ ] Happy path: [specific scenario]
- [ ] Edge case: [boundary condition]
- [ ] Error case: [failure scenario]
- [ ] Concurrent access: [if applicable]

**Expected Results:**
- [ ] All tests pass
- [ ] Coverage ≥80%
- [ ] No new warnings

[Add Frontend/E2E sections if applicable]

### Performance Requirements
- [ ] Metric 1: [quantified]
- [ ] Metric 2: [measurable]

### Documentation Requirements
- [ ] Code comments updated
- [ ] Pattern documented in relevant guide
- [ ] CHANGELOG.md updated

## Security Considerations
[If security-related: CWE, CVSS, threat model, mitigation layers]

[If not security-related: Remove this section]

## Resources
- Related issues: #XXX
- Django docs: [link]
- Stack Overflow: [link]
- OWASP guide: [link]
- Audit report: `path/to/report.md`

## Labels
`bug`/`feature`, `django`/`react`, `p1-critical`/`p2-high`, `[area]`

## Milestone
v1.1 (Production Readiness)

## Assignees
@backend-team / @frontend-team

## Estimate
[X hours - from todo "Effort" section]
```

---

## Label Taxonomy (For This Project)

```
Type:
  bug          - Something is broken
  feature      - New functionality
  enhancement  - Improvement to existing feature
  security     - Security fix
  refactor     - Code cleanup, no behavior change
  docs         - Documentation only

Technology Stack:
  django       - Backend Python code
  react        - Web frontend
  flutter      - Mobile app
  database     - Schema/migration changes
  api          - REST API endpoints
  ci-cd        - Build/deploy pipeline

Priority (From Todos):
  p1-critical  - Data loss, security, race conditions
  p2-high      - Performance, UX issues, technical debt
  p3-medium    - Nice-to-have improvements
  p4-low       - Future enhancements

Area (From Codebase):
  forum        - Forum app (posts, threads, categories)
  blog         - Blog/CMS (Wagtail)
  plant-id     - Plant identification service
  auth         - Authentication/authorization
  ui-ux        - User interface/experience
  performance  - Speed/optimization
  data-integrity - Database consistency
```

---

## Issue Title Conventions

**Good Titles (Specific):**
- ✅ "Fix race condition in Post.save() thread statistics update"
- ✅ "Add CASCADE to SET_NULL for PlantDiseaseResult.identified_disease"
- ✅ "Implement magic number validation for image uploads"
- ✅ "Add soft delete to Attachment model for consistency"

**Bad Titles (Vague):**
- ❌ "Fix bug in forum"
- ❌ "Improve security"
- ❌ "Update database"
- ❌ "Make uploads better"

**Pattern:**
```
[Action Verb] [Specific Component] [Optional: in Location]

Examples:
Fix race condition in Post.save() thread statistics
Add transaction boundary to post creation workflow
Implement Pillow validation for image uploads
Change CASCADE to SET_NULL for disease results
```

---

## Testing Requirements by Issue Type

### Bug Fixes (Race Conditions, Data Integrity)

```markdown
## Testing Requirements

### Unit Tests (Required)
```bash
python manage.py test apps.forum.tests.test_models --keepdb -v 2
```

**Test Cases:**
- [ ] Single operation works correctly (baseline)
- [ ] Concurrent operations produce correct result
- [ ] Edge cases handled (null, empty, max values)
- [ ] Error conditions raise appropriate exceptions

**Concurrency Testing:**
```bash
# Run tests in parallel to detect race conditions
python manage.py test apps.forum --parallel 4
```

### Load Testing (For Critical Paths)
```bash
locust -f tests/load/test_forum.py --users 50 --spawn-rate 10
```

**Acceptance Criteria:**
- [ ] 500 operations → correct final state (no lost updates)
- [ ] Error rate <0.1%
- [ ] P95 latency <200ms
```

### Security Fixes (Input Validation, File Upload)

```markdown
## Testing Requirements

### Unit Tests
```bash
python manage.py test apps.forum.tests.test_attachment --keepdb -v 2
```

**Test Cases:**
- [ ] Valid input accepted (baseline)
- [ ] Invalid input rejected with clear error
- [ ] Malicious input safely handled (no code execution)
- [ ] Edge cases (max size, unusual formats)

### Security Tests
- [ ] Upload .exe disguised as .jpg → rejected
- [ ] Upload decompression bomb → rejected
- [ ] Upload with path traversal attempt (../../etc/passwd) → sanitized
- [ ] SQL injection attempt in search → parameterized query prevents
- [ ] XSS attempt in post content → DOMPurify sanitizes

**Security Scan:**
```bash
# Run OWASP dependency check
safety check --json
```
```

### Feature Additions (New Functionality)

```markdown
## Testing Requirements

### Backend Unit Tests
```bash
python manage.py test apps.module.tests --keepdb -v 2
```
- [ ] Core functionality works (happy path)
- [ ] Error handling graceful
- [ ] Permissions enforced
- [ ] Rate limiting works

### Frontend Component Tests
```bash
cd web && npm run test
```
- [ ] Component renders correctly
- [ ] User interactions work (click, submit)
- [ ] Error states display
- [ ] Loading states display
- [ ] Accessibility (ARIA, keyboard)

### E2E Tests (Critical Flows Only)
```bash
cd web && npm run test:e2e
```
- [ ] End-to-end workflow succeeds
- [ ] Error handling user-friendly
- [ ] Cross-browser compatibility (Chrome, Firefox, Safari)
```

---

## Priority Mapping (From Todos)

| Todo Priority | GitHub Label | When to Address |
|---------------|--------------|-----------------|
| P1 | `p1-critical` | Before production launch |
| P2 | `p2-high` | Within 2 weeks |
| P3 | `p3-medium` | Next sprint |
| P4 | `p4-low` | Backlog |

**Current P1 Issues to Convert:**
1. `001-pending-p1-transaction-boundaries-post-save.md` → Race condition fix
2. `002-pending-p1-cascade-plant-disease-result.md` → Data loss prevention
3. `004-pending-p1-reaction-toggle-race-condition.md` → Race condition fix
4. `005-pending-p1-attachment-soft-delete.md` → Pattern consistency
5. `008-pending-p1-image-magic-number-validation.md` → Security fix

---

## Quick Validation Checklist

Before creating GitHub issue:

- [ ] **Title:** Clear, specific, <80 characters
- [ ] **Problem:** Specific file paths with line numbers
- [ ] **Solution:** Code examples with explanations
- [ ] **Tests:** Executable commands + expected results
- [ ] **Acceptance Criteria:** Testable, measurable, specific
- [ ] **Labels:** Type + tech + priority + area
- [ ] **Estimate:** Hours (from todo "Effort" field)
- [ ] **Resources:** Links to docs, related issues

**5-Second Test:** Can another engineer implement this without asking questions?
- ✅ Yes → Create issue
- ❌ No → Add more details

---

## Example: Perfect GitHub Issue

See `GITHUB_ISSUE_BEST_PRACTICES_RESEARCH.md` → "Real-World Examples" section for two complete examples:

1. **Example 1:** Race condition fix (Django backend)
2. **Example 2:** Image upload feature (React + Django)

Both examples demonstrate:
- Clear problem statement with context
- Multiple proposed solutions with tradeoffs
- Comprehensive acceptance criteria (functional, testing, performance, docs)
- Specific test commands and expected results
- Security considerations (for Example 2)
- All required metadata (labels, milestone, assignees)

---

**Next Step:** Choose a P1 todo and convert it using this template!

**Recommended Order:**
1. `008-pending-p1-image-magic-number-validation.md` (security, straightforward)
2. `001-pending-p1-transaction-boundaries-post-save.md` (race condition)
3. `005-pending-p1-attachment-soft-delete.md` (pattern consistency)
4. `004-pending-p1-reaction-toggle-race-condition.md` (race condition)
5. `002-pending-p1-cascade-plant-disease-result.md` (schema change)
