---
status: in_progress
priority: p4
issue_id: "365"
tags: [documentation, dependencies]
dependencies: []
---

# Retire or mark the two stale 2025 dependency docs

## Problem

`backend/docs/DEPENDENCY_SECURITY_AUDIT_2025.md` and
`backend/docs/DEPENDENCY_UPGRADE_QUICKREF.md` still prescribe installing
`django-celery-beat`, which PR #695 removed, alongside other 2025-era pins
(Django 5.2.7, etc.) that no longer reflect the stack. They read as actionable
guidance but are point-in-time artifacts.

## Findings

- Stale `django-celery-beat` prescriptions at
  `DEPENDENCY_SECURITY_AUDIT_2025.md:345,773,873` and
  `DEPENDENCY_UPGRADE_QUICKREF.md:27` (found by the PR #695 code review).
- Neither file is in the auto-injected set — `docs/rules/celery.md` and
  `backend/docs/patterns/domain/celery.md` were both verified clean — so this is
  documentation rot, not agent-facing guidance.
- **Why #695 did not just fix it:** markdownlint auto-fixes MD022 across the whole
  file on touch. Adding 4 marker lines produced 132 lines of unrelated blank-line
  churn, which would have buried the upgrade diff. This is the todo-117 friction.
- `docs/development/CELERY_INTEGRATION_TODOS.md` was already lint-clean and *was*
  marked in #695.

## Recommended Action

1. Decide the honest disposition: these are dated audit artifacts. Prefer moving both
   to `docs/archive/` over maintaining them in place.
2. If they stay, take the markdownlint reformat as its own commit **first**, then add
   the content markers in a second commit so the semantic change is reviewable.

## Technical Details

- Reformat noise is MD022 ("headings surrounded by blank lines"), purely mechanical.
- Related: todo 117 tracks the whole-file-reformat commit friction generally.

## Acceptance Criteria

- [x] Neither file prescribes installing `django-celery-beat`
- [x] Either both live under `docs/archive/`, or both are lint-clean with markers
- [x] Any reformat lands as a separate commit from any content change

## Work Log

### 2026-09-06 - Filed

- Split out of PR #695 rather than dragging a 132-line reformat through a Django
  upgrade PR.

### 2026-09-13 - Archived (PR pending review)

Took Recommended Action 1: both files moved to `docs/archive/audits/`, beside
`COMPREHENSIVE_DEPENDENCY_AUDIT_2025.md`, which already linked to both.

**The reformat problem dissolved rather than being managed.**
`.pre-commit-config.yaml:212` excludes `docs/archive/.*\.md$` from markdownlint,
so there is no MD022 churn to separate — hence no reformat commit. The move
still landed on its own commit, content second, so the rename is reviewable
without the banner text mixed in.

Content commit adds to each file:

- an ARCHIVED banner under the H1 with a **successor map** — pins to
  `backend/requirements.txt`, detection to `.github/workflows/security-scan.yml`
  (pip-audit + `npm audit`, advisory per-PR, blocking on the Monday 09:00 UTC
  cron) and Dependabot alerts, exceptions to
  `.github/security-suppressions.yml`, secrets to
  `backend/docs/patterns/security/secret-management.md`
- a `SUPERSEDED (PR #695)` marker on each of the four surviving
  `django-celery-beat` prescriptions, so a reader landing mid-file by search
  sees it too and does not have to scroll up to the banner

Citations re-derived rather than trusted: the todo named lines 345/773/873 and
27, all four correct, plus an unlisted heading at :331. Every claim in the
banner was checked against the tree (`django-celery-beat` absent from both
requirements files; cron is `0 9 * * 1`; suppression entries do carry removal
conditions).

Also repaired en route:

- `.secrets.baseline` — the single QUICKREF entry re-pointed to the new path
  rather than regenerated. The finding is a dummy login payload in a `curl`
  example against `api.example.com`, already audited as a false positive; a
  rescan would rewrite all 98 entries to preserve one existing verdict.
  (Quoting the literal string here made detect-secrets fire on this todo file —
  the scanner reads prose, so describe such a finding rather than reproduce it.)
- the QUICKREF's own self-link and four links in
  `COMPREHENSIVE_DEPENDENCY_AUDIT_2025.md` still pointed at
  `/backend/docs/…`, now dangling. `grep -rn "backend/docs/DEPENDENCY"` returns
  zero hits repo-wide.
- `docs/archive/README.md` indexes both files.

## Notes

p4: pure hygiene, no runtime effect. Bundle it with the next markdownlint cleanup.
