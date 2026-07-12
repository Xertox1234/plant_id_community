---
status: pending
priority: p3
issue_id: "262"
tags: [forum, wagtail, i18n, docs]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M17, M18"
---

# Forum epic: reusable-package polish (docs + i18n)

## Problem

`wagtail_forum` is pip-installable and positioned as a reusable Wagtail
package, but its README documents almost nothing a reuser needs, and it has
zero i18n — wagtail-localize has no path to forum content and every user-facing
string is untranslatable. p3 epic from the 2026-07-11 forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

- **M18** — README (24 lines) is silent on ALL 13 `WAGTAILFORUM_*` settings
  (`W/conf.py:5-34`), the 3 public signals (`W/signals.py:18-20`), the
  pluggable `SpamBackend` interface, and install/bootstrap steps (workflow
  bootstrap, "Forum Moderators" group pattern). The package IS pip-installable
  (pyproject.toml verified) — the gap is docs only. Two agents converged
  independently. **Must also correct the README's overstated search-backend
  caveat** (audit H22 outcome: with `django.contrib.postgres` installed the
  default backend resolves to `PostgresSearchBackend` with real FTS, ranking,
  and applied GIN migrations — the "unindexed linear scan" warning only applies
  to SQLite/unknown vendors).
- **M17** — Zero i18n: no `gettext_lazy` on any user/admin-facing string (menu
  labels `W/wagtail_hooks.py:10-51`, all API error messages
  `W/api/views.py:97-119`, `W/api/sanitize.py:62-136`), no `TranslatableMixin`
  on Topic/Post.

## Recommended Action

1. **M18 README**: install + INSTALLED_APPS + migration/bootstrap steps
   (workflow get-or-create, moderator group), settings table generated from
   `conf.py`, the 3 signals with payloads, the `SpamBackend` contract, the
   host-owned error-envelope dependency (coordinate wording with todo 258
   M39's decision), and the corrected search-backend guidance per H22.
2. **M17 i18n**: `gettext_lazy` sweep over hooks labels + API/sanitize error
   strings; verify `makemessages` yields a sane catalog. Evaluate
   `TranslatableMixin` on Topic/Post separately — it changes uniqueness
   constraints and adds migrations; investigate before committing, and record
   an adopt/defer decision (user-generated content arguably doesn't need
   content translation — the strings do).

## Technical Details

- `docs/rules/wagtail.md` auto-injects on package edits; long-form patterns in
  `backend/docs/patterns/domain/forum.md`.
- `test_reusability.py` forbids `apps.*` imports — README examples must show
  host-side wiring, not package changes.

## Acceptance Criteria

- [ ] README documents all 13 settings, 3 signals, SpamBackend contract,
      bootstrap steps, and the envelope dependency; search caveat corrected
- [ ] User/admin-facing strings wrapped in `gettext_lazy`;
      `makemessages` produces a usable catalog
- [ ] TranslatableMixin decision recorded (adopt with migration plan, or defer
      with rationale)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 2 open findings per the manifest's Phase 4 grouping table; the
  H22 README-caveat correction was folded into M18 at triage.

## Notes

p3. Cheap, self-contained; good candidate to ride along with any package PR.
