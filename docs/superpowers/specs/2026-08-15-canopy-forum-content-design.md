# Canopy Forum Content & Artifact Parity — Design Spec

**Date:** 2026-08-15
**Status:** Approved in brainstorm (this session); ready for implementation planning.
**Parent spec:** `docs/superpowers/specs/2026-08-13-canopy-design.md` — this pulls the
forum half of its §7 (demo content) forward and supersedes its `DEBUG=True` seed gate
(see §5). The blog half of §7 stays in PR 3.
**Artifact of record:** <https://claude.ai/code/artifact/4bd858c2-a531-4c28-ad75-d62e942fd3ce>
(the approved Canopy mockup; source `canopy-mockup.html`). Where this spec and the
artifact disagree, this spec wins — every divergence is recorded in §9.

## 1. Goal

Make the live forum look and act like the Canopy artifact: the five boards exist with
their deliberate identities, the forum is populated with a believable demo world, the
landing page carries the artifact's hero / chips / "Your season" cards / rail modules,
and the topbar search becomes the ⌘K command palette. Features the artifact implies but
we are not wiring yet (day streak + badges, live presence) render as clearly-marked
mocks with tracked follow-up todos.

## 2. Decisions locked with the user (2026-08-15)

- **Sequencing:** PR #537 gets its 7 approved review fixes and merges first. This work
  starts clean on `main` afterwards.
- **Seed scope:** the FULL demo world (boards, topics, replies, demo users, images) goes
  to production. The app is pre-launch with zero users. The seed command is idempotent
  and requires `--confirm` when `DEBUG=False`; it is NOT DEBUG-locked (supersedes parent
  spec §7).
- **Real features now:** "Your season" per-user stats; ⌘K command palette.
- **Mocked now, wired later:** day streak + badges; "Experts online" presence dots. Both
  visible in the live UI, marked in code, each with a todo file so they are not
  forgotten.
- **Delivery:** one PR ("PR 2.5"), SDD-executed like PR 2, branch `feat/canopy-forum-content`.

## 3. Board catalogue

Seeded verbatim. Slugs are explicit (never derived at runtime). The existing
"General Discussion" board is deleted by the seed **only if it has zero topics**;
otherwise it is left untouched and reported.

| Title | Slug | Tone | Icon (lucide) | Description (verbatim) |
|---|---|---|---|---|
| Plant identification | `plant-identification` | sage | `Leaf` | Post a photo, get a name. Most plants are identified within the hour. |
| Care & problems | `care-problems` | pollen | `Droplet` | Yellow leaves, root rot, repotting panic — bring it here. |
| Pests & diseases | `pests-diseases` | bloom | `Bug` | Spot it early. Bugs, blight, and mystery spots, diagnosed together. |
| Garden design | `garden-design` | orchid | `LayoutDashboard` | Beds, borders, and balcony jungles. Show your plans and steal ideas. |
| Show & tell | `show-tell` | sage | `Camera` | New growth, first blooms, full shelfies. Brag freely. |

**Frontend board identity map** (extends `web/src/utils/forumTones.ts`, single module):
slug → `{ tone, icon, chipLabel }`. Chip labels: Identification / Care / Pests / Design /
Show & tell. Unknown slugs keep today's hash-derived tone, a default icon, and the full
board name as chip label — the map is a lookup layer, not a requirement on the data.

## 4. Demo cast

Eight demo users. Natural key: `username`. All get `set_unusable_password()` (no one can
log in as them) and an email of `<username>@demo.houseplant-md.com`. Avatars need **no
backend work**: the web's existing hash-based specimen-avatar assignment already gives
every user a committed `public/avatars/specimen-*.jpg` deterministically (simplification
vs the in-chat design, recorded in §9).

**New model field:** `ForumProfile.title` — `CharField(max_length=80, blank=True)`,
admin-set only (not member-editable via the profile API), serialized read-only wherever
`display_name`/`trust_level` already appear. This is the standard forum "user title"
concept (cf. Discourse) and is what makes the artifact's role labels real data.

| Username | Display name | Title | Trust level |
|---|---|---|---|
| `iris_delgado` | Iris Delgado | Head moderator | LEADER (4) |
| `sam_whitaker` | Sam Whitaker | Master gardener | LEADER (4) |
| `june_park` | June Park | Plant pathologist | REGULAR (3) |
| `theo_brandt` | Theo Brandt | Arborist | REGULAR (3) |
| `maya_okafor` | Maya Okafor | Balcony gardener | MEMBER (2) |
| `priya_nair` | Priya Nair | — | MEMBER (2) |
| `marcus_webb` | Marcus Webb | — | BASIC (1) |
| `lena_fischer` | Lena Fischer | — | NEW (0) |

