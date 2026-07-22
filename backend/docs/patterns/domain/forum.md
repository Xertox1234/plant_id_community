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

## Image blocks are scoped to an allowed-uploader set, not just collection membership (audit L21)

The forum image collection (`collections.get_forum_image_collection()`) is a
single shared collection across every member — collection-membership alone
(audit L5's IDOR-by-reference fix) stops a body from referencing an image
outside the forum entirely, but does **not** stop one member from embedding
another member's upload, since Wagtail's own `Image.uploaded_by_user` was
recorded at upload time but never checked.

`api/sanitize.py::validate_forum_body(value, allowed_uploader_ids)` now takes
a required second argument: the set of user ids (a `None` member is legal —
see below) whose uploads may be referenced. The three write serializers
(`_ForumBodyContract` in `api/serializers.py`) compute this per request:

- **Create** (`TopicCreateSerializer`/`ReplyCreateSerializer`): just the
  acting `request.user` — no post exists yet.
- **Edit** (`PostEditSerializer`): `request.user` **plus** the post's
  pre-existing `author_id` (passed via `context={"existing_author_id": ...}`
  at the view call site). PATCH resends the *entire* body — a moderator
  editing someone else's post while keeping the author's existing image
  blocks must not have them rejected just because the editor changed.

**`None` is a legal member of `allowed_uploader_ids`**, and it is handled with
an explicit `Q(uploaded_by_user_id__isnull=True)` branch, *not*
`uploaded_by_user_id__in={..., None}` — SQL's `IN (NULL)` is never true, even
for a row whose value actually is `NULL` (caught by a test before this ever
reached review). `None` matters because Wagtail's `Image.uploaded_by_user` and
`Post.author` both go `SET_NULL` together on account deletion — a deleted
author's pre-existing images grandfather in automatically without any special
casing, since `existing_author_id` is already `None` in that case.

The moderator-edit carve-out is intentionally narrow: it grandfathers the
POST's existing author, not "any image a privileged user chooses" — a
moderator cannot smuggle in a *different*, unrelated member's image while
editing someone else's post (pinned by
`test_moderator_edit_cannot_smuggle_in_a_different_members_image`).

## LLM spam backend (optional, host-side — todo 255 slice 2 / H13)

The package ships one spam check (`HeuristicSpamBackend`: banned words + link
count) and a one-setting swap, `WAGTAILFORUM_SPAM_BACKEND`. `apps/forum_host/`
adds `LLMSpamBackend` (`apps/forum_host/spam.py`), a **heuristic-first
composite** that screens what the heuristic passes through `generate_ai_text()`.
It ships **dormant** — enable per-environment with:

    WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend

(requires a working `OPENAI_API_KEY`.)

`check()` runs synchronously inside the moderation workflow's
`@transaction.atomic` publish path, so the LLM call is bounded by a hard
wall-clock timeout (`SPAM_LLM_TIMEOUT_SECONDS`, a `ThreadPoolExecutor` +
`future.result(timeout=…)`). Two deliberate, distinct failure postures:

- **Provider failure** (timeout / exception / unparseable reply) → **fail
  closed**: returns a rejected `SpamResult` so the post follows the same
  reject → pending-draft path a heuristic flag takes (a normal `reject`, not a
  raise — a raise would roll the workflow back into a limbo draft with no
  moderation-queue entry). Matches `workflow.py`'s "FAIL CLOSED" posture.
- **Global AI budget exhausted** (`AIRateLimiter.check_global_limit()`) →
  **degrade to heuristic** (publish): a cost decision, not an outage.

Definitive `CLEAN`/`SPAM` verdicts are cached in Redis by
`sha256(text)` + prompt version; transient failures are never cached. All
tunables live in `apps/forum_host/constants.py` (`SPAM_LLM_*`).
