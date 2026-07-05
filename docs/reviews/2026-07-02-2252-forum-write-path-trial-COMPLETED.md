# Forum Write-Path Review — 2026-07-02 (todo-244 trial findings)

Source: the todo-244 side-by-side review trial (bundled `/code-review` at xhigh
vs the four generic custom reviewers) run on commit `c3cbdd3` (forum PR-2a
backend write path). Every finding below was **re-verified against main at
`d52cf14`** on 2026-07-02 before filing — line numbers refer to current main.
Full trial methodology and verifier evidence:
`todos/archive/244-completed-p3-rationalize-reviewer-agent-fleet.md`.

Paths abbreviated: `W = backend/packages/wagtail_forum/wagtail_forum`.

## Findings

### Correctness (bundled /code-review; adversarially verified)

1. **Workflow wedge after a flagged edit** — `W/workflow.py:116`:
   `submit_edit_for_moderation` always calls `workflow.start(obj, None)`, but
   Wagtail permits only ONE active WorkflowState (IN_PROGRESS **or**
   NEEDS_CHANGES) per object. After one spam-rejected edit leaves
   NEEDS_CHANGES, every later `start()` raises `ValidationError`, which the
   view swallows → the post is permanently stuck: no future edit by that
   author is ever screened or published, with no API recovery. Wagtail's own
   resubmit flow uses `current_workflow_state.resume()`/`cancel()`.
2. **NULL-author crash loses moderator edits** — `W/workflow.py:108`:
   `ForumProfile.for_user(obj.author)` with `Post.author = None` (SET_NULL on
   account deletion; the serializer renders `[deleted]`, so this state is
   supported) raises before `save_revision` → a moderator's redaction edit is
   silently discarded while the API returns 200 "pending".
3. **Fake "pending" on edit failure** — `W/api/views.py:407-413`: the blanket
   `except Exception → moderation_status='pending'` was copied from the create
   path, where a draft row already exists before submit. On the edit path a
   failure before/inside `save_revision` persists nothing, so the client is
   told the edit awaits moderation when it was never recorded.
4. **`moderation_decided` signal never fired for edits** — `W/workflow.py`:
   the create path notifies hosts at line 82; `submit_edit_for_moderation`
   ends without any signal, so host notification/dashboard layers never hear
   about edit outcomes.
5. **DELETE skips the closed/locked-topic guard** — `W/api/views.py` delete
   handler: PATCH 409s on `topic.is_closed or topic.locked` (line 401) but
   DELETE checks only `is_opening_post` (line 434) — authors can gut a
   moderator-frozen thread, and the unpublish recount mutates its counters.
6. **Per-post `LockableMixin` lock ignored** — Post is admin-lockable
   (LockableMixin + registered SnippetViewSet lock UI), but no write path
   checks `post.locked`; a trusted author's PATCH publishes over a
   moderator-locked post (Wagtail enforces locks only in admin views).
7. **409 advises an endpoint that doesn't exist** — `W/api/views.py:435`:
   "Cannot delete the opening post; delete the topic." — no topic-delete
   route exists in either URL config; topic deletion is Wagtail-admin-only.
8. **`can_edit`/`can_delete` affordances lie** — `W/api/serializers.py:277-289`:
   both flags compute only owner-or-moderator, omitting the view's
   opening-post (delete→409) and closed/locked-topic (edit→409) rules; the
   PR-2b web UI gates buttons on exactly these flags, so users see actions
   that always 409.

### Checklist gaps (custom generic reviewers; verified)

9. **No unauthenticated 401 test for PATCH/DELETE `/posts/{id}/`** — every
   write test `force_authenticate`s first; dropping
   `permission_classes = [IsAuthenticated]` would pass the whole suite.
10. **`locked=True` operand of the edit guard untested** — only
    `is_closed=True` is exercised on the PATCH path (the reply path tests
    both); deleting `or topic.locked` from the guard would pass the suite.
11. **429 responses undocumented in OpenAPI** — the host throttle wrappers
    (`backend/apps/forum_host/api.py`) add no `@extend_schema` 429 entries and
    no package response map includes 429, yet the endpoints return it
    (test-asserted). Related: `MeProfileView` has no `@extend_schema` at all;
    `capabilities` SerializerMethodField lacks `@extend_schema_field`.

### Cleanup (bundled quality angles)

12. **Write-path duplication cluster** — the post-visibility predicate exists
    in 3 shapes (PostWriteView `_get_editable`, ReactionToggleView, list-view
    queryset filters); `get_permissions()` is duplicated verbatim
    (`W/api/views.py:134` and `:271`) where declarative
    `IsAuthenticatedOrReadOnly` suffices; `PostEditSerializer` is a byte-copy
    of `ReplyCreateSerializer` (`W/api/serializers.py:301/:308`); the
    trust-routing core is duplicated between `submit_for_moderation` and
    `submit_edit_for_moderation`; PATCH does a redundant `refresh_from_db`
    (the helper already refreshes); `_get_editable` uses fetch-then-check
    (2 queries) instead of the established single-query shape; the host
    throttle guard test pins class identity but not per-method rates (a new
    unsafe method ships unthrottled); a comment still references the deleted
    `ReplyCreateView`; `submit_edit_for_moderation` is a bare `def` (backend
    convention: type hints on service methods).

### Plausible (unverified mechanism, filed with #1-4)

13. **PATCH/DELETE race can republish a just-deleted post** — no
    atomicity/locking between `_get_editable`'s `live` check and the
    trusted-path `revision.publish()`; a PATCH racing a moderator unpublish
    can bring the post back live.

### Not filed (already fixed or refuted)

- Web `updatePost` legacy contract — fixed by PR-2b (#396).
- `serialize_forum_body` StreamValue N+1 — fixed in PR-3a (#406, raw_data).
- Search-excerpt "XSS" — refuted (nh3-sanitized at write; client strips tags).
- `signature` "unbounded" — refuted (model caps at CharField(max_length=255)).
- `topic_id` missing `read_only=True` — refuted as bug (serializer never used
  for input); folded into finding 11's schema-hygiene scope.
- Unpublish "zombie revision" — refuted (NEEDS_CHANGES isn't approvable;
  SpamCheckTask resolves synchronously).

## Finding Status

One line per todo (findings were grouped into 6 todos, not converted 1:1), keyed
by each todo's `source_finding` — the lead number shown. The mapping is 1:1
(6 todos ↔ 6 lines), so when all six archive the section is fully checked and
the doc renames to `-COMPLETED`. Match the lead token WITH its trailing space
(`#1 `, not `#1`) so it doesn't also hit `#11`/`#12`.

- [x] #1 edit-moderation failure cluster (covers #2, #3, #4, #13) → todo 250 (completed 2026-07-03)
- [x] #5 write-path guard gaps (covers #6, #7) → todo 251 (completed 2026-07-04)
- [x] #8 can-edit-delete-affordance-parity → todo 252 (completed 2026-07-04)
- [x] #9 write-endpoint test gaps (covers #10) → todo 253 (completed 2026-07-04)
- [x] #11 429-undocumented-in-openapi → todo 254 (completed 2026-07-04)
- [x] #12 write-path-duplication-cluster → todo 255 (completed 2026-07-04)