Each gets a one-to-two-sentence bio in the seed (plan supplies copy; plain, plant-flavored,
no credentials beyond the title).

## 5. Seed command — `seed_demo_content`

Location: `backend/apps/forum_host/management/commands/seed_demo_content.py` (host app,
beside `seed_default_forum`; the demo world is host-specific content, not package
behavior). Committed image assets live under
`backend/apps/forum_host/seed_assets/` so the Railway Docker image contains them.

Behavior:

- Runs `seed_default_forum`'s guarantees first (ForumIndex exists under the site root)
  or requires them — plan decides; either way it never duplicates that logic's repairs.
- **Guard (two layers):** when `settings.DEBUG` is `False`, refuse to run unless
  `--confirm` is passed, printing what it would create. Independently of the flag,
  the command **aborts whenever any real user account exists** — a user that is not
  in the demo email namespace and not a superuser. Once the app has a single real
  member, the seed self-bricks; `--confirm` cannot override this (adversarial
  review 2026-08-15: "a sleep-deprived engineer could easily pass --confirm").
- **Idempotent by natural keys:** users by username, boards by slug, topics by slug
  within their board. Posts have no natural key, so idempotency is topic-granular: a
  topic that already exists is skipped whole — its posts, reactions, solution, and
  images are never re-touched. A re-run creates nothing new and modifies nothing; it
  reports "already seeded" per section. Skip-not-overwrite is deliberate: content
  edited by hand after seeding always wins over the catalogue; the seed is a
  bootstrap, not a sync.
- Creates content through the normal ORM paths so existing signals maintain the
  denormalized `topic_count` / `post_count` / trust recounts. **Timestamps** are then
  spread with post-hoc `queryset.update()` writes (bypassing `auto_now`/signals):
  topics aged 1–30 days, replies spaced realistically, the most recent activity minutes
  to a few hours old, and `last_post_at` re-derived to match. Offsets are fixed values
  relative to invocation time, defined in the topic catalogue (plan carries the table).
- Attaches in-post images through the same pipeline the API upload uses (Wagtail image
  in the forum collection + however posts reference images today), so the SPA renders
  them identically to user uploads. Reactions are sprinkled on showcase posts using
  existing reaction types only.
- Identification content is **snapshot data only** — invented species/confidence/provider
  values on the existing `ForumIdentificationAttachment`; nothing FKs into plant-ID
  history (`PlantIdentificationResult` has zero writers — todo-273 finding).
- All tunables (topic ages, reply spacing, counts) are named constants at the top of the
  command or in the host app's `constants.py` — no magic numbers inline.
- After the timestamp pass, the command refreshes whatever search index covers forum
  content (plan verifies which backend indexes topics/posts and whether save-time
  indexing needs a re-run once timestamps moved); a no-op is fine if search reads
  straight from the DB.

### Topic catalogue (16 topics)

Reply counts are targets (authored, real-feeling copy — no lorem, no duplicated
paragraphs). "Solved" topics get an accepted solution via the existing solutions
mechanism. "Image" topics get 1–2 seeded post images.

| # | Board | Title | Author | Replies | Notes |
|---|---|---|---|---|---|
| 1 | plant-identification | Monstera albo — is this variegation stable? | maya_okafor | 12 | image (monstera); artifact-named |
| 2 | plant-identification | Found this trailing thing at an estate sale — hoya or dischidia? | lena_fischer | 6 | solved (sam_whitaker) |
| 3 | plant-identification | ID please: fuzzy leaves, purple undersides | marcus_webb | 5 | solved (june_park) |
| 4 | plant-identification | What tree is this? Bark peels like paper | priya_nair | 7 | solved (theo_brandt); identification attachment (snapshot) |
| 5 | care-problems | Fiddle leaf dropped 3 leaves after the move | marcus_webb | 8 | image (fiddle leaf); artifact-named |
| 6 | care-problems | Yellow halo on pothos leaves — overwatering or light? | lena_fischer | 9 | solved (sam_whitaker) |
| 7 | care-problems | Repotting panic: roots circling the pot three times | maya_okafor | 6 | — |
| 8 | care-problems | My calathea folds up at noon, not night. Normal? | priya_nair | 4 | — |
| 9 | pests-diseases | What's eating my hosta leaves overnight? | maya_okafor | 10 | image (hosta damage); artifact-named |
| 10 | pests-diseases | Tiny white cotton blobs on jade stems | lena_fischer | 7 | solved (june_park); image (mealybugs) |
| 11 | pests-diseases | Brown spots with yellow rings spreading across my monstera | marcus_webb | 5 | — |
| 12 | garden-design | Balcony jungle v2 — before and after | maya_okafor | 9 | images (before + after) |
| 13 | garden-design | North-facing bed: what actually thrives? | theo_brandt | 6 | — |
| 14 | show-tell | Three years of the same pothos, one photo per year | priya_nair | 8 | image (pothos) |
| 15 | show-tell | First bloom on the orchid I rescued from the grocery store | lena_fischer | 7 | image (orchid) |
| 16 | show-tell | Bloom watch 2026: what's flowering at your place this August? | iris_delgado | 11 | **pinned**, slug `bloom-watch-2026`; the hero's CTA target |

