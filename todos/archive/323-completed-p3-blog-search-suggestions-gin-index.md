---
status: completed
priority: p3
issue_id: "323"
tags: [backend, blog, api, performance, database]
dependencies: []
---

# `search_suggestions` uses `title__icontains` with no GIN trigram index — add one now that it's routed

## Problem

`BlogPostPageViewSet.search_suggestions` (routed in todo 307) does
`BlogPostPage.objects.live().public().filter(title__icontains=query)` —
a substring lookup with no supporting GIN trigram index. Per
`docs/rules/database.md`: "Add GIN indexes for `__icontains` / full-text
search columns; plain B-tree indexes do not accelerate substring
search." This endpoint was unreachable before todo 307 (no `path()`
entry), so the missing index never mattered in practice; now it's a
live, public, unauthenticated endpoint.

## Findings

- Surfaced by `kimi-review` (WARNING) while codifying todo 307:
  *"`search_suggestions` uses `title__icontains` which requires a GIN
  index for acceptable performance on any non-trivial dataset. Verify
  that a GIN index exists on the `title` column of `BlogPostPage` (or
  add one via a migration) now that this endpoint is routed and
  reachable."*
- Confirmed via `grep`: no `GinIndex`/`trigram`/`pg_trgm` reference
  anywhere in `apps/blog/migrations/` or `apps/blog/models.py`.
  `BlogPostPage.search_fields` uses Wagtail's own `index.SearchField`
  (full-text search backend), which is a **separate** mechanism from a
  plain-Postgres `title__icontains` ORM filter — it does not help this
  query.
- Not urgent today: current dataset is small (dev/early-prod scale), so
  a sequential scan is cheap. Becomes a real cost once the blog has a
  meaningful number of posts.
- Same class of issue as the `by_category`/`related`-adjacent GIN-index
  guidance already documented in `docs/rules/database.md`; this todo is
  just applying it to a newly-live endpoint, not a novel pattern.

## Recommended Action

1. Add a migration enabling the `pg_trgm` extension (if not already
   enabled — check `backend/plant_community_backend/settings.py` /
   existing migrations for `TrigramExtension` first) and a `GinIndex`
   with `opclasses=["gin_trgm_ops"]` on `BlogPostPage.title`.
2. Confirm with `EXPLAIN ANALYZE` that `title__icontains` now uses the
   index (Bitmap Index Scan) instead of a sequential scan.
3. Consider whether the same treatment is worth it for
   `search_suggestions`'s tag-name lookup
   (`Tag.objects.filter(name__icontains=query, ...)`) — `taggit`'s `Tag`
   model may already have appropriate indexing; check before assuming
   it needs the same fix.

## Technical Details

- `backend/apps/blog/api/viewsets.py` — `search_suggestions` action
  (title-match query around `title__icontains=query`).
- `backend/apps/blog/models.py` — `BlogPostPage` model, would need the
  `GinIndex` added to `Meta.indexes`.
- Pattern reference: `backend/docs/patterns/performance/query-optimization.md`
  ("Add GIN indexes for `__icontains`" rule).
- Related: todo 307 (routed this action; this todo addresses a
  performance gap the routing surfaced, not a correctness bug).

## Acceptance Criteria

