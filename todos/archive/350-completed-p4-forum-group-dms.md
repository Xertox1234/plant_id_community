---
status: completed
priority: p4
issue_id: "350"
tags: [forum, dm, package]
dependencies: ["339"]
---

# Group DMs — conversations with more than two members

## Problem

`Conversation` is a canonicalized 1:1 pair by design
(`wagtail_forum/models/messages.py:1-92`). Regional seed swaps, club
committees, and moderator→ambassador coordination all want small group
threads. Both Discourse and NodeBB treat group messages as core.

## Findings

- The 1:1 canonicalization (probably a normalized `(user_a, user_b)` pair
  with an ordering constraint) is exactly the schema that makes group
  retrofitting breaking — `wagtail_forum/models/messages.py`.
- Block semantics get harder: in a group, does one block eject the blockee,
  filter their messages for the blocker, or prevent group formation?
- Depends on 339: no UI exists even for 1:1, so group DMs have no surface
  to extend until that lands.

## Recommended Action

**Do not** retrofit groups onto the current `Conversation` row. Preferred:

1. **Package (`wagtail_forum`):** add `ConversationParticipant` M2M-through
   model on `Conversation`; keep the 1:1 path as the degenerate case and
   migrate existing pairs to two participants each. A `kind` field
   (`direct`/`group`) lets direct chats keep canonical-pair dedup while
   groups dedup only on explicit idempotency keys.
2. Group policies to decide and record: max participants (suggest ~8, via
   `get_setting`), add/remove members, who can add members (creator only?),
   block interaction (suggest: DM send blocked if ANY participant blocks or
   is blocked by the sender — conservative).
3. Spam surface widens (bulk invites) — extend `DEFAULT_FORUM_RATELIMITS`
   with a `dm_group_create` bucket.
4. UI lands after 339: group creation from the new messages screen.

## Technical Details

- Base implementation: `wagtail_forum/api/direct_messages.py:1-356`,
  `wagtail_forum/models/messages.py:1-92`.
- Notification behavior for group replies: default notify all participants
  (batched push per `send_forum_push_batch` precedent).
- Keep per-pair canonicalization tests from todo 319 passing for `direct`.

## Acceptance Criteria

- [x] Group conversations creatable via API with participant model +
      migration of existing pairs (no data loss; test-pinned)
