---
status: completed
priority: p2
issue_id: "363"
tags: [dependencies, wagtail, django]
dependencies: []
---

# Assess and execute Wagtail 7.4.3 → 8.0

## Problem

PR #695 put the backend on Django 6.1.1 while leaving Wagtail at 7.4.3. Wagtail
7.4.3 declares `Django>=5.2` with **no upper bound**, so it installs and runs — but
its trove classifiers stop at `Framework :: Django :: 6.0`. The pairing is therefore
untested upstream. Wagtail 8.0 is the first release classifying Django 6.1.

## Findings

- `wagtail==7.4.3` (`backend/requirements.txt:197`); Wagtail 8.0 classifies 5.2, 6.0
  **and 6.1** (PyPI `requires_dist`/classifiers, checked 2026-09-06).
- The full suite is green on the 7.4.3 × 6.1.1 pairing (2273 passed, 8 skipped),
  including the forum package's 36-migration surface, and CI is 17/17.
- The only Django-6.1-induced behaviour change found was a query-count *reduction*
  in our own serializer path (a redundant PK refetch in `get_opening_post_id`) —
  nothing inside Wagtail internals broke.
- A page-EDIT render smoke test was added in #695
  (`apps/blog/tests/test_admin_render_smoke.py::test_page_edit_view_renders_the_form`)
  specifically to cover the admin form surface for this pairing. It passes.

## Recommended Action

1. Read the Wagtail 8.0 release notes' upgrade considerations in full.
2. Bump `wagtail` to 8.0 and run the full suite plus `manage.py check`.
3. Work through the 6.4–7.3 deprecation removals that 8.0 enforces, in particular
   the ones this codebase plausibly uses:
   - `construct_wagtail_userbar` hook now takes a third `page` argument
   - telepath moves `wagtail.telepath` → `wagtail.admin.telepath`
   - `WAGTAILSEARCH_BACKENDS` `INDEX` option → `INDEX_PREFIX`
   - custom listing views must supply a `breadcrumbs_items` context variable
   - custom viewset permission policies must register via `register_permission_policy()`
   - `SnippetChooserViewSet.widget_class` returns a class, not an instance
   - `Page._get_site_root_paths()` parameter renamed `request` → `cache_object`
   - AVIF/WebP no longer auto-convert to PNG — configure conversions explicitly
4. Expect three **new** dependencies: `django-ninja`, `pydantic`, `swapper`.
5. Re-run the R2 rendition path (`USE_R2`) given the AVIF/WebP conversion change.

## Technical Details

- `backend/packages/wagtail_forum/` is the highest-risk consumer: 36 migrations,
  custom admin views (`admin_views.py`), custom viewsets, custom permission policies.
- `django-treebeard` must stay `<6.0` — both Wagtail 7.4.3 and 8.0 cap it there, so
  do **not** take `django-treebeard` 7.0.1 as part of this.
