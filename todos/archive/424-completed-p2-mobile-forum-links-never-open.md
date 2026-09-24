---
status: completed
priority: p2
issue_id: "424"
tags: [forum, flutter, mobile, accessibility]
dependencies: []
---

# Links in forum posts never open on mobile: the app shows the raw URL in a SnackBar

## Problem

Tapping any link in a forum thread in the Flutter app does not open it. The
thread screen's handler only shows the URL as text:

```dart
// plant_community_mobile/lib/features/forum/screens/forum_thread_screen.dart
void _showLink(BuildContext context, String href) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(href)));
}
```

This applies to video embed cards and to ordinary links in post text. Both
reach `_showLink` through `onOpenLink` (`forum_body_renderer.dart`,
`post_card.dart`). The app has no `url_launcher` dependency: it appears in
neither `pubspec.yaml` nor `pubspec.lock`.

Found on 2026-09-24 during build 13's VoiceOver check (todo 398). A double-tap
on a video card now correctly runs its tap action, but the result is a
SnackBar that VoiceOver spells out character by character, and the video never
opens. Sighted users get the same SnackBar, silently.

## Findings

- This was deliberate, but it was never tracked anywhere. Todo 344's Work Log
  says the card hands its URL to the existing `onOpenLink` "url_launcher-free"
  and that "a real launcher stays parity work (todo 341)". Todo 341
  (`todos/archive/341-completed-p3-flutter-forum-feature-parity.md`) is
  **completed** and never mentions opening links. The pointer led to a closed
  todo, so the gap had no owner.
- `_showLink` is the only link handler in `lib/`. There is no second
  implementation to reconcile.

## Recommended Action

1. Add `url_launcher`. In `_showLink`, open `http`/`https` URLs in an in-app
   browser (`LaunchMode.inAppBrowserView`, which is Safari View Controller on
   iOS and a Custom Tab on Android). Refuse every other scheme (`javascript:`,
   `file:`, `intent:`, and so on). The server sanitizes `href`s (nh3), but the
   client should enforce the allowlist too.
2. On failure (`launchUrl` returns false, or the scheme is rejected), show a
   short message such as "Couldn't open this link", not the raw URL.
3. iOS: declare `LSApplicationQueriesSchemes` only if the code uses
   `canLaunchUrl` for `https`. The in-app browser mode doesn't need it.
4. It ships in the next TestFlight build (14 or later). The fix doesn't reach
   the device before that.

## Acceptance Criteria

- [x] Tapping a paragraph link and tapping a video card each open the URL in
      the in-app browser, with VoiceOver on and off. Checked on a device.
- [x] A widget test with a fake launcher shows that tapping a link, and
      performing `SemanticsAction.tap` on an embed card, pass the exact URL to
      the launcher. The test fails against the current SnackBar code.
      `forum_thread_links_test.dart`: both failed first (`Actual: []`).
- [x] A non-`http(s)` `href` is never passed to the launcher. Pinned by a
      test. Five hrefs through the screen plus 12 in the `openableForumLink`
      unit test. Deleting the scheme check fails 2 tests.
- [x] A link that fails to launch shows a readable error, not the raw URL.
      Covers both a `false` return and a thrown exception.
- [x] `flutter analyze` is clean, the full `flutter test` passes, and
      codegen is unaffected. 774 passed, 9 skipped. The provider is a plain
      `Provider`, so there is no `build_runner` output.

## Work Log

### 2026-09-24 - Filed from build 13's device check

- VoiceOver double-tap on the video card in topic 44 showed the URL in a
  SnackBar, and VoiceOver spelled it out. Todo 398's own fix works: the tap
  action now fires. The broken part is what the tap action does.

### 2026-09-24 - Launcher wired in; device check waits for build 14

- Added `url_launcher` ^6.3.2. The lockfile gained only its eight
  `url_launcher*` packages. `pod install` added `url_launcher_ios` to
  `ios/Podfile.lock`.
- `lib/features/forum/services/forum_link_launcher.dart` holds two things.
  `forumLinkLauncherProvider` is the seam that tests override;
  `LaunchMode.inAppBrowserView` is the real launcher. `openableForumLink`
  enforces the allowlist: an absolute `http`/`https` URL with a host.
  Relative hrefs are refused too. The server does keep them (nh3 limits
  schemes only on absolute URLs), so a post holding `<a href="/forum/...">`
  shows the error on mobile. It never opened before this change either
  (the SnackBar). Resolving it against the web origin is todo 425; the
  bundled `/code-review` raised it as a low-severity finding.
- `forum_thread_screen.dart`: `_showLink` became `_openLink`. It returns the
  one fixed message "Couldn't open this link." for a refused scheme, a
  `false` return, or a thrown exception. VoiceOver no longer reads a URL
  aloud.
- No `LSApplicationQueriesSchemes`: the code never calls `canLaunchUrl`.
- The todo stays `pending` until the build 14 device check (the first AC).
  The archive tripwire fails an archived todo that has an unchecked AC.

### 2026-09-24 - Verified on a device (TestFlight build 14)

- The owner checked build 14 with VoiceOver on and off. Links and video cards
  both open in the in-app browser. The first AC passes.
- A VoiceOver problem was found in the browser itself: the URL bar's focus
  area covers the close (X) button, so a VoiceOver user can't dismiss the
  browser by tapping. This is in Apple's SFSafariViewController UI, not our
  widget tree. Filed as todo 427.
