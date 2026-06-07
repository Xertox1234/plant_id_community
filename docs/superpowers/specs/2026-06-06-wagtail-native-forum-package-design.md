# Wagtail-Native Forum Package (`wagtail-forum`) — Design

- **Date:** 2026-06-06
- **Status:** Approved (brainstorming) — ready for implementation planning
- **Scope:** Backend only — build a reusable, Wagtail-native forum package and
  wire it into the plant app, retiring django-machina. Updating the React web +
  Flutter mobile clients to the new API is **a separate, sequenced spec (Spec 2)**.
- **Author:** Brainstorming session (William + Claude)

## Background

The plant community app is, in the user's words, "mostly three other apps
working together." The forum is the weakest of the three as a portfolio piece
because it is **not actually built in Wagtail** — it is django-machina with a
thin Wagtail presentation wrapper.

Current state (verified by reading the code):

- The forum **engine is django-machina**. The real entities (Forum, Topic, Post,
  permissions, moderation, tracking) are 100% machina.
- `backend/apps/forum_integration/` is a Wagtail/DRF shim: a few `Page` types
  (`ForumIndexPage`, `ForumCategoryPage`) that *read from* machina, plus admin
  menu items, an extension model layer (`RichPost`, `PostReaction`,
  `ForumPostImage`, trust/AI metadata), and a DRF API at `/api/v1/forum/*`.
- The **blog**, by contrast, is genuinely Wagtail-first (Page + Snippet,
  StreamField, Wagtail search, Wagtail AI, headless preview).

So "make the forum part of Wagtail" means **replace the machina engine with
Wagtail-native models** so the forum gets the same first-class Wagtail powers the
blog has — and package it as a clean, reusable plugin, because there is no
popular "Wagtail-native forum" package in the ecosystem.

### Decisions locked in during brainstorming

1. **Full rebuild, Wagtail-native** — replace machina entirely.
2. **Reusable package** (`wagtail-forum`) — domain-agnostic, installable,
   open-sourceable. **No plant coupling in the core.** Portfolio story:
   "I filled a real gap in a major CMS."
3. **Greenfield** — the app has never been used; no real users or content. We
   drop machina with **no data migration**.
4. **Headless / API-first** — core is frontend-agnostic; ships an optional DRF
   API module; the app's React + Flutter clients consume it.
5. **Batteries-included but configurable core** — boards, topics, posts,
   moderation workflow, search, images, **plus** trust levels, spam detection,
   and reactions. Trust/spam are settings-driven so the package stays reusable.
6. **DRF API module** (not Wagtail API v2 — API v2 is page-centric and won't
   expose snippet topics/posts without pushing the model toward page-tree bloat).
7. **Mobile-first** — Flutter is the primary platform; the API and data model are
   designed for mobile (denormalized counters, cheap list payloads, cursor
   pagination, idempotent writes, offline delta-sync, responsive renditions).

### Verified against Wagtail stable docs (Context7)

The load-bearing claims were confirmed against the Wagtail stable documentation:

- **Workflow on snippets** — `WorkflowMixin` "can be added to any non-page Django
  model"; requires `RevisionMixin` + `DraftStateMixin`, recommends `LockableMixin`.
- **Search on snippets** — `index.Indexed` + `search_fields` indexes them.
- **Preview on snippets** — `PreviewableMixin` works, but it is **server-side
  template preview**; headless preview of *snippets* is not a first-class path.
  Therefore post preview is **deferred from v1** (it would need a server-side
  template the headless package otherwise has no use for); `PreviewableMixin` is
  a trivial future add. It is intentionally absent from the v1 model mixin list.

## Goal

A reusable, Wagtail-native community forum package where:

1. Moderation **is a Wagtail Workflow** (not bespoke machina moderation).
2. Topics and posts are **revisioned, lockable, searchable snippets**.
3. Forum content is unified into **Wagtail search**.
4. It is **consumed headlessly** by React + Flutter via a DRF API.
5. The core has **zero domain coupling** and is installable into any Wagtail site.

## Non-Goals / Out of Scope

- **Updating the React + Flutter clients** to the new API — that is **Spec 2**,
  sequenced after this one. Named here so it is not silently folded in.
- **Data migration from machina** — greenfield; nothing to preserve.
- **Per-board moderator scoping** — v1 ships a single global moderator group
  (see Moderation). Per-board scoping is a documented extension point for later.
