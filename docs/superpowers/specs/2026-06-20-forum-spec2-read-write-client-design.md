# Forum Spec 2 — Read/Write API + Web Client Migration — Design

- **Date:** 2026-06-20
- **Status:** Approved (brainstorming) — ready for implementation planning
- **Scope:** Web only. Build the missing `wagtail_forum` read/write endpoints and
  migrate the React web forum client off the retired machina dialect to the new
  API, at **full feature parity** with today's (broken) UI.
- **Tracks:** todo `231-pending-p1-forum-spec2-read-api-web-client.md`
  (forum audit finding **H4**); design Spec 1 =
  `2026-06-06-wagtail-native-forum-package-design.md` (which named this as "Spec 2").
- **Author:** Brainstorming session (William + Claude)

## Background

The forum was rebuilt as a Wagtail-native package (`wagtail_forum`, host
`apps/forum_host`) in Spec 1; machina was retired. Spec 1 was **backend only** and
explicitly deferred updating the React/Flutter clients to "Spec 2." That deferral
was never done, so the **deployed web forum is 100% broken**.

Verified against production (`plantidcommunity-production.up.railway.app`) on
2026-06-20:

- `GET /api/v1/forum/boards/` → **200** `{"results":[]}` — new API is live and healthy.
- `GET /api/v1/forum/categories/` → **404 (HTML body)** — the path the web client
  still calls.

The visible symptom on `houseplant-md.com/forum` is **"Error loading categories:
Request failed."** Mechanism: `CategoryListPage` → `fetchCategoryTree()` →
`GET …/forum/categories/` returns a 404 with an HTML body; `authenticatedFetch`
(`web/src/services/forumService.ts:55-58`) sees `!response.ok`, `response.json()`
throws on the HTML, and the `.catch(() => ({ message: 'Request failed' }))`
fallback surfaces the generic error. Every other forum page fails the same way.

### Root cause

The deployed web client (`forumService.ts`) speaks the **retired machina dialect**
(`categories/`, `topics/<id>/`, `posts/?topic=`, `posts/<id>/delete/`, …). The new
`wagtail_forum` API serves a different surface (`boards/`, `boards/<slug>/topics/`,
…) and is **missing** the read endpoints the client needs (topic detail, post
list) and several write endpoints (post edit, delete, image upload).

## Goal

A working web forum at parity with the current UI's feature set:

- Browse: boards → threads (per board) → thread detail with posts.
- Compose: create topic, reply, edit own post, delete own post.
- React: toggle reactions, see counts + the current user's active reactions.
- Images: upload and display inline post images.
- Search: topics + posts (post bodies indexed for full parity).
- No machina paths remain: `grep -r "categories/" web/src/services/` is empty.

## Non-Goals / Out of Scope (named, not silently dropped)

- **Flutter forum client** — `plant_community_mobile/lib/features/forum/forum_screen.dart`
  is an explicit stub ("live posting is not yet implemented", hardcoded sample
  posts). There is no real Flutter forum client to migrate; building one is a
  **separate future spec**.
- **Public profiles** (`GET /users/{id}/profile/`) — only `/me/profile/` exists;
  not required for parity. Deferred.
- **Delta-sync hardening** — compound `(updated_at, id)` cursor and soft-delete
  tombstones (todo 231 sub-items) are backend-internal to `/sync/`, not used by
  the web client. Deferred; remain tracked under todo 231.
- **Post preview** — deferred in Spec 1; unchanged here.
- **WebSockets / real-time** — unchanged from Spec 1.

## Architecture & invariants

The forum is a **reusable, zero-plant-coupling package** mounted by a thin host:

- Package endpoints live in `backend/packages/wagtail_forum/wagtail_forum/api/`
  (`views.py`, `urls.py`, `serializers.py`, `pagination.py`, `sanitize.py`,
  `idempotency.py`, `exceptions.py`).
- The host (`backend/apps/forum_host/`) re-mounts each package route via a
  **rate-limited wrapper** (`api.py` + `api_urls.py`) so throttling lives in the
  app, not the reusable core.
