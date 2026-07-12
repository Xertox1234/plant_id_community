---
status: pending
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

- [ ] One author object shape across topic list/detail and post payloads; one
      deleted-author convention; web mappers drop the `as unknown as ForumAuthor`
      casts for author identity (overlaps todo 258 M28 — whichever lands first)
- [ ] Avatar settable via `/me/profile` and rendered on posts
- [ ] Clicking an author opens a public profile page (profile + recent activity)
- [ ] Reacted state visible with `aria-pressed`; reaction counts visible
      logged-out
- [ ] Trust level renders as a styled badge
- [ ] List query pins unchanged or new counts explained in-comment

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 7 open findings per the manifest's Phase 4 grouping table.

## Notes

p2. Pairs naturally with todo 253 (@mentions need profile links) and todo 258
(author-shape change is an API-contract change — sequence the H26 unification
before or with the M28 type cleanup).
