---
status: pending
priority: p3
issue_id: "405"
tags: [backend, dead-code, product, api]
dependencies: []
source_review: "docs/audits/2026-09-23-web-dead-code.md"
source_finding: "L13"
---

# Backend endpoints no client calls: decide to wire up, keep for mobile, or remove

## Problem

The 2026-09-23 web dead-code audit mapped every backend route against both
clients. It found whole API families that **neither** web nor mobile calls. Each
is either an unfinished feature (wire it up) or dead code (remove it, along with
its tests and maintenance cost). That is a product decision per family, not a
mechanical fix.

## Findings

The route walk used `django.urls.resolve()` plus a URLconf walk, not grep.
Mobile-only endpoints were excluded as expected.

- **Forum AI:** `GET forum/topics/<id>/summary/` (premium) and
  `GET forum/topics/similar/` (503 unless `FORUM_VECTOR_SEARCH_ENABLED`).
  Backend-complete, with no UI anywhere.
- **Blog v2:** `blog-posts/featured|recent|by_category|search_suggestions|<pk>/related`,
  `blog-index/*`, `blog-categories/*`, `blog-authors/*`, `series/*`. The web
  uses list, detail, `popular/` and `categories/` only.
- **Blog v1 (DRF):** almost all of it, including `newsletter/*` and `stats/`.
- **Plant CMS v2:** `plant-species/*`, `plant-categories/*`, `care-guides/*`,
  `plants/*`, `plant-index/*`.
- **Plant ID v1:**
  - `species/*` and `results/*` (vote, accept, add_to_collection,
    regenerate-care);
  - `plants/<pk>/` edits;
  - `disease-results/*`, `disease-database/*`;
  - `saved-diagnoses/*`, `saved-care-instructions/*`, `treatment-attempts/*`;
  - `search/*`.
- **Users v1:** `me/searches/*`, `me/dashboard-stats/`,
  `me/push-notifications/*`, `me/care-reminders/*`, `me/onboarding/*`,
  `me/email-preferences/*`.
- **Garden and calendar:** all of `/api/v1/garden/*` and
  `/api/v1/calendar/api/*`. Mobile garden data lives in Firestore.
- **Legacy unversioned `/api/` mount** (`plant_community_backend/urls.py`,
  "TODO: Remove after 2025-07-01"). Its only web user was `diagnosisService`,
  deleted by this audit (H1). Whether other clients or tests use it is a
  hypothesis, not verified.
- **Dead preview mode (L14):** `BlogPostPage.preview_modes` offers
  "Mobile (Flutter)", but wagtail-headless-preview 0.9 calls
  `get_client_root_url(request)` without the mode. So that option opens the web
  preview and the `plantid://` branch is unreachable.

## Recommended Action

For each family above, record one decision in the Work Log, with the reason:

- **wire up:** file a feature todo;
- **mobile roadmap:** keep, and say which planned screen will use it;
- **remove:** delete the routes, views, serializers and tests in a PR.

Start with the legacy `/api/` mount: grep tests, mobile and e2e for `/api/`
paths without `v1`/`v2` before removing it.

## Technical Details

- Route inventory method: `django.urls.get_resolver()` walk, with each web and
  mobile call resolved. The audit manifest has the tables.
- `backend/plant_community_backend/urls.py` (the legacy mount, routers)
- `backend/apps/blog/models.py` (`BlogPostPage.preview_modes`,
  `get_client_root_url`)

## Acceptance Criteria

- [x] Every family listed above has a recorded decision (wire up, mobile
      roadmap, or remove) with a reason. See the 2026-09-23 decision table
      in the Work Log (owner decisions; the evidence is quoted per row).
- [ ] The legacy unversioned `/api/` mount is removed, or kept with evidence
      of a live caller.
- [ ] The "Mobile (Flutter)" preview mode is either made to work or removed
      from `preview_modes`.

## Work Log

### 2026-09-23 - Filed from the web dead-code audit (L13, L14)

This is a product triage, so it could not be fixed inside a web dead-code PR.

### 2026-09-23 - Evidence gathered; owner decisions recorded

