---
status: completed
priority: p3
issue_id: "319"
tags: [forum, trust-and-safety, drf, web]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M10"
---

# Forum: private messaging (M10)

## Problem

No private messaging exists between forum members. Originally filed together
with M9 (block/mute) as todo 284, with a hard ordering constraint: **shipping
DMs before block/mute would hand every member an unfilterable private channel
to every other member.** M9 has now shipped (backend PR #577, web UI PR #578,
both merged 2026-08-29), so that gate is satisfied and this finding is
promoted into its own standalone todo per todo 284's own Notes ("ship M9,
leave M10 unstarted").

## Findings

State verified against `main` at 2026-08-29 (todo 284's Work Log): no DM
model, endpoint, or UI exists anywhere in the repo. `UserBlock`
(`backend/packages/wagtail_forum/wagtail_forum/models/user_blocks.py`) now
does exist and is fully wired through every content read path plus
notification fan-out — a future DM feature has a real, tested block primitive
to enforce against at send time (see Recommended Action below).

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

## Recommended Action

Per todo 284's original Phase 2 plan, this needs at minimum:

1. A conversation/message model — decide 1:1 vs. group at design time; the
   audit's framing (and this repo's existing forum surface) only motivates
   1:1.
2. Per-message rate limiting, following this repo's `_throttled()` +
   `DEFAULT_FORUM_RATELIMITS` convention (`apps/forum_host/api.py`,
   `constants.py`).
3. The existing spam backend applied to DM bodies
   (`WAGTAILFORUM_SPAM_BACKEND` — see todo 280; currently unset/dormant in
   prod, an ops decision independent of this todo).
4. **Block enforcement at send time** — a blocked sender must not be able to
   reach the blocked recipient. Decide and document: does the send call
   return a success-shaped response with silent non-delivery, or an explicit
   403? `UserBlock.can_block`/`UserBlock.objects.filter(...)` (both
   directions — mirror `_drop_blocked_pairs` in
   `apps/forum_host/notifications.py`) is the primitive to check against;
   don't re-derive block-pair logic independently.
5. Report-a-DM support, reusing the existing `Report` model/flow
   (`W/models/reports.py`) rather than a parallel one.
6. A retention/tombstone story matching the forum's existing tombstone-prune
   cron (todo 261) — decide whether DMs are covered by the same cron or need
   their own retention policy, and record the choice.

## Technical Details

- Package purity: no `apps.*` imports in `backend/packages/wagtail_forum/`
  (`test_reusability.py`).
- Reuse `UserBlock`'s existing bidirectional-check shape
  (`_should_filter_blocks`/`_exclude_blocked_authors` in
  `W/api/views.py`, `_drop_blocked_pairs` in `apps/forum_host/notifications.py`)
  rather than writing new block-pair logic for DMs — todo 284 already solved
  the "check both directions, moderator bypass, NULL-safety" problems once.
- Patterns: `backend/docs/patterns/domain/forum.md` (trust levels,
  moderation), `backend/docs/patterns/architecture/rate-limiting.md`,
  `backend/docs/patterns/security/input-validation.md`.

## Acceptance Criteria

- [x] A blocked sender cannot deliver a DM to the user who blocked them —
      test, both directions (blocker→blocked and blocked→blocker)
- [x] Conversation/message model with per-message rate limiting — test
- [x] Report-a-DM reuses the existing `Report` model — test
- [x] Retention/tombstone decision recorded in the Work Log (covered by the
      existing cron, or a new one — either is acceptable, silence is not)
- [x] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-08-29 - Promoted out of todo 284 (M9 shipped)

- M9 (block/mute) shipped: backend PR #577 (merge commit
  0abc21425399ffd069972f4c8c52bd5a44ea4d78) + web UI PR #578, both merged.
  Todo 284's hard gate ("no private-messaging code may merge until block/mute
  is merged") is now satisfied.
- Finding re-verified absent on `main` — no DM model/endpoint/UI anywhere in
  the repo.
- Source review's Finding Status line for #M10 re-pointed from todo 284 to
  this todo (319), per this project's re-pointing convention (a promoted
  finding is re-pointed, never checked off, until it actually ships).

### 2026-08-30 - Started by completing-todos skill (run 2026-08-30-0011)

- Picked up by automated workflow. User explicitly requested starting this
  todo despite its own Notes recommending it stay unstarted.

