---
status: completed
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

- [x] README documents all ~~13~~ **19** settings (count corrected — see work
      log), 3 signals, SpamBackend contract, bootstrap steps, and the envelope
      dependency; search caveat corrected
- [x] User/admin-facing strings wrapped in `gettext_lazy`;
      `makemessages` produces a usable catalog
- [x] TranslatableMixin decision recorded (adopt with migration plan, or defer
      with rationale)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 2 open findings per the manifest's Phase 4 grouping table; the
  H22 README-caveat correction was folded into M18 at triage.

### 2026-07-26 - Started by completing-todos skill (run 2026-07-26-1628)

- Picked up by automated workflow. Branch `forum-pkg/262-readme-i18n` cut off
  fresh `main` (6a3e459).

### 2026-07-26 - M18 README (24 -> 357 lines)

- **The audit's "13 settings" was stale — `conf.DEFAULTS` now has 19.** Verified
  the set is complete and closed: `grep -rn "WAGTAILFORUM_"` over the package
  shows the only read site is `conf.get_setting`, and all 19 keys have a
  `get_setting("...")` call. No setting is read outside `DEFAULTS`. AC amended.
- README now covers: requirements, install + `INSTALLED_APPS`, migrate, the
  host-owned bootstrap (workflow `ensure_default_workflow()` + "Forum
  Moderators" group, with runnable host-side example mirroring
  `apps/forum_host/bootstrap.py`), page-tree setup, API mounting, all 19
  settings in 3 grouped tables, the 3 signals with kwargs + 4 contract notes,
  the `SpamBackend` contract, error envelope, idempotency, rate limiting,
  search, management commands, and i18n.
