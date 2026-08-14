# Canopy Foundation (PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the Canopy token system, the Houseplant MD app shell, and the ui primitive kit so every route renders inside the new chrome, with the 4-palette switcher retired and a 404 page added.

**Architecture:** Two-layer tokens (raw `--canopy-*` ramp under the existing semantic `--gt-*` names) so all current pages restyle without markup changes; a new `AppShell` (sidebar + topbar + portal-based right rail) replaces Header/Footer inside `RootLayout`; new primitives live in `src/components/ui/` and are consumed by later per-area PRs.

**Tech Stack:** React 19, TypeScript, Tailwind 4.2 CSS-first (`@theme` in `index.css`, no config file), Vitest + Testing Library, Playwright, lucide-react.

**Spec:** `docs/superpowers/specs/2026-08-13-canopy-design.md`

## Global Constraints

- Work on branch `feat/canopy-foundation` (exists; carries the spec commits). Never push to `main`.
- All work under `web/` except nothing — this PR touches only the web app. Run all npm commands from `/Users/williamtower/projects/plant_id_community/web`.
- Palette hexes (verbatim from spec): abyss `#051F20`, pine `#0B2B26`, moss `#163832`, forest `#235347`, sage `#8EB69B`, mint `#DAF1DE`, pollen `#E7B75F`, bloom `#E88E76`, orchid `#B7A5E0`, error red `#DE6B5A`.
- Brand: UI says **Houseplant MD** (never "PlantID" in new code); logo is the **badged leaf** mark. The cross must NEVER render red-on-white (Geneva emblem constraint) — it is `#DE6B5A` on green grounds only.
- Semantic token NAMES (`--gt-*`, Tailwind utilities `bg-surface`, `text-ink` …) must not change — only their values. The `.wf-*` Field Notes block in `index.css` (lines ~314–591) stays untouched in this PR (deleted in PR 2).
- Density tokens and `data-density` stay. `data-palette` is removed entirely.
- All animation must be disabled under `prefers-reduced-motion: reduce` (wrap in `no-preference` media queries).
- Pre-commit hooks lint whole staged files (prettier/eslint): run `npx prettier --write <files>` on every touched file before `git add`. Kimi-review gates commits; fix a `[CRITICAL]` rather than bypassing.
- PostToolUse formatter strips imports that are unused at format time — always add an import in the same edit as its first usage.
- Playwright must be invoked as `./node_modules/.bin/playwright` (the rtk proxy mangles `npx playwright` args).
- Unit tests: `npx vitest run <path>` for one file, `npm test -- --run` for the suite.
- Commit after each task with a `feat(canopy): …` / `test(canopy): …` message ending in the `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: Canopy token layer in `index.css` + theme e2e/probe updates

**Files:**

- Modify: `web/src/index.css:39-205` (replace `:root` palette, all `[data-palette]` blocks, dark blocks, shadow block), `web/src/index.css:207-247` (extend `@theme inline`), `web/src/index.css:270-312` (body + display classes), plus append component classes BEFORE the `.wf-*` section comment at line 314.
- Modify: `web/src/pages/debug/ThemePreviewPage.tsx`
- Modify: `web/e2e/green-thumb-theme.spec.ts`
- Test: `web/e2e/green-thumb-theme.spec.ts`, `web/src/pages/debug/ThemePreviewPage.test.tsx`

**Interfaces:**

- Consumes: nothing (first task).
- Produces: raw vars `--canopy-abyss|pine|moss|forest|sage|mint|pollen|bloom|orchid|red`; new semantic tokens `--gt-ground`, `--gt-grad-card`, `--gt-grad-sweep`, `--gt-grad-cta`, `--gt-grad-ambient`, `--gt-tile-sage|pollen|bloom|orchid`; Tailwind color utilities `abyss`, `pollen`, `bloom`, `orchid` (registered in `@theme inline`); CSS classes `.canopy-card`, `.canopy-interactive`, `.canopy-cta`, `.canopy-ground`, `.app-rail`, `.app-nav-active`. Every later task styles through these.

- [ ] **Step 1: Rewrite the token blocks.** In `web/src/index.css`, replace everything from the `/* ───────── Green Thumb semantic vars` comment (line 39) through the density blocks' end (line 204) with:

```css
/* ───────── Canopy raw ramp (spec §3.1) ───────── */
:root {
  --canopy-abyss: #051f20;
  --canopy-pine: #0b2b26;
  --canopy-moss: #163832;
  --canopy-forest: #235347;
  --canopy-sage: #8eb69b;
  --canopy-mint: #daf1de;
  --canopy-pollen: #e7b75f;
  --canopy-bloom: #e88e76;
  --canopy-orchid: #b7a5e0;
  --canopy-red: #de6b5a;
}

