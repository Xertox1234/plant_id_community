---
status: completed
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

- [x] The device checks above are recorded here. Checks 1 and 2 were run
      and both pass (see the Work Log). Check 3 (`showTitle`) was dropped: it
      needs a new build and only mattered if 1 and 2 failed.
- [x] A VoiceOver user can reliably leave a link they opened and get back to
      the thread. Checked on a device (build 14, 2026-09-24): both the
      two-finger Z scrub and swiping to the X then double-tapping work.
- [x] If the launch mode changes with VoiceOver, a widget test pins the
      mode chosen for each case. Not applicable: the launch mode does not
      change, because no app change was needed.

## Work Log

### 2026-09-24 - Filed from build 14's device check

### 2026-09-24 - Device checks done: VoiceOver users can get out; no app change

The owner tested build 14 with VoiceOver on:
- **Check 1 (swipe navigation): passes.** Touching the X selects the URL,
  but one swipe right from the URL moves focus to the close button, and a
  double-tap closes the browser. Swiping is how VoiceOver users normally
  move around, so this is an ordinary path.
- **Check 2 (two-finger Z scrub): passes.** It closes the browser, the
  standard VoiceOver "go back".
- **Check 3 (`showTitle`): not run.** It needs a new build and mattered only
  if 1 and 2 failed.

The remaining problem is that the X's touch target overlaps the URL bar's in
Apple's SFSafariViewController. The app can't change that: `url_launcher`
exposes only `showTitle`. Switching VoiceOver users to Safari itself
(`externalApplication`) would give up the in-app browser for a gap that two
standard gestures already cover, so it was not done. If it's wanted, report
the overlap to Apple through Feedback Assistant as an SFSafariViewController
accessibility bug.
