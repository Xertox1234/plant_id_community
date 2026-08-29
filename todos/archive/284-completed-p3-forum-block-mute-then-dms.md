---
status: completed
priority: p3
issue_id: "284"
tags: [forum, trust-and-safety, drf, web]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M9, M10"
---

# Forum: block/mute, then (only then) private messaging (M9, M10)

## Problem

Members have no way to stop seeing a specific other member (M9), and there is no
private messaging (M10). These are filed together because the ordering is a
safety requirement, not a preference: **direct messaging without block/mute
hands every member an unfilterable private channel to every other member.**
Promoted out of the todo 263 parking epic at the 2026-07-26 roadmap review,
which carried the same hard ordering as an acceptance criterion.

## Findings

State verified against `main` at 2026-07-26 (commit 27ade0c):

- **M9 — no block/mute.** No block/mute model, endpoint, or filter exists in
  `backend/packages/wagtail_forum/` (grep for `BlockedUser`/`block_user`/`mute`
  returns nothing). A member's only recourse against another member today is
  the report/flag path to moderators (`W/models/reports.py`) — which is a
  moderator action, not a personal filter.
- **M10 — no private messaging.** No DM model, endpoint, or UI exists.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

## Recommended Action

### Phase 1 — M9 block/mute (must land first)

1. `UserBlock` model (`blocker`, `blocked`, `created_at`) with a
   `UniqueConstraint` on the pair and a self-block guard. Follow the
   `related_name` conventions documented in `W/models/subscriptions.py:17-21`.
2. `POST`/`DELETE /users/{id}/block/` plus `GET /me/blocks/`.
3. **Apply the filter everywhere content is read**, not just the thread view —
   this is where block features usually leak: topic lists, thread posts, search
   results, mentions/@-typeahead, notifications, and the reactions surface.
   Enumerate the read paths from `W/api/views.py` and cover each.
4. Decide and record: does blocking hide the blocked user's posts entirely, or
   collapse them behind a "blocked — show anyway" affordance? Collapse is the
   safer default (it does not distort thread structure).
5. Moderators must still see everything — the filter is a viewer-side
   preference, never a moderation mechanism.

### Phase 2 — M10 private messaging (gated on Phase 1 shipping)

Do not begin until block/mute is merged and deployed. When promoted, that work
needs at minimum: a conversation/message model, per-message rate limiting, the
existing spam backend applied to DM bodies
(`WAGTAILFORUM_SPAM_BACKEND` — see todo 280), block enforcement at *send* time
(a blocked sender gets a success-shaped response but no delivery, or an explicit
403 — decide and document), report-a-DM support, and a retention/tombstone
story matching the forum's existing tombstone-prune cron (todo 261).

## Technical Details

- Block filtering is a cross-cutting read-path concern. Prefer one queryset
  helper (`exclude_blocked(qs, user)`) reused by every view over per-view
  `.exclude(...)` calls, so a new endpoint cannot silently miss it.
- Query-count risk: naively filtering per-row costs an N+1. Fetch the blocker's
  block-id set once per request (cacheable) and filter against it, mirroring the
  batched approach used for reactions/read-state.
- Package purity: no `apps.*` imports (`test_reusability.py`).
- Patterns: `backend/docs/patterns/domain/forum.md` (trust levels, moderation),
  `backend/docs/patterns/architecture/rate-limiting.md` (DM send limits),
  `backend/docs/patterns/performance/query-optimization.md`.

## Acceptance Criteria

- [x] **Hard gate — no private-messaging code may merge until block/mute is
      merged.** A DM PR that touches this repo before `UserBlock` exists on
      `main` must be closed or held, and this box may only be checked by
      recording the block/mute merge commit here — backend PR #577, merge
      commit `0abc21425399ffd069972f4c8c52bd5a44ea4d78`; web UI PR #578
      followed. M10 promoted to todo 319, still unstarted.
- [x] Blocking a user hides/collapses their content on every read path —
      one test per path: topic list, thread detail, search, mentions typeahead,
      notifications — see the per-surface table in the Work Log; also covers
      experts rail and public profile beyond the AC's original list
- [x] A moderator's view is unaffected by another user's blocks — test
      (`test_block_filtering_moderator_bypass.py`, one test per HIDE surface);
      made uniformly inert everywhere, not just where the AC requires it — see
      Work Log for the N+1/inversion bug this caught and the fix
- [x] Self-block is rejected — test (DB-level `CheckConstraint` +
      `UserBlock.can_block()` guard, both tested)
- [x] Block filtering adds no per-row query — exact `assertNumQueries` test on
      the thread-detail and topic-list endpoints (and post-list, search,
      notifications) — see Work Log for the one-time (not per-row) `has_perm`
      cache-warm cost this surfaced and how each pin documents it
- [x] Hide-vs-collapse decision recorded in the Work Log
- [x] `manage.py spectacular` passes; `pytest` forum suite green (875 backend
      tests, 0 regressions)

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Both findings re-verified absent on `main` @ 27ade0c.
- Kept as ONE todo rather than two so the ordering is structural: M10 cannot be
  picked up as an independent unit of work without reading M9's gate. Todo 263's
  AC2 ("M9 lands before or with M10 if DMs are ever promoted") is carried
  forward verbatim as this todo's first acceptance criterion.

### 2026-08-29 - M9 shipped; M10 promoted to todo 319

Backend PR #577 (merge commit `0abc21425399ffd069972f4c8c52bd5a44ea4d78`) +
web UI PR #578 (follow-up, per-slice convention), both merged. Backend-only
per the todo's literal AC, but shipped with a minimal web UI too (user
decision during planning) since a block feature with no UI can't actually be
used.

