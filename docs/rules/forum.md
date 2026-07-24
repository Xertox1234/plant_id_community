# Forum — binding rules

Compact checklist auto-injected before edits to the forum code. Long-form:
`backend/packages/wagtail_forum/README.md`.

- **Forum code lives in three places** (django-machina and `apps/forum_integration/`
  were fully retired, PR #362): the reusable package `backend/packages/wagtail_forum/`
  (boards are Wagtail Pages; topics/posts are snippets; optional DRF API), the host
  integration app `backend/apps/forum_host/`, and management commands in
  `backend/apps/forum/management/`. The package core must import nothing
  host-specific — use `settings.AUTH_USER_MODEL`, never a concrete user model.
- **Host-agnostic also covers instance attributes, not just the FK type.**
  `settings.AUTH_USER_MODEL` avoids a hardcoded FK, but package code (e.g.
  `wagtail_forum/api/`) can still break the contract by reading a property
  that only exists on THIS host's custom User model (e.g. `.display_name`).
  Use `user.get_full_name() or user.get_username()` instead — both are part
  of Django's base `AbstractBaseUser`/`AbstractUser` contract, so they work
  for any host. Mirrors `PostAuthorSerializer.get_display_name`; see the fix
  in `wagtail_forum/api/user_search.py` (todo 253 slice 4 review, "most
  significant single finding"). Note: a package-OWNED model can legitimately
  have its own `display_name` field (e.g. `models/profiles.py`'s `Profile`) —
  the rule is about reading a *host User model's* attributes, not about the
  string "display_name" itself.
- **The forum is always-on — there is no `ENABLE_FORUM` flag.** It was a dead
  no-op after the machina retirement (defined but used nowhere) and was removed
  2026-06-10. Do not re-introduce a gate without wiring it to `INSTALLED_APPS`
  AND URL mounting AND CI, and remember `INSTALLED_APPS` gating is evaluated at
  import time (`@override_settings` cannot re-register apps — use a subprocess).
- **Never use `or` as a numeric default where 0 is valid** — `(max_order or -1) + 1` fails
  when `max_order` is 0 because `0 or -1 == -1`. Use `(max_order if max_order is not None else -1) + 1`.
  Also, auto-assign logic in `save()` must be insert-only (`self.pk is None`), or it re-fires on UPDATE.
- **Catch DB errors inside `atomic()` only with a savepoint** — catching an `IntegrityError` inside
  an outer `transaction.atomic()` without a nested `with transaction.atomic():` poisons the connection
  (`TransactionManagementError` on the next query). Wrap each risky insert in its own savepoint so
  partial-success semantics don't break the outer transaction.
- **`Ratelimited` does not carry the rate string** — `django-ratelimit 4.x` raises a bare
  `class Ratelimited(PermissionDenied): pass` with no `.rate` attribute. Use the
  `apps/core/ratelimit.py` wrapper that catches `Ratelimited` and re-raises `RatelimitedWithRate(rate)`
  so the exception handler can derive the real `Retry-After` window instead of hardcoding a constant.
- **The frozen-topic guard is deliberately symmetric**: PATCH and DELETE are both
  blocked (409) on a closed/locked topic **including for moderators** — a product
  decision for mirror-PATCH predictability, not a bug; a moderator reopens the
  topic to remove content. Don't add a moderator bypass without a new product
  decision. (The earlier "reply_count desync" justification was wrong —
  `unpublish()`'s recount is state-independent.) Policy is single-sourced in
  `Post.edit_block`/`delete_block` (`wagtail_forum/models/posts.py`).
- **Register a `transaction.on_commit(...)` side-effect only INSIDE the `try`
  that guards its preceding write**, right after the write succeeds — never
  after the whole `try/except` (unconditionally). A caught write failure must
  not still deliver the side-effect (e.g. a push notification for a
  `Notification` row that was never persisted). Caught by kimi-review, not the
  domain reviewers, in `forum_host/notifications.py`'s `reply_added` branch
  (todo 253 slice 1) — see `backend/docs/patterns/architecture/services.md`.
- **HOST-side forum views/tasks reading topic or post content MUST enforce board
  visibility** — `_get_visible_topic(topic_id)` (404s hidden/restricted, no
  existence leak) or `Topic.objects.filter(..., board__in=_visible_boards())`
  (both from `wagtail_forum.api.views`). `PageViewRestriction` is NOT
  auto-enforced. This applies to NEW endpoint types too: the H14 AI
  thread-summary endpoint (`apps/forum_host/summary.py`) shipped without it and
  a CI security review flagged a HIGH authz bypass — a premium user could
  summarize a restricted board's thread (todo 255 slice 3). The package-only
  visibility trigger did not cover `apps/forum_host/`; a broadened trigger now
  does. Filter the SOURCE too (e.g. a vector-index queryset), not just the
  response — never embed/cache restricted content.
- **Public crawl surfaces enforce board visibility too.** The forum
  `sitemap.xml` + RSS feed (`apps/forum_host/{sitemaps,feeds}.py`, todo 256 H9)
  are the widest-blast-radius surface — anonymous, cacheable, search-indexed —
  so both filter topics through `board__in=_visible_boards()` (`.live().public()`)
  and list only `ForumIndex.objects.live().public()` boards. `.public()` excludes
  a restricted board AND every descendant of a restricted ancestor, so a
  restriction on the `ForumIndex` hides the whole tree; a coverage test must
  exercise the ancestor case, not just a directly-restricted board. Draft
  (`live=False`) topics need their own exclusion test per surface — the sitemap's
  and the feed's `live=True` guards are independent.
- **A settable image/file reference on a user resource (e.g. profile `avatar_id`)
  must be validated against the caller's OWN uploads within the allowed collection
  before assignment** — `uploaded_by_user=<caller>` AND
  `collection=get_forum_image_collection()`, the same two-part check that gates
  inline images (audit L21). Never trust a bare image id; a `None` clear needs no
  ownership check. See `docs/patterns/domain/forum.md` (unified author contract).
- **Serialize every forum author through the single `serialize_forum_author` helper**
  (topic `author`/`last_post_author`, post `author`, notification `actor`) so the
  shape and the `[deleted]` sentinel OBJECT stay identical; `select_related` the
  full `author__wagtail_forum_profile__avatar` chain to keep list pins flat.
