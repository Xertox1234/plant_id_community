---
status: pending
priority: p2
issue_id: "707"
tags: [privacy, backend, firebase, web, legal]
dependencies: []
triage: blocked-owner
blocked_on: product decisions on tracking defaults, profile visibility and under-13 deletion
triaged: 2026-11-10
---

# Privacy defaults and data handling left by the 2026-11-10 audit

## Problem

Eight findings from the auth + legal audit concern what is collected or shown
by default and what deletion reaches. Most need a product decision before
code.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md` (rows named below).

- **M8** Tracking is on by default with no opt-out: Sentry replay for 10% of
  web sessions, signed-out ones included (`web/src/config/sentry.ts`), email
  click attribution (`apps/core/email_feedback.py:519-523`), blog views with
  IP and user (`apps/blog/middleware.py:97-126`).
- **M9** `profile_visibility` is enforced nowhere: outside the model, admin
  and audit log it appears once, in the serializer. New accounts default to
  `public`, `show_location=True`, and a public default collection
  (`apps/users/models.py:186-204`, `signup.py:69`).
- **M10** The sign-up block list is an unsalted SHA-256 of the lower-cased
  address: `name+1@…` aliases pass it, anyone with a database copy can test
  addresses against it, and two kinds of row are kept forever
  (`apps/users/deletion.py:65-90`, `apps/core/email_feedback.py:161-165`,
  `retention.py:136-158`).
- **M11** Deleting an under-13 account runs the standard job, which keeps the
  other person's DM copy, quoted text and moderation records
  (`apps/users/admin.py:189-193`).
- **M15** Firebase rules never require a verified email, and the Storage
  rules allow 10 MB image uploads although no client uses Firebase Storage
  (`firebase/storage.rules:6-36`, `firebase/firestore.rules:5-60`).
- **L11** Account deletion has no Firebase Storage step (closes with M15).
- **L13** Access and portability are by email with no procedure or export;
  dead `zip_code` / `latitude` / `longitude` columns on `User`
  (`apps/users/models.py:96-134`).
- **L15** Deletion is not propagated to Sentry, Resend, Plant.id / PlantNet
  or OpenAI.

## Recommended Action

1. M8: set the replay session sample rate to 0 and keep replay on error;
   owner decides on click tracking and blog-view logging.
2. M9: owner decides whether profiles are private by default; then either
   enforce `profile_visibility` in the profile and forum views or remove the
   field. A control that does nothing should not be shown.
3. M10: replace the plain hash with an HMAC keyed by a server secret, and
   normalise `+` aliases before hashing; migrate existing rows by keeping
   both lookups until the old rows age out.
4. M11: owner + lawyer decide what an under-13 deletion must reach.
5. M15: deny all in `storage.rules`; require `email_verified` in Firestore
   rules. Test with the emulator, and deploy when someone can watch the app.
6. L13: drop the dead columns in a migration; write the access-request
   procedure next to the breach runbook (todo 702).
7. L15: list each processor's deletion route in the processor register
   (todo 702).

## Technical Details

- Firebase rules patterns: `firebase/docs/patterns/firestore-rules.md`.
- Migrations and auth code: no kimi tools (owner's standing rule).

## Acceptance Criteria

- [x] Replay records no session without an error (unit test on the config).
- [x] `profile_visibility` either changes what another user can see (test) or
      is gone from the model and serializer.
- [x] The block list matches `name+1@x` after `name@x` was blocked, and holds
      no unkeyed hash (tests).
- [x] Emulator tests show an unverified Firebase user cannot write, and
      Storage refuses every upload.
- [ ] The dead `User` columns are removed by a migration.
- [x] M11 has a dated owner decision in the Work Log.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: product and legal decisions come first; a Firebase
  rules change is live the moment it deploys.

### 2026-11-10 - Replay rate, and a correction to M15

- M8, part: `replaysSessionSampleRate` is 0; replay on error stays. Test
  `records no session unless it hits an error` failed first. The Privacy
  Policy still says "about 10% of sessions" (`privacy.en.md:83,107`, and the
  Spanish file): that sentence changes with the todo 701 revision, because
  policy text needs a version bump.
- M15 correction: "no client uses Firebase Storage" is true of current code
  only. `git log -S firebase_storage -- plant_community_mobile/pubspec.yaml`
  shows it was removed by #1251 (2026-11-05); before that,
  `plant_identification_service.dart` uploaded each identification photo to
  `plant-identifications/{uid}/`. So Storage deny-all needs two owner answers
  first: is any build older than 19 still in use, and may the bucket be
  emptied. L11 closes only when the bucket is empty.
- H6 in the manifest now records the owner's decision (no fallback).

### 2026-11-10 - Owner decisions, and what shipped

Owner decisions (2026-11-10):

- M9: profiles stay public by default. Still open: enforce
  `profile_visibility` or remove it.
- M8: email click attribution and blog-view logging stay on.
- M11: an under-13 deletion reaches whatever the law requires in Canada, the
  US and Mexico. Read as COPPA, 16 CFR 312.10 (the strictest): delete what
  was collected from the child. Not legal advice.
- No build older than 19 is in use, and the Storage bucket may be emptied.

Shipped:

- M11 (this PR): `under_13` erases reported posts at once, deletes the
  messages the child sent, removes their words from `post_quote` blocks in
  other posts, and blanks the detail of reports they filed. Limit: words
  retyped into a plain `quote` block, and a mention of their username in
  someone else's post, are not found.
- M10 (#1295): `address_hash()` is an HMAC-SHA256 keyed by `SECRET_KEY`, with
  `+tag` dropped. No dual lookup (app not live): older rows no longer match.
- M15, Storage half (#1294): every path denied. The bucket held 4 photos and
  was emptied 2026-11-10. **The rules still need `firebase deploy --only
  storage`.** The emulator test was not written.
- L11: closed by the two lines above once the rules are deployed.
- L13 correction: `zip_code` / `latitude` / `longitude` are not dead.
  `garden_calendar/api/views.py` reads them for `near_me` and weather alerts.
  No API writes them, so they hold no data. Not dropped.

Left: M9 enforce-or-remove, Firestore `email_verified` with emulator tests
(M15), the access-request procedure (L13), processor deletion routes (L15,
todo 702).

### 2026-11-10 - M9: the three visibility settings are removed

- `profile_visibility`, `show_email` and `show_location` are gone from the
  model (migration `0024`), serializer, admin and audit log, and from the
  mobile model, service and the "coming soon" tile. Nothing read them.
  Tests in `test_visibility_settings_removed.py` failed first; a build that
  still sends the keys gets 200 and they are ignored.
- Checked before removing: no endpoint returns another user's email or
  `location`. The users-app `UserSerializer` goes only to the signed-in
  user. `first_name` / `last_name` are returned for blog authors and garden
  event organisers; the Privacy Policy should say so (todo 701).
- Not changed: the default "My Plants" collection stays `is_public: True`
  (`signup.py:69`), under the owner's "public by default" decision.
- Lost on deploy: the stored value of those three columns for every account.

### 2026-11-10 - M15: Firestore open only to the owner's verified sign-in

- `firestore.rules` opens one path, `users/{uid}/identified_plants`, to the
  owner with `email_verified`. The user document and five collections no
  client uses are closed. `git log -S` finds none of those five names in any
  version of the app or web code, and account deletion erases `users/<uid>`
  and everything under it.
- `scripts/test_firebase_rules_emulator.py`: 13 emulator tests, Firestore and
  Storage, run in CI by `firebase-rules-emulator.yml`. Against the old rules
  the Firestore tests failed.
- The collection screen tells an unverified account to verify its email, and
  shows a failed read at once instead of after a minute of retries.
- **Not live until deployed:** `firebase deploy --only firestore:rules,storage`
  from `main`, then run the `Firebase rules drift` workflow.

Left in this todo: the access-request procedure (L13) and the processor
deletion routes (L15), both with todo 702.

### 2026-11-10 - L13 and L15: the two procedures are written

- L13: `docs/operations/access-requests.md`. Identity check, what to collect
  from each store, deadlines (20 business days, never past 30 calendar days),
  and the manual steps the policy promises. There is still no export tool.
- L15: `docs/operations/processors.md`. Per processor: what it receives, what
  the deletion job removes, what stays and the route to ask for deletion.
  The job itself is unchanged: it does not call Sentry, Resend, Plant.id,
  PlantNet or OpenAI. Cells the providers' documentation did not answer are
  marked "unsourced".
- Declined: the "dead `User` columns" box. They are read by `near_me` and
  the weather alerts (see the correction above), so no migration drops them.

## Notes

Step 1 (replay rate) needed no decision and is done. Step 5 (Storage
deny-all) turned out to need one: see the Work Log.
