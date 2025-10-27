#!/bin/bash

###############################################################################
# GitHub Issue Creation Script
#
# Creates 34 GitHub issues from code audit findings
# Source: /todos/*.md files (status: ready)
#
# Usage: ./create_github_issues.sh [--dry-run] [--priority p1|p2|p3|p4]
#
# Options:
#   --dry-run    Show what would be created without creating issues
#   --priority   Only create issues for specific priority (p1, p2, p3, p4)
#
# Examples:
#   ./create_github_issues.sh                    # Create all 34 issues
#   ./create_github_issues.sh --dry-run          # Preview all issues
#   ./create_github_issues.sh --priority p1      # Create only P1 issues
#   ./create_github_issues.sh --priority p1 --dry-run  # Preview P1 issues
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TODOS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/todos"
DRY_RUN=false
PRIORITY_FILTER=""
CREATED_COUNT=0
SKIPPED_COUNT=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --priority)
            PRIORITY_FILTER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--priority p1|p2|p3|p4]"
            exit 1
            ;;
    esac
done

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install with: brew install gh"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Function to extract YAML frontmatter field
get_yaml_field() {
    local file=$1
    local field=$2
    grep "^${field}:" "$file" | sed "s/^${field}: //" | tr -d '"' | tr -d "'"
}

# Function to get issue type prefix based on tags and priority
get_issue_prefix() {
    local tags=$1
    local priority=$2

    if [[ $tags == *"security"* ]]; then
        echo "security"
    elif [[ $tags == *"performance"* ]]; then
        echo "perf"
    elif [[ $tags == *"bug"* ]] || [[ $tags == *"data-integrity"* ]]; then
        echo "fix"
    elif [[ $tags == *"documentation"* ]]; then
        echo "docs"
    elif [[ $tags == *"testing"* ]]; then
        echo "test"
    else
        echo "refactor"
    fi
}

# Function to get labels based on priority and tags
get_labels() {
    local priority=$1
    local tags=$2
    local labels=""

    # Priority label
    case $priority in
        p1)
            labels="priority:critical"
            ;;
        p2)
            labels="priority:high"
            ;;
        p3)
            labels="priority:medium"
            ;;
        p4)
            labels="priority:low"
            ;;
    esac

    # Type labels
    if [[ $tags == *"security"* ]]; then
        labels="${labels},type:security"
    fi
    if [[ $tags == *"performance"* ]]; then
        labels="${labels},type:performance"
    fi
    if [[ $tags == *"bug"* ]] || [[ $tags == *"data-integrity"* ]]; then
        labels="${labels},type:bug"
    fi
    if [[ $tags == *"testing"* ]]; then
        labels="${labels},type:test"
    fi
    if [[ $tags == *"documentation"* ]]; then
        labels="${labels},type:docs"
    fi
    if [[ $tags == *"refactor"* ]] || [[ $tags == *"code-quality"* ]] || [[ $tags == *"cleanup"* ]]; then
        labels="${labels},type:refactor"
    fi

    # Area labels
    if [[ $tags == *"backend"* ]] || [[ $tags == *"django"* ]] || [[ $tags == *"database"* ]]; then
        labels="${labels},area:backend"
    fi
    if [[ $tags == *"frontend"* ]] || [[ $tags == *"react"* ]] || [[ $tags == *"vite"* ]]; then
        labels="${labels},area:web"
    fi
    if [[ $tags == *"mobile"* ]] || [[ $tags == *"flutter"* ]]; then
        labels="${labels},area:mobile"
    fi

    # Special labels
    labels="${labels},code-review"

    echo "$labels"
}

# Function to extract problem statement section
extract_section() {
    local file=$1
    local section=$2
    local next_section=$3

    awk "/^## ${section}/,/^## ${next_section}/" "$file" | grep -v "^## ${section}" | grep -v "^## ${next_section}" | sed '/^$/d' | head -20
}

# Function to extract first code block
extract_code_block() {
    local file=$1
    awk '/```/,/```/' "$file" | head -30
}

# Function to create issue body
create_issue_body() {
    local file=$1
    local issue_id=$2
    local priority=$3
    local tags=$4

    # Determine emoji and label
    local emoji=""
    local priority_label=""
    case $priority in
        p1) emoji="🔴"; priority_label="P1" ;;
        p2) emoji="🟡"; priority_label="P2" ;;
        p3) emoji="🔵"; priority_label="P3" ;;
        p4) emoji="⚪"; priority_label="P4" ;;
    esac

    # Extract title (remove leading # and trim)
    local title=$(grep "^# " "$file" | head -1 | sed 's/^# //')

    # Extract problem statement
    local problem=$(extract_section "$file" "Problem Statement" "Findings")

    # Extract solution
    local solution=$(extract_section "$file" "Proposed Solutions" "Recommended Action")

    # Extract acceptance criteria
    local acceptance=$(awk '/^## Acceptance Criteria/,/^## Work Log/' "$file" | grep -E "^\- \[" | head -10)

    # Extract technical details
    local tech_details=$(extract_section "$file" "Technical Details" "Resources")

    # Create body
    cat <<EOF
