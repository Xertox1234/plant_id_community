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
- **Only ONE active `WorkflowState` (IN_PROGRESS *or* NEEDS_CHANGES) may exist
  per object.** `WorkflowState.save()` calls `full_clean()`, which raises
  `ValidationError` if you call `workflow.start()` again while a prior state is
  still active. A rejected task (e.g. `SpamCheckTask` reject) leaves
  NEEDS_CHANGES, which counts as active — so a naive "re-submit on every edit"
  path raises on the second submission, and a blanket `except` around it wedges
  the object at a silent, unrecoverable "pending". Before re-submitting, resume
  or cancel the existing state (`obj.current_workflow_state.resume()/cancel()`),
  mirroring Wagtail's own resubmit flow. Verified vs Wagtail 7.4; reference
  implementation is `wagtail_forum.workflow.submit_edit_for_moderation` (cancel
  the stale state before `start()`) — todo 250.
- **`save_revision()` calls `full_clean()`, so a `null=True` FK needs `blank=True`
  too when the row is ever re-saved with that FK NULL.** A
  `ForeignKey(null=True, on_delete=SET_NULL)` with `blank` unset (`=False`) makes
  `save_revision`/`full_clean` raise `{'field': ['This field cannot be blank.']}`
  on a row the DB happily holds NULL (e.g. an account-deleted author's post →
  moderator edit is rejected/lost). Add `blank=True` (state-only migration, no
  SQL). See `docs/LEARNINGS.md` 2026-07-03.
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
- **Serialize a StreamField body from `stream_value.raw_data`, never by iterating
  the resolved StreamValue.** Plain `for bound in stream_value` makes Wagtail
  bulk-resolve each block type — and for a `ChooserBlock` (image/document/page)
  that is an `Image.objects.in_bulk()` PER post: an N+1 across a page that no
  `prefetch_renditions` on the post queryset can reach (the ids live inside the
  JSON, not a relation). Collect chooser ids from `raw_data` up front, batch-fetch
  once into an `{id: obj}` map, then read the map while iterating raw data. Pin the
  endpoint's `assertNumQueries` and prove it's flat across N. See `docs/LEARNINGS.md`
  2026-06-25.
- **Relax an API-write chooser-block rejection only with a collection-membership
  check.** When permitting an image/chooser block on the DRF write path, resolve
  every referenced PK with one bulk query scoped to the feature's Wagtail
  collection (`get_image_model().objects.filter(id__in=ids, collection=…)`); reject
  any nonexistent or out-of-collection id. The `to_python` dry-run never resolves
  chooser PKs, so an unchecked id is an IDOR-by-reference.
- **Never pass a user to `workflow.start()`.** On auto-approval workflows the
  completion hook publishes AS `requested_by` WITHOUT skipping permission checks →
  `PublishPermissionError` for non-moderator authors. Attribute at the action
  instead: `revision.publish(user=…, skip_permission_checks=True)`; for unpublish
  call `UnpublishAction(obj, user=…).execute(skip_permission_checks=True)` — the
  `DraftStateMixin.unpublish()` method cannot skip the check. (`LogContext` only
  attributes in the admin auth flow; DRF permissions are the real gate.)
- **An attributed log write adds one `auth_user` existence-check query** — passing
  `user=` into publish/unpublish shifts exact query pins by +1 per logged action;
  update the pin WITH a comment explaining the new number.
- **Seed/create pages under `Site.root_page`, never `Page.objects.filter(depth=1)`.**
  The depth-1 treebeard root is NOT the routable site root — a page attached
  there is a sibling of Home: `page.url` is `None` and `serve()`/`route()` never
  reach it (shipped-unroutable-forum near-miss, audit 2026-07-17 H1). Resolve
  `Site.objects.get(is_default_site=True).root_page` (handle `DoesNotExist` and
  `MultipleObjectsReturned` with a clear error in commands), and follow
  `add_child()` with `save_revision().publish()` so seeded pages have revision
  parity (`first_published_at`, `page_published`) with admin-created ones.
- **Never hardcode the admin mount in hooks or admin templates** (`/cms/...`,
  `/blog-admin/...`). Resolve inside the hook function body:
  `reverse(Model.snippet_viewset.get_url_name("list"))` for snippet views,
  `reverse("blog_admin:<name>")` for app admin URLs, `{% url %}` via a context
  var in templates. Hook registries are lazy (`cached_property`, first admin
  request), so `reverse()` in the function body is URLconf-safe; a hardcoded
  path silently 404s when the mount changes or a reusable package lands in
  another host (audit 2026-07-17 M1/M2 — the forum copied the blog's bug).
