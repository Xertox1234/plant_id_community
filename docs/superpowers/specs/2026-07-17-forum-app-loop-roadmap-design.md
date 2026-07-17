# Forum App-Loop Roadmap — Design

**Date:** 2026-07-17
**Status:** Approved (brainstorming session, this date)
**Context:** Product-gap assessment of the shipped `wagtail_forum` package + web client
(inventoried backend, web frontend, and open todos; live walkthrough with seeded data).
Supersedes the *sequencing* of epics 253–263 from
`docs/audits/2026-07-11-forum-modernization.md`; individual findings keep their
`source_review` traceability.

## Goal and locked decisions

The forum's purpose is an **app community**: it serves Plant ID app users
(help-identify threads, care Q&A). Three decisions lock the shape:

1. **App community over open growth or portfolio.** SEO/discovery work is demoted to
   cheap meta tags; package polish stays parked.
2. **Mobile early.** The Flutter client lands immediately after the backend primitives
   it needs, not after web reaches feature parity.
3. **Plant-ID integration is the marquee.** The identification-embed feature is pulled
   forward from the later wave (todo 263) into Wave 2.

The flagship journey everything sequences around:

> Photo in app → uncertain ID → "Ask the community" → forum topic with the
> identification embedded → someone answers → author marks it solved → asker
> gets a push notification.

## Wave 1 — Honesty & polish sprint (web)

Small fixes only; no new features. Makes existing features findable and truthful
before building on them. All in `web/` except one serializer change.

1. **Search discoverable** — forum search entry point in the header nav.
2. **Honest search results** — extend `SearchView` topic payload with `reply_count`,
   `view_count`, `last_post_at`, and board slug; frontend stops fabricating
   "0 replies • recently". Drop the decorative author/date filter inputs; keep
   query + category, wiring a `board_id` filter into `SearchView` (the models
   already declare the needed `FilterField`).
3. **Permalinks** — per-post copy-link affordance on the existing `#post-N` anchors;
   notification clicks navigate with the anchor and scroll-highlight the post
   (add `post_id` to the notification payload if absent).
4. **Mention styling** — `@username` renders as a highlighted span (becomes a link in
   Wave 4 when profiles exist).
5. **Reactions visible logged-out** — read-only non-zero counts for anonymous readers.
6. **Reaction row de-clutter** — at rest, non-zero counts as pills plus a single
   "add reaction" affordance; no four zero-count buttons per post.
7. **Draft autosave** — sessionStorage keyed by board/topic; restore on mount, clear on
   successful post.

**Acceptance:** each item verified in the running app (not just tests); search results
show real counts; a notification click lands on the specific post.

## Wave 2 — App-loop backend primitives (+ minimal web UI)

### Solved answers

- `Topic.solved_post` FK (nullable) + `solved_at`.
- `POST/DELETE /topics/{id}/solution/` with `post_id`.
- **Decision:** topic author and moderators may mark/unmark. Available on all boards in v1.
- Serializers expose `is_solved` / `solved_post_id`; topic lists show a Solved badge;
  thread view highlights the accepted post with a "mark as answer" affordance.
- Accepted-answer author gets a notification via the existing pipeline.

### Identification embed

- **Decision:** a `ForumIdentificationAttachment` model — a topic-level **snapshot**,
  not a StreamField body block and not an FK into `plant_identification` records.
  Created at compose time from an `identification_result_id`: the photo is copied into
  the forum image collection through the existing 4-layer/IDOR upload pipeline; top-3
  candidates + confidences + provider stored as JSON.
- Rationale: no FK into users' private identification history (they can purge history
  without breaking public forum content — consistent with the app's GDPR posture), and
  no schema-in-body migration pain later.
- Rendered as a card above the opening post.
- v1 is display + compose only. Writing a "confirmed species" back into the ID system
  is **out of scope**.
- Web entry point: the identify results page gets an "Ask the community" button that
  pre-fills the new-thread composer with the attachment.

### Mobile-gating API hardening (subset of todo 258)

- Idempotency for `PATCH /posts/{id}/` and image upload (audit M35/M36 — flagged
  "land before mobile writes").
- OpenAPI response-code completeness for every endpoint the mobile client consumes.
- Nothing else from 258 in this wave.

**Acceptance:** solved + embed exercised end-to-end from the web UI; idempotent
retries verified for all mobile-bound write endpoints.

## Wave 3 — Flutter forum client (todo 260)

Four slices, one PR each:

1. **Read-only client** — boards → topic list (cursor pagination, unread badges) →
   thread (posts, reactions, solved highlight, ID-attachment card).
2. **Auth + writes** — topics/replies/reactions with `Idempotency-Key`, mention
   autocomplete, image upload.
3. **Flagship flow** — camera/ID result → "Ask the community" → prefilled composer;
   solved-marking in-thread.
4. **Push deep links** — notification tap opens the thread at the right post.

Constraints and fold-ins:

- Online-first; the `/sync/` delta endpoint enables offline later (**not v1**).
- The prod Celery topology check and `prune_forum_tombstones` scheduling (todo 261
  items) fold in here — push delivery E2E depends on the first, traffic hygiene on
  the second.
- Riverpod 3 + existing app conventions; state/API details resolved in the
  implementation plan, not here.
- **Editorial gate:** before the app announces the forum, production needs real seed
  content (currently one topic). This is content work, tracked alongside slice 4.

**Acceptance:** the full flagship journey works on a device against production.

## Wave 4 — Identity (todo 257)

- Public profile endpoint: `display_name`, avatar, bio, trust level, joined date,
  post count, recent posts.
- Avatar upload through the existing image pipeline; rendition-served thumbnails.
- `PostAuthorSerializer` returns real `trust_level` (currently hardcoded `None`) and
  avatar thumbnail.
- Web profile page replaces the "Coming Soon" stub; mobile gets a profile screen.
- Wave 1 mention highlights become links to profiles.
- **Decision:** signatures stay dead — field remains, no UI renders it.
- Badges/gamification deferred.

**Acceptance:** tapping any post author (web and mobile) opens a public profile.

## Demoted / out of scope for this roadmap

- **Todo 255 (AI + premium):** parked until there is real posting activity.
- **SEO:** reduced to meta/OG tags, done opportunistically.
- **Todo 259 (modal/a11y hardening) and 262 (package docs):** unchanged in backlog.
- **Quote-reply, tags, threading, polls, DMs, offline forum:** not in these waves.

## Todo bookkeeping

Re-scope existing todos; do not renumber:

- Solved answers move out of 256; the identification embed moves out of 263 — both
  into a new Wave 2 epic todo with `source_review` pointing at the 2026-07-11 audit.
- 258 splits: mobile-gating subset into Wave 2, remainder stays.
- 260 = Wave 3; 257 = Wave 4; 261 partially folds into Wave 3.
- Wave 1 gets its own small todo (or ships directly as a reviewed PR).

## Delivery conventions

Per-slice PRs off fresh `main`, kimi-review commit gate, bundled `/code-review` +
checklist orchestrator on substantial diffs, pattern codification at session end —
all per existing project workflow. Backend changes carry strict-assertion tests;
web carries Vitest; mobile carries widget + integration tests per platform
conventions.
