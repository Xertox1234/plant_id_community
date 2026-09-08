---
status: pending
priority: p2
issue_id: "374"
tags: [forum, frontend, mobile, wagtail-images, ux]
dependencies: []
---

# Forum image reuse-picker + self-service delete UI (React + Flutter)

## Problem

The backend now grants every forum member Wagtail's own image-ownership
permissions on the forum's image collection (`add_image` + `choose_image`
via the "Forum Members" group; `change_image` for "Forum Moderators" — see
`apps/forum_host/bootstrap.py`) and exposes two endpoints built on top of
that: `GET /forum/images/mine/` (a member's own previously-uploaded forum
images, paginated) and `DELETE /forum/images/<id>/` (self-service delete,
ownership-checked via Wagtail's real `permission_policy`, with moderator
override). Neither the React web composer nor the Flutter app has any UI
that calls either endpoint — members can only ever upload a fresh photo when
composing a post, and have no way to remove one they previously shared to
the forum. The permission plumbing is live and does nothing without a UI on
top of it.

## Findings

- `packages/wagtail_forum/wagtail_forum/api/image_management.py` defines
  `MyForumImagesView` (list, cursor-paginated via `ForumImageCursorPagination`)
  and `ForumImageDetailView.delete` — but `web/src` and
  `plant_community_mobile/lib` have no reference anywhere to either endpoint;
  confirmed with `grep -rn "images/mine" web/src plant_community_mobile/lib`
  and `grep -rn "forum/images/" web/src plant_community_mobile/lib` (no
  client-side calls to either route beyond the existing upload-only path).
- `web/src/pages/IdentifyPage.tsx`'s `handleAskCommunity` and the plain
  `<input type="file">` composer flow in `web/src/components/forum/
  TipTapEditor.tsx` always call `uploadPostImage` (a fresh multipart upload)
  — there is no "or pick one you've already posted" step anywhere in the
  compose UI.
- `plant_community_mobile/lib/features/forum/` has display-side identification
  widgets (`identification_card.dart`) but no compose-side image picker or
  management screen at all.
- Wagtail's own `choose` permission is collection-wide by design; the
  product decision made when the backend shipped (see conversation history /
  `apps/forum_host/bootstrap.py`'s `_ensure_forum_image_permissions`
  docstring) was a **personal** library — `MyForumImagesView` already scopes
  the queryset to `uploaded_by_user=request.user`, so the client does not
  need to (and must not) do that filtering itself.

## Proposed Solutions

### Option 1: React first, Flutter as a fast-follow (Recommended)

- **Implementation:** Add a "Choose from your photos" affordance next to the
  existing upload control in `web/src/components/forum/TipTapEditor.tsx`
  (and wherever `IdentifyPage.tsx`'s `handleAskCommunity` composes its own
  upload step) that opens a small grid backed by
  `GET /forum/images/mine/`, letting the user pick an existing `image_id`
  instead of re-uploading. Add a delete affordance (e.g. in the user's
  profile/settings, or directly on the picker grid) calling
  `DELETE /forum/images/<id>/`, with a confirmation step and a clear message
  that removed images render as a no-photo placeholder in any post that
  referenced them (this is already true server-side — see
  `serialize_forum_body`'s image-map fallback — nothing new to build there).
  Ship Flutter's equivalent (a picker screen + delete action in
  `plant_community_mobile/lib/features/forum/`) as a follow-up PR once the
  React version's UX is validated.
- **Pros:** Faster to ship and validate with real usage; React is the
  higher-traffic client today; avoids building the same UX twice before
  either has been used.
- **Cons:** Flutter members lack the feature until the follow-up ships —
  acceptable since they currently lack it entirely.
- **Effort:** ~4-6h React (picker component + delete control + empty/error
  states), ~4-6h Flutter follow-up.
- **Risk:** Low — both endpoints are already covered by
  `tests/api/test_image_management.py`; this is pure client work against a
  stable, tested contract.

### Option 2: Ship both clients together

Same UI shape, built in lockstep for React and Flutter in one PR.

- **Pros:** No feature gap between clients.
- **Cons:** Roughly doubles time-to-ship for the first usable version; delays
  validating the UX with real users.

## Recommended Action

1. React: build the "choose from your photos" picker (cursor-paginated grid,
   reusing `ForumImageCursorPagination`'s `next`/`previous` shape) and wire it
   into the composer's image-attach step in `TipTapEditor.tsx` and the
   `IdentifyPage.tsx` "Ask the community" handoff.
2. React: add a delete-my-image control (profile/settings screen is the
   likely home — check for an existing "manage my uploads" section before
   adding a new one) calling `DELETE /forum/images/<id>/`, with a confirm
   step.
3. Handle `403` (not a Forum Member — should not occur for any signed-up
   user post-backfill, but the endpoint enforces it) and empty-list states
   explicitly rather than letting them read as a loading spinner forever.
4. Flutter: mirror both once the React UX is settled (Option 1) or in the
   same pass (Option 2).
5. Update `web/src/services/forumService.ts` (or wherever `uploadPostImage`
   lives) with `listMyForumImages()` / `deleteForumImage(id)` wrappers so
   both new UI pieces share one client implementation.

## Technical Details

- List: `GET /forum/images/mine/` → paginated `{next, previous, results:
  [{id, url, alt, decorative, width, height}, ...]}` (same per-item shape
  `uploadPostImage` already returns, so existing image-rendering components
  should drop in unchanged).
- Delete: `DELETE /forum/images/<id>/` → `204` on success, `403` if not the
  owner and not a moderator, `404` if the id doesn't exist or isn't in the
  forum collection.
- Both require `IsAuthenticated`; the list additionally 403s if the caller
  somehow isn't in "Forum Members" (should be everyone post-backfill —
  `apps/forum_host/management/commands/backfill_forum_members.py`).
