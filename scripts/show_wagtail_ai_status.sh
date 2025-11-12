#!/bin/bash

# Wagtail AI Integration - Project Status Display
# Run this to see current project status at a glance

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo "${BOLD}  🤖 Wagtail AI Integration - Project Status${NC}"
echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check Wagtail version
cd "$(dirname "$0")/../backend" || exit 1
source venv/bin/activate 2>/dev/null || true

WAGTAIL_VERSION=$(python -c "import wagtail; print(wagtail.__version__)" 2>/dev/null || echo "Not installed")

echo "${BOLD}📦 Current Versions${NC}"
echo "──────────────────────────────────────────────────────────"
echo "  Django:  $(python -c "import django; print(django.__version__)" 2>/dev/null || echo "Not found")"
echo "  Wagtail: ${WAGTAIL_VERSION}"

# Check if upgrade needed
if [[ "$WAGTAIL_VERSION" == "7.0.3" ]]; then
    echo "  ${RED}⚠️  UPGRADE REQUIRED: Wagtail 7.1+ needed for AI${NC}"
elif [[ "$WAGTAIL_VERSION" =~ ^7\.[1-9] ]]; then
    echo "  ${GREEN}✅ Wagtail version compatible with AI${NC}"
else
    echo "  ${YELLOW}⚠️  Unknown compatibility status${NC}"
fi

echo "  Wagtail AI: $(python -c "import wagtail_ai; print(wagtail_ai.__version__)" 2>/dev/null || echo "Not installed")"
echo ""

# Check wagtail_ai status in settings
echo "${BOLD}⚙️  Wagtail AI Configuration${NC}"
echo "──────────────────────────────────────────────────────────"

if grep -q "^[[:space:]]*'wagtail_ai'" plant_community_backend/settings.py 2>/dev/null; then
    echo "  ${GREEN}✅ wagtail_ai ENABLED in INSTALLED_APPS${NC}"
elif grep -q "^[[:space:]]*#.*'wagtail_ai'" plant_community_backend/settings.py 2>/dev/null; then
    echo "  ${YELLOW}⏸️  wagtail_ai DISABLED (commented out)${NC}"
else
    echo "  ${RED}❌ wagtail_ai NOT FOUND in settings${NC}"
fi

# Check for OpenAI API key
if [[ -f .env ]]; then
    if grep -q "^OPENAI_API_KEY=sk-" .env 2>/dev/null; then
        echo "  ${GREEN}✅ OpenAI API key configured${NC}"
    elif grep -q "^OPENAI_API_KEY=" .env 2>/dev/null; then
        echo "  ${YELLOW}⚠️  OpenAI API key placeholder (not set)${NC}"
    else
        echo "  ${RED}❌ OpenAI API key not configured${NC}"
    fi
else
    echo "  ${RED}❌ .env file not found${NC}"
fi

echo ""

# Check GitHub issues
echo "${BOLD}📋 GitHub Issues${NC}"
echo "──────────────────────────────────────────────────────────"

# Check if gh CLI is available
if command -v gh &> /dev/null; then
    ISSUE_158=$(gh issue view 158 --json state,title,assignees 2>/dev/null || echo "")
    ISSUE_157=$(gh issue view 157 --json state,title,assignees 2>/dev/null || echo "")

    if [[ -n "$ISSUE_158" ]]; then
        STATE_158=$(echo "$ISSUE_158" | python -c "import sys,json; print(json.load(sys.stdin)['state'])" 2>/dev/null || echo "unknown")
        if [[ "$STATE_158" == "OPEN" ]]; then
            echo "  ${YELLOW}#158: Wagtail Upgrade - OPEN${NC}"
        else
            echo "  ${GREEN}#158: Wagtail Upgrade - CLOSED ✅${NC}"
        fi
    else
        echo "  #158: Not found"
    fi

    if [[ -n "$ISSUE_157" ]]; then
        STATE_157=$(echo "$ISSUE_157" | python -c "import sys,json; print(json.load(sys.stdin)['state'])" 2>/dev/null || echo "unknown")
        if [[ "$STATE_157" == "OPEN" ]]; then
            echo "  ${YELLOW}#157: Wagtail AI - OPEN${NC}"
        else
            echo "  ${GREEN}#157: Wagtail AI - CLOSED ✅${NC}"
        fi
    else
        echo "  #157: Not found"
    fi