Evidence came from three research agents (route walk with `get_resolver()`,
client grep, git history, roadmap docs) plus one adversarial verifier. The
verifier ran probes against a test DB with Trefle and OpenAI patched, and it
confirmed every plant-ID/CMS claim, several of them as worse than first
reported.

**Owner decisions (2026-09-23):**

| Family | Decision | Reason / evidence |
|---|---|---|
| `apps.garden` (outdoor garden planner) | **REMOVE the whole app** | Off-brand for Houseplant MD (owner). No client, no API tests, no feature work since 2025-11. Its FCM bootstrap moves to `apps/core/firebase_config.py`. Production row count 2026-09-23 (`railway ssh --service plant_id_community`, `m.objects.count()` per model): **9 tables, 0 rows each**. |
| `apps.garden_calendar` | **KEEP** | "Still fairly useful" (owner). Mobile's client is todo 386. The Houseplant MD scope may trim beds, harvests and weather. |
| Plant ID v1 dead groups; Plant CMS v2 | **Owner asked for a thorough check first.** Every claim verified; removal plan below. | Verifier: `search_external` served 150/150 anonymous calls with no limit (every one hit Trefle). The other Trefle endpoints give anonymous callers the *authenticated* tier (~1000/h). `process_now` re-runs a paid diagnosis with no limit. The Wagtail plant `@action`s all resolve to `wagtail_serve`, so they 404. The demo seeder is broken three ways. |
| `/api/auth/token/` + `token/verify/` (SimpleJWT) | **REMOVE (security)** | A password grant with no rate limit and no lockout check. Nothing calls it. |
| Email unsubscribe / preferences | **Build properly** (owner) | Signed token and real templates. Today the templates are missing (500), it takes an unsigned `?user=<uuid>`, and `SITE_URL` may point at the wrong domain. |
| Blog newsletter | **Wire up** (owner) | Must add double opt-in and rate limits first: anyone can subscribe or unsubscribe any email today, and it leaks who is subscribed. No sender exists yet. |
| `me/care-reminders`, `me/dashboard-stats`, `me/onboarding`, `me/push-notifications` | **Wire up** (owner) | Each becomes its own feature todo. |
| Forum AI `summary/` | **Wire up** (web button) | Finished and tested; the only premium AI feature with no UI. |
| Forum AI `similar/` | **KEEP dark** | It waits on `FORUM_VECTOR_SEARCH_ENABLED` and a built index. |
| Blog v2 extras | **KEEP** for the mobile blog (todo 385) | The owner already decided this in todo 307. |
| Legacy unversioned `/api/` mount | **REMOVE** | No HTTP caller (299 duplicate routes). It is load-bearing only through root URL namespaces: `users:unsubscribe`, `users:oauth_callback`, `blog_api:*`. Those must move to `v1:` first. |
| `preview_modes` "Mobile (Flutter)" | **REMOVE** | The library never passes `mode`. There is no `plantid://` scheme on either platform. |

**Slice 1 (this PR): garden app removed.** Contents:

- `firebase_config.py` and its test moved to `apps/core`, with 55 references
  updated. The new path routes to the same inject domains.
- `apps.garden` removed from `INSTALLED_APPS` and from both URL mounts, and
  its package deleted.
- `apps/core/migrations/0003_drop_garden_tables.py`: `DROP TABLE IF EXISTS`
  child-first, no CASCADE; content types removed through the ORM so
  permissions cascade; the `django_migrations` rows deleted.

Proof on a scratch Postgres DB:

- Migrating with the pre-removal code created 9 garden tables, 9 content
  types, 36 permissions and 1 migration row.
- Migrating the same DB with this branch applied `core.0003` and left 0 of
  each. The 11 `garden_calendar_*` tables are untouched.

**Remaining slices of this todo (removals only; each wire-up is its own todo):**

- **Slice 2 (security, next):**
  - Remove SimpleJWT `api/auth/token/` and `token/verify/`.
  - Remove the dead Plant ID v1 groups: `species/*` including
    `search_external`; `characteristics`, `growth-info`, `search/*` and
    `enrich-plant-data` (the Trefle proxies); `results/*` and
    `regenerate-care`; `care-instructions`, `saved-care-instructions`,
    `disease-results`, `disease-database`, `saved-diagnoses` and
    `treatment-attempts`.
  - Rate-limit `disease-requests/<id>/process_now/`.
  - Remove the dead preview mode.
  - Keep every live model named in the verifier's claim 7.