/* ───────── semantic layer — :root = DARK (Canopy default, spec §3.4) ───────── */
:root {
  --gt-ground: var(--canopy-abyss);
  --gt-surface: var(--canopy-pine);
  --gt-surface-2: var(--canopy-moss);
  --gt-surface-3: color-mix(in oklab, var(--canopy-moss) 55%, var(--canopy-forest));
  --gt-ink: var(--canopy-mint);
  --gt-ink-2: color-mix(in oklab, var(--canopy-sage) 85%, var(--canopy-mint));
  --gt-ink-3: color-mix(in oklab, var(--canopy-sage) 65%, var(--canopy-forest));
  --gt-line: color-mix(in oklab, var(--canopy-forest) 45%, transparent);
  --gt-line-2: color-mix(in oklab, var(--canopy-forest) 75%, transparent);
  --gt-primary: var(--canopy-mint);
  --gt-on-primary: var(--canopy-abyss);
  --gt-secondary: var(--canopy-sage);
  --gt-tertiary: var(--canopy-pollen);
  --gt-clay: var(--canopy-pollen);
  --gt-on-clay: var(--canopy-abyss);
  --gt-leaf: var(--canopy-sage);
  --gt-berry: var(--canopy-bloom);
  --gt-sky: var(--canopy-orchid);
  --gt-ok: var(--canopy-sage);
  --gt-warn: var(--canopy-pollen);
  --gt-error: var(--canopy-red);
  --gt-pad-card: 16px;
  --gt-pad-screen: 16px;
  --gt-gap: 12px;
  --gt-shadow-1: 0 1px 0 rgba(0, 0, 0, 0.1), 0 2px 6px rgba(0, 0, 0, 0.18);
  --gt-shadow-2: 0 2px 0 rgba(0, 0, 0, 0.12), 0 8px 22px rgba(0, 0, 0, 0.26);
  --gt-shadow-3: 0 4px 0 rgba(0, 0, 0, 0.14), 0 18px 40px rgba(0, 0, 0, 0.38);
  --gt-grad-card: linear-gradient(
    150deg,
    color-mix(in oklab, var(--canopy-moss) 88%, var(--canopy-forest)) 0%,
    var(--canopy-moss) 46%,
    color-mix(in oklab, var(--canopy-moss) 80%, var(--canopy-pine)) 100%
  );
  --gt-grad-sweep: radial-gradient(
    120% 90% at 12% -10%,
    color-mix(in oklab, var(--canopy-mint) 9%, transparent) 0%,
    transparent 55%
  );
  --gt-grad-cta: linear-gradient(
    135deg,
    var(--canopy-mint) 0%,
    color-mix(in oklab, var(--canopy-sage) 70%, var(--canopy-mint)) 100%
  );
  --gt-grad-ambient:
    radial-gradient(
      90rem 60rem at 18% -12%,
      color-mix(in oklab, var(--canopy-sage) 16%, transparent) 0%,
      transparent 60%
    ),
    radial-gradient(
      70rem 50rem at 105% 42%,
      color-mix(in oklab, var(--canopy-forest) 34%, transparent) 0%,
      transparent 62%
    );
  --gt-tile-sage: linear-gradient(135deg, var(--canopy-mint), var(--canopy-sage));
  --gt-tile-pollen: linear-gradient(135deg, #f2d28f, var(--canopy-pollen));
  --gt-tile-bloom: linear-gradient(135deg, #f5b3a0, var(--canopy-bloom));
  --gt-tile-orchid: linear-gradient(135deg, #d3c7ee, var(--canopy-orchid));
}

/* ───────── light mode — derived, not inverted (spec §3.4) ───────── */
[data-mode='light'] {
  --gt-ground: #cde9d4;
  --gt-surface: var(--canopy-mint);
  --gt-surface-2: #f2faf4;
  --gt-surface-3: #e9f5ec;
  --gt-ink: var(--canopy-pine);
  --gt-ink-2: #35594b;
  --gt-ink-3: #5e8271;
  --gt-line: color-mix(in oklab, var(--canopy-sage) 38%, transparent);
  --gt-line-2: color-mix(in oklab, var(--canopy-sage) 62%, transparent);
  --gt-primary: var(--canopy-forest);
  --gt-on-primary: var(--canopy-mint);
  --gt-shadow-1: 0 1px 0 rgba(11, 43, 38, 0.05), 0 2px 6px rgba(11, 43, 38, 0.08);
  --gt-shadow-2: 0 2px 0 rgba(11, 43, 38, 0.06), 0 8px 22px rgba(11, 43, 38, 0.12);
  --gt-shadow-3: 0 4px 0 rgba(11, 43, 38, 0.07), 0 18px 40px rgba(11, 43, 38, 0.18);
  --gt-grad-card: linear-gradient(150deg, #fdfffd 0%, #f2faf4 55%, #e9f5ec 100%);
  --gt-grad-sweep: radial-gradient(
    120% 90% at 12% -10%,
    rgba(255, 255, 255, 0.85) 0%,
    transparent 55%
  );
  --gt-grad-cta: linear-gradient(135deg, var(--canopy-moss), var(--canopy-forest));
  --gt-grad-ambient: radial-gradient(
    70rem 40rem at 15% -20%,
    rgba(255, 255, 255, 0.75) 0%,
    transparent 60%
  );
}

/* ───────── density blocks (cozy is the :root default) — UNCHANGED ───────── */
[data-density='comfortable'] {
  --gt-pad-card: 18px;
  --gt-pad-screen: 18px;
  --gt-gap: 14px;
}
[data-density='compact'] {
  --gt-pad-card: 12px;
  --gt-pad-screen: 14px;
  --gt-gap: 10px;
}
```

This deletes: the loam `:root` values, all three `[data-palette]` blocks, both `[data-palette][data-mode='dark']` blocks, and the bare `[data-mode='dark']` shadow block (dark shadows now live in `:root`).

- [ ] **Step 2: Extend `@theme inline`.** Inside the existing `@theme inline` block, add after the `--color-error` line:

```css
  --color-abyss: var(--canopy-abyss);
  --color-pollen: var(--canopy-pollen);
  --color-bloom: var(--canopy-bloom);
  --color-orchid: var(--canopy-orchid);
  --color-ground: var(--gt-ground);
```

- [ ] **Step 3: Update body + display classes.** In `@layer base`, change the body background to the ground token:

```css
@layer base {
  body {
    font-family: var(--font-sans);
    background: var(--gt-ground);
    color: var(--gt-ink);
  }
}
```

In the `.gt-display`, `.gt-h1`, `.gt-h2`, `.gt-h3` classes, delete the `font-style: italic;` line from each (Canopy display type is upright) and delete the stale italic comment above `.gt-display`.

- [ ] **Step 4: Add Canopy component classes.** Immediately BEFORE the `/* ═══════════ Field Notes · forum ledger system` comment, insert:

```css
/* ═══════════ Canopy chrome & materials (PR 1) ═══════════ */
@layer components {
  .canopy-card {
    position: relative;
    overflow: hidden;
    background: var(--gt-grad-card);
    border: 1px solid var(--gt-line);
  }
  .canopy-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: var(--gt-grad-sweep);
    pointer-events: none;
  }
  .canopy-interactive {
    transition:
      transform 0.15s ease,
      border-color 0.15s ease;
  }
  .canopy-interactive:hover {
    transform: translateY(-1px);
    border-color: var(--gt-line-2);
  }
  .canopy-cta {
    background: var(--gt-grad-cta);
    color: var(--gt-on-primary);
  }
  .canopy-ground {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background: var(--gt-grad-ambient);
  }
  .app-shell {
    position: relative;
    z-index: 1;
  }
  /* rail hides itself when no page fills it (portal target is empty) */
  .app-rail:not(:has(*)) {
    display: none;
  }
  .app-nav-active {
    background: var(--gt-grad-card);
    border: 1px solid var(--gt-line);
    color: var(--gt-ink);
  }
}
@media (prefers-reduced-motion: no-preference) {
  .canopy-ground {
    animation: canopy-drift 70s ease-in-out infinite alternate;
  }
}
@keyframes canopy-drift {
  from {
    transform: translate3d(0, 0, 0) scale(1);
  }
  to {
    transform: translate3d(-3%, 2.5%, 0) scale(1.06);
  }
}
```

- [ ] **Step 5: Update the dev probe page.** Rewrite `web/src/pages/debug/ThemePreviewPage.tsx`: delete the `PALETTES` const; the combo grid becomes `DENSITIES × MODES` (6 cards) with no `data-palette` attribute; the outer wrapper uses the token ground instead of the hardcoded neutral. Concretely: remove line 4; in the combo `flatMap`, drop the palette loop and key by `` `${density}-${mode}` ``; remove the `data-palette={palette}` prop and the `{palette}/` prefix in the label; change the outer `className="min-h-screen bg-neutral-100 p-4"` to `className="min-h-screen bg-ground p-4"`; delete both `italic` classNames on the `font-mono` spans. Then run `npx vitest run src/pages/debug/ThemePreviewPage.test.tsx` — it is a 10-line smoke test; if it asserts a combo-card count of 24, change that number to 6; otherwise leave it.

- [ ] **Step 6: Rewrite the theme e2e spec.** Replace the body of `web/e2e/green-thumb-theme.spec.ts` tests (keep the `setTheme` helper but delete its `palette` field and the `data-palette` lines):

```ts
test.describe('Canopy runtime tokens', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/debug/theme');
  });

  test('default (dark) surface resolves to pine', async ({ page }) => {
    await setTheme(page, {});
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(11, 43, 38)'
    );
  });

  test('light mode resolves to mint cream', async ({ page }) => {
    await setTheme(page, { mode: 'light' });
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(218, 241, 222)'
    );
  });

  test('density changes resolved padding (discriminating wiring)', async ({ page }) => {
    await setTheme(page, { density: 'compact' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '12px');
    await setTheme(page, { density: 'comfortable' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '18px');
  });

  test('alpha modifier resolves on a themed token', async ({ page }) => {
    await setTheme(page, {});
    const bg = await page
      .getByTestId('probe-alpha')
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).not.toBe('rgba(0, 0, 0, 0)'); // modifier ignored → transparent
    expect(bg).not.toBe('rgb(231, 183, 95)'); // modifier dropped → solid pollen #E7B75F
  });

  test('display headings use Bricolage Grotesque', async ({ page }) => {
    const family = await page
      .getByTestId('probe-display')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(family).toContain('Bricolage Grotesque');
  });
});
```

- [ ] **Step 7: Sweep stale palette references.** Run `grep -rn "data-palette\|'loam'\|'garden'\|'heritage'" src/ --include="*.tsx" --include="*.ts"` — remaining hits after this task must be only `ThemeContext*` and `SettingsPage*` (handled in Task 2). `src/components/forum/ThreadCard.tsx` matches on a comment only: reword that comment to not reference palettes; change no behavior.

- [ ] **Step 8: Verify.** Run `npm run build` (must compile), `npx vitest run src/pages/debug/ThemePreviewPage.test.tsx` (PASS). Start `npm run dev` and run `./node_modules/.bin/playwright test e2e/green-thumb-theme.spec.ts --project=chromium` → all PASS. Expected visual state: site renders in light-mint by default (ThemeContext still defaults to light until Task 2) and dark forest with localStorage `gt-mode=dark`.

- [ ] **Step 9: Commit.** Prettier-write touched files, then commit `feat(canopy): replace palette matrix with Canopy two-layer tokens (dark-first + derived light)`.

---

### Task 2: ThemeContext dark default + palette retirement + Settings

**Files:**

- Modify: `web/src/contexts/ThemeContext.tsx`, `web/src/contexts/ThemeContext.test.tsx`
- Modify: `web/src/pages/SettingsPage.tsx`, `web/src/pages/SettingsPage.test.tsx`

**Interfaces:**

- Consumes: token layer from Task 1.
- Produces: `useTheme(): { density, mode, setDensity, setMode, toggleMode }` — **no `palette`/`setPalette`**; exported types `Density`, `Mode` (type `Palette` deleted). Mode default `'dark'`. Task 7's Topbar consumes `mode`/`toggleMode`.

- [ ] **Step 1: Update the context test first.** Rewrite `ThemeContext.test.tsx`: in `Harness`, drop `palette`/`setPalette` (state testid renders `` `${density}/${mode}` ``, buttons: `compact`, `toggle`); in `beforeEach` drop the `dataset.palette` line; tests become: defaults `cozy/dark` with `data-density="cozy"` + `data-mode="dark"` and NO `data-palette` attribute (`expect(document.documentElement).not.toHaveAttribute('data-palette')`); `setDensity` persists (unchanged); `toggleMode` from dark→light persists `gt-mode=light`; reads persisted `gt-mode=light` on mount; invalid stored density `'ultrawide'` falls back to `cozy`.

- [ ] **Step 2: Run it to see it fail.** `npx vitest run src/contexts/ThemeContext.test.tsx` → FAIL (context still has palette, defaults light).

- [ ] **Step 3: Rewrite `ThemeContext.tsx`.** Delete: `Palette` type, `PALETTES`, `KEYS.palette`, the palette state/effect/`setPalette`, and `palette` from the context value/interface. Change the mode default to `'dark'`: `useState<Mode>(() => read(KEYS.mode, 'dark', MODES))`. Add one cleanup effect so stale attributes from old sessions disappear:

```tsx
useEffect(() => {
  delete document.documentElement.dataset.palette;
  try {
    localStorage.removeItem('gt-palette');
  } catch {
    /* ignore */
  }
}, []);
```

- [ ] **Step 4: Run tests.** `npx vitest run src/contexts/ThemeContext.test.tsx` → PASS.

- [ ] **Step 5: Update Settings test then page.** In `SettingsPage.test.tsx`: delete the two palette tests and the `dataset.palette` cleanup line; add `it('renders no palette controls', () => { renderPage(); expect(screen.queryByRole('button', { name: /loam/i })).toBeNull(); })`; the dark-toggle test now starts dark, so click `screen.getByRole('button', { name: /light/i })` and assert `data-mode="light"`. In `SettingsPage.tsx`: delete `PALETTE_SWATCH`, the whole Palette `<section>`, and the `Palette` import; `useTheme()` destructuring drops `palette`/`setPalette`. Run `npx vitest run src/pages/SettingsPage.test.tsx` → PASS.

- [ ] **Step 6: Full unit suite + commit.** `npm test -- --run` → all green (fix any straggler asserting light default). Commit `feat(canopy): dark-first ThemeContext, retire the 4-palette switcher`.

---

### Task 3: Houseplant MD brand — BrandMark, favicon, page title

**Files:**

- Create: `web/src/components/ui/BrandMark.tsx`, `web/src/components/ui/BrandMark.test.tsx`, `web/public/favicon.svg`
- Modify: `web/index.html`

**Interfaces:**

- Consumes: nothing.
- Produces: `BrandMark({ size?: number; className?: string })` — default size 34, rounded badged-leaf SVG, `role="img"` + `aria-label="Houseplant MD"`. Task 7's Sidebar and Task 8's 404 page consume it.

- [ ] **Step 1: Write the failing test.**

```tsx
// web/src/components/ui/BrandMark.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BrandMark from './BrandMark';

