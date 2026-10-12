---
status: completed
priority: p4
issue_id: "587"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Item 7: convert wide-gamut avatars to sRGB with ImageCms before stripping metadata (owner, 2026-10-11)"
---

# Follow-ups from PR #1028 (todos 553, 558, 562, 565, 567)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1028 (avatar EXIF stripping, profile rate limits and account-lockout privacy). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

Note from the run: items 4 and 8 (MPO re-encoded as PNG) were fixed on the PR before it merged (`_REENCODE` maps MPO to JPEG and the re-encode is size-checked; see the dropped list). They stayed only because the curation's pool counting matched each returned phrasing to one stored line (todo 596 item 2). Close them on sight.

## Findings

PR #1028 (todo sweep run 2026-10-11-1448, group g1, todos 553, 558, 562, 565, 567); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/users/avatars.py:61` The thumbnail file is deleted, but imagekit's cached EXISTS state is not (CACHE_TIMEOUT=None in prod). The name comes from the source name and spec hash, so an avatar later stored under a freed name never gets a thumbnail and its URL 404s.
2. **medium** `plant_community_mobile/lib/services/auth_service.dart:782` `_surfaceAccountConflict` awaits `_clearJWT()` before re-checking `_isCurrentExchange.` If the exchange was superseded, the delete still runs and may wipe tokens a newer exchange just stored. Only the state write is guarded.
3. **medium** `backend/apps/users/views.py:404` The new DELETE auth/user/avatar/ endpoint and the throttled update_profile have no @extend_schema, so their 401/429 responses and the {message, user} envelope are missing from OpenAPI (docs/rules/api.md). | also: views.py:379 update_profile (rate-limited, block=True) and delete_avatar have no @extend_schema, so the 429 and the new error envelope are undocumented. views.py has no extend_schema at all.
4. **medium** `backend/apps/users/avatars.py:270` Pillow reports many phone JPEGs (those with an MP extension) as format "MPO", not "JPEG". `_REENCODE.get` falls back to PNG, so the photo is stored as a much larger lossless .png after the 2 MB check. Reproduced: a 2.56 MB MPO .jpg became IMG_0001.png at 5.76 MB. | also: Multi-picture JPEGs (camera photos with a gain map or depth frame) open with Pillow format 'MPO', which is not in `_REENCODE.` They are re-encoded as PNG and renamed .png. A 2 MB photo of up to 4096x4096 becomes a PNG of tens of MB, stored and served as the avatar. Pillow 12.3 reports format MPO for such a file (checked).
5. **medium** `backend/apps/users/views.py:379` update_profile (now rate-limited, block=True) and the new delete_avatar endpoint have no @extend_schema, so the 429 and the new error envelope are undocumented in the OpenAPI schema. views.py has no extend_schema at all.
6. **low** `backend/apps/core/security.py:247` The account_lockout alert (an ERROR log line that Sentry receives) pseudonymizes the username but still carries raw ip_addresses, which are now real client IPs, so the account owner's IPs go to Sentry.
7. **low** `backend/apps/users/avatars.py:90` Rebuilding the image from pixels drops the ICC profile along with EXIF, so wide-gamut photos (iPhone Display P3) are stored untagged and render desaturated or shifted.
8. **low** `backend/apps/users/avatars.py:31` `_REENCODE` has no 'MPO' entry. Pillow reports a phone-camera JPEG that carries MPF data as MPO, so it falls through to PNG and is renamed .png. The stored file can grow to several MB, past the 2 MB cap that validation already enforced on the original.

18 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/users/avatars.py:303 strip_image_metadata re-encodes any format it does not list as PNG with no size check after: a multi-picture JPEG (Pillow 'MPO') or a TIFF/BMP named .jpg becomes a large PNG that gets past MAX_AVATAR_SIZE (2 MB). (fixed on main: origin/main avatars.py:34 maps 'MPO' to JPEG. An unknown format now raises KeyError, which becomes AvatarUnreadableError (no PNG fallback). Lines 118-119 raise AvatarTooLargeError when output > MAX_AVATAR_SIZE.; the refuter agreed: origin/main avatars.py:34 maps MPO->JPEG; line 107 `_REENCODE`[source_format] raises KeyError for unknown formats, caught at 116 as AvatarUnreadableError (no PNG fallback); lines 118-119 raise AvatarTooLargeError when output > MAX_AVATAR_SIZE.)
- medium: backend/apps/users/avatars.py:302 strip_image_metadata decodes with source.load() and re-encodes with no error handling, so a truncated or corrupt file that passed header validation raises OSError and gives a 500 instead of a 400. (fixed on main: origin/main avatars.py:102-117 wraps open/load/convert/save in try and maps OSError, ValueError, KeyError and DecompressionBombError to AvatarUnreadableError, which the serializer turns into a 400.; the refuter agreed: origin/main avatars.py:102-117 wraps open/load/exif_transpose/convert/save in try and maps OSError, ValueError, KeyError, DecompressionBombError to AvatarUnreadableError, which the docstring says the serializer turns into a 400.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1028 (todos 553, 558, 562, 565, 567).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Item 1: `backend/apps/users/avatars.py` now resets imagekit's cached state for each deleted thumbnail (`_forget_thumbnail_state`), so an avatar stored later under the freed name gets a new thumbnail. Tests in `backend/apps/users/tests/test_avatar_privacy.py`.
- Item 2: `_surfaceAccountConflict` in `plant_community_mobile/lib/services/auth_service.dart` re-checks `_isCurrentExchange` before each token delete, so an overtaken refresh no longer deletes a newer exchange's tokens. Test: "todo 587" group in `test/services/auth_service_test.dart`.
- Items 3 and 5: already fixed on main by PR #1040 (`UPDATE_PROFILE_SCHEMA`, `DELETE_AVATAR_SCHEMA` in `backend/apps/users/view_schemas.py`); this run added their 401 and 429 (shared with todo 599). Items 4 and 8: closed on sight, as the todo says (`_REENCODE` maps MPO to JPEG and the re-encode is size-checked).
- Item 6: the account_lockout alert in `backend/apps/core/security.py` sends `log_safe_ip` pseudonyms, not raw IPs. The lockout email still lists the real addresses. Test in `backend/apps/users/tests/test_account_lockout.py`.
- Item 7 (owner decision): `strip_image_metadata` converts an ICC-tagged image to sRGB with `ImageCms` before it strips the metadata. If a profile cannot be applied, the image is stored untagged, as before. Tested with a Display P3 JPEG and a Display P3 PNG with alpha.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest apps/users/tests/test_avatar_privacy.py apps/users/tests/test_account_lockout.py apps/users/tests/test_profile_update.py --create-db -q -p no:cacheprovider && cd plant_community_mobile && flutter test test/services/auth_service_test.dart; echo EXIT=$?'` — evidence `.sweep-evidence/g5/587-ac0.txt` (not committed), last lines:

  ```text
  00:00 +57: todo 587 item 2: a refresh 409 overtaken mid-clear keeps the newer tokens
  00:00 +58: session-expiry exemption signOut's FCM-clear PATCH carries skipSessionExpiryKey
  00:00 +59: session-expiry exemption a real 401 on an exempt request does not trigger the session-expired handler, while an unexempt one does
  00:00 +60: All tests passed!
  EXIT=0
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