- **Slice 3:** remove the Plant CMS v2 endpoints and their models:
  PlantCategory, PlantCareGuide, PlantSpeciesPage, PlantCategoryIndexPage and
  PlantCareBlocks. Take a production page/snippet row count first (the
  garden-style gate), and handle PlantCareGuide's blog references and the
  migration-graph dependencies (blog 0004 depends on plant_identification
  0005).
- **Slice 4:** remove the legacy unversioned `/api/` mount. It **depends on
  todo 408**: `users:unsubscribe` resolves only through that mount. Also move
  `users:oauth_callback`, `blog_api:plant_stats` and the middleware path lists
  to `/api/v1/`.

**Filed as feature todos:** 408 (unsubscribe, p2), 409 (newsletter, p2), 410
(care reminders), 411 (dashboard stats), 412 (onboarding plus the broken demo
seeder), 413 (web push), 414 (forum summary button).

### 2026-09-23 - Slice 1 merged and verified in production; slice 2 (security removals)

**Slice 1: PR #799, merged 21:45 UTC.** Production was checked on 2026-09-23
with a read-only `railway ssh`:

- `showmigrations core` shows `[X] 0003_drop_garden_tables`;
- introspection lists **no** `garden_*` tables (the calendar tables are
  separate and untouched).

**Slice 2 removed these, none of which had a client:**

- **SimpleJWT `api/auth/token/` and `token/verify/`.** It was an unthrottled
  password grant that bypassed the login view's rate limit and lockout. A new
  test pins both paths as 404. The bearer-auth and refresh tests now mint
  tokens with `RefreshToken.for_user`.
- **Plant ID v1 routes:**
  - `species/*`, including `search_external`. The verifier had shown 150 of 150
    anonymous requests reaching Trefle.
  - The Trefle proxies: `characteristics`, `growth-info`, `search/species` and
    `enrich-plant-data`. Anonymous callers got the authenticated tier, about
    1000/h.
  - `search/plants|diseases`.
  - `results/*`, including vote, accept, add_to_collection and the OpenAI
    `regenerate-care`.
  - `care-instructions`, `saved-care-instructions`, `disease-results`,
    `disease-database`, `saved-diagnoses` and `treatment-attempts`.
- **`disease-requests/<id>/process_now/`.** It is *removed*, where the slice
  plan said rate-limited. Its docstring said "for testing", no client calls
  it, and each call re-ran the paid plant.health diagnosis with no limit.
  Removing it is the stricter fix. `status/` and `results/` stay.
- **The dead "Mobile (Flutter)" preview mode**, its `plantid://` branch, and
  the two tests that pinned the dead behaviour. The web default mode is now
  pinned instead.
- **Five serializers left with no reference:** DiseaseCareInstructions,
  PlantDiseaseDatabase, SavedDiagnosis, SavedCareInstructions and
  TreatmentAttempt.

`views.py` went from 1667 lines to 195. All live models stay, per the
verifier's claim 7. Dropping the dead models (PlantDiseaseVote,
SavedDiagnosis, TreatmentAttempt, the Batch* models) is left for a later
slice, behind the production row-count gate.

**Verification:**

- Full backend pytest: 3581 passed, 8 skipped.
- `check` and `makemigrations --check` are clean.
- `spectacular --validate` exits 0. Its pre-existing errors fell from 212
  (49 unique) to 176 (41 unique), because the removed routes carried some of
  them.

**Slice 2 review (bundled /code-review): 0 blocking.**

- Leftovers fixed in the PR: the dead vote-URL helper and `APIClient` setup in
  `test_disease_vote_deduplication.py`, and the empty section header at the
  end of `views.py`.
- Carried to slice 3:
  - Stale docs still name removed routes:
    `backend/docs/API_DOCUMENTATION_IMPLEMENTATION.md:216` (`/api/auth/token/`),
    and the mobile `api_service.dart:254` and `services/README.md:49`
    (`/plant-identification/species/`).
  - `PlantSpecies.get_absolute_url` (`models.py:234`) already raised
    NoReverseMatch before this slice: it reverses `species_detail`, a name that
    never existed.
  - `plant_care_reminder_service.py:390` links to
    `/profile/care-instructions/<uuid>/`, whose API this slice removed. Revisit
    it with todo 410 (care reminders).

