---
status: pending
priority: p2
issue_id: "427"
tags: [forum, flutter, mobile, accessibility, ios]
dependencies: []
---

# VoiceOver users can't close the in-app browser: the URL bar covers the X

## Problem

Since build 14 (todo 424), forum links and video cards open in the in-app
browser (`LaunchMode.inAppBrowserView`, which is SFSafariViewController on
iOS). On 2026-09-24 the owner found that with VoiceOver on, the URL bar's
focus area covers the close (X) button. Touching where the X is selects the
URL, and the X can't be reached that way. A VoiceOver user who opens a link
may be stuck in the browser.

With VoiceOver off, the browser closes normally.

## Findings

- The browser is Apple's SFSafariViewController, not our widget tree. Its
  layout and focus areas belong to iOS, so nothing in
  `forum_link_launcher.dart` controls them. Hypothesis, not verified: this is
  iOS 26 system behaviour, not something the app can fix in place.
- `url_launcher` 6.3.2's only in-app browser option is
  `InAppBrowserConfiguration(showTitle:)`. It can't set
  `dismissButtonStyle` or the bar tint.
- Not yet tested (check these first, on the device, with VoiceOver on):
  1. **Swipe navigation:** swipe right or left through the elements. Does
     focus ever land on the X on its own, separate from the URL?
  2. **The escape gesture:** a two-finger "Z" scrub is VoiceOver's standard
     "go back/dismiss". Does it close the browser?
  3. **Whether `showTitle: true`** changes the bar layout enough to separate
     the two areas.
  If 1 or 2 works, VoiceOver users have a standard way out, and this becomes
  a question of whether the tap target is good enough.

## Recommended Action

Do the three device checks above first. Then, depending on the results:

- **If VoiceOver users have no reliable way out:** when VoiceOver is on
  (`MediaQuery.accessibleNavigationOf(context)`), open links with
  `LaunchMode.externalApplication`. Safari's own UI is fully accessible, and
  the system "◀ Houseplant MD" status-bar chip returns to the app. Or do this
  for everyone if the difference isn't worth keeping.
- **If only the tap target is poor:** record the working gesture and
  consider reporting it to Apple (Feedback Assistant) as an
  SFSafariViewController accessibility bug.

## Acceptance Criteria

- [ ] The three device checks above are recorded here.
- [ ] A VoiceOver user can reliably leave a link they opened and get back to
      the thread. Checked on a device.
- [ ] If the launch mode changes with VoiceOver, a widget test pins the
      mode chosen for each case (the fake launcher from
      `forum_thread_links_test.dart` records the mode).

## Work Log

### 2026-09-24 - Filed from build 14's device check
