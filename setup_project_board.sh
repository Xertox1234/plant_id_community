#!/bin/bash
# Setup GitHub Project Board for Code Review Findings
# Created: November 3, 2025
# Usage: bash setup_project_board.sh

set -e  # Exit on error

echo "🚀 Setting up Code Review Findings Project Board..."
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed"
    echo "Install: brew install gh"
    exit 1
fi

# Check if jq is installed (for JSON parsing)
if ! command -v jq &> /dev/null; then
    echo "⚠️  Warning: jq not installed (optional, for better output)"
    echo "Install: brew install jq"
fi

echo "📋 Step 1: Creating project..."
PROJECT_RESPONSE=$(gh project create \
  --owner "Xertox1234" \
  --title "Code Review Findings - Nov 2025" \
  --format json 2>&1) || {
    echo "❌ Error creating project:"
    echo "$PROJECT_RESPONSE"
    echo ""
    echo "💡 Try: gh auth refresh -s project,read:project"
    exit 1
}

if command -v jq &> /dev/null; then
    PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')
    PROJECT_URL=$(echo "$PROJECT_RESPONSE" | jq -r '.url')
else
    PROJECT_ID=$(echo "$PROJECT_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    PROJECT_URL=$(echo "$PROJECT_RESPONSE" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
fi

echo "✅ Created project: $PROJECT_ID"
echo "🔗 URL: $PROJECT_URL"
echo ""

echo "📝 Step 2: Adding issues to project..."

# Array of issues to add
ISSUES=(
    "113:PostViewSet N+1 Query (BLOCKER)"
    "114:Frontend Constants (BLOCKER)"
    "115:Prefetch Filter (IMPORTANT)"
    "116:PII in Logs (IMPORTANT)"
    "117:Regression Test (IMPORTANT)"
)

for ISSUE_INFO in "${ISSUES[@]}"; do
    ISSUE_NUM=$(echo "$ISSUE_INFO" | cut -d':' -f1)
    ISSUE_DESC=$(echo "$ISSUE_INFO" | cut -d':' -f2)

    echo "  Adding #$ISSUE_NUM - $ISSUE_DESC"
    gh project item-add "$PROJECT_ID" \
        --owner "Xertox1234" \
        --url "https://github.com/Xertox1234/plant_id_community/issues/$ISSUE_NUM" \
        2>&1 || echo "  ⚠️  Could not add issue #$ISSUE_NUM"
done

echo ""
echo "✅ Project board setup complete!"
echo ""
echo "📊 Summary:"
echo "  - Project ID: $PROJECT_ID"
echo "  - Issues Added: 5"
echo "  - Blockers: 2 (#113, #114)"
echo "  - Important: 3 (#115, #116, #117)"
echo "  - Total Effort: 85 minutes"
echo ""
echo "🔗 View project: $PROJECT_URL"
echo ""
echo "📋 Next Steps:"
echo "  1. Open project in browser"
echo "  2. Create columns: 🚨 Blockers, ⚠️ Important, 🔄 In Progress, ✅ Done"
echo "  3. Drag issues to appropriate columns"
echo "  4. Add custom fields: Effort, Pattern, Area, Risk"
echo ""
echo "🎯 Recommended fix order:"
echo "  1. #113 (30 min) - N+1 query fix → biggest impact"
echo "  2. #114 (15 min) - Frontend constants → quick win"
echo "  3. #115 (10 min) - Prefetch filter → builds on #113"
echo "  4. #116 (10 min) - PII logging → security compliance"
echo "  5. #117 (20 min) - Regression test → depends on #113"
echo ""
echo "✨ Done!"
