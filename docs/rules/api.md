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
- **`strip_tags` is not an HTML→text converter** — it substitutes nothing for a tag
  and decodes no entities, so `'<p>a</p><p>b</p>'` → `'ab'` and `'<p>&nbsp;</p>'` →
  the truthy `'&nbsp;'` (passing a `if not text` empty-guard). Wherever the output is
  consumed as prose (LLM prompt, email body, excerpt, search doc), substitute block
  boundaries with newlines first, then strip, then `html.unescape`. Test it with a
  MULTI-block fixture and an entity fixture — a single-`<p>` fixture cannot exhibit
  the bug (shipped past 20 passing tests, todo 275). Prefer walking StreamField
  blocks (`plain_text_excerpt`) when the source is structured.
- **Never override the decorated method on a `method_decorator`-wrapped view.**
  `@_throttled("search", "GET")` wraps whatever `get` the MRO resolves at
  class-creation time, so `class X(ThrottledSearchView)` defining its own `get`
  REPLACES the wrapper and ships the endpoint unthrottled — silently, since every
  functional test still passes. Add behaviour as a mixin composed *ahead* of the
  base and apply the decorator to the composed class; re-declare `@extend_schema`
  there too, or the OpenAPI description reverts while the response shape changed.
- **One AI cost centre, one budget counter, peek-then-consume.** Never share a cache
  key between features (non-commensurable unit costs, and one feature's cap then
  triggers another's degrade posture), and never `check-and-increment`: charge only
  after the provider actually returned, so an outage cannot drain the cap through
  failed attempts. An empty-but-successful response IS a charge — it was billed.
  See `backend/docs/patterns/domain/forum.md`.
- **One status covering both permanent and transient failures needs a machine-readable
  `code`.** `compose_assist` returned 503 for three unrelated reasons — feature flag
  off (permanent) vs provider error/timeout/empty completion (transient) — so the web
  client's `permanent = status === 503` disabled its button for the whole session on
  the first provider blip, blaming the user's account. Add a stable `code` to the body
  (`"disabled"` vs `"unavailable"`) and have clients branch on THAT; the
  transient/permanent split is a product fact, not an HTTP one. Corollary: a client
  latch that caches a failure verdict must be keyed to (or cleared on) whatever the
  verdict depends on — a 403 meaning "not premium" must not outlive the account.
- **`ListField(max_length=…)` cannot bound the work a request triggers.** DRF
  appends it as a `MaxLengthValidator` in `self.validators`, which run in
  `run_validation` AFTER `to_internal_value` has already child-validated every
  element — so a caller can still pay for ~1M items inside
  `DATA_UPLOAD_MAX_MEMORY_SIZE`. Check the raw length FIRST in a `to_internal_value`
  override (same "bound it before you parse it" shape as `MAX_BODY_BLOCKS` in
  `wagtail_forum/api/sanitize.py`). Same trap for any post-parse bound: a limit
  enforced after the expensive step is documentation, not a limit. Pair it with
  O(1) dedup — an `if x not in list` accumulator over request-controlled input is
  O(n^2) (todo 276: 30k tags = 2.24s).
- **DRF's `request.data` MERGES POST and FILES under `MultiPartParser`** — so a
  field you expect as text can arrive as an `UploadedFile`, and any string
  method on it raises `AttributeError` → **500**, not 400. `(request.data.get("alt")
  or "").strip()` is the shape that bites (todo 281). Guard with
  `isinstance(value, str)` and treat anything else as absent. Happy-path tests
  send the field as a field and never exercise this — write the file-part case
  explicitly for every text field on a multipart endpoint.
