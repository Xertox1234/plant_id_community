# Scan Keep or Dismiss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop auto-saving finished scans to My Plants. The user keeps one only by tapping Add after seeing the full result. Dismissed or ignored scans (24 h) are erased.

**Architecture:** The server owns the decision. `ScanJob` gains `decision` and `decided_at`, plus keep/dismiss/remove actions, an undecided list and a 15-minute expiry beat. Erasing deletes the photo rows and files and clears `result`, but keeps the row, so the allowance still counts it. The app drops the tracker's Firestore save and adds a short card (My Plants grid, `/scans/<id>`). Firestore is written only on Add.

**Tech Stack:** Django 5 / DRF / drf-spectacular / Celery beat (backend), Flutter + Riverpod 3 + go_router + Firestore (mobile).

**Spec:** `docs/superpowers/specs/2026-11-06-scan-keep-or-dismiss-design.md` (owner-approved 2026-11-06). Mockups: <https://claude.ai/artifact/4Gv7HKquwA4N5E1Mh5YekU>.

## Global Constraints

- Decision values, exactly: `undecided`, `kept`, `dismissed`, `expired`, `removed`. "Erased" means `dismissed`, `expired` or `removed`.
- Decide window: **24 hours** from `finished_at` (`SCAN_DECISION_WINDOW_HOURS = 24` in `constants.py`). The sweep runs every **15 minutes**.
- New-client header on `POST scans/`: `X-Scan-Decisions: 1`. A job created **without** it starts `kept` (old TestFlight builds 17/18 auto-save). A job created with it starts `undecided`.
- **Dismiss and expiry never refund.** `status` and `charged_as` are left untouched. The only refund is `retry_of` on a `degraded` + `undecided` job owned by the caller: erased as `dismissed` and `charged_as=""`.
- Erased jobs answer **404** (`code: not_found`) on retrieve and photos. They never answer 410.
- Failed and cancelled scans: their photos are deleted when the job ends. Fails stay free (todo 698, no change).
- Existing `done`/`degraded` jobs become `kept` in the migration. Existing Firestore plants are untouched.
- Copy, exactly:
  - Buttons: "View", "Dismiss", "Add to My Collection".
  - States: "In My Collection", "This scan was deleted".
  - Countdown: "Deletes in N h", or "Deletes in N min" under an hour.
  - Diagnosis lines: "Identified only" (identify scan), "Health check didn't run" (degraded).
  - Remove action: "Remove".
- Every `@action` keeps `get_permissions()` calling `super()` (CLAUDE.md gotcha 1). Every new endpoint has `@extend_schema` with its error codes, or the `apps/core/tests` OpenAPI guards fail.
- Backend tests: `cd backend && venv/bin/python -m pytest <path> -q`. **An app-scoped run is a false green**: the final task runs `apps/core/tests` and the full suite.

## Review Focus

1. **Add on one phone while the sweep or another phone dismisses.** The second writer must get a clean refusal or no-op, never a kept card without a photo. Pinned in Task 3 (`test_keep_after_dismiss_is_404`, `test_dismiss_after_keep_is_409`).
2. **An old build creating a scan after deploy.** Its plant must keep its photo past 24 h. Pinned in Task 4 (`test_create_without_header_starts_kept`) and Task 5 (`test_expiry_skips_kept`).
3. **Dismissing to win a check back.** `remaining` must not change after a dismiss or an expiry. It does change after a `retry_of`. Pinned in Tasks 3, 4 and 5.
4. **A push opened after the scan was erased.** The app shows "This scan was deleted", not an error screen or a spinner. Pinned in Task 9 (`shows deleted state on 404`).
5. **A countdown that passes zero while My Plants is open.** The card leaves without a refresh. Pinned in Task 10 (`hides an undecided card whose decide_by passed`).

---

### Task 1: Decision fields, migration, serializer

**Files:**