- **Envelope wording**: todo 258 / M39 is already resolved (completed
  2026-07-24, PR #494) — the package ships
  `wagtail_forum.api.exception_handler.forum_exception_handler` as the
  reference handler. README documents the host-owned dependency and that
  skipping it silently yields bare DRF `{"detail": ...}`.
- **H22 search caveat corrected**: replaced the blanket "un-indexed icontains
  scan" warning with per-backend guidance — Postgres resolves to
  `PostgresSearchBackend` (real FTS + `ts_rank` + GIN) with no extra config;
  the degraded path is SQLite/unknown vendors only. Kept the genuine residue
  (50-result cap, no pagination, no `has_more`).
- Added `tests/test_docs.py` so the README cannot silently re-rot: it asserts
  every `conf.DEFAULTS` key appears as `WAGTAILFORUM_<NAME>` and every
  module-level `Signal()` declared in `signals.py` is named in the README.

### 2026-07-26 - M17 i18n

- `gettext_lazy` applied to: 5 Wagtail admin `menu_label`s + the
  `SearchArea("Forum")` label (`wagtail_hooks.py`); all model choice labels
  (`TrustLevel`, `Report.REASON_CHOICES`/`STATUS_CHOICES`,
  `Reaction.REACTION_CHOICES`, `NotificationVerb`); and every DRF error message
  across `api/{views,serializers,sanitize,exceptions,upload_validation,`
  `notifications,idempotency}.py`. f-string messages in `upload_validation.py`
  were converted to `%(name)s` interpolation so they stay lazy and translatable.
- **Zero migrations needed** — `makemigrations wagtail_forum` reports
  "No changes detected". Django's lazy proxy compares equal to its source
  string, so the autodetector sees no field change. `makemigrations --check
  --dry-run` across the whole project also exits 0, so the CI gate stays green.
- Deliberately NOT wrapped (Django's own convention): logger calls,
  `ImproperlyConfigured` messages, management-command help text, docstrings.
- Catalog: `django-admin makemessages -l en` produces
  `locale/en/LC_MESSAGES/django.po` with **61 msgids**; `compilemessages`
  succeeds. The `.po` is committed as the extraction reference; `.mo` is
  gitignored (built at deploy) and the README documents the workflow.
- **Round-trip verified with a real translation** (scratch `de` catalog, since
  removed): under `translation.override("de")` a translated msgid renders in
  German, an untranslated one falls back to the msgid, and DRF's `detail`
  stays an `ErrorDetail` (a `str` subclass) that `json.dumps` accepts — so no
  lazy proxy can reach response serialization.

### 2026-07-26 - TranslatableMixin decision: DEFER

Recorded in README ("Internationalization"). Evidence gathered before deciding:
`USE_I18N = True` but `LANGUAGE_CODE = "en-us"`, no `WAGTAIL_I18N_ENABLED`, no
`WAGTAIL_CONTENT_LANGUAGES`, and wagtail-localize is not in `requirements.txt`
— there is no consumer. Cost if adopted: `locale`/`translation_key` fields plus
a `unique_together(translation_key, locale)` constraint interacting with the
existing topic-slug and `uniq_opening_post_per_topic` constraints, and
migrations on live tables. Forum content is user-generated, so it needs
*interface* translation (delivered above), not *content* translation. Note
`ForumIndex`/`ForumBoard` are `Page` subclasses and already carry
`locale`/`translation_key`, so board structure is translatable today.

### 2026-07-26 - Code review (code-review-orchestrator) + repair

4 findings; 1 critical + 3 high were real and all repaired. Both real defects
were things my own verification could not have caught, so they are worth
recording:

1. **[critical] README typo `WAGTAILFORUM_MENTION_MAX_PER_POSTX`.** Self-
   inflicted: my mutation-check of `test_docs.py` had a broken restore path
   (relative `cp` after a `cd`, so the restore silently failed, and the second
   run then overwrote the backup with the already-mutated file). The typo
   survived — **and `test_docs.py` passed anyway**, because `f"WAGTAILFORUM_
   {name}" not in text` is a *substring* check and the real name is a prefix of
   the typo. Fixed the README and hardened the test to
   `re.search(rf"WAGTAILFORUM_{name}\b", text)`. Re-verified by mutation, this
   time restoring with `git checkout --`: mutated → fails naming
   `MENTION_MAX_PER_POST`, restored → passes, tree clean.
2. **[high x3] Missed i18n strings in `models/posts.py`.** `edit_block()` /
   `delete_block()` return `(code, message)` tuples whose message reaches
   clients via `raise Conflict(message)` in `api/views.py` — genuinely
   user-facing, and outside the audit's stated line refs, so my sweep missed
   them. Wrapped "Post is locked.", "Topic is closed or locked.", and
   "Opening posts cannot be deleted via the API."

Follow-up sweep of my own after the repair (`grep` for any remaining
`raise <Exc>("...")` package-wide, excluding tests): **zero** remaining bare
user-facing strings. Catalog regenerated: 61 → 64 msgids.

Deliberately left unwrapped after tracing their sinks — `SpamResult.reason`
(persisted as a Wagtail workflow rejection comment; translating at write time
would corrupt the moderation audit trail) and `DEFAULT_WORKFLOW_NAME` /
`"Spam check"` (`get_or_create` lookup keys — a translated name would create a
duplicate workflow row per locale). Both rationales documented in the README so
a future reader does not "fix" them.

### 2026-07-26 - Catalog compilation is NOT wired into any build (stated, not fixed)

Raised on final review: the `.mo` is gitignored and Django reads only the
compiled catalog, so a clean-checkout build ships `.po` with no `.mo` and the
catalogs are inert at runtime. Checked whether to wire `compilemessages` next
to the Dockerfile's baked `collectstatic` (todo 261) — **it would fail**:
`backend/Dockerfile` is `python:3.13-slim` and installs only `build-essential
libpq-dev`, so `msgfmt` is absent.

Decision: do NOT wire it in this p3 docs PR. Adding `gettext` to the production
image is a deploy-risk change for zero current benefit — the host is
English-only (`LANGUAGE_CODE = "en-us"`, no `WAGTAIL_CONTENT_LANGUAGES`) and the
sole catalog is `en` with every `msgstr` empty, so the compiled artifact would
be a no-op. Instead the README now says plainly that nothing in this repo
compiles catalogs, why (no `gettext` in the image), and exactly what a host
adopting a non-English locale must add. The earlier wording implied a build step
existed somewhere; that was the misleading part, and it is fixed.

### 2026-07-26 - Packaging: investigated, no change needed

Checked whether templates and the new catalogs actually ship (they would be
useless otherwise). Built wheel + sdist before and after adding an explicit
`[tool.setuptools.package-data]` block: **identical output both ways** (5
templates, locale files, 118 wheel entries / 143 sdist entries). setuptools'
pyproject-mode `include-package-data` already covers them, so the block was
removed rather than shipping redundant config with a false justification.

### 2026-07-26 - Completed by completing-todos skill (run 2026-07-26-1628)

- Verification: all 3 acceptance criteria passed.
  `pytest packages/wagtail_forum apps/forum_host --create-db` → **532 passed**
  (twice: before and after the review repair — the suite includes tests that
  assert error messages verbatim, e.g. `resp.data["message"] == "Post is
  locked."`, which confirms the lazy wrapping renders identically under `en`).
  `manage.py makemigrations --check --dry-run` → "No changes detected".
  `makemessages` → 64 msgids, `compilemessages` OK. ruff + flake8 clean.
- Review: 4 findings, 4 blocking (1 critical + 3 high) — **all repaired**, then
  re-verified. No findings accepted unaddressed.
- Source review `docs/audits/2026-07-11-forum-modernization.md`: #M17 and #M18
  checked off. 19 findings remain open there, so the doc is NOT renamed.

## Notes

p3. Cheap, self-contained; good candidate to ride along with any package PR.
