#!/bin/bash

###############################################################################
# GitHub Label Creation Script
#
# Creates labels for code audit issue tracking
#
# Usage: ./create_github_labels.sh [--dry-run]
#
# Options:
#   --dry-run    Show what would be created without creating labels
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DRY_RUN=false

# Parse arguments
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# Check gh CLI
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) not installed${NC}"
    exit 1
fi

# Function to create or update label
create_label() {
    local name=$1
    local color=$2
    local description=$3

    if [[ "$DRY_RUN" == true ]]; then
        echo -e "${YELLOW}[DRY RUN]${NC} Would create: ${BLUE}$name${NC} (#$color) - $description"
    else
        # Check if label exists
        if gh label list | grep -q "^${name}"; then
            echo -e "${YELLOW}Updating:${NC} $name"
            gh label edit "$name" --color "$color" --description "$description" 2>/dev/null || true
        else
            echo -e "${GREEN}Creating:${NC} $name"
            gh label create "$name" --color "$color" --description "$description" 2>/dev/null || true
        fi
    fi
}

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}GitHub Label Creation Script${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}Running in DRY RUN mode${NC}"
    echo ""
fi

echo "Creating Priority Labels..."
create_label "priority:critical" "d73a4a" "Fix within 24-48 hours (P1)"
create_label "priority:high" "ff9800" "Fix within 1 week (P2)"
create_label "priority:medium" "ffeb3b" "Fix within 2-4 weeks (P3)"
create_label "priority:low" "e0e0e0" "Fix when possible (P4)"

echo ""
echo "Creating Type Labels..."
create_label "type:security" "d93f0b" "Security vulnerability or concern"
create_label "type:bug" "d73a4a" "Something isn't working correctly"
create_label "type:performance" "ff6f00" "Performance improvement needed"
create_label "type:refactor" "fbca04" "Code refactoring or cleanup"
create_label "type:test" "0e8a16" "Testing improvements"
create_label "type:docs" "0075ca" "Documentation improvements"

echo ""
echo "Creating Area Labels..."
create_label "area:backend" "0052cc" "Django backend"
create_label "area:web" "1d76db" "React web frontend"
create_label "area:mobile" "5319e7" "Flutter mobile app"

echo ""
echo "Creating Special Labels..."
create_label "code-review" "c5def5" "From code review/audit findings"
create_label "code-quality" "bfdadc" "Code quality improvement"
create_label "data-integrity" "c2e0c6" "Data integrity concern"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [[ "$DRY_RUN" == false ]]; then
    echo -e "${GREEN}✓ Labels created/updated successfully${NC}"
    echo ""
    echo "View labels:"
    echo "  gh label list"
else
    echo -e "${YELLOW}✓ Dry run complete${NC}"
    echo ""
    echo "Run without --dry-run to create labels:"
    echo "  ./create_github_labels.sh"
fi

echo ""
