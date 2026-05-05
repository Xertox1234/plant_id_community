# Deep Linking Setup Guide

**Date**: November 15, 2025
**Status**: Configuration Ready
**go_router Version**: 17.0.0

Deep linking allows users to open specific screens in your app from external sources like:
- Push notifications
- Email links
- Web links
- QR codes
- Other apps

## Overview

Our app uses the following URI schemes:

- **Custom Scheme**: `plantcommunity://` (for app-to-app navigation)
- **Universal Links (iOS)**: `https://plantcommunity.app/` (for web-to-app navigation)
- **App Links (Android)**: `https://plantcommunity.app/` (for web-to-app navigation)

## Supported Deep Link Routes

| Route | Deep Link | Example |
|-------|-----------|---------|
| Home | `plantcommunity://home` | Open app to home screen |
| Results | `plantcommunity://results?id=abc123` | View specific plant result |
| Profile | `plantcommunity://profile` | Open user profile |
| Garden | `plantcommunity://garden` | Open garden overview |
| Garden Bed | `plantcommunity://garden?bed_id=xyz789` | View specific garden bed |

## iOS Configuration

### Step 1: Update Info.plist

Add the following to `ios/Runner/Info.plist`:

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLName</key>
    <string>com.plantcommunity.app</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>plantcommunity</string>
    </array>
  </dict>
</array>

<!-- Universal Links (for web URLs) -->
<key>com.apple.developer.associated-domains</key>
<array>
  <string>applinks:plantcommunity.app</string>
</array>
```

### Step 2: Create apple-app-site-association File

Host this file at `https://plantcommunity.app/.well-known/apple-app-site-association`:

```json
{
  "applinks": {
    "apps": [],
    "details": [
      {
        "appID": "TEAM_ID.com.plantcommunity.app",
        "paths": [
          "/home",
          "/results/*",
          "/profile",
          "/garden/*"
        ]
      }
    ]
  }
}
```

**Important**: Replace `TEAM_ID` with your actual Apple Team ID.

### Step 3: Enable Associated Domains in Xcode

1. Open `ios/Runner.xcworkspace` in Xcode
2. Select the Runner target
3. Go to "Signing & Capabilities" tab
4. Click "+ Capability" and add "Associated Domains"
5. Add domain: `applinks:plantcommunity.app`

## Android Configuration

### Step 1: Update AndroidManifest.xml

Add intent filters to `android/app/src/main/AndroidManifest.xml`:

```xml
<activity
    android:name=".MainActivity"
    ...>

    <!-- Existing intent filter for launch -->
    <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
    </intent-filter>

    <!-- Deep link intent filter (custom scheme) -->
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="plantcommunity" />
    </intent-filter>

    <!-- App Links intent filter (web URLs) -->
    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="https"
            android:host="plantcommunity.app" />
    </intent-filter>

</activity>
```

### Step 2: Create assetlinks.json File

Host this file at `https://plantcommunity.app/.well-known/assetlinks.json`:

```json
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.plantcommunity.app",
      "sha256_cert_fingerprints": [
        "YOUR_APP_SHA256_FINGERPRINT_HERE"
      ]
    }
  }
]
```

**Get your SHA256 fingerprint**:

```bash
# Debug keystore
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android -keypass android

# Release keystore
keytool -list -v -keystore /path/to/your/keystore -alias your_alias
```

## Flutter Code (Already Implemented)

Our go_router configuration automatically handles deep links. No additional Flutter code needed!

The router will:
1. Parse incoming deep link URIs
2. Extract route path and query parameters
3. Navigate to the appropriate screen
4. Show error screen if route is invalid

### Example: Handling Deep Links in Code

```dart
// Helper methods are already available via DeepLinks class
import 'package:plant_community_mobile/core/routing/navigation_extensions.dart';

// Generate deep link URI for push notification
final plantResultsUri = DeepLinks.results('plant-123');
print(plantResultsUri); // Output: plantcommunity://results?id=plant-123

// Generate deep link for specific garden bed
final gardenBedUri = DeepLinks.gardenBed('bed-456');
print(gardenBedUri); // Output: plantcommunity://garden?bed_id=bed-456
```

## Testing Deep Links

### iOS Simulator

```bash
# Test custom scheme
xcrun simctl openurl booted "plantcommunity://home"
xcrun simctl openurl booted "plantcommunity://results?id=abc123"

# Test universal links
xcrun simctl openurl booted "https://plantcommunity.app/home"
```

### Android Emulator

```bash
# Test custom scheme
adb shell am start -W -a android.intent.action.VIEW -d "plantcommunity://home"

# Test app links
adb shell am start -W -a android.intent.action.VIEW -d "https://plantcommunity.app/home"
```

### Physical Devices

**iOS**:
1. Send yourself an email or iMessage with the deep link
2. Tap the link
3. App should open to the correct screen

**Android**:
1. Send yourself an email or SMS with the deep link
2. Tap the link
3. Choose "Plant Community" app from the chooser (or set as default)

## Debugging

### iOS

Check system logs in Console.app:
```
process:Runner
```

Look for messages like:
```
Opening URL: plantcommunity://home
```

### Android

Check logcat:
```bash
adb logcat | grep -i "plant"
```

Look for messages like:
```
Intent received: plantcommunity://home
```

### Common Issues

**iOS Universal Links Not Working**:
1. Verify `apple-app-site-association` file is accessible (no redirect, returns JSON)
2. Check TEAM_ID is correct
3. Ensure Associated Domains capability is enabled
4. Universal links don't work if app is already installed - uninstall and reinstall

**Android App Links Not Working**:
1. Verify `assetlinks.json` file is accessible
2. Check SHA256 fingerprint matches your app
3. Ensure `android:autoVerify="true"` is set
4. Clear app defaults: Settings → Apps → Plant Community → Open by default → Clear defaults

## Production Checklist

- [ ] `apple-app-site-association` hosted at `https://plantcommunity.app/.well-known/`
- [ ] `assetlinks.json` hosted at `https://plantcommunity.app/.well-known/`
- [ ] Apple Team ID configured correctly
- [ ] Android SHA256 fingerprint from release keystore
- [ ] Associated Domains enabled in Xcode
- [ ] `android:autoVerify="true"` in AndroidManifest.xml
- [ ] Deep links tested on iOS physical device
- [ ] Deep links tested on Android physical device
- [ ] Analytics tracking for deep link usage (optional)

## Security Considerations

### URL Validation

Our router already validates incoming deep links:
- Invalid routes → Error screen
- Missing required parameters → Error screen
- Unauthenticated users accessing protected routes → Redirected to login

### Sensitive Data

**Never include sensitive data in deep links**:
- ❌ BAD: `plantcommunity://profile?password=secret123`
- ✅ GOOD: `plantcommunity://profile` (fetch data after authentication)

**For sensitive operations**:
1. Use deep link to navigate to screen
2. Require authentication if not logged in
3. Fetch sensitive data from API with JWT token

## Future Enhancements

- [ ] Firebase Dynamic Links (shorter URLs, analytics, cross-platform)
- [ ] Branch.io integration (advanced attribution)
- [ ] Deferred deep linking (install → open to specific screen)
- [ ] Deep link analytics dashboard
- [ ] A/B testing with different deep link formats

---

**Last Updated**: November 15, 2025
**Contributors**: Claude Code + Will Tower
**Related Files**:
- `lib/core/routing/app_router.dart` - Router configuration
- `lib/core/routing/navigation_extensions.dart` - DeepLinks helper class
- `ios/Runner/Info.plist` - iOS configuration
- `android/app/src/main/AndroidManifest.xml` - Android configuration
