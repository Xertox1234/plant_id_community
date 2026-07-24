---
status: completed
priority: p2
issue_id: "257"
tags: [forum, profiles, product-ux, api]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H7, H26, M23, M41, L1, L5, L14"
---

# Forum epic: identity & public profiles

## Problem

Forum users have no public identity: no profile endpoint or page, the post
author serializer never joins ForumProfile (trust_level hardcoded None; the
avatar field can't even be set), the API ships two incompatible author shapes,
and reaction state is invisible. Profile fields are write-only vanity. p2 epic
from the 2026-07-11 forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

- **H7** — No public user identity: no profile endpoint/page;
  `PostAuthorSerializer` never joins ForumProfile (display_name from
  `get_full_name()`, `trust_level` hardcoded None); `avatar` exists on the model
  but is absent from MeProfileSerializer so it can't be set
  (`W/api/serializers.py:212-222,341-350`, `W/models/profiles.py:22-28`).
- **H26** — `author` is a bare username string on Topic resources but a rich
  object on Post resources (`last_post_author` string-only too) — two
  incompatible shapes for one concept; merges naturally with H7
  (`W/api/serializers.py:74-77,96-99` vs `:226,251-259`).
- **M23** — Reaction "reacted" state discarded: backend returns
  `ReactionToggleResult.reacted`, web `handleReact` drops it, the `Post` type
  can't hold it, buttons have no pressed state or `aria-pressed`
  (`web/types/forum.ts:239`, `web/pages/forum/ThreadDetailPage.tsx:180-194`).
- **M41** — Deleted-author representation inconsistent: `null` on topics vs a
  `{"username":"[deleted]"}` sentinel on posts (`W/api/serializers.py:74` vs `:252-258`).
- **L1** — Reaction counts invisible to logged-out readers (row renders only
  when `onReact` is passed) — social proof lost (`web/components/forum/PostCard.tsx:133`).
- **L5** — No badges/gamification; trust levels exist as machinery but are
  invisible (with H7), so no progression incentive (`W/models/profiles.py:6-11`).
- **L14** — Identity polish cluster: `trust_level` renders as raw unstyled text,
  decorative emoji not `aria-hidden`, reactions row missing `flex-wrap`
  (`PostCard.tsx:71-75,134`).

## Recommended Action

1. **Unify the author contract** (H26 + M41): one AuthorSerializer shape
   everywhere (username, display_name, avatar, trust_level via
   `select_related`/`prefetch` on ForumProfile), one deleted-author convention.
   API-breaking for topic payloads — coordinate web mapper changes in the same
   PR and update the exact query pins.
2. **H7 identity**: add `avatar` to MeProfileSerializer; public profile
   endpoint `/forum/users/{username}/` (profile + recent topics/posts);
   web profile page; author names/avatars on PostCard link to it.
3. **M23 reacted state**: carry `reacted` per reaction type into the list
   payload + `Post` type, render pressed state with `aria-pressed`.
4. **L1**: render reaction counts read-only for anonymous readers.
5. **L5**: style trust level as a badge with community-appropriate naming;
   defer full badge/achievement machinery unless cheap.
6. **L14 polish** rides along with the PostCard work.

## Technical Details

- Profile join must not regress the pinned list query counts — extend the
  existing `select_related("author")` to `author__forum_profile` (OneToOne) so
  the pins stay flat; update pin comments per the tests' contract.
- `ForumProfile.for_user()` get-or-creates — the public endpoint must not
  create profiles for arbitrary usernames (read via `select_related`, 404 on
  missing user).
- M23's backend payload addition: per-type `reacted` map on the post
  serializer for authenticated requests (mirror `reaction_counts`).

## Acceptance Criteria

- [x] One author object shape across topic list/detail and post payloads; one
      deleted-author convention; web mappers drop the `as unknown as ForumAuthor`
      casts for author identity (overlaps todo 258 M28 — whichever lands first)
      (slice A, 2026-07-24: `serialize_forum_author` everywhere incl. notif actor;
      `[deleted]` sentinel OBJECT; `mapAuthor` cast-free)
- [x] Avatar settable via `/me/profile` and rendered on posts (slice A: IDOR-scoped
      `avatar_id` write + absolute-URL read; `<img>` on PostCard)
- [x] Clicking an author opens a public profile page (profile + recent activity)
      (slice B: `GET /forum/users/{username}/` read-only endpoint + `UserProfilePage`;
      author name links on PostCard + thread header)
- [x] Reacted state visible with `aria-pressed`; reaction counts visible
      logged-out (slice C: M23 per-type `reacted` map on the post payload +
      `aria-pressed`; L1 anon counts already shipped in Wave 1 #473, test-proven)
- [x] Trust level renders as a styled badge (slice C: the styled trust pill from
      wave 2 #474 satisfies the badge AC; L5's fuller gamification machinery is
      explicitly DEFERRED per the finding's own "defer unless cheap" guidance)
- [x] List query pins unchanged or new counts explained in-comment (slice A: pins
      flat via select_related avatar JOINs; slice C: authed post-list 3→4/6 and
      edit-delete 70→71 all explained in-comment with the batched-map rationale)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 7 open findings per the manifest's Phase 4 grouping table.

### 2026-07-24 - Started by completing-todos skill (run 2026-07-24-1314)

- Reconciled vs current `main`: nothing re-homed (all 7 findings still point
  here). Wave 2 slice 1 (#474) already gave `PostAuthorSerializer` real
  `trust_level` + `display_name` (part of H7) and the web trust_level→label
  render (part of L14). Residual: everything else — Topic authors are still bare
  username strings (H26), no `avatar` in `MeProfileSerializer`/`PostAuthorSerializer`,
  no public profile endpoint/page, reacted-state/anon-counts/badge/polish pending.
- **258 overlap**: H26 unification collides with 258's M28 ("whichever lands
  first"). 258 is pending/unstarted → **257 owns H26**; leave 258 a breadcrumb.
- **User triage**: ALL slices, full treatment (review→fix→codify→merge per slice).
  Order: **A** author-contract unification (H26+M41+avatar) → **C** PostCard UX
  cluster (M23+L1+L5+L14) → **B** public profile endpoint + page (H7 remainder).
- Slice A branch: `forum-257a-author-contract`.

### 2026-07-24 - Slice A COMPLETE (author-contract unification, H26+M41+avatar)

- Backend: one `serialize_forum_author(user, request)` helper backs every topic,
  post, AND notification-actor payload → `{username, display_name, avatar, trust_level}`;
  single `[deleted]` sentinel OBJECT (M41); `PostAuthorSerializer` deleted.
- Avatar: read = absolute URL; write = `avatar_id` (write-only), IDOR-scoped to
  caller-uploaded forum-collection images (mirrors `api/sanitize.py`); `<img>` on PostCard.
- Web: new `ForumAuthor` type unifies `Thread.author`+`Post.author`; `mapAuthor` drops
  the `as unknown as` casts; `NotificationActor` gains avatar.
- **Decisions (advisor-vetted, review PASS 0 findings):**
  1. Notification actor folded into the unified helper (its `@extend_schema_field`
     already promised avatar) — full contract consistency.
  2. Avatar = raw `.file.url` (full-size original), NOT a rendition — deliberate:
     a `get_rendition` adds a per-author SELECT that breaks the flat list pin. Inline
     body images still use renditions; avatars trade fidelity for pin-flatness.
  3. `last_post_author` → `null` (not the sentinel) for a deleted last-poster: the
     denorm can't tell "no posts" from "poster gone" without a pin-breaking query
     (AC: pins unchanged). Primary M41 target (`author`) uses the sentinel. Documented
     in `get_last_post_author`.
  4. Mobile-safe: `plant_community_mobile` forum screen uses hardcoded mock strings,
     not API author parsing (Wave 3 unstarted) — the string→object change breaks nothing.
- Verify: backend 324+2 pass (`--create-db`), `spectacular` exit 0; web `type-check`
  clean, `vitest run` 656 pass. code-review-orchestrator: PASS, 0 findings.
- Commits on branch: `2ed4b28` (impl) + `f29076f` (review-response) + `9acc12e` (codify).
- **MERGED**: PR #490 squashed to main as `e8d461d` (2026-07-24). Slice A ACs checked above.
- NEXT: slice C (PostCard UX: M23/L1/L5/L14) off fresh main → then slice B (H7 profile
  endpoint+page) → then archive todo 257. Slice C/B execution plan in scratchpad RESUME-257.md.

### 2026-07-24 - Slice C COMPLETE (PostCard UX cluster: M23/L1/L5/L14)

- Branch `forum-257c-postcard-ux` off fresh main (e8d461d).
- **Reconciliation narrowed the scope**: L1 (anon reaction counts) + L14 reactions
  `flex-wrap` shipped in Wave 1 #473 already (PostCard renders the row for anon when
  `nonZeroReactions>0`; row has `flex-wrap`); the L5 trust-badge pill shipped in wave 2
  #474. So net-new = **M23** + **L14 emoji `aria-hidden`**.
- **M23 (reacted state)**: `PostSerializer.reacted` (list of the current user's active
  reaction types, `[]` anon). Pin-safe: `PostListView.list()` builds a per-page batched
  `forum_reacted_map` in ONE query (authed-only, like `build_forum_image_map`); the
  serializer reads it → zero per-post queries. Single-post responses (edit/reply) have no
  map → ONE O(1) fallback query, deliberately (keeps the edit response's `reacted` correct
  so `handleEditSubmit`'s replace-the-post update can't clobber it — advisor-flagged).
  Web: `Post.reacted`/`BackendPost.reacted`, `mapPostToPost` maps it, `handleReact` carries
  the toggle's `reacted` (was dropped), PostCard buttons get `aria-pressed` + pressed styling.
- **L14 emoji `aria-hidden`**: reaction emoji spans marked `aria-hidden` (the aria-label/count
  conveys meaning).
- **Query pins (the M23 landmine)**: authed post-list is FLAT under N — pinned at 4 (author
  viewing own posts: 3 base + 1 batched reacted map; owner short-circuits has_perm) and 6
  (non-author: +2 has_perm cache-fill, once); edit-delete 70→71 (single-post fallback). All
  explained in-comment. Anonymous pins unchanged (reacted query is authed-only).
- Verify: backend 329 forum tests pass (`--create-db`) + `spectacular` exit 0; web
  `type-check` clean + `vitest run` 658 pass. New tests: reacted serialization (authed/anon/
  no-leak), authed multi-post batched pin, single-object fallback value, PostCard aria-pressed
  - emoji aria-hidden, ThreadDetailPage toggle flips pressed state, mapper reacted default.
- NEXT: review (orchestrator + advisor) → fix → codify → PR → merge; then slice B (H7).

### 2026-07-24 - Slice B COMPLETE + EPIC CLOSED (H7 public profiles) — PR #492 (64d7d30)

- Backend: `GET /forum/users/<username>/` (`PublicProfileView`, AllowAny, read-only) —
  identity via `serialize_forum_author` + bio/signature/post_count/joined_at + 10 most
  recent live topics/replies as lightweight dicts (NOT the heavy serializers). Never
  leaks fcm_token/flags_received; getattr-not-`for_user()`; 404 missing/inactive vs
  defaults for profileless; visibility-filtered; query pin=4 flat. Route mounted in BOTH
  the package urls AND `apps/forum_host/api_urls.py` (route-parity CI catch — the host
  mount was missed first pass; fixed + codified).
- Web: `UserProfilePage` (`/forum/users/:username`); author name links on PostCard +
  thread header (ThreadCard left plain — the whole card is already a `<Link>`, nested
  `<a>` is invalid); shared `utils/forumAuthor` constants; stale-flash fix.
- Review: 3 reviewers + advisor, all findings folded (route-collision was a false
  positive — board URLs are ID-prefixed; restricted-board test added). Verified: backend
  full forum suite (incl. apps/forum_host) + spectacular exit 0; web tsc + vitest green.
- Codified: `react-typescript.md` (nested-anchor + RR score-based matching), `rules/react.md`,
  `rules/forum.md` (host-route parity), `forum.md` (public read-only profile pattern).

**EPIC 257 DONE — all 3 slices merged (A #490, C #491, B #492); all 7 findings resolved
(H7, H26, M23, M41, L1, L5, L14). L5 = trust badge satisfied; fuller gamification deferred
per the finding's own guidance.**

## Notes

p2. Pairs naturally with todo 253 (@mentions need profile links) and todo 258
(author-shape change is an API-contract change — sequence the H26 unification
before or with the M28 type cleanup).
