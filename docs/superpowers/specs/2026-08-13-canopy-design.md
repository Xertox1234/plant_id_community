# Canopy — Site-Wide Design Overhaul

**Date:** 2026-08-13
**Status:** Approved direction (mockup signed off); spec pending user review
**Mockup:** <https://claude.ai/code/artifact/4bd858c2-a531-4c28-ad75-d62e942fd3ce> (private artifact, "Canopy")
**Scope:** `web/` React frontend only. Backend touched only for the demo-content seed command.

## 1. Vision

Replace the Field Notes ledger design (PR #535) and the generic pre-shell chrome with a single
modern app-shell UI across the entire web frontend, modeled structurally on the user's reference
screenshots (dark forum dashboard: sidebar + topbar + right rail + accent icon tiles) and
chromatically on the six-green "forest" palette image.

Design thesis: **liveliness comes from light, not noise.** One monochrome green world, lit by
gradients, with three warm derived accents confined to small elements (icon tiles, badges,
progress). Dark mode is the identity; light mode is derived from the same ramp.

Working name for the design language: **Canopy**.

## 2. Decisions already made (with the user)

| Decision | Choice |
|---|---|
| Direction | Reference structure site-wide; Field Notes fully replaced |
| Palette | 6-green ramp: `#051F20 #0B2B26 #163832 #235347 #8EB69B #DAF1DE`; gradients are first-class |
| Accents | Green + derived accents: Pollen `#E7B75F`, Bloom `#E88E76`, Orchid `#B7A5E0` |
| Theme modes | Dark-first + derived mint light mode |
| Shell scope | Whole frontend, blog included; blog gets reference-style hero |
| Palette switcher | Retired — one identity; `data-palette` plumbing and the 4 palettes (loam/garden/forest/heritage) are removed; density setting kept |
| Landing strategy | Foundation PR, then per-area PRs |
| Demo content | Seeded via backend command: mock blog posts + forum threads with Runware-generated images and default avatars |
| Product name | **Houseplant MD** (domain houseplant-md.com) — the UI brand everywhere; "Canopy" names only the design language |
| Logo | Cross-bearing mark in "clinic red" on green; candidates in the mockup's Brand section (recommended: Cross-leaf) |

### 2.1 Brand: Houseplant MD

- The web UI's visible name becomes **Houseplant MD** (sidebar brand block, page titles/meta,
  auth screens); tagline "The plant clinic". The repo/project name is unchanged.
- **Logo (chosen by the user): "Leaf, badged"** — the leaf outline in mint→sage gradient stroke
  on a deep-pine rounded tile, with a coral (`#DE6B5A`) circular badge bottom-right carrying a
  mint cross. The other two candidates (*Cross-leaf*, *Clinic cross*) remain in the mockup for
  reference. The mark ships as an inline SVG component plus favicon/app-icon exports.
- **Legal constraint (binding)**: the red Greek cross on white is a Geneva-Conventions-protected
  emblem, enforced against apps. The mark must never render as a red cross on a white/light
  ground; the cross uses Canopy's clinic red `#DE6B5A`/Bloom on green or mint-green grounds.
- Copy voice may lean into the clinic metaphor where it fits (Diagnose = "checkup",
  solutions = "treatment"), without turning every string into a pun.

## 3. Token architecture (`web/src/index.css`)

Rewrite of the token layer, keeping the **semantic `--gt-*` names** so existing components keep
compiling. Two layers where today there is one:

### 3.1 Raw ramp layer (new)

```css
--canopy-abyss:  #051F20;  /* page ground */
--canopy-pine:   #0B2B26;  /* app-frame canvas */
--canopy-moss:   #163832;  /* raised surfaces */
--canopy-forest: #235347;  /* interactive / borders (via color-mix) */
--canopy-sage:   #8EB69B;  /* secondary ink, soft accents */
--canopy-mint:   #DAF1DE;  /* primary ink, bright accents */
--canopy-pollen: #E7B75F;
--canopy-bloom:  #E88E76;
--canopy-orchid: #B7A5E0;
--canopy-red:    #DE6B5A;  /* error only */
```

### 3.2 Semantic layer (re-mapped, names kept)

