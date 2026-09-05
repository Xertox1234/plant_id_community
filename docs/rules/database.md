# Database & migrations — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/performance/query-optimization.md`.

- **Never f-string identifiers into raw SQL.** Use `psycopg2.sql.Identifier()`
  with an explicit whitelist of allowed table/column names in a migration `RunSQL`.
- **Eliminate N+1 queries** — use `select_related()` (FK/one-to-one) and
  `prefetch_related()` (M2M/reverse FK) on querysets that feed serializers.
- **Pin query counts in tests** with `assertNumQueries(...)` — exact, not `<=`.
- **Add GIN indexes** for `__icontains` / full-text search columns; plain B-tree
  indexes do not accelerate substring search. **On PostgreSQL, `icontains` compiles
  to `UPPER(col) LIKE UPPER(%s)`, not `ILIKE`** — a `gin_trgm_ops` index must be
  built on `UPPER(col)`, not the bare column, or Postgres never picks it and the
  index does nothing. Verify with `Model.objects.filter(x__icontains=...).query`
  before trusting a migration's index expression, and assert the test on
  `pg_indexes.indexdef`, not just `indexname`. See
  `docs/patterns/performance/query-optimization.md` Pattern 32.
- **Migrations must be reversible** where practical; data migrations get an
  explicit reverse or `migrations.RunPython.noop`.
- After changing a migration, rebuild the test DB with `--noinput` — a stale test
  DB raises `FieldError`.
