# Forum — binding rules

Compact checklist auto-injected before edits to the forum code. Long-form:
`backend/packages/wagtail_forum/README.md`.

- **Forum code lives in three places** (django-machina and `apps/forum_integration/`
  were fully retired, PR #362): the reusable package `backend/packages/wagtail_forum/`
  (boards are Wagtail Pages; topics/posts are snippets; optional DRF API), the host
  integration app `backend/apps/forum_host/`, and management commands in
  `backend/apps/forum/management/`. The package core must import nothing
  host-specific — use `settings.AUTH_USER_MODEL`, never a concrete user model.
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