- **Post preview** — not built in v1 (neither headless nor an admin template).
  `PreviewableMixin` is a trivial future add when a template is warranted.
- **Swappable models** — a classic reusable-package time-sink; explicitly avoided.
- **WebSockets / real-time** — v1 is polling/delta-sync friendly, not live.

## Architecture

### Modeling decision (the core fork)

**Approach A — Board = Page, Topic + Post = feature-rich Snippets.** Chosen over
(B) everything-as-snippets, which throws away the page-tree story, and (C)
Topic-as-Page, which bloats the page tree with user-generated content — the exact
anti-pattern Wagtail snippets exist to avoid. Headless consumption removes
Approach C's only real advantage (URL routing), since clients route by ID/slug.

```text
ForumIndex(Page)        # optional root; lets the host place the forum in its page tree
 └─ ForumBoard(Page)    # a board/category — low-volume, structural
```

```python
Topic(WorkflowMixin, DraftStateMixin, LockableMixin, RevisionMixin, index.Indexed)
    board        = FK ForumBoard
    title, slug
    author       = FK settings.AUTH_USER_MODEL
    is_pinned, is_locked, is_closed
    # denormalized for mobile-cheap list rendering:
    reply_count, view_count, last_post_at, last_post_author
    _revisions       = GenericRelation("wagtailcore.Revision")
    workflow_states  = GenericRelation("wagtailcore.WorkflowState", ...)

Post(WorkflowMixin, DraftStateMixin, LockableMixin, RevisionMixin, index.Indexed)
    topic            = FK Topic
    author           = FK settings.AUTH_USER_MODEL
    body             = StreamField(forum-safe blocks)   # no raw HTML
    is_opening_post  = bool   # the topic's first post lives here — uniform editing/moderation
    reaction_counts  = denormalized per-type counts
    created_at, updated_at, edited
    _revisions, workflow_states = GenericRelations (as above)

ForumProfile  one-to-one settings.AUTH_USER_MODEL
    # member-editable (via API):
    display_name, avatar (FK wagtailimages.Image), bio, signature
    # system-computed (read-only):
    trust_level (0–4, Discourse-style), post_count, flags_received, joined_at, last_seen

Reaction      FK Post · FK User · reaction_type · unique(post, user, reaction_type)
              → updates Post.reaction_counts

Attachments   inline images via Wagtail Images (StreamField image block → renditions);
              file attachments via a model FK Post
```

**Key modeling choices:**

- **The opening post is a `Post`** (`is_opening_post=True`), not body-on-Topic.
  One uniform object for editing, revisions, and moderation — simpler API and
  mobile composer.
- **Denormalized counters everywhere** (`reply_count`, `reaction_counts`,
  `last_post_*`) so mobile list screens render in 1–2 queries (proven by
  `assertNumQueries`). Small write-time bookkeeping cost, accepted.
- **`updated_at` on every entity** for cheap offline delta-sync.
- **Inline images → Wagtail renditions** for bandwidth-appropriate mobile variants.
- **`ForumProfile` owns member-facing fields** so the package does not depend on
  the host user model having `avatar`/`bio` (reusability). Optional
  `WAGTAILFORUM_PROFILE_SOURCE` resolver lets a host source avatar/display_name
  from its own user model to avoid duplication; default is self-contained.

### Package layout & reusability

Ships as a standalone, installable package (own `pyproject.toml`) so the
"reusable Wagtail forum package" claim is literally true and it can be split to
its own repo later.

```text
backend/packages/wagtail_forum/
  pyproject.toml                # wagtail>=7; djangorestframework as an extra
  README.md
  wagtail_forum/
    models/  boards.py  topics.py  posts.py  profiles.py  reactions.py
    blocks.py              # forum-safe StreamField block set (no raw HTML)
    workflow.py            # trust-based auto-routing into the Wagtail workflow
    spam/  base.py heuristic.py    # pluggable spam backend (default heuristic)
    wagtail_hooks.py       # SnippetViewSets + register_snippet + admin menu
    search.py              # index config
    signals.py             # emits forum events for the host (e.g. FCM push)
    api/  serializers.py views.py urls.py pagination.py throttling.py   # OPTIONAL DRF module
    conf.py                # WAGTAILFORUM_* settings resolution
    migrations/
```

**Reusability discipline:**

- **No plant imports anywhere in core.** Zero coupling. A package test suite runs
  against a minimal settings module with no plant apps to prove it.
