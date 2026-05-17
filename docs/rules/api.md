# API & DRF — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/architecture/viewsets.md`, `.../rate-limiting.md`.

- **`get_permissions()` overrides MUST call `super()`** so `@action`-level
  `permission_classes` still apply. This is a recurring security hole.
- **Rate limiting returns 429, not 403.** `django-ratelimit`'s `Ratelimited`
  subclasses `PermissionDenied`, so DRF emits 403 by default. A custom exception
  handler must check `isinstance(exc, Ratelimited)` and return 429 + `Retry-After`.
- **Type-hint service methods** — params and return types on anything in a
  service layer or called across app boundaries.
- **Bracketed log prefixes** — `logger.info("[CACHE] ...")`, `[AUTH]`, `[PLANT_ID]`
  — so logs are greppable by subsystem.
- Serializer field changes are API-contract changes — version or document them.
- Validate at the boundary (request data); trust internal calls.
