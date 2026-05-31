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