- [x] Block policy decision recorded + enforced (test-pinned)
- [x] Rate limit on group creation
- [x] Web + Flutter group UI (after 339)

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  group DMs). P4 and dependency-gated on 339 — the voluntary defer.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow (339 merged as #640, so the dependency is satisfied).

### 2026-09-05 - Package + host implemented (run 2026-09-05-1142)

Decisions (recorded per the todo's "decide and record" list):

- **Participant model for EVERY kind.** `ConversationParticipant`
  (conversation, user, joined_at, read_at) replaces the two per-side read
  columns; migration 0036 backfills one row per side for every existing pair
  with its read marker (test winds the app back to 0035, seeds a pair, migrates
  forward — no data loss). Direct threads keep the canonical
  `(participant_a, participant_b)` pair + `between()` dedup (`kind=direct`);
  a group has no pair (`kind=group`, both null — a CHECK constraint pins the
  shape) and dedups only on the client's Idempotency-Key.
- **Cap:** `DM_GROUP_MAX_PARTICIPANTS` = 8 INCLUDING the creator (host
  setting, README row); 2–7 others at creation.
- **Membership:** creator-only add/remove; any member may leave; the creator
  cannot leave while others remain (400 "Transfer or close the group first." —
  v1 has no ownership transfer, recorded). A removed member no longer sees the
  room (404 everywhere). Direct threads have no membership surface (404).
- **Block policy (conservative, as suggested):** a group stays VISIBLE to
  everyone in it (you cannot un-see a room you are in); a member I blocked —
  either direction — has their messages filtered out of MY reads, previews and
  unread counts; a send into a room containing anyone block-paired with the
  sender is an explicit 403 ("You cannot message this group."), never a
  silent drop; creating/adding with a block pair is the same generic 400 as a
  missing or inactive user ("One of the members cannot be added." — no oracle).
- **Rate limits:** `dm_group_create` 5/h (bulk-invite surface),
  `dm_group_manage` 30/h (membership changes), send-by-id shares
  `message_send`. The list and messages views now have host wrappers for their
  POST arms; their GETs stay unrated.
- **Send by id** (`POST conversations/<id>/messages/`) works for direct and
  group; the username send stays for direct. Inbox rows gained `kind`, `title`,
  `participants`, `participant_count`, `created_by`, `can_manage` and
  `last_message.sender` (from the prefetched members — no extra query).
- **Notifications:** no push/email exists for DMs today (direct included);
  groups inherit that. Out of scope, recorded.

Evidence:

```text
$ pytest test_group_conversations.py → 13 passed (create/envelope, 4 rejection cases, cap via host setting,
  idempotency, send-by-id + 404s, block policy, membership rules, direct canonicalization, flat inbox
  query count across group sizes, migration backfill)
$ pytest test_direct_messages_api.py test_api_mounted.py test_ratelimits.py → 62 passed (+ 2 new host tests: 429 + Retry-After on dm_group_create, real-mount round trip)
$ manage.py makemigrations --check → No changes detected; manage.py spectacular --validate → clean
```

### 2026-09-05 - Review round 1 (django-drf): 7 findings — all repaired; contract gained a single-row GET

- Added during the round (both client agents had to resolve a group by walking
  the inbox): `GET conversations/<id>/` returns the inbox row, 404 like the
  messages endpoint (test incl. stranger / blocked pair / removed member).
- **MEDIUM last member leaving orphaned the room** → a memberless group is
  deleted with its messages inside the same transaction (test; mutation → fails).
- **MEDIUM the two rate-limit drift guards** (`wrapped` callback-identity pin,
  `wrappers` unsafe-handler list) did not know the four new host views → added.
- **MEDIUM the block-in-group unread test could not tell a per-message FILTER
  from a whole-row suppression** → new test with one blocked and one ordinary
  newer message asserts exactly 1 (mutation dropping the exclusion → fails).
- LOW vacuous `row == [] or …` assertion → direct assertion (a pair is listed
  as soon as `between()` ran, its participant rows are eager); the direct
  send-by-id branch reuses the computed blocked set (one query fewer);
  `between()`'s unconditional participant insert documented as the self-heal
  it is; the reverse migration deletes group rows before the NOT NULL
  reversal (documented dev-only limitation).

```text
pytest test_group_conversations.py test_ratelimits.py test_api_mounted.py test_direct_messages_api.py → 79 passed
mutation checks: last-member delete, unread filter, group send 403 → each 1 failed; restored via cp
```

### 2026-09-05 - Review round 1 (cross-cutting): 14 findings — 12 repaired, 2 already fixed by the django round

- **HIGH `transaction=True` on the migration test flushes Wagtail's seeded
  root page for every later test** → investigated and **kept** transaction
  mode: plain `django_db` cannot host `MigrationExecutor` (DDL with pending
  trigger events), and `serialized_rollback=True` — the documented remedy —
  FAILS here, because the host's post_migrate bootstrap re-creates the
  "Forum Moderators" group that the serialized snapshot then re-inserts
  (UniqueViolation at setup, seen in the full run). The full suite was run
  with the plain marker and every later Page-dependent test passed (2250);
  the reason and that evidence are in a comment on the test, and
  `docs/rules/testing.md` now carries the exception.
- **HIGH unbounded invite list** (`ListField(max_length=50)` validates every
  item first) → `_BoundedUsernameListField(_BoundedListField)` with
  `MAX_GROUP_INVITE_ITEMS = 50` checked before per-item validation (test: 51
  names → "Too many members").
- **HIGH drift guards** → done in the django round.
- **MEDIUM the messages GET paid a membership query for direct threads** →
  direct keeps the zero-query pair check; only groups hit the participant
  table; pin: direct 4 queries, group 6.
- **MEDIUM the creator avatar leg untested** → the flat-count fixture gives the
  creator an avatar. **MEDIUM `between()` inserted participants on every
  send** → gated on `created` (0036 backfilled every existing pair).
  **MEDIUM missing edge cases** → spam-flagged create (400 with the reason,
  nothing created), removed member cannot send (404) or report (404),
  `conversations/with/` never resolves a group, both CHECK-constraint arms
  raise `IntegrityError`, the badge endpoint counts a group (positive case in
  the discriminating unread test). LOW: replay keeps the Location header
  (asserted), backfill batch size is a named constant, dead `validate_title`
  removed, last-member orphan already handled.

```text
pytest test_group_conversations.py → 21 passed
pytest test_direct_messages_api.py test_ratelimits.py test_api_mounted.py test_profiles.py test_docs.py → 75 passed
```

### 2026-09-05 - Review round 1 (react-typescript 9 findings, flutter-dart 7) — repairs dispatched

Both clients were built against the contract before the single-row GET
existed and resolved a group by WALKING the inbox — a false "unavailable"
for a quiet group behind 400 busier ones (web) and a permanently disabled
Members action on a deep link (Flutter). The backend gained
`GET conversations/<id>/` during the django round; both clients now switch
to it (HIGH, both).

- **CRITICAL (web) `last_message.sender` is null once the member left** →
  type + "Former member" fallback in the inbox row; the group/direct routing
  condition split so a defensive null `other_participant` on a direct row
  no longer borrows the group branch.
- **HIGH (backend, found by the react review)** the membership/create 400s
  were raised under `usernames` / `username` field keys, which the envelope
  flattener (todo 320) prefixes into the client's `message` ("usernames: One
  of the members cannot be added.") while the client fixtures asserted the
  bare sentence → raised under `detail` like every other one-off message in
  the module; the clients render `message` verbatim.
- **MEDIUM (web)** the search min-chars/at-cap guard was untested (timers
  cancelled by keystrokes) → fake-timer test; no keyboard path into the
  suggestions → ArrowDown/Up + Enter + Escape with `aria-activedescendant`.
  **LOW (web)** Cancel restores focus to the toggle; chip remove button 44px;
  `participant_count` only decremented when a member was actually removed;
  `authorName` deduplicated.
- **MEDIUM (Flutter)** Leave had no confirmation → the Block dialog pattern;
  no narrow-viewport test for the avatar cluster row → 375-wide test.
  **LOW (Flutter)** cluster `excludeSemantics`; self/duplicate member entry
  gets an inline hint; own messages no longer flash as someone else's while
  the profile resolves; router tests for the two protected group routes.

### 2026-09-05 - Client repairs (both review rounds) — completed after the agents hit the model limit

Both client repair agents were killed mid-run by a model rate limit. The web
agent had landed the nullable `sender` type, the single-row `fetchConversation`
and the `authorName` extraction; the Flutter agent had edited nothing. I
finished the web half directly and re-dispatched the Flutter half.

Web (finished in-session):

- The inbox row's null-sender crash is fixed with a "Former member"
  attribution, and the group / direct branches are split so a defensive null
  `other_participant` renders a non-linked "Unavailable conversation" row
  instead of borrowing the group layout and link.
- The suggestion list is a real combobox: `role="listbox"` / `role="option"`,
  `aria-activedescendant`, ArrowDown/ArrowUp wrap, Enter takes the highlighted
  suggestion (typed text otherwise), Escape closes without submitting.
- The chip Remove button is a 44 px target; Cancel returns focus to the
  New group toggle; the min-length search guard is pinned by a real-clock
  wait past the debounce (fake timers deadlocked the file's other
  userEvent flows — recorded in the test).

```text
npm run type-check → exit 0; eslint + prettier clean
npx vitest run → Test Files 98 passed (98) / Tests 1296 passed (1296)
mutations: null-sender fallback, Escape handler, detail-GET URL → each 1 failed; restored via cp
full backend suite (final) → 2250 passed, 8 skipped
```

Flutter (re-dispatched after the rate-limit death, completed):

- The group thread now resolves through `fetchConversation(id)` (the by-id
  GET) with the mounted inbox row as a cache; the page-1 scan is gone. A 404
  becomes an explicit unavailable state with a re-fetching Retry and a
  disabled composer.
- Leave goes through the Block screen's `showDialog<bool>` confirmation;
  the avatar cluster's summary `Semantics` uses `excludeSemantics: true`;
  the new-group member field shows "That's you." / "Already added." instead
  of a silent no-op; group attribution is gated on the first profile
  resolve so own messages never flash on the wrong side.
- **A repair that turned out to be dead code was removed rather than kept:**
  the reviewer's suggested "cache the last-known username" made no test
  fail, because Riverpod's `asData` already retains the previous value
  across a re-fetch — the gate is the real fix. `flutter-patterns.md` was
  corrected to say so.
- The 375-wide narrow-viewport test exposed no overflow (the row already
  fits); a mutation shrinking the viewport to 140 px makes it fail, so the
  test is not vacuous.

```text
$ flutter analyze → No issues found! (ran in 5.2s)
$ dart format --set-exit-if-changed (13 files) → 0 changed
$ flutter test → 01:33 +687 ~3: All tests passed!
$ build_runner → wrote 4 outputs; forum_providers.g.dart hash line only
$ mutations (5): resolver scan, leave confirmation, attribution gate, excludeSemantics, viewport → each red; restored
```

### 2026-09-05 - Acceptance criteria flipped (evidence)

- AC1 (group conversations creatable with a participant model + migration of
  existing pairs, no data loss, test-pinned): `test_group_conversations.py`
  create/envelope tests plus `test_migration_0036_backfills_participants_with_read_markers`
  (winds the schema back to 0035, seeds a pair with a read marker, migrates
  forward, asserts both participant rows and the preserved marker).
- AC2 (block policy decision recorded + enforced, test-pinned): the decision
  is recorded in this Work Log and `backend/docs/patterns/domain/forum.md`;
  `test_block_policy_in_a_group_filters_their_messages_and_refuses_sends`
  and `test_unread_count_excludes_only_the_blocked_members_messages` pin it.
- AC3 (rate limit on group creation): `dm_group_create` 5/h with
  `test_group_create_is_throttled_with_429_and_retry_after` (429 + Retry-After
  3600) and both host drift guards extended.
- AC4 (web + Flutter group UI): web 1296 tests / Flutter 687 tests green,
  covering inbox rows, creation, membership gating, leave and send-by-id.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-1142)

- Verification: all 4 acceptance criteria passed (backend 2250, web 1296, Flutter 687).
- Review: 4 reviewers, 37 findings (1 critical, 4 high) — every actionable finding repaired in one round; two client agents were killed by a model rate limit and their work was finished directly and by re-dispatch.
- Codified: `docs/rules/{database,security,testing}.md`, `backend/docs/patterns/domain/forum.md`, `web/docs/patterns/react-typescript.md`, `plant_community_mobile/docs/patterns/flutter-patterns.md`, django reviewer checklist.