- Modify: `backend/apps/plant_identification/scan_models.py` (ScanJob)
- Modify: `backend/apps/plant_identification/constants.py`
- Create: `backend/apps/plant_identification/migrations/0032_scanjob_decision.py`
- Modify: `backend/apps/plant_identification/api/scan_serializers.py`
- Test: `backend/apps/plant_identification/tests/test_scan_decisions.py` (new), `tests/test_scanjob_decision_migration.py` (new; copy the harness of `test_scanjob_one_active_migration.py`)

**Interfaces:**

- Produces:
  - `ScanJob.DECISION_CHOICES`, `ScanJob.ERASED_DECISIONS = ("dismissed", "expired", "removed")`.
  - Fields `decision = CharField(max_length=16, choices=…, default="undecided")` and `decided_at = DateTimeField(null=True, blank=True)`.
  - Index `scanjob_user_decision_idx` on `(user, decision)`.
  - `constants.SCAN_DECISION_WINDOW_HOURS = 24`.
  - Serializer fields `decision` (read-only choice) and `decide_by` (ISO datetime or null: `finished_at + 24 h` only while `undecided` with `status in ("done","degraded")`).

- [ ] **Step 1: Write failing tests.**
  - `test_decide_by_is_finished_plus_24h_for_undecided_done`: assert `data["decide_by"] == (finished_at + timedelta(hours=24))` in ISO form, and `data["decision"] == "undecided"`.
  - `test_decide_by_null_when_kept_or_failed`.
  - Migration test `test_existing_finished_jobs_become_kept`: before 0032, create jobs with status `done`, `degraded`, `failed`, `pending`. After it, assert done → `kept`, degraded → `kept`, failed → `undecided`, pending → `undecided`.
- [ ] **Step 2: Run them and see them fail.**
  Run: `venv/bin/python -m pytest apps/plant_identification/tests/test_scan_decisions.py apps/plant_identification/tests/test_scanjob_decision_migration.py -q`
  Expected: FAIL (`decision` unknown).
- [ ] **Step 3: Implement.**
  - Add the fields and the index.
  - Migration 0032: AddField and AddIndex, then a `RunPython` with `.filter(status__in=("done","degraded")).update(decision="kept")`. Reverse is a noop. No raw SQL.
  - Add the serializer fields to `Meta.fields`.
- [ ] **Step 4: Run Step 2 again, plus `makemigrations --check`.**
  Run: `venv/bin/python manage.py makemigrations --check --dry-run`
  Expected: PASS, and "No changes detected".
- [ ] **Step 5: Commit** `feat(scan): decision field on scan jobs (keep or dismiss, 1/11)`.

### Task 2: Erase helper; failed and cancelled scans drop their photos

**Files:**

- Modify: `backend/apps/plant_identification/scan_jobs.py`
- Modify: `backend/apps/plant_identification/tasks.py` (`_finalize`)
- Modify: `backend/apps/plant_identification/api/scan_views.py` (`cancel`)
- Test: `tests/test_scan_decisions.py`, `tests/test_scan_task.py`

**Interfaces:**

- Produces:
  - `erase_scan(job_id: int, decision: str, *, from_decisions: tuple[str, ...], refund: bool = False) -> bool` in `scan_jobs.py`.
    - It runs in `transaction.atomic()`.
    - It does a conditional `filter(pk=job_id, decision__in=from_decisions).update(decision=decision, decided_at=now, result=None, **({"charged_as": ""} if refund else {}))`.
    - If the update hit no row, it returns False.
    - Otherwise it deletes `ScanJobImage.objects.filter(job_id=job_id)` one by one (`for img in qs: img.delete()`), so the existing `post_delete` signal removes each file on commit. Then it returns True.
  - `delete_scan_photos(job_ids: Iterable[int]) -> None`: the same per-row delete, with no decision change.