- Reference implementation/tests:
  `packages/wagtail_forum/wagtail_forum/api/image_management.py`,
  `packages/wagtail_forum/wagtail_forum/tests/api/test_image_management.py`.

## Acceptance Criteria

- [ ] React composer offers "choose from your photos" as an alternative to a
      fresh upload, backed by `GET /forum/images/mine/`.
- [ ] React exposes a way to delete a previously-uploaded forum image via
      `DELETE /forum/images/<id>/`, with a confirmation step.
- [ ] Deleting an image that is currently referenced by a live post is
      handled gracefully in the UI (no crash; matches the server's
      no-photo-fallback behavior).
- [ ] Flutter has the equivalent picker + delete affordance (may ship as a
      separate follow-up PR per Option 1).
- [ ] New client code has test coverage (component/widget tests) for the
      picker, the delete confirmation, and the 403/empty-list states.

## Work Log

### 2026-09-08 - Backend half landed; this todo stays open for the UI

The premise above was **not true when this todo was written**. It says the
backend "exposes two endpoints" and that "the permission plumbing is live" —
but `images/mine/` and `images/<int:image_id>/` were added to the package's
`wagtail_forum/api/urls.py` only. Production serves
`apps.forum_host.api_urls`, which never mounted either, so both returned 404
and the delete endpoint would have shipped unthrottled. The repo's own parity
guard, `test_host_api_routes_match_package`, was failing exactly as designed.

A review of that uncommitted work (bundled `/code-review`, todo 358 session)
found nine issues; all are fixed in the backend PR:

- **Routes unmounted** (HIGH) — both now in `apps/forum_host/api_urls.py`. The
  GET list mounts straight from the package like the other read views; DELETE
  goes through a new `@_throttled("image_delete", "DELETE")` wrapper in
  `apps/forum_host/api.py`, with a new `image_delete: 20/h` rate sized against
  `post_delete`.
- **Missing `UnversionedForumAPIMixin`** (HIGH) — both views inherited the
  host's `NamespaceVersioning`, so `determine_version` raised `NotFound` in
  `initial()` *before* authentication and every assertion in the new test file
  got a 404 instead of 401/403/200/204. They also silently lost the
  `TouchLastSeenMixin` presence touch that rides on the same mixin.
- **`filter_backends` / `serializer_class`** (MEDIUM) — `?ordering=id` reached
  `OrderingFilter.get_default_valid_fields`, which falls back to
  `get_serializer_class()` and raises `ImproperlyConfigured` → 500. Now
  `filter_backends = []`, matching `BoardListView`/`TopicBookmarkListView`.
- **`PrivateForumReadCacheMixin`** (MEDIUM) — a per-user image library was
  served with no `Cache-Control`, which a "cache everything" CDN rule can
  store and replay to another viewer.
- **`swagger_fake_view` guard** (MEDIUM) — `get_queryset` raised
  `PermissionDenied` on any schema path that instantiates the view without an
  authenticated request.
- **`image_perms[codename]` KeyError** (MEDIUM) — bare dict indexing inside a
  `post_migrate` receiver aborts `manage.py migrate` (a failed deploy) if
  Wagtail ever renames or drops one of these codenames. Now `.get()` with a
  warning, matching the Meta-permission block forty lines above whose comment
  already says "the list stays correct even if a Wagtail version drops one".
- **Collection-wide `choose` check** (LOW) — `user_has_permission(user,
  "choose")` passes no collection, so a blog editor with `choose_image`
  anywhere cleared a gate whose whole job is "is this a forum member?". Now
  scoped via `collections_user_has_permission_for`.
- **`group.user_set.add(*to_add)`** (LOW) — unpacked the entire remaining-user
  queryset on the first production run. Now chunked at 1000.
- **Degradation proven only for the legacy block shape** (LOW) — the test
  stored a bare PK, the pre-0037 shape, which takes a different branch in
  `image_block_pk`. Added the `ImageBlock` dict shape production actually
  writes.

**Still open, and the reason this todo stays pending:** every acceptance
criterion below is client-side. `web/src` and `plant_community_mobile/lib`
still have no call to either endpoint. The difference now is that the backend
they will call actually answers.

## Notes

- Related but explicitly out of scope here: `DiseaseDiagnosePage.tsx` still
  lacks the "Ask the community" upload handoff that `IdentifyPage.tsx`
  already has (a text hint only, no button) — separate todo if prioritized.
- Also related: the disclosure copy discussed for the "Ask the community"
  flow ("your photo will be uploaded to the forum and visible to the
  community... removing it from your collection won't remove it from the
  forum") was not part of this backend change and should land alongside
  whichever client work touches that flow next.
- Priority is P2 rather than P1/P3: the backend permission and API work this
  depends on is already merged and inert without a UI, but nothing is broken
  or blocking other work in the meantime — it's a completed capability
  waiting on its front end, not a regression.
