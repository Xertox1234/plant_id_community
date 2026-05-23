---
status: completed
priority: p3
issue_id: "085"
tags: [audit-2026-05-17, backlog]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "M1-M5,M7,M8,M10,M12,M14-M25,M26-M46,L1-L4,L8-L30"
---

# Medium / Low audit findings backlog (2026-05-17 full audit)

## Problem

The 2026-05-17 full audit logged 46 Medium and 31 Low findings. The audit fixed
Critical + security + N+1 only; the rest were deferred. This todo is the backlog
index — the authoritative per-finding detail (description, file:line, severity)
lives in the manifest. Forum-app (`apps/forum/`) M/L findings are tracked
separately in todo 084.

## Findings

See `docs/audits/2026-05-17-full.md` — Medium and Low tables. Notable Mediums
worth pulling forward:

- **M1** — Firebase token exchange links accounts by email, no `firebase_uid`
  binding (`apps/users/firebase_auth_views.py:252`) — security defence-in-depth.
- **M2** — Firebase Storage rules let any authenticated user read every user's
  private images (`firebase/storage.rules:24,33,44`) — privacy.
- **M3** — Unescaped LIKE wildcards in 5 search endpoints — query-cost DoS.
- **M22** — Unmigrated StreamField change (model 6 blocks, migration 0003 has 10) —
  `makemigrations blog` will generate a pending migration.

L7 is a confirmed false-positive (duplicate of H7) — no action needed.

## Recommended Action

Work the Medium findings first (M1/M2/M3/M22 have real user-facing/security
impact). Pull each finding from the manifest, verify it still applies, fix, and
update the manifest's `Status` column. Low findings are opportunistic cleanup.

## Acceptance Criteria

- [x] Medium security/privacy findings (M1, M2, M3) addressed or risk-accepted.
- [x] Remaining Medium/Low findings triaged — each fixed, or closed with rationale
      recorded in the manifest.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4) per user triage (fix scope was
  Critical + security + N+1 only).

### 2026-05-21 - Started by completing-todos skill (run 2026-05-21-0238)

- Picked up by automated workflow.

### 2026-05-21 - Security/privacy fixes + backlog triage

Fixed the named security/privacy Mediums and the migration item:

- **M1 — fixed.** Added `User.firebase_uid` (migration `0009_user_firebase_uid`).
  `get_or_create_user_from_firebase` now: looks up by `firebase_uid` first; falls
  back to email for legacy accounts and **backfills** the UID on first sign-in;
  **rejects** sign-in when an email is already bound to a different UID
  (`ValueError`). Defence-in-depth against email-reassignment account takeover.
- **M2 — fixed.** `firebase/storage.rules`: the three private image paths
  (`plant-identifications`, `disease-diagnoses`, `user-plants`) changed from
  `allow read: if isAuthenticated()` to `if isOwner(userId)`; avatars stay public.
  NOTE: takes effect only on `firebase deploy --only storage`.
- **M3 — fixed.** Applied `escape_search_query()` (the project's LIKE-wildcard
  escaper) to all 5 search endpoints: `blog/views.py` `blog_search`,
  `blog/api_views.py` autocomplete, `forum_integration/{views,api_views}.py`
  `forum_search`, and `plant_identification/api/endpoints.py` family filters.
- **M22 — false-positive.** `makemigrations blog --check` reports "No changes
  detected" — model and migrations are in sync (a later migration reconciled the
  0003 discrepancy the audit saw).

Remaining ~37 Medium + ~27 Low findings: triaged in
`docs/audits/2026-05-17-full.md` → new "## Triage (todo 085)" section. All are
non-security quality/consistency/polish items (API contract, perf micro-opts,
Wagtail-AI architecture, Celery/web/mobile robustness, test quality, Low polish),
each enumerated by ID with a deferral rationale. None is an active security or
data-integrity exposure (those were M1–M3, now fixed).

Verification (`python manage.py test --noinput`): `python manage.py check` 0 issues;
users 96 OK + test_firebase_auth 17 OK (M1); blog 177 OK, plant_identification 108
OK, forum_integration 16 OK (M3).

### 2026-05-21 - Code review + completion

- Code review (code-review-orchestrator → security + django-drf checklists):
  **no critical/high findings**. M1 confirmed sound (UID→email lookup fails closed,
  unique-nullable migration safe in Postgres, create() sets UID); M2 rules correct;
  M3 escaping applied correctly. Two items repaired:
  - **MEDIUM** — M3 gap: `blog/views.py` tag filter (`tags__name__icontains=tag`)
    was unescaped. Fixed with `escape_search_query(tag)`; blog 177 OK.
  - **LOW** — M1 `ValueError` (UID/email mismatch) fell through to a generic 500.
    Added an `except ValueError` returning **409 Conflict**; test_firebase_auth 17 OK.
  - INFO (no action): `create_error_response` flat-shape change is intentional (todo
    081 H13); no client parses the old shape.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-0238)

- Verification: both acceptance criteria passed (M1/M2/M3 fixed, M22 false-positive,
  ~64 remaining M/L findings triaged with per-finding rationale in the manifest).
- Review: 0 blocking findings; 1 MEDIUM + 1 LOW repaired, 1 INFO recorded.

### 2026-05-21 - M1 hardened at commit gate

The `kimi-review` pre-commit hook flagged M1 auth code. Two of its points were
addressed in code (the "email-reassignment takeover" CRITICAL was a false-positive
already covered by the upstream `email_verified`/trusted-provider gate, but harden
anyway for defence-in-depth + reviewer visibility):

- `get_or_create_user_from_firebase` now takes an explicit `email_verified` arg and
  refuses to bind/backfill a UID onto an existing email account unless verified;
  the caller passes `email_verified or trusted-provider`.
- The new-user create is wrapped in `except IntegrityError` → re-fetch, so a
  concurrent first sign-in for the same identity returns the winning row instead
  of a 500.
- Added tests: `test_unverified_email_cannot_link_existing_account`,
  `test_mismatched_uid_rejected_for_bound_account`. users 98 OK + firebase 19 OK.