- **No swappable models.** Concrete models; `settings.AUTH_USER_MODEL` everywhere.
- **Batteries are configurable, not hard-wired** — trust thresholds, spam backend,
  and moderation policy are `WAGTAILFORUM_*` settings.
- **Host owns auth** — the DRF module uses Django/DRF's configured auth classes;
  it does not hardcode the app's JWT/Firebase.
- **Notifications via signals** — the package emits `topic_created`,
  `reply_added`, `moderation_decided`; the host subscribes and fires FCM push.

## Moderation — a native Wagtail Workflow (portfolio centerpiece)

Moderation **is a Wagtail Workflow** running on the Topic/Post snippets, not
machina moderation.

- Posts are created as **drafts** (`DraftStateMixin`) and submitted to a Workflow.
- The workflow chains **Tasks**:
  - **`SpamCheckTask`** — custom `wagtail.models.Task` subclass running the
    configurable spam backend; auto-approves / auto-rejects / escalates.
  - **`GroupApprovalTask`** — Wagtail built-in; human moderator approval for
    escalated or new-user content.
- **Trust-based auto-routing** (`workflow.py`) — the custom glue, since Wagtail
  expects a *deliberate* "submit for moderation":
  - **Trust 0–1 (new):** → `SpamCheckTask` → suspicious? → human
    `GroupApprovalTask`; else publish.
  - **Trust 2+ (established):** skip workflow, publish immediately.
- On approval → publish the revision → post goes live, counters update,
  `moderation_decided` + `reply_added` signals fire.
- **`RevisionMixin`** = full edit-history audit per post.
  **`LockableMixin`** = mods lock a heated topic; API rejects new posts on it.

**Permission scoping (honest call):** because topics/posts are snippets, not
pages, there is **no page-tree permission cascade** — Board-as-Page does *not*
grant per-board moderator rights. **v1 ships a single global moderator group**
(simple, correct), with a documented extension point for per-board scoping later.

**Spam + trust are pluggable:** default `HeuristicSpamBackend` (link count,
new-account velocity, repeated content, banned words); swap via
`WAGTAILFORUM_SPAM_BACKEND`. Trust-promotion thresholds are settings-driven.

### Design rationale: why every `Post` (incl. replies) carries the workflow mixins

A reasonable concern is that putting `WorkflowMixin`/`DraftStateMixin`/
`RevisionMixin` on *every* post — not just opening posts — adds overhead to
simple replies. It was considered and accepted, for four reasons:

1. **The workflow does not run on every reply.** The expensive part (task
   execution, approval queue, moderator notification) is conditionally invoked by
   the trust router in `workflow.py`. Trust 2+ replies **skip the workflow** and
   publish immediately; only new/untrusted posts pay for it.
2. **Draft state on replies is feature-required, not gratuitous.** A *new user's
   reply* must be representable as "awaiting approval," which needs
   `DraftStateMixin` on replies. The verified dependency chain (`WorkflowMixin` →
   `DraftStateMixin` → `RevisionMixin`) means the stack necessarily comes along
   under the uniform-`Post` model.
3. **The cost is bounded and on the write path only.** Reads use denormalized
   counters and never join `_revisions`/`workflow_states`. Per-reply cost is ~one
   `Revision` row + a `publish()` call — and revisions double as the edit-history
   feature forums want on replies anyway. Revisions are prunable.
4. **The alternative is worse.** Splitting `Post`/`Reply` into two models to give
   replies a leaner path would break the uniform-object choice and double the
   edit/moderation/render code paths — a poor trade for a write-path
   micro-optimization.

## Mobile-first DRF API

Prefix configurable; defaults to `/api/v1/forum/`.

| Endpoint | Notes |
|---|---|
| `GET /boards/` | Board list, denormalized counts, cacheable |
| `GET /boards/{slug}/topics/` | **Cursor pagination** (infinite scroll); compact list serializer |
| `GET /topics/{id}/` | Topic detail |
| `GET /topics/{id}/posts/` | Posts, cursor pagination |
| `POST /topics/` | Create topic (with opening post) — **idempotency key** |
| `POST /topics/{id}/posts/` | Reply — **idempotency key** |
| `PATCH /posts/{id}/` | Edit → new revision |
| `DELETE /posts/{id}/` | Soft delete |
| `POST /posts/{id}/reactions/` | Toggle reaction → returns new counts (optimistic-UI ready) |
| `GET /search/?q=` | Wagtail search across topics + posts |
| `GET /sync/?since=T&board=` | **Delta-sync**: changed entities since `T` + delete tombstones |
| `GET /users/{id}/profile/` | Public profile — display_name, avatar renditions, bio, trust badge, post_count |
| `PATCH /me/profile/` | Edit member-editable profile subset only (system fields read-only) |
| `GET /me/profile/` | Current user trust level + capability map (drives mobile UI gating) |

