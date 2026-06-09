# Retire django-machina — Design

- **Date:** 2026-06-08
- **Status:** Approved (ready for writing-plans)
- **Source todo:** `todos/220-pending-p2-wagtail-forum-retire-machina.md`
- **Predecessor:** `docs/superpowers/specs/2026-06-06-wagtail-native-forum-package-design.md` (Spec 1, Plans 1A–1D-T3 — the new `wagtail_forum` package + `apps.forum_host`, now live on `main` at `/api/v1/forum/`).
- **Scope label:** Plan 1D-T4, re-specced. This is the deferred final piece of the forum migration: removing django-machina + `apps.forum_integration`.

## 1. Context

The Wagtail-native forum (`wagtail_forum` package + `apps.forum_host`) is built, merged to `main`, and serving all forum routes. The legacy forum routes are already removed (Plan 1D-T1). The one remaining piece — retiring django-machina, `django-mptt`, `django-haystack`, and `apps.forum_integration` — was deferred because the original "thin greenfield removal" plan assumed machina was isolated host-wiring. It is not: machina is imported at **module top level** in core account code (`apps/users/services.py`), so a naïve uninstall crashes `apps.users.services` on import and takes the whole backend down.

The interim state (new forum live, machina dormant-but-installed) is coherent and deployable. This spec defines how to remove machina safely.

## 2. Key finding (the reframe)

The todo framed this as a risky rewrite of *live* account/dashboard code. Verification on 2026-06-08 shows the opposite: **every machina touchpoint in core account code is dead or unreachable.** Deleting it is behavior-preserving.

Evidence (caller-trace greps over `backend/apps`, **not** excluding `forum_integration`):

| Symbol | Machina coupling | Callers outside its own definition |
|---|---|---|
| `TrustLevelService.setup_forum_permissions` | `Forum`, `ForumPermission`, `GroupForumPermission` | **0** |
| `TrustLevelService.check_user_can_attach_files` | `PermissionHandler` | 1 — the `forum_permissions` view (itself unused, being deleted) |
| `ForumPostService` (whole class) | machina `Post` | **0** |
| `_create_demo_forum_posts` / demo cleanup branch | machina `Forum`/`Post`/`Topic` | internal only, `ENABLE_FORUM`-gated (default `False`) |

The module-level imports/lookups in `services.py` (L20–21, L35–38) feed only `setup_forum_permissions` and `check_user_can_attach_files` — both provably dead. So removing the import-time blocker is safe.

The three machina-coupled endpoints in `apps/users/views.py` — `forum_activity`, `dashboard_stats`, `forum_permissions` — are **not consumed by any web (`web/src`) or mobile (`plant_community_mobile/lib`) client and have no backend tests.** Blast radius of changing them is minimal.

The new forum already owns trust levels **independently**: `wagtail_forum` ships its own `ForumProfile.trust_level` + `post_count` + signals + workflow autopublish. The old `User.trust_level` → machina bridge is vestigial. (`User.trust_level` the model field stays — it has live consumers in `apps/users/signals.py` and `apps/users/auditlog.py`. Only the machina bridge is removed.)

## 3. Goals

1. `apps/users/services.py` imports cleanly with machina **uninstalled**.
2. Account create/delete + `dashboard_stats` keep working without machina.
3. `django-machina`, `django-mptt`, `django-haystack` removed from `requirements.txt` and uninstalled.
4. `apps/forum_integration/` and `apps/search/` deleted.
5. `grep -rn "machina\|forum_integration"` over `backend/apps` + `backend/plant_community_backend` is clean (only intentional comments, if any).
6. `manage.py check` clean, `makemigrations --check` clean, `spectacular` OpenAPI validate clean, full `pytest apps packages` green.

## 4. Non-goals (explicit, conscious decisions)

- **Re-wiring `User.trust_level` / `posts_count_verified` to new-forum activity.** `wagtail_forum` maintains its own `ForumProfile.trust_level`/`post_count`. The machina-era User-level bridge (`ForumPostService.update_user_post_count`, `setup_forum_permissions`) is **retired, not reconnected**. If a future product need wants account-level trust driven by the new forum, that is its own spec.
- **React/Flutter client changes.** No client consumes the removed endpoints today, so nothing to update now. Any future re-add of a "my forum activity" endpoint is Spec 2.
- **Removing now-dead *non-machina* helpers.** Some non-machina methods (e.g. `create_trust_level_groups`, `update_all_user_trust_levels`) may lose their last caller once machina methods go. They are left in place to keep this change machina-scoped and behavior-preserving; flagged as a future cleanup, not done here.

## 5. Approach

**Decouple-first, then delete, test-gated** — one feature branch, ordered commits, full `pytest apps packages` green after each. Machina stays installed until the final commit, so every intermediate state is runnable and bisectable.

Rejected alternatives:

- *Big-bang single commit* — no bisect signal, harder to review account-adjacent code.
- *Make-removable-first* (lazy imports + feature-flag, delete later, todo's Option 2) — designed for *live* coupling; the code is provably dead, so the intermediate is pure churn.

## 6. Detailed design

### 6.1 `apps/users/services.py` — sever machina

- Remove module-level machina imports + `apps.get_model`/`get_class` lookups (`from machina...` L20–21; the 4 `ForumPermission`/`GroupForumPermission`/`UserForumPermission`/`PermissionHandler` lines L35–38). **This is the import-time blocker.**
- Delete dead machina methods: `TrustLevelService.setup_forum_permissions`, `TrustLevelService.check_user_can_attach_files`, and the whole `ForumPostService` class.
- Demo data: delete `_create_demo_forum_posts`, the `_is_forum_enabled()`-gated forum-demo call in `create_demo_data`, and the machina branch in `cleanup_demo_data`. Demo plant-IDs + care reminders are untouched.
- Retain the `ENABLE_FORUM` setting var (todo-sanctioned). `_is_forum_enabled()` loses its only purpose (gating the removed forum demo) → remove it.
- Keep all non-machina trust methods.

### 6.2 `apps/users/views.py` + `apps/users/urls.py`

- **Delete** `forum_activity` (uses machina `Post`/`Topic` + `apps.forum_integration.serializers`) and its route (`urls.py` L45).
- **Delete** `forum_permissions` (uses machina `Forum` + `check_user_can_attach_files`) and its route (`urls.py` L48). This removes the last machina import in `views.py` and the sole caller of `check_user_can_attach_files`.
- **Keep** `dashboard_stats` (route `urls.py` L46) and **repoint** its forum portion to `wagtail_forum.models.Topic`/`Post`. Response shape preserved.

#### `dashboard_stats` repoint mapping

| machina (old) | wagtail_forum (new) |
|---|---|
| `Topic.subject` | `Topic.title` |
| `Topic.poster` / `Post.poster` | `Topic.author` / `Post.author` |
| `Topic.created` / `Post.created` | `Topic.created_at` / `Post.created_at` |
| `approved=True` | `live=True` |
| `Topic.forum.name` | `Topic.board.title` (board is a Wagtail `Page`) |
| exclude first posts via `Topic.first_post_id` | filter `Post.is_opening_post=False` |
| `select_related("forum")` | `select_related("board")` |
| `select_related("topic", "topic__forum")` | `select_related("topic", "topic__board")` |
| url `/forum/topic/{topic.id}` | `/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}` |

- `forum_stats`: `total_topics`/`topics_this_month` from `Topic.objects.filter(author=user, live=True)`; `total_posts`/`posts_this_month` from `Post.objects.filter(author=user, live=True)`.
- `recent_activity` forum entries: topics → `title` / `board.title` / `created_at`; posts → `Post.objects.filter(author=user, live=True, is_opening_post=False)` with `topic.title` / `topic.board.title`.
- `total_activity_score` math unchanged (still reads `forum_stats["total_topics"]` / `["total_posts"]`).
- **`url` field — repoint in commit 1, not deferred.** The legacy `/forum/topic/{topic.id}` matches **no current route**. The live web forum addresses a thread as `/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}` (id is the lookup key, slug decorative — see `web/src/utils/forumUrls.ts` + its test). Build that exact shape so the response shape stays consistent (every `recent_activity` item keeps a `url`) and never serves a broken link. Requires `board.id`/`board.slug`/`topic.slug` in the `.only()` selection (a `forumUrls`-style helper, kept in the view, is fine — backend already owned this URL string).

### 6.3 Delete `apps/forum_integration/`

- Remove the whole app (models, 5 migrations, API, serializers, templates, mgmt commands, `sanitization.py`, tests).
- Drop the two `pytest.ini` ignore lines (L20 `--ignore=apps/forum_integration/tests.py`, L21 `--ignore=apps/forum_integration/tests`). Pytest count is unchanged by deletion (those tests were already ignored).
- Verified: no other app's migrations declare a dependency on `forum_integration` migrations.

### 6.4 Delete `apps/search/`

- Remove the whole app directory. Its machina-importing files (`signals.py`, `services/search_service.py`, `views.py`, `migrations/0003_simple_search_vectors.py`) are **internal to the app** and go with the directory — there is no separate import to chase elsewhere.
- Remove the **only** external references (verified 2026-06-08, these are the complete set): the commented `LOCAL_APPS` line (`settings.py` L195) and the two commented urlconf includes (`urls.py` L126/L146). No stray `import apps.search` / `from apps.search` exists outside the app. (`settings.py` L542 is an unrelated OpenAPI tag literally named "search" — keep it.)
- Verified: no other app's migrations depend on `search` migrations. The new `wagtail_forum` ships its own search endpoint, so no capability is lost.

### 6.5 `plant_community_backend/settings.py` — remove machina footprint

Remove: `MACHINA_APPS` (incl. `machina.apps.forum_search`), the `ENABLE_FORUM`-gated `LOCAL_APPS` insert + `INSTALLED_APPS += MACHINA_APPS`, `MACHINA_*` config block, `HAYSTACK_CONNECTIONS`, machina context processors, machina template dir, `machina_attachments` cache entries, commented machina middleware. Collapse the now-empty `if ENABLE_FORUM:` blocks.

**Retain:** `ENABLE_FORUM` setting var (L169) and `wagtail.search` (L137 — Wagtail's own, not machina).

### 6.6 `requirements.txt`

Remove `django-machina==1.3.1`, `django-mptt==0.18.0`, `django-haystack==3.3.0`; `pip uninstall` from the venv.

### 6.7 `plant_community_backend/urls.py`

Confirm no residual machina / `forum_integration` route references (legacy include already removed in 1D-T1).

### 6.8 Data

Greenfield — no real forum data, so no data migration. `migrate forum_integration zero` / `forum_conversation zero` are no-ops on a fresh DB. For a developer cleaning an existing dev DB, run those `zero` migrations **while the apps are still in `INSTALLED_APPS`** (before commit 2/3). Not required for CI (fresh test DB each run).

## 7. Sequencing

Branch off `main` (e.g. `refactor/retire-machina`). One PR, ordered commits:

- **Commit 1 — decouple account code.** §6.1 + §6.2 (`services.py`, `views.py`, `urls.py`) + the new `dashboard_stats` test. Machina still installed. Run full `pytest apps packages`.
- **Commit 2 — delete dead apps.** §6.3 + §6.4 (`forum_integration`, `search`, `pytest.ini` ignore lines, commented refs). Run full suite + `manage.py check` **+ `makemigrations --check`** — the latter immediately after the deletions, to catch any cross-app migration dependency that slipped in between the 2026-06-08 verification and the branch cut.
- **Commit 3 — uninstall machina.** §6.5 + §6.6 + §6.7. `pip uninstall django-machina django-mptt django-haystack`. Run `manage.py check`, `makemigrations --check`, `spectacular --validate`, full `pytest apps packages`.

After commit 3: run the §3 acceptance greps and confirm clean.

## 8. Testing strategy

- The existing suite is the safety net for behavior-preserving deletions — run full `pytest apps packages` after every commit.
- **New test (the one piece of new behavior):** `dashboard_stats` against `wagtail_forum`. A user with `wagtail_forum` `Topic`/`Post` rows (live and draft) gets correct `forum_stats` (only `live=True` counted), correct `recent_activity` forum entries (including the repointed `url`), and the endpoint returns 200 with machina uninstalled. There is no existing `dashboard_stats` test, so this is net-new.
- **Commit 1 confirmation:** run `apps.users` tests. `apps/users/signals.py` (trust-upgrade logging) and `apps/users/auditlog.py` (audits the `trust_level` field) are **verified machina-free** and depend only on the retained `User.trust_level` field — so severing the machina bridge must not regress them.
- **Fixtures:** verified there is no machina/`forum_integration` reference in `pytest.ini` (beyond the two `--ignore` lines) or in any `conftest.py` — no fixture cleanup required.
- Final gates: `manage.py check`, `makemigrations --check` (no orphan migrations), `spectacular` OpenAPI schema validates (criterion: `dashboard_stats` still in the schema), acceptance greps clean.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Cross-app migration depends on `forum_integration`/`search` migrations | **Verified none** (2026-06-08). Re-check during plan if migrations change. |
| Hidden machina import via app-config side effects | `forum_host` verified machina-free; full suite + `manage.py check` after each commit catches import-time regressions. |
| `dashboard_stats` repoint changes forum-stat semantics (now counts `wagtail_forum` live content) | Acceptable — endpoint is unused by clients and the new semantics are more correct. Covered by the new test. |
| Stale `recent_activity` `url` values point at legacy `/forum/topic/{id}` (no matching route) | Resolved in commit 1: repoint to the live web scheme `/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}` (§6.2). No client consumes it today, so no client coordination needed. |
| Backend hard-codes a frontend URL convention (the `{id}-{slug}` shape) | Pre-existing — the old code already hard-coded `/forum/topic/{id}`. This corrects it to match live routes rather than introducing new coupling. If the web route scheme changes, this one helper in `users/views.py` is the single update point. |

## 10. Acceptance criteria (from todo 220)

- [ ] `grep -rn "machina\|forum_integration" backend/apps backend/plant_community_backend --include=*.py` → clean (or only intentional comments).
- [ ] `apps/users/services.py` imports cleanly with machina uninstalled; account create/delete + `dashboard_stats` work without machina.
- [ ] `django-machina`, `django-mptt`, `django-haystack` removed from `requirements.txt` and uninstalled.
- [ ] `apps/forum_integration/` deleted; `apps/search/` deleted.
- [ ] `manage.py check` clean; `makemigrations --check` clean; full `pytest apps packages` green.

## 11. Open questions

None — `apps/search` resolved to **delete**; `dashboard_stats` resolved to **repoint**; `forum_permissions` resolved to **delete**.
