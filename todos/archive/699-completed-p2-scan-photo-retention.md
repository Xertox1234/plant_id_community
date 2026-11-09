---
status: completed
priority: p2
issue_id: "699"
tags: [scan, privacy, r2, owner-decision]
dependencies: []
owner_decision: "Retention settled by keep-or-dismiss: dismiss/24 h expiry erase; failed/cancelled erased at end; kept until removed (2026-11-06)"
---

# Scan 2.0: private scan photos are kept forever

## Problem

Scan photos (users' homes and plants) live in the private R2 bucket with no
retention: failed, cancelled and old finished scans keep them until the user
deletes their account. Data minimisation says to delete what is no longer
needed, and nothing in the app needs a photo after its result is seen.

## Findings

- `grep ScanJob` outside tests finds no delete or prune path; photos go only
  with the user (CASCADE + `delete_scan_photo_on_commit`).
- Precedent: `manage.py prune_link_preview_images`, run nightly by
  `forum-prune-cron` (CLAUDE.md `FORUM_LINK_PREVIEWS_ENABLED` row).
- Source: scan-2 audit 2026-11-05, M6 (CC M3).

## Proposed Solutions

### Option 1: Prune photos N days after the job finished (Recommended)

- **Implementation:** `manage.py prune_scan_photos [--dry-run]` deletes the
  `ScanJobImage` rows (and their objects, through the existing signal) of jobs
  finished more than `SCAN_PHOTO_RETENTION_DAYS` ago; failed/cancelled sooner
  (e.g. 1 day). Run it from `forum-prune-cron`. Keep the job row and result.
- **Effort:** half a day. **Risk:** low (follow `docs/rules/security.md`
  fail-closed deletion rules: refuse non-finite or negative ages).

## Recommended Action

1. Owner picks the retention window(s).
2. Build the command with a dry run and tests; add it to the cron.
3. Document the window in CLAUDE.md and the privacy policy.

## Technical Details

- `backend/apps/plant_identification/scan_models.py`, `scan_storage.py`.
- Deletion-tool rules: `docs/rules/security.md` (todo 697 codification).

## Acceptance Criteria

- [x] Owner's retention window recorded here with its date (2026-11-06, see owner_decision).
- Dropped, not done: `prune_scan_photos --dry-run` lists, and a real run deletes, only photos
      past the window; tests cover the boundary and a non-finite age.
- Dropped, not done: Scheduled on the cron service.

## Work Log

### 2026-11-06 - Filed from the scan-2 audit

- Deferred at triage: the retention window is the owner's call.

### 2026-11-06 - Closed by the keep-or-dismiss branch

- Retention is settled by the decision flow, not a `prune_scan_photos` command:
  dismissing a scan, or letting it sit undecided for 24 h (the 15-minute
  `scan-decision-sweep`), erases its photos; failed and cancelled scans erase
  their photos when they end; a kept scan keeps them until the user removes it.
- No `prune_scan_photos` command was built and nothing was added to
  `forum-prune-cron`, so the second and third criteria were replaced by the
  above rather than met as written. The privacy-policy wording is not updated here.
