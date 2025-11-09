#!/bin/bash

# TypeScript Migration Script
# Converts remaining JSX files to TSX with basic transformations

set -e

echo "🚀 Starting TypeScript migration..."

# Array of files to convert (excluding tests)
files=(
  "src/App.jsx"
  "src/main.jsx"
  "src/contexts/RequestContext.jsx"
  "src/components/ErrorBoundary.jsx"
  "src/components/StreamFieldRenderer.jsx"
  "src/components/forum/TipTapEditor.jsx"
  "src/components/forum/ImageUploadWidget.jsx"
  "src/components/diagnosis/DiagnosisCard.jsx"
  "src/components/diagnosis/ReminderManager.jsx"
  "src/components/diagnosis/SaveDiagnosisModal.jsx"
  "src/components/diagnosis/StreamFieldEditor.jsx"
  "src/components/PlantIdentification/FileUpload.jsx"
  "src/components/PlantIdentification/IdentificationResults.jsx"
  "src/pages/HomePage.jsx"
  "src/pages/IdentifyPage.jsx"
  "src/pages/ProfilePage.jsx"
  "src/pages/SettingsPage.jsx"
  "src/pages/BlogPage.jsx"
  "src/pages/BlogListPage.jsx"
  "src/pages/BlogDetailPage.jsx"
  "src/pages/BlogPreview.jsx"
  "src/pages/ForumPage.jsx"
  "src/pages/auth/LoginPage.jsx"
  "src/pages/auth/SignupPage.jsx"
  "src/pages/diagnosis/DiagnosisListPage.jsx"
  "src/pages/diagnosis/DiagnosisDetailPage.jsx"
  "src/pages/forum/CategoryListPage.jsx"
  "src/pages/forum/ThreadListPage.jsx"
  "src/pages/forum/ThreadDetailPage.jsx"
  "src/pages/forum/SearchPage.jsx"
)

count=0
total=${#files[@]}

for file in "${files[@]}"; do
  if [ -f "$file" ]; then
    # Get new filename
    newfile="${file%.jsx}.tsx"

    echo "[$((count+1))/$total] Converting: $file -> $newfile"

    # Copy file
    cp "$file" "$newfile"

    # Basic transformations using sed
    # 1. Update react-router-dom to react-router
    sed -i '' "s/from 'react-router-dom'/from 'react-router'/g" "$newfile"
    sed -i '' 's/from "react-router-dom"/from "react-router"/g' "$newfile"

    # Remove the old JSX file
    rm "$file"

    ((count++))
  else
    echo "⚠️  File not found: $file"
  fi
done

echo ""
echo "✅ Converted $count files to TypeScript!"
echo ""
echo "📝 Manual steps remaining:"
echo "  1. Add type interfaces for component props"
echo "  2. Remove PropTypes imports and declarations"
echo "  3. Add type annotations for state, refs, and event handlers"
echo "  4. Import types from '@/types'"
echo "  5. Run: npm run test"
echo "  6. Fix any type errors"
echo ""
echo "📚 See TYPESCRIPT_MIGRATION_COMPLETION_GUIDE.md for detailed conversion patterns"