describe('BrandMark', () => {
  it('renders an accessible Houseplant MD mark', () => {
    render(<BrandMark />);
    expect(screen.getByRole('img', { name: 'Houseplant MD' })).toBeInTheDocument();
  });
  it('two instances have no colliding gradient ids', () => {
    const { container } = render(
      <div>
        <BrandMark />
        <BrandMark />
      </div>
    );
    const ids = Array.from(container.querySelectorAll('linearGradient')).map((g) => g.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
```

- [ ] **Step 2: Run to verify failure.** `npx vitest run src/components/ui/BrandMark.test.tsx` → FAIL (module missing).

- [ ] **Step 3: Implement.** `useId()` prefixes the gradient ids so multiple instances never collide:

```tsx
// web/src/components/ui/BrandMark.tsx
import { useId } from 'react';

interface BrandMarkProps {
  size?: number;
  className?: string;
}

/** Houseplant MD badged-leaf mark. The cross is clinic red #DE6B5A on green —
 *  NEVER red-on-white (protected Geneva emblem; spec §2.1). */
export default function BrandMark({ size = 34, className = '' }: BrandMarkProps) {
  const uid = useId();
  const tileId = `${uid}-tile`;
  const leafId = `${uid}-leaf`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={className}
      role="img"
      aria-label="Houseplant MD"
    >
      <defs>
        <linearGradient id={tileId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#10362F" />
          <stop offset="1" stopColor="#0B2B26" />
        </linearGradient>
        <linearGradient id={leafId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#DAF1DE" />
          <stop offset="1" stopColor="#8EB69B" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${tileId})`} />
      <g
        transform="translate(10 8) scale(1.85)"
        fill="none"
        stroke={`url(#${leafId})`}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
        <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
      </g>
      <circle cx="47" cy="47" r="11.5" fill="#DE6B5A" />
      <g fill="#DAF1DE">
        <rect x="44.8" y="40.8" width="4.4" height="12.4" rx="2.2" />
        <rect x="40.8" y="44.8" width="12.4" height="4.4" rx="2.2" />
      </g>
    </svg>
  );
}
```

- [ ] **Step 4: Run tests.** `npx vitest run src/components/ui/BrandMark.test.tsx` → PASS.

- [ ] **Step 5: Favicon + title.** Create `web/public/favicon.svg` with the same SVG as static markup (plain `id="hpmd-tile"`/`id="hpmd-leaf"` are fine in a standalone file; add `xmlns="http://www.w3.org/2000/svg"` to the root element, drop React-only attributes — use `stroke-width`, `stroke-linecap`, `stroke-linejoin`). In `web/index.html`: `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />` and `<title>Houseplant MD</title>` (replaces `web` and `/vite.svg`).

- [ ] **Step 6: Commit.** `feat(canopy): Houseplant MD brand mark + favicon`.

---

### Task 4: Primitives A — Card, Tile, Chip

**Files:**

- Create: `web/src/components/ui/Card.tsx` + `Card.test.tsx`, `web/src/components/ui/Tile.tsx` + `Tile.test.tsx`, `web/src/components/ui/Chip.tsx` + `Chip.test.tsx`

**Interfaces:**

- Consumes: `.canopy-card`, `.canopy-interactive`, `--gt-tile-*`, color utility `text-abyss` (Task 1).
- Produces:
  - `Card({ children, interactive?: boolean, className?, ...divProps })` → gradient surface div.
  - `type TileTone = 'sage' | 'pollen' | 'bloom' | 'orchid'` (exported); `Tile({ tone?: TileTone, size?: 'sm' | 'md', children, className? })` → accent icon square.
  - `Chip({ active?: boolean, children, className?, ...buttonProps })` → filter pill button with `aria-pressed`.

- [ ] **Step 1: Write the failing tests.**

```tsx
// web/src/components/ui/Card.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Card from './Card';

describe('Card', () => {
  it('renders children on the gradient surface class', () => {
    render(<Card data-testid="c">hello</Card>);
    const el = screen.getByTestId('c');
    expect(el).toHaveTextContent('hello');
    expect(el.className).toContain('canopy-card');
    expect(el.className).not.toContain('canopy-interactive');
  });
  it('interactive adds the hover-lift class', () => {
    render(<Card data-testid="c" interactive />);
    expect(screen.getByTestId('c').className).toContain('canopy-interactive');
  });
});
```

```tsx
// web/src/components/ui/Tile.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Tile from './Tile';

describe('Tile', () => {
  it('paints the tone gradient token', () => {
    render(<Tile tone="pollen" data-testid="t" />);
    expect(screen.getByTestId('t')).toHaveStyle({ background: 'var(--gt-tile-pollen)' });
  });
  it('defaults to sage', () => {
    render(<Tile data-testid="t" />);
    expect(screen.getByTestId('t')).toHaveStyle({ background: 'var(--gt-tile-sage)' });
  });
});
```

```tsx
// web/src/components/ui/Chip.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Chip from './Chip';

describe('Chip', () => {
  it('reflects active state via aria-pressed and the CTA class', () => {
    render(<Chip active>All</Chip>);
    const b = screen.getByRole('button', { name: 'All' });
    expect(b).toHaveAttribute('aria-pressed', 'true');
    expect(b.className).toContain('canopy-cta');
  });
  it('inactive chip is pressable', async () => {
    const onClick = vi.fn();
    render(<Chip onClick={onClick}>Care</Chip>);
    const b = screen.getByRole('button', { name: 'Care' });
    expect(b).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(b);
    expect(onClick).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run to verify failures.** `npx vitest run src/components/ui/Card.test.tsx src/components/ui/Tile.test.tsx src/components/ui/Chip.test.tsx` → 3 files FAIL (modules missing).

- [ ] **Step 3: Implement all three.**

```tsx
// web/src/components/ui/Card.tsx
import { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
  /** Hover-lift + border-brighten for clickable cards/rows. */
  interactive?: boolean;
}

export default function Card({
  children,
  interactive = false,
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={`canopy-card rounded-md ${interactive ? 'canopy-interactive' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
```

```tsx
// web/src/components/ui/Tile.tsx
import { HTMLAttributes, ReactNode } from 'react';

export type TileTone = 'sage' | 'pollen' | 'bloom' | 'orchid';

interface TileProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: TileTone;
  size?: 'sm' | 'md';
  children?: ReactNode;
}

const SIZES: Record<'sm' | 'md', string> = {
  sm: 'h-9 w-9 rounded-[11px]',
  md: 'h-[46px] w-[46px] rounded-[14px]',
};

export default function Tile({
  tone = 'sage',
  size = 'md',
  children,
  className = '',
  style,
  ...props
}: TileProps) {
  return (
    <span
      className={`inline-grid flex-none place-items-center text-abyss ${SIZES[size]} ${className}`}
      style={{ background: `var(--gt-tile-${tone})`, ...style }}
      {...props}
    >
      {children}
    </span>
  );
}
```

```tsx
// web/src/components/ui/Chip.tsx
import { ButtonHTMLAttributes, ReactNode } from 'react';

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  children: ReactNode;
}

export default function Chip({ active = false, children, className = '', ...props }: ChipProps) {
  const look = active
    ? 'canopy-cta font-semibold'
    : 'border border-line bg-surface-2/60 text-ink-2 hover:bg-surface-2 hover:text-ink';
  return (
    <button
      type="button"
      aria-pressed={active}
      className={`rounded-pill px-4 py-2 text-[13px] font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary ${look} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: Run tests.** Same vitest command → 3 files PASS.

- [ ] **Step 5: Commit.** `feat(canopy): Card, Tile, Chip primitives`.

---

### Task 5: Primitives B — CountBadge, Avatar, ProgressBar, StatCard

**Files:**

- Create: `web/src/components/ui/CountBadge.tsx` + `CountBadge.test.tsx`, `web/src/components/ui/Avatar.tsx` + `Avatar.test.tsx`, `web/src/components/ui/ProgressBar.tsx` + `ProgressBar.test.tsx`, `web/src/components/ui/StatCard.tsx` + `StatCard.test.tsx`

**Interfaces:**

- Consumes: `Card`, `Tile`, `TileTone` (Task 4); `.canopy-cta` (Task 1).
- Produces:
  - `CountBadge({ count: number, max?: number })` → pill (renders `9+` style when `count > max`, default max 99); renders nothing when `count <= 0`.
  - `Avatar({ src, alt, size?: 'sm' | 'md', presence?: boolean, className? })` → rounded-square img, optional presence dot.
  - `ProgressBar({ value: number, max: number, tone?: TileTone, label: string })` → `role="progressbar"` with aria values.
  - `StatCard({ icon, value, label, sublabel?, tone?, progress?: { value: number; max: number } })` → composed stat card.

- [ ] **Step 1: Write the failing tests.**

```tsx
// web/src/components/ui/CountBadge.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CountBadge from './CountBadge';

describe('CountBadge', () => {
  it('renders the count', () => {
    render(<CountBadge count={4} />);
    expect(screen.getByText('4')).toBeInTheDocument();
  });
  it('caps at max with a plus', () => {
    render(<CountBadge count={120} />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });
  it('renders nothing at zero', () => {
    const { container } = render(<CountBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

```tsx
// web/src/components/ui/Avatar.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Avatar from './Avatar';

describe('Avatar', () => {
  it('renders the image with alt text', () => {
    render(<Avatar src="/avatars/specimen-1.jpg" alt="Iris Delgado" />);
    expect(screen.getByRole('img', { name: 'Iris Delgado' })).toBeInTheDocument();
  });
  it('shows a presence dot when online', () => {
    const { container } = render(<Avatar src="/a.jpg" alt="x" presence />);
    expect(container.querySelector('[data-presence]')).not.toBeNull();
  });
});
```

```tsx
// web/src/components/ui/ProgressBar.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProgressBar from './ProgressBar';

describe('ProgressBar', () => {
  it('exposes progressbar semantics', () => {
    render(<ProgressBar value={34} max={50} label="Progress to Botanist badge" />);
    const bar = screen.getByRole('progressbar', { name: 'Progress to Botanist badge' });
    expect(bar).toHaveAttribute('aria-valuenow', '34');
    expect(bar).toHaveAttribute('aria-valuemax', '50');
  });
  it('clamps overflow to 100%', () => {
    render(<ProgressBar value={80} max={50} label="x" />);
    const fill = screen.getByRole('progressbar', { name: 'x' }).firstElementChild as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });
});
```

```tsx
// web/src/components/ui/StatCard.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Leaf } from 'lucide-react';
import StatCard from './StatCard';

describe('StatCard', () => {
  it('renders value, label, sublabel and progress', () => {
    render(
      <StatCard
        icon={<Leaf aria-hidden="true" />}
        value={34}
        label="Identifications"
        sublabel="16 to your Botanist badge"
        tone="sage"
        progress={{ value: 34, max: 50 }}
      />
    );
    expect(screen.getByText('34')).toBeInTheDocument();
    expect(screen.getByText('Identifications')).toBeInTheDocument();
    expect(screen.getByText('16 to your Botanist badge')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Identifications' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failures.** `npx vitest run src/components/ui/CountBadge.test.tsx src/components/ui/Avatar.test.tsx src/components/ui/ProgressBar.test.tsx src/components/ui/StatCard.test.tsx` → 4 FAIL.

- [ ] **Step 3: Implement.**

```tsx
// web/src/components/ui/CountBadge.tsx
interface CountBadgeProps {
  count: number;
  max?: number;
}

export default function CountBadge({ count, max = 99 }: CountBadgeProps) {
  if (count <= 0) return null;
  return (
    <span className="canopy-cta inline-grid h-5 min-w-5 place-items-center rounded-pill px-1.5 font-mono text-[10.5px] font-semibold">
      {count > max ? `${max}+` : count}
    </span>
  );
}
```

```tsx
// web/src/components/ui/Avatar.tsx
interface AvatarProps {
  src: string;
  alt: string;
  size?: 'sm' | 'md';
  /** Green presence dot (e.g. "expert online"). */
  presence?: boolean;
  className?: string;
}

const SIZES: Record<'sm' | 'md', string> = {
  sm: 'h-[34px] w-[34px] rounded-[11px]',
  md: 'h-[38px] w-[38px] rounded-[12px]',
};

export default function Avatar({
  src,
  alt,
  size = 'md',
  presence = false,
  className = '',
}: AvatarProps) {
  return (
    <span className={`relative inline-block flex-none ${className}`}>
      <img src={src} alt={alt} className={`border border-line-2 object-cover ${SIZES[size]}`} />
      {presence && (
        <span
          data-presence
          aria-hidden="true"
          className="absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-pill border-2 border-surface bg-secondary"
        />
      )}
    </span>
  );
}
```

```tsx
// web/src/components/ui/ProgressBar.tsx
import type { TileTone } from './Tile';

interface ProgressBarProps {
  value: number;
  max: number;
  tone?: TileTone;
  /** Accessible name for the bar. */
  label: string;
}

export default function ProgressBar({ value, max, tone = 'sage', label }: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className="h-[5px] overflow-hidden rounded-pill bg-line"
    >
      <span
        className="block h-full rounded-pill"
        style={{ width: `${pct}%`, background: `var(--gt-tile-${tone})` }}
      />
    </div>
  );
}
```

```tsx
// web/src/components/ui/StatCard.tsx
import type { ReactNode } from 'react';
import Card from './Card';
import Tile, { type TileTone } from './Tile';
import ProgressBar from './ProgressBar';

interface StatCardProps {
  icon: ReactNode;
  value: ReactNode;
  label: string;
  sublabel?: string;
  tone?: TileTone;
  progress?: { value: number; max: number };
}

export default function StatCard({
  icon,
  value,
  label,
  sublabel,
  tone = 'sage',
  progress,
}: StatCardProps) {
  return (
    <Card className="flex flex-col gap-3 p-card">
      <Tile tone={tone} size="sm">
        {icon}
      </Tile>
      <div>
        <div className="font-mono text-[22px] tracking-tight tabular-nums">{value}</div>
        <div className="text-[12.5px] font-medium">{label}</div>
        {sublabel && <div className="text-[11.5px] text-ink-3">{sublabel}</div>}
      </div>
      {progress && (
        <ProgressBar value={progress.value} max={progress.max} tone={tone} label={label} />
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Run tests.** Same command → 4 PASS.

- [ ] **Step 5: Commit.** `feat(canopy): CountBadge, Avatar, ProgressBar, StatCard primitives`.

---

### Task 6: Primitives C — HeroCard, RailModule + Button restyle

**Files:**

- Create: `web/src/components/ui/HeroCard.tsx` + `HeroCard.test.tsx`, `web/src/components/ui/RailModule.tsx` + `RailModule.test.tsx`
- Modify: `web/src/components/ui/Button.tsx:48-58`

**Interfaces:**

- Consumes: `Card` (Task 4), `.canopy-cta` (Task 1).
- Produces:
  - `HeroCard({ eyebrow?, title, description?, actions?, art? })` — `title: ReactNode` renders in an `<h2>` display face; `art: ReactNode` sits right on wide screens.
  - `RailModule({ icon, title, children })` — right-rail section with icon heading.
  - `Button` keeps its exact API (`variant`, `size`, `loading`, `loadingText`) but primary is the mint CTA gradient pill.

- [ ] **Step 1: Write the failing tests.**

```tsx
// web/src/components/ui/HeroCard.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HeroCard from './HeroCard';

describe('HeroCard', () => {
  it('renders eyebrow, heading, description, actions and art', () => {
    render(
      <HeroCard
        eyebrow="Community event"
        title="The bloom watch is on."
        description="Post yours, get it identified."
        actions={<button>Join</button>}
        art={<img src="/x.webp" alt="" data-testid="art" />}
      />
    );
    expect(screen.getByRole('heading', { name: 'The bloom watch is on.' })).toBeInTheDocument();
    expect(screen.getByText('Community event')).toBeInTheDocument();
    expect(screen.getByText('Post yours, get it identified.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Join' })).toBeInTheDocument();
    expect(screen.getByTestId('art')).toBeInTheDocument();
  });
});
```

```tsx
// web/src/components/ui/RailModule.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Users } from 'lucide-react';
import RailModule from './RailModule';

describe('RailModule', () => {
  it('renders a titled section with children', () => {
    render(
      <RailModule icon={<Users aria-hidden="true" />} title="Experts online">
        <p>Iris Delgado</p>
      </RailModule>
    );
    expect(screen.getByRole('heading', { name: 'Experts online' })).toBeInTheDocument();
    expect(screen.getByText('Iris Delgado')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failures.** `npx vitest run src/components/ui/HeroCard.test.tsx src/components/ui/RailModule.test.tsx` → FAIL.

- [ ] **Step 3: Implement.**

```tsx
// web/src/components/ui/HeroCard.tsx
import type { ReactNode } from 'react';
import Card from './Card';

interface HeroCardProps {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  art?: ReactNode;
}

export default function HeroCard({ eyebrow, title, description, actions, art }: HeroCardProps) {
  return (
    <Card className="rounded-lg p-8 md:p-10">
      <div className={`grid items-center gap-8 ${art ? 'md:grid-cols-[1.25fr_0.75fr]' : ''}`}>
        <div className="flex flex-col items-start gap-3.5">
          {eyebrow && (
            <span className="font-mono text-[11px] tracking-[0.18em] text-secondary uppercase">
              {eyebrow}
            </span>
          )}
          <h2 className="gt-h1 text-balance md:text-[38px]">{title}</h2>
          {description && <p className="max-w-[44ch] text-[14.5px] text-ink-2">{description}</p>}
          {actions && <div className="mt-2 flex flex-wrap gap-2.5">{actions}</div>}
        </div>
        {art && <div className="justify-self-start md:justify-self-end">{art}</div>}
      </div>
    </Card>
  );
}
```

```tsx
// web/src/components/ui/RailModule.tsx
import type { ReactNode } from 'react';

interface RailModuleProps {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}

export default function RailModule({ icon, title, children }: RailModuleProps) {
  return (
    <section className="flex flex-col gap-3.5">
      <h4 className="flex items-center gap-2 text-[13px] font-semibold [&>svg]:h-[15px] [&>svg]:w-[15px] [&>svg]:text-secondary">
        {icon}
        {title}
      </h4>
      {children}
    </section>
  );
}
```

- [ ] **Step 4: Restyle Button.** In `Button.tsx` change only the style constants (API untouched):

```tsx
const baseStyles =
  'inline-flex items-center justify-center font-semibold transition-all rounded-pill focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-50 disabled:cursor-not-allowed';

const variants: Record<ButtonVariant, string> = {
  primary: 'canopy-cta shadow-1 hover:-translate-y-px hover:shadow-2',
  secondary: 'bg-surface-2 text-ink border border-line hover:bg-surface-3',
  outline: 'border border-line-2 text-ink hover:bg-surface-2',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink',
};
```

Run `npm test -- --run` — fix any existing Button/ClayButton assertions that reference the removed `rounded-lg`/`bg-clay` classes by updating the expected class strings (behavioral assertions must keep passing untouched).

- [ ] **Step 5: Run tests.** `npx vitest run src/components/ui/HeroCard.test.tsx src/components/ui/RailModule.test.tsx` → PASS; full `npm test -- --run` → green.

- [ ] **Step 6: Commit.** `feat(canopy): HeroCard, RailModule; Button wears the CTA gradient`.

---

### Task 7: AppShell — sidebar, topbar, rail; retire Header/Footer

**Files:**

- Create: `web/src/layouts/AppShell.tsx`, `web/src/layouts/AppShell.test.tsx`, `web/src/components/layout/RailSlot.tsx`
- Modify: `web/src/layouts/RootLayout.tsx`
- Delete: `web/src/components/layout/Header.tsx`, `web/src/components/layout/Header.test.tsx`, `web/src/components/layout/Footer.tsx` (and `Footer.test.tsx` if present)

**Interfaces:**

- Consumes: `BrandMark` (Task 3), `useTheme` (Task 2), existing `NotificationBell`, `UserMenu`, `useAuth`. (`CountBadge` joins the sidebar's Forum item in PR 2 with the unread count — not wired here.)
- Produces: `AppShell({ children })`; `RailSlot({ children })` + exported const `RAIL_CONTAINER_ID = 'app-rail'` — pages render `<RailSlot>…</RailSlot>` anywhere in their tree and the content portals into the shell's right rail (rail column hides itself when empty via the Task 1 `:has()` rule). Later PRs consume `RailSlot`.

- [ ] **Step 1: Implement `RailSlot`.**

```tsx
// web/src/components/layout/RailSlot.tsx
import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

export const RAIL_CONTAINER_ID = 'app-rail';

/** Portals page-provided content into the AppShell right rail.
 *  Mount-gated: the rail div exists only after AppShell commits. */
export default function RailSlot({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setTarget(document.getElementById(RAIL_CONTAINER_ID));
  }, []);
  return target ? createPortal(children, target) : null;
}
```

- [ ] **Step 2: Implement `AppShell`.**

```tsx
// web/src/layouts/AppShell.tsx
import { useState, type ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import {
  Activity,
  BookOpen,
  Home,
  LogIn,
  LogOut,
  Menu,
  MessagesSquare,
  Moon,
  Plus,
  ScanSearch,
  Search,
  Settings as SettingsIcon,
  Sprout,
  Sun,
  X,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import NotificationBell from '../components/layout/NotificationBell';
import UserMenu from '../components/layout/UserMenu';
import { RAIL_CONTAINER_ID } from '../components/layout/RailSlot';
import BrandMark from '../components/ui/BrandMark';

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/identify', label: 'Identify', icon: ScanSearch, end: false },
  { to: '/forum', label: 'Forum', icon: MessagesSquare, end: false },
  { to: '/blog', label: 'Blog', icon: BookOpen, end: false },
  { to: '/my-plants', label: 'My garden', icon: Sprout, end: false },
  { to: '/diagnose', label: 'Diagnose', icon: Activity, end: false },
];

function navClass({ isActive }: { isActive: boolean }) {
  return `flex items-center gap-2.5 rounded-md px-3 py-2 text-[13.5px] font-medium transition-colors ${
    isActive ? 'app-nav-active' : 'text-ink-2 hover:bg-surface-2/70 hover:text-ink'
  }`;
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate} className={navClass}>
          <Icon className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </>
  );
}

function SideFoot({ onNavigate }: { onNavigate?: () => void }) {
  const { isAuthenticated, logout } = useAuth();
  const handleLogout = async () => {
    await logout();
    onNavigate?.();
  };
  return (
    <nav aria-label="Account" className="mt-auto flex flex-col gap-0.5">
      <NavLink to="/settings" onClick={onNavigate} className={navClass}>
        <SettingsIcon className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
        Settings
      </NavLink>
      {isAuthenticated ? (
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 rounded-md px-3 py-2 text-left text-[13.5px] font-medium text-ink-2 transition-colors hover:bg-surface-2/70 hover:text-ink"
        >
          <LogOut className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          Log out
        </button>
      ) : (
        <NavLink to="/login" onClick={onNavigate} className={navClass}>
          <LogIn className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          Log in
        </NavLink>
      )}
    </nav>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { isAuthenticated } = useAuth();
  const { mode, toggleMode } = useTheme();
  const themeLabel = mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  const closeDrawer = () => setDrawerOpen(false);

  const brand = (
    <Link to="/" className="flex items-center gap-2.5 px-2" aria-label="Houseplant MD home">
      <BrandMark size={34} />
      <span className="text-[14.5px] leading-tight font-semibold text-ink">
        Houseplant MD
        <small className="block font-mono text-[9.5px] tracking-[0.14em] text-ink-3 uppercase">
          The plant clinic
        </small>
      </span>
    </Link>
  );

  return (
    <div className="min-h-screen">
      <div className="canopy-ground" aria-hidden="true" />
      <a href="#main-content" className="skip-nav">
        Skip to main content
      </a>
      <div className="app-shell mx-auto flex min-h-screen w-full max-w-[1500px]">
        {/* Sidebar (desktop) */}
        <aside className="sticky top-0 hidden h-screen w-[236px] flex-none flex-col gap-6 border-r border-line bg-surface px-3.5 py-5 md:flex">
          {brand}
          <nav aria-label="Main" className="flex flex-col gap-0.5">
            <NavItems />
          </nav>
          <SideFoot />
        </aside>

        {/* Mobile drawer */}
        {drawerOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div
              className="absolute inset-0 bg-abyss/70"
              onClick={closeDrawer}
              aria-hidden="true"
            />
            <aside className="absolute inset-y-0 left-0 flex w-[260px] flex-col gap-6 border-r border-line bg-surface px-3.5 py-5">
              <div className="flex items-center justify-between">
                {brand}
                <button
                  onClick={closeDrawer}
                  aria-label="Close menu"
                  className="rounded-md p-2 text-ink-3 hover:bg-surface-2"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
              <nav aria-label="Main" className="flex flex-col gap-0.5">
                <NavItems onNavigate={closeDrawer} />
              </nav>
              <SideFoot onNavigate={closeDrawer} />
            </aside>
          </div>
        )}

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col bg-surface">
          <header className="flex items-center gap-3 border-b border-line px-4 py-3.5 md:px-7">
            <button
              onClick={() => setDrawerOpen(true)}
              className="rounded-md p-2 text-ink-3 hover:bg-surface-2 md:hidden"
              aria-label="Open menu"
              aria-expanded={drawerOpen}
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
            <Link
              to="/forum/search"
              className="flex max-w-[430px] flex-1 items-center gap-2.5 rounded-pill border border-line bg-surface-2/70 px-4 py-2.5 text-[13.5px] text-ink-3 transition-colors hover:border-line-2"
            >
              <Search className="h-[15px] w-[15px]" aria-hidden="true" />
              Search plants, posts, people…
            </Link>
            <div className="ml-auto flex items-center gap-2">
              <Link
                to="/forum/new-thread"
                aria-label="New post"
                title="New post"
                className="grid h-[38px] w-[38px] place-items-center rounded-md border border-line bg-surface-2/60 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
              </Link>
              <button
                type="button"
                onClick={toggleMode}
                aria-label={themeLabel}
                aria-pressed={mode === 'dark'}
                title={themeLabel}
                className="grid h-[38px] w-[38px] place-items-center rounded-md border border-line bg-surface-2/60 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
              >
                {mode === 'dark' ? (
                  <Sun className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Moon className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
              {isAuthenticated && <NotificationBell />}
              {isAuthenticated ? (
                <UserMenu />
              ) : (
                <Link
                  to="/signup"
                  className="canopy-cta rounded-pill px-4 py-2 text-[13px] font-semibold"
                >
                  Sign up
                </Link>
              )}
            </div>
          </header>
          <div className="flex min-w-0 flex-1">
            <main id="main-content" className="min-w-0 flex-1">
              {children}
            </main>
            <aside
              id={RAIL_CONTAINER_ID}
              className="app-rail hidden w-[300px] flex-none flex-col gap-7 border-l border-line px-5 py-6 xl:flex"
              aria-label="Related"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
```

Note: the rail `<aside>` is `hidden xl:flex`, and the Task 1 rule `.app-rail:not(:has(*)) { display: none }` additionally hides it on `xl+` whenever no page has filled the portal.

- [ ] **Step 3: Swap RootLayout.**

```tsx
// web/src/layouts/RootLayout.tsx  (full replacement)
import { Outlet } from 'react-router-dom';
import AppShell from './AppShell';

/** All routes render inside the Canopy AppShell (sidebar + topbar + rail). */
export default function RootLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
```

- [ ] **Step 4: Delete the old chrome.** `git rm web/src/components/layout/Header.tsx web/src/components/layout/Header.test.tsx web/src/components/layout/Footer.tsx` (plus `Footer.test.tsx` if it exists). Then `grep -rn "layout/Header\|layout/Footer" src/` — must return nothing.

- [ ] **Step 5: Write the shell test.**

```tsx
// web/src/layouts/AppShell.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import AppShell from './AppShell';
import RailSlot from '../components/layout/RailSlot';

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: false, user: null, logout: vi.fn() }),
}));
vi.mock('../components/layout/NotificationBell', () => ({ default: () => null }));
vi.mock('../components/layout/UserMenu', () => ({ default: () => null }));

const renderShell = (children: React.ReactNode = <p>page body</p>) =>
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AppShell>{children}</AppShell>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('AppShell', () => {
  it('renders brand, nav, search, and the page body', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Houseplant MD home' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /search plants, posts, people/i })).toBeInTheDocument();
    expect(screen.getByText('page body')).toBeInTheDocument();
    expect(document.getElementById('main-content')).not.toBeNull();
  });
  it('shows Sign up and Log in when logged out', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Sign up' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument();
  });
  it('RailSlot portals page content into the rail', () => {
    renderShell(
      <RailSlot>
        <p>rail content</p>
      </RailSlot>
    );
    const rail = document.getElementById('app-rail');
    expect(rail).not.toBeNull();
    expect(rail).toHaveTextContent('rail content');
  });
});
```

- [ ] **Step 6: Run tests.** `npx vitest run src/layouts/AppShell.test.tsx` → PASS; then `npm test -- --run` — update any test that rendered `RootLayout` expecting Header/Footer text (check `src/tests/utils.tsx` consumers; `utils.tsx` itself does not import them and needs no change).

- [ ] **Step 7: Visual smoke.** `npm run dev`, open `http://localhost:5174/` and `/forum` — every page renders inside the shell (old page markup, new colors); sidebar active state follows the route; mobile viewport (375px) shows the hamburger drawer. Fix layout breakage found here before committing.

- [ ] **Step 8: Commit.** `feat(canopy): AppShell replaces Header/Footer — sidebar, topbar, portal rail`.

---

### Task 8: 404 page

**Files:**

- Create: `web/src/pages/NotFoundPage.tsx`, `web/src/pages/NotFoundPage.test.tsx`, `web/public/illustrations/lost-leaf.webp`
- Modify: `web/src/App.tsx` (add lazy import + catch-all route)

**Interfaces:**

- Consumes: `Card`, `Button` (Tasks 4/6); `BrandMark` NOT used here (the shell already shows it).
- Produces: `NotFoundPage` default export; route `path="*"` inside the public `RootLayout` block.

- [ ] **Step 1: Illustration asset.** Copy the session-generated hero (`scratchpad/hero-forum.webp`, the magnifying-glass-on-monstera clay render) to `web/public/illustrations/lost-leaf.webp`. If the scratchpad file no longer exists, regenerate via Runware MCP (`mcp__runware__run`, model `runware:400@1`, 1024×1024 WEBP) with prompt: `cute 3D clay render illustration, oversized magnifying glass examining a single monstera deliciosa leaf, soft rounded playful shapes, smooth matte clay material, gentle studio lighting with soft shadows, deep forest green background color #163832, mint green and sage accent details, centered composition, high quality render` — then download and save to that path.

- [ ] **Step 2: Write the failing test.**

```tsx
// web/src/pages/NotFoundPage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFoundPage from './NotFoundPage';

describe('NotFoundPage', () => {
  it('explains the miss and offers routes home', () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /not in our records/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to home/i })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /browse the forum/i })).toHaveAttribute(
      'href',
      '/forum'
    );
  });
});
```

- [ ] **Step 3: Run to verify failure.** `npx vitest run src/pages/NotFoundPage.test.tsx` → FAIL.

- [ ] **Step 4: Implement.**

```tsx
// web/src/pages/NotFoundPage.tsx
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import PageMeta from '../components/PageMeta';

export default function NotFoundPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <PageMeta title="Page not found — Houseplant MD" />
      <Card className="flex flex-col items-center gap-6 rounded-lg p-10 text-center md:flex-row md:text-left">
        <img
          src="/illustrations/lost-leaf.webp"
          alt=""
          className="h-44 w-44 flex-none rounded-lg border border-line-2 object-cover"
        />
        <div className="flex flex-col items-center gap-3 md:items-start">
          <span className="font-mono text-[11px] tracking-[0.18em] text-secondary uppercase">
            404
          </span>
          <h1 className="gt-h1 text-balance">This leaf isn&apos;t in our records.</h1>
          <p className="text-ink-2">
            The page you&apos;re looking for was moved, renamed, or never sprouted. Try the search
            in the top bar, or head somewhere green:
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-2.5">
            <Link to="/" className="canopy-cta rounded-pill px-5 py-2.5 text-[13.5px] font-semibold">
              Back to home
            </Link>
            <Link
              to="/forum"
              className="rounded-pill border border-line-2 px-5 py-2.5 text-[13.5px] font-semibold text-ink transition-colors hover:bg-surface-2"
            >
              Browse the forum
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Wire the route.** In `App.tsx`: add `const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));` with the other lazy imports, and as the LAST child inside the public `<Route element={<RootLayout />}>` block add `<Route path="*" element={<NotFoundPage />} />`.

- [ ] **Step 6: Run tests + verify live.** `npx vitest run src/pages/NotFoundPage.test.tsx` → PASS. Dev server: `http://localhost:5174/definitely-not-a-page` renders the 404 inside the shell.

- [ ] **Step 7: Commit.** `feat(canopy): 404 page with lost-leaf illustration + catch-all route`.

---

### Task 9: Verification sweep + PR

**Files:**

- Modify: none expected (fixes only).

**Interfaces:**

- Consumes: everything above.
- Produces: pushed branch + open PR for user review.

- [ ] **Step 1: Full gates.** From `web/`: `npm test -- --run` (all green), `npx tsc --noEmit` (clean), `npm run build` (succeeds), `./node_modules/.bin/playwright test e2e/green-thumb-theme.spec.ts --project=chromium` against the dev server (green).
- [ ] **Step 2: Visual sweep.** With `npm run dev`, screenshot (Playwright MCP) each of: `/`, `/identify`, `/forum`, `/blog`, `/login`, `/settings`, `/nope-404` at 1440px and 375px, dark and light. Check: no horizontal scroll, no unreadable text (accents never carry body text), drawer works, reduced-motion (emulate via `page.emulateMedia({ reducedMotion: 'reduce' })`) stops the ground drift.
- [ ] **Step 3: Residue greps.** `grep -rn "data-palette\|setPalette\|PALETTE" src/ e2e/` → zero hits; `grep -rn "PlantID" src/ | grep -v test` → hits only in per-area page copy scheduled for PRs 2–5 (list them in the PR body as known-remaining).
- [ ] **Step 4: Push + PR.** `git push -u origin feat/canopy-foundation`, then `gh pr create` titled `feat(canopy): foundation — tokens, Houseplant MD shell, primitives, 404 (PR 1/5)` with a body summarizing the spec link, the five-PR plan position, the palette-retirement migration note (existing users' stored `gt-mode` is honored; `gt-palette` is cleaned up), and screenshots. End the body with the standard Claude Code attribution line. Do NOT merge — stop for user review per repo convention.

---

## Out of scope for PR 1 (spec §9)

Forum `.wf-*` deletion and forum rebuild (PR 2); blog list/detail + seed command (PR 3); per-page brand-string/copy updates and `App.css` deletion (PRs 4–5); rail content for any page (pages fill `RailSlot` in their own PRs); video hero.

**Deliberate deviation from spec §4:** the sidebar has two states (full ≥`md`, drawer below), not the spec's three (`~1180px` icon-rail intermediate). The icon-rail collapse is deferred to the polish PR — it's pure enhancement and would double the sidebar's test surface in the foundation.
