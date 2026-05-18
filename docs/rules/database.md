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
