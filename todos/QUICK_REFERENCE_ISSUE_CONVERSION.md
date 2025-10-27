# Quick Reference: Todo to GitHub Issue Conversion

> Fast conversion guide for your 24 code audit todos

**Created**: October 27, 2025
**Project**: Plant ID Community (Django + React + Flutter)

---

## Quick Commands

### Convert All Todos to GitHub Issues

```bash
# Navigate to todos directory
cd /Users/williamtower/projects/plant_id_community/todos

# Bulk create issues with gh CLI (requires GitHub CLI installed)
for file in *-pending-*.md; do
  # Extract priority from filename (001-pending-p1-*.md -> p1)
  priority=$(echo $file | grep -oP '(?<=pending-p)\d+')

  # Extract title from first markdown heading
  title=$(grep -m 1 '^# ' $file | sed 's/^# //')

  # Create issue with labels
  gh issue create \
    --title "$title" \
    --body-file "$file" \
    --label "priority:p$priority" \
    --milestone "Code Audit Remediation - October 2025"
done
```

### Create Milestone First

```bash
gh milestone create "Code Audit Remediation - October 2025" \
  --description "Comprehensive codebase audit findings from October 25, 2025" \
  --due-date "2025-11-30"
```

### Create Project Board

```bash
gh project create \
  --title "Code Audit Remediation" \
  --owner @me

# Link all issues to project
gh project item-add <project-number> --owner @me --url https://github.com/USER/REPO/issues/101
```

---

## Priority Classification

### Your Current Todos

**P1 (Critical)** - 5 issues - **Fix within 48 hours**:
- 001: Add Circuit Breaker to PlantNet Service
- 002: Add Type Hints to Views Layer
- 003: Fix Vite Port Mismatch (5174 vs 5173)
- 004: Fix Vote Race Condition
- 005: Verify API Key Rotation Completed

**P2 (High)** - 8 issues - **Fix within 1 week**:
- 006: Fix ESLint Errors (60+ warnings)
- 007: Fix React Re-rendering Issues
- 008: Add Missing Database Indexes
- 009: Remove Dead Code in Services
- 010: Fix Documentation Mismatch
- 011: Add Error Boundaries (React)
- 012: Fix CORS Debug Mode Leakage
- 013: Simplify ThreadPool Executor

**P3 (Medium)** - 11 issues - **Fix within 2-4 weeks**:
- 014: Add IP Spoofing Protection
- 015: Set SameSite Cookie Attribute
- 016: Remove PII from Logs
- 017: Add CSP Nonces
- 018: Clean Up Constants Files
- 019: Fix Hash Collision Risk
- 020: Add Migration Safety Checks
- 021-024: Compliance and audit improvements

---

## Label Mapping

### Platform Labels

```markdown
# Backend Issues (Django)
001, 002, 004, 005, 008, 009, 012, 013, 014, 016, 018, 019, 020, 024
→ `backend:django`

# Frontend Issues (React)
003, 006, 007, 011, 015, 017
→ `frontend:react`

# Cross-Platform Issues
004 (voting), 012 (CORS)
→ `backend:django`, `frontend:react`
```

### Type Labels

```markdown
# Security Issues
005 (API key rotation), 014 (IP spoofing), 015 (cookies), 016 (PII), 017 (CSP), 024 (audit)
→ `type:security`

# Performance Issues
001 (circuit breaker), 008 (indexes), 009 (dead code), 013 (threadpool)
→ `type:performance`

# Code Quality Issues
002 (type hints), 006 (eslint), 010 (docs), 018 (constants), 019 (hash)
→ `type:refactor`

# Bug Fixes
003 (port), 004 (race condition), 007 (re-rendering), 011 (error boundaries), 012 (CORS)
→ `type:bug`

# Technical Debt
009 (dead code), 010 (docs), 013 (overengineering), 018 (constants), 020 (migrations)
→ `type:technical-debt`
```

---

## Issue Templates by Type

### Quick Template Selector

| Todo | Priority | Template to Use |
|------|----------|----------------|
| 001 | P1 | Django Performance Issue Template |
| 002 | P1 | Type Hints Technical Debt Template |
| 003 | P1 | React Configuration Bug Template |
| 004 | P1 | Django Concurrency Bug Template |
| 005 | P1 | Security Vulnerability Template |
| 006-013 | P2 | Standard Bug/Enhancement Template |
| 014-024 | P3 | Security/Compliance Template |

---

