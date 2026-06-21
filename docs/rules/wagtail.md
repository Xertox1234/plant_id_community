# Wagtail CMS — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/domain/wagtail.md`, `.../domain/blog.md`.

- **Wagtail admin is at `/cms/`, not `/admin/`.**
- **Signal handlers use `isinstance(instance, BlogPostPage)`**, never `hasattr` —
  multi-table inheritance makes `hasattr` match unintended page types.
- **StreamField blocks need matching frontend handling** — every new block type
  added to a model must get a case in the React `StreamFieldRenderer`.
- **Prefetch related pages** (`related_posts`, etc.) in the API queryset to avoid
  N+1 and empty results.
- Cache-invalidation signals must cover `page_published` AND `page_unpublished`.
- Verify the Wagtail API v2 serializes new fields before wiring the frontend.
- **`format_html()` needs interpolation args** — a bare `format_html('<x>')` with
  no `{}`/args raises `TypeError` on Django 6.0 (only a warning on 5.x) and 500s
  every admin page when it's in an `insert_global_admin_*` hook. Use `mark_safe()`
  for trusted static HTML, or pass a format arg: `format_html('{}', static(...))`.
- **`published` fires on EVERY publish, not just the first.** Guard
  notifications/side-effects with `first_published_at == last_published_at`
  (both non-None) — and only republish instances freshly loaded from the DB:
  `save_revision()` on a stale instance snapshots stale timestamps and corrupts
  `first_published_at` itself.
- **`PageViewRestriction` is NOT auto-enforced in custom views/APIs** — filter
  page querysets with `.live().public()` (and gate child-object queries via
  `parent__in=<that queryset>`), or restricted content leaks.
- **Page slugs are unique only among siblings** — a bare
  `Model.objects.get(slug=...)` across the tree can raise
  `MultipleObjectsReturned` (500). Scope the lookup or handle 0/2+ explicitly.
- **API-writable StreamField bodies need explicit validation**: `to_python()`
  silently DROPS unknown block types (content vanishes, no error), does NOT
  type-check values (an int paragraph reaches `nh3.clean()` → TypeError 500),
  and does NOT resolve ChooserBlock PKs (IDOR-by-reference). Reject unknown
  types, enforce str/dict-of-str values, and reject/validate chooser blocks
  before storing.
- **`workflow.start()` is the ONLY workflow trigger** — programmatic
  `save_revision().publish()` bypasses an assigned moderation workflow entirely.
  Anything user-visible that publishes programmatically (titles!) must be
  screened by the code doing the publish.
- **Filtering a Wagtail search queryset on a RELATED model's field needs
  `index.RelatedFields`.** `backend.search(q, Post.objects.filter(topic__live=True,
  topic__board__in=...))` raises `FilterFieldError` at query-compile unless
  `Post.search_fields` declares `index.RelatedFields("topic", [index.FilterField(
  "live"), index.FilterField("board_id")])`. Declare it — never drop the
  visibility filter to silence the error (that leaks hidden content). No
  migration: `search_fields` is not schema on the DB backend.
- **Never seed Wagtail pages in `post_migrate`.** It also runs against every TEST
  database, colliding with test helpers that build the same (sibling-unique) slug
  → `MultipleObjectsReturned`/409. Seed via an idempotent management command and
  wire it into the deploy `startCommand` (`railway.json`) — a documented-but-unwired
  seed command ships an empty forum to prod.
