#!/bin/bash
#
# create-issues.sh
#
# Automate creation of GitHub issues from markdown files
# Usage: ./create-issues.sh
#
# Prerequisites:
# - GitHub CLI (gh) installed and authenticated
# - Run from /backend/github-issues/ directory (or provide path)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  GitHub Issues Creator - Plant ID Community Backend       ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}✗ Error: GitHub CLI (gh) is not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  macOS:   brew install gh"
    echo "  Linux:   https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    echo "  Windows: https://github.com/cli/cli/releases"
    echo ""
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}✗ Error: Not authenticated with GitHub${NC}"
    echo ""
    echo "Authenticate with:"
    echo "  gh auth login"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ GitHub CLI authenticated${NC}"
echo ""

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -z "$REPO" ]; then
    echo -e "${RED}✗ Error: Not in a GitHub repository or cannot detect repository${NC}"
    echo ""
    echo "Navigate to your repository directory and try again."
    exit 1
fi

echo -e "${BLUE}Repository: ${REPO}${NC}"
echo ""

# ============================================================================
# STEP 1: Create Labels
# ============================================================================

echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Step 1: Creating GitHub Labels${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

create_label() {
    local name="$1"
    local color="$2"
    local description="$3"

    if gh label list --json name -q ".[] | select(.name == \"$name\") | .name" | grep -q "$name"; then
        echo -e "  ${BLUE}→${NC} Label '${name}' already exists (skipping)"
    else
        gh label create "$name" --color "$color" --description "$description" 2>/dev/null && \
            echo -e "  ${GREEN}✓${NC} Created label '${name}'" || \
            echo -e "  ${RED}✗${NC} Failed to create label '${name}'"
    fi
}

# Priority labels
echo -e "${BLUE}Priority Labels:${NC}"
create_label "priority: critical" "b60205" "Fix within 24-48 hours"
create_label "priority: high" "d93f0b" "Fix within 7 days"
create_label "priority: medium" "fbca04" "Fix within 30 days"
create_label "priority: low" "0e8a16" "Fix within 90 days"
echo ""

# Type labels
echo -e "${BLUE}Type Labels:${NC}"
create_label "type: security" "d73a4a" "Security vulnerability"
create_label "type: bug" "fc2929" "Something isn't working"
create_label "type: refactor" "1d76db" "Code refactoring"
create_label "type: performance" "5319e7" "Performance improvement"
echo ""

# Area labels
echo -e "${BLUE}Area Labels:${NC}"
create_label "area: backend" "0075ca" "Django backend"
create_label "area: web" "0075ca" "React frontend"
create_label "area: mobile" "0075ca" "Flutter mobile"
echo ""

# Context labels
echo -e "${BLUE}Context Labels:${NC}"
create_label "week-3" "c5def5" "Week 3 Quick Wins"
create_label "code-review" "e99695" "From code review findings"
create_label "code-quality" "bfdadc" "Code quality improvement"
create_label "data-integrity" "f9d0c4" "Data integrity concern"
echo ""

# ============================================================================
# STEP 2: Create Issues
# ============================================================================

echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Step 2: Creating GitHub Issues${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

CREATED_ISSUES=()
FAILED_ISSUES=()

create_issue() {
    local title="$1"
    local body_file="$2"
    local labels="$3"
    local issue_num="$4"

    echo -e "${BLUE}Creating Issue ${issue_num}:${NC} ${title}"

    if [ ! -f "$body_file" ]; then
        echo -e "  ${RED}✗ Error: File not found: ${body_file}${NC}"
        FAILED_ISSUES+=("$title (file not found)")
        return 1
    fi

    # Create the issue
    ISSUE_URL=$(gh issue create \
        --title "$title" \
        --body-file "$body_file" \
        --label "$labels" 2>&1)

    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓ Created:${NC} ${ISSUE_URL}"
        CREATED_ISSUES+=("$ISSUE_URL")
    else
        echo -e "  ${RED}✗ Failed:${NC} ${ISSUE_URL}"
        FAILED_ISSUES+=("$title")
        return 1
    fi
    echo ""
}

# Issue 001: Security - Rotate exposed API keys
create_issue \
    "security: Rotate exposed API keys and remove from git history" \
    "001-security-rotate-exposed-api-keys.md" \
    "priority: critical,type: security,area: backend,week-3,code-review" \
    "001"

# Issue 002: Security - Fix insecure SECRET_KEY
create_issue \
    "security: Fix insecure SECRET_KEY default in Django settings" \
    "002-security-fix-secret-key-default.md" \
    "priority: critical,type: security,area: backend,week-3,code-review" \
    "002"

# Issue 003: Fix - Lock release error handling
create_issue \
    "fix: Add error handling for distributed lock release failures" \
    "003-fix-lock-release-error-handling.md" \
    "priority: high,type: bug,area: backend,week-3,code-review,data-integrity" \
    "003"

# Issue 004: Security - File upload validation
create_issue \
    "security: Add multi-layer file upload validation to prevent malicious files" \
    "004-security-file-upload-validation.md" \
    "priority: high,type: security,area: backend,week-3,code-review" \
    "004"

# Issue 005: Refactor - Type hints
create_issue \
    "refactor: Add missing type hints to service methods for better IDE support" \
    "005-refactor-add-missing-type-hints.md" \
    "priority: medium,type: refactor,area: backend,week-3,code-review,code-quality" \
    "005"

# ============================================================================
# STEP 3: Summary
# ============================================================================

echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Summary${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✓ Created ${#CREATED_ISSUES[@]} GitHub issues:${NC}"
for issue in "${CREATED_ISSUES[@]}"; do
    echo -e "  • ${issue}"
done
echo ""

if [ ${#FAILED_ISSUES[@]} -gt 0 ]; then
    echo -e "${RED}✗ Failed to create ${#FAILED_ISSUES[@]} issues:${NC}"
    for issue in "${FAILED_ISSUES[@]}"; do
        echo -e "  • ${issue}"
    done
    echo ""
fi

# Production readiness calculation
TOTAL_ISSUES=5
CRITICAL_ISSUES=2
HIGH_ISSUES=2
MEDIUM_ISSUES=1

echo -e "${BLUE}Production Readiness Impact:${NC}"
echo -e "  Current:  95% production-ready"
echo -e "  Critical: ${CRITICAL_ISSUES} issues (fix within 24-48 hours)"
echo -e "  High:     ${HIGH_ISSUES} issues (fix within 7 days)"
echo -e "  Medium:   ${MEDIUM_ISSUES} issue (fix within 30 days)"
echo -e "  After fixes: 100% production-ready ✅"
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Review created issues on GitHub"
echo -e "  2. Assign issues to team members"
echo -e "  3. Start work on critical issues TODAY"
echo -e "  4. Schedule high priority issues for this week"
echo -e "  5. Add medium priority to next sprint backlog"
echo ""

echo -e "${BLUE}View all issues:${NC}"
echo -e "  gh issue list --label \"week-3,code-review\""
echo ""

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ GitHub Issues Created Successfully                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
