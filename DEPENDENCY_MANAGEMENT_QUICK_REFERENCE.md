# Dependency Management Quick Reference

**Version**: 1.0 | **Last Updated**: November 2, 2025

---

## Priority Matrix (5-Tier System)

| Priority | Type | Example | Merge Strategy | Verification |
|----------|------|---------|----------------|--------------|
| **P1** | GitHub Actions | actions/checkout v4→v5 | Individual | All workflows pass |
| **P2** | Core Backend | Django, DRF, Wagtail | Group minor/patch | Full test suite |
| **P3** | Dev Tools | pytest, eslint, ruff | Batch 10-20 | Smoke test |
| **P4** | Production Libs | axios, vite, openapi | Individual major | Integration tests |
| **P5** | Mobile (Dev) | Flutter packages | Safe to merge | Mobile tests |

---

## Quick Commands

### Check PR Priority
```bash
# GitHub Actions (P1)
grep "actions/" .github/workflows/*.yml

# Backend dependencies (P2)
grep "django\|wagtail\|drf" backend/requirements.txt

# Frontend dependencies (P4)
grep "react\|vite\|axios" web/package.json
```

### Merge Individual PR
```bash
gh pr merge <N> --squash --body "✅ Approved: <Package> <Old>→<New>

Rationale: <Why merging>
Verification: <What was tested>
Breaking changes: <None or list>"
```

### Batch Merge PRs
```bash
for pr_num in 101 102 103 104 105; do
  gh pr merge $pr_num --squash --body "✅ Approved: Dev dependency update

Category: Development tools
Risk: Minimal (no production impact)
Verification: CI passing"
done
```

### Handle Merge Conflicts
```bash
# Detect conflicts
gh pr view <N> --json mergeable

# Request rebase (ALWAYS use this, never manual)
gh pr comment <N> --body "@dependabot rebase"

# Wait 1-2 minutes, then verify
gh pr checks <N>
```

### Verify After Merge
```bash
# Backend tests
cd backend && python manage.py test --keepdb -v 2

# Frontend tests
cd web && npm run test

# E2E tests
cd web && npm run test:e2e
```

---

## Decision Trees

### Should I Batch Merge?