## Sample Issue Creation

### Example 1: Todo 001 → GitHub Issue

**File**: `001-pending-p1-plantnet-circuit-breaker.md`

**Command**:
```bash
gh issue create \
  --title "Add Circuit Breaker to PlantNet Service" \
  --body-file "001-pending-p1-plantnet-circuit-breaker.md" \
  --label "priority:critical,backend:django,type:performance,needs-fix" \
  --milestone "Code Audit Remediation - October 2025" \
  --assignee "@me"
```

**Expected Result**:
```
Creating issue in Xertox1234/plant_id_community

https://github.com/Xertox1234/plant_id_community/issues/101
```

### Example 2: Todo 002 → GitHub Issue

**File**: `002-pending-p1-views-type-hints.md`

**Command**:
```bash
gh issue create \
  --title "Add Type Hints to Views Layer (28 functions)" \
  --body-file "002-pending-p1-views-type-hints.md" \
  --label "priority:critical,backend:django,type:refactor,code-quality" \
  --milestone "Code Audit Remediation - October 2025"
```

---

## Batch Processing Script

Save as `convert_todos_to_issues.sh`:

```bash
#!/bin/bash

# Convert todos to GitHub issues
# Usage: ./convert_todos_to_issues.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Milestone name
MILESTONE="Code Audit Remediation - October 2025"

# Create milestone if it doesn't exist
echo -e "${YELLOW}Creating milestone...${NC}"
gh milestone create "$MILESTONE" \
  --description "Comprehensive codebase audit findings from October 25, 2025" \
  --due-date "2025-11-30" 2>/dev/null || echo "Milestone already exists"

# Label mapping based on priority and filename
get_labels() {
  local filename=$1
  local priority=$(echo $filename | grep -oP '(?<=pending-p)\d+')
  local labels="priority:p$priority"

  # Add type-specific labels based on keywords in filename
  if [[ $filename == *"circuit-breaker"* ]] || [[ $filename == *"performance"* ]]; then
    labels="$labels,type:performance"
  fi

  if [[ $filename == *"type-hints"* ]] || [[ $filename == *"code-quality"* ]]; then
    labels="$labels,type:refactor,code-quality"
  fi

  if [[ $filename == *"security"* ]] || [[ $filename == *"api-key"* ]] || [[ $filename == *"spoofing"* ]]; then
    labels="$labels,type:security"
  fi

  # Add platform labels
  if [[ $filename == *"react"* ]] || [[ $filename == *"eslint"* ]] || [[ $filename == *"vite"* ]]; then
    labels="$labels,frontend:react"
  else
    labels="$labels,backend:django"
  fi

  echo "$labels,needs-fix"
}

# Counter
count=0
success=0
failed=0

# Process each pending todo file
for file in *-pending-*.md; do
  if [[ ! -f "$file" ]]; then
    continue
  fi

  count=$((count + 1))

  # Extract title from first markdown heading
  title=$(grep -m 1 '^# ' "$file" | sed 's/^# //')

  if [[ -z "$title" ]]; then
    echo -e "${RED}[SKIP]${NC} $file - No title found"
    failed=$((failed + 1))
    continue
  fi

  # Get labels
  labels=$(get_labels "$file")

  echo -e "${YELLOW}[CREATE]${NC} $title"

  # Create issue
  if gh issue create \
    --title "$title" \
    --body-file "$file" \
    --label "$labels" \
    --milestone "$MILESTONE" 2>&1; then
    echo -e "${GREEN}[SUCCESS]${NC} Created issue: $title"
    success=$((success + 1))
  else
    echo -e "${RED}[FAILED]${NC} $file"
    failed=$((failed + 1))
  fi

  echo ""
done

# Summary
echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}Summary:${NC}"
echo -e "  Total todos: $count"
echo -e "  ${GREEN}Created: $success${NC}"
echo -e "  ${RED}Failed: $failed${NC}"
echo -e "${GREEN}===========================================${NC}"

# Create project board
echo -e "\n${YELLOW}Creating project board...${NC}"
gh project create \
  --title "Code Audit Remediation" \
  --owner @me || echo "Project already exists"

echo -e "\n${GREEN}Done! View issues at:${NC}"
echo "https://github.com/Xertox1234/plant_id_community/issues"
```

**Usage**:
```bash
cd /Users/williamtower/projects/plant_id_community/todos
chmod +x convert_todos_to_issues.sh
./convert_todos_to_issues.sh
```

