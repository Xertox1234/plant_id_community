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
