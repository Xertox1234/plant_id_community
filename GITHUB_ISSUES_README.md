# GitHub Issues Creation Guide

This guide explains how to create 34 GitHub issues from the code audit findings.

## Overview

**Total Issues:** 34
- 🔴 **P1 (Critical):** 5 issues - Fix within 48 hours
- 🟡 **P2 (High):** 8 issues - Fix within 1 week
- 🔵 **P3 (Medium):** 12 issues - Fix within 2-4 weeks
- ⚪ **P4 (Low):** 9 issues - Fix when possible

**Source:** Comprehensive code audit (October 25, 2025)
**Location:** `/todos/*.md` files (status: ready)

---

## Quick Start (3 Steps)

### Step 1: Create Labels (5 minutes)

```bash
# Preview what will be created
./create_github_labels.sh --dry-run

# Create labels
./create_github_labels.sh
```

**Labels Created:**
- Priority: `priority:critical`, `priority:high`, `priority:medium`, `priority:low`
- Type: `type:security`, `type:bug`, `type:performance`, `type:refactor`, `type:test`, `type:docs`
- Area: `area:backend`, `area:web`, `area:mobile`
- Special: `code-review`, `code-quality`, `data-integrity`

### Step 2: Preview Issues (5 minutes)

```bash
# Preview all 34 issues
./create_github_issues.sh --dry-run

# Preview only P1 (critical) issues
./create_github_issues.sh --priority p1 --dry-run

# Preview only P2 (high) issues
./create_github_issues.sh --priority p2 --dry-run
```

### Step 3: Create Issues (10 minutes)

```bash
# Create all 34 issues
./create_github_issues.sh

# OR create by priority
./create_github_issues.sh --priority p1  # Create P1 first
./create_github_issues.sh --priority p2  # Then P2
# etc.
```

---

## Detailed Usage

### Prerequisites

1. **GitHub CLI installed:**
   ```bash
   brew install gh  # macOS
   # OR: https://cli.github.com/
   ```

2. **Authenticated:**
   ```bash
   gh auth login
   gh auth status  # Verify
   ```

3. **In repository directory:**
   ```bash
   cd /Users/williamtower/projects/plant_id_community
   ```

### Script Options

#### `create_github_labels.sh`

Creates/updates GitHub labels for issue organization.

```bash
# Syntax
./create_github_labels.sh [--dry-run]

# Examples
./create_github_labels.sh --dry-run  # Preview
./create_github_labels.sh            # Create
```

#### `create_github_issues.sh`

Creates GitHub issues from todo files.

```bash
# Syntax
./create_github_issues.sh [--dry-run] [--priority p1|p2|p3|p4]

# Examples
./create_github_issues.sh                          # All 34 issues
./create_github_issues.sh --dry-run                # Preview all
./create_github_issues.sh --priority p1            # Only P1 (5 issues)
./create_github_issues.sh --priority p1 --dry-run  # Preview P1
```

---

## Issue Structure

Each issue follows this format:

```markdown
## Overview
[Priority emoji] [Priority level] - [Brief description]
Source, effort estimate, timeline

## Problem Statement
Current state, why it matters, location in code

## Proposed Solution
Detailed solution with code examples

## Technical Details
Affected files, dependencies, configuration

## Acceptance Criteria
- [ ] Checkboxes for each requirement

## References
Links to code, docs, related issues
```

### Issue Titles

Format: `[type]: [description]`

**Examples:**
- `security: Add circuit breaker to PlantNet service` (P1)
- `fix: Resolve vote race condition in identification endpoint` (P1)
- `refactor: Add missing type hints to view methods` (P2)
- `docs: Add comprehensive API documentation` (P4)

### Issue Labels

Each issue gets 3-5 labels:

**Priority + Type + Area + Special**
- Example P1: `priority:critical`, `type:bug`, `area:backend`, `code-review`
- Example P2: `priority:high`, `type:refactor`, `area:web`, `code-quality`
- Example P3: `priority:medium`, `type:security`, `area:backend`, `code-review`

---

## What Gets Created

### P1 - Critical (5 issues)

| # | Title | Effort | Labels |
|---|-------|--------|--------|
| 001 | fix: Add circuit breaker to PlantNet service | 2-4h | priority:critical, type:bug, area:backend |
| 002 | refactor: Add type hints to views layer | 4h | priority:critical, type:refactor, area:backend |
| 003 | fix: Vite port mismatch causing CORS failures | 15min | priority:critical, type:bug, area:web |
| 004 | fix: Vote race condition in identification results | 2h | priority:critical, type:bug, area:backend |
| 005 | security: Verify API key rotation after Oct 23 incident | 1h | priority:critical, type:security, area:backend |

### P2 - High Priority (8 issues)

| # | Title | Effort | Labels |
|---|-------|--------|--------|
| 006 | fix: ESLint errors in React components | 3h | priority:high, type:refactor, area:web |
| 007 | perf: Optimize React re-rendering in blog components | 4h | priority:high, type:performance, area:web |
| 008 | perf: Add missing database indexes | 3h | priority:high, type:performance, area:backend |
| 009 | refactor: Remove dead code from services layer | 2h | priority:high, type:refactor, area:backend |
| 010 | docs: Fix documentation mismatches | 2h | priority:high, type:docs |
| 011 | fix: Add error boundaries to React app | 3h | priority:high, type:bug, area:web |
| 012 | security: Remove CORS_ALLOW_ALL_ORIGINS in production | 30min | priority:high, type:security, area:backend |
| 013 | refactor: Review ThreadPoolExecutor singleton pattern | 1h | priority:high, type:refactor, area:backend |

