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
- **Adding `choices=` to an existing WRITABLE field is a breaking change.** DRF
  maps a model field with `choices` to a `ChoiceField`, so writes carrying any
  value outside the enum start returning 400. Before adding it, enumerate every
  value existing clients send (grep mobile, web, AND tests) and make the new enum
  a superset (+ an `other` escape hatch). A field with `choices` is also what
  makes `get_FOO_display()` exist and drf-spectacular emit an enum.
- **`Retry-After` must reflect the actual rate window, not a constant.**
  `django-ratelimit`'s `Ratelimited` carries no rate (the decorator discards it),
  so capture the rate at the decorator site (`apps/core/ratelimit.py` wraps it and
  re-raises with `.rate`) and map it (`/m`→60, `/h`→3600, …) in the handler.