Moderator/expert accounts (iris, sam, june, theo) appear mostly as repliers — that is
what makes the solved threads and "Experts online" read as credible.

### Seed assets (committed, Runware-generated, WEBP, ≤120KB each)

`backend/apps/forum_host/seed_assets/`: `post-monstera-albo.webp`,
`post-fiddle-leaf.webp`, `post-hosta-damage.webp`, `post-mealybugs.webp`,
`post-balcony-before.webp`, `post-balcony-after.webp`, `post-pothos-years.webp`,
`post-orchid-bloom.webp`. Style: honest phone-photo look (not glossy hero art) —
these masquerade as user uploads.

## 6. Backend API additions (wagtail_forum package)

Three small read endpoints. All carry `@extend_schema`; all follow the package's
existing error shape and versioning. New numbers (limits, windows) live in the
package's `conf.py` defaults, overridable per host convention.

### 6.1 `GET me/stats/` (auth required; 401 anonymous)

```json
{ "posts": 118, "solutions_accepted": 12, "identifications_shared": 3 }
```

- `posts`: `ForumProfile.post_count` (existing denormalized counter).
- `solutions_accepted`: count of topics whose accepted-solution post was authored by
  the requesting user (exact field per the H6/#522 solutions mechanism).
- `identifications_shared`: count of `ForumIdentificationAttachment` rows on posts
  authored by the requesting user.
- All-time counts. No season windowing (see §9 honesty notes).

### 6.2 `GET topics/recent/` (public)

Query: `?limit=` default 5, max 20. Ordered `-last_post_at`. Live/public topics only.

```json
{ "results": [ {
  "id": 42, "slug": "bloom-watch-2026", "title": "…",
  "board": { "name": "Show & tell", "slug": "show-tell" },
  "reply_count": 11, "last_post_at": "2026-08-15T14:02:00Z",
  "is_pinned": true, "thumbnail_url": null
} ] }
```

- **Dedicated slim serializer** — deliberately NOT `TopicListSerializer`, so this does
  not become a fourth "hit builder" (todo-273 finding: Topic LIST fields must update
  three builders; this endpoint opts out by owning its shape).
- `thumbnail_url`: a small Wagtail rendition of the topic's first post image, or
  `null` (frontend falls back to an icon tile). Must be N+1-safe — batched, not
  per-row queries; if the post→image linkage cannot be resolved in bounded queries,
  the plan must say how (e.g., precomputed on the topic) rather than ship a hidden N+1.

### 6.3 `GET users/experts/` (public)

Up to 4 users with `trust_level >= REGULAR`, ordered `-trust_level, -post_count`:

```json
{ "results": [ { "username": "iris_delgado", "display_name": "Iris Delgado",
  "title": "Head moderator", "trust_level": 4 } ] }
```

Client renders `title`, falling back to the trust-level label when blank. No presence
data — the online dot is a frontend mock (§9).

**Caching:** the two public endpoints (`topics/recent/`, `users/experts/`) get a short
server-side cache (60s, named constant, per `docs/patterns/architecture/caching.md`)
— they render on every forum-landing load and their data tolerates a minute of
staleness. `me/stats/` is per-user and stays uncached.

## 7. Frontend — forum landing parity (`CategoryListPage` + rail)

- **Hero (event variant):** eyebrow "Community event"; title "The bloom watch is on.";
  body verbatim from the artifact ("Every August the community tracks what's flowering,
  fruiting, and quietly failing. Post yours, get it identified, and help a neighbor's
  garden along."); primary CTA **Join the bloom watch** → the pinned topic; ghost CTA
  **Browse boards** → scrolls/focuses the board list. Detection: the recent-topics
  payload contains a pinned topic whose slug starts with `bloom-watch`; when absent,
  the page renders the current "Ask the canopy" hero unchanged (fallback, not error).
- **Board chips:** `All` + one chip per loaded board (chipLabel from the identity map).
  Selecting a chip filters the board list client-side; `All` restores. Chips are
  buttons with `aria-pressed`, min 44px tap target.
- **Board rows:** tone tile + icon from the identity map; real topic/post counts
  (existing data); description; chevron — the artifact's row anatomy on the existing
  `CategoryCard`.
- **"Your season" (authenticated only):** four `StatCard`s — Identifications, Posts,
  Solutions from `me/stats/`; **Day streak mocked** (fixed value, code comment naming
  its todo). Anonymous visitors keep the current Boards/Threads/Posts trio untouched.
- **Rail — Experts online:** real users from `users/experts/`, specimen avatar (hash),
  display name, title/trust label; the green presence dot renders unconditionally and
  is a mock (code comment naming its todo).
- **Rail — Active now:** switches from boards to topics via `topics/recent/`:
  thumbnail (or icon tile), title, "N replies · 2h" line. Links to the topic.
- **Rail — From the blog:** unchanged (its excerpt bug is fixed in the PR #537 fix
  wave).

## 8. Frontend — ⌘K command palette

`web/src/components/CommandPalette.tsx`, mounted in `AppShell`.

- **Open:** Cmd+K (mac) / Ctrl+K, or clicking the topbar search pill. The pill is
  restyled to the artifact: "Search plants, posts, people…" + a `kbd` showing ⌘K or
  Ctrl K by platform.
- **Sections:** Quick actions (Identify a plant, Start a thread, one entry per forum
  board); Topics (existing forum search API, debounced ≥250ms via `useRef` timer, top
  5, final row links to the full search page); People (existing `users/search/`
  endpoint; the section is hidden when signed out if that endpoint requires auth —
  plan verifies its permission class). Result handling carries a stale-response
  guard (request epoch or equivalent): a slow earlier query resolving after a newer
  one must be dropped, never rendered out of order — same bug class as the
  unread-badge race fixed in PR #537.
- **A11y:** `role="dialog"` + `aria-modal`, focus trapped, Escape closes, focus
  returns to the trigger, arrow-key navigation with `aria-activedescendant` or roving
  tabindex, backdrop click closes. Motion ≤200ms and gated by `prefers-reduced-motion`.
- Empty query shows quick actions only; loading and error states are explicit.

## 9. Honesty ledger — mocks, deviations, deferrals

Recorded deviations from the artifact (each deliberate):

- **Day streak card is a mock** (fixed value). Real streaks need activity tracking →
  todo "wire day streak + badges".
- **Badge-progress sublabels and progress bars are omitted** from the three real season
  cards — bars imply progress toward a badge threshold that doesn't exist yet. The
  mocked streak card may carry its bar. Bars return with the badges todo.
- **"Experts online" presence dot is a mock** — the people and titles are real; the
  "online" claim is not. `ForumProfile.last_seen` already exists; wiring it (heartbeat
  - "active in last 15 min") → todo "wire Experts-online presence".
- **`me/stats` are all-time**, not "this season" — no season windowing until there is
  a reason; card sublabels must not claim a season.
- **Demo users have unusable passwords** and a `@demo.houseplant-md.com` email
  namespace, so the demo cast is identifiable in the DB and can never authenticate.
- **Avatar simplification:** demo users rely on the web's existing hash-based specimen
  avatars instead of seeded Wagtail avatar images (visually identical, zero backend
  surface).
- Both mocks carry a code comment naming their todo file. The two todo files are
  created in this PR per repo convention (next free numbers), with `source_review`-style
  provenance pointing at this spec.

## 10. Testing & acceptance

Backend (full `pytest` run required — Topic-adjacent serializer surface is touched):

- Seed: run-twice idempotency (identical row counts + no modified timestamps),
  production guard (`DEBUG=False` without `--confirm` refuses), real-user abort
  (any non-demo, non-superuser account present → refuses even WITH `--confirm`),
  General-Discussion deletion only-if-empty AND the kept-when-nonempty path,
  solutions/pins/attachments actually created.
- Endpoints: auth/anon matrix, response shapes, `topics/recent/` query-count
  assertion (documented N, per the repo's strict-count convention), experts ordering.

Web (Vitest + Playwright):

- Component tests: palette (open/close/keyboard/sections), chips filter, season cards
  (authed real values, anon fallback, mocked streak), Experts/Active-now rail modules
  (module-level — RailSlot portals are null in jsdom).
- Updated `CategoryListPage` suite (hero variants: bloom-watch present vs absent).
- E2E: one palette smoke (open with keyboard, search, navigate) — locators scoped to
  the palette dialog; forum locators scoped to `#main-content` per docs/rules/testing.
- Two-mode screenshot sweep of the landing page compared against the artifact.

Acceptance: after merge, the seed runs on Railway (manual, with the user); the user
judges dev + prod against the artifact.

## 11. Out of scope

- Blog list/detail + blog seed (PR 3, unchanged).
- Streak/badges and presence **wiring** (their todos).
- Search backend changes; the palette consumes existing search endpoints.
- Flutter client and `wagtail_forum` fallback templates.
- Any change to PR #537's pages beyond what §7 names.
