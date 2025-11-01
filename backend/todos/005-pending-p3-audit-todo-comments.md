---
status: pending
priority: p3
issue_id: "005"
tags: [code-review, technical-debt, maintenance, audit]
dependencies: []
---

# Audit and Resolve TODO/FIXME Comments

## Problem Statement
The codebase contains 65 files with technical debt markers (TODO, FIXME, HACK, XXX, BUG), indicating deferred work items that are not being tracked in the todo system or issue tracker. This creates invisible technical debt that loses context over time.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- **Total files affected**: 65 (backend only)
- **Frontend**: 4 files (relatively clean)
- **Pattern**: TODO comments scattered across production code

**Sample affected files**:
- `backend/apps/users/authentication.py`
- `backend/apps/core/constants.py`
- `backend/apps/plant_identification/services/plantnet_service.py`
- `backend/apps/plant_identification/services/combined_identification_service.py`
- `backend/apps/blog/signals.py`
- `backend/apps/blog/models.py`
- `backend/plant_community_backend/settings.py`
- `backend/plant_community_backend/urls.py`

**Note**: Documentation files (`.md`) containing TODOs are acceptable for planning purposes.

**Impact of untracked TODOs**:
1. Lost context over time (who, why, when)
2. Deferred security/performance fixes
3. Duplicate work (unclear what's been attempted)
4. Invisible technical debt
5. No prioritization or tracking

## Proposed Solutions

### Option 1: Comprehensive Audit and Conversion (Recommended)
**Phase 1 - Extract and Categorize** (2 hours):
```bash
# Extract all TODO comments with context
grep -rn "TODO\|FIXME\|HACK\|XXX\|BUG" backend/apps --include="*.py" > todo_audit.txt

# Analyze by category:
# - Security issues → P1 todos
# - Performance optimizations → P2 todos
# - Code cleanup → P3 todos
# - Future enhancements → Backlog/GitHub issues
```

**Phase 2 - Convert to Tracked Items** (3 hours):
1. Create todo files for critical items (P1/P2)
2. Create GitHub issues for long-term items
3. Remove completed/obsolete TODOs
4. Update remaining with ticket references

**Phase 3 - Establish Policy** (30 minutes):
```python
# Add to .pre-commit-config.yaml or CI
# Prevent new TODOs without ticket references
- repo: https://github.com/pre-commit/pygrep-hooks
  hooks:
    - id: python-check-todo-has-ticket
```

**Pros**:
- Complete visibility into technical debt
- Prioritized work items
- Context preserved
- Prevents future untracked TODOs

**Cons**:
- Significant upfront time investment
- Requires discipline to maintain

**Effort**: Medium (5-6 hours total)
**Risk**: Low

### Option 2: Incremental Cleanup
Only address TODOs as they're encountered during feature work.

**Pros**:
- No dedicated time needed
- Natural prioritization

**Cons**:
- Technical debt persists
- Context continues to degrade
- No systematic improvement

**Effort**: None (ongoing)
**Risk**: Medium (debt accumulation)

## Recommended Action
**Option 1** - Comprehensive audit with phased approach:
1. Week 1: Extract and categorize all TODOs
2. Week 2: Convert P1/P2 items to tracked todos
3. Week 3: Create GitHub issues for backlog items
4. Week 4: Establish pre-commit policy

This achieves systematic debt reduction while maintaining momentum.

## Technical Details
- **Affected Files**: 65 Python files across backend
  - `apps/users/`: 3 files
  - `apps/plant_identification/`: 8 files
  - `apps/blog/`: 5 files
  - `apps/core/`: 4 files
  - `apps/forum/`: 6 files
  - `plant_community_backend/`: 2 files
  - `docs/`: 37 files (documentation planning - acceptable)

- **TODO Categories to Look For**:
  - `TODO:` - General deferred work
  - `FIXME:` - Known bugs to fix
  - `HACK:` - Temporary workarounds
  - `XXX:` - Warning/attention needed
  - `BUG:` - Known issues

- **Exclude Patterns**:
  - Documentation files (planning TODOs are OK)
  - Test files (test TODOs are OK)
  - Migration files (historical context)

## Resources
- Code review audit: October 31, 2025
- Todo file format: `backend/todos/README.md`
- GitHub issue templates: `backend/github-issues/README.md`
- Pre-commit hooks: `PRE_COMMIT_SETUP.md`

## Acceptance Criteria
- [ ] Extract all TODO comments to `todo_audit.txt`
- [ ] Categorize by priority (P1/P2/P3/Backlog)
- [ ] Create todo files for P1/P2 items (estimated 10-15 todos)
- [ ] Create GitHub issues for backlog items
- [ ] Remove completed/obsolete TODOs from code
- [ ] Update remaining TODOs with ticket references
- [ ] Document policy in `backend/docs/development/`
- [ ] Optional: Add pre-commit hook to enforce ticket references

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered 65 files with TODO markers during codebase audit
- Identified pattern: untracked technical debt
- Analyzed distribution across apps
- Categorized as P3 maintenance issue

**Learnings:**
- Most TODOs in documentation (37 files) are acceptable planning notes
- Production code TODOs (28 files) should be tracked
- No critical security TODOs found (good sign)
- Need systematic approach to prevent accumulation

**Sample TODOs found**:
- Performance optimizations (combined_identification_service.py)
- Code cleanup (authentication.py)
- Future enhancements (blog/models.py)
- Wagtail signal fixes (blog/signals.py)

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P3 (maintenance, not critical)
Category: Technical Debt - Code Maintenance
Estimated todos to create: 10-15 (based on P1/P2 categorization)
