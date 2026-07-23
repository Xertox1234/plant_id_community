# Design — Forum semantic "similar topics" via pgvector (todo 255, slice 4 / H15)

Branch `todo-255-slice4-similar-topics` (off fresh `main` AFTER slice 3 merges).
Epic todo `todos/255-in_progress-p1-forum-ai-premium.md`. Source finding H15.
User decision 2026-07-22: **build H15 now** (precheck GREEN — see slice-3 spec).

## Problem

H15 = semantic "similar topics" using django-ai-core's dormant pgvector index.
Precheck confirmed Railway PG18 exposes `vector 0.8.2` and the app role is
superuser, so `CREATE EXTENSION vector` succeeds at deploy. This slice activates
the vector index over forum Topics and ships a compose-time similar-topics
endpoint.

## Substrate (verified against installed source, django-ai-core 0.1.5)

- **No settings read, NO autodiscovery** — an index registers only when the
  module defining its `@registry.register()` class is imported. We force the
  import from `ForumHostConfig.ready()`.
- `VectorIndex` subclass with class attrs `sources`, `embedding_transformer`,
  `storage_provider`. `search_documents(q)` → scored `BaseStorageDocument`s
  (`score = 1 - cosine_distance`, `metadata["pk"]`); `find_similar(obj)` →
  model instances (no score, INCLUDES the query object). Default page size 20 →
  slice to limit.
- `ModelSource(queryset=..., content_fields=...)`; `str()`s each field →
  StreamField renders junk, so we **override `get_content`** to emit
  `title + first-post plaintext`.
- `CoreEmbeddingTransformer(LLMService.create(provider="openai",
  model="text-embedding-3-small", api_key=...))` — 1536-dim. `PgVectorProvider()`
  (no dim kwarg; `VectorField()` is unbounded → accepts 1536 unchanged).
- **`LLMService.create` RAISES `MissingApiKeyError` at construction with an empty
  key** (verified) → the transformer must be built LAZILY (at index
  instantiation), never at class-def/import.
- Latent package bug: `find_similar` `UnboundLocalError` if the passed object's
  exact type isn't a registered source — we use `search_documents(query_str)`
  (string query), which avoids it and fits the compose use case.

## Environments — pgvector availability (verified 2026-07-22)

| Env | vector ext | action |
|-----|-----------|--------|
| Local dev/test | 0.8.1 available | none (migration works) |
| CI `backend-tests` | `postgres:16` → **lacks vector** | **swap service image → `pgvector/pgvector:pg16`** |
| CI `backend-checks` | SQLite, no migrate | none (imports only; pgvector pip pkg present) |
| Prod (Railway) | 0.8.2, superuser | none (migration works) |

The `CREATE EXTENSION vector` migration (shipped by the pgvector storage app)
runs at every migrated test-DB creation, so CI's Postgres MUST have vector →
the one-line image swap is mandatory, independent of any feature flag.

## Gating — `FORUM_VECTOR_SEARCH_ENABLED` (default False)

The apps + migration are **always installed** (all envs have vector; CI tested).
The **endpoint + any embedding spend** gate behind
`FORUM_VECTOR_SEARCH_ENABLED = config(..., default=False, cast=bool)`:

- Off (dev/CI default): endpoint returns `503 {"detail":"not enabled"}`; no
  embedding API call ever fires → zero accidental spend over the empty forum.