- [ ] **Step 1: Write failing tests.**
  - `test_erase_deletes_rows_files_and_result_keeps_charge`: after `erase_scan(...)`, `ScanJobImage` count is 0, the file is gone from `tmp_path` storage, `result is None`, and `charged_as == "diagnose"`.
  - `test_erase_from_wrong_decision_is_noop` returns False, and the photos are still present.
  - `test_failed_finalize_deletes_photos` (`test_scan_task.py`).
  - `test_cancel_deletes_photos`.
  - `test_expire_stale_deletes_photos`.
- [ ] **Step 2: Run them and see them fail.**
  Run: `venv/bin/python -m pytest apps/plant_identification/tests/test_scan_decisions.py apps/plant_identification/tests/test_scan_task.py -q -k "erase or deletes_photos"`
- [ ] **Step 3: Implement.**
  - `_finalize`: when `status == "failed"` and the update hit, call `delete_scan_photos([job_id])` inside the same atomic block.
  - `cancel`: after a successful update, call `delete_scan_photos([job.pk])`.
  - `expire_stale_jobs`: after its update, call `delete_scan_photos(job_ids)`.
- [ ] **Step 4: Run Step 2 again, plus the whole existing `test_scan_task.py` and `test_scan_api.py`.**
  Expected: PASS.
- [ ] **Step 5: Commit** `feat(scan): erase helper; failed and cancelled scans drop photos (2/11)`.

### Task 3: Keep, dismiss, remove, undecided list; erased jobs 404

**Files:**

- Modify: `backend/apps/plant_identification/api/scan_views.py`
- Modify: the error-schema constants in the same file (follow `ERROR_NOT_ACTIVE`)
- Test: `tests/test_scan_decisions.py`

**Interfaces:**

- Consumes: `erase_scan`, `ScanJob.ERASED_DECISIONS` (Tasks 1–2).
- Produces:
  - `POST scans/{uuid}/keep/` → 200 job JSON.
    - It is a conditional update from `undecided` to `kept`. A job already `kept` is a 200 no-op.
    - Otherwise it answers 409 `code: "not_undecided"`.
    - Only `status in ("done","degraded")` can be kept; anything else gets the same 409.
  - `POST scans/{uuid}/dismiss/` → 204.
    - It calls `erase_scan(pk, "dismissed", from_decisions=("undecided",))`.
    - A job already erased is a 204 no-op.
    - A `kept` job answers 409 `code: "already_kept"`.
  - `POST scans/{uuid}/remove/` → 204.
    - It calls `erase_scan(pk, "removed", from_decisions=("kept","undecided"))`.
    - A job already erased is a 204 no-op.
  - `GET scans/?decision=undecided` → 200 list of job JSON (no pagination; at most 50).
    - It returns the caller's jobs with status `done`/`degraded`, `decision="undecided"` and `finished_at >= now - 24h`, newest `finished_at` first.
    - A missing or other `decision` value answers 400 `code: "invalid"`.
  - `get_queryset()` excludes `decision__in=ERASED_DECISIONS` except for the `dismiss` and `remove` actions, so retrieve and photos 404 on an erased job.

- [ ] **Step 1: Write failing tests.**
  - `test_keep_sets_kept_and_decided_at`.
  - `test_keep_twice_is_200`.
  - `test_keep_after_dismiss_is_404` (an erased job is outside the queryset; assert 404 and the decision is still `dismissed`).
  - `test_dismiss_after_keep_is_409`.
  - `test_dismiss_twice_is_204`.
  - `test_dismiss_leaves_allowance_remaining_unchanged`: the `GET scans/allowance/` `identify.remaining` / `diagnose.remaining` is equal before and after.
  - `test_dismissed_job_retrieve_and_photo_404`.
  - `test_remove_kept_erases_photos`.
  - `test_list_undecided_only_own_recent_finished_newest_first`.
  - `test_list_requires_decision_param`.
  - `test_other_users_job_keep_dismiss_remove_404`.
- [ ] **Step 2: Run them and see them fail.**
  Run: `venv/bin/python -m pytest apps/plant_identification/tests/test_scan_decisions.py -q`
