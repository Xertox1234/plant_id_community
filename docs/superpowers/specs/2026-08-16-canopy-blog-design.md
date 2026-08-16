# Canopy Blog & Seed — Design Spec (PR 3)

**Date:** 2026-08-16
**Status:** Approved in brainstorm (this session); ready for implementation planning.
**Parent spec:** `docs/superpowers/specs/2026-08-13-canopy-design.md` — this pulls the
"PR 3 — Blog + seed" slice (§6 Blog row, §7 Demo content, §9 landing plan) into an
implementable sub-spec. PR 2.5's decisions supersede the parent where they conflict
(notably: the seed runs on production behind `--confirm` + the no-override real-user
guard, not `DEBUG=True` only).
**Artifact of record:** <https://claude.ai/code/artifact/4bd858c2-a531-4c28-ad75-d62e942fd3ce>
(the "Canopy" mockup's Blog section). Acceptance is the user judging the seeded blog
against it.

## 1. Goal

Build the Canopy blog surface (list page rebuild + detail page from stub) and the demo
blog seed, so the deployed site's `/blog` looks and reads like the artifact's blog
screen and the forum rail's FromTheBlogModule lights up. Backend is touched only for
the seed command; no blog API changes.

## 2. Decisions locked with the user (2026-08-16)

1. **Seed shape — one entry, blog owns its half.** New `seed_demo_blog` command in
   `apps/blog` (own catalogue module, own copy of the two-layer guard).
   `seed_demo_content` `call_command()`s it at the end, so the prod runbook stays a
   single `seed_demo_content --confirm` run; the blog seed is also independently
   runnable/testable. Re-running on already-seeded prod: forum half skips
   (topic-granular idempotency), blog half seeds.
2. **List controls — chips + pagination only.** Category filter becomes a Chip row;
   the Pagination primitive stays. The old page's search form, sort dropdown, and
   category sidebar are retired ("Read the latest" covers recency; the rail's popular
   module covers popularity).
3. Full design approved including the flagged judgment calls: honest auto-calculated
   reading times (§9), June Park authors the feature post, delete the obsolete
   `create_demo_blog_posts.py`, empty rail on the detail page.

## 3. Category catalogue (4)

`BlogCategory` rows, `get_or_create` by slug, never modified if present:

| Name | Slug |
|---|---|
| Care | `care` |
| Propagation | `propagation` |
| Pests & diseases | `pests-diseases` |
| Design | `design` |

`icon`/`color` stay blank — the frontend chips don't consume them.

## 4. Post catalogue (6)

Authors are the four expert-tier forum demo users from PR 2.5's cast (June Park —
plant pathologist, Sam Whitaker — master gardener, Iris Delgado — head moderator,
Theo Brandt — arborist). Two titles are **locked verbatim from the artifact**; the
newest post is the hero's "This month" feature. Ages follow the eyebrow's
"new posts weekly" claim (§9). Full body copy (~500–900 words each, StreamField
paragraphs + headings + an occasional quote) is authored at plan time, PR 2.5 style.

| # | Slug | Title | Category | Author | Age | Views | Cover asset |
|---|---|---|---|---|---|---|---|
| 1 | `killed-by-kindness` | Killed by kindness | Care | june_park | 3 d | 340 | `cover-kindness.webp` (new) |
| 2 | `variegation-isnt-magic` | Variegation isn't magic, it's mutation **(locked)** | Propagation | iris_delgado | 10 d | 210 | `cover-variegation.webp` (= `thumb-monstera.webp`) |
| 3 | `fiddle-leaf-adjusting` | Your fiddle leaf isn't dying, it's adjusting **(locked)** | Care | sam_whitaker | 17 d | 290 | `cover-fiddle.webp` (= `thumb-fig.webp`) |
| 4 | `spider-mites-early` | Spider mites move in before you notice | Pests & diseases | june_park | 24 d | 150 | `cover-mites.webp` (new) |
| 5 | `prune-like-you-mean-it` | Prune like you mean it | Design | theo_brandt | 31 d | 120 | `cover-pruning.webp` (new) |
| 6 | `small-space-jungle` | A jungle in forty square feet | Design | sam_whitaker | 38 d | 80 | `cover-jungle.webp` (new) |

Post #1's thesis matches the hero subcopy (overwatering — "why most houseplants are
killed by kindness"); a pathologist writing about root rot is on-brand. View counts
are varied and non-monotonic with age so the popular ranking is deterministic and
feels organic (top-5 popular = all but `small-space-jungle`).

## 5. Seed command — `seed_demo_blog`

**Files:** `apps/blog/management/commands/seed_demo_blog.py` (command),
`apps/blog/seed_content.py` (CATEGORIES + POSTS catalogue),
`apps/blog/seed_assets/` (6 committed WEBP covers).