## Overview

${emoji} **${priority_label}** - ${title}

**Source:** Code audit (October 2025) - Multi-agent code review
**Estimated Effort:** See acceptance criteria

## Problem Statement

${problem}

**Location:** See Technical Details section

## Proposed Solution

${solution}

## Technical Details

${tech_details}

## Acceptance Criteria

${acceptance}

## References

- **Todo File:** \`todos/${file##*/}\`
- **Code Review:** Comprehensive audit (2025-10-25)
- **Related Docs:** See \`/backend/docs/\` and \`COMPREHENSIVE_AUDIT_SUMMARY.md\`

---

**Priority:** ${emoji} ${priority_label}
**Issue ID:** ${issue_id}
**Tags:** ${tags}
EOF
}

# Function to create a single issue
create_issue() {
    local file=$1

    # Extract metadata
    local status=$(get_yaml_field "$file" "status")
    local priority=$(get_yaml_field "$file" "priority")
    local issue_id=$(get_yaml_field "$file" "issue_id")
    local tags=$(get_yaml_field "$file" "tags")

    # Skip if not ready
    if [[ "$status" != "ready" ]]; then
        echo -e "${YELLOW}Skipping $file (status: $status)${NC}"
        ((SKIPPED_COUNT++))
        return
    fi

    # Skip if priority filter doesn't match
    if [[ -n "$PRIORITY_FILTER" ]] && [[ "$priority" != "$PRIORITY_FILTER" ]]; then
        ((SKIPPED_COUNT++))
        return
    fi

    # Extract title
    local title=$(grep "^# " "$file" | head -1 | sed 's/^# //')

    # Get issue prefix and labels
    local prefix=$(get_issue_prefix "$tags" "$priority")
    local labels=$(get_labels "$priority" "$tags")
    local full_title="${prefix}: ${title}"

    # Create issue body
    local body=$(create_issue_body "$file" "$issue_id" "$priority" "$tags")

    # Display what we're creating
    local priority_display=$(echo "$priority" | tr '[:lower:]' '[:upper:]')
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Creating Issue #${issue_id} (${priority_display})${NC}"
    echo -e "${BLUE}Title:${NC} $full_title"
    echo -e "${BLUE}Labels:${NC} $labels"
    echo -e "${BLUE}Source:${NC} ${file##*/}"

    if [[ "$DRY_RUN" == true ]]; then
        echo -e "${YELLOW}[DRY RUN] Would create issue${NC}"
        echo ""
        echo "$body" | head -30
        echo ""
        echo "... (body truncated)"
        ((CREATED_COUNT++))
    else
        # Create the issue
        if gh issue create --title "$full_title" --body "$body" --label "$labels" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Issue created successfully${NC}"
            ((CREATED_COUNT++))
        else
            echo -e "${RED}✗ Failed to create issue${NC}"
            ((SKIPPED_COUNT++))
        fi
    fi

    echo ""
    sleep 1  # Rate limiting
}

# Main execution
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}GitHub Issue Creation Script${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}Running in DRY RUN mode (no issues will be created)${NC}"
    echo ""
fi

if [[ -n "$PRIORITY_FILTER" ]]; then
    FILTER_UPPER=$(echo "$PRIORITY_FILTER" | tr '[:lower:]' '[:upper:]')
    echo -e "${BLUE}Filter:${NC} Only creating ${FILTER_UPPER} issues"
    echo ""
fi

# Check if todos directory exists
if [[ ! -d "$TODOS_DIR" ]]; then
    echo -e "${RED}Error: Todos directory not found: $TODOS_DIR${NC}"
    exit 1
fi

# Create issues in priority order
echo -e "${GREEN}Creating issues from todo files...${NC}"
echo ""

# Create issues from all matching todo files
for file in "$TODOS_DIR"/*-pending-*.md; do
    [[ -f "$file" ]] && create_issue "$file"
done

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}DRY RUN COMPLETE${NC}"
    echo -e "Would create: ${GREEN}$CREATED_COUNT${NC} issues"
else
    echo -e "${GREEN}Issues created: $CREATED_COUNT${NC}"
fi

echo -e "Skipped: $SKIPPED_COUNT"
echo ""

if [[ "$DRY_RUN" == false ]] && [[ $CREATED_COUNT -gt 0 ]]; then
    echo -e "${GREEN}View created issues:${NC}"
    echo "  gh issue list --label code-review"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Review issues: gh issue list --label priority:critical"
    echo "  2. Assign P1 issues to developers"
    echo "  3. Create milestone: gh milestone create \"Code Audit - October 2025\""
    echo "  4. Link issues to milestone"
fi

echo ""
