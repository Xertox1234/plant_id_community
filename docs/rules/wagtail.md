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
- **A field editable in BOTH the CMS admin and the DRF API has two write paths —
  and only one runs your serializer.** Adding `FieldPanel("tags")` gives staff a
  writer that bypasses every serializer-side normalization/bound, so read-side
  code that assumes the canonical form silently breaks on admin-authored data.
  `django-taggit` makes this concrete: `Tag.name` is case-SENSITIVE (unless the
  host sets `TAGGIT_CASE_INSENSITIVE`) and the admin widget treats a comma as its
  list separator. A moderator's "Monstera" was unreachable from an exact-match
  `?tag=` filter — from the very chip the UI renders out of that name. Either
  normalize on BOTH paths, or make the READ side path-agnostic (`__iexact`) — and
  if you choose `__iexact` on an M2M, add `.distinct()`, since "Monstera" and
  "monstera" are two Tag rows and a row carrying both joins twice (todo 276 M5).
- **Never conclude a framework hook is dead by grepping only THIS repo.** Wagtail
  calls plenty of declarative hooks itself. `index.AutocompleteField` looked
  unused (`grep '\.autocomplete('` matched nothing of ours) and was removed as
  dead index cost — but the caller is Wagtail's generic `search_queryset`
  (`admin/views/generic/base.py`), which uses `backend.autocomplete()` whenever
  `model.get_autocomplete_search_fields()` is non-empty and otherwise silently
  degrades to whole-word `search()` + a `RuntimeWarning`. Any `SnippetViewSet`
  with `search_fields` is therefore a reader. Removing it broke CMS prefix search
  ("mons" no longer matched "Monstera repotting") with every test still green,
  because `pytest.ini` only silences Deprecation warnings, not `RuntimeWarning`.
  Before deleting a declarative field, grep the INSTALLED framework for the
  attribute name, and pin the behaviour with an admin-listing test (todo 276 L8).
- **`expand_db_html` has SIDE EFFECTS — sanitize before it, not only after.**
  Wagtail's DB rich-text representation carries `<embed>` placeholders that the
  expander resolves by *doing work*: `embedtype="media"` calls the oEmbed finder,
  which does `requests.get(...)` with **no `timeout=`** (verified in
  `wagtail/embeds/finders/oembed.py`), and `embedtype="image"` generates a real
  rendition (PIL resize + storage write + DB row). Sanitizing only the OUTPUT
  discards the `<iframe>`/`<img>` while still paying for it — the allowlist looks
  like a control but is not one. On a public, unauthenticated, CDN-fronted
  endpoint an unreachable provider hangs the request, and a failed oEmbed fetch
  caches nothing, so every cache miss pays again. Strip embeds in a pre-pass
  (keep `a[linktype][id]` so page/document links still resolve), THEN expand,
  THEN sanitize the output.
  Pair it with `RichTextField(features=[...])` that excludes `image`/`embed` —
  but do not rely on `features` alone: it governs the editor toolbar, not what a
  fixture, an import, or a direct DB write can put in the column. Note Wagtail's
  DEFAULT feature set includes both (`bold, document-link, embed, h2-h4, hr,
  image, italic, link, ol, ul` — no `blockquote`), so an unrestricted
  `RichTextField` is opted IN. Adding `features` needs no migration; it is not
  part of the field's deconstruct. Hit in todo 278 (`ForumIndex.intro`).
- **Always guard `get_rendition()` on API paths.** A missing source file (media
  wiped on redeploy while `Image` rows survive) raises `SourceImageIOError` on
  the cache-miss path and 500s the whole endpoint — and the anon cache can pin
  the failure. Catch it (plus the `OSError` family), log `[ERROR]`, and degrade
  that thumbnail to `null`. Hit on `topics/recent/` (PR #538 review).
- **Back-dating published content must set `first_published_at` AND
  `last_published_at`,** not just `created_at`/`updated_at` — counter recomputes
  (`_refresh_topic_counters`) derive from `first_published_at`, so a back-date
  that skips it snaps curated timestamps to wall-clock on the first
  unpublish/delete/recount. Hit in `seed_demo_content` (PR #538 review).
- **A custom `PagesAPIViewSet` subclass's `self.action` is NOT DRF's
  `"list"`/`"retrieve"`.** Wagtail's router wires the base endpoints via
  `cls.as_view({"get": "listing_view"})`/`{"get": "detail_view"}`/
  `{"get": "find_view"}` (`wagtail/api/v2/views.py`; Wagtail's OWN base class
  checks `self.action == "listing_view"` internally) — so a
  `get_serializer_class()`/`get_queryset()` branch written as
  `if self.action == "list":` never matches and silently falls through to
  the OTHER branch on every request. Branch on `"listing_view"`/
  `"detail_view"` instead. Only genuine DRF `@action`-decorated custom
  endpoints (`.as_view({"get": "popular"})`) get their real method name in
  `self.action`, since those ARE dispatched through DRF's own
  `ViewSetMixin.as_view()`. Verify by live-probing the actual endpoint
  response, not by re-reading the branch — see `docs/LEARNINGS.md`
  2026-08-16 and todo 306.
- **`WagtailAPIRouter`/`BaseAPIViewSet.get_urlpatterns()` does NOT auto-mount
  `@action`-decorated methods** — it only ever wires the three fixed base
  routes (`listing_view`/`detail_view`/`find_view`), unlike DRF's own
  `SimpleRouter`. Every custom `@action` needs an explicit `path()` entry in
  the project urlconf or it's dead code — importable, even unit-testable via
  `as_view({"get": "..."})(request)` direct dispatch, but 404 over any real
  URL. Generate the routes from `get_extra_actions()` (see
  `backend/docs/patterns/domain/wagtail.md`) instead of hand-writing one
  `path()` per action — hand-writing is exactly how 6 of 7 actions on
  `BlogPostPageViewSet` shipped unroutable for months. See
  `docs/LEARNINGS.md` 2026-08-31 and todo 307.
- **`list_export` resolves dotted paths with `multigetattr`, which RAISES on a
  NULL intermediate** — `"post.topic.title"` on a `Report` whose `post` is NULL
  (message reports) 500s the whole CSV/XLSX download. Expose a model property
  that returns `""` for the other shape (`Report.topic_title`) and export that.
- **Registered snippets are already in `ReferenceIndex`** (`register_snippet`
  registers the model; `update_reference_index_on_save` runs synchronously under
  the immediate django-tasks backend): the image/document usage views and delete
  confirmations list them natively. Don't rebuild usage tracking — pin it with a
  test and add only what is missing (e.g. a live-content deletion warning).
- **A Wagtail contrib API viewset registered on `api_router` needs a subclass
  with `versioning_class = None`** — DRF `NamespaceVersioning` rejects the
  router's `wagtailapi` namespace with "Invalid version in URL path", and the raw
  `/api/v2/pages/` and `/api/v2/images/` mounts already 404 this way. Mirror
  `apps/forum_host/redirects.py::RedirectsAPIViewSet` (PR #624).
