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
- **`logger.exception()` only works inside an `except` block** — elsewhere it
  logs `NoneType: None`. For `Signal.send_robust()` results, use
  `logger.error(..., exc_info=response)` (the returned exception carries
  `__traceback__`).
- **Idempotency-Key endpoints**: hash the user-supplied key (sha256) and scope
  it by endpoint + user; fingerprint route-params + payload (422 on reuse with
  a different request); replay the ORIGINAL status code, not 200; `cache.add()`
  an in-flight sentinel (short TTL, placed AFTER validation) → 409 for
  concurrent twins. See wagtail_forum/api/idempotency.py for the reference shape.
- **DRF cursor pagination `next`/`previous` are ABSOLUTE URLs** (built from the
  request host). Clients fetch them verbatim — do NOT re-prefix the API base
  (double-prefixing 404s). The page-fetch helper must accept either a relative
  path (first page) or an absolute cursor URL (subsequent pages).
- **Never name a custom OpenAPI auth scheme `cookieAuth`** — drf-spectacular's
  built-in SessionAuthentication scheme already claims that name (the
  `sessionid` cookie); a second identity under it triggers "2 components with
  identical names … different identities" and an incorrect schema. Name it for
  the actual cookie (`jwtCookieAuth` for `access_token`) — see
  `apps/users/schema.py`.
- **drf-spectacular pre/post-processing hooks must not share module-global
  state.** Two concurrent `SpectacularAPIView` regenerations interleave
  `.clear()`/`.add()` with iteration → silently missing schema entries or "Set
  changed size during iteration". Keep cross-hook state in `threading.local()`
  (reference: `plant_community_backend/api_schema.py`), import
  `django.conf.settings` inside the hook body (a top-level import added before
  its first use gets stripped by the formatter), and derive the path prefix
  from `SPECTACULAR_SETTINGS["SCHEMA_PATH_PREFIX"]` rather than re-hardcoding
  a regex that can drift.
- **Pin `filter_backends = []` on DRF generics views in reusable packages.** They
  inherit the host's `DEFAULT_FILTER_BACKENDS`; a global `OrderingFilter` lets any
  client `?ordering=` REPLACE the cursor paginator's ordering (un-pinning
  pinned-first lists) and 500 via dotted serializer sources
  (`?ordering=author__get_username` → `FieldError`). List order is a package
  contract, not client-selectable (audit 2026-07-11 Phase 6 R1).
- **An idempotent endpoint's replay must re-attach response headers, not just
  body + status.** A retried create that returns a `Location` drops it on replay
  unless the idempotency cache stores headers too — persist them
  (`remember(..., headers={"Location": ...})`) and re-apply them in the replay
  helper, or the replayed 201 silently differs from the original (todo 258 M35/L19).
- **Never hardcode a URL namespace in `reverse()` inside a reusable/mountable
  package.** `reverse("wagtail_forum_api:topic-detail", …)` 500s
  (`NoReverseMatch`) when the package is a bare root urlconf (no namespace) or
  nested under a host namespace (`v1:wagtail_forum_api`) — `app_name` only makes a
  namespace when `include()`d. Resolve within the live request instead:
  `ns = request.resolver_match.namespace; reverse(f"{ns}:name" if ns else "name", …)`
  (see `_created_location`, todo 258 L19).