- **Guards (same two layers as the forum seed):** DEBUG=False requires `--confirm`;
  any real (non-demo, non-superuser) account aborts unconditionally — no override
  flag, by design. Same census semantics as `seed_demo_content` (demo = demo username
  AND `@demo.houseplant-md.com` email); the plan may extract a shared helper or
  import the constants from `apps.forum_host.seed_content` — either way, one source
  of truth for the demo shape.
- **Authors:** normally exist already (forum seed runs first). For standalone runs,
  `get_or_create` the four author accounts from the same `USERS` specs with the same
  demo shape and the same per-account non-adoption check (never adopt or modify a
  real account, superuser included).
- **Author names (new requirement):** the blog API's author `display_name` is
  `User.get_full_name() or username` — the forum seed set display names only on
  `ForumProfile`, so without this the blog renders "iris_delgado". The blog seed sets
  `first_name`/`last_name` on the four author accounts, **only** on accounts that
  pass the demo-shape check.
- **Page tree:** `get_or_create` a `BlogIndexPage` (slug `blog`) under the default
  site's root page, published; posts are its children. Idempotent; an existing index
  is used as-is.
- **Idempotency:** post-granular by slug — if a `BlogPostPage` with the slug exists
  anywhere, skip it entirely (manual edits always win, matching the forum seed's
  skip-not-overwrite contract).
- **Publish + back-date:** create → `save_revision().publish()` → then a final
  timestamp pass via queryset `.update()` setting `first_published_at` and
  `last_published_at`, plus the model's own `publish_date` DateField, per the
  codified LEARNINGS 2026-08-15 lesson (back-dating must set publish fields, and
  `.update()` dodges auto-set fields).
  Blog signals are cache-invalidation only — no counter-recompute trap — but the
  invalidation means seeding order doesn't leave stale caches.
- **`reading_time`:** left unset → the API auto-calculates from real body length (§9).
- **Search index:** `seed_demo_blog` runs `update_index` (verbosity 0) itself when it
  created posts, because the forum half may have skipped and not refreshed.
- **Integration:** `seed_demo_content` calls `call_command("seed_demo_blog")` after
  its forum work, forwarding nothing — the guard re-runs cheaply and keeps the blog
  command safe standalone.
- **Retirement:** delete `apps/blog/management/commands/create_demo_blog_posts.py`
  and its tests if any — off-brand "Plant Community" copy, and it creates a
  `demo@plantcommunity.com` author that would permanently trip the real-user guard.

## 6. Seed assets (committed WEBPs, ≤120 KB each)

- `apps/blog/seed_assets/` gets 6 covers (names in §4). Two are the already-committed
  web thumbs **moved** into the backend (`thumb-monstera.webp` → `cover-variegation.webp`,
  `thumb-fig.webp` → `cover-fiddle.webp`) for exact artifact parity on the two locked
  posts; four are new Runware generations in the same moody-botanical style
  (controller-executed task, like PR 2.5's Task 1).
- The `web/public/illustrations/thumb-*.webp` copies are deleted afterward — real
  cards render `featured_image` renditions from the API. `hero-blog.webp` stays (it
  is static UI art for the list hero).
- Images are created through Wagtail's image model (title `Seed: <asset>`, reuse by
  title like the forum seed). Prod media is persistent + served since PR #539, so no
  new infra.

## 7. Frontend — list page rebuild (`BlogListPage`)

- **HeroCard** (reference-style hero, parent spec §2): eyebrow
  `The blog · new posts weekly`, display headline **"Do less to your plants."**,
  subcopy `Guides, experiments, and honest failures from the community garden. This
  month: why most houseplants are killed by kindness.`, art
  `/illustrations/hero-blog.webp` (gentle float, reduced-motion gated).
  - Primary CTA **"Read the latest"** → newest post's detail page, resolved by a
    dedicated `fetchBlogPosts({ page: 1, limit: 1, order: 'latest' })` on mount
    (independent of the active filter); while unresolved or on failure it falls back
    to scrolling to the grid.
  - Ghost CTA **"All topics →"** clears the category filter and scrolls to the grid
    (no separate topics page).
- **Chip row:** `All` + the categories from `fetchCategories()`; selected chip drives
  the existing `?category=` param plumbing.
- **Card grid:** 2 columns (1 below ~md). `BlogCard` rebuilt on the `Card` primitive:
  cover rendition, category Chip, title, meta `N min read · Author` (Geist Mono meta,
  Bricolage title). Compact variant kept for rail use.
- **Pagination** primitive kept; search form, sort dropdown, category sidebar removed.
- **Rail:** one `RailModule` — popular posts (top 5, compact BlogCard rows) via the
  existing `fetchPopularPosts`.
- Loading / error / empty states restyled on Canopy patterns (no emoji chrome).

## 8. Frontend — detail page (new build, `BlogDetailPage`)