### P3 - Medium Priority (12 issues)

| # | Title | Effort |
|---|-------|--------|
| 014-025 | Security, code quality, optimization issues | 15min - 4h each |

### P4 - Low Priority (9 issues)

| # | Title | Effort |
|---|-------|--------|
| 026-034 | Documentation, polish, nice-to-have improvements | 15min - 16h each |

**Full list:** See `COMPREHENSIVE_AUDIT_SUMMARY.md`

---

## After Creation

### 1. View Created Issues

```bash
# All code review issues
gh issue list --label code-review

# By priority
gh issue list --label priority:critical
gh issue list --label priority:high

# By area
gh issue list --label area:backend
gh issue list --label area:web
```

### 2. Create Milestone (Optional)

```bash
gh milestone create "Code Audit - October 2025" \
  --description "Remediate findings from October 2025 code audit" \
  --due-date "2025-11-30"

# Link issues to milestone
gh issue list --label code-review --json number --jq '.[].number' | \
  xargs -I {} gh issue edit {} --milestone "Code Audit - October 2025"
```

### 3. Assign Issues

```bash
# Assign P1 issues to developers
gh issue list --label priority:critical --json number,title --jq '.[] | "\(.number): \(.title)"'

# Assign individual issues
gh issue edit 1 --assignee username
```

### 4. Start Work

```bash
# View P1 issue details
gh issue view 1

# Work on an issue
gh issue comment 1 --body "Starting work on this"

# Close when done
gh issue close 1 --comment "Fixed in PR #123"
```

---

## Troubleshooting

### "gh: command not found"

**Solution:**
```bash
# macOS
brew install gh

# Linux
# See: https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Verify
gh --version
```

### "Not authenticated"

**Solution:**
```bash
gh auth login
# Follow prompts to authenticate

# Verify
gh auth status
```

### "Label already exists"

**Solution:** The script updates existing labels, so this is fine. If you want to start fresh:
```bash
gh label list | awk '{print $1}' | xargs -I {} gh label delete {} --yes
./create_github_labels.sh
```

### "Rate limit exceeded"

**Solution:** The script includes `sleep 1` between issues. If you hit limits:
```bash
# Check rate limit
gh api rate_limit

# Wait and retry
sleep 300  # 5 minutes
./create_github_issues.sh --priority p1  # Resume
```

### "Issue creation failed"

**Solution:** Check specific issue:
```bash
# Enable verbose output
gh issue create --title "test" --body "test" --label "priority:critical" --verbose
```

Common causes:
- Missing labels (run `./create_github_labels.sh` first)
- Invalid Markdown in issue body
- Network issues

---

## Verification

After creating issues, verify:

```bash
# Count issues created
echo "Total: $(gh issue list --label code-review --json number --jq '. | length')"
echo "P1: $(gh issue list --label priority:critical --json number --jq '. | length')"
echo "P2: $(gh issue list --label priority:high --json number --jq '. | length')"
echo "P3: $(gh issue list --label priority:medium --json number --jq '. | length')"
echo "P4: $(gh issue list --label priority:low --json number --jq '. | length')"

# Expected output:
# Total: 34
# P1: 5
# P2: 8
# P3: 12
# P4: 9
```

---

## File Structure

```
plant_id_community/
├── create_github_labels.sh      # Step 1: Create labels
├── create_github_issues.sh      # Step 2: Create issues
├── GITHUB_ISSUES_README.md      # This file
├── COMPREHENSIVE_AUDIT_SUMMARY.md  # Full audit report
└── todos/
    ├── 001-pending-p1-*.md      # P1 issues (5)
    ├── 006-pending-p2-*.md      # P2 issues (8)
    ├── 014-pending-p3-*.md      # P3 issues (12)
    └── 026-pending-p4-*.md      # P4 issues (9)
```

---

## Next Steps After Issue Creation

1. **Week 1: P1 Issues (8 hours)**
   - Assign to developers
   - Daily standup tracking
   - Target: 95% production readiness

2. **Week 2: P2 Issues (select 5-7, ~15 hours)**
   - Triage by impact
   - Implement highest value fixes
   - Defer rest to later sprints

3. **Week 3: P3 Issues (select subset, ~10 hours)**
   - Focus on security/compliance
   - Quick wins first
   - Defer low-value items

4. **Week 4+: P4 Issues (optional, ~20 hours)**
   - Developer experience improvements
   - Documentation
   - Polish

---

## Support

**Questions?** Check:
- `COMPREHENSIVE_AUDIT_SUMMARY.md` - Full audit details
- `todos/*.md` - Individual issue details
- GitHub CLI docs: https://cli.github.com/manual/

**Issues with scripts?** Check:
- Script permissions: `chmod +x *.sh`
- Working directory: `pwd` should be project root
- GitHub auth: `gh auth status`
