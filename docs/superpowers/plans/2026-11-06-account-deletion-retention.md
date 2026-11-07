# Account Deletion and Retention Implementation Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users can delete their own account in the app, on the web, and signed out at `/delete-account`. A resumable job erases everything the Privacy Policy says it erases. Logs are pruned at 90 days.

**Architecture:**

- **Request.** Every path ends in `request_account_deletion(user, reason)`. It deactivates the user, revokes their tokens, writes a `DeletedAccount` row (status `pending`) and queues a Celery task.
- **Erasure.** The task runs idempotent steps in order:
  1. Django data
  2. forum
  3. email and logs
  4. Firestore
  5. Firebase Auth
  6. the "done" email

  It records each finished step on the row, so a retry resumes where it stopped.
- **Nightly prune.** A Celery beat task does three jobs: the 90-day retention, posts held under open reports, and orphaned Firebase logins.

**Tech Stack:** Django/DRF, Celery (worker with embedded beat), firebase_admin (Auth + Firestore), React 19, Flutter + Riverpod 3 + firebase_auth.

**Spec:** `docs/superpowers/specs/2026-11-06-legal-policies-and-account-deletion-design.md`. Plan B covers sections B1 and B2, decision 12, and the deletion parts of "Settled after the builder check". **Build after Plan A has merged:** Task 1 edits the account-creating paths that Plan A changed.

## Global Constraints

- **No grace period.** Deletion starts when it is confirmed. The user is told "Your account is being deleted. You'll get an email when it's done." and gets a "done" email.
- **Erased:**
  - the account, profile and avatar;
  - garden data;
  - scans and their photos;
  - Firestore `users/{uid}`, recursively, then Firebase Auth `delete_user(uid)` **last**;
  - push tokens (`PushDevice`, `PushSubscription`, `ForumProfile.fcm_token`);
  - `BlogNewsletter` by email, case-insensitive;
  - blocks, mutes, bookmarks, subscriptions and reads;
  - onboarding;
  - the user's `EmailNotification` rows;
  - the user's `BlogPostView` rows;
  - auditlog `LogEntry` rows whose object is this user;
  - blog comments.
- **Forum posts.**
  - The body is emptied and the post's Wagtail revisions are deleted. Wagtail images with `uploaded_by_user` = this user are deleted.
  - The author becomes NULL, which already renders as `[deleted]`.
  - Topics the user started keep their place. Their title becomes `[deleted]`, and their revisions are deleted.
  - A post with an open `Report` (`status="open"`) is **held**. It keeps its body, gets `erase_after = now + 30 days`, and the nightly prune erases it once no open report remains or `erase_after` has passed.
- **DMs.** The other members keep the thread. The deleted user's messages stay and show `[deleted]` as the sender. Reports the user filed stay, with the reporter NULL.
- **Kept.**
  - `DeletedAccount` holds `email_hash` (the same normalisation and SHA-256 as `EmailSuppression.address_hash`), `deleted_at`, `reason` and `policy_version`. The plain email and the Firebase uid are cleared once the job is done.
  - `EmailSuppression` is untouched.
  - Text other users quoted, and @mentions, stay in their posts.
- **Reasons:** `self`, `staff`, `abuse`, `under_13`. A sign-up whose email hash matches a `DeletedAccount` with reason `abuse` or `under_13` is refused with HTTP 403 `{"error": "This email address can't be used to create an account.", "code": "signup_blocked"}`.
- **Retention:** `BlogPostView`, `EmailNotification` and auditlog `LogEntry` older than **90 days** are deleted nightly. `DeletedAccount` and `Report` are never pruned.
- **Orphaned Firebase logins:** a Firebase user older than **7 days** whose uid has no `User` row is deleted nightly. A run that would delete more than **50** aborts, alerts through Sentry, and deletes nothing.
- **Mobile re-auth:** the client calls `reauthenticateWithCredential`, then sends a fresh Firebase ID token. The server verifies it, with revocation checked, and requires `auth_time` within **300 s** and `uid == user.firebase_uid`.
- **Web, and signed out:** a single-use emailed link valid for **3600 s**. The response is always the same, whether or not the address has an account.
- **Ruling (not in the spec): staff and blog authors cannot self-delete.** `BlogPostPage.author` and `BlogAuthorPage.author` are `on_delete=PROTECT`, so their accounts cannot be removed. Such a request answers 409 `{"code": "contact_support", "error": "This account can't be deleted from the app. Email [[CONTACT_EMAIL]] and we'll help."}` and changes nothing.
- **Ruling (not in the spec): the web uses the emailed link for every signed-in user, instead of a password prompt.** There is no password re-entry endpoint today, and Google users have no password. One flow serves the signed-in web user and `/delete-account`.
- **Ruling (not in the spec): legacy `UserMessage` (users app) keeps CASCADE.** It is the retired DM model, and both sides of it go.
- Config goes in the app's `constants.py`. Log prefixes are bracketed (`[ACCOUNT DELETE]`, `[SECURITY]`). Email addresses are redacted in logs (`redact_email`). The cheap-worker scripts are never used on this plan: it is auth and security code.
- Commits end with the session's attribution lines and use `SKIP_KIMI_REVIEW=1`. Flutter commands need the sandbox disabled.

