#!/bin/bash
# Firebase API Key Rotation Script
# Issue #142: Rotate compromised Firebase keys via CLI

set -e  # Exit on error

PROJECT_ID="plant-community-prod"
ANDROID_PACKAGE="com.plantcommunity.plant_community_mobile"
IOS_BUNDLE_ID="com.plantcommunity.plantCommunityMobile"

echo "🔐 Firebase Key Rotation Script"
echo "================================"
echo ""

# Step 1: Login (if needed)
echo "📝 Step 1: Checking Firebase authentication..."
if ! firebase projects:list &>/dev/null; then
    echo "⚠️  Not logged in. Running: firebase login"
    firebase login
fi
echo "✅ Authenticated"
echo ""

# Step 2: List current apps
echo "📋 Step 2: Listing current app registrations..."
echo "Android apps:"
firebase apps:list ANDROID --project=$PROJECT_ID

echo ""
echo "iOS apps:"
firebase apps:list IOS --project=$PROJECT_ID
echo ""

# Step 3: Get app IDs (for deletion)
echo "🔍 Step 3: Finding app IDs..."
ANDROID_APP_ID=$(firebase apps:list ANDROID --project=$PROJECT_ID --json | jq -r '.result[] | select(.packageName=="'$ANDROID_PACKAGE'") | .appId' | head -1)
IOS_APP_ID=$(firebase apps:list IOS --project=$PROJECT_ID --json | jq -r '.result[] | select(.bundleId=="'$IOS_BUNDLE_ID'") | .appId' | head -1)

if [ -n "$ANDROID_APP_ID" ]; then
    echo "Found Android app: $ANDROID_APP_ID"
else
    echo "⚠️  No Android app found with package: $ANDROID_PACKAGE"
fi

if [ -n "$IOS_APP_ID" ]; then
    echo "Found iOS app: $IOS_APP_ID"
else
    echo "⚠️  No iOS app found with bundle ID: $IOS_BUNDLE_ID"
fi
echo ""

# Step 4: Confirm deletion (CRITICAL - irreversible)
echo "⚠️  WARNING: This will DELETE the existing app registrations!"
echo "⚠️  This will IMMEDIATELY invalidate the old API keys."
echo "⚠️  All users with old app versions will need to update."
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Aborted by user"
    exit 1
fi
echo ""

# Step 5: Delete Android app
if [ -n "$ANDROID_APP_ID" ]; then
    echo "🗑️  Step 5a: Deleting Android app..."
    echo "App ID: $ANDROID_APP_ID"
    
    # Note: firebase apps:delete is not available in CLI
    # Must use Firebase Console or gcloud CLI
    echo "⚠️  Firebase CLI doesn't support app deletion yet."
    echo "Please delete manually:"
    echo "1. Go to: https://console.firebase.google.com/project/$PROJECT_ID/settings/general"
    echo "2. Scroll to 'Your apps' section"
    echo "3. Click Android app → Delete app"
    echo ""
    read -p "Press ENTER after deleting Android app in console..."
else
    echo "⏭️  Skipping Android app deletion (not found)"
fi

# Step 6: Delete iOS app
if [ -n "$IOS_APP_ID" ]; then
    echo "🗑️  Step 5b: Deleting iOS app..."
    echo "App ID: $IOS_APP_ID"
    echo "⚠️  Firebase CLI doesn't support app deletion yet."
    echo "Please delete manually:"
    echo "1. Go to: https://console.firebase.google.com/project/$PROJECT_ID/settings/general"
    echo "2. Scroll to 'Your apps' section"  
    echo "3. Click iOS app → Delete app"
    echo ""
    read -p "Press ENTER after deleting iOS app in console..."
else
    echo "⏭️  Skipping iOS app deletion (not found)"
fi

# Step 7: Create new Android app
echo ""
echo "➕ Step 6a: Creating new Android app..."
firebase apps:create ANDROID \
    --project=$PROJECT_ID \
    --package-name=$ANDROID_PACKAGE \
    --display-name="Plant Community Mobile (Android)"

# Get new Android app ID
NEW_ANDROID_APP_ID=$(firebase apps:list ANDROID --project=$PROJECT_ID --json | jq -r '.result[] | select(.packageName=="'$ANDROID_PACKAGE'") | .appId' | head -1)
echo "✅ Created Android app: $NEW_ANDROID_APP_ID"
echo ""

