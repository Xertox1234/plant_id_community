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