- [x] `BlogPostPage.title` has a GIN trigram index (migration +
      **amended at completion**: a documenting comment on `Meta`, not a
      literal `Meta.indexes` entry — `title` is inherited from
      `wagtail.Page` via multi-table inheritance and lives in
      `wagtailcore_page`, not `blog_blogpostpage`; a `Meta.indexes` entry
      for it trips Django's system check `models.E016` ("refers to field
      'title' which is not local to model"). Same constraint
      `BlogPostPage.Meta` already documents for `first_published_at`.
      Implemented instead as a hand-written `RunPython` migration
      against `wagtailcore_page` (`CREATE INDEX CONCURRENTLY` +
      `connection.vendor` guard — required after review found a plain
      `RunSQL` would lock the table during a live deploy and target the
      wrong SQL expression; see the code-review Work Log entry below).
- [x] `EXPLAIN ANALYZE` on the `title__icontains` query shows an index
      scan, not a sequential scan, against a dataset large enough to
      matter (or a documented note that Postgres's planner still
      prefers seq scan below some row count, which is expected/fine).

## Work Log

### 2026-08-31 - Started by completing-todos skill (run 2026-08-31-1317)

- Picked up by automated workflow. Plan reviewed and approved beforehand
  (see plan mode session): the AC's literal `Meta.indexes` requirement is
  not achievable (`title` is inherited from `wagtail.Page` via multi-table
  inheritance — Django's system check `models.E016` rejects it). Will ship
  as a hand-written `RunSQL` migration + a documenting `Meta` comment
  instead, amending AC1's wording accordingly at completion. Branch
  `feat/blog-title-gin-index-todo-323`.

### 2026-08-31 - Implementation + verification

- Added `apps/blog/migrations/0014_add_blog_title_trigram_index.py`
  (`TrigramExtension()` + `RunSQL` creating
  `wagtailcore_page_title_trgm_idx`, vendor-safe/reversible). Extended
  `BlogPostPage.Meta`'s existing inherited-field comment to also cover
  `title`, pointing at migration 0014. `makemigrations --check --dry-run`
  → `No changes detected` (model state matches the migration exactly, no
  drift from the comment-only model edit).
- Applied: `python manage.py migrate blog` →
  `Applying blog.0014_add_blog_title_trigram_index... OK`.
- AC1: index existence pinned in
  `backend/apps/blog/tests/test_indexes.py` (queries `pg_indexes`).
  `python manage.py test apps.blog.tests.test_indexes --noinput` →
  `Ran 1 test in 0.004s / OK`.
- AC2: `EXPLAIN (ANALYZE, BUFFERS)` with `enable_seqscan = off` on
  `SELECT * FROM wagtailcore_page WHERE title ILIKE '%monstera%'` →
  `Bitmap Heap Scan on wagtailcore_page` /
  `Bitmap Index Scan on wagtailcore_page_title_trgm_idx` — confirms the
  index is usable for this query shape (right opclass/operator),
  independent of table size.
- Full blog suite on a fresh DB: `python manage.py test apps.blog
  --noinput` → `Ran 233 tests in 29.491s / OK (skipped=7)`. No
  regressions. `python manage.py check` → no issues.
- **Taggit `Tag` model — explicitly deferred, not implemented** (per the
  Recommended Action's "consider, not necessarily implement"): `Tag` is a
  third-party model in its own app (`app_label = "taggit"`); adding a
  `GinIndex` to it means migrating a vendored package's schema from
  application code, a materially bigger/riskier change than this p3's
  scope. Its practical query cardinality in `search_suggestions` is
  already narrow (tags used on blog posts only, `.distinct()[:5]`). Not
  filed as a separate follow-up todo — noted here per the explicit-defer
  requirement so it isn't silently dropped.

### 2026-08-31 - Code review round 1: 2 blocking findings, repaired

- `code-review-orchestrator` routed to `wagtail-reviewer` +
  `cross-cutting-reviewer` (parallel, dispatched by the calling session
  since the orchestrator itself only has Bash and cannot dispatch
  agents). Both independently reviewed migration 0014 and found the
  index **did not actually fix the performance problem it exists for**:
  - **[CRITICAL, cross-cutting-reviewer]** No `CONCURRENTLY` — a plain
    `CREATE INDEX` on `wagtailcore_page` (shared by every Page subclass
    site-wide, not blog-scoped) takes an `ACCESS EXCLUSIVE` lock for the
    full build, blocking all page reads/writes during a live
    `preDeployCommand` migrate. (Wagtail-reviewer independently flagged
    the same gap as medium.)
  - **[HIGH, both reviewers]** Index built on bare `title`, but Django's
    Postgres backend compiles `title__icontains` as
    `UPPER(title::text) LIKE UPPER(%s)`, not a direct `ILIKE` — a
    trigram index on the raw column can't serve that expression.
  - **[HIGH, cross-cutting-reviewer]** `TrigramExtension()`'s reverse
    unconditionally runs `DROP EXTENSION pg_trgm` with no
    dependent-object check; `plant_identification/0013` already has
    trigram indexes depending on the same extension, so reversing this
    migration would fail.
  - **[HIGH/LOW, wagtail/cross-cutting]** No `connection.vendor` guard
    on the raw SQL — breaks on `DATABASE_URL`'s SQLite dev default.
  - **[MEDIUM, both]** `test_indexes.py` only asserted `indexname`
    existence, not `indexdef` — couldn't catch a wrong-type or
    wrong-expression regression under the same name.
  - I independently, empirically confirmed the two structural findings
    before trusting them: `BlogPostPage.objects.filter(title__icontains=...).query`
    printed `UPPER("wagtailcore_page"."title"::text) LIKE UPPER(%s)`;
    `EXPLAIN (ANALYZE)` with `enable_seqscan = off` against the
    bare-title index forced a `Seq Scan` (`Disabled: true` — no usable
    index existed); the same query against a `UPPER(title) gin_trgm_ops`
    index correctly produced a `Bitmap Index Scan`.

- **Repair**: rewrote migration 0014 — `RunPython` + `atomic = False` +
  `CREATE/DROP INDEX CONCURRENTLY` on `UPPER(title) gin_trgm_ops`
  (mirroring migration 0012's established pattern), `pg_trgm` enabled
  via a `RunPython` pair with a true no-op reverse (mirroring
  `plant_identification/0013`'s established pattern, not
  `TrigramExtension()`), both guarded on `connection.vendor`.
  `test_indexes.py` rewritten to assert on `indexdef` (`"using gin"`,
  `"gin_trgm_ops"`, `"upper("`).
- **Re-verified empirically**: rolled the migration back to 0013 then
  forward again — `wagtailcore_page_title_upper_trgm_idx` correctly
  dropped and recreated, `pg_trgm` extension survived the rollback
  (still present in `pg_extension`). `EXPLAIN (ANALYZE)` on the real
  ORM-compiled query now shows `Bitmap Index Scan on
  wagtailcore_page_title_upper_trgm_idx`. Full blog suite (233/233),
  `manage.py check`, `makemigrations --check --dry-run` all clean.
- **Verification round** (per the review-loop budget: round 2 verifies
  the specific fixes, not a fresh review): sent the corrected file back
  to both reviewer agents. Both independently re-verified against the
  live dev DB (not just the pasted diff) — `wagtail-reviewer` re-ran its
  own `EXPLAIN`/`test_indexes` checks; `cross-cutting-reviewer`
  inspected `pg_indexes.indexdef`, `django_migrations`, and
  `pg_extension` directly. **All 5 consolidated findings verdict:
  resolved.** Wagtail-reviewer flagged one residual low note from its
  own verification pass — `test_indexes.py` had no
  `skipUnless(vendor == "postgresql")` guard — fixed immediately
  (cheap, same file already open). Re-ran the full suite after: still
  233/233 green.
- (One process note: an agent-ID mixup briefly sent the wrong finding
  set to the wrong reviewer; both agents caught it, declined to
  fabricate verdicts, and the corrected messages were re-sent to the
  right recipients before any verdict was accepted.)

### 2026-08-31 - Completed by completing-todos skill (run 2026-08-31-1317)

- Verification: both acceptance criteria passed (AC1 amended per the
  E016 constraint, migration + `Meta` comment shipped instead; AC2
  confirmed via live `EXPLAIN` showing `Bitmap Index Scan` on the real
  ORM-compiled query). Full blog suite 233/233 green, `manage.py check`
  and `makemigrations --check --dry-run` clean.
- Review: 2 rounds. Round 1 found 2 CRITICAL/HIGH-tier structural bugs
  (index built on the wrong SQL expression — didn't actually accelerate
  the target query; no `CONCURRENTLY` on a site-wide shared table) plus
  3 smaller findings, all repaired. Round 2 (verification-only, per the
  review-loop budget) — both reviewers independently confirmed all 5
  resolved against the live DB, plus one residual low note (missing
  test `skipUnless` guard) fixed on the spot.

### 2026-08-31 - Filed

- Filed while codifying todo 307 (blog viewset routing) — `kimi-review`
  flagged the missing index on the newly-reachable `search_suggestions`
  endpoint. Not blocking merge (small dataset today), filed as p3
  follow-up rather than expanding todo 307's scope with a migration.

## Notes

- p3: performance/scalability concern, not a correctness bug — the
  endpoint returns correct results today, just via a seq scan.