# Step 8: Create new iOS app
echo "➕ Step 6b: Creating new iOS app..."
firebase apps:create IOS \
    --project=$PROJECT_ID \
    --bundle-id=$IOS_BUNDLE_ID \
    --display-name="Plant Community Mobile (iOS)"

# Get new iOS app ID
NEW_IOS_APP_ID=$(firebase apps:list IOS --project=$PROJECT_ID --json | jq -r '.result[] | select(.bundleId=="'$IOS_BUNDLE_ID'") | .appId' | head -1)
echo "✅ Created iOS app: $NEW_IOS_APP_ID"
echo ""

# Step 9: Download new configuration files
echo "📥 Step 7: Downloading new configuration files..."

echo "Downloading google-services.json..."
firebase apps:sdkconfig ANDROID $NEW_ANDROID_APP_ID \
    --project=$PROJECT_ID \
    --out android/app/google-services.json.NEW

echo "Downloading GoogleService-Info.plist..."
firebase apps:sdkconfig IOS $NEW_IOS_APP_ID \
    --project=$PROJECT_ID \
    --out ios/Runner/GoogleService-Info.plist.NEW

echo "✅ Downloaded new configuration files"
echo ""

# Step 10: Extract keys to .env
echo "🔑 Step 8: Extracting keys to .env file..."

# Extract from google-services.json
ANDROID_API_KEY=$(jq -r '.client[0].api_key[0].current_key' android/app/google-services.json.NEW)
ANDROID_APP_ID=$NEW_ANDROID_APP_ID
ANDROID_PROJECT_ID=$PROJECT_ID
ANDROID_SENDER_ID=$(jq -r '.project_info.project_number' android/app/google-services.json.NEW)
ANDROID_STORAGE_BUCKET=$(jq -r '.project_info.storage_bucket' android/app/google-services.json.NEW)

echo "Updating .env file..."
cat > .env << ENVEOF
# Firebase Configuration
# Generated by rotate_firebase_keys.sh on $(date)
# DO NOT commit this file to git

# Android Firebase Configuration
FIREBASE_ANDROID_API_KEY=$ANDROID_API_KEY
FIREBASE_ANDROID_APP_ID=$ANDROID_APP_ID
FIREBASE_ANDROID_MESSAGING_SENDER_ID=$ANDROID_SENDER_ID
FIREBASE_ANDROID_PROJECT_ID=$ANDROID_PROJECT_ID
FIREBASE_ANDROID_STORAGE_BUCKET=$ANDROID_STORAGE_BUCKET

# iOS Firebase Configuration (extract manually from GoogleService-Info.plist.NEW)
FIREBASE_IOS_API_KEY=EXTRACT_FROM_PLIST
FIREBASE_IOS_APP_ID=$NEW_IOS_APP_ID
FIREBASE_IOS_MESSAGING_SENDER_ID=$ANDROID_SENDER_ID
FIREBASE_IOS_PROJECT_ID=$ANDROID_PROJECT_ID
FIREBASE_IOS_STORAGE_BUCKET=$ANDROID_STORAGE_BUCKET
FIREBASE_IOS_BUNDLE_ID=$IOS_BUNDLE_ID
ENVEOF

echo "✅ Updated .env file"
echo ""

# Step 11: Summary
echo "✅ Key Rotation Complete!"
echo "========================"
echo ""
echo "📝 Next Steps:"
echo "1. Manually extract iOS API key from ios/Runner/GoogleService-Info.plist.NEW"
echo "2. Update FIREBASE_IOS_API_KEY in .env file"
echo "3. Test app: flutter run -d android"
echo "4. Test app: flutter run -d ios"
echo "5. Delete .NEW files: rm android/app/google-services.json.NEW ios/Runner/GoogleService-Info.plist.NEW"
echo "6. Commit changes (placeholder files only): git add .gitignore android/app/google-services.json.example"
echo "7. Build and deploy new app versions to stores"
echo ""
echo "⚠️  Old API key is now INVALIDATED"
echo "⚠️  Users with old app versions will need to update"
echo ""
echo "🔐 New Keys Summary:"
echo "Android API Key: $ANDROID_API_KEY"
echo "Android App ID: $ANDROID_APP_ID"
echo "iOS App ID: $NEW_IOS_APP_ID"
echo ""