- No magic numbers — domain constants live in each app's `constants.py`.
- **A relation-reading field on a SHARED serializer N+1s EVERY list view that uses
  it** (incl. nested-serializer parents, e.g. a feed's `first_post`). When you add
  one, add `prefetch_related(...)` to ALL those querysets and a query-count test
  per path — not just the endpoint you came to change.
- **Model `save()` auto-assignment must be insert-only** (`if self.pk is None:`),
  or it re-fires on every UPDATE and mutates the row. Never use `or` for a numeric
  default where 0 is valid (`0 or -1` is `-1`) — use `is None`.
- **Aggregate on `Count("pk")`, never `Count("id")`/`Count("uuid")`.** Several
  models use a UUID primary key (`Plant`, `CareTask` → `pk == "uuid"`, no `id`
  field), so `Count("id")` raises `FieldError` at query construction → 500;
  `Harvest` is the reverse (`id` PK, no `uuid`). `pk` always resolves to the real
  primary key. (2026-06-02 audit: shipped twice via endpoints with no test — pair
  every aggregate rewrite with an endpoint test + `assertNumQueries`.)
- **Data migrations must be self-contained — never `call_command()` from
  `RunPython`.** The command's *current* code re-runs on every fresh `migrate`
  in every future environment (CI test DBs, new prod), long after the one-time
  intent has passed. Inline the operation with `apps.get_model()`; once a
  one-time data migration has served its purpose, make it a documented no-op.
- **Model-signal receivers MUST pass `sender=`** — `@receiver(post_delete)` (or
  `pre_delete`/`post_save`) without a sender registers for EVERY model: Django's
  `can_fast_delete()` then returns False project-wide, so every bulk/cascade
  delete anywhere fetches rows and deletes one-by-one with per-instance signal
  dispatch. Use lazy strings: `@receiver(post_delete, sender="app.Model")`.
- **Denormalized counters: recount in ONE UPDATE statement**
  (`.update(n=Coalesce(Subquery(...Count...), 0))`) — the subquery evaluates
  inside the UPDATE, so concurrent writers can't persist a stale read the way a
  read-modify-write `save()` can. And preserve every invariant other code relies
  on (e.g. a cursor-pagination "never NULL" ordering field needs `Coalesce` to a
  fallback in EVERY writer).
- **`field__in={..., None}` never matches a NULL column value.** SQL's
  `IN (NULL)` evaluates to unknown, not true, even for a row whose value
  actually is `NULL`. When `None` is a legitimate member of an `__in` set
  (e.g. grandfathering a nullable FK), split it out:
  `Q(field__in=non_null_values) | Q(field__isnull=True)`.
- **After `select_for_update().get(pk=…)`, mutate the LOCKED instance, never an
  earlier unlocked read.** `save()`/`unpublish()`/`publish()` on the pre-lock
  object writes fields back as they were at the stale read, clobbering a
  concurrent writer's committed changes. Re-read any value you gate on
  (`if not locked.live: …`) from the locked row too — that re-read under the lock
  is what makes the check-then-write atomic (e.g. stops an edit's `publish()` from
  resurrecting a concurrently-unpublished row). Catch the exception OUTSIDE the
  `atomic()`, not inside (a caught DB error inside poisons the connection).
- **Don't wrap `get_or_create`/`update_or_create` in your own
  `except IntegrityError: .get()` fallback without checking Django's own
  internals first.** Both already retry their own internal `.get()` once
  after a failed `create()` and only let `IntegrityError` propagate when that
  retry ALSO finds nothing — i.e. a genuinely unrecoverable failure (FK
  violation, etc.), not a lost create-race. A caller-added fallback on top
  only ever fires in that unrecoverable case, converting an already
  correctly-typed `IntegrityError` into a confusing masked `DoesNotExist`
  instead of a safety net. Verify against the exact Django version in
  `requirements.txt` before assuming — don't take this file's word for it
  either. See `backend/docs/patterns/architecture/services.md` and
  `docs/LEARNINGS.md` (2026-07-16) for the full empirical trail.
- **A `select_for_update().get(pk=…)` re-fetch can itself raise `DoesNotExist`** if
  the row was hard-deleted (e.g. a CASCADE) between the first fetch and the lock.
  In a request handler, catch it and return 404 — do NOT let a blanket
  `except Exception` swallow it into a fake success and then re-raise on the next
  ORM call (`refresh_from_db`). Keep the service layer framework-free: let the
  model's `DoesNotExist` propagate and translate it to `NotFound` at the view.
- **A per-request-user field on a `many=True` serializer must batch its data into
  serializer context in ONE query (like `build_forum_image_map`), and the field
  method must guard the map read with `if map is not None:` — NEVER truthiness.**
  An authed user with zero rows yields an empty `{}` (falsy but not `None`); a
  truthiness check silently routes every row to the per-object fallback and
  reintroduces the N+1. Pin an authed test where the user has NO rows. See
  `docs/patterns/performance/query-optimization.md` Pattern 31.
- **Wrapping a model's `choices` labels in `gettext_lazy` needs NO migration** —
  Django's lazy proxy compares equal to its source string, so the autodetector
  sees no field change (`makemigrations` reports "No changes detected"). Verified
  across 5 choice fields in `wagtail_forum` (todo 262). Do not hand-write an
  `AlterField` for it, and do not avoid i18n out of migration fear. This is the
  opposite of a *value* change (`("spam", "Spam")` -> `("spam", "Junk")`), which
  DOES generate one — see migration `wagtail_forum/0015_alter_notification_verb`.
- **`transaction.on_commit()` defers NOTHING when no transaction is open — and
  the test suite is the one place where it does defer, so no pinned-query test
  can catch the difference.** This project runs `ATOMIC_REQUESTS = False`, so
  unless a view opens an explicit `atomic()`, Django's autocommit branch
  (`db/backends/base/base.py::on_commit`, verified against Django 6.0.7) runs
  the callback IMMEDIATELY and inline, inside the request. Under
  `@pytest.mark.django_db` (and `TestCase`) the body IS inside an atomic block,
  so the same callback defers and is rolled back unrun — which is why observing
  it needs `django_capture_on_commit_callbacks`. Consequence: a
  `CaptureQueriesContext`/`assertNumQueries` pin can honestly read N while
  production runs N+2. Never write "moved to on_commit, so it's outside the
  request / doesn't count against the pin" — check `connection.in_atomic_block`
  instead. `robust=True` IS still honored on the immediate path, so the
  don't-500-an-already-successful-200 fail-safe survives; only the deferral
  doesn't. For a reusable package this is the HOST's configuration, not yours:
  open your own `atomic()` if you need real defer-until-commit, and reach for
  Celery if you need the work off the request — `atomic()` does not do that.
  See `docs/LEARNINGS.md` 2026-07-29 (todo 271).
- **`DataError` is NOT a subclass of `IntegrityError`.** A retry loop written as
  `except IntegrityError: continue` (e.g. the topic-create slug auto-suffix) does
  not catch a value that overflows a column's width — it escapes as an unhandled
  500 where a 400 belonged. So validate lengths against the ACTUAL column width,
  and clamp rather than trust a configurable bound: `min(get_setting("X"), COLUMN_MAX)`.
  A host raising a setting past the column width must not be able to turn a
  validation error into a server error (todo 276, taggit `Tag.name` VARCHAR(100)).
- **A `get_or_create(defaults=…)` value that costs a query must be a CALLABLE, not
  a computed value.** Django resolves callable defaults only inside the
  `except DoesNotExist` branch (`params = dict(resolve_callables(params))`,
  `db/models/query.py` — verified against the installed 6.0.7), so
  `defaults={"x": lambda: expensive_lookup()}` pays nothing on the common
  already-exists path, while `defaults={"x": expensive_lookup()}` pays on EVERY
  call. This matters most in signal handlers, where the row usually exists:
  `wagtail_forum/signals.py::_refresh_profile` runs on every post
  publish/unpublish. Pin it by driving the production function under
  `CaptureQueriesContext` and asserting the extra table is untouched — not by
  copying the `get_or_create` into the test.
- **Every `order_by` feeding a sliced or paginated public list ends with a
  deterministic tie-break (`-id`).** Ties on the cut line otherwise flicker
  between requests (arbitrary Postgres order) and the cached anon copy can
  disagree with an authed response. Bit twice in one PR: `topics/recent/`
  (caught at build, Ruling 4) and `users/experts/` (caught only at review).
- **Never use `django.contrib.postgres.operations.TrigramExtension()` (or any
  `CreateExtension` subclass) when the extension is already shared by another
  app's migrations.** Its `database_backwards` unconditionally runs
  `DROP EXTENSION IF EXISTS <name>` with no dependent-object check — reversing
  the migration fails once any other app's index still depends on that
  extension (Postgres refuses the DROP). Use a `RunPython` pair instead:
  `CREATE EXTENSION IF NOT EXISTS <name>;` forward, `migrations.RunPython.noop`
  reverse — pg_trgm and similar extensions are a shared, database-scoped
  resource that no single migration should tear down on its own rollback.
- **On a hot, shared table, pair `CREATE INDEX CONCURRENTLY` with
  `atomic = False`** on the `Migration` class — `CONCURRENTLY` cannot run
  inside a transaction block. `wagtailcore_page` (shared by every Wagtail Page
  subclass) is the canonical case: a plain `CREATE INDEX` there locks
  reads/writes site-wide, not just one app, for the build's duration.
- **Never wire `full_clean()` into `save()` on a model whose uniqueness is
  handled by catching `IntegrityError` from a `UniqueConstraint`** (the
  savepoint pattern above). Since Django 4.1, `full_clean()` also runs
  `validate_constraints()`, which pre-checks the constraint against the DB
  and raises a `ValidationError` BEFORE the INSERT — the caller's
  `except IntegrityError:` (returning a deliberate 409, say) never fires,
  and the `ValidationError` escapes uncaught as a 500 instead. A model
  `clean()` method that checks something ELSE (e.g. "does this FK actually
  belong to that other FK") is fine and should stay unwired from `save()`
  for the same reason — any writer that wants the check calls `clean()` (or
  `full_clean()`) itself; the one hot path that relies on the DB-level
  `IntegrityError` stays untouched. Verified against Django 6.0.7
  (`wagtail_forum.PollVote`, todo 320 #8) — caught by `advisor` before
  shipping, not by a failing test, so don't assume a passing suite proves
  this interaction is absent; trace it deliberately whenever `full_clean()`
  and an `except IntegrityError:` savepoint coexist for the same model.
- **Every django-ai-core vector index shares ONE `PgVectorEmbedding` table,
  and `document_key` is its PRIMARY KEY.** Keys must carry an index-unique
  prefix (`ModelSource.source_id` = the model label); `PgVectorProvider.clear()`
  deletes EVERY index's rows and `delete(keys)` ignores `index_name` — purge
  with `PgVectorEmbedding.objects.filter(index_name=..., document_key__startswith=...)`.
  `add()` only upserts the keys it is handed (nothing ever purges a stale tail),
  and `VectorIndex.update()` re-registers every source object in
  `ModelSourceIndex` on every call — per-object maintenance goes through the
  transformer + provider directly. Verified against 0.1.5 (todo 289).
- **Never call `search_documents()` outside `vector_indexes._scored_search`.**
  It is the single place that owns the flag, the query cap and the embedding
  budget; an unsliced result also silently caps at 20 rows. Wrappers:
  `find_similar_topics()` (Topic pks) and `retrieve_grounding_passages()`
  (scored, floored). See `backend/docs/patterns/domain/forum.md`.
- **Never set a non-zero `CONN_MAX_AGE` unconditionally.** Persistent connections
  assume a bounded number of processes (gunicorn); `runserver` spawns a THREAD PER
  REQUEST and each thread's connection is then held for the full `CONN_MAX_AGE`, so
  under any parallel load they accumulate far faster than they expire and Postgres
  hits `max_connections` — every request then 500s with `FATAL: sorry, too many
  clients already`. Gate it on `DEBUG` (`0 if DEBUG else 600`, overridable via
  `DB_CONN_MAX_AGE`). Corollary for diagnosis: **a high idle connection count is
  usually this, not a leak** — check connection *lifetime* before hunting a leak,
  and measure at true rest (this repo idles at 9, 8 of them Postgres's own
  background workers). See `docs/LEARNINGS.md` 2026-09-01 (todo 331).
- **A unique constraint never de-dupes rows where a constrained column is NULL**
  (SQL: `NULL <> NULL`), so `update_or_create(...)`/`.get(...)` keyed on a
  `unique_together`/`UniqueConstraint` that includes a nullable column can raise
  `MultipleObjectsReturned` after a concurrent double insert — Wagtail's
  `Redirect(old_path, site)` with `site=None` is the live case (Wagtail's own
  `RedirectForm.clean` de-dupes by hand for this reason). Write
  `filter(...).update(...)` and create only when nothing matched, or declare
  `UniqueConstraint(..., nulls_distinct=False)` (Postgres 15+). See
  `docs/LEARNINGS.md` 2026-09-04 (PR #624).
- **`istartswith` compiles to `UPPER("col"::text) LIKE UPPER(%s)` on Postgres —
  a prefix LIKE on a `text` EXPRESSION.** Neither the column's plain B-tree nor
  a trigram GIN (Pattern 32's `icontains` fix) serves it; under a non-C locale a
  plain B-tree cannot serve LIKE at all. The index that does is a functional
  B-tree on `UPPER(col)` with `text_pattern_ops` (the expression is `text` after
  the cast, so NOT `varchar_pattern_ops`), built `CONCURRENTLY` with
  `atomic = False` on any hot table. Prove it, don't assert it: pin
  `pg_indexes.indexdef` AND run the real ORM query through `EXPLAIN` with
  `SET LOCAL enable_seqscan = off` and assert the index name appears — a wrong
  opclass or expression compiles fine and is simply never chosen. See
  `performance/query-optimization.md` Pattern 33 (audit 2026-09-04 L11).
- **A model-level aggregate must not depend on a VIEW-level invariant.**
  `Poll.results()` summed per-option counts as "voters" because the vote view
  guaranteed one row per voter — the moment the DB constraint moved to
  `(poll, user, option)`, any writer that bypassed the view (admin, a data
  migration, a second endpoint) would double-count silently. Compute the
  aggregate from the rows (`Count("user", distinct=True)`), and if the cost
  matters fold it into the existing query as a correlated `Subquery` rather
  than trusting the caller (todo 349 review).
- **An idempotent seed command must dedupe on EVERY unique field, in its own
  savepoint per row — it runs in `preDeployCommand`, where one IntegrityError
  blocks every later deploy.** `seed_default_badges` checked `slug` only while
  `name` was also unique and CMS-editable; an editor renaming a custom badge
  "First post" would have wedged deploys until someone fixed the DB by hand.
  Check `Q(slug=…) | Q(name=…)`, wrap each create in `transaction.atomic()`
  and catch `IntegrityError` → skip + warn (todo 348 review).
- **A plain FK from a history/award table to a Wagtail snippet is `PROTECT`,
  not `CASCADE`.** Only chooser/`ReferenceIndex`-tracked relations get the
  admin's "used by N" warning on delete; a plain FK silently cascades, so a
  moderator deleting a `Badge` would erase every member's award history with
  no prompt. Refuse the delete and retire via an `is_active` flag (todo 348).
