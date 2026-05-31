# Forum — binding rules

Compact checklist auto-injected before edits to `forum_integration/`. Long-form:
`backend/docs/patterns/domain/forum.md`.

- **Real app is `forum_integration/`**, not `forum/`. Machina models come from
  `machina.apps.forum.*` (third-party); our logic lives in `apps/forum_integration/`.
- **Never hardcode trust-level thresholds** — always use `TrustLevelService.get_trust_level()`
  or import from `apps/forum_integration/constants.py`. Hardcoded `timedelta(days=7)` etc.
  diverge silently from the service definition.
- **Spam keyword scoring uses `max()`, not `sum()`** — summing inflates the score
  across categories. Use the highest category score.
- **Detail `@action` endpoints must include the `uuid` lookup parameter** — omitting it
  causes `CanUploadImages` and other trust-level permission classes to silently fail.
  (Same as `get_permissions()` + `super()` rule in `docs/rules/api.md`.)
- **`SpamDetectionService` caches internally** — do not wrap calls in your own cache.
  Ensure Redis is running; a missing cache falls back to DB on every check.
- **`ENABLE_FORUM` is evaluated at import time** — `@override_settings(ENABLE_FORUM=True)`
  cannot re-register apps mid-test. Use a subprocess with the env var set to test startup
  paths that depend on `INSTALLED_APPS`.
- Run `python manage.py warm_moderation_cache` post-deploy to avoid cold-start penalty on
  the moderation dashboard.
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