- Fetch via existing `fetchBlogPost(slug)`; unknown slug → the NotFoundPage
  treatment; `PageMeta` for title + meta description (from `introduction`).
- Composition, top to bottom: category Chip + publish date eyebrow → display headline
  (Bricolage) → author line (`Author name · N min read`) → full-width cover image
  (Card treatment) → article body → "More from the blog" strip rendered from the
  detail response's server-computed `related_posts` (up to 3; strip hidden when
  empty). The deprecated always-empty `fetchRelatedPosts()` stub is not used.
- **Body:** `StreamFieldRenderer` with a Canopy typography pass — ~65–70ch measure,
  Bricolage headings, tokens-only restyle of quote / code / plant_spotlight /
  call_to_action blocks. No new block support needed (renderer already covers all 7
  types with an unsupported-block fallback).
- **Rail deliberately empty** on detail — the content column widens for reading
  (RailSlot unused; empty-rail hide rule from PR 1 does the layout work).

## 9. Honesty ledger — deviations & choices

- **Reading time is true, not mocked:** `reading_time` auto-calculates (~200 wpm)
  from the actually-authored bodies, so cards may say 3–5 min where the mockup's
  placeholders said 7/5 min. Approved deviation; the meta line must never claim a
  length the copy doesn't have.
- **Weekly cadence is true:** back-dated `publish_date`s are ~weekly, matching the
  eyebrow's "new posts weekly".
- **"All topics →"** is a filter-clear + scroll, not a fictional topics page.
- **No comments UI** (`allow_comments` exists model-side; no frontend — out of scope).
- **Detail rail empty by choice**, not omission (reading width beats module filler).
- Motion inherits parent spec §8 (all animation gated by `prefers-reduced-motion`).

## 10. Testing & acceptance

- **Backend** (`apps/blog/tests/test_seed_demo_blog.py`): guard trips (DEBUG/
  `--confirm`, real-user census, non-adoption of a real account on a demo username);
  idempotency (second run creates 0); counts (6 posts, 4 categories, index page);
  back-dating asserts on `first_published_at`/`publish_date` (publish-fields lesson);
  name-setting only on demo-shape accounts; deterministic popular ordering from
  seeded `view_count`s. Page-creating tests: run with `--create-db` locally per the
  reuse-db root-truncation gotcha. Then the **full pytest suite**, not the blog subset.
- **Web:** Vitest for BlogCard / list / detail (assert key presence, not just
  values — DRF SkipField lesson applies to missing API keys generally); `tsc`;
  production build.
- **Visual:** Playwright screenshot sweep against a seeded scratch DB (scratch server
  gets its own `REDIS_URL` db index — rendition-cache collision gotcha), judged by
  the user against the artifact. Acceptance = user's visual judgment.
- **Post-merge:** user-supervised Railway seed session; runbook unchanged — one
  `railway ssh --service plant_id_community "python manage.py seed_demo_content --confirm"`
  (forum half skips, blog half seeds).

## 11. Out of scope

- Comments UI, blog search backend, `BlogAuthorPage` / `BlogSeries` surfaces,
  view-tracking changes.
- R2 media migration (todo 305 rides this branch as a todo file only).
- Flutter app and `wagtail_forum` fallback templates.
- Any change to blog API endpoints or serializers.

## 12. Verified plan-time facts (cite, don't re-derive)

- `User.display_name` = `get_full_name() or username` (`apps/users/models.py:251`) —
  hence the seed's name-setting requirement.
- Blog signals are cache invalidation only (`apps/blog/signals.py`) — no counter
  recompute on publish; the forum seed's `_refresh_topic_counters` trap has no blog
  analogue, but the publish-fields back-dating lesson still applies via `auto_now`.
- Popular endpoint orders by `-recent_views, -view_count, -first_published_at` and
  never excludes zero-view posts (`apps/blog/api/viewsets.py:324–405`) — seeded
  `view_count`s alone produce the ranking; no `BlogPostView` rows needed.
- `reading_time` API fallback: `self.reading_time or self.calculate_reading_time()`
  (`apps/blog/models.py:794`, ~200 wpm).
- `StreamFieldRenderer` already renders all 7 `BlogStreamBlocks` types with an
  unsupported-block fallback (`web/src/components/StreamFieldRenderer.tsx:109–249`) —
  detail-page body work is styling only.
- `fetchBlogPost(slug)` exists (`web/src/services/blogService.ts:90`); list fetch
  maps `category` → `category_slug` (`:51`).
- `BlogPostPage.author` FKs `User` with `on_delete=PROTECT` (`apps/blog/models.py:604`)
  — any future teardown deletes pages before demo users.
- Forum rail's `FromTheBlogModule` already consumes the popular endpoint — it lights
  up with zero forum-side changes once posts exist.
