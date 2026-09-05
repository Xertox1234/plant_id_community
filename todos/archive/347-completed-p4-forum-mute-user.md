---
status: completed
priority: p4
issue_id: "347"
tags: [forum, social, package, web]
dependencies: []
---

# Mute user — silence notifications/content without a hard block

## Problem

`UserBlock` is a hard, reciprocal-suppression block: it hides mentions,
replies, DMs, and public-profile activity in **both directions**
(`wagtail_forum/models/user_blocks.py:1-85`). There is no lighter "I just
don't want to see/hear this person" option — the Discourse "mute". Users
who don't want to escalate have no middle tool.

## Findings

- Block behavior today: DMs refuse with 403; mentions/replies suppressed;
  profile activity filtered (2026-09-04 backend catalog §4.6).
- A mute is materially different and simpler: **one-directional**, hides
  the muted user's posts/notifications for the muter only, does NOT block
  DMs... or does it? Decision point below.
- Web UI precedent exists: block/unblock controls in `PostCard.tsx:423-451`,
  `UserProfilePage.tsx:168-205`, `SettingsPage.tsx:60-132`.

## Recommended Action

1. **Package (`wagtail_forum`):** `UserMute(user, muted_user)` model,
   unique per pair, `FOR😯UM_MUTE_*` not needed — reuse block table shape.
   Add mute checks to the same centralized filters as blocks:
   `_visible_boards()`-adjacent topic/post filtering (muted author's
   content hidden from the muter), notification fan-out suppression in
   `wagtail_forum/notifications.py`, and serializer-level `is_muted` flag
   for the UI.
   - **Decision to record in Work Log:** whether mute silences DM sends for
     the muter (recommended: yes — a muted user's DMs land in a collapsed
     state or are refused softly). Discourse precedent: muted users' DMs
     still arrive; blocked users' don't. Match that unless there's a reason.
2. **API:** `POST/DELETE /users/<username>/mute/`, list on `me/blocks/`-
   style endpoint (`me/mutes/`) — mirrors `api/user_blocks.py:1-106`.
3. **Web:** mute action in the same menus as block; muted users list beside
   blocked users in Settings.
4. **Flutter:** deferred to the parity epic (341) rather than built twice.

## Technical Details

- Follow the block implementation closely — same auth, idempotency, and
  rate-limit wrapping (`apps/forum_host/api.py:28-193`,
  `DEFAULT_FORUM_RATELIMITS` in `apps/forum_host/constants.py:15-91`).
- Anything block-aware today should be enumerated and a decision recorded
  per site: search results, similar topics, experts rail, polls votes
  display, home activity feed.

## Acceptance Criteria

- [x] Package model + endpoints + tests (one-directional: the muted user
      can still see the muter; verify explicitly)
- [x] Muted authors excluded from muter's notification fan-out and content
      surfaces (test-pinned, including search)
- [x] Web UI: mute/unmute + settings list
- [x] DM behavior decision recorded and test-pinned

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  "mute-without-block").

### 2026-09-04 - Started by completing-todos skill (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Design decisions (run 2026-09-05-0408)

- **DMs: unaffected in both directions** (Discourse precedent, as the todo's
  own second paragraph recommends): a muted member's messages still arrive;
  only a block refuses DMs. Test-pinned
  (`test_a_mute_does_not_touch_direct_messages_in_either_direction`).
- **One-directional, content-only.** The muter stops seeing the muted
  member's topics (list/search), posts (collapsed with `is_muted`), profile
  activity, experts-rail entry and notifications (read-time hide AND
  fan-out suppression in `forum_host/notifications.py`). The muted member's
  view, mentions, typeahead and DMs are untouched — pinned by
  `test_a_mute_is_one_directional_the_muted_member_notices_nothing` and the
  reverse-direction fan-out test in `test_signals.py`.
- **Per-site decisions (every block-aware site enumerated):** topic list —
  HIDE; search — HIDE; experts rail — HIDE (it lists people the viewer asked
  not to see); notifications — HIDE + no fan-out; post list / topic detail —
  COLLAPSE via `is_muted`; public profile — flag + empty activity; DMs —
  unaffected; @mention typeahead — unaffected (a one-way preference must not
  change what the muted member can do, and the muter may still mention);
  polls/vote display — no per-user surface, nothing to decide; home activity
  feed (`topics/recent/`) — was NOT block-aware at all (cross-cutting review
  caught the claim); now HIDE for both mutes and blocks, no-op for anonymous
  and moderators, test-pinned. Moderators' own mutes are inert,
  mirroring blocks (`_should_filter_blocks` gates both).
- **Implementation shape:** the two existing helpers in `api/views.py`
  (`_annotate_author_blocked`, `_exclude_blocked_authors`) now carry mutes
  too (a second `Exists`/`Subquery`), so every block-aware surface became
  mute-aware in one place; `UserMute` mirrors `UserBlock` (unique pair,
  no-self check, `muted` index for the fan-out lookup). Flutter: deferred
  to todo 341 (parity epic) per the todo.

### 2026-09-05 - Verification evidence (run 2026-09-05-0408)

