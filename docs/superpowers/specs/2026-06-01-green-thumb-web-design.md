# Green Thumb Web Migration (Phase A) — Design Spec

> **Companion to** the mobile work: `docs/superpowers/specs/2026-05-31-green-thumb-phase2-design.md` (design language) and `docs/superpowers/plans/2026-05-31-green-thumb-phase2.md` (mobile TDD plan). This spec adapts the *same* Green Thumb design system to the **React web app in `web/`**. The implementation plan it feeds lives at `docs/superpowers/plans/2026-06-01-green-thumb-web-phase-a.md`.

## Goal

Apply the Green Thumb design system to the existing `web/` React app. Replace every raw Tailwind color class (`text-gray-700`, `bg-green-600`, …) with Green Thumb **semantic tokens**, adopt the new radius/density/shadow scales and the full mobile type system, add runtime palette + density + dark-mode switching (persisted), wire a Settings UI and a dev-only all-combinations debug preview, and delete the dead legacy `@theme` tokens once nothing references them.

**This is the inverse of the mobile job.** Mobile had a centralized semantic layer (`AppColors.green600 → ext.clay` — a clean swap). The web app has **no semantic layer at all**: 1095 raw default-Tailwind color classes across 39 `.tsx` files, and the existing `@theme` custom tokens (`--color-primary` etc.) are **dead** (1 stray reference, to shades that aren't even defined). Redefining the `@theme` vars re-themes *nothing*. The real work is building a semantic token layer and migrating 1095 usages onto it.

## Scope

**Pure Phase A — re-theme and migrate what EXISTS.** The `design_reference/src/components/*.tsx` mockups are **reference-only**; building them as net-new routes would regress 4 of 7 into mock-data screens that are less capable than the existing pages (e.g. the 91-line `PlantResults` mockup vs. the 673-line `DiagnosisDetailPage`). No net-new screens, no restructuring pages to match mockups, no new wiring. Phase B is captured as a deferred follow-up note at the end.

**Modify (token system & infra):**

- `web/src/index.css` — replace dead `@theme` tokens with the Green Thumb token system + runtime override blocks + `@font-face`
- `web/index.html` — preload font woff2 (optional perf)

**Create (new):**

- `web/src/contexts/ThemeContext.tsx` — palette / density / mode state, `<html>` data-attributes, localStorage
- `web/src/components/ui/ClayButton.tsx` — primary CTA button
- `web/src/components/ui/GrainOverlay.tsx` — subtle texture (HomePage only)
- `web/src/components/ui/Eyebrow.tsx` — uppercase label component
- `web/src/pages/debug/ThemePreviewPage.tsx` — all-combos preview (`/debug/theme`)
- `web/public/fonts/*` — self-hosted Bricolage Grotesque, Geist, Geist Mono woff2
- Co-located `*.test.tsx` per new component; Playwright specs for color-resolution & visual

**Migrate (39 files using 1095 color classes):** all of `web/src/components/{ui,layout,forum,diagnosis,PlantIdentification}/`, `BlogCard`, `StreamFieldRenderer`, `ErrorBoundary`, and all of `web/src/pages/{,auth,forum,diagnosis}/` (Home, Identify, Profile, Settings, Blog×4, Forum×4, Auth×2, Diagnosis×2). Includes removing now-redundant `dark:` color variants from the 9 forum files.

**Replace (Task 1) / verify-delete (Task 13):**

- **Task 1** rewrites the `@theme` block entirely — the old palette/radius/font tokens are replaced by the Green Thumb token system. The token *names* `--color-primary` and `--color-error` are **redefined** (repointed to `var(--gt-*)`); genuinely orphaned names with no GT equivalent (`--color-primary-hover`, `--color-primary-light`, `--color-secondary`, `--color-secondary-hover`, `--color-success`, `--color-warning`, `--color-info`, and the unused `--font-xs … --font-3xl` size tokens) are dropped at that point.
- **Task 13** gates on a zero-reference grep: removes any raw `gray-/green-/red-/amber-/…` color class that slipped through (areas were migrated in Tasks 4–11) and confirms no orphaned `@theme` tokens remain.

**Out of scope:** net-new screens, backend, Flutter mobile, the `design_reference/` mockups, the `existing_implementation/` archive.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime swap mechanism | CSS custom properties overridden per `[data-palette][data-mode][data-density]` + `@theme inline` | Verified against Tailwind 4 docs: `@theme inline` makes utilities resolve the var *at the element*, so a cascade override on `<html>` wins. Plain `@theme` inlines build-time values — the override would do nothing. This is the load-bearing fact (learning J). |
| Default palette in `:root` | loam · light · cozy | Every component renders correctly with **no provider** (learning A) — Vitest, isolated rendering, a page rendered before context mounts. |
| Dark mode | Data-attribute driven (`[data-mode="dark"]`), **not** `prefers-color-scheme` | An explicit in-app toggle. `@custom-variant dark` is rekeyed to the attribute so any residual `dark:` utility aligns with the toggle. Most `dark:` color utilities are *removed* — the `--gt-*` vars flip under `[data-mode]`, so `bg-surface` is automatically correct in dark. |
| Primary CTA | `bg-clay text-on-clay rounded-pill` (`ClayButton`) | Warm terracotta, distinct from brand green; matches mobile. |
| Secondary action | `bg-primary text-on-primary rounded-pill` | Moss — the M3 primary role. |
| Radius scale | Override Tailwind defaults: xs6 / sm10 / md16 / lg22 / xl28 / pill999 | Old web scale was sm6/md8/lg12/full. Overriding the named scale re-skins every existing `rounded-md`/`rounded-lg` automatically. |
| GrainOverlay placement | **HomePage only** | The one Splash/Home-style landing that exists on web. Functional pages stay clean (mirrors mobile: Splash + Home only). |
| Typography | Full mobile type system — Bricolage Grotesque (display/headings, italic) · Geist (body/labels) · GeistMono (scientific names) | User-selected; all three are OFL-licensed and self-hostable. |
| Transitional bridge | **None** | User opted out. Migration proceeds area-by-area; each task keeps its own area shippable via TDD. |
| Debug preview | Dev-only `/debug/theme` route, all 4×3×2 = 24 combos | Visual QA for the matrix (mobile's `ThemePreviewScreen` analog). |
| Persistence | `localStorage` (`gt-palette`, `gt-density`, `gt-mode`) | Web standard; cleared/mocked between Vitest runs (learning I). |

---

## Runtime Theming Architecture

### `index.css` structure

```css
@import "tailwindcss";

/* ── (a) @font-face: self-hosted woff2 ───────────────────────────── */
@font-face { font-family:"Bricolage Grotesque"; src:url("/fonts/BricolageGrotesque-SemiBold.woff2") format("woff2"); font-weight:600; font-style:normal; font-display:swap; }
/* Bricolage has no true italic — synthesize via font-style:italic at use sites,
   OR ship the variable font and apply `font-style: italic`. Geist / Geist Mono: */
@font-face { font-family:"Geist";      src:url("/fonts/Geist-Regular.woff2")  format("woff2"); font-weight:400; font-display:swap; }
@font-face { font-family:"Geist";      src:url("/fonts/Geist-Medium.woff2")   format("woff2"); font-weight:500; font-display:swap; }
@font-face { font-family:"Geist";      src:url("/fonts/Geist-SemiBold.woff2") format("woff2"); font-weight:600; font-display:swap; }
@font-face { font-family:"Geist Mono"; src:url("/fonts/GeistMono-Regular.woff2") format("woff2"); font-weight:400; font-display:swap; }

/* ── (b) Semantic vars — :root = DEFAULT (loam · light · cozy) ────── */
:root {
  /* surfaces */     --gt-surface:#F6F0E2; --gt-surface-2:#ECE3CC; --gt-surface-3:#DDD0AE;
  /* ink */          --gt-ink:#1F1A12; --gt-ink-2:#4A3F2C; --gt-ink-3:#7C6E55;
  /* lines */        --gt-line:#D4C5A0; --gt-line-2:#BCA97E;
  /* roles */        --gt-primary:#4A7034; --gt-on-primary:#F6F0E2;
                     --gt-secondary:#97B86A; --gt-tertiary:#E0B445;
                     --gt-clay:#C9542A; --gt-on-clay:#FFF8EA;
                     --gt-leaf:#C2D680; --gt-berry:#C45577; --gt-sky:#6FA0AA;
  /* status */       --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
  /* density (cozy) */ --gt-pad-card:16px; --gt-pad-screen:16px; --gt-gap:12px;
  /* shadows (light) */
  --gt-shadow-1:0 1px 0 rgba(27,34,24,.04), 0 2px 6px rgba(27,34,24,.05);
  --gt-shadow-2:0 2px 0 rgba(27,34,24,.05), 0 8px 22px rgba(27,34,24,.08);
  --gt-shadow-3:0 4px 0 rgba(27,34,24,.06), 0 18px 40px rgba(27,34,24,.14);
}

/* ── (c) palette LIGHT (and forest, which is dark-only) blocks.
   Specificity (0,1,0), later than :root → they win. Values in tables. ─ */
[data-palette="garden"]   { --gt-surface:#F4F1E4; --gt-clay:#D86B2C; /* …light set… */ }
[data-palette="forest"]   { --gt-surface:#0F1A12; --gt-clay:#F0935A; /* forest = dark-only; this IS its only set */ }
[data-palette="heritage"] { --gt-surface:#F0EBDB; --gt-clay:#B0481E; /* …light set… */ }

/* dark COLOR blocks MUST be palette-qualified (0,2,0) so they outrank the
   palette base block. A BARE [data-mode="dark"] color block would tie on
   specificity with [data-palette="forest"] (0,1,0) and, being later, clobber
   forest with loam-dark — a cascade bug. Forest needs NO dark block (its base
   already holds dark values; nothing outranks it). ThemeContext always writes
   data-palette, so a qualified block always matches. */
[data-palette="loam"][data-mode="dark"]      { --gt-surface:#12100A; --gt-clay:#E58A52; … }
[data-palette="garden"][data-mode="dark"]    { --gt-surface:#0E140F; … }   /* _gardenDark */
[data-palette="heritage"][data-mode="dark"]  { --gt-surface:#0E140F; … }   /* heritage dark = _gardenDark */
/* forest: no dark block — light == dark */

/* dark SHADOWS are palette-INDEPENDENT → one bare [data-mode="dark"] block
   that sets ONLY shadow vars (no colors here, so no cascade conflict). */
[data-mode="dark"] {
  --gt-shadow-1:0 1px 0 rgba(0,0,0,.04), 0 2px 6px rgba(0,0,0,.05);
  --gt-shadow-2:0 2px 0 rgba(0,0,0,.05), 0 8px 22px rgba(0,0,0,.08);
  --gt-shadow-3:0 4px 0 rgba(0,0,0,.06), 0 18px 40px rgba(0,0,0,.14);
}

/* ── (d) density override blocks (padCard, padScreen, gapY) ───────── */
[data-density="comfortable"] { --gt-pad-card:18px; --gt-pad-screen:18px; --gt-gap:14px; }
/* cozy is the :root default */
[data-density="compact"]     { --gt-pad-card:12px; --gt-pad-screen:14px; --gt-gap:10px; }

/* ── (e) @theme inline: register vars → generate utilities that
   RESOLVE THE VAR AT THE ELEMENT (so cascade overrides win) ───────── */
@theme inline {
  --color-surface: var(--gt-surface);     --color-surface-2: var(--gt-surface-2);
  --color-surface-3: var(--gt-surface-3);
  --color-ink: var(--gt-ink);             --color-ink-2: var(--gt-ink-2);
  --color-ink-3: var(--gt-ink-3);
  --color-line: var(--gt-line);           --color-line-2: var(--gt-line-2);
  --color-primary: var(--gt-primary);     --color-on-primary: var(--gt-on-primary);
  --color-secondary: var(--gt-secondary); --color-tertiary: var(--gt-tertiary);
  --color-clay: var(--gt-clay);           --color-on-clay: var(--gt-on-clay);
  --color-leaf: var(--gt-leaf);           --color-berry: var(--gt-berry);
  --color-sky: var(--gt-sky);
  --color-ok: var(--gt-ok);   --color-warn: var(--gt-warn);   --color-error: var(--gt-error);
  /* density spacing MUST be inline — it changes at runtime */
  --spacing-card: var(--gt-pad-card);  --spacing-screen: var(--gt-pad-screen);  --spacing-gapy: var(--gt-gap);
  /* shadows */
  --shadow-1: var(--gt-shadow-1); --shadow-2: var(--gt-shadow-2); --shadow-3: var(--gt-shadow-3);
  /* font families */
  --font-display: "Bricolage Grotesque", serif;
  --font-sans: "Geist", system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;
}

/* ── (f) radius scale is constant across palettes → static @theme.
   Overriding the named scale re-skins existing rounded-* utilities. ─ */
@theme {
  --radius-xs:6px; --radius-sm:10px; --radius-md:16px;
  --radius-lg:22px; --radius-xl:28px; --radius-pill:999px;
}

/* ── (g) dark variant keyed to OUR toggle, not OS preference ──────── */
@custom-variant dark (&:where([data-mode="dark"], [data-mode="dark"] *));
```

> **Why `@theme inline` for colors/spacing but plain `@theme` for radius:** colors and density change at runtime via the cascade; their utilities must resolve `var(--gt-*)` at the element. Radius is identical across all 24 combos, so it can be a static value.

### Token name → utility → mobile source

| Web token (`--color-*`) | Tailwind utility | Mobile source | Role |
|---|---|---|---|
| `surface` / `surface-2` / `surface-3` | `bg-surface` … | bg / bg2 / bg3 | page / card / raised |
| `ink` / `ink-2` / `ink-3` | `text-ink` … | ink / ink2 / ink3 | primary / secondary / muted text |
| `line` / `line-2` | `border-line` … | line / line2 | border / strong border |
| `primary` / `on-primary` | `bg-primary` | moss / onMoss | brand green; secondary CTA |
| `clay` / `on-clay` | `bg-clay` | clay / onClay | **primary CTA** |
| `secondary` | `bg-secondary` | sage | M3 secondary |
| `tertiary` | `bg-tertiary` | honey | collection/honey accent |
| `leaf` | `text-leaf` | leaf | "identified" badge, lime accent |
| `berry` | `text-berry` | berry | community/social accent |
| `sky` | `text-sky` | sky | water/care accent |
| `ok` / `warn` / `error` | `text-ok` … | ok / warn / bad | status (error also uses `on-clay` as on-color) |
| `card` / `screen` / `gapy` (spacing) | `p-card`, `px-screen`, `gap-gapy` | density padCard/padScreen/gapY | density-responsive padding & gaps |
| radius `xs/sm/md/lg/xl/pill` | `rounded-md` … | rXs..rPill 6/10/16/22/28/999 | corner scale |
| `shadow-1/2/3` | `shadow-1` … | shadow1/2/3 | elevation (light+dark) |

### Full palette values (all 4 × light/dark)

`forest` is dark-only (light == dark). `heritage` dark falls back to garden dark (`_gardenDark`). Hex values transcribed from `plant_community_mobile/lib/core/theme/app_palettes.dart`.

| field | loam L | loam D | garden L | garden/heritage D (`_gardenDark`) | forest (L=D) | heritage L |
|---|---|---|---|---|---|---|
| bg (`surface`)      | `#F6F0E2` | `#12100A` | `#F4F1E4` | `#0E140F` | `#0F1A12` | `#F0EBDB` |
| bg2 (`surface-2`)   | `#ECE3CC` | `#1C1810` | `#ECE7D2` | `#161E18` | `#16241A` | `#E4DBC2` |
| bg3 (`surface-3`)   | `#DDD0AE` | `#272218` | `#DFD9BD` | `#1F2A21` | `#1F3024` | `#D3C9AC` |
| ink                 | `#1F1A12` | `#F2EBD8` | `#102015` | `#EEF4E2` | `#E8F0D8` | `#1A1F10` |
| ink2 (`ink-2`)      | `#4A3F2C` | `#D4C8A4` | `#2E4233` | `#C8D5B8` | `#C2D2AC` | `#3A4128` |
| ink3 (`ink-3`)      | `#7C6E55` | `#8A7E60` | `#5C6E5A` | `#8A9A7E` | `#87987C` | `#756E50` |
| line                | `#D4C5A0` | `#2E2818` | `#D2CCAE` | `#2A3628` | `#2A3A2F` | `#CFC4A2` |
| line2 (`line-2`)    | `#BCA97E` | `#423A26` | `#B8B391` | `#3A4A37` | `#3D5142` | `#B8AC85` |
| moss (`primary`)    | `#4A7034` | `#B8D680` | `#2F6B3A` | `#A8CC6E` | `#B8DC7C` | `#3D5A22` |
| onMoss (`on-primary`)| `#F6F0E2`| `#12100A` | `#F4F1E4` | `#14180F` | `#0F1A12` | `#F0EBDB` |
| sage (`secondary`)  | `#97B86A` | `#A3C26C` | `#7FA66B` | `#9BBE82` | `#A8CC6E` | `#768B4E` |
| leaf                | `#C2D680` | `#CCE090` | `#A8CC6E` | `#BEDC8C` | `#C8E198` | `#A4B86E` |
| honey (`tertiary`)  | `#E0B445` | `#E8C76B` | `#E5B84B` | `#E8C76B` | `#F0CC68` | `#C99B3A` |
| clay                | `#C9542A` | `#E58A52` | `#D86B2C` | `#E58A52` | `#F0935A` | `#B0481E` |
| onClay (`on-clay`)  | `#FFF8EA` | `#12100A` | `#FFF8EA` | `#14180F` | `#0F1A12` | `#FFF8EA` |
| berry               | `#C45577` | `#D286A2` | `#B8466A` | `#D286A2` | `#E090A8` | `#B8466A` |
| sky                 | `#6FA0AA` | `#9CC0CA` | `#6FA0AA` | `#9CC0CA` | `#94BFC8` | `#6FA0AA` |
| ok                  | `#3F5D3F` | `#3F5D3F` | `#3F5D3F` | `#3F5D3F` | `#3F5D3F` | `#3F5D3F` |
| warn                | `#C4A570` | `#C4A570` | `#C4A570` | `#C4A570` | `#C4A570` | `#C4A570` |
| bad (`error`)       | `#B5451C` | `#B5451C` | `#B5451C` | `#B5451C` | `#B5451C` | `#B5451C` |

> `error`'s on-color = `on-clay` (matches mobile `ColorScheme.onError = colors.onClay`).

### Density (padCard, padScreen, gapY)

| density | `--gt-pad-card` | `--gt-pad-screen` | `--gt-gap` |
|---|---|---|---|
| comfortable | 18px | 18px | 14px |
| **cozy** (default) | 16px | 16px | 12px |
| compact | 12px | 14px | 10px |

### Shadows

| token | light (`#1B2218` → `rgb(27,34,24)`) | dark (`#000`) |
|---|---|---|
| `shadow-1` | `0 1px 0 /.04, 0 2px 6px /.05` | same offsets, `rgba(0,0,0,…)` |
| `shadow-2` | `0 2px 0 /.05, 0 8px 22px /.08` | … |
| `shadow-3` | `0 4px 0 /.06, 0 18px 40px /.14` | … |

---

## Typography System

Self-host woff2 under `web/public/fonts/`. Type roles transcribed from `app_typography.dart`. Italic display/headings are the signature element.

| Role | Family | Weight | Style | Size / line-height / tracking | Web utility plan |
|---|---|---|---|---|---|
| display | Bricolage | 600 | italic | 32 / 1.02 / −0.02em | `font-display italic` + `text-[2rem]` (or `.gt-display`) |
| h1 | Bricolage | 600 | italic | 28 / 1.1 / −0.02em | `.gt-h1` |
| h2 | Bricolage | 600 | italic | 22 / 1.15 / −0.02em | `.gt-h2` |
| h3 | Bricolage | 600 | italic | 18 / 1.2 / −0.02em | `.gt-h3` |
| eyebrow | Geist | 600 | upper | 11 / 1.4 / +0.66px | `<Eyebrow>` component |
| body | Geist | 400 | — | 16 / 1.625 | `font-sans text-base` |
| bodySm | Geist | 400 | — | 14 / 1.625 | `text-sm` |
| bodyXs | Geist | 400 | — | 12 / 1.5 | `text-xs` |
| label | Geist | 500 | — | 14 / 1.4 | `font-medium text-sm` |
| button | Geist | 600 | — | 16 / 1.4 / +0.25px | `ClayButton` default |
| buttonSm | Geist | 600 | — | 14 / 1.4 / +0.25px | `ClayButton` small |
| caption | Geist | 400 | — | 12 / 1.4 | `text-xs` |
| mono | Geist Mono | 400 | (italic at use) | 14 / tabular | `font-mono italic` for scientific names |

Heading roles ship as small component classes (`.gt-h1/.gt-h2/.gt-h3/.gt-display`) in a `@layer components` block, since they bundle family + style + tracking + leading; body/label/mono use Tailwind utilities. `font-sans` (Geist) becomes the global default on `body`.

---

## Legacy → Green Thumb Mapping (the migration key)

The 1095 usages are **table-driven**, not 1095 judgments. Apply this map; judgment only enters at the marked boundaries.

| Legacy class | → Green Thumb | Notes |
|---|---|---|
| `text-gray-900` | `text-ink` | primary text |
| `text-gray-700`, `text-gray-800` | `text-ink-2` | secondary text |
| `text-gray-400/500/600` | `text-ink-3` | muted text |
| `bg-white` | `bg-surface-2` | cards (mobile cards = bg2) |
| `bg-gray-50`, `bg-gray-100` | `bg-surface` / `bg-surface-2` | page vs subtle fill — **context** |
| `bg-gray-800/900` (dark fills) | `bg-surface` / `bg-surface-2` | only on `dark:`; usually removable |
| `border-gray-200` | `border-line` | |
| `border-gray-300/600` | `border-line-2` | |
| `bg-green-600`, `bg-green-700` | `bg-clay` (button) **or** `bg-primary` (brand accent) | **BOUNDARY**: CTA→clay, brand surface/logo→primary |
| `ring-green-500`, `border-green-500/600` | `ring-primary` / `border-primary` | focus rings = brand |
| `text-green-600/700/800` | `text-leaf` **or** `text-primary` | label/badge→leaf, link/icon→primary — **BOUNDARY** |
| `bg-green-50`, `bg-green-100` | `bg-primary/10` | tinted brand fill (alpha utility) |
| `bg-red-50`, `text-red-*`, `border-red-*`, `bg-red-900` | `error` tokens (`bg-error/10`, `text-error`, `border-error`) | |
| `bg-yellow-50`, `text-yellow-900`, `amber-*` | `warn` or `tertiary` | warnings→warn, honey accents→tertiary — **BOUNDARY** |
| `text-blue-*`, `bg-blue-*` | `text-sky` | water/info accent |
| `purple-*` | `berry` | social/community |
| `rounded-sm/md/lg/xl/full` | unchanged class, **new values** | re-skinned automatically by the radius override; promote to `rounded-pill` on buttons |
| `dark:<color>` variants | **removed** | `--gt-*` vars flip under `[data-mode]`; `bg-surface` is correct in both modes |
| screen/card padding (`p-4`, `p-6`, `px-4`) | `p-card` / `px-screen` / `gap-gapy` | only where density-responsiveness is wanted; structural spacing stays Tailwind numeric |

> **Alpha utilities:** `bg-primary/10`, `bg-clay/10`, etc. work because the color is a `var()`; Tailwind 4 composes the slash-opacity via `color-mix`. Verify in Task 1's test.

---

## ThemeContext API

```tsx
type Palette = 'loam' | 'garden' | 'forest' | 'heritage';
type Density = 'comfortable' | 'cozy' | 'compact';
type Mode    = 'light' | 'dark';

interface ThemeContextValue {
  palette: Palette; density: Density; mode: Mode;
  setPalette(p: Palette): void;
  setDensity(d: Density): void;
  setMode(m: Mode): void;
  toggleMode(): void;
}
```

- On mount: read `localStorage` keys `gt-palette` / `gt-density` / `gt-mode` (defaults `loam` / `cozy` / `light`); apply to `document.documentElement.dataset` (`data-palette`, `data-density`, `data-mode`).
- On any setter: update state, write the data-attribute, persist to `localStorage`.
- `ThemeProvider` wraps the app in `main.tsx` (above `RootLayout`). Because `:root` carries the loam/light/cozy default, **a subtree without the provider still renders correctly** (learning A) — the provider only *overrides* defaults.
- No SSR concern (Vite SPA), but set the initial `<html data-palette …>` in `index.html` or an inline pre-hydration script to avoid a flash if a non-default theme is persisted (optional polish).

---

## Shared Components

### `ClayButton` (`web/src/components/ui/ClayButton.tsx`)

```tsx
type ClayVariant = 'primary' | 'secondary' | 'outline';
type ClaySize    = 'sm' | 'md' | 'lg';
interface ClayButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string; icon?: React.ReactNode; fullWidth?: boolean;
  size?: ClaySize; variant?: ClayVariant; loading?: boolean;
}
```

| Variant | Classes |
|---|---|
| primary | `bg-clay text-on-clay shadow-1` |
| secondary | `bg-primary text-on-primary shadow-1` |
| outline | `bg-transparent border border-primary text-primary` |

- Shape `rounded-pill`; min tap target `min-h-[44px]` (tailwind.md rule).
- Sizes (px / py / font): sm `px-md py-sm`/14 · md `px-lg py-md`/16 · lg `px-xl py-lg`/16 — uses spacing scale.
- Disabled: `bg-surface-3 text-ink-3/40 shadow-none cursor-not-allowed`, `disabled` attribute.
- Loading: replaces icon/label with a `LoadingSpinner` sized to text; `aria-busy`.

**Tests (Vitest):** renders label; primary has `bg-clay`; secondary has `bg-primary`; outline has `border-primary` + transparent bg; disabled sets `disabled` + no shadow; `fullWidth` adds `w-full`; icon renders; loading shows spinner & hides label.

### `GrainOverlay` (`web/src/components/ui/GrainOverlay.tsx`)

Wraps children; renders an absolutely-positioned, `pointer-events-none`, low-opacity tiled noise layer above the background but below content. Implementation: a fixed/absolute `div` with a data-URI SVG `feTurbulence` noise as `background-image`, `mix-blend-multiply` (light) / `screen` (dark), `opacity ~0.04`. **Used only on HomePage.** Test: renders children; overlay node present with `aria-hidden` and `pointer-events-none`.

### `Eyebrow` (`web/src/components/ui/Eyebrow.tsx`)

`<p className="font-sans font-semibold uppercase text-ink-3 text-[11px] tracking-[0.66px] leading-[1.4]">{children}</p>` (or a `.eyebrow` component class). Test: renders text uppercase-styled with `text-ink-3`.

---

## Settings UI (`web/src/pages/SettingsPage.tsx`)

The current page is a "Coming Soon" placeholder — replace its body with working controls wired to `ThemeContext`:

- **Appearance** — Light / Dark toggle (`toggleMode`), eyebrow section heading.
- **Palette** — 4 tappable swatches (Loam / Garden / Forest / Heritage); selected = 2px `border-primary` + bold; calls `setPalette`. Each swatch previews its own clay/primary colors.
- **Density** — segmented control (Comfortable / Cozy / Compact); calls `setDensity`.

**Tests (Vitest):** 4 palette swatches render; clicking "Forest" calls `setPalette('forest')` **and** sets `document.documentElement` `data-palette="forest"`; density control renders; changing it calls `setDensity` and sets `data-density`; dark toggle flips `data-mode`. (These are jsdom-safe — attribute application, not color resolution.)

---

## Debug Preview Route (`/debug/theme`)

`web/src/pages/debug/ThemePreviewPage.tsx`, registered only when `import.meta.env.DEV`. Renders a grid of 24 cards (4 palettes × 3 densities × light/dark), each card a self-contained scope that sets `data-palette/-density/-mode` on its own wrapper element, showing: surface/card, primary & clay buttons, ink hierarchy, leaf/berry/sky/honey chips, an eyebrow, a Bricolage heading, and a GeistMono scientific name. This is the manual-QA surface for the matrix. Test: route renders 24 preview cards in dev.

---

## Migration Batches → TDD Tasks (~14)

Foundation-first (mirrors mobile's widgets-first shape — everything depends on Task 1–4).

1. **Token foundation** — `index.css`: **replaces the dead `@theme` block** with all palette/density/mode override blocks, `@theme inline`, radius/shadow scales, `@custom-variant dark`. Orphaned legacy tokens dropped here. *(All value-resolution tests — color AND density px — → Playwright; data-attribute + class-presence → Vitest.)*
2. **Typography foundation** — `@font-face`, font families in `@theme`, heading component classes, global `font-sans` on body. *(Vitest: heading class applies `font-display`; Playwright: font actually loads/renders.)*
3. **ThemeContext + localStorage** — provider, data-attributes, persistence. *(Vitest: attribute application + persistence + default-without-provider.)*
4. **Primitives** — `ClayButton`, `GrainOverlay`, `Eyebrow`; migrate existing `ui/` (`Button`, `Input`, `LoadingSpinner`).
5. **Settings UI** — palette/density/dark controls.
6. **Layout** — `Header`, `Footer`, `UserMenu`, `RootLayout`, `ProtectedLayout`.
7. **HomePage** — tokens + `GrainOverlay` + `Eyebrow` + `ClayButton`.
8. **Auth** — `LoginPage`, `SignupPage`.
9. **Blog** — `BlogCard`, `StreamFieldRenderer`, `BlogListPage`, `BlogDetailPage`, `BlogPage`, `BlogPreview`.
10. **Forum** — `ThreadCard`, `PostCard`, `CategoryCard`, `ImageUploadWidget`, `TipTapEditor` + `CategoryListPage`, `ThreadListPage`, `ThreadDetailPage`, `SearchPage` (**strip `dark:` variants here**).
11. **Diagnosis + Plant ID + misc** — `DiagnosisCard`, `ReminderManager`, `SaveDiagnosisModal`, `StreamFieldEditor`, `DiagnosisListPage`, `DiagnosisDetailPage`, `IdentifyPage`, `FileUpload`, `IdentificationResults`, `ProfilePage`, `ErrorBoundary`.
12. **Debug preview route** — `/debug/theme`, 24 combos.
13. **Delete legacy** — after `grep` proves zero references to raw palette classes (migrated in Tasks 4–11) and confirms no orphaned `@theme` tokens remain; remove any stragglers; re-run full suite.
14. **Final verification** — full Vitest + relevant Playwright + `type-check` + `lint`; manual QA of live switching.

---

## Testing Strategy

Carries the mobile learnings. **Know the test layer's limits (learning C):** jsdom does **not** cascade CSS custom properties from stylesheets, so `getComputedStyle(el).getPropertyValue('--color-clay')` after switching `data-palette` reads empty/default even when the code is correct.

| Layer | Asserts | Examples |
|---|---|---|
| **Vitest (jsdom)** | Logic, state, **data-attribute application**, **class presence**, persistence | `expect(document.documentElement).toHaveAttribute('data-palette','forest')`; `localStorage.getItem('gt-palette')==='forest'`; `expect(btn).toHaveClass('bg-clay')`; Settings click sets `data-density="compact"`. **Class presence + attribute application ONLY — never computed-value resolution: jsdom does not cascade stylesheet vars and Vitest isn't running the Tailwind pipeline, so `getComputedStyle().getPropertyValue('--gt-*')` reads empty (the learning C/D false-green trap).** |
| **Playwright (real browser)** | **All value resolution** (color, density px), font rendering, responsive/visual | After `setPalette('forest')`, `getComputedStyle($('.surface')).backgroundColor` = forest bg; **forest+dark surface = `#0F1A12`, NOT loam-dark `#12100A`** (cascade-fix guard); compact `p-card` computes to **12px** (≠ cozy 16, ≠ comfortable 18 — the discriminating wiring proof, learning B); per-page screenshots; debug route renders all 24 combos |

- **Discriminating wiring (learning B):** every "is it themed?" test must assert a value distinct from BOTH the `:root` default AND the old legacy value. The compact-density `p-card`=12px is the cleanest such discriminator (≠ default 16, ≠ any legacy padding) — but because it's a *resolved value*, it lives in **Playwright**, not Vitest. Vitest's wiring proof is data-attribute application + class presence.
- **Test isolation (learning I):** `beforeEach` clears `localStorage` and resets `document.documentElement` dataset.
- **Run the FULL suite before the PR (learning D):** all of Vitest + the Playwright specs — not just the changed area's tests.
- **Generated artifacts (learning H):** none — Tailwind 4 `@theme` is plain committed CSS, no codegen step. (Confirmed: no `tailwind.config.*`, CSS-first config.)

---

## Mobile-Session Learnings Applied

| # | Learning | Web application |
|---|---|---|
| A | Null-safe token access | `:root` default palette → components render with no provider; never throw on a missing context |
| B | Discriminating "is it wired?" tests | **Playwright** asserts compact `p-card` computes to 12px (≠ default 16, ≠ legacy) and forest+dark ≠ loam-dark; **Vitest** asserts data-attribute application + class presence |
| C | Know the test layer's limits | ALL value resolution (color + density px) → Playwright; data-attribute / class presence / logic → Vitest |
| D | Run the full suite before declaring done | full Vitest + Playwright before PR |
| E | Plan code is a guide — read each component first | each migration task reads the current component before editing; the data-driven realities (e.g. `.map` over feature cards) take precedence over assumed structure |
| F | Delete legacy only after zero-reference grep | Task 13 gates on `grep` for dead tokens + raw palette classes |
| G | TDD + commit per task | failing test → impl → green → commit; each commit keeps its area shippable |
| H | Generated-artifact gate | n/a — `@theme` is committed CSS, no codegen |
| I | Persistence + test isolation | localStorage; cleared/reset per test |
| J | Runtime palette switching is THE hard problem | solved via `@theme inline` + `[data-palette][data-mode][data-density]` overrides + Context — verified against Tailwind 4 docs |

---

## Success Criteria

1. `grep -rE "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+" web/src --include="*.tsx"` returns **zero** matches.
2. The old `@theme` block is fully replaced by the Green Thumb token system; orphaned legacy tokens (`--color-*-hover`/`-light`, `--color-secondary`, `--color-success`/`-warning`/`-info`, unused `--font-*` size tokens) no longer present in `index.css`.
3. `npm run type-check` — zero errors; `npm run lint` — clean.
4. `npm run test` (Vitest) — all pass, incl. data-attribute wiring + density discriminator.
5. Relevant Playwright specs — color resolution per palette + per-page visual pass.
6. `/debug/theme` shows all 24 combinations correctly styled (manual QA).
7. Settings page switches palette / density / dark **live**, persists across reload.
8. `GrainOverlay` visible on HomePage; absent elsewhere.
9. No `dark:` *color* variants remain (vars handle dark); any residual `dark:` keys off the in-app toggle, not OS.

---

## Phase B — Deferred Follow-up (NOT in this plan)

Building the `design_reference` mockups as net-new website routes was evaluated and **declined** — the website already has richer equivalents for 5 of 7 screens. If revisited, it would be a separate spec/plan/PR and would depend on this token foundation. Per-screen finding:

- **PlantCamera / PlantResults** → existing `IdentifyPage` + `IdentificationResults` are functionally richer (real API, save, auth, errors). Mockups only add camera-capture UX + an inline care card.
- **PlantHistory** → `DiagnosisListPage` is far richer (search/filter/sort/paginate/CRUD).
- **ForumUI** → existing forum pages are far richer (real threads, TipTap editor, categories).
- **HomePage** → comparable; mockup adds onboarding emphasis.
- **SettingsPage** → mockup richer than the *old* placeholder, but Phase A already replaces it with working theme controls.
- **SplashScreen** → genuine gap (no web equivalent), but websites rarely need a splash; low value.

Net: the mockups are best used as a visual reference to decide if any single layout idea is worth porting later — not as a build target.