- On (prod, when there's a corpus + a real `OPENAI_API_KEY`): live.

This mirrors slice-2's "ship the capability, enable by one setting" posture. The
index is registered regardless (import is key-free via lazy transformer), so
`rebuild_indexes` works wherever a key + flag are set.

## Architecture

### `apps/forum_host/vector_indexes.py`

```python
@registry.register()
class SimilarTopics(VectorIndex):
    storage_provider = PgVectorProvider()
    sources = []                          # set in __init__ (see below)
    embedding_transformer = None          # lazy — set in __init__, NOT import

    def __init__(self):
        # BOTH deferred to instantiation, never class-def/import:
        #  - source queryset filtered through _visible_boards() so restricted-
        #    board content is NEVER embedded (defense in depth, not just a
        #    query-time refetch filter — mirrors the slice-3 authz lesson).
        #  - transformer built here so LLMService.create's empty-key
        #    MissingApiKeyError can't fire at import (dev/CI have no key).
        self.sources = [TopicSource(
            queryset=Topic.objects.filter(live=True, board__in=_visible_boards())
        )]
        self.embedding_transformer = _build_embedding_transformer()  # reads key
        super().__init__()

class TopicSource(ModelSource):
    def get_content(self, obj) -> str:
        # title + first live post's StreamField body as plaintext
        ...
```

> **Spikes PASSED 2026-07-22** (both required before building, per advisor):
>
> - `VectorIndex.__init__` reads `self.storage_provider/sources/embedding_transformer`
>   (all instance access, `base.py:31-44`), so setting `self.sources` +
>   `self.embedding_transformer` before `super().__init__()` wires the instance
>   values — verified by a runtime spike (sentinel transformer arrived in the
>   QueryHandler; `index_name` resolved). `storage_provider = PgVectorProvider()`
>   stays a class attr (no key/DB at construction).
> - App labels `index`, `pgvector`, `django_ai_core` are all free (no collision
>   among the 52 installed apps).

`_build_embedding_transformer()` = `CachedEmbeddingTransformer(CoreEmbeddingTransformer(
LLMService.create(provider="openai", model=EMBED_MODEL, api_key=settings.OPENAI_API_KEY)))`
— cached-embeddings so a rebuild only re-embeds changed content (content-hash
cache table). Reads the key at instantiation only.

`find_similar_topics(query, board_slug=None, limit=K) -> list[Topic]`:

- returns `[]` if `not FORUM_VECTOR_SEARCH_ENABLED`.
- `docs = SimilarTopics().search_documents(query)`, take pks from
  `metadata["pk"]` in score order, refetch **through `_visible_boards()`** (board
  privacy — the slice-3 authz lesson), optional board-slug filter, exclude none,
  cap at `limit`. Never raises to the caller (log + `[]` on any provider fault).

### `apps/forum_host/similar.py` — `SimilarTopicsView(APIView)`

- `GET /api/v1/forum/topics/similar/?q=<text>&board=<slug>` — compose-time.
- Auth: `IsAuthenticatedOrReadOnly`-style public read (audit: "arguably
  free-for-all"); throttled per-IP `_throttled("similar_topics","GET",key=client_ip_key)`
  like `search`. Result cached by `(q, board)` hash (short TTL) to bound
  embedding spend on debounced typing.
- `503` when the flag is off; `200 {"results":[{id,slug,title,board_slug,...}]}`
  otherwise. `q` required (400 if blank), bounded length.

### Registration — `apps/forum_host/apps.py`

`ForumHostConfig.ready()` imports `vector_indexes` unconditionally (import is
key-free), so `rebuild_indexes SimilarTopics` sees it. (If `apps.py` has no
AppConfig yet, add one + set `default_app_config`/`INSTALLED_APPS` entry.)

### Rebuild

Ships with the package command: `python manage.py rebuild_indexes SimilarTopics`
(re-embeds via the cached transformer — unchanged topics are free). NOT wired to
Celery beat (empty corpus → no schedule yet); documented as the operator step.
A thin `forum_host` management passthrough is out of scope (YAGNI).

## Files changed

- `backend/requirements.txt` — add `pgvector==0.4.1`.
- `backend/plant_community_backend/settings.py` — 2 INSTALLED_APPS
  (`django_ai_core.contrib.index`, `...storage.pgvector`); `FORUM_VECTOR_SEARCH_ENABLED`;
  `FORUM_EMBED_MODEL` default; watch the index app's bare label `index` for collision.
- `.github/workflows/backend-ci.yml` — `postgres:16` → `pgvector/pgvector:pg16`.
- `apps/forum_host/vector_indexes.py`, `similar.py` (new); `apps.py` (ready());
  `api.py` (+`_throttled` wrapper or reuse), `api_urls.py` (route),
  `constants.py` (rate + K + TTL + model + cache prefix + max chars).
- Tests `tests/test_similar.py`; drift-guard `HOST_ONLY_ROUTES` += similar route;
  `test_schema_429` += similar GET.
- `CLAUDE.md` env table += `FORUM_VECTOR_SEARCH_ENABLED`.

## Testing

- **View tests** (mock `find_similar_topics`): flag-off → 503; blank q → 400;
  ranked results serialized; throttle fires; board filter passed through.
- **Integration test** (real pgvector, MOCK only the embedding transformer to
  return deterministic vectors; flag on via `override_settings` + a fake key):
  build a 3-topic index, `search_documents("...")` returns them ranked; a
  restricted-board topic is excluded from `find_similar_topics` (authz).
- Never calls the real OpenAI embeddings API. `makemigrations --check` clean
  (apps own their migrations); `spectacular` OK; full `apps/forum_host` +
  `apps/blog` green on local pgvector.

## Acceptance criteria satisfied (epic AC #5, #6)

- #5: precheck recorded GREEN (slice 3) + similar-topics endpoint SHIPPED.
- #6: M13 RAG stays unstarted — this slice builds only the H15 index+endpoint,
  no retrieval-augmented generation.