**Hide/collapse/annotate decision, per surface** (AC6):

| Surface | Decision | Reasoning |
|---|---|---|
| Topic list | HIDE | Freestanding items, no thread-structure cost |
| Topic detail | ANNOTATE only, stays reachable | A thread a viewer bookmarked/replied to before blocking the OP shouldn't 404 |
| Posts in a thread | COLLAPSE (flag only) | Removing a reply mid-thread breaks numbering/reply-count continuity; client (`PostCard`) renders a "blocked — show anyway" affordance over the real, unredacted payload |
| Search | HIDE (both topic and post hits) | Discovery surface |
| Mentions/@-typeahead | HIDE, bidirectional | Neither side should be able to @-mention the other |
| Experts rail | HIDE | Directly lists users |
| Notifications | HIDE | Read-time filtering only hides an existing bell row — see fan-out note below |
| Public profile | Flagged (`is_blocked`), still viewable; `recent_topics`/`recent_posts` skipped when blocked | Never expose whether the *target* has blocked the viewer |
| Reactions surface | No-op (considered, not missed) | `reaction_counts` is a denormalized per-type total with no usernames; `reacted` only ever reflects the viewer's own reactions. Filtering it would require live per-post recomputation — a real N+1 for a field that never leaked identity |
| `RecentTopicsView`/`SyncView` | No-op (considered) | Neither payload carries an author field — a blocked user's topic *title* could still surface, never their identity |

**Moderator bypass**: made uniformly inert everywhere (not a duty-vs-personal-
preference split) — a moderator's OWN blocks never affect what they see,
stronger than the AC's "another user's blocks don't affect a moderator." One
consolidated test file (`test_block_filtering_moderator_bypass.py`) covers
every HIDE surface.

**Notification fan-out**: read-time filtering alone only hides an *existing*
bell row — it doesn't stop a blocked user's mention/reply from pushing/
emailing in the first place. Added `_drop_blocked_pairs` in
`apps/forum_host/notifications.py`, applied to `reply_added`'s
`mentioned`/`reply_recipients` and `topic_created`'s `mentioned`.
Deliberately NOT applied to `answer_accepted`/`moderation_decided` — both
notify the recipient about their *own* content's outcome, never a blocked
stranger's activity.

**Three bugs an advisor pass caught before merge** (worth recording — none
showed up in the first 871-test-green backend run or the first 957-test-green
web run; all three were data/query-shape correctness issues invisible to
happy-path tests whose fixtures didn't match the real contract):

1. `_annotate_author_blocked` originally SKIPPED annotating for moderators
   (relying on the caller's early-out). This caused a genuine per-post N+1
   for a moderator reading a page of posts (the serializer's fallback did a
   `.exists()` query per row) AND returned `True` for the moderator's OWN
   blocks — inverting the uniform-inert guarantee above. Fixed to always
   annotate (constant `False` when not filtering); regression-pinned in
   `test_post_list_moderator_own_blocks_add_no_per_post_queries`.
2. Three host-side (`apps/forum_host/`) read paths bypass the package's
   `SearchView`/`TopicListView` filtering entirely — the exact failure mode
   `docs/rules/forum.md` warns about by name (citing H14's prior miss).
   `find_similar_topics` (shared by the premium semantic-search section AND
   the compose-time similar-topics endpoint) now takes an opt-in `user=`
   param; **`semantic_search.py` passes it** (response is always
   `private, no-store` for the caller, never cross-user cached), while
   **`similar.py` deliberately does not** (its serialized-results cache is
   shared cross-user, keyed on `(query, board_slug)` alone — passing `user=`
   there would leak one user's blocklist into another user's cached
   response). **`summary.py`'s AI thread-summary cache is left unfiltered**,
   recorded as a considered no-op: its `AICacheService` cache is
   content-hash-keyed and shared across every reader by design (the entire
   point of the cache — one LLM call serving every subsequent viewer);
   per-viewer filtering would fragment that cost-governed cache into one
   entry per distinct block combination touching a thread — a real spend
   regression, not a free filter — and a summary is an LLM paraphrase, not
   the blocked author's verbatim text.
3. `UserProfilePage`'s block toggle originally only flipped `is_blocked`
   locally and left the pre-block `recent_topics`/`recent_posts` in state —
   but `PublicProfileView` skips those queries entirely and returns `[]`
   once blocked, so the shipped copy ("their recent activity is still shown
   below") was actively false the moment a real block happened, and
   unblocking couldn't restore real data the client never received while
   blocked. Every web test's `mockProfile` fixture carried non-empty
   activity regardless of `is_blocked`, so nothing caught it. Fixed by
   refetching the whole profile on block/unblock success (optimistic flag
   flip only, no optimistic list mutation) and rewriting the copy to say
   "hidden" rather than "shown below"; both directions are now
   regression-tested against the real `[]`-on-block, real-data-on-unblock
   server shape.

**Query-count pins**: `_should_filter_blocks`'s `has_perm()` gate costs a
one-time (not per-row) 2-query cache-warm on the first request-scoped call
to `has_perm`, per Django's permission-cache mechanics — confirmed via
direct probes, not assumed. Five existing pins moved by exactly this amount;
each carries an explanatory comment.

**M10**: promoted to its own todo (319) now that M9's gate is satisfied.
Deliberately still unstarted — no model, route, or UI scaffolding anywhere.

## Notes

p3 — but note the asymmetry: M9 alone is a genuine trust-and-safety improvement
worth doing on its own merits, while M10 is a large surface-area addition
(moderation, spam, retention, abuse reporting) that this project has no current
demand signal for. The recommended outcome is **ship M9, leave M10 unstarted**.
