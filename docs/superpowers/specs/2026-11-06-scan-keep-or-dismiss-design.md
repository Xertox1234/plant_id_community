# Scan results: Add to My Collection or Dismiss

Date: 2026-11-06. Status: waiting on the owner's approval (builder check done).

## Why

Today every finished scan is saved to My Plants automatically
(`ScanJobTracker._saveThenClear` in
`plant_community_mobile/lib/features/scan/scan_job_tracker.dart`). Users'
collections fill with photos they never meant to keep. The owner wants the user
to choose: after a diagnosis or an identification, **Add to My Collection** or
**Dismiss**. Fewer photos stay in collections, and fewer private photos stay on
our servers.

## What the owner decided

1. A finished scan (diagnosis or identification) offers two buttons: **Add to
   My Collection** and **Dismiss**.
2. **Dismiss** deletes the scan immediately.
3. **Add** keeps it in My Plants until the user removes it.
4. Until the user chooses, the scan **still shows in My Plants**, marked as
   undecided. The marking is mockup **B**: a dashed card with a countdown
   ("Keep it? 18 h left") and the Add and Dismiss buttons on the card itself.
5. If nothing is chosen within **24 hours**, the scan is deleted. There is no
   reminder, modal or coach message. If the user ignores it, it is gone.
6. **Plants already in collections stay as they are**: normal kept plants, no
   countdown.
7. **Fails are free** (todo 698): a failed or cancelled scan never costs the
   user an allowance slot, even if it already spent Plant.id calls. No change
   to the current rule; todo 698 closes as "no change, owner decision
   2026-11-06".

8. **Dismissed scans cost a check; a half-result retried does not.** A
   dismissed or expired scan still counts against the allowance. The exception
   is a half-result: a diagnosis whose health check did not run (`degraded`),
   which offers **Try again**. Tapping Try again dismisses the half-result
   automatically **and hands back its identification**, so only the new scan
   counts.

## Goals

- No scan reaches My Plants as a kept plant without the user tapping Add.
- A dismissed or expired scan leaves nothing behind that the user, or anyone,
  can retrieve: no card, no photo file, no stored result.
- A kept plant keeps working exactly as today, photo included, until removed.
- A kept plant can be removed from My Plants (there is no remove action today).

## Non-goals

- Reminders, notifications or coach prompts about undecided scans.
- Any change to plants already saved, or to the allowance numbers.
- The web app (scans are mobile-only).
- A retention limit on kept plants.

## Anti-goals (a failure even if it "works")

- **Dismiss refunds a check.** Dismissing must not give the user their
  diagnosis or identification back. Today the allowance is counted from
  `ScanJob` rows (`counted_created_at` in
  `backend/apps/plant_identification/scan_jobs.py`), so deleting the row on
  dismiss would hand the slot back. The row must stay until it no longer
  counts.
- **A plant someone already has disappears** or loses its photo.
- **A dismissed photo is still served** by `scans/{uuid}/photos/{role}/`.
- A kept plant's photo breaks because the sweep deleted it.

## How it works (builder's calls are marked)

### Server (`backend/apps/plant_identification/`)

- **Decision on the job.** *(My call)* Add a `decision` field to `ScanJob`:
  `undecided`, `kept`, `dismissed`, `expired`, `removed`, plus `decided_at`. It
  applies only to jobs that finished with a result (`done`, `degraded`); a job
  gets `undecided` when it finishes with a result. The migration sets every
  existing `done` / `degraded` job to `kept`, because those were all
  auto-saved (owner decision 6).
- **Keep:** `POST scans/{uuid}/keep/` sets `kept`. Owner-only, same lookup and
  permissions as `cancel`. Allowed only while `undecided`; repeating it on a kept
  job is a no-op success.
- **Dismiss:** `POST scans/{uuid}/dismiss/` sets `dismissed`, deletes the
  job's `ScanJobImage` rows (the existing `post_delete` signal deletes the
  files on commit) and clears `result`. The row itself stays, with `status`
  and `charged_as` untouched, so the allowance still counts it (anti-goal 1).
  Allowed while `undecided`. Repeating it on a dismissed or expired job is a
  no-op success. On a `kept` job it is refused; kept plants go through remove.
- **Remove:** `POST scans/{uuid}/remove/` on a `kept` job: same deletion as
  dismiss, decision `removed`. Called by the app when a kept Scan 2.0 plant is
  removed from My Plants.
- **Expiry:** *(My call)* a beat task deletes, like dismiss, every `undecided`
  job whose `finished_at` is more than 24 hours old, with decision `expired`.
  It runs every 15 minutes, so a scan lives at most about 24 h 15 m. It can be
  a new task next to `expire_stale_scan_jobs` or an extension of it; that is
  the builder's call. Put the 24 h in `constants.py` with the other scan
  windows.
- **Undecided list:** `GET scans/?decision=undecided` returns the user's undecided
  jobs (newest first) with `cover_photo`, the name fields and a
  `decide_by` timestamp (`finished_at` + 24 h). *(My call)* The server is the
  source of truth for undecided scans. Firestore only ever holds kept plants,
  so the expiry needs no Firestore access.
- **Retrieve and photos** for a `dismissed` / `expired` / `removed` job answer
  410 (or 404; the builder's call, keep it consistent with L1's 404), never the
  old result.
- **Failed and cancelled scans.** *(My call)* Their photos are deleted when the
  job ends: nothing reads them after that, because "Try again" uses the
  capture held on the phone. This finishes todo 699 (photo retention) along
  with the rules above. Kept photos stay until removal or account deletion.