else
    echo "  ${YELLOW}⚠️  GitHub CLI not installed (install with: brew install gh)${NC}"
    echo "  View issues manually:"
    echo "    - https://github.com/Xertox1234/plant_id_community/issues/158"
    echo "    - https://github.com/Xertox1234/plant_id_community/issues/157"
fi

echo ""

# Check Redis
echo "${BOLD}💾 Redis Status${NC}"
echo "──────────────────────────────────────────────────────────"

if command -v redis-cli &> /dev/null; then
    if redis-cli ping &>/dev/null; then
        echo "  ${GREEN}✅ Redis running${NC}"

        # Check for AI cache keys
        AI_KEYS=$(redis-cli keys "blog:ai:*" 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$AI_KEYS" -gt 0 ]]; then
            echo "  ${GREEN}✅ ${AI_KEYS} AI cache keys found${NC}"
        else
            echo "  ${YELLOW}⏸️  No AI cache keys yet${NC}"
        fi
    else
        echo "  ${RED}❌ Redis not running${NC}"
    fi
else
    echo "  ${YELLOW}⚠️  redis-cli not installed${NC}"
fi

echo ""

# Status summary
echo "${BOLD}📊 Project Status Summary${NC}"
echo "──────────────────────────────────────────────────────────"

if [[ "$WAGTAIL_VERSION" == "7.0.3" ]]; then
    echo "  ${YELLOW}STATUS: Ready for Prerequisite (Issue #158)${NC}"
    echo ""
    echo "  Next Steps:"
    echo "    1. ${BOLD}Complete Issue #158${NC} - Upgrade Wagtail to 7.1+"
    echo "       Timeline: 1-2 days (4-5 hours)"
    echo "       Guide: docs/WAGTAIL_AI_PROJECT_OVERVIEW.md"
    echo ""
    echo "    2. After #158 complete:"
    echo "       Start Issue #157 Phase 1 (AI integration)"
elif [[ "$WAGTAIL_VERSION" =~ ^7\.[1-9] ]]; then
    if grep -q "^[[:space:]]*'wagtail_ai'" plant_community_backend/settings.py 2>/dev/null; then
        echo "  ${GREEN}STATUS: Wagtail AI Active${NC}"
        echo ""
        echo "  Configuration verified:"
        echo "    ✅ Wagtail 7.1+ installed"
        echo "    ✅ wagtail_ai enabled"
        echo ""
        echo "  Next: Continue with Issue #157 phases"
    else
        echo "  ${YELLOW}STATUS: Ready for AI Integration (Issue #157)${NC}"
        echo ""
        echo "  Prerequisite complete!"
        echo "    ✅ Wagtail 7.1+ installed"
        echo ""
        echo "  Next Steps:"
        echo "    1. Uncomment 'wagtail_ai' in settings.py:132"
        echo "    2. Add OPENAI_API_KEY to .env"
        echo "    3. python manage.py migrate"
        echo "    4. Follow Issue #157 Phase 1"
    fi
else
    echo "  ${RED}STATUS: Version Check Required${NC}"
    echo ""
    echo "  Current Wagtail version: ${WAGTAIL_VERSION}"
    echo "  Required for AI: 7.1+"
fi

echo ""

# Documentation links
echo "${BOLD}📚 Documentation${NC}"
echo "──────────────────────────────────────────────────────────"
echo "  Project Overview:  docs/WAGTAIL_AI_PROJECT_OVERVIEW.md"
echo "  GitHub Project:    docs/GITHUB_PROJECT_SETUP.md"
echo "  Issue #158:        https://github.com/Xertox1234/plant_id_community/issues/158"
echo "  Issue #157:        https://github.com/Xertox1234/plant_id_community/issues/157"
echo ""

echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""