- `surface/surface-2/surface-3` → pine/moss/forest-mix; `ink/ink-2/ink-3` → mint/sage-mix/muted-mix;
  `line/line-2` → forest color-mixes; `primary` → mint (CTA), `on-primary` → abyss.
- Legacy accent names re-pointed rather than deleted: `clay`→pollen, `berry`→bloom, `sky`→orchid,
  `leaf`→sage, so existing usages inherit sane Canopy colors before their area PR lands.
- `ok`→sage-based, `warn`→pollen-based, `error`→`--canopy-red`.
- `--wf-*` derived tokens and all `.wf-*` classes/keyframes (index.css lines ~314–591): **deleted**
  in the forum PR (the shell PR must not break the still-Field-Notes forum, so deletion waits).

### 3.3 New token groups

- **Gradient materials:** `--gt-grad-card` (moss→pine, lit top-left), `--gt-grad-sweep`
  (radial mint highlight overlay), `--gt-grad-cta` (mint→sage), `--gt-grad-ambient`
  (the canopy glow behind the shell). Every raised surface uses `grad-card` + `grad-sweep`,
  not flat fills.
- **Accent tile gradients:** per-accent light→base pairs for icon tiles and progress fills.
- Radius tokens: existing `--radius-*` kept (pill already exists).

### 3.4 Theming mechanism

- `data-mode="dark"` becomes the **default** (`:root` = dark values; `[data-mode="light"]` overrides).
  ThemeContext: remove `gt-palette` key + all palette logic; keep mode + density. Settings page
  drops palette swatches.
- The `@custom-variant dark` stays wired to `data-mode` (no `prefers-color-scheme` change).
- Light mode is **derived, not inverted**: canvas `#DAF1DE`-family, card gradients near-white
  mint, ink = pine, CTA = pine→forest gradient with mint text. Accents keep their jobs.

## 4. App shell (`web/src/layouts/`)

New `AppShell` replaces the `Header`/`Footer` top-nav chrome in `RootLayout`:

- **Sidebar** (~236px, fixed): Houseplant MD brand mark + name, primary nav — Home, Identify, Forum (unread count
  badge), Blog, My garden, Diagnose — plus footer nav (Settings, Log out / Log in). Active item
  gets the gradient-card pill treatment. Collapses to icon rail at ~1180px; hidden behind a
  hamburger drawer below ~860px (reusing the existing drawer pattern from `Header.tsx`).
- **Topbar**: global search field (visual first; wired to `/forum/search` initially), "new post"
  button, `NotificationBell` (restyled), user avatar menu (`UserMenu` restyled).
- **Right rail** (~300px): a slot (`<RailSlot>`) pages can fill; empty = wider content column.
  Forum fills it with Experts online / Active now / From the blog; blog list with popular posts.
  Hidden below ~1180px.
- **Ambient ground**: fixed-position canopy-glow gradient layer behind the frame, slow drift
  animation, disabled under `prefers-reduced-motion`.
- **Footer retired**: legal/util links move to a small sidebar footer block.
- Skip-nav link and `main#main-content` are preserved; sidebar nav is a `<nav aria-label>`;
  focus-visible states on all interactive chrome.
- **404 page** added (none exists today) — shell-wrapped, uses one generated illustration.

## 5. Primitive components (`web/src/components/ui/`)

New (all styled exclusively through tokens): `Card` (gradient surface + sweep), `Tile` (accent
icon square), `Chip` (filter pill, `on` state), `CountBadge`, `Avatar` (rounded-square, presence
dot variant), `StatCard` (tile + mono number + progress bar), `ProgressBar` (accent gradient
fills), `HeroCard` (eyebrow/headline/copy/actions/art layout used by forum + blog + home),
`RailModule` (right-rail section with icon heading). Existing `Button` gains the mint-gradient
primary and ghost variants; `Eyebrow`, `Divider`, `Pagination`, dialogs are restyled in place.
Icons remain `lucide-react`; the bespoke `ForumIcons` set is retired where lucide covers it.

Numbers/data render in Geist Mono with `tabular-nums`. Type roles unchanged: Bricolage
Grotesque 600 = display, Geist 400–600 = body/UI, Geist Mono = data/eyebrows.

## 6. Per-area treatment