---

## Manual Conversion Checklist

If you prefer manual creation, follow this checklist for each todo:

### For Each Todo File:

1. **Read todo file**:
   ```bash
   cat 001-pending-p1-plantnet-circuit-breaker.md
   ```

2. **Identify priority** (from filename):
   - `p1` → `priority:critical`
   - `p2` → `priority:high`
   - `p3` → `priority:medium`

3. **Identify platform** (from content):
   - Backend: `backend:django`
   - Frontend: `frontend:react`
   - Mobile: `mobile:flutter`

4. **Identify type**:
   - Security: `type:security`
   - Performance: `type:performance`
   - Bug: `type:bug`
   - Refactor: `type:refactor`

5. **Create GitHub issue**:
   ```bash
   gh issue create \
     --title "..." \
     --body-file "..." \
     --label "..." \
     --milestone "..." \
     --assignee "@me"
   ```

6. **Mark todo as converted**:
   ```bash
   mv 001-pending-p1-plantnet-circuit-breaker.md \
      001-converted-p1-plantnet-circuit-breaker.md
   ```

---

## Label Creation

First, create all labels in your repository:

```bash
# Priority labels
gh label create "priority:critical" --color "d73a4a" --description "Critical priority - fix within 48 hours"
gh label create "priority:high" --color "ff9800" --description "High priority - fix within 1 week"
gh label create "priority:medium" --color "ffeb3b" --description "Medium priority - fix within 2-4 weeks"
gh label create "priority:low" --color "2196f3" --description "Low priority - fix when time allows"

# Platform labels
gh label create "backend:django" --color "0e8a16" --description "Django backend issues"
gh label create "frontend:react" --color "61dafb" --description "React web application"
gh label create "mobile:flutter" --color "02569b" --description "Flutter mobile app"

# Type labels
gh label create "type:security" --color "d73a4a" --description "Security vulnerability or concern"
gh label create "type:performance" --color "ff9800" --description "Performance optimization"
gh label create "type:bug" --color "d73a4a" --description "Something isn't working"
gh label create "type:refactor" --color "0052cc" --description "Code refactoring"
gh label create "type:technical-debt" --color "fbca04" --description "Technical debt cleanup"

# Status labels
gh label create "needs-fix" --color "d73a4a" --description "Needs to be fixed"
gh label create "needs-review" --color "fbca04" --description "Needs code review"
gh label create "needs-testing" --color "fbca04" --description "Needs testing"
```

---

## Post-Conversion Checklist

After converting todos to issues:

- [ ] All 24 todos converted to GitHub issues
- [ ] Issues added to milestone "Code Audit Remediation - October 2025"
- [ ] Project board created with Kanban columns
- [ ] P1 issues (5) assigned to developers
- [ ] Labels applied consistently
- [ ] Related issues linked (dependencies)
- [ ] Original todo files renamed or archived

---

## Verification

```bash
# Count created issues
gh issue list --milestone "Code Audit Remediation - October 2025" | wc -l
# Expected: 24

# View P1 issues
gh issue list --label "priority:critical"
# Expected: 5 issues

# View backend issues
gh issue list --label "backend:django"
# Expected: ~15 issues

# View security issues
gh issue list --label "type:security"
# Expected: ~6 issues
```

---

## Next Steps

1. **Convert todos to issues** (use script or manual):
   ```bash
   cd /Users/williamtower/projects/plant_id_community/todos
   ./convert_todos_to_issues.sh
   ```

2. **Triage P1 issues** (5 critical issues):
   - Assign to developers
   - Set target fix date (48 hours)
   - Create branches for each issue

3. **Create project board**:
   - Columns: Backlog, In Progress, In Review, Done
   - Add all issues to board
   - Move P1 issues to "In Progress"

4. **Start work on P1**:
   ```bash
   git checkout -b fix/001-plantnet-circuit-breaker
   # Implement fix
   # Create PR with "Fixes #101" in description
   ```

5. **Track progress**:
   - Daily standup: Review board
   - Weekly: Update milestone progress
   - Biweekly: Triage new P2/P3 issues

---

## Resources

- **Full Guide**: `/Users/williamtower/projects/plant_id_community/todos/GITHUB_ISSUE_CREATION_GUIDE.md`
- **GitHub CLI Docs**: https://cli.github.com/manual/
- **Project Board**: https://github.com/USER/REPO/projects
- **Milestone**: https://github.com/USER/REPO/milestones