- [ ] **Step 3: Implement** the three `@action(detail=True, methods=["post"])` and a `list(self, request)` with `@extend_schema` (parameter `decision`, enum `["undecided"]`; responses 200/400/404/409). Log `"[SCAN] job=%s %s by user=%s"`.
- [ ] **Step 4: Run Step 2 again, plus the schema check.**
  Run: `venv/bin/python manage.py spectacular --validate --fail-on-warn --file /dev/null`
  Expected: PASS, with no warnings.
- [ ] **Step 5: Commit** `feat(scan): keep, dismiss, remove and undecided list endpoints (3/11)`.

### Task 4: Create: the new-client header and `retry_of`

**Files:**

- Modify: `backend/apps/plant_identification/api/scan_views.py` (`create`)
- Modify: `backend/apps/plant_identification/api/scan_serializers.py` (`ScanJobCreateSerializer`: optional `retry_of` UUID, for the schema)
- Test: `tests/test_scan_decisions.py`

**Interfaces:**

- Produces:
  - In `create`: `decision="undecided" if request.headers.get("X-Scan-Decisions") == "1" else "kept"`, passed to `ScanJob.objects.create`.
  - `retry_of` (optional form field, a UUID).
    - Inside the locked atomic block, after the refusal re-check, it calls `erase_scan(target.pk, "dismissed", from_decisions=("undecided",), refund=True)`.
    - It does this only when the target is `ScanJob.objects.filter(user=user, uuid=retry_of, status="degraded").first()`.
    - A malformed, foreign, non-degraded or already-decided `retry_of` is silently ignored.

- [ ] **Step 1: Write failing tests.**
  - `test_create_with_header_starts_undecided`.
  - `test_create_without_header_starts_kept`.
  - `test_retry_of_degraded_refunds_identify_and_erases`: `identify.remaining` goes up by 1 compared with before the retry. The degraded job ends `dismissed` with `charged_as == ""`, and its photos are gone.
  - `test_retry_of_done_job_ignored`.
  - `test_retry_of_other_users_job_ignored`.
  - `test_retry_of_garbage_ignored_201`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them again, plus the whole `test_scan_api.py`.** Existing create tests send no header, so they now create `kept` jobs. Assert nothing else changed.
- [ ] **Step 5: Commit** `feat(scan): new-client header and Try again refund (4/11)`.

### Task 5: Expiry beat

**Files:**

- Modify: `backend/apps/plant_identification/scan_jobs.py`, `tasks.py`
- Modify: `backend/plant_community_backend/settings.py` (`CELERY_BEAT_SCHEDULE`)
- Test: `tests/test_scan_decisions.py`

**Interfaces:**

- Produces:
  - `expire_undecided_jobs(now: datetime | None = None) -> int` in `scan_jobs.py`.
    - It finds the ids of jobs with status `done`/`degraded`, `decision="undecided"` and `finished_at < now - 24h`.
    - It calls `erase_scan(id, "expired", from_decisions=("undecided",))` for each id and returns the count.
  - Celery task `expire_undecided_scan_jobs` (`ignore_result=True`).
  - Beat entry `"scan-decision-sweep": {"task": "apps.plant_identification.tasks.expire_undecided_scan_jobs", "schedule": crontab(minute="*/15")}`.

- [ ] **Step 1: Write failing tests** (freezegun).
  - `test_expiry_erases_after_24h`: at 24 h 1 s, the job is `expired` and its photos are gone.
  - `test_expiry_keeps_at_23h59`.
  - `test_expiry_skips_kept`.
  - `test_expiry_leaves_allowance_remaining_unchanged`.
  - `test_beat_schedule_has_decision_sweep`: assert the key and the task path in `settings.CELERY_BEAT_SCHEDULE`.
- [ ] **Step 2: Run them, see them fail. Step 3: Implement. Step 4: Run them, see them pass.**
- [ ] **Step 5: Commit** `feat(scan): expire undecided scans after 24 h (5/11)`.

### Task 6: Mobile API and model

**Files:**

