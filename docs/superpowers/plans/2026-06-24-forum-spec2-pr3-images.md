# Forum Spec 2 — PR-3 (images): implementation plan

**Todo:** `231-in_progress-p1-forum-spec2-read-api-web-client.md` (archives after PR-3).
**Spec:** `docs/superpowers/specs/2026-06-20-forum-spec2-read-write-client-design.md` (Phase 3).
**Predecessors merged to main:** PR-1 (#394 read cleanup), PR-2a (#395 backend write),
PR-2b (#396 web write).

PR-3 is the inline-image story — the only thing still on legacy paths. Split into
**PR-3a (backend)** and **PR-3b (web)** like PR-2a/PR-2b: the backend is security-sensitive
(file upload + sanitizer relaxation + IDOR guard) and earns isolated review; the web suite
mocks `fetch`, so PR-3b is independently verifiable. PR-3a is the prerequisite for live
integration.

## Design decisions (this session)

- **Compose UX = TRUE INTERLEAVING** (user choice): images render exactly where placed.
  Custom TipTap image node + a bidirectional body serializer. Backend forces images to be
  separate `image` StreamField blocks anyway — nh3's rich-text allowlist (`api/sanitize.py`)
  has no `img`, so inline `<img>` in a paragraph is stripped by design.
- **Upload route is topic-independent: `POST /api/v1/forum/images/`** (deviates from the
  spec's `POST /topics/{id}/images/`). New-thread compose has no topic id, and the image is
  never scoped to a topic — it's a Wagtail Image referenced by id in a body block. Security =
  collection membership (sanitize) + `IsAuthenticated`; the topic would be decorative.
- **Rendition JSON = flat `{id, url, alt, width, height}`** (matches the existing web
  renderer idiom; the spec's `{id, renditions}` is reconciled to flat here).
- **Image serialization is a serializer special-case, not an `ImageChooserBlock` subclass**
  — avoids a StreamField migration; mirrors how RichText is already special-cased.

## Current state (verified)

- `image = ImageChooserBlock()` is already live in `ForumBodyBlock` (`blocks.py:27`); the
  model accepts it. Gaps are entirely API-layer.
- `validate_forum_body` (`api/sanitize.py`) rejects image blocks at **two** sites: the
  int-value type guard (L88-89) and the blanket chooser rejection (L96-106).
- `serialize_forum_body(stream_value)` (`api/serializers.py:124-139`) falls image blocks into
  the `else` branch → bare int id, no renditions.
- No upload endpoint, no forum Collection anywhere in the package.
- Bodies are serialized via `PostSerializer.get_body` only in **`PostListView`** (paginated)
  and **`PostWriteView.patch`** (single) — the two two-pass sites. `TopicDetailView` does NOT
  serialize a body.
- `tests/api/test_post_list.py` pins exactly 3 queries with **text-only** posts → stays green
  if `build_forum_image_map` short-circuits on empty image-id sets.

## PR-3a — backend (TDD, package-local; no `apps.*` imports — `test_reusability` guard)

1. **`conf.py`** — add image config to `DEFAULTS` (overridable via `WAGTAILFORUM_*`):
   `IMAGE_ALLOWED_EXTENSIONS`, `IMAGE_ALLOWED_MIME_TYPES`, `IMAGE_MAX_SIZE_BYTES` (10MB),
   `IMAGE_MAX_PIXELS` (100M), `IMAGE_MAX_WIDTH`/`IMAGE_MAX_HEIGHT` (5000),
   `IMAGE_COLLECTION_NAME` ("Forum Images").
2. **`collections.py`** — `get_forum_image_collection()`: idempotent get-or-create of a child
   under `Collection.get_first_root_node()`. *Test: called twice → one collection.*
3. **`api/sanitize.py`** — relax `validate_forum_body`: (a) permit an int value when
   `type=="image"` in the type guard; (b) replace the blanket image rejection with one bulk
   membership query `get_image_model().objects.filter(id__in=image_ids,
   collection=get_forum_image_collection())` → reject nonexistent/out-of-collection ids; keep
   all other choosers rejected. *Tests: nonexistent id (12345) still raises (keep existing
   test, update rationale); a valid forum-collection id round-trips; other-collection id
   raises.*
4. **`api/upload.py`** — package-local 4-layer validator (copy garden_calendar logic) +
   `PostImageUploadView` (`IsAuthenticated`, `versioning_class=None`, `MultiPartParser`) →
   `get_image_model().objects.create(file=…, collection=…, uploaded_by_user=request.user,
   title=<from filename>)` → `{id, url, alt, width, height}` via the shared rendition helper.
   *Tests `tests/api/test_post_image_upload.py`: each layer rejects (bad ext, MIME spoof,
   oversize, non-image, bomb via PIL mock), valid round-trip, 401 anon.*
5. **`api/serializers.py`** — `build_forum_image_map(posts)` (reads `body.raw_data`, one
   `filter(id__in).prefetch_renditions(...)`), `serialize_forum_body(stream_value, image_map)`
   image special-case → flat shape from the map (no per-block query), update `FORUM_BODY_SCHEMA`.
   `PostSerializer.get_body` reads `self.context["forum_image_map"]`.
6. **`api/views.py`** — `PostListView.list()` builds the map from the paginated page →
   serializer context; `PostWriteView.patch` builds it for the one post. *New query-pin test
   for an image body; existing text-only pin untouched.*
7. **Routes/throttle** — `api/urls.py` `path("images/", PostImageUploadView, name="image-upload")`;
   `forum_host/api_urls.py` mirror via a throttled wrapper; `forum_host/api.py` `image_upload`
   wrapper (`method="POST"`, `name="post"`); `forum_host/constants.py` add `image_upload`
   (e.g. `"30/h"`). *Update parity, callback-pin (`wrapped`), and add a throttle test in
   `tests/test_ratelimits.py`.*

**Verify:** `python manage.py test packages.wagtail_forum apps.forum_host.tests.test_ratelimits
--noinput`; `python manage.py spectacular --file /dev/null` exits 0 with `/forum/images/`.

## PR-3b — web (TDD Vitest; separate branch off main, after PR-3a merges)

Types (`ImageBlock` in `types/blog.ts` union) · `StreamFieldRenderer` `image` case ·
TipTap image node + "Add image" toolbar button + trim nh3-flattened buttons
(heading/quote/strike/code-block) · bidirectional `toBodyBlocks`/`fromBodyBlocks` ·
`uploadPostImage` → `POST /api/v1/forum/images/` · delete the three dead legacy fns
(`fetchPostImages`/`deletePostImage`/`reorderPostImages`) + dead types (`Attachment`,
`BackendImage`, `mapImageToAttachment`) + orphaned `ImageUploadWidget`. Detailed in the
approved plan-mode file `~/.claude/plans/snug-soaring-volcano.md`; expand into its own plan
doc when PR-3a is merged.