- AC1 model + endpoints + one-directional: `models/user_mutes.py`,
  `migrations/0029_usermute.py`, `api/user_mutes.py`, routes in the package
  `urls.py` and the host `api_urls.py` (route parity test green);
  `tests/test_user_mutes.py` (3), `tests/api/test_user_mutes_api.py` (15) —
  `test_a_mute_is_one_directional_the_muted_member_notices_nothing` checks
  the muted member's topic list, post flags, notifications and profile view
  of the muter are unchanged.
- AC2 fan-out + content surfaces incl. search:
  `test_topic_list_search_and_experts_hide_a_muted_member`,
  `test_notification_list_hides_a_muted_actor`,
  `test_post_list_flags_a_muted_author_as_muted_not_blocked_without_hiding`,
  `test_topic_detail_flags_a_muted_author`,
  `test_public_profile_flags_muted_and_empties_activity`;
  `apps/forum_host/tests/test_signals.py::test_reply_added_does_not_notify_a_subscriber_who_muted_the_replier`
  (+ the reverse-direction test proving the replier muting the subscriber
  changes nothing). Mutation check: with the muted-author exclusion and the
  fan-out drop removed, `2 failed`; restored from copies (0 `MUTANT`).
- AC3 web: `PostCard.test.tsx` +4 (mute control gate, onMute, muted
  placeholder + reveal + inline Unmute, block outranks mute),
  `ThreadDetailPage.test.tsx` +2, `UserProfilePage.test.tsx` +2 (optimistic
  + refetch + announced failure), `SettingsPage.test.tsx` +3 (Muted users
  section). tsc/eslint/prettier clean; full web suite `1091 passed (90 files)`.
- AC4 DM decision: unaffected both ways — recorded in the decisions entry,
  pinned by `test_a_mute_does_not_touch_direct_messages_in_either_direction`
  and the host `test_mute_endpoints_are_mounted_and_throttled`.
- Full backend suite: `1 failed, 2087 passed, 8 skipped` — the one failure
  was the single-post edit query pin (73 → 74: `get_is_muted`'s single-object
  `.exists()` fallback, the exact mirror of the documented 72 → 73 block
  fallback); pin updated with rationale, file re-run `78 passed` together
  with `test_polls_api.py` (which also gained the absolute multi-choice pin
  kimi-review asked for on PR #634).

### 2026-09-05 - Code review round 1 + repair (run 2026-09-05-0408)

- Reviewers: django-drf, react-typescript, cross-cutting (read-only,
  parallel) + kimi-review on the backend diff (`No findings`).
- django-drf — nothing blocking. MEDIUM ×2 repaired: the two query-pin
  tests compared mute-present vs mute-absent captures, which an N+1 inflates
  equally; rewritten as 1-post vs 10-post FLATNESS checks
  (`test_a_moderators_own_mutes_are_inert_and_the_flag_stays_flat`,
  `test_mute_flags_stay_flat_across_a_page_for_a_regular_viewer`). LOW ×2
  repaired: two docstrings named helpers that were planned, not written
  (`_annotate_author_flags`/`_exclude_hidden_authors` → the real
  `_annotate_author_blocked`/`_exclude_blocked_authors`).
- react-typescript — nothing blocking. MEDIUM ×3 repaired: PostCard's
  single `revealed` boolean let a reveal of the MUTE placeholder pre-empt a
  later BLOCK placeholder (the card survives a refetch under a stable key)
  → `revealedFor: 'block' | 'mute' | null`, block outranks mute, pinned by
  `revealing a muted post does not pre-empt the block placeholder…`;
  UserProfilePage's block and mute handlers each refetch the profile with
  independent pending flags (two in flight would race) → one shared gate
  disables both buttons while either is pending, pinned by
  `disables Block while a mute is in flight…`; `muteActionError` was not
  cleared on username change → reset alongside the block error.
- Post-repair: `test_user_mutes_api.py` `16 passed`; web touched files
  `131 passed`, full web suite `1093 passed (90 files)`, tsc/eslint/prettier
  clean. Residue sweep clean.

### 2026-09-05 - Code review round 1, cross-cutting (run 2026-09-05-0408)

- cross-cutting — nothing blocking. MEDIUM repaired: my per-site decision
  log claimed the home "Active now" feed "reuses the topic list filter" —
  it never called either helper (blocks were missing there too). Wired
  `_exclude_blocked_authors` into `RecentTopicsView` before the slice
  (`test_home_activity_feed_hides_muted_and_blocked_members_for_the_viewer_only`;
  the anonymous query pin is untouched because `_should_filter_blocks`
  short-circuits). MEDIUM repaired: `MyMutesView`'s avatar `select_related`
  pinned exactly with avatar-bearing fixtures
  (`test_my_mutes_with_avatars_adds_no_per_row_queries`, 2 queries).
- INFO, recorded for todo 253's moderation verbs: both suppression paths
  key off the actor, so a future actor-scoped moderation notice would be
  suppressible by muting/blocking that moderator — give such verbs a NULL
  actor (already NULL-safe) or exempt them explicitly, with a test.
- Final full backend suite after all repairs: `2090 passed, 8 skipped in 269.06s`.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 4 acceptance criteria passed (Flutter deferred to todo 341 per the todo); full backend suite 2090 passed, full web suite 1093 passed.
- Review: 9 findings across three reviewers + kimi (no findings), 0 blocking — all 9 repaired, including a false 'already covered' claim about the home feed that made both blocks and mutes apply there.