- Modify: `plant_community_mobile/lib/features/scan/scan_job_api.dart`
- Test: `plant_community_mobile/test/features/scan/scan_job_api_test.dart`

**Interfaces:**

- Produces:
  - Model additions:
    - `enum ScanDecision { undecided, kept, dismissed, expired, removed }`.
    - `ScanJob.decision` (`ScanDecision`; an unknown or missing value becomes `kept`, so an old server never shows a countdown).
    - `ScanJob.decideBy` (`DateTime?`).
  - API additions:
    - `Future<ScanJob> keep(String id)` → `POST {id}/keep/`.
    - `Future<void> dismiss(String id)` → `POST {id}/dismiss/`.
    - `Future<void> remove(String id)` → `POST {id}/remove/`.
    - `Future<List<ScanJob>> undecided()` → `GET ?decision=undecided`.
  - `create(CaptureResult r, {String? retryOf, …})` sends the header `X-Scan-Decisions: 1` on every create, and the field `retry_of` when it is given.
  - `static String? jobIdFromPhotoUrl(String? url)`: the uuid in `/scans/<uuid>/photos/`, or null.

- [ ] **Step 1: Write failing tests.**
  - The fake Dio adapter asserts the header and the `retry_of` part.
  - `fromJson` maps `decision`/`decide_by`, and a missing decision becomes `kept`.
  - `jobIdFromPhotoUrl` handles a real URL, a Firebase Storage URL (null) and null.
- [ ] **Step 2: Run them and see them fail.**
  Run: `cd plant_community_mobile && flutter test test/features/scan/scan_job_api_test.dart`
- [ ] **Step 3: Implement. Step 4: Run them, see them pass.**
- [ ] **Step 5: Commit** `feat(mobile): scan decision API (6/11)`.

### Task 7: Tracker: no auto-save; Try again sends `retry_of`

**Files:**

- Modify: `plant_community_mobile/lib/features/scan/scan_job_tracker.dart` (+ `.g.dart` via build_runner)
- Test: `test/features/scan/scan_job_tracker_test.dart`, `fake_scan_job_tracker.dart`

**Interfaces:**

- Consumes: `ScanJobApi.create(..., retryOf:)` (Task 6).
- Produces:
  - `_saveThenClear` becomes `_clearAfterFinish(ScanJob job, int gen)`, which only does the stored-id bookkeeping. The tracker no longer reads `firestoreServiceProvider`.
  - `retry()` passes `retryOf: state.job?.id` when the state is `ready` + `degraded`, and null when it is `failed`.
  - `submit(CaptureResult r, {String? retryOf})`.

- [ ] **Step 1: Update the tests.**
  - Replace the existing tests that assert `savePlant` was called on finish with `does not write Firestore when a job finishes` (the fake FirestoreService records zero calls).
  - Add `retry of a degraded job sends retry_of` and `retry after a failure sends no retry_of`.
  - Record in the commit message which existing tests changed, and why.
- [ ] **Step 2: Run them, see them fail. Step 3: Implement. Step 4: Run them, see them pass.**
  Run: `dart run build_runner build --delete-conflicting-outputs && flutter test test/features/scan/`
- [ ] **Step 5: Commit** `feat(mobile): stop auto-saving scans; Try again refunds (7/11)`.

### Task 8: Decisions provider (keep, dismiss, remove, the undecided list)

**Files:**

- Create: `plant_community_mobile/lib/features/scan/scan_decisions.dart`
- Test: `test/features/scan/scan_decisions_test.dart`

**Interfaces:**