| Area | Work |
|---|---|
| **Forum** | Delete `.wf-*` system; rebuild CategoryList (hero + board rows + chips + stat cards + rail), ThreadList, ThreadDetail (posts as gradient cards, solution highlight in sage, reaction pills as chips), Search, NewThread, UserProfile on the primitives |
| **Blog** | List page: HeroCard + card grid + rail. **Build `BlogDetailPage`** (currently a stub): cover image, display headline, StreamFieldRenderer with Canopy typography styles |
| **Home** | HeroCard welcome + quick actions (Identify CTA) + activity modules |
| **Plant ID / Identify** | Upload/result flow restyled on Card/Tile/Chip; results as specimen cards |
| **Garden (`MyPlantsPage`)** | Plant cards on the new Card, care states via status chips |
| **Diagnose** | `DiseaseDiagnosePage` restyled; unrouted diagnosis list/detail pages stay untouched |
| **Auth** | Login/Signup as a centered gradient Card inside the shell (no rail); Google button unchanged internals |
| **Profile / Settings** | Restyle; Settings loses palette swatches, keeps mode + density |

## 7. Demo content (backend seed)

`python manage.py seed_demo_content` (idempotent, guarded to `DEBUG=True`):

- **Blog**: ~6 Wagtail posts with Runware-generated cover images (moody botanical photo style)
  and real-feeling copy; images stored through Wagtail's image model.
- **Forum**: boards mapped to the five Canopy boards (identification / care & problems /
  pests & diseases / garden design / show & tell), ~15 topics with replies, several with
  generated in-post images; demo users assigned the existing `public/avatars/specimen-*.jpg`
  set (copied/served as user avatars) with varied trust levels; a few accepted-solution threads.
- Constraint honored: **nothing FKs into plant-ID history** — any "identification" content in
  seeds is snapshot data (per the todo-273 finding that `PlantIdentificationResult` has no writers).
- Generated assets are committed under version control (small WEBPs), so seeding is reproducible
  without a Runware key.

## 8. Motion

- Ambient: canopy-glow drift (70s alternate) behind the shell.
- Micro: hover lift + border brighten on cards/rows; chip/CTA transitions ≤200ms.
- Hero art: gentle float (7s alternate).
- One orchestrated moment kept from the shell mockup, nothing scattered; **all animation gated
  by `prefers-reduced-motion`**. Scroll-driven `animation-timeline` experiments from Field Notes
  are not carried forward.
- Optional later pass (explicitly deferred): Runware-generated video hero for the home page.

## 9. Landing plan (approved: foundation PR, then per-area PRs)

1. **PR 1 — Foundation**: this spec, token rewrite, AppShell + 404, ui primitives, ThemeContext
   palette removal, Settings cleanup. All pages render inside the shell wearing re-mapped tokens
   (old page markup, sane new colors). Forum keeps `.wf-*` temporarily.
2. **PR 2 — Forum**: full forum rebuild; delete `.wf-*` CSS + `ForumIcons` residue.
3. **PR 3 — Blog + seed**: blog list/detail build, seed command + generated assets.
4. **PR 4 — Identify + Garden + Diagnose + Home**.
5. **PR 5 — Auth + Profile/Settings + polish sweep** (dead `App.css` deleted here).

Each PR: tests green (`npm test`), visual check via Playwright screenshots, kimi-review gate,
auto-merge only after user review per repo convention.

## 10. Testing & acceptance

- Existing Vitest suites updated where markup assertions change; primitives get component tests
  (render, variant classes, a11y roles).
- Playwright smoke: shell renders on all routes; sidebar nav works; mode toggle persists;
  reduced-motion honored (no animation frames scheduled).
- Contrast: ink-on-surface pairs meet WCAG AA in both modes (sage-on-pine is secondary text
  only; accents never used for body text).
- Acceptance: user judges seeded forum + blog visually against the mockup.

## 11. Out of scope

- Flutter mobile app and `wagtail_forum` fallback templates (SPA is the real UI).
- Unrouted diagnosis pages (`DiagnosisListPage`, `DiagnosisDetailPage`) and `BlogPage.tsx` test
  fixture — untouched.
- Search backend changes (topbar search links to existing forum search).
- Video hero (deferred motion pass).
- Any renaming of the product; "Canopy" names the design language only.