- A **route-parity test** (`apps/forum_host/tests/test_ratelimits.py`) asserts the
  host and package route sets stay identical — a new package endpoint that is not
  host-wrapped fails CI. **Every new endpoint below must be added in both places
  and keep this test green.**
- Auth: DRF `DEFAULT_AUTHENTICATION_CLASSES` lead with
  `apps.users.authentication.CookieJWTAuthentication`, so the web cookie-JWT
  session authenticates write endpoints (`IsAuthenticated`) with no Bearer header.
  Mutating requests already send `X-CSRFToken` + `credentials: 'include'`.
- **Versioning:** every existing forum view sets `versioning_class = None` because
  the host mounts the package under a `NamespaceVersioning` `v1` namespace that
  would otherwise 404 the package's own routes. **Every new view below MUST set
  `versioning_class = None`** — omitting it is a silent 404.

No plant imports may be added to the package core (a package test runs against a
minimal settings module to prove zero coupling).

## Implementation phases

Sequenced so the production error dies first, at lowest risk (the read path is
public — that is why `/boards/` already 200s without auth).

### Phase 1 — Read path (removes the live error)

**New package endpoints (+ host wrappers + parity test):**

| Endpoint | View | Notes |
|---|---|---|
| `GET /topics/{id}/` | `TopicDetailView` | Live topic on a visible board, else 404. Returns detail serializer (below). |
| `GET /topics/{id}/posts/` | `PostListView` | Cursor pagination (mirrors `TopicListView`); ordered `created_at, id`. |

**Visibility** mirrors the existing guards (`_visible_boards()` = `.live().public()`;
topic `live=True`): a hidden/draft topic or one on a restricted/non-live board is
**404**, never 403 (no existence leak) — consistent with `ReplyCreateView`.

**`TopicDetailSerializer`** (read): `id, title, slug, board {id, slug, title},
author, is_pinned, is_closed, locked, reply_count, view_count, created_at,
last_post_at, opening_post_id`. Denormalized counters only — no joins to
`_revisions`/`workflow_states` (preserve the mobile-cheap-read invariant).

**`PostSerializer`** (read): `id, topic_id, author {username, display_name,
trust_level}, body (StreamField JSON, see §Body), created_at, updated_at,
edited_at (nullable), edited_by (username/display_name, nullable), is_opening_post,
status (live|pending), reaction_counts, can_edit, can_delete (capability flags
computed for request.user)`. No `reacted_by_me` — `PostCard.tsx` renders reaction
*counts* only and does not highlight the user's own reactions, so per-user reaction
state is unused at parity (a `my_reactions: string[]` field for active-reaction
highlighting is a deferred enhancement).

**Pinned `assertNumQueries`** on the post-list endpoint proves the denormalized-read
claim and guards N+1 (reactions/author must not fan out per post).