- Consumes: Task 6 API; `FirestoreService.savePlant(uid, Plant)` and `deletePlant(uid, plantId)`; `currentUserIdProvider`.
- Produces:
  - `undecidedScansProvider`: `FutureProvider.autoDispose<List<ScanJob>>`, from `undecided()`.
  - `ScanDecisions` (a Riverpod notifier or a plain class behind `scanDecisionsProvider`):
    - `Future<void> keep(ScanJob job)`:
      - It calls the API keep first, then `savePlant`, with the Plant built exactly as today's tracker built it: id = job id, `imageUrl` = `coverPhoto`, timestamp = `createdAt`, `care: const []`.
      - Then it invalidates `undecidedScansProvider`.
    - `Future<void> dismiss(String jobId)`: the API dismiss, then it invalidates the list.
    - `Future<void> removePlant(Plant plant)`:
      - It calls `deletePlant` first.
      - Then, if `jobIdFromPhotoUrl(plant.imageUrl) ?? plant.id` is a scan job id (that is, the URL matched), it calls the API remove.
      - It ignores a 404 from remove.
  - An `ApiException` from the server step propagates unchanged; the UI shows it.

- [ ] **Step 1: Write failing tests.**
  - `keep calls api then firestore in that order`.
  - `keep does not write firestore when api keep fails`.
  - `removePlant on a scan plant calls deletePlant and api remove`.
  - `removePlant on a legacy plant calls only deletePlant`.
  - `dismiss invalidates the undecided list`.
- [ ] **Step 2: Run them, see them fail. Step 3: Implement. Step 4: Run them, see them pass. Step 5: Commit** `feat(mobile): scan decisions provider (8/11)`.

### Task 9: The short card, `/scans/<id>`, and the full result with Add

**Files:**

- Create: `plant_community_mobile/lib/features/scan/widgets/short_scan_card.dart`
- Modify: `lib/features/scan/scan_result_screen.dart`, `lib/features/results/results_screen.dart` (an optional `decisionBar` slot), `lib/core/routing/app_router.dart` (child route `full`: `/scans/:id/full`, plus `scanFullResultPath(id)`)
- Test: `test/features/scan/short_scan_card_test.dart`, `test/features/scan/scan_result_screen_test.dart`

**Interfaces:**