### 2026-08-30 - Implemented and verified

**Model**: `Conversation` (1:1, participants canonicalized by pk via
`Conversation.between()` so the unordered pair is unique regardless of
initiator) + `Message` (plain-text body, not a StreamField) —
`W/models/messages.py`, migration `0025_conversation_message_and_more.py`
(generated via `makemigrations`, not hand-written;
`makemigrations --check --dry-run` confirms no drift after).

**Endpoints** (`W/api/direct_messages.py`, package-side; host-mounted +
throttled in `apps/forum_host/api.py` + `api_urls.py`):
- `POST users/<username>/messages/` — send (creates the conversation on
  first send)
- `GET conversations/` — my conversations
- `GET conversations/<id>/messages/` — messages in one conversation
  (404s a non-participant, same existence-leak posture as `_get_visible_post`)
- `POST messages/<id>/report/` — report-a-DM

**Decisions recorded** (per this todo's Recommended Action items 3-6):
1. **Blocked send → explicit 403**, never a silent success-shaped drop.
   Enforced bidirectionally in the package view (`_is_blocked_pair`, mirrors
   `_drop_blocked_pairs`), not host-side — a correctness invariant, not a
   host policy choice.
2. **Spam-flagged send → explicit 400.** No moderation queue exists for DMs
   (no Wagtail workflow/revision state on `Message`), so there is nothing to
   hold a flagged message IN for review the way `SpamCheckTask` holds a
   Post/Topic. The heuristic/LLM spam backend is reused via `get_spam_backend()`
   through a small `_SpamCheckAdapter` (Message bodies are plain text, not a
   StreamField, so a bare `Message` can't be passed to `extract_text` as-is).
3. **Report-a-DM reuses the `Report` model**, not a parallel `MessageReport`
   model, per this todo's Recommended Action — `post`/`message` are both now
   nullable with a `CheckConstraint` enforcing exactly one set, plus two
   *conditioned* `UniqueConstraint`s (one per target) so a NULL on one column
   never collides with a NULL on the other. `Report.file_for_message()` mirrors
   `Report.file()` (same idempotent-duplicate handling, same
   `flags_received` bump — now credited to the message SENDER, the
   per-user-cumulative-signal reading of that counter) but has NO
   `select_for_update` lock and no `UnpublishAction`-equivalent: unlike a
   Post, a DM has no publish/unpublish state, so crossing the auto-hide
   threshold only flips matching reports to `AUTO_HIDDEN` as a
   moderator-visibility signal — a moderator must still act manually to
   remove content. This is a deliberate scope reduction, not an oversight.
4. **No automatic retention/tombstone job.** Messages persist indefinitely in
   this slice. The existing Topic tombstone-prune cron (todo 261,
   `prune_forum_tombstones` + `railway.cron.json`) does not apply — it exists
   because Topics are hard-deleted and mobile clients need to evict them from
   local cache; DMs are never hard-deleted here, so there is nothing to
   tombstone yet. Revisit once a delete/moderation action for DMs exists.

**Rate limiting**: `message_send` (30/h, per-user, same tier as
`reply_create`) is a new throttle; `message-report` reuses the existing
`report_create` rate (same `Report` model/flow as post reports). Both are
enforced via the existing `_throttled()` decorator and covered by
`test_host_api_routes_match_package` / `test_wrapped_routes_use_the_throttled_views`
/ `test_every_unsafe_handler_is_throttled` (all three updated).

**Verification** (commands run from `backend/`, venv active):

```
$ python manage.py makemigrations --check --dry-run
No changes detected

$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py spectacular --file /dev/null   # exact CI command
[exit 0] Warnings: 189 (107 unique)  Errors: 204 (46 unique)   <- pre-existing,
   unrelated to this change (garden/garden_calendar apps); the only two new
   entries attributable to this todo are the same class of benign
   SerializerMethodField type-hint warning every other forum author field
   already emits (get_sender/get_other_participant).

$ python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_messages.py \
    packages/wagtail_forum/wagtail_forum/tests/test_reports.py \
    packages/wagtail_forum/wagtail_forum/tests/api/test_direct_messages_api.py \
    apps/forum_host/tests/test_ratelimits.py \
    apps/forum_host/tests/test_api_mounted.py --create-db -q
54 passed

$ python -m pytest apps/forum_host packages/wagtail_forum --reuse-db -q
903 passed
```

All 5 acceptance criteria verified and checked off above. No `apps.*` import
was added to `backend/packages/wagtail_forum/` (package purity preserved —
`test_reusability.py` passes as part of the 903).

**Known issues / follow-ups not blocking this todo**: none filed. This is a
backend-only slice — no web/mobile UI ships in this todo, matching the
Acceptance Criteria (which are backend-only) and the Recommended Action
(which never mentions a UI). A future UI todo would consume these four
endpoints.

### 2026-08-30 - Code review (code-review-orchestrator: django-drf-reviewer,
wagtail-reviewer, cross-cutting-reviewer)

18 raw findings across the three domain reviewers (4 high, 8 medium, 6 low)
— 17 unique after merging one duplicate (django-drf-reviewer and
cross-cutting-reviewer independently flagged the same `ReportViewSet` admin
gap, at medium and high severity respectively). All 17 repaired, none
accepted-unfixed:

- **[high] `Report.file_for_message` silently no-ops the `flags_received`
  bump for a DM-only sender** — no `ForumProfile` row exists yet (Message
  creation fires no profile-seeding signal, unlike the post/topic publish
  signal), so the original bare `.filter().update()` matched zero rows for
  exactly the spammer population this feature is meant to credit. Fixed via
  `ForumProfile.for_user()` get-or-create before the atomic block (called
  outside it — `for_user()`'s own race-handling has no nested savepoint).
  The regression test was ALSO fixed: it originally pre-created the profile,
  which hid the bug (django-drf-reviewer + advisor-style catch).
- **[high] Wagtail admin `ReportViewSet` unusable for message reports** —
  `list_display=["post", ...]` and `select_related("post", ...)` both
  omitted the new `message` FK, so a moderator had no way to see or act on a
  filed DM report (found independently by both django-drf-reviewer and
  cross-cutting-reviewer). Fixed: added `Report.target` property (post or
  message) and updated `list_display`/`select_related`.
- **[high] `participant_b` arm of every OR-guard was completely untested** —
  `Conversation.between()` always assigns the lower-pk user to
  `participant_a`, and every original test authenticated as that user, so
  deleting the `participant_b` arm from either the list filter or the
  membership check would not have failed any test. Fixed: added
  `test_conversation_list_visible_from_the_later_created_participant_too`.
- **[high] No unauthenticated-401 coverage on any of the 4 new endpoints** —
  `IsAuthenticated` on the two GET-only views has no framework backstop
  (project default is `IsAuthenticatedOrReadOnly`, which does not block
  anon GET), so it was entirely unverified. Fixed: added a 401 test per
  endpoint (send, report, conversation-list, conversation-messages).
- **[medium] `MessageSendView.post` had no `transaction.atomic()`** around
  `Conversation.between()` + `Message.objects.create()`, unlike
  `Report.file()`'s explicit same-savepoint discipline. Fixed.
- **[medium] Block enforcement was send-time only** — after either side
  blocked the other, both could still read (and the docstring's
  "correctness invariant" framing was contradicted by) the existing
  conversation via the two GET views. Fixed: both views now exclude/404 a
  blocked pair, symmetrically for both participants (mirrors the
  bidirectional send-time check) — recorded as a design decision in the
  module docstring, plus 2 new tests.
- **[medium] Spam-backend-unavailable conflated with a genuine flag** — a
  fail-closed LLM provider verdict and a real policy violation both
  produced the same generic 400 message, and a package-side view has no
  host-only reason string to special-case. Fixed: surface the backend's
  real `spam_result.reason` in the 400 detail instead.
- **[medium] `MessageReportView`'s non-participant guard had no denied-case
  test** — deleting it would not have failed any test. Fixed: added
  `test_a_non_participant_cannot_report_a_message`.
- **[medium] Missing `@extend_schema_field(AUTHOR_SCHEMA)`** on
  `get_other_participant`/`get_sender` — both shipped as untyped `string` in
  the OpenAPI schema. Fixed, plus extended
  `test_read_serializer_method_fields_are_typed_not_default_string` to cover
  the new `Conversation`/`Message` components.
- **[medium] Missing `@extend_schema` class decorators** on
  `ConversationListView`/`ConversationMessagesView`. Fixed.
- **[medium] No query-count regression test** for the two new
  `serialize_forum_author`-consuming list views. Fixed — pinned at 4
  (presence-touch + 2 blocked-id lookups + 1 page query); the test clears
  the cache first since `TouchLastSeenMixin`'s throttle otherwise makes the
  count depend on incidental cache state from an earlier test (a real
  flakiness risk caught while verifying the pin, not just following the
  reviewer's suggestion).
- **[low]** Dead `except Message.DoesNotExist` in `MessageReportView.post`
  (copied from `PostReportView` but `file_for_message` has no `.get()` call
  that could raise it) — removed.
- **[low]** No dedicated `ConversationCursorPagination` — the base
  `ForumCursorPagination`'s `-id` ordering was coincidentally correct but
  didn't self-enforce `Conversation.Meta.ordering` the way every sibling
  pagination class does. Fixed.
- **[low]** Misleading comment implying `message_send`'s rate shares a
  budget with `report_create` — verified against `django_ratelimit` source
  (`get_usage`'s `group=None` fallback derives the bucket from the
  decorated function's `__qualname__`, confirmed empirically) that they are
  in fact independent buckets despite reusing the same rate NAME. Comment
  corrected.
- **[low]** README's Idempotency section omitted `message` create from the
  enumerated write list. Fixed.
- **[low]** `Message.body`'s `max_length=4000` duplicated as a literal in
  the serializer. Fixed via a shared `MESSAGE_BODY_MAX_CHARS` constant.

Full suite re-verified after repair:
```
$ python manage.py makemigrations --check --dry-run
No changes detected
$ python manage.py check
System check identified no issues (0 silenced).
$ python manage.py spectacular --file /dev/null   # exit 0
$ python -m pytest apps/forum_host packages/wagtail_forum --reuse-db -q
912 passed
```

### 2026-08-30 - Post-review correction (advisor-caught)

The review's `ReportViewSet` admin fix (above) was itself unverified and
carried a real regression risk: it replaced the working `list_display` entry
`"post"` with a new `target` property that returns a **model instance**, not
a renderable value, and the change was never actually loaded in a browser or
test before being marked repaired. Had Wagtail's index view choked on a
non-field, instance-valued `list_display` entry, the fix would have broken
the Reports listing for post reports too — the only surface that was working
before this todo touched it.

Corrected:
- Reverted `list_display` to keep `"post"` unchanged (proven-safe, untouched
  by this todo).
- Added `Report.message_summary` — a new `@property` returning a small `str`
  (sender + a 60-char body excerpt), additive alongside `post` rather than
  replacing it. Removed the model-instance `Report.target` property entirely
  — with `list_display` no longer wired to it, it was unused dead code
  outside its own definition.
- Added `test_report_snippet_list_renders_with_a_message_report_present`
  (`test_admin.py`), which hits the real `/cms/snippets/wagtail_forum/report/`
  URL with a message report AND a post report both present, asserts 200, and
  asserts the rendered page actually contains the summary text — verified
  live, not reasoned about. All 15 `test_admin.py` tests pass.
- Ran the full backend suite fresh (`pytest --create-db`, not just the forum
  subset): **1664 passed, 8 skipped, 0 failed** — supersedes the narrower
  912-test forum-only run as the completion evidence.
- Documented a latent tradeoff in `direct_messages.py`: echoing
  `spam_result.reason` verbatim in the send-rejection response is an oracle
  for `SPAM_BANNED_WORDS` under the heuristic backend (harmless today, the
  setting defaults to `[]`) — noted in a docstring for any host that
  populates the list.

### 2026-08-30 - Completed by completing-todos skill (run 2026-08-30-0011)

- Verification: all 5 acceptance criteria passed (912 backend forum tests
  green after repair, up from 903 pre-review; see command output above).
- Review: 17 unique findings (4 high, 7 medium, 6 low; 18 raw before merging
  one duplicate), all repaired — none accepted-unfixed.

## Notes

p3 — no current demand signal for this feature; todo 284's Notes were
explicit that M9 alone was the recommended shippable outcome and M10 should
stay unstarted absent a concrete need. This todo exists so the finding stays
tracked, not as a signal to prioritize it. Implemented 2026-08-30 on explicit
user request, overriding that default recommendation — see the Work Log above.
