# Todos Directory

**Generated**: October 25, 2025
**Source**: Comprehensive multi-agent codebase audit
**Total Issues**: 34 across 4 priority levels

---

## Quick Reference

### Priority Levels

- **P1 (Critical)**: Production blockers, security incidents, data integrity issues
- **P2 (High)**: Performance problems, code quality gaps, developer experience
- **P3 (Medium)**: Security enhancements, compliance, optimization opportunities
- **P4 (Low)**: Nice-to-haves, documentation, polish

### Effort Summary

| Priority | Count | Total Effort | Average Effort |
|----------|-------|--------------|----------------|
| P1 | 5 | 8 hours | 1.6 hours |
| P2 | 8 | 25 hours | 3.1 hours |
| P3 | 12 | 14 hours | 1.2 hours |
| P4 | 9 | 23 hours | 2.6 hours |
| **Total** | **34** | **70 hours** | **2.1 hours** |

### Quick Wins (<1 hour)

10 issues totaling ~3 hours:
- 003: Vite Port Mismatch (15min)
- 012: CORS Debug Mode (30min)
- 015: SameSite Cookie (30min)
- 019: Hash Collision (5min)
- 020: Migration Safety (30min)
- 021: Confidence Validators (15min)
- 026: HSTS Preload (30min)
- 028: API Keys Env Vars (30min)
- 030: API Security Headers (15min)
- 022: CASCADE Behavior (30min)

---

## P1 - Critical (5 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 001 | PlantNet Circuit Breaker | 30min | 001-pending-p1-plantnet-circuit-breaker.md |
| 002 | Views Type Hints | 4h | 002-pending-p1-views-type-hints.md |
| 003 | Vite Port Mismatch | 15min | 003-pending-p1-vite-port-mismatch.md |
| 004 | Vote Race Condition | 2h | 004-pending-p1-vote-race-condition.md |
| 005 | API Key Rotation Verification | 1h | 005-pending-p1-api-key-rotation-verification.md |

**Total**: 8 hours

**Recommended Action**: Address in Week 1

---

## P2 - High Priority (8 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 006 | ESLint Errors | 3h | 006-pending-p2-eslint-errors.md |
| 007 | React Re-rendering | 4h | 007-pending-p2-react-rerendering.md |
| 008 | Database Indexes | 3h | 008-pending-p2-database-indexes.md |
| 009 | Dead Code Services | 2h | 009-pending-p2-dead-code-services.md |
| 010 | Documentation Mismatch | 2h | 010-pending-p2-documentation-mismatch.md |
| 011 | Error Boundaries | 3h | 011-pending-p2-error-boundaries.md |
| 012 | CORS Debug Mode | 30min | 012-pending-p2-cors-debug-mode.md |
| 013 | ThreadPool Overengineering | 1h | 013-pending-p2-threadpool-overengineering.md |

**Total**: 25 hours

**Recommended Action**: Address in Week 2-3

---

## P3 - Medium Priority (12 issues)

### Security & Compliance (6 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 014 | IP Spoofing Protection | 2h | 014-pending-p3-ip-spoofing-protection.md |
| 015 | SameSite Cookie | 30min | 015-pending-p3-samesite-cookie.md |
| 016 | PII Logging | 2h | 016-pending-p3-pii-logging.md |
| 017 | CSP Nonces | 1h | 017-pending-p3-csp-nonces.md |
| 023 | PII Encryption | 2h | 023-pending-p3-pii-encryption.md |
| 024 | Audit Trail | 3h | 024-pending-p3-audit-trail.md |

### Code Quality (4 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 018 | Constants Cleanup | 1h | 018-pending-p3-constants-cleanup.md |
| 019 | Hash Collision | 5min | 019-pending-p3-hash-collision.md |
| 020 | Migration Safety | 30min | 020-pending-p3-migration-safety.md |
| 021 | Confidence Validators | 15min | 021-pending-p3-confidence-validators.md |

### Architecture (2 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 022 | CASCADE Behavior | 30min | 022-pending-p3-cascade-behavior.md |
| 025 | Bundle Optimization | 4h | 025-pending-p3-bundle-optimization.md |

**Total**: 14 hours

**Recommended Action**: Select 5-7 issues for Week 3

---

## P4 - Low Priority (9 issues)

### Security Enhancements (3 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 026 | HSTS Preload | 30min | 026-pending-p4-hsts-preload.md |
| 027 | JWT Lifetime | 2h | 027-pending-p4-jwt-lifetime.md |
| 030 | API Security Headers | 15min | 030-pending-p4-api-security-headers.md |

### Developer Experience (3 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 028 | API Keys in Env Vars | 30min | 028-pending-p4-api-keys-env.md |
| 029 | Rate Limiting Consistency | 4h | 029-pending-p4-rate-limiting-consistency.md |
| 031 | API Documentation | 4h | 031-pending-p4-api-documentation.md |

### Code Quality (3 issues)

