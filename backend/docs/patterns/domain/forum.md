# Forum Patterns (wagtail_forum)

**Last Updated**: 2026-06-21
**Status**: Accurate for the Wagtail-native forum (post machina retirement, PR #362)

> The previous version of this doc described the **retired** `apps/forum_integration/`
> system (`TrustLevelService`, `SpamDetectionService`, `warm_moderation_cache` — none
> of which exist anymore). It is archived at
> `docs/archive/forum-patterns-trust-spam-pre-wagtail.md`. This doc points to the live
> sources rather than re-documenting them, so it can't rot the same way.

## Where the forum lives

The forum is a reusable, Wagtail-native package — no django-machina, no
`forum_integration` (both fully retired in PR #362):

- **`backend/packages/wagtail_forum/`** — the package. Boards are Wagtail **Pages**;
  topics and posts are feature-rich **snippets** (moderation workflow, revisions,
  locking, search). The package core imports nothing host-specific — it uses
  `settings.AUTH_USER_MODEL`, never a concrete user model.
  - `spam/` — pluggable spam detection (`base.py` interface, `heuristic.py` default).
  - `models/moderation.py` — moderation state + actions.
  - `api/` — optional headless DRF API: `serializers.py`, `views.py`, `urls.py`,
    `pagination.py`, `idempotency.py`, `exceptions.py`. **Body HTML is sanitized
    through `api/sanitize.py`** before storage.
  - `tests/` — `test_spam.py`, `test_moderation_task.py`, and the rest of the suite.
- **`backend/apps/forum_host/`** — the host integration: rate-limit wrappers
  (`api.py`), route mounting (`api_urls.py`), and host settings. Throttling lives
  here by design (the package is host-agnostic).
- **`backend/apps/forum/management/`** — management commands (e.g. `seed_default_forum`).

## Authoritative references (read these, not this file)

- **Package overview**: `backend/packages/wagtail_forum/README.md`.
- **Binding rules** (auto-injected before forum edits): `docs/rules/forum.md` — the
  compact always/never checklist (numeric-default footgun, savepoint-on-`IntegrityError`,
  `Ratelimited` carries no `.rate`, forum is always-on, etc.).
- **Spam / moderation / API contracts**: the package modules above and their tests
  are the source of truth — prefer reading them over any prose summary.

## Key invariants (full list in `docs/rules/forum.md`)

- **The forum is always-on** — the `ENABLE_FORUM` flag was a dead no-op and was
  removed (PR #371). Do not re-introduce a gate without wiring `INSTALLED_APPS` +
  URL mounting + CI.
- **Host applies throttling, package does not** — rate limits are `forum_host`
  wrappers; a route-parity test fails if the host doesn't mount a new package route.
- **Idempotency** for write endpoints follows `api/idempotency.py` (hash the
  user key, scope by endpoint+user, replay the original status, `cache.add()` an
  in-flight sentinel → 409 on concurrent twins).
- **Visibility**: filter page querysets with `.live().public()`; gate child-object
  queries via the visible-board set (`PageViewRestriction` is not auto-enforced in
  custom views/APIs).

## Moderation permission scope is global, deliberately (audit M19)

Moderation is one flat `"Forum Moderators"` group (`apps/forum_host/bootstrap.py`)
with `change_topic`/`change_post` etc. — there is no per-board moderator concept.
This is a **deliberate decision, not an oversight**:

- `Topic`/`Post` are snippets, not Pages — Wagtail's `GroupPagePermission` (which
  `ForumBoard`, itself a Page, could otherwise use) has no snippet analog. A
  board-scoped check would mean a new group↔board mapping model consulted from
  every permission check site (`Post.edit_block`/`delete_block`,
  `_edit_is_trusted`'s `acting_as_moderator`, the bulk-unpublish action's
  `check_perm`, the SnippetViewSet permission gate) — high blast radius through
  security-critical code.
  - `seed_default_forum` creates exactly one board. There is no product signal
    (no second board, no request for delegated moderators) that justifies that
    blast radius today (YAGNI, root `CLAUDE.md`).
- **Revisit trigger**: when a second board ships AND it needs a moderator distinct
  from the global group, design the group↔board mapping then, against a real
  requirement instead of a speculative one.