### 2026-09-23 - Slice 2 merged (PR #800); slice 3: Plant CMS v2 and dead models

**Slice 2** merged at 22:18 UTC.

**Production gate for slice 3** (2026-09-23, read-only `railway ssh`,
`count()` per model): **all 11 models held 0 rows.**

- PlantCategory, PlantCareGuide, PlantSpeciesPage, PlantCategoryIndexPage;
- PlantDiseaseVote, SavedDiagnosis, TreatmentAttempt;
- BatchIdentificationRequest, BatchIdentificationComparison,
  BatchIdentificationImage, BatchProcessingQueue.

(`PlantCareBlocks` is a StreamField block, not a table.)

**Slice 3 removed:**

- The 5 Wagtail v2 plant endpoints (`plant-species`, `plant-categories`,
  `care-guides`, `plants`, `plant-index`), plus `api/endpoints.py` and
  `api/serializers.py`.
- The 11 dead models, `PlantCareBlocks`, and the abstract
  `PlantIdentificationBasePage` (its only subclasses were removed). This cut
  `models.py` from 2810 lines to about 1570.
- The blog command `migrate_care_guides_to_blog` and its test file.
- The tests of removed code: `test_stock_meta_fields_site_based`,
  `test_search_wildcards`, `test_page_viewsets_versioning_and_wiring`,
  `test_disease_vote_deduplication`, and the PlantCategory N+1 test.
- The stale docs from the slice 2 review: `API_DOCUMENTATION_IMPLEMENTATION.md`,
  and the mobile `api_service.dart` and `services/README.md` doc examples.

**About migration `0027_remove_dead_cms_and_diagnosis_models`:**

- **The autodetector's output failed on a production-shaped DB**
  (`FieldDoesNotExist: TreatmentAttempt has no field named 'saved_diagnosis'`).
  `SavedDiagnosis.treatments_tried` is an M2M *through* TreatmentAttempt, and
  the generated field-by-field ops removed the FK after the M2M removal had
  already dropped it from state.
- The ops are now **hand-ordered**: remove the through-M2M, then `DeleteModel`
  child-first. Content types are removed through the ORM at the end.
  `makemigrations --check` reports "No changes detected", so the state matches.
- **Proof on a scratch Postgres DB migrated from current main:**
  - before: 11 tables, 11 content types, 44 permissions;
  - after `0027` (OK): 0 of each, and no leftover M2M or tag tables;
  - all 7 kept tables (PlantSpecies, UserPlant, PlantDiseaseResult,
    PlantDiseaseDatabase, DiseaseCareInstructions, SavedCareInstructions,
    PlantIdentificationVote) are present.

**Noted, not fixed (it predates this slice and is independent of it):**
`get_absolute_url` on PlantSpecies, PlantIdentificationRequest, UserPlant and
PlantDiseaseRequest (`models.py` ~230/453/741/920) reverses route names that
never existed (`species_detail`, `request_detail`, `user_plant_detail`,
`disease_request_detail`), so each raises NoReverseMatch if called. Nothing in
the app calls them. Fix or delete them in a later cleanup.

### 2026-09-23 - Slice 3 verified in production; slice 4 unblocked by todo 408

- **Slice 3 (PR #801) is verified in production.** A read-only `railway ssh`,
  running `showmigrations plant_identification` plus a table introspection,
  showed `plant_identification.0027_remove_dead_cms_and_diagnosis_models`
  applied at about 22:58 UTC, with `LEFTOVER []` (no removed-model tables
  remain).
- **Slice 4 (removing the legacy unversioned `/api/` mount) is unblocked for
  unsubscribe.** Todo 408 (PR #802) replaced `users:unsubscribe` with
  `v1:users:email_unsubscribe[_check]`, and `EmailService` no longer reverses
  any `users:` name.
- **Still to check before slice 4:** `users:oauth_callback` and `blog_api:*`,
  both from the earlier route walk. Also `templates/emails/forum_digest.html`'s
  `{% url 'users:email_preferences' %}`, which is not a live template (todo
  415).
