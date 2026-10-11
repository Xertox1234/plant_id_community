---
status: completed
priority: p4
issue_id: "565"
tags: [mobile, backend, follow-ups]
dependencies: []
triage: needs-design
triaged: 2026-10-11
blocked_on: "Owner picks the onboarding fix for old builds (#3), plus the avatar storage policy: delete old files and strip EXIF server-side (#2, #6), and build or decline deleteAvatar (#9)"
owner_decision: "#3: keep the 'profile' step but leave it out of complete (complete = the first 3 steps). #2/#6: delete the old original and its imagekit thumbnail on replace, strip EXIF (GPS included) server-side, and add a per-user throttle on update_profile. #9: build a backend avatar-delete route and a mobile 'Remove photo' action (2026-10-11)"
---

# Follow-ups from PR #999 (todo 455, mobile profile edit)

## Problem

Todo-sweep run 2026-10-11-0053 merged PR #999. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none.
Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #999 (todo sweep run 2026-10-11-0053, group g3, todos 455); follow-ups: verified.

1. **medium** `backend/apps/users/views.py:381` update_profile returns raw serializer.errors on 400 ({"avatar": [...]}). Mobile handleDioException reads only message/detail/error, so every avatar rejection (too small, aspect >10, bad type) and an over-long bio shows as 'Failed to upload photo: Bad Request'.
2. **medium** `backend/apps/users/views.py:372` Mobile uploads avatars via update_profile, which has no throttle, and replacing an avatar never deletes the old file or its imagekit thumbnail. Each 'Change photo' leaves the old photo stored and public at its old URL (R2); a user can fill storage at 2 MB per request. | also: plant_community_mobile/lib/services/user_profile_service.dart:188 uploadAvatar replaces User.avatar, but nothing deletes the previous file or its imagekit thumbnail. Each 'Change photo' leaves the old photo stored and still public at its old URL (R2), which a user replacing a photo would not expect. | Replacing the avatar through the new multipart PATCH leaves the old original and its imagekit thumbnail in storage (ImageField does not delete replaced files). A replaced photo stays publicly reachable at its old URL.
3. **medium** `backend/apps/users/onboarding.py:23` Adding a 4th required 'profile' step: builds from #851 onward skip unknown keys, so users with the 3 known steps done see '3 of 3 done' with nothing to tap, and complete stays false; the card never clears except via Dismiss. | also: Adding a fourth step flips complete=false for users who had already finished the 3-step checklist. Dismissed state is client-set, so a previously completed card may reappear. | Adding a 4th required step means `complete` stays false for users on older app builds, which skip unknown keys. Their card shows '3 of 3 done' with nothing left to tap and never goes away on its own, only by Dismiss. Users who finished 3 steps but whose completion was never recorded also see the card come back. | A 4th required step breaks the checklist contract for app builds already installed. The card skips keys it doesn't know, but the server sets `complete` only when all 4 are done, so an old build (e.g. TestFlight 14) shows '3 of 3 done' with no action and never clears.
4. **medium** `backend/apps/users/serializers.py:196` get_avatar_thumbnail catches bare Exception and logs only the type name, no message or exc_info, so a storage outage or config bug on every GET /auth/user/ is masked as avatar_thumbnail=null; it also hides programming errors. | also: The new except branch has a [PROFILE] log prefix, but the serializer's thumbnail-failure path may lack a test. A test where avatar_thumbnail.url raises, asserting avatar_thumbnail is None and the response is 200, would pin the fallback. | get_avatar_thumbnail catches bare Exception and logs only the type name, with no exc_info. A real storage or config fault on every GET /auth/user/ would be silently masked as avatar_thumbnail=null with almost no diagnostic. | The thumbnail guard uses a blanket `except Exception`. A real storage or config bug would show up only as a warning with the exception type, and the client would get a null thumbnail with no signal.
5. **medium** `plant_community_mobile/lib/features/profile/edit_profile_screen.dart:165` Save is enabled whenever profileAsync.value != null, but the bio field is filled only when the AsyncData branch renders. In error/reloading state holding an old value, Save stays live and sends bio "", erasing the user's bio.
6. **medium** `plant_community_mobile/lib/features/profile/edit_profile_screen.dart:48` Avatar upload keeps photo EXIF (image_picker's resize path copies original EXIF incl. GPS). Backend stores and serves the original with no strip, so a home location can be public (blog author avatar_url). Not reproduced; plugin behaviour unverified.
7. **medium** `plant_community_mobile/lib/features/profile/edit_profile_screen.dart:239` Avatar uses NetworkImage rather than CachedNetworkImage, against the checklist rule that network images are cached; the avatar reloads on every visit to this screen.
8. **low** `plant_community_mobile/lib/features/profile/edit_profile_screen.dart:262` TextField maxLength counts grapheme clusters but backend max_length=500 counts code points; a bio with emoji (e.g. ZWJ sequences) can pass the 500 client counter and be refused with a 400 shown as 'Bad Request'.
9. **low** `plant_community_mobile/lib/services/user_profile_service.dart:181` The diff deletes the 'Add deleteAvatar()' TODO without building it. A user who adds a photo from mobile cannot remove it there, only replace it, and the replaced file is kept.

14 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- #1: `update_profile` uses `is_valid(raise_exception=True)`, so a refusal is the API error envelope (`message` such as "avatar: ...", plus `errors`), which mobile and web both read. #2 (owner decision): a replaced avatar's original and imagekit thumbnail are deleted on commit (`backend/apps/users/avatars.py`). `update_profile` has a per-user throttle (`RATE_LIMITS["user_features"]["profile_updates"]`, raised from an unused 10/h to 30/h because the mobile profile screen PATCHes once per notification toggle). Tests cover deletion, a bio-only update keeping the files, and the 429.
- #3 (owner decision): `complete` is the first three steps (`COMPLETION_STEPS`); "profile" stays listed and ticked. #4: the thumbnail fallback logs at ERROR with the traceback (`logger.exception`), tested with `exc_info`. #6 (owner decision): `UserProfileSerializer.validate_avatar` re-encodes the upload from its pixels after `exif_transpose`, so EXIF and GPS are gone and orientation is kept. The test checks the make, the GPS and the upright size.
- #5: Save is enabled only while the form shows the profile, and the bio field is filled before the app bar is built. A test opens the screen during a reload holding an old value. #7: the avatar uses `CachedNetworkImageProvider`. #9 (owner decision): new `DELETE auth/user/avatar/` (`delete_avatar`, throttled, deletes both files), `UserProfileService.deleteAvatar()`, and a confirmed "Remove photo" action on the edit screen, tested on both sides.
- #8 declined: a bio past 500 code points but under 500 graphemes is rare (long emoji sequences). With #1 the server's 400 now reads "bio: Ensure this field has no more than 500 characters." instead of "Bad Request". Code-point counting in the field would need a custom formatter and counter for a cosmetic edge.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/users/tests/test_profile_update.py apps/users/tests/test_onboarding_checklist.py --create-db -q -p no:randomly && cd plant_community_mobile && flutter test test/features/profile/edit_profile_screen_test.dart test/services/user_profile_service_test.dart'` — evidence `.sweep-evidence/g1/565-ac0.txt` (not committed), last lines:

  ```text
  [USER_PROFILE] Profile fetched successfully
  00:01 +29: plant_community_mobile/test/features/profile/edit_profile_screen_test.dart: cancelling the removal sends nothing
  [USER_PROFILE] Fetching current user profile
  [USER_PROFILE] Profile fetched successfully
  00:01 +30: All tests passed!
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