| ID | Issue | Effort | File |
|----|-------|--------|------|
| 032 | Component Tests | 16h | 032-pending-p4-component-tests.md |
| 033 | Unused StreamField Blocks | 2h | 033-pending-p4-unused-streamfield-blocks.md |
| 034 | Duplicate DOMPurify | 3h | 034-pending-p4-duplicate-dompurify.md |

**Total**: 23 hours

**Recommended Action**: Defer or implement as stretch goals

---

## Todo File Structure

Each todo file follows this structure:

```markdown
---
status: pending | in_progress | completed | blocked
priority: p1 | p2 | p3 | p4
issue_id: "001"
tags: [security, performance, etc.]
dependencies: [issue_ids]
---

# Issue Title

**CVSS**: X.X (if security issue)

## Problem
Brief description of the issue

## Findings
Agent-attributed findings with line numbers and specifics

## Proposed Solutions
### Option 1: Recommended Solution (if applicable)
- Pros/Cons
- Effort estimate
- Risk assessment

### Option 2: Alternative
...

## Recommended Action
Clear next steps with code examples

## Technical Details
File paths, line numbers, configuration examples

## Resources
Links to documentation, OWASP, etc.

## Acceptance Criteria
- [ ] Checklist of completion criteria

## Work Log
- Timestamps of major updates

## Notes
Priority rationale, related issues, trade-offs
```

---

## How to Use This Directory

### 1. Triage Workflow

```bash
# Find all P1 (critical) issues
grep -l "priority: p1" todos/*.md

# Find all security issues
grep -l "tags:.*security" todos/*.md

# Find quick wins (<1 hour)
grep -B2 "Effort.*min" todos/*.md
```

### 2. Update Status

Edit the YAML frontmatter when starting work:

```yaml
---
status: in_progress  # Change from pending
priority: p1
issue_id: "001"
tags: [performance, api]
dependencies: []
assigned_to: "developer-name"  # Add this field
started_at: "2025-10-26"  # Add this field
---
```

### 3. Mark Complete

When done:

```yaml
---
status: completed
priority: p1
issue_id: "001"
tags: [performance, api]
dependencies: []
assigned_to: "developer-name"
completed_at: "2025-10-26"
---
```

Add work log entry:

```markdown
## Work Log
- 2025-10-25: Issue identified by performance-oracle agent
- 2025-10-26: @developer-name implemented circuit breaker
- 2025-10-26: Tested and verified, marked complete
```

### 4. Track Dependencies

Some issues depend on others:

```yaml
---
status: blocked
priority: p2
issue_id: "007"
tags: [performance, frontend]
dependencies: ["025"]  # Blocked by bundle optimization
---
```

### 5. Generate Reports

```bash
# Count by status
grep "^status:" todos/*.md | sort | uniq -c

# Count by priority
grep "^priority:" todos/*.md | sort | uniq -c

# List in-progress tasks
grep -l "status: in_progress" todos/*.md
```

---

## Recommended Workflow

### Week 1: P1 Issues (8 hours)
1. Review all 5 P1 todos
2. Assign to developers based on expertise
3. Daily standup to track progress
4. Mark complete as finished

### Week 2: P2 Issues (Select 5-7, ~15 hours)
1. Triage P2 todos
2. Select highest impact issues
3. Assign and track
4. Defer remaining P2 to later sprints

### Week 3: P3 Issues (Select subset, ~10 hours)
1. Review P3 todos
2. Pick security/compliance issues
3. Implement quick wins first
4. Defer low-value items

### Week 4+: P4 Issues (Optional, ~20 hours)
1. Focus on developer experience (API docs, tests)
2. Skip low-value polish items
3. Revisit based on team capacity

---

## Related Documentation

- **COMPREHENSIVE_AUDIT_SUMMARY.md** - Full audit report with methodology, metrics, action plan
- **BEST_PRACTICES_AUDIT_2025.md** - Industry best practices research
- **backend/docs/quick-wins/** - Previous quick win implementations
- **KEY_ROTATION_INSTRUCTIONS.md** - Security incident response (relates to issue #005)

---

## Audit Metadata

**Command**: `/compounding-engineering:review audit codebase and report back to me`
**Date**: October 25, 2025
**Agents Used**: 12 specialized review agents
**Analysis Scope**: Backend (Django/Wagtail), Frontend (React), Mobile (Flutter)
**Total Findings**: 34 issues
**Estimated Total Effort**: 70 hours
**Critical Path (P1)**: 8 hours
**Quick Wins**: 10 issues, 3 hours

---

## Quick Commands

```bash
# Navigate to todos
cd /Users/williamtower/projects/plant_id_community/todos

# View a specific todo
cat 001-pending-p1-plantnet-circuit-breaker.md

# Find all security issues
grep -l "security" *.md

# Count pending issues
grep "^status: pending" *.md | wc -l

# Generate summary
echo "P1: $(grep -l 'priority: p1' *.md | wc -l)"
echo "P2: $(grep -l 'priority: p2' *.md | wc -l)"
echo "P3: $(grep -l 'priority: p3' *.md | wc -l)"
echo "P4: $(grep -l 'priority: p4' *.md | wc -l)"
```
