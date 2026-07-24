# wagtail-forum

A reusable, Wagtail-native community forum. Boards are Wagtail Pages; topics and
posts are feature-rich snippets (moderation workflow, revisions, locking, search).
Headless DRF API is optional (`pip install wagtail-forum[api]`).

The core imports nothing host-specific and uses `settings.AUTH_USER_MODEL`.

## Search backend

`/search/` delegates to `wagtail.search.backends.get_search_backend()`. With the
default database fallback backend this degrades to an un-indexed `icontains`
scan over topic titles (bounded at 50 results). For production traffic,
configure a real backend (Elasticsearch/OpenSearch) or, on PostgreSQL, use
Wagtail's `database` backend (full-text search) and consider a `pg_trgm` GIN
index on `wagtail_forum_topic.title`.

## Rate limiting

The package ships no throttling by design — auth and rate limits are the host's
responsibility. Wrap the API views (see `apps/forum_host/api.py` in the
reference host: `method_decorator(ratelimit(...))` subclasses mounted in place
of `wagtail_forum.api.urls`, with a route-parity test against this package).

## Error envelope

Every API error path raises a DRF `APIException` (never a hand-built
`Response({"detail": ...})`), so all errors flow through one exception handler
and share a single envelope:

```json
{
  "error": true,
  "message": "Idempotency-Key was already used with a different payload.",
  "code": "unprocessable",
  "status_code": 422,
  "errors": {"body": ["This field is required."]}
}
```

`errors` carries field-level validation errors, or `{"detail": "<message>"}` for
a non-field error; it is absent when the exception has no detail. Register the
shipped reference handler so a mounted host gets this contract instead of bare
DRF responses:

```python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": (
        "wagtail_forum.api.exception_handler.forum_exception_handler"
    ),
}
```

A host may substitute its own compatible handler — the plant_id reference host
uses `apps.core.exceptions.custom_exception_handler`, which emits the identical
core envelope plus an optional `request_id` and a 429 branch for its rate
limiter.

## Idempotency

Every unsafe write (`topic`/`reply`/`image` create, `post` edit, `reaction`
toggle, `report`) honours an `Idempotency-Key` request header: a retry with the
same key replays the original response (original status code) instead of
repeating the side effect; reuse with a different body returns `422`; a same-key
twin still in-flight returns `409`. Keys are scoped per (endpoint, user) and
cached for 24h. See `api/idempotency.py`.
