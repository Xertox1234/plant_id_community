# Database & migrations — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/performance/query-optimization.md`.

- **Never f-string identifiers into raw SQL.** Use `psycopg2.sql.Identifier()`
  with an explicit whitelist of allowed table/column names in a migration `RunSQL`.
- **Eliminate N+1 queries** — use `select_related()` (FK/one-to-one) and
  `prefetch_related()` (M2M/reverse FK) on querysets that feed serializers.
- **Pin query counts in tests** with `assertNumQueries(...)` — exact, not `<=`.
- **Add GIN indexes** for `__icontains` / full-text search columns; plain B-tree
  indexes do not accelerate substring search.
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