**YES** ✅ (Batch safe):
- All dev dependencies
- All minor/patch versions (1.2.3→1.2.4)
- Same family (django-*, @types/*)
- All CI checks passing

**NO** ❌ (Merge individually):
- Major versions (1.x→2.x)
- GitHub Actions (P1)
- Core backend (Django, React)
- Breaking changes mentioned

### Is This a Regression?

**Regression** 🔴 (Rollback immediately):
- Test passed BEFORE update
- Error mentions updated package
- Isolated to updated code
- CI was green, now red

**Pre-Existing** 🟡 (Document):
- Test failed BEFORE update
- Error generic/unrelated
- Widespread across codebase
- CI was red before and after

---

## Common Scenarios

### Scenario: GitHub Actions Update
```bash
# Always P1, always individual
gh pr view <N> --json body  # Review changelog
gh pr checks <N>  # Verify ALL workflows
gh pr merge <N> --squash --body "✅ GitHub Actions update..."
```

### Scenario: Django Ecosystem Update
```bash
# P2, can group if all minor/patch
cd backend && python manage.py test --keepdb -v 2
# If 100% pass or pre-existing failures only: MERGE
# If new failures: ROLLBACK
```

### Scenario: 4 PRs with Merge Conflicts
```bash
# Merge first PR
gh pr merge 101 --squash

# Others now show conflicts
for pr in 102 103 104; do
  gh pr comment $pr --body "@dependabot rebase"
done

# Wait 2-3 minutes for all rebases
# Then merge sequentially
```

---

## Test Failure Response

### New Failure (Regression)
```bash
# 1. Rollback immediately
gh pr revert <N>

# 2. Investigate compatibility
# 3. Fix issues
# 4. Create new PR with fix
```

### Pre-Existing Failure
```bash
# 1. Create TODO file
cat > backend/todos/0XX-pending-pN-fix-ISSUE.md <<EOF
---
status: pending
priority: p2
issue_id: "0XX"
tags: [testing, category]
estimated_effort: "X-Y hours"
---

# [Title]

## Problem Statement
[Error examples]

## Root Cause Analysis
[Analysis]

## Proposed Solutions
### Option 1 (Recommended)
**Pros**: [3-5 items]
**Cons**: [1-3 items]
**Effort**: X hours

### Option 2
[Same structure]

### Option 3
[Same structure]

## Implementation Plan
[Phases with time estimates]

## Acceptance Criteria
- [ ] [8-15 testable criteria]

## Work Log
[Discovery details]
EOF

# 2. Continue with dependency merge
# (failure not caused by update)
```

---

## Cheat Sheet

### ✅ DO
- Merge GitHub Actions individually (P1)
- Use `@dependabot rebase` for conflicts
- Run full test suites after merging
- Document pre-existing failures (11KB+)
- Group minor/patch dev dependencies
- Check breaking changes in changelogs

### ❌ DON'T
- Batch GitHub Actions updates
- Manually resolve Dependabot conflicts
- Skip test verification
- Ignore test failures without analysis
- Mix major versions in batch merges
- Merge without checking CI status

---

## Templates

### Individual Merge
```
✅ Approved: <Package> <Old>→<New> (<Category>)

Rationale: <Security/features/compatibility>
Verification: <Tests run and results>
Breaking changes: <None or list>
```

### Batch Merge
```
✅ Approved: Dev dependency update

Category: Development tools
Risk: Minimal (no production impact)
Verification: CI passing
```

### Rebase Request
```
@dependabot rebase
```

### TODO File Name
```
backend/todos/0XX-pending-pN-fix-DESCRIPTION.md
```

---

## Key Metrics Targets

- **P1 Merge Time**: < 5 min (individual review + merge)
- **P2 Merge Time**: < 15 min (test suite + merge)
- **P3 Batch Time**: < 10 min (10-20 PRs)
- **Rebase Time**: 1-2 min (Dependabot automation)
- **Test Suite**: Backend ~45s, Frontend ~60s
- **Regression Rate**: 0% (all failures pre-existing)
- **Documentation**: 11KB+ for complex failures

---

## Quick Verification

### Before Merging
```bash
- [ ] Priority level identified (P1-P5)
- [ ] Breaking changes checked
- [ ] CI status verified (all green)
- [ ] Merge strategy chosen (individual/group/batch)
```

### After Merging
```bash
- [ ] Tests run (backend + frontend)
- [ ] Failures analyzed (regression vs pre-existing)
- [ ] Pre-existing failures documented
- [ ] No regressions introduced
```

---

## Reference Documents

- **Full Patterns**: `/backend/docs/development/DEPENDENCY_MANAGEMENT_PATTERNS_CODIFIED.md` (25KB)
- **Code Review Agent**: `/.claude/agents/code-review-specialist.md` (Step 4.5)
- **Summary**: `/PATTERNS_CODIFICATION_SUMMARY.md` (11KB)
- **This Guide**: `/DEPENDENCY_MANAGEMENT_QUICK_REFERENCE.md` (You are here)

---

## Emergency Procedures

### Regression Detected
```bash
# 1. Immediate rollback
gh pr revert <PR_NUMBER>

# 2. Notify team
echo "Regression in PR <N>: <Package> <Old>→<New>"

# 3. Create investigation issue
gh issue create --title "Investigate regression: <Package> update"

# 4. Document failure in issue
# 5. Fix compatibility
# 6. Create new PR with fix + tests
```

### Multiple Conflicts
```bash
# 1. Sort by priority (P1 first)
# 2. Merge highest priority
# 3. Request rebase for others: @dependabot rebase
# 4. Wait for all rebases (parallel)
# 5. Merge next highest priority
# 6. Repeat until all merged
```

### Test Suite Timeout
```bash
# Backend: Use --keepdb for faster reruns
python manage.py test --keepdb -v 2

# Frontend: Use --bail to stop on first failure
npm run test -- --bail

# E2E: Run subset first
npm run test:e2e -- <specific-test>.spec.js
```

---

**Document Version**: 1.0
**Last Updated**: November 2, 2025
**Print-Friendly**: Yes (designed for quick desk reference)