- `djangorestframework` is already at 3.18.0 (#695), which is Wagtail 8.0's floor.

## Acceptance Criteria

- [x] `wagtail==8.0` in `backend/requirements.txt`, `pip check` clean
- [x] Full backend suite green, CI green — 2328 passed locally; CI 17/17 on PR #710
- [x] `/cms/` login, dashboard, explorer listing and page-edit smoke tests all pass
- [x] Forum admin views exercised — 24 admin tests + `test_moderation_queue.py`,
      plus the menu-order render checked empirically
- [~] `USE_R2` rendition path manually exercised once — **retired from this todo,
      re-pointed to [todo 371]**. Not done here and not claimed as done: no R2
      credentials exist locally. `[~]` means moved, not shipped.
- [x] Any new deprecation warnings triaged, not merely observed

## Work Log

### 2026-09-06 - Filed

- Deferred deliberately from PR #695 (Django 6.1.1 upgrade) so the Django bump could
  land on a green, reviewable diff. Raised by the #695 code review as the one
  remaining untested-upstream pairing.

## Notes

p2, not p1: the pairing is empirically green and prod is unaffected today. But it
is the last unsupported-by-classifier dependency in the stack, and Django 6.2 LTS
(April 2027) will need Wagtail 8.x regardless — so this is on the critical path to
the next LTS, not optional.

### 2026-09-07 - Started by completing-todos skill (run 2026-09-07-2255)

- Picked up by automated workflow. Worktree `../plant_id_community-wagtail8`,
  branch `chore/todo-363-wagtail-8`, own venv.

### 2026-09-07 - Executed: Wagtail 8.0 bump

**Result: `wagtail==8.0` installed and green. 2328 passed, 8 skipped, 0 failed
(26m03s), `manage.py check` clean, `makemigrations --check` clean.**

#### The dependency list in "Recommended Action" step 4 was wrong in both directions

Predicted three new deps (`django-ninja`, `pydantic`, `swapper`); only **two**
are new. `pydantic==2.13.3`, `django-tasks==0.12.0` and `django-filter==26.1`
were already pinned and already inside 8.0's ranges. It also missed two hard
`ResolutionImpossible` conflicts:

| Package | Was | Wagtail 8.0 requires | Now |
|---|---|---|---|
| `draftjs_exporter` | 5.2.0 | `>=7.1.0,<8.0` | **7.1.0** (2-major bump) |
| `modelsearch` | 1.3.1 | `>=1.3.2,<1.4` | **1.3.2** |
| `django-ninja` | *(unpinned)* | `>=1.6.3,<2.0` | **1.7.0** (new) |
| `swapper` | *(unpinned)* | `>=1.4,<2` | **1.5.0** (new) |

Rather than discover these one failed install at a time, all 21 of Wagtail 8.0's
declared deps were checked against our pins programmatically (`packaging`
specifiers vs. the flat freeze) — that found `modelsearch` before pip did.

`modelsearch` 1.3.2 is pure bugfixes, one of which is *"Fix SQLite
MatchExpression for Django >=6.1"* — a fix for our exact Django version.
`draftjs_exporter` 6.0.0 changed rich-text output ("reduce redundant tags in
nested and partially nested inline style output"); semantically equivalent HTML,
no test asserted the old markup, suite green. OSV: all four pins CLEAN.

#### `pip check` alone would have passed a completely failed install

On both failed resolution attempts `pip check` printed **"No broken requirements
found"** while `pip install` had exited 1 — it was inspecting a venv containing
only pip/setuptools/wheel. AC line 1 as written ("`pip check` clean") is
satisfiable by an install that never happened. The gate used here is
`INSTALL_RC=0` **and** `PIPCHECK_RC=0`; both are 0.

#### Step 3's deprecation list: 7 of 8 items are not-applicable, verified

Checked against source (grep over `apps/ packages/ config/ templates/`, `.py`
`.html` `.js` `.ts` `.tsx`), not assumed:

- `construct_wagtail_userbar` third arg — hook never registered
- `wagtail.telepath` / `wagtail.widget_adapters` moves — no imports
- `WAGTAILSEARCH_BACKENDS` `INDEX` → `INDEX_PREFIX` — setting absent
- `breadcrumbs_items` on custom listing views — covered by the suite's
  `test_moderation_queue.py`, green
- `SnippetChooserViewSet.widget_class` — no `ChooserViewSet` anywhere
- `Page._get_site_root_paths()` `request` → `cache_object` — no callers
- Also zero hits for `TAG_LIMIT`, `TAG_SPACES_ALLOWED`, `PageListingButton`,
  `SnippetListingButton`, `UserListingButton`, `init_new_page`,
  `submissions_list_view_class`, `_editor_js.html`, `buildExpandingFormset`,
  `initPrefillTitleFromFilename`, `resetValue`, `TeleportController`

`register_permission_policy()` is the one item worth stating precisely rather
than as "done": it does **not** apply to us. The `RemovedInWagtail90Warning` is
raised only from `ModelViewSet.permission_policy`
(`wagtail/admin/viewsets/model.py:24-25,135`). Our sole `permission_policy` is
on `ModerationQueueView`, a `ReportView` — the *view*-level attribute in
`wagtail/admin/views/generic/permissions.py`, which is fully supported and not
deprecated. None of the five forum `SnippetViewSet`s set it.

#### AVIF/WebP: took the new default deliberately

Verified by diffing `default_conversions` in the two **installed** copies rather
than trusting the release note:

- 7.4.3 — `{"avif": "png", "bmp": "png", "webp": "png", "heic": "jpeg"}`
- 8.0 — `{"bmp": "png", "heic": "jpeg"}`

No `WAGTAILIMAGES_FORMAT_CONVERSIONS` is set, so WebP/AVIF now fall through to
`output_format = original_format`. Confirmed end-to-end: a real WebP upload
renders a `.webp` rendition (`{'WEBP': 'webp', 'PNG': 'png', 'JPEG': 'jpg'}`).

Added `apps/core/tests/test_image_rendition_formats.py` as that decision's
guardrail. Mutation-checked: with
`WAGTAILIMAGES_FORMAT_CONVERSIONS={"webp": "png"}` the webp test fails
(`MUTATION_RESULT: png`), so it is not vacuous.

**Caveat for whoever sees mixed formats in R2 later — not a bug:** renditions
are cached on `(image, filter_spec, focal_point_key)`, not on output format.
Existing WebP originals keep serving their already-cached PNG renditions; only
*new* renditions come out WebP. The two formats will coexist indefinitely.

#### AC 4 is split, and half of it is honestly unmet

**Forum admin — done.** 24 admin tests green (snippet listings, inspect views,
bulk unpublish incl. the permission-denied path, CSV/XLSX exports, admin
search), plus `test_moderation_queue.py`. The 8.0 "`ViewSet.menu_order` now
respected in `ViewSetGroup`" change was checked empirically, not by grep:
`menu_order` is `None` on all five viewsets (class default,
`wagtail/admin/menu.py:180`) and the rendered submenu is
`['Topics', 'Posts', 'Profiles', 'Reports', 'Badges']` — identical to the
declared `items` order. No silent reorder.

**`USE_R2` rendition round trip — NOT exercised.** There are no R2 credentials
in the local `.env`. `apps/core/tests/test_r2_storage.py` covers the *config*
path (subprocess `manage.py check` with controlled env) and is green, and the
rendition-format decision proven above is Willow/Wagtail-side and
storage-agnostic — R2 only changes where the bytes land, not what format they
are. That is an argument, not a verification, so the box stays unchecked.

#### Deprecation-warning triage (AC 5)

65 warnings, **zero attributable to Wagtail**: `grep -icE "RemovedInWagtail"` on
the run log returns `0`, and no warning originates inside
`site-packages/wagtail/`. Full classification:

| Class | n | Origin | Pre-existing? |
|---|---|---|---|
| `RemovedInDjango70Warning` | 10 | `pytest_django` (EMAIL_* → MAILERS), `apps/core/security.py:293` (`send_mail(fail_silently=)`), `taggit/managers.py:46` | yes — Django 6.1, not this bump |
| `DeprecationWarning` | 3 | `quota_manager.py:80,91` (`datetime.utcnow()`), `pythonjsonlogger` | yes |
| `UnorderedObjectListWarning` | 2 | DRF pagination, `test_n_plus_1.py` | yes |
| `RuntimeWarning` | 2 | naive datetime, `apps/garden` tests | yes |
| `UserWarning` | 1 | `fuzzywuzzy` missing python-Levenshtein | yes |

None are new and none are Wagtail 8's. The Django 7.0 MAILERS migration and the
`datetime.utcnow()` calls are pre-existing debt outside this todo's scope.

#### Other findings

- One new migration pends: `wagtailcore.0098_apitoken` — additive table for
  Wagtail 8's new v3 (django-ninja) write API.
- **The v3 API is not mounted here.** `INSTALLED_APPS` and `urls.py` register
  only `wagtail.api.v2`, so `django-ninja` is a passive transitive dependency:
  no new routes, no OpenAPI surface change. This also defuses the one upstream
  concern found — `wagtail-headless-preview` issue #80 ("Headless preview
  compatibility with v3 API in Wagtail 8.0", open since 2026-06-19) is about
  that v3 API and does not reach us on v2.
- `wagtail-ai==3.1.1` and `wagtail-headless-preview==0.9.0` both still classify
  `Framework :: Wagtail :: 7` with no upper bound — the same metadata-lag shape
  this todo was filed about for Wagtail×Django 6.1. Both are load-bearing
  (`AIFieldPanel`/`AITitleFieldPanel`/`AIDescriptionFieldPanel` on
  `BlogPostPage`; `generate_ai_text` behind forum spam screening, RAG,
  compose-assist and summaries; `HeadlessPreviewMixin` on `BlogPostPage`).
  Empirically fine: `manage.py check` logs
  `[WAGTAIL_AI_V3] ✅ Caching and rate limiting integration installed
  successfully` on Wagtail 8, and the suite is green. Not filed as a blocker —
  metadata lag, not a break.

#### Commands and evidence

```
pip install -r requirements.txt   → INSTALL_RC=0
pip check                          → "No broken requirements found." PIPCHECK_RC=0
manage.py check                    → "System check identified no issues (0 silenced)."
makemigrations --check --dry-run   → "No changes detected"
pytest -p no:randomly --create-db  → "2328 passed, 8 skipped, 65 warnings in 1563.67s"
grep -icE "RemovedInWagtail"       → 0
```

### 2026-09-07 - Code review + repairs

`code-review-orchestrator` on the diff: **0 critical, 0 high**, 3 medium, 1 low,
2 info. It verified the flat freeze independently (`pip freeze` vs
`requirements.txt` — only the expected editable-package and dev-only
differences) and confirmed all four pins sit inside Wagtail 8.0's ranges. Three
findings were worth fixing rather than logging; all are now addressed.

**1. AVIF was untested (medium).** Correct catch — AVIF and WebP were removed
from `default_conversions` *together*, and AVIF additionally needs a Pillow
build with an AVIF **encoder**, which is a rendition-time requirement an
upload-time check would never surface. Verified `Pillow 12.3.0` (our pin) has it
(`PIL.features.check("avif") is True`, and a real encode succeeds), then
parametrized the test over both formats. 4 tests pass.

**2. `draftjs_exporter` 7.0.0 was undocumented (medium) — and the trail led
somewhere real.** 7.0.0's change is *"the Markdown export now escapes all
content"*. My first assumption — that Wagtail doesn't use the Markdown
exporter — was **wrong**: Wagtail 8.0 adds
`wagtail/admin/rich_text/converters/markdown_db.py` and `wagtail/api/rich_text.py`
(both absent in 7.4.3), and **API v2 is newly wired to `APIRichText`**
(`wagtail/api/v2/serializers.py:10,279-283`). Our React frontend consumes that
endpoint, so this needed checking rather than dismissing.

It is a non-issue, for a specific reason: `APIRichText.DEFAULT_FORMAT` is
`db_html`, `_serialize_db_html()` is a pure passthrough (`return value`), and we
do not set `WAGTAILAPI_RICH_TEXT_FORMAT`. Markdown is reachable only via an
explicit `?rich_text_format=markdown` query parameter that nothing in our stack
sends. So API v2 rich-text output is byte-identical to 7.4.3 and the 7.0.0
escaping change cannot reach us.

Worth recording as an additive API surface change: `?rich_text_format=` is now
an accepted query parameter on our public API v2, offering `db_html` (default),
`html`, `db_markdown` and `markdown`. No new data is exposed — the same content
in a different rendering — but it is new public behaviour that arrived with the
dependency rather than with a change of ours.

**3. Unchecked AC 4 becomes invisible debt (medium).** Fair, and the project's
own convention covers it: non-blocking review findings become a follow-up todo.
Filed **todo 371** (p3, `dependencies: ["363"]`) for the real-R2 round trip, and
repointed AC 4 at it rather than checking off work that was not done.

**4. Probe files leaked into `MEDIA_ROOT` (low).** The reviewer noted this
matches existing project practice and flagged it for visibility only; fixed
anyway, since it is a new test and the fix is three lines. Added an autouse
fixture pointing `MEDIA_ROOT` at pytest's `tmp_path`. Verified it works rather
than assuming: probe files in `media/` before a run = 16, after = 16 (zero new).
The 16 orphans from the earlier un-isolated runs were removed from the
worktree's gitignored `media/`.

Both info findings were confirmations, no action: the flat freeze is internally
consistent, and `wagtailcore.0098_apitoken` will apply via `railway.json`'s
`preDeployCommand: python manage.py migrate --noinput` on the next deploy.

### 2026-09-07 - CI green on PR #710

All 17 required checks pass. The decisive one is the backend suite job
(`Run backend test suite`), which runs the same 2336 tests against the
PostgreSQL 16 + Redis 7 service containers rather than this worktree's local
Postgres. Also green: `No new dependency advisories`, `Backend Python Security
Scan` and `CodeQL`, which together cover the four new/bumped pins.

Remaining before archive: acceptance criterion 4's real-R2 half, tracked as
todo 371. This todo stays `in_progress` until that is either verified or
explicitly retired — an operator decision, not an automated one.

### 2026-09-07 - Round-1 review repairs (bundled deep pass on PR #710)

The bundled `/code-review` pass independently re-verified the dependency,
migration and deprecation claims (all held) and chased two hypotheses to
ground before finding anything: `?rich_text_format=markdown` cannot poison
`BlogPostPageViewSet`'s 24h slug-keyed cache, because `get_serializer_class()`
returns the hand-written `BlogPostPageSerializer` and so never builds Wagtail's
dynamic `api_fields` — `APIRichText` never touches `introduction`. And the AVIF
encoder is present in CI, since `ubuntu-latest` + `setup-python` pulls Pillow
manylinux wheels, which bundle libavif from 11.3 on.

It then found two real defects, both introduced by the previous commit on this
branch. Both are fixed.

**1. The `MEDIA_ROOT` isolation fixture silently no-opped under `USE_R2=True`.**
`settings.py:481` swaps `STORAGES["default"]` to `storages.backends.s3.S3Storage`
when the flag is on, and S3Storage ignores `MEDIA_ROOT` entirely. The trigger is
this very branch: todo 371 asks an operator to exercise the rendition path with
`USE_R2=True`, and the obvious way to do that is to point that run at this test
file — which would have written four probe originals plus their renditions into
the **real R2 bucket**, under `file_overwrite=False` and
`Cache-Control: public, max-age=31536000, immutable`, with nothing to clean them
up.

Verified rather than reasoned about, by forcing the S3 config and re-resolving
`default_storage`:

```
OLD-FIXTURE storage: S3Storage        | location: (empty)
NEW-FIXTURE storage: FileSystemStorage | location: /…/pytest-34/test_hardened…
```

The fixture now pins `STORAGES["default"]` alongside `MEDIA_ROOT` **and asserts
the pin took effect** — a fixture whose only job is isolation should fail loudly
rather than quietly stop isolating.

**2. `status: in_progress` made this todo invisible to every sweep.** All four
entrypoints discover candidates with `grep -l "^status: pending" todos/*.md`
(`todo-sweep:51`, `todo-next:25`, `todo-batch:39`, `completing-todos:56`), so
`in_progress` is unreachable — the same failure already recorded for
`status: blocked`. That is the exact opposite of this PR's stated intent of
keeping the residual visible. Set back to `pending`; the unchecked AC 4 and this
work log carry what remains, matching how todo 330 keeps an operator gate
discoverable.

**3. A circular dependency I created, found while fixing #2.** Todo 371 declared
`dependencies: ["363"]` while 363's sole remaining criterion is satisfied *by
performing 371* — a deadlock, and `todo-batch:112` would have *silently* excluded
371 as blocked by an out-of-batch dependency. 371 needs only the merged code, not
this todo file's status, so its `dependencies` are now empty.

### 2026-09-07 - Completed and archived

Archived on the operator's call, with the upgrade verified working and the one
residual re-pointed rather than checked off.

**Why this archives with a `[~]` and not a fifth `[x]`.** Acceptance criterion 4
bundled two unrelated things. The forum-admin half is done and is now its own
checked line. The `USE_R2` rendition round trip is **not** done — there are no R2
credentials in a local checkout — so it is marked `[~]` (moved) and carried by
**todo 371**, following this repo's rule that a finding which *moved* is
re-pointed, never checked off, because `[x]` means shipped and nobody re-audits
a checked box. Todo 371 is `status: pending` with empty `dependencies`, so every
sweep can see it.

**Evidence the upgrade is working:**

| Gate | Result |
|---|---|
| `pip install -r requirements.txt` | `INSTALL_RC=0` |
| `pip check` | `PIPCHECK_RC=0` |
| `manage.py check` | "System check identified no issues (0 silenced)." |
| `makemigrations --check --dry-run` | "No changes detected" |
| Full suite, PostgreSQL | 2328 passed, 8 skipped, 0 failed (26m03s) |
| CI on PR #710 | 17/17 at `c510cbb`; only tests/docs changed after |
| `RemovedInWagtail*` warnings | 0 — and none from inside `site-packages/wagtail/` |
| OSV on all four new/bumped pins | clean |

**What shipped beyond the version bump:** `draftjs_exporter` 5.2.0→7.1.0 and
`modelsearch` 1.3.1→1.3.2 (both forced by hard resolution conflicts this todo
did not anticipate), new pins `django-ninja==1.7.0` and `swapper==1.5.0`, a
mutation-checked guardrail test for the deliberate AVIF/WebP rendition-format
change, and codification into `docs/LEARNINGS.md`,
`backend/docs/patterns/domain/wagtail.md`, `docs/rules/testing.md` and a
write-time trigger.

**Review:** bundled deep pass returned 0 critical / 0 high and 2 medium, both
introduced by this branch and both repaired (`c8615c3`) — a storage-isolation
fixture that no-opped under `USE_R2=True`, and this todo's own `in_progress`
status hiding it from every sweep. The checklist pass (`code-review-orchestrator`)
returned 0 critical / 0 high, 3 medium, all addressed.