- Consumes: `ScanDecisions`, `scanJobProvider` (exists), `ScanJobTracker.retry`.
- Produces:
  - `ShortScanCard({required ScanJob job, required VoidCallback onView, required Future<void> Function() onDismiss, VoidCallback? onTryAgain, DateTime Function()? now})`.
    - It shows the cover photo, `result.plantName`, the confidence as `"${(c*100).round()}%"` (hidden when null), a one-line diagnosis, and the countdown.
    - The diagnosis line is: the diagnosis name when the diagnosis state is ok; "Identified only" for identify mode; "Health check didn't run" for degraded.
    - The countdown shows "Deletes in N h", or "Deletes in N min" under an hour, from `decideBy`.
    - The buttons are "View" and "Dismiss", and "Try again" when `onTryAgain` is given.
    - The card has a dashed border in the Canopy warning colour, taken from `GreenThumbExtension`; read `docs/rules/flutter.md` and `flutter-ui-design.md` first.
  - `/scans/:id` (`ScanResultScreen`):
    - An `undecided` job → a plain screen with `ShortScanCard`. View pushes `/scans/:id/full`; Dismiss calls `dismiss` and then pops (or goes Home if there is nothing to pop); Try again is offered when the tracker's `canRetry` holds.
    - A `kept` job → the full result with "In My Collection".
    - A 404 → "This scan was deleted" (it replaces today's `ErrorScreen` for `NotFound` only).
    - The existing `viewed()` call stays.
  - `/scans/:id/full`: `ResultsScreen` with a `decisionBar`.
    - An undecided job gets "Add to My Collection" (`keep`, then the bar shows "In My Collection") and "Dismiss" (dismiss, then go to My Plants).
    - A kept job shows "In My Collection".

- [ ] **Step 1: Write failing widget tests.**
  - `short card shows name, 92%, diagnosis line and Deletes in 18 h` (fixed `now`).
  - `shows minutes under an hour`.
  - `identify scan shows Identified only`.
  - `undecided job opens the short card`.
  - `View opens the full result with Add to My Collection`.
  - `Add calls keep and shows In My Collection`.
  - `Dismiss calls dismiss and leaves`.
  - `shows deleted state on 404`.
  - `kept job shows In My Collection and no Add`.
  - `half-result offers Try again`.
- [ ] **Step 2: Run them, see them fail. Step 3: Implement. Step 4: Run them, see them pass.**
  Run: `flutter test test/features/scan/`
- [ ] **Step 5: Commit** `feat(mobile): short scan card and Add to My Collection (9/11)`.

### Task 10: My Plants: undecided cards first, Remove on long-press

**Files:**

- Modify: `plant_community_mobile/lib/features/collection/collection_screen.dart`
- Test: `test/features/collection/collection_screen_test.dart`

**Interfaces:**

- Consumes: `undecidedScansProvider`, `ShortScanCard`, `ScanDecisions.removePlant/dismiss`.

**What it does:**

- Undecided cards render as full-width `ShortScanCard`s in a sliver above the grid, newest first, and View pushes `/scans/:id/full`.
- A card whose `decideBy` has passed is filtered out at build time. A 1-minute `Timer.periodic` in a small `StatefulWidget` wrapper rebuilds the countdown and drops expired cards.
- A list fetch error hides the section; the kept grid still shows.
- The eyebrow count stays `plants.length` (kept only).
- A long-press on a kept `_PlantCard` opens a bottom sheet with "Remove". Confirming (an in-app sheet with "Remove" / "Cancel"; no `showDialog` of `confirm`) calls `removePlant`. A failure shows a SnackBar with the error message.

- [ ] **Step 1: Write failing tests.**
  - `shows undecided cards above kept plants`.
  - `hides an undecided card whose decide_by passed` (inject `now`).
  - `count shows kept plants only`.
  - `long-press Remove confirms then calls removePlant`.
  - `undecided list error still shows kept grid`.
- [ ] **Step 2: Run them, see them fail. Step 3: Implement. Step 4: Run them, see them pass.**
  Run: `flutter test test/features/collection/`
- [ ] **Step 5: Commit** `feat(mobile): undecided scans and Remove in My Plants (10/11)`.

### Task 11: Docs, todos, full verification

**Files:**

- Modify: `CLAUDE.md`.
  - `SCAN_DIAGNOSE_DAILY_*` row: add "a dismissed or expired scan still counts; Try again on a half-result hands its identification back".
  - `SCAN_JOB_STALE_MINUTES` row: name the new `scan-decision-sweep` (15 min, 24 h window).
- Move: `todos/698-pending-p2-scan-free-plant-id-spend-rule.md`. Set it to complete with the resolution "no change, owner decision 2026-11-06: fails are free", and archive it the way `completing-todos` does (check `todos/` for the archive folder convention).
- Move: `todos/699-…`. Set it to complete with the resolution "done by keep-or-dismiss (dismiss/expiry erase, failed/cancelled erase at end)".
- Modify: `docs/rules/api.md`, one bullet: "Erasing a scan never deletes its `ScanJob` row before its allowance window passes: the allowance counts rows."

- [ ] **Step 1: Make the doc edits.**
- [ ] **Step 2: Backend full verification.**
  - Run: `venv/bin/python -m pytest -q -p no:cacheprovider` (full suite, about 10 min; launch it detached per memory `project_background_pytest_detach_macos`). Then run `ruff check .`, `mypy`, `manage.py check`, `makemigrations --check --dry-run` and `spectacular --validate --fail-on-warn`.
  - Expected: all green. The `apps/core/tests` OpenAPI guards must be green.
- [ ] **Step 3: Mobile full verification.**
  Run: `flutter analyze && flutter test`
  Expected: "No issues found", and all tests pass.
- [ ] **Step 4: Commit** `docs(scan): keep-or-dismiss rules; close todos 698 and 699 (11/11)`.
- [ ] **Step 5: Open the PR** (`gh pr create`). The body lists the owner decisions and the old-build header rule. The owner device check on a new TestFlight build is the remaining step. The PR is not merged until the owner asks.