## Review Focus

1. **A user in a group DM and a 1:1 DM deletes their account.** The other members still see both threads, with the deleted user's messages from `[deleted]`. Test: T2 `test_conversations_survive_participant_deletion`.
2. **Deletion is requested twice, or from two devices.** There is one `DeletedAccount` row, one task run, and one done email. Test: T5 `test_second_request_reuses_pending_deletion`.
3. **The Firestore step succeeds, then `delete_user` raises.** The retry skips Firestore, deletes the Auth user, and sends the email once. Test: T5 `test_retry_resumes_after_auth_failure`.
4. **A signed-out deletion request for an email with no account.** The response is identical, no email is sent, and nothing is written. Test: T6 `test_request_unknown_email_same_response`.
5. **A staff user or blog author asks to delete.** The answer is 409 `contact_support`, and the user is still active. Test: T6 `test_blog_author_refused`.
6. **The orphan prune would delete 51 Firebase users.** It aborts and deletes none. Test: T8 `test_orphan_prune_aborts_over_cap`.

---

### Task 1: DeletedAccount record and blocked sign-up

**Files:**

- Modify: `backend/apps/users/models.py`, `backend/apps/users/constants.py`
- Create: `backend/apps/users/deletion.py`
- Create: a migration (`makemigrations users -n deleted_account`)
- Modify: `backend/apps/users/views.py` (`register`), `backend/apps/users/firebase_auth_views.py` (`get_or_create_user_from_firebase`, at the create point, beside Plan A's `ConsentRequired`), `backend/apps/users/oauth_views.py` (`_find_or_create_user`, at the same point)
- Test: `backend/apps/users/tests/test_deleted_account.py`

**Interfaces:**

- Produces:
  - `class DeletedAccount(models.Model)` with these fields:
    - `user_id: BigIntegerField(null=True, unique=True)`, the old pk. It is not an FK.
    - `email: CharField(blank=True)`, cleared on done.
    - `email_hash: CharField(max_length=64, db_index=True)`
    - `firebase_uid: CharField(blank=True)`, cleared on done.
    - `reason: CharField(choices=self|staff|abuse|under_13)`
    - `policy_version: CharField(blank=True)`
    - `status: CharField(choices=pending|done, default=pending)`
    - `steps_done: JSONField(default=list)`
    - `requested_at: auto_now_add`
    - `deleted_at: DateTimeField(null=True)`
  - `def email_hash(address: str) -> str`. It reuses the normaliser that `EmailSuppression` uses (find it in `apps/core`) and does not copy it.
  - `def is_signup_blocked(address: str) -> bool`
  - `class SignupBlocked(Exception)`
  - `def signup_blocked_response() -> Response`, the 403 from Global Constraints.
  - The three create paths raise or return the 403 before creating anything. The OAuth callback redirects to its frontend URL with `?error=signup_blocked`.
  - **Order:** the `signup_blocked` check runs *before* Plan A's consent check at each create path, so a blocked address is never asked to accept the terms. Add a test per path: a blocked email with no `accepted_terms` gets 403 `signup_blocked`, not 428.
  - Add a message for `signup_blocked` to `web/src/pages/auth/GoogleCallbackPage.tsx`'s error map: "This email address can't be used to create an account."

- [ ] **Step 1: Write the failing tests.**
  - `email_hash` equals `EmailSuppression`'s hash for `" Foo@Example.com "`.
  - `is_signup_blocked`:
    - true for reason `abuse` and for `under_13`;
    - false for `self` and for `staff`.
  - `register`, the token exchange (new uid) and the OAuth callback (new user) each refuse a blocked email with 403 `signup_blocked`, or the redirect `?error=signup_blocked`, and create no `User`.
  - An existing user whose email is on the list still signs in. That cannot normally happen, but the check applies only on create.
- [ ] **Step 2:** Run `cd backend && venv/bin/pytest apps/users/tests/test_deleted_account.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Run `makemigrations`.
- [ ] **Step 4:** Run `venv/bin/pytest apps/users -q` and `venv/bin/python manage.py makemigrations --check --dry-run`. Expected: PASS, and "No changes detected".
- [ ] **Step 5:** Commit: `feat(users): deleted-account record and blocked re-sign-up`.

### Task 2: Schema changes deletion needs (forum and forum_host)

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/messages.py`. `Conversation.participant_a`, `participant_b` and `Message.sender` change to `null=True, on_delete=SET_NULL`.
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/reports.py`. `Report.reporter` changes to `null=True, SET_NULL`.
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/posts.py`. Add `erase_after = DateTimeField(null=True, blank=True, db_index=True)`.
- Modify: `backend/apps/forum_host/models.py`. `RagAnswerReport.reporter` changes to `null=True, SET_NULL`.
- Modify: the DM and report serializers or views that read `sender`, `participant_*` or `reporter`. Find them with `grep -rn "\.sender\b\|participant_a\|participant_b\|\.reporter\b" backend/packages/wagtail_forum/wagtail_forum backend/apps/forum_host --include=*.py | grep -v tests`. A NULL value renders through the existing `_deleted_author()` sentinel (`api/serializers.py:161`) and never raises `AttributeError`.
- Check: any `UniqueConstraint` or `CheckConstraint` on `(participant_a, participant_b)`. Keep it valid when one side is NULL, and say how in the report.
- Already verified, no change needed: `Topic.author`, `Topic.last_post_author`, `Post.author` and `Conversation.created_by` are SET_NULL. `ConversationParticipant.user` stays CASCADE (only the deleted user's own membership row goes; the group survives). Before migrating, list every other FK to the user model in `wagtail_forum` and `forum_host` with `on_delete=CASCADE` and confirm each removes only the deleted user's own rows, never another user's content; report the list.
- Create: migrations in both apps.
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/test_account_deletion_schema.py`

**Interfaces:**

- Produces: `Post.erase_after`. Deleting a `User` no longer deletes conversations, messages or reports they are part of.

- [ ] **Step 1: Write the failing tests.**
  - `test_conversations_survive_participant_deletion`:
    - Set up a 1:1 conversation between A and B, and a group conversation of A, B and C, each with messages from A and B.
    - Delete A.
    - B still lists both conversations through the DM list API, and A's messages are returned with the `[deleted]` sender.
  - `test_reports_survive_reporter_deletion`: a Report filed by A still exists after A is deleted, with reporter NULL. Do the same for `RagAnswerReport`.
  - `test_moderation_queue_renders_null_reporter`: the moderation report list API returns 200 for that report.
- [ ] **Step 2:** Run `venv/bin/pytest packages/wagtail_forum/wagtail_forum/tests/test_account_deletion_schema.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Run `makemigrations wagtail_forum forum_host`.
- [ ] **Step 4:** Run `venv/bin/pytest packages/wagtail_forum apps/forum_host -q`, `venv/bin/python -m mypy`, and `makemigrations --check --dry-run`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(forum): conversations, messages and reports survive a deleted user`.

### Task 3: Erasing Django data (steps 1–3)

**Files:**

- Modify: `backend/apps/users/deletion.py`
- Test: `backend/apps/users/tests/test_account_erasure.py`

**Interfaces:**

- Consumes: T1 `DeletedAccount`, T2 `Post.erase_after`.
- Produces:
  - `def erase_django_data(record: DeletedAccount) -> None`. This is steps `django`, `forum` and `email`, each appended to `record.steps_done` and saved after it finishes, and each skipped if already listed. It runs in this order:
    1. **`forum`**, while the user row still exists:
       - each authored post: if it has an open report, set `erase_after = now + FORUM_HELD_POST_DAYS (30)`; otherwise call `erase_post(post)`;
       - each authored topic: title becomes `"[deleted]"` and its revisions are deleted;
       - Wagtail images with `uploaded_by_user` = this user are deleted, **except** images referenced by a held post's body (moderators reviewing the report must still see them). `erase_post` removes those later;
       - notifications whose `actor` is this user are deleted.
    2. **`email`:**
       - delete the user's `EmailNotification` rows (by FK, and by `recipient_email__iexact`);
       - delete the user's `BlogPostView` rows;
       - delete `BlogNewsletter` rows with `email__iexact`;
       - delete auditlog `LogEntry` rows for the User content type with `object_pk = str(user_id)`;
       - delete `OutstandingToken` rows, the same way `expire_unverified_accounts` does.
    3. **`django`:**
       - delete the avatar files with `delete_avatar_files_on_commit`;
       - clear `ForumProfile.fcm_token`;
       - `user.delete()`. The cascades remove the rest, and the scan photos go through the existing on-commit signal.
    - If the `User` row is already gone, the remaining Django steps are marked done.
  - `def erase_post(post: Post) -> None`:
    - deletes the Wagtail images its body references that no other post's body references (this is how a held post's images go when it is released);
    - `body = []`;
    - `author = None`;
    - `erase_after = None`;
    - the post's `wagtailcore.Revision` rows are deleted;
    - the post is saved without creating a new revision.

- [ ] **Step 1: Write the failing tests.**
  - `test_erasure_leaves_no_identifying_rows`. Build a user who has all of the following:
    - avatar, garden bed and plant, ScanJob with a photo;
    - forum post with an image, topic, DM, report filed;
    - newsletter row, EmailNotification, BlogPostView with an IP;
    - PushDevice, PushSubscription, OnboardingAnalytics, an auditlog entry.

    Run `erase_django_data`, then assert:
    - no `User` row remains;
    - a search of every model's text and char fields finds neither the email nor the username, except in `DeletedAccount.email` (pending), `EmailSuppression` (hash only), and other users' post bodies (quotes).

    Write the search as a helper that walks `apps.get_models()`.
  - `test_post_with_open_report_is_held`: `erase_after` is set, the body is still intact and its image still exists. The user is still deleted and the author is NULL.
  - `test_erase_post_deletes_its_images`: after `erase_post` on the released post, its image is gone; an image another post also references is kept.
  - `test_erase_post_removes_body_and_revisions`.
  - `test_topic_title_becomes_deleted_and_replies_remain`: another user's reply still has its body.
  - `test_steps_are_idempotent`: running it twice raises nothing, and `steps_done == ["forum", "email", "django"]`.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_account_erasure.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Put `FORUM_HELD_POST_DAYS = 30` in `apps/users/constants.py`.
- [ ] **Step 4:** Run the same pytest, plus `venv/bin/pytest apps/users packages/wagtail_forum -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(users): erase a deleted account's Django and forum data`.

### Task 4: Erasing Firebase data (steps 4–5)

**Files:**

- Modify: `backend/apps/users/deletion.py`, and `backend/apps/core/firebase_config.py` if a helper is needed
- Test: `backend/apps/users/tests/test_firebase_erasure.py`

**Interfaces:**

- Consumes: `apps.core.firebase_config.get_firestore_client()` and `initialize_firebase()`.
- Produces: `def erase_firebase_data(record: DeletedAccount) -> None`. It runs two steps, recorded the same way as in T3:
  - **`firestore`:** `client.recursive_delete(client.collection("users").document(uid))`.
  - **`firebase_auth`:** `firebase_admin.auth.delete_user(uid)`. `UserNotFoundError` counts as done.
  - With no `firebase_uid`, both steps are marked done without any call.
  - When Firebase is not configured (no credentials), it raises a clear `RuntimeError`, so the task retries and alerts instead of silently passing.

- [ ] **Step 1:** Look for other writers of the extra Firestore collections. Run `grep -rn "plant_identifications\|user_plants\|disease_diagnoses\|user_preferences\|sync_queue" firebase plant_community_mobile/lib functions --include=*.ts --include=*.js --include=*.dart 2>/dev/null | grep -v node_modules`. If anything writes them, also delete those documents by their user-id field and add a test for it. If nothing does, say so in the report.
- [ ] **Step 2: Write the failing tests,** with mocks for the Firestore client and `firebase_admin.auth`.
  - It calls `recursive_delete` on `users/<uid>` and then `delete_user(<uid>)`, in that order.
  - `UserNotFoundError` counts as done.
  - With no uid, neither is called.
  - When the Firestore step is already in `steps_done`, it is not called again.
  - When unconfigured, it raises `RuntimeError`.
- [ ] **Step 3:** Run `venv/bin/pytest apps/users/tests/test_firebase_erasure.py -q`. Expected: FAIL.
- [ ] **Step 4:** Implement, then run the same pytest. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(users): erase a deleted account's Firestore data and Firebase login`.

### Task 5: Requesting deletion and the Celery job

**Files:**

- Modify: `backend/apps/users/deletion.py`, `backend/apps/users/tasks.py`
- Create: `backend/templates/emails/account_deleted.html` and `account_deleted.txt` (extend `emails/base.html`)
- Test: `backend/apps/users/tests/test_account_deletion_job.py`

**Interfaces:**

- Consumes: T1, T3 and T4.
- Produces:
  - `def request_account_deletion(user: User, reason: str) -> DeletedAccount`.
    - Inside one transaction with `select_for_update` on the user, it returns the existing pending row if there is one.
    - Otherwise it does the following:
      - sets `is_active=False`;
      - blacklists every outstanding refresh token;
      - creates the `DeletedAccount` with the plain email, its hash, the uid, the reason, and `policy_version_accepted or ""`;
      - queues `delete_account_task.delay(record.pk)` with `transaction.on_commit`.
    - It raises `DeletionRefused` for `is_staff` users and for authors of `BlogPostPage` or `BlogAuthorPage`.
  - `@shared_task(bind=True, max_retries=8, retry_backoff=True, retry_backoff_max=3600)` `delete_account_task(self, record_id: int)`. It runs these steps, then a `notified` step:
    1. `erase_django_data`
    2. `erase_firebase_data`
    3. send the done email with `send_transactional_email` (the `deliver_provider_linked_notice` pattern in `apps/users/account_links.py`)
    4. set `status="done"` and `deleted_at`, and clear `email` and `firebase_uid`

    On the last retry it calls `sentry_sdk.capture_exception` and logs `[ACCOUNT DELETE]` with the record id only.
  - Email copy:
    - Subject: "Your Houseplant MD account has been deleted".
    - Body: "Your account and its data have been deleted, as described in our Privacy Policy. If you didn't ask for this, reply to this email."

- [ ] **Step 1: Write the failing tests.** Run Celery eagerly or call the task directly.
  - `test_request_deactivates_and_queues`: the user is inactive, the tokens are blacklisted, the record is pending, and the task is queued once.
  - `test_second_request_reuses_pending_deletion`: the same row comes back and only one task is queued.
  - `test_job_completes_and_emails_once`: the status is done, `email == ""`, and exactly one mail is in `mail.outbox` with the subject.
  - `test_retry_resumes_after_auth_failure`: the first run has `delete_user` raise. On the second run, `recursive_delete` is called once in total, `delete_user` succeeds, and exactly one mail is sent.
  - `test_staff_and_blog_author_refused`: `DeletionRefused`, and the user stays active.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_account_deletion_job.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same pytest, plus `venv/bin/pytest apps/users -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(users): account deletion request and resumable erase job`.

### Task 6: Deletion endpoints

**Files:**

- Create: `backend/apps/users/deletion_views.py`
- Modify: `backend/apps/users/urls.py`, `backend/apps/users/constants.py`
- Create: `backend/templates/emails/account_delete_confirm.html` and `.txt`
- Test: `backend/apps/users/tests/test_account_deletion_api.py`

**Interfaces:**

- Consumes: T5 `request_account_deletion`, `DeletionRefused`.
- Produces (under the users urls, `/api/v1/auth/`):
  - **`POST account/delete/`.** JWT required, body `{"firebase_token": str}`. It verifies the token with `check_revoked=True` and requires `uid == request.user.firebase_uid` and `now - auth_time <= ACCOUNT_DELETE_REAUTH_MAX_AGE_SECONDS (300)`.
    - Otherwise: 403 `{"code": "reauth_required"}`.
    - On success: 202 `{"status": "scheduled"}`.
    - `DeletionRefused`: 409 `contact_support`, with the copy from Global Constraints.
  - **`POST account/delete/request/`.** Public, CSRF-exempt like `register`. Body `{"email": str}`.
    - Rate limits: `ACCOUNT_DELETE_REQUEST_RATE_IP = "5/h"` and `ACCOUNT_DELETE_REQUEST_RATE_EMAIL = "3/h"`. A 429 goes through the project's ratelimit handler.
    - It always answers 200 `{"status": "sent"}`.
    - If an active account matches, it emails a link to `{SITE_URL}/delete-account/confirm?token=<t>`. The email is sent from a Celery task (`.delay()`), so the response time doesn't reveal whether the address has an account.
    - The token is `signing.dumps({"u": pk, "n": nonce}, salt="account-delete")`. The nonce is stored in the cache under `account-delete:<pk>` with `ACCOUNT_DELETE_LINK_TTL_SECONDS = 3600`.
  - **`POST account/delete/confirm/`.** Public. Body `{"token": str}`.
    - It verifies the signature, `max_age=3600`, and that the cache nonce matches. It deletes the nonce first, so the token is single-use.
    - Bad, expired or used token: 400 `{"code": "link_invalid", "error": "This link has expired or was already used. Request a new one."}`.
    - Valid token: `request_account_deletion(user, "self")`, then 202. It clears the JWT cookies if the caller had them.
    - `DeletionRefused`: 409.
  - Every view carries `@extend_schema`, and an `@api_view` with `permission_classes` set the way `register` does it.

- [ ] **Step 1: Write the failing tests.**
  - Mobile:
    - a fresh token gives 202;
    - `auth_time` 301 s old gives 403 `reauth_required`;
    - another user's uid gives 403;
    - no JWT gives 401.
  - `test_request_unknown_email_same_response`: the body and status are identical to a known address, `mail.outbox` is empty, and no cache key is set.
  - `test_request_known_email_sends_link`.
  - `test_confirm_valid_token_schedules_and_single_use`: the second use gives 400 `link_invalid`.
  - `test_confirm_expired_token`: freeze time to 3601 s, then expect 400.
  - `test_blog_author_refused`: 409 `contact_support`, and the user stays active.
  - `test_request_rate_limited`: the sixth request from one IP within an hour gives 429.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_account_deletion_api.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same pytest, plus `venv/bin/pytest apps/users -q` and `venv/bin/python manage.py spectacular --validate --fail-on-warn > /dev/null`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(users): account deletion endpoints with re-auth and emailed link`.

### Task 7: Staff deletion in the admin

**Files:**

- Modify: `backend/apps/users/admin.py`, and the Wagtail user admin if users are managed at `/cms/`. Check both and cover every place a staff member can delete a user.
- Test: `backend/apps/users/tests/test_admin_account_deletion.py`

**Interfaces:**

- Consumes: T5 `request_account_deletion`.
- Produces:
  - Admin actions "Delete account (staff)", "Delete account (abuse — blocks re-sign-up)" and "Delete account (under 13 — blocks re-sign-up)". Each calls `request_account_deletion(user, reason)` per selected user and reports the count.
  - The default delete is disabled for `User` (`has_delete_permission` returns False, and the bulk delete action is removed), so staff cannot bypass the erase job.
  - **`DeletedAccount` admin, read-only**, so a stuck deletion is visible: list `id`, `reason`, `status`, `steps_done`, `requested_at`, `deleted_at`, filterable by `status`. No add, change or delete. The plain `email` is not shown in the list. One action, "Retry erase", re-queues `delete_account_task` for each selected `pending` row.

- [ ] **Step 1: Write the failing tests.**
  - The abuse action creates a `DeletedAccount` with reason `abuse`, and `is_signup_blocked(email)` becomes true.
  - The admin delete view for a user returns 403, or the delete action is not offered.
  - "Retry erase" on a pending row queues the task once; on a done row it queues nothing.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_admin_account_deletion.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same pytest. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(users): staff account deletion runs the erase job`.

### Task 8: Nightly prune (retention, held posts, orphaned Firebase logins)

**Files:**

- Create: `backend/apps/users/retention.py`
- Modify: `backend/apps/users/tasks.py`, `backend/plant_community_backend/settings.py` (`CELERY_BEAT_SCHEDULE`, entry `privacy-retention-prune` at 03:50), `backend/apps/users/constants.py`
- Test: `backend/apps/users/tests/test_retention.py`

**Interfaces:**

- Consumes: T3 `erase_post`, and `firebase_admin.auth.list_users`.
- Produces:
  - `def prune_retention(now: datetime | None = None) -> dict[str, int]`. It deletes `BlogPostView`, `EmailNotification` and auditlog `LogEntry` rows older than `PRIVACY_RETENTION_DAYS = 90`, in batches. Copy `_delete_in_batches` from `apps.core.tasks`.
  - `def release_held_posts(now: datetime | None = None) -> int`. It calls `erase_post` on each post where `erase_after` is set and either `erase_after <= now` or there is no Report with `status="open"`.
  - `def prune_orphan_firebase_users(now: datetime | None = None, dry_run: bool = False) -> int`.
    - It pages `auth.list_users()` and collects users with `user_metadata.creation_timestamp` older than `ORPHAN_FIREBASE_USER_DAYS = 7` whose uid matches no `User.firebase_uid` and no pending `DeletedAccount.firebase_uid`, **and** whose email (case-insensitive) matches no `User.email`. A uid mismatch alone is not enough: an account whose uid was never stored must not lose its login.
    - If there are more than `ORPHAN_FIREBASE_DELETE_CAP = 50`, it logs `[SECURITY]`, calls `sentry_sdk.capture_message`, and returns 0 without deleting.
    - **Ships log-only.** Unless `settings.ORPHAN_FIREBASE_PRUNE_ENABLED` is `True` (env var, default `False`), it behaves as `dry_run=True`: it logs the count and the uids (never emails) and deletes nothing. Add the variable to the env table in root `CLAUDE.md` and declare it `preserve()` in `.railway/railway.ts` only if that file declares the others this way; otherwise leave Railway untouched and say so.
    - Otherwise it deletes each one (one by one, not in a batch) and returns the count.
    - When Firebase is unconfigured, it returns 0 and logs.
  - `@shared_task privacy_retention_prune()` calls all three and logs the counts.
  - A management command, `manage.py privacy_prune --dry-run`, does the same and prints the counts.

- [ ] **Step 1: Write the failing tests.**
  - Retention: rows at 91 days are deleted, rows at 89 days are kept, and `DeletedAccount` and `Report` are untouched.
  - Held posts:
    - a held post with its report closed is erased;
    - one with an open report and `erase_after` in the future is kept;
    - one past `erase_after` is erased even though its report is open.
  - Orphans, with a mocked `list_users`:
    - an 8-day-old orphan is deleted;
    - an 8-day-old uid that has a `User` is kept;
    - a 6-day-old orphan is kept;
    - `test_orphan_prune_aborts_over_cap`: 51 orphans give 0 deleted, and Sentry is called;
    - an 8-day-old Firebase user with an unmatched uid but an email matching a `User` is kept;
    - with `ORPHAN_FIREBASE_PRUNE_ENABLED=False` (the default), an 8-day-old orphan is logged, not deleted;
    - dry-run deletes nothing.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_retention.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same pytest, plus `venv/bin/python manage.py privacy_prune --dry-run` against the dev DB. Expected: PASS, and three count lines printed.
- [ ] **Step 5:** Commit: `feat(users): nightly 90-day retention, held-post release and orphan login prune`.

### Task 9: Web deletion screens

**Files:**

- Create: `web/src/services/accountDeletionService.ts`, `web/src/pages/account/DeleteAccountPage.tsx` (`/delete-account`), `web/src/pages/account/ConfirmDeleteAccountPage.tsx` (`/delete-account/confirm`), `web/src/components/settings/DeleteAccountSection.tsx`, and a test for each
- Modify: `web/src/App.tsx` (both routes public), `web/src/pages/SettingsPage.tsx` (the section goes last, after `MyForumImages`), and the footer (a "Delete account" link beside Privacy and Terms)

**Interfaces:**

- Consumes: T6 `request/` and `confirm/`.
- Produces:
  - `requestAccountDeletion(email: string): Promise<void>` and `confirmAccountDeletion(token: string): Promise<'scheduled'>`. The confirm throws a typed error carrying `code` (`link_invalid`, `contact_support`).
  - **Settings section.**
    - Heading "Delete account".
    - One line: "This permanently deletes your account, plants, garden, scans and forum posts. It can't be undone."
    - A danger button "Email me a deletion link". It opens a `ConfirmDialog`; on confirm it requests deletion for the signed-in email and shows "Check your email for a link to finish deleting your account."
  - **`/delete-account`.**
    - The same explanation, plus "Deleting your account doesn't cancel a Premium subscription. Cancel it in the App Store or Google Play."
    - An email field and a "Send deletion link" button.
    - It always shows "If an account exists for that address, we've sent a link."
  - **`/delete-account/confirm`.**
    - It lists what will be deleted.
    - A danger button "Delete my account".
    - On 202 it shows "Your account is being deleted. You'll get an email when it's done.", clears the auth context and logs out locally.
    - On `link_invalid` it shows the server's message and a link to `/delete-account`.
    - On `contact_support` it shows the server's message.

- [ ] **Step 1: Write the failing tests** for each component. Cover:
  - the copy above;
  - the API is called with the right body;
  - each error branch renders its message;
  - the confirm page never auto-submits, so the button must be pressed.
- [ ] **Step 2:** Run `cd web && npx vitest run src/pages/account src/components/settings/DeleteAccountSection`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same vitest, plus `npm run type-check && npm run lint`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(web): delete-account settings section and public deletion pages`.

### Task 10: Mobile deletion screen

**Files:**

- Create: `plant_community_mobile/lib/features/settings/delete_account_screen.dart`, `plant_community_mobile/lib/services/account_deletion_service.dart`
- Modify: `plant_community_mobile/lib/features/settings/settings_screen.dart` (a new `ACCOUNT` section before `ABOUT`, with a "Delete account" tile), `plant_community_mobile/lib/core/routing/app_router.dart` (route `/settings/delete-account`; regenerate with build_runner), `plant_community_mobile/lib/services/auth_service.dart` (`Future<String> freshIdTokenAfterReauth({String? password})`)
- Test: `plant_community_mobile/test/features/settings/delete_account_screen_test.dart`, `plant_community_mobile/test/services/account_deletion_service_test.dart`

**Interfaces:**

- Consumes: T6 `POST account/delete/`.
- Produces:
  - **`freshIdTokenAfterReauth`.** It picks the credential from `currentUser.providerData`:
    - `password`: `EmailAuthProvider.credential(email, password)`, where the password comes from a dialog on the screen.
    - `google.com`: a fresh Google `authenticate()`, then `GoogleAuthProvider.credential(idToken:)`.

    It then calls `reauthenticateWithCredential` and returns `getIdToken(true)`. If the user cancels or enters a wrong password, it throws `AuthException` with a readable message.
  - **`AccountDeletionService.deleteAccount(String firebaseToken)`.** It posts and maps the response:
    - 202: success.
    - 403 `reauth_required`: "Please confirm it's you again."
    - 409 `contact_support`: the server message.
    - Network failure: "You're offline. Connect and try again."
  - **The screen:**
    - Title "Delete account".
    - Copy: "This permanently deletes your account, saved plants, garden, scans and forum posts. Other people keep their copy of messages you sent them. It can't be undone."
    - "Deleting your account doesn't cancel a Premium subscription. Manage subscriptions in the App Store or Google Play." This links to the platform's subscriptions page.
    - A danger button "Delete my account". Pressing it runs re-auth (the password dialog for password users), then `deleteAccount`, then `signOut()`.
    - A final dialog: "Your account is being deleted. You'll get an email when it's done." On OK, it goes to the login screen.

- [ ] **Step 1: Write the failing tests.**
  - Service: each status maps to its result or message.
  - Screen:
    - the copy is present;
    - the button runs re-auth, then the service, then sign-out, in order (with fakes);
    - a cancelled re-auth leaves the user signed in and shows no error dialog;
    - a 409 shows the server message and does not sign out.
- [ ] **Step 2:** Run `cd plant_community_mobile && flutter test test/features/settings/delete_account_screen_test.dart test/services/account_deletion_service_test.dart`. Expected: FAIL.
- [ ] **Step 3:** Implement, using Canopy tokens, `docs/rules/flutter.md`, and the danger colour for the button.
- [ ] **Step 4:** Run `flutter test` and `flutter analyze`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(mobile): delete account from settings with re-authentication`.

### Task 11: Docs and full verification

**Files:**

- Modify: root `CLAUDE.md`. Add a line: "Never `user.delete()` directly — call `request_account_deletion` (`apps/users/deletion.py`); the admin delete is disabled." Also note the `privacy-retention-prune` beat entry.
- Modify: `backend/apps/users/management/commands/expire_unverified_accounts.py` only if its direct `user.delete()` would now leave Firebase data behind. It skips users with a `firebase_uid`, so most likely it needs no change; say so in the report.

- [ ] **Step 1:** Backend: `cd backend && venv/bin/pytest -q -p no:cacheprovider`, `venv/bin/ruff check .`, `venv/bin/python -m mypy`, `venv/bin/python manage.py check`, `makemigrations --check --dry-run`, and `spectacular --validate --fail-on-warn`. Expected: all clean, with the count recorded.
- [ ] **Step 2:** Web: `cd web && npm run test -- --run && npm run type-check && npm run lint && npm run build`. Expected: clean.
- [ ] **Step 3:** Mobile: `flutter analyze && flutter test`. Expected: clean.
- [ ] **Step 4:** Commit: `docs: account deletion conventions`.

## Owner follow-ups (not tasks)

- Enter `https://houseplant-md.com/delete-account` as the account-deletion URL in Google Play Console (Data safety).
- Deploy order: backend first (migrations), then the web, then a new TestFlight build.
- The orphan Firebase prune ships log-only. After a few nightly runs, read the logged uids (or run `manage.py privacy_prune --dry-run` on prod), confirm none is a real account (check the simtest accounts), then set `ORPHAN_FIREBASE_PRUNE_ENABLED=True` on Railway.
- After a deletion, check the `DeletedAccount` admin for rows stuck in `pending`; "Retry erase" re-queues them.