**Mobile-first principles baked in:**

- **Cursor pagination**, not offset — stable infinite scroll as content shifts.
- **Idempotency keys on writes** (client UUID) — retry-safe over flaky networks;
  no duplicate posts.
- **Compact list serializers** separate from detail — lists carry an excerpt, not
  the full StreamField.
- **Delta-sync + `updated_at` + tombstones** — Flutter offline cache refreshes
  cheaply.
- **Capability flags in every payload** (`can_edit`, `can_reply`, `can_react`)
  plus `/me/profile/` — mobile UI gates actions per trust level without guessing.
- **Image renditions (srcset-style) in responses** — mobile picks the right size.
- **`status: pending` surfaced** — a post awaiting moderation is shown as
  "awaiting approval," not a vanished post.
- **ETag / Cache-Control** on reads; **django-ratelimit → 429** throttling
  (CLAUDE.md gotcha #4: a custom handler must return 429, not DRF's default 403).
- **Body as structured StreamField JSON** — the Flutter renderer consumes it like
  the existing blog `StreamFieldRenderer`.

## The Wagtail-feature payoff (portfolio story)

Every forum capability maps to a native Wagtail feature, not custom code:

| Forum capability | Native Wagtail feature |
|---|---|
| Moderation / approval queue | Workflow + Task (`SpamCheckTask`, `GroupApprovalTask`) |
| Post edit history / audit | `RevisionMixin` |
| Draft posts, "awaiting approval" | `DraftStateMixin` |
| Lock a heated thread | `LockableMixin` |
| Unified search (forum + blog) | `index.Indexed` + Wagtail search backend |
| Rich post bodies, no raw HTML | StreamField (forum-safe block set) |
| Responsive images / attachments | Wagtail Images → renditions |
| Boards in the site's page tree | `Page` (`ForumBoard`) |
| Admin management UI, free | `SnippetViewSet` |
| Moderator roles | Groups + permissions |
| Activity audit log | Wagtail log actions |

Headline: *"A reusable, Wagtail-native community forum where moderation is a
Wagtail Workflow, posts are revisioned/lockable snippets, and content is unified
into Wagtail search — filling a genuine gap in the ecosystem, consumed headlessly
by React and Flutter."*

## Host integration & decomposition

**Spec 1 (this spec) — backend only:**

1. Build the `wagtail_forum` package (models, admin, workflow moderation,
   spam/trust, reactions, profiles, DRF API).
2. Wire into the plant app: add to `INSTALLED_APPS`, include API URLs, register
   the moderator group, add host signal handlers (forum events → FCM push).
3. **Retire machina + the old `forum_integration` app** — remove the dependency,
   delete machina-backed models/views, drop the tables (greenfield).

**Spec 2 (separate, sequenced):** update the **React web + Flutter mobile**
clients to the redesigned API. Its own spec → plan cycle.

## Testing strategy

Per CLAUDE.md testing rules:

- **No DB mocks** — real Postgres test DB; real Wagtail workflow/revision
  machinery exercised end-to-end.
- **Strict query-count assertions** (`assertNumQueries`) on every list endpoint —
  proves the denormalized-counter mobile-perf claim and guards N+1 regressions.
- **Workflow tests** — new-user post → spam task → approval → publish;
  trusted-user post → immediate publish; locked topic rejects replies.
- **API contract tests** — cursor-pagination stability, idempotency-key dedupe
  (double POST → one post), delta-sync changes + tombstones, capability flags
  correct per trust level.
- **Reusability test** — the package suite runs against a minimal settings module
  with no plant imports, proving zero coupling (doubles as portfolio evidence).

## Open questions for implementation planning

- Exact `pyproject.toml` packaging mechanism for an in-repo editable install
  (path dependency vs. namespace package) — settle in the plan.
- Whether file attachments (non-image) are in v1 or deferred to keep scope tight.
- Trust-level promotion trigger: post-publish signal vs. periodic recompute.