- **Try again on a half-result** (decision 8): `POST scans/` accepts an
  optional `retry_of` (the half-result's uuid). In the same transaction as the
  create, if that job is the caller's own, `degraded` and still `undecided`, the
  server dismisses it (photos and result deleted, as above) and clears its
  `charged_as`, so it stops counting. Any other `retry_of` is ignored, not an
  error. A plain Dismiss of a half-result, without Try again, still costs its
  identification. Test both.
- **Allowance and Plant.id quota:** otherwise unchanged. Fails are free (decision 7).
  A dismissed or expired scan still counts for the rest of its 24 h window
  because its row remains.

### Mobile (`plant_community_mobile/`)

- **Stop the auto-save.** The tracker no longer writes to Firestore when a job
  finishes, and `viewed()` no longer saves either. The stored-job id
  bookkeeping that exists only to retry the save goes with it, if nothing
  else needs it.
- **Result screen** (`features/scan/scan_result_screen.dart` →
  `ResultsScreen`): an undecided job shows **Add to My Collection** and
  **Dismiss**.
  - Add: call keep, then write the Firestore plant exactly as the tracker does
    today (same doc id = job uuid, `imageUrl` = cover photo, timestamp = job
    creation). The screen then shows "In My Collection".
  - Dismiss: call dismiss, then leave the screen.
  - A kept job shows "In My Collection". A dismissed or expired job (an old
    push opened late) shows "This scan was deleted".
- **My Plants** (`features/collection/collection_screen.dart`): undecided
  scans from the undecided list appear in the same grid as **dashed cards** with
  the countdown and Add / Dismiss on the card (mockup B), ahead of kept plants
  *(my call: undecided first, newest first)*. Tapping the card body opens the
  result screen. The countdown reads from `decide_by`; under an hour it shows
  minutes. When it runs out, the card goes away without waiting for the sweep.
  The "N PLANTS IDENTIFIED" count covers kept plants only *(my call)*.
- **Remove:** a kept plant gets a Remove action (on its detail screen, or a
  long-press menu; the builder's call) with an in-app confirmation. It deletes
  the Firestore doc (`FirestoreService.deletePlant`). If the plant came from a
  Scan 2.0 job (its id is a job uuid and its image is a `scans/` photo), the
  app also calls remove so the photos go. Older plants just lose their doc.
- **Offline:** Add, Dismiss and Remove need the server. *(My call)* With no
  connection they show a clear error and change nothing; undecided cards come
  from the server, so offline My Plants shows only kept plants.
- **Try again** (`ScanJobTracker.retry`) sends the half-result's id as
  `retry_of`, and the half-result's card leaves My Plants.
- **Copy:** the "scan ready" push and the pill keep their wording. *(My call;
  the owner may want "Keep or dismiss within 24 h" added.)*

### Docs and todos

- CLAUDE.md: the `SCAN_DIAGNOSE_DAILY_*` row says failed and cancelled scans
  cost nothing. Add that dismissed and expired scans still count.
- Close todo 698 as "no change, owner decision 2026-11-06: fails are free".
- Close todo 699 as done by this work.

## Edge cases the builder must cover

- Two devices: Add on one, Dismiss on the other. The server decides: the
  second call is refused, or is a no-op if it repeats the first decision. The
  app refreshes the card from the server's answer.
- Add succeeds on the server but the Firestore write fails or is offline.
  Firestore queues offline writes; on a hard failure the app retries the write
  from the result screen, since the job is now `kept` and the result is still
  there.
- The expiry and a tap race: decide under a row lock (`select_for_update`),
  the same way `cancel` does.
- Account deletion still cascades and deletes every photo (existing signal).
- Tests must show that a dismiss leaves `remaining` unchanged on
  `GET scans/allowance/`, and that a dismissed job's photo URL no longer
  serves the file.

## Settled after the builder check (my calls)

- **Installed builds that still auto-save.** TestFlight builds 17/18 save
  every finished scan to Firestore themselves. If the server started such a
  job as `undecided`, the sweep would delete the photo of a plant the user
  already has. So the new app sends a header on `POST scans/` (for example
  `X-Scan-Decisions: 1`), and a job created without it starts as `kept`.
  Old builds keep working as they do today, and nothing they saved loses its
  photo. The header check can go once old builds are retired.
- **Kept on the server, missing from Firestore.** Add calls keep, then writes
  the Firestore plant. If the app dies in between, the job stays `kept` with
  no card. This is tolerated: the user chose to keep it, and the result screen
  (reached from the push or the pill) still offers to write it again. The same
  goes for older jobs whose auto-save never ran. No reconcile endpoint.
- **Name clash.** The decision value for "not chosen yet" is `undecided`, not
  `pending`, so it never reads like the job status `pending`. The list filter
  is `GET scans/?decision=undecided`.
- **Gone jobs answer 404**, not 410. The tracker already forgets a job on 404
  (`_handledReadError`); a 410 would keep the poll retrying.
- **Remove lives on a long-press menu** on the kept plant's card. There is no
  plant detail screen today.
- **Race between the sweep and a tap:** decide with a conditional `UPDATE`
  (`filter(decision="undecided").update(...)`), the way `cancel` does, rather
  than a row lock.

## Left to the builder

The endpoint shapes beyond what is above, the exact sweep cadence, where Remove
lives in the UI, the result screen's layout after Add, and the visual details
of the dashed card. Follow the Canopy tokens and `docs/rules/flutter.md`.