**Client (Phase 1):** rewrite the read side of `forumService.ts` +
`forumMappers.ts` + `types/forum.ts`; update `CategoryListPage`, `ThreadListPage`,
`ThreadDetailPage` (read render), `SearchPage`. Cursor pagination replaces
page-number ("Load More" follows the `next` cursor; "remaining" derives from the
topic's `reply_count`). Boards route by **slug**, topics by **id**. `PostCard.tsx`
moves from `sanitizeHtml(content_raw)` + `dangerouslySetInnerHTML` to rendering the
StreamField `body` via the extended `StreamFieldRenderer` (§Body); it already reads
`edited_at`/`edited_by`, which the new `PostSerializer` provides.

**Board seeding (decided — auto-seed):** `forum_host` bootstrap (`bootstrap.py`,
`post_migrate`) today seeds only the moderation workflow + "Forum Moderators"
group — **no `ForumBoard`** — so a freshly-migrated forum is empty and `/forum`
renders "No categories available yet." Extend the host bootstrap to idempotently
ensure a `ForumIndex` page + one starter `ForumBoard` ("General Discussion") so
Phase 1 renders real content and tests have a board. Seeding lives in `forum_host`
(the app), **not** the reusable package core. Plan must settle page-tree placement
(parent page / site root, locale, treebeard `add_child`) and idempotency. This is
part of Phase 1's definition-of-done — without it, the empty state is
indistinguishable from a bug.

**Search (decided — full parity, topics + posts):** the existing `SearchView`
indexes/searches topic titles only and returns `{results:[{id,slug,title}]}`; the
current `SearchPage` expects topic **and** post hits. Extend the backend: add
`index.Indexed` + `search_fields` on `Post` (body), search across live topics +
posts (on visible boards), and return `{topics:[...], posts:[...]}` with serialized
hits (post hit: `id, topic_id, excerpt, author`). Bound + query-count-pin the
search path. Client `searchForum` maps the new shape to the existing
`SearchForumResponse`.

### Phase 2 — Write path

**Route rationalization** (do now — no consumer depends on these yet; parity test
guards it):

- `POST /boards/{slug}/topics/create/` → **`POST /boards/{slug}/topics/`**
- `POST /topics/{id}/posts/create/` → **`POST /topics/{id}/posts/`**

(`TopicListView`/`PostListView` keep `GET` on the same collection paths; the create
views take `POST`. Rename view route names + host wrappers + parity test + the
existing forum_host rate-limit tests in lockstep.)

**New package endpoints (+ host wrappers + parity test):**

| Endpoint | View | Notes |
|---|---|---|
| `PATCH /posts/{id}/` | `PostUpdateView` | Author (or moderator) edits own post → new `RevisionMixin` revision; re-runs `validate_forum_body`; rejects if topic `is_closed`/`locked` (409); 404 on hidden; 403 on not-author/non-mod. Sets `edited=True`. |
| `DELETE /posts/{id}/` | `PostDeleteView` | Author (or moderator) soft-deletes; recounts topic `reply_count`. Opening-post rule: see Open Questions. |

Wire the client write side: create topic, reply, edit, delete — onto the
**existing** `TopicCreateView`/`ReplyCreateView`/`ReactionToggleView` plus the two
new write views. Reactions: the toggle endpoint already exists; adapt the client to
its `{reaction_counts, reacted}` response and drive UI from the post's
`reaction_counts`.

**De-risk first (before building the composer):** prototype the
TipTap-HTML → `paragraph` `RichTextBlock` value → `expand_db_html()` round-trip on
a throwaway spike. Wagtail's stored rich-text DB format is not identical to editor
output HTML; `bold`/`italic`/`ol`/`ul`/`code`/external-`link` should round-trip,
but confirm nothing corrupts silently through `to_python`/`expand_db_html` before
committing the composer design. This is the Phase 2 long pole and where scope can
grow.

### Phase 3 — Images

**New package endpoint (+ host wrapper + parity test):**

| Endpoint | View | Notes |
|---|---|---|
| `POST /topics/{id}/images/` | `PostImageUploadView` | 4-layer-validated upload (extension, MIME, size, PIL — `backend/docs/patterns/security/file-upload.md`) into a **forum-scoped Wagtail collection**; returns `{id, renditions}`. `IsAuthenticated`. |

**Relax `validate_forum_body`** (`api/sanitize.py:96-106` currently rejects all
chooser/image blocks): accept an `image` block **only if** its id references an
image in the forum collection (collection-membership check) — closes the IDOR /
nonexistent-id holes the current hard rejection guards against. All other chooser
types stay rejected.

**Read render:** the `image` block serializes to renditions (srcset-style); add an
`image` case to the web `StreamFieldRenderer` (it was removed; line 94). On read,
inline images come back inside the body StreamField — no separate attachments call.

> Image model note: Spec 1 models inline images as `ImageChooserBlock` inside the
> body StreamField (Wagtail Image → renditions), **not** a separate per-post
> attachment model (the machina `ForumPostImage` shape the old client used). The
> client's compose flow therefore changes from "attach files to a post" to "insert
> an image block into the body."

## Body serialization & rendering (cross-cutting)

The post body is **StreamField JSON** on read and write — the package already
mandates this (`TopicCreateSerializer.body`/`ReplyCreateSerializer.body` are
`JSONField` validated by `validate_forum_body`; the machina client sent an HTML
string, which the new API rejects).

- **Block set** (`ForumBodyBlock`): `heading` (text), `paragraph` (RichText:
  bold/italic/link/ol/ul/code), `quote`, `code` (language + code), `image`.
- **Read:** serialize the body as a list of `{type, value}` blocks. The
  `paragraph` block's value is rendered through Wagtail `expand_db_html()` so the
  link rewriter runs (SECURITY note in `blocks.py:18-21`) — **never** raw
  `value.source`. Text blocks (`heading`/`quote`/`code`) stay text-by-contract.
  - **`expand_db_html` query cost:** internal *page*/document links would make
    `expand_db_html` do a per-link DB lookup → a hidden N+1 across a page of posts,
    exactly where the post-list `assertNumQueries` is pinned. This is neutralized
    by the existing write-path sanitizer: `nh3`'s `ALLOWED_ATTRIBUTES` for `<a>` is
    `{href, title}` only (`api/sanitize.py:26`), so Wagtail's `linktype="page"`/`id`
    attributes are stripped on write — no internal-link markup survives for
    `expand_db_html` to resolve. The pinned `assertNumQueries` must **verify** this
    holds (it is the guardrail, not just an assumption); if a future change admits
    internal links, restrict the `paragraph` `link` feature to external-only.
- **Render (web):** reuse the shared `StreamFieldRenderer` — it already handles
  `heading`/`paragraph`/`quote`/`code` (forum `code` = `{language, code}` matches;
  forum `quote` = string is handled by its string-or-struct branch). **Add an
  `image` case.** `paragraph` HTML is DOMPurify-sanitized at render
  (`SANITIZE_PRESETS.STREAMFIELD`) on top of server-side `nh3` on write
  (defense-in-depth).
- **Write/compose:** the composer emits forum-safe block JSON. Minimum viable:
  wrap rich text as `[{type:'paragraph', value:'<p>…</p>'}]`; images add
  `{type:'image', value:<image_id>}` blocks after upload. Replaces the TipTap→HTML
  output. `nh3` server-side sanitization (`sanitize_rich_text`) is the trust
  boundary — direct API POSTs bypass any editor filtering.

## Error handling

The client must surface real backend statuses instead of the generic "Request
failed": **404** (hidden/missing), **409** (closed/locked topic; idempotency twin
in-flight), **422** (idempotency key reused with a different payload), **429**
(throttled — host wrappers; CLAUDE.md gotcha #4 requires 429 not 403), **400**
(validation). `authenticatedFetch` already prefers `error.message`/`error.detail`;
the new views return JSON error bodies so the parse path no longer falls through to
the "Request failed" string.

## Testing strategy

Per CLAUDE.md testing rules — **no DB mocks**, real Postgres + real Wagtail
revision/workflow machinery.

**Backend:**

- `assertNumQueries` pinned on `GET /topics/{id}/posts/` and `GET /topics/{id}/`
  (denormalized-read + N+1 guard; reactions/author must not fan out per post).
- Visibility: hidden/draft topic, restricted/non-live board → 404 on detail, post
  list, edit, delete, upload.
- Edit: author edits → new revision + `edited=True`; non-author → 403; locked/closed
  topic → 409; malformed body → 400 (not 500).
- Delete: author/moderator soft-deletes; `reply_count` recounted; opening-post rule
  enforced (per resolved Open Question).
- Images: 4-layer validation rejects bad uploads; **collection-validation test** —
  an `image` block referencing an out-of-collection / nonexistent id is rejected
  (IDOR guard); a valid forum-collection image round-trips through body validation.
- Search: topic-title **and** post-body hits returned; results scoped to visible
  boards + live content; query-count pinned.
- Board seeding: `forum_host` bootstrap idempotently creates `ForumIndex` + the
  starter `ForumBoard` (running `migrate` twice does not duplicate).
- **Route-parity test green** after every route add/rename; forum_host rate-limit
  tests updated for renamed routes.
- Package zero-coupling test still passes (no plant imports added to core).

**Web:**

- `forumService` + `forumMappers` unit tests rewritten to the new contract;
  machina-shape tests deleted.
- Page tests: `CategoryListPage` renders boards (and the empty state when
  `{"results":[]}`), `ThreadDetailPage` renders a StreamField body **including an
  image block**, compose/edit/delete/react flows, cursor "Load More".
- Type-check + ESLint + Vitest green (web CI gates).

## Resolved decisions (2026-06-23, approved by William)

The four implementation-planning questions below were resolved during the Spec 2
Phase 2/3 brainstorming session, grounded in the actual model code
(`models/posts.py`, `models/topics.py`, `workflow.py`):

1. **Opening-post delete → REJECT (409).** `DELETE` on an `is_opening_post` post
   returns **409** ("delete the topic instead"). Deleting it would orphan the
   topic (it backs `uniq_opening_post_per_topic` + `get_opening_post_id`) or force
   a surprise cascade that removes every reply. Topic-delete stays out of scope.
2. **Edit re-moderation → moderation-by-trust, but an edit NEVER unpublishes live
   content.** A trusted author's edit (`trust >= TRUST_AUTOPUBLISH_LEVEL`) saves a
   new revision and publishes it immediately, setting `edited=True`. An untrusted
   author's edit saves a new revision that enters the spam-check workflow: clean →
   published (`edited=True`); flagged → the **new revision stays pending** while the
   post keeps serving its last-approved revision. No approved content goes dark
   because of an edit. This needs a **dedicated edit helper** — the existing
   `submit_for_moderation` is create-shaped (it force-drafts `live=False`), which
   would unpublish a live post; the edit path must NOT force `live=False`.
3. **Soft-delete → no new field; delete = unpublish (`live=False`).** `PostListView`
   stays `live=True`-only, so a *deleted* post and a *pending* post are both
   unlisted and never need distinguishing → **no migration**. Web does **not** show
   an author their own pending posts (matches current web parity; the Spec-1 mobile
   "awaiting approval" list UX is deferred). `status: pending|published` is returned
   by the **create/reply** responses only (so the composer can show "awaiting
   approval"), **not** by the post-list serializer. Recount `topic.reply_count`
   (live, non-opening posts) on delete.
4. **View-count → no increment in this epic.** `GET /topics/{id}/` does **not** bump
   `view_count`. Meaningful view tracking needs per-session dedup and would add an
   UPDATE to the `assertNumQueries`-pinned detail endpoint; both are out of scope.
   `view_count` renders as-is (deferred enhancement).

## Scope note — todo 231 criteria beyond this (web-focused) spec

This spec is web-only (§Scope) and explicitly defers the `/sync/` compound
`(updated_at, id)` cursor + the read-view `@extend_schema` annotations as
"backend-internal / out of web scope" — but both are **acceptance criteria of
todo 231** (AC3 and AC1 respectively). The implementation plan therefore also
covers, as a self-contained backend slice:

- **AC1:** add `@extend_schema` (+ `swagger_fake_view` guards) to `TopicDetailView`
  and `PostListView` (read endpoints, `expand_db_html`, query-pins already landed
  in Phase 1).
- **AC3:** `SyncView` compound `(updated_at, id)` cursor + same-timestamp livelock
  test. Verified **no consumer** exists (`grep` of `web/` + `plant_community_mobile/`
  for `/sync/`/`next_since` is empty), so the `next_since` contract change is free.
- **AC2 grep caveat:** `grep -r "categories/" web/src/services/` can never be empty
  (`blogService.ts` legitimately calls `/api/v2/categories/` for the blog). The real
  gate is "no machina **forum** paths in `forumService.ts`" (finding H4 was
  forumService-specific).
