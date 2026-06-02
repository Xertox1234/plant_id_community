# Green Thumb Web Migration (Phase A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-theme and fully migrate the existing `web/` React app to the Green Thumb design system — semantic CSS-variable tokens, a runtime 4-palette × 3-density × light/dark matrix, the full mobile type system — replacing all 1095 raw Tailwind color classes across 39 files, and delete the dead legacy tokens.

**Architecture:** Tailwind 4 `@theme inline` registers `--color-*`/`--spacing-*` tokens that point at `--gt-*` CSS custom properties. The `--gt-*` defaults live in `:root` (loam · light · cozy) and are overridden per `[data-palette]` / `[data-palette][data-mode]` / `[data-density]` selectors on `<html>`. A React `ThemeContext` writes those data-attributes and persists to `localStorage`. Because `@theme inline` makes utilities resolve the var *at the element*, a cascade override on `<html>` re-themes every component live, with no rebuild. Components render correctly with **no provider** because `:root` carries the default palette.

**Tech Stack:** React 19 · TypeScript · Tailwind CSS 4 (CSS-first `@theme`, no config file) · Vite · Vitest + `@testing-library/react` (jsdom) · Playwright (`./e2e`, real browser) · react-router-dom.

**Spec:** `docs/superpowers/specs/2026-06-01-green-thumb-web-design.md` — read it for the full token tables, palette hex values, and the legacy→token mapping.

---

## Critical conventions (read before any task)

- **Test layers (learning C/D):** jsdom does **NOT** cascade CSS custom properties from stylesheets, and Vitest isn't running the Tailwind pipeline. So **never** assert resolved values (`getComputedStyle().getPropertyValue('--gt-*')`, computed colors, computed px) in Vitest — they read empty (a false-green). Vitest asserts **class presence** (`toHaveClass`), **attribute application** (`toHaveAttribute`), DOM presence, props, state, and localStorage. **All value-resolution lives in Playwright.**
- **Tailwind generates only classes it sees in source.** A token utility (`bg-surface`) exists in the compiled CSS only if some scanned `.tsx`/`.css` references it. Task 1 ships `ThemePreviewPage` to guarantee the core token utilities are generated and to give Playwright something to assert against.
- **Read each file before editing it (learning E).** The migration mapping is a guide, not gospel — current components are data-driven (`.map`) and differ from assumptions. Apply the mapping to what's actually there.
- **Import router from `react-router-dom`, never `react-router`** (silent runtime failure).
- **TDD + commit per task (learning G).** Failing test → minimal change → green → commit. Each commit keeps its area shippable. kimi-review runs as a commit gate (`[CRITICAL]` blocks; bypass only with `SKIP_KIMI_REVIEW=1`).
- **All commands run from `web/`** unless stated.

## The legacy → Green Thumb mapping (applied in every migration task)

| Legacy class | → Green Thumb | Boundary note |
|---|---|---|
| `text-gray-900` | `text-ink` | |
| `text-gray-600` / `-700` / `-800` | `text-ink-2` | `-600` is mid-emphasis body, not muted — keep at ink-2 (shipped convention, Tasks 9–12) |
| `text-gray-400` / `-500` | `text-ink-3` | |
| `bg-white` | `bg-surface-2` | cards (mobile cards = bg2) |
| `bg-gray-50` / `-100` | `bg-surface` / `bg-surface-2` | page vs subtle fill — context |
| `bg-gray-700` / `-800` / `-900` (dark fills) | `bg-surface` / `bg-surface-2` | usually on `dark:` → remove the variant |
| `border-gray-200` | `border-line` | |
| `border-gray-300` / `-600` | `border-line-2` | |
| `bg-green-600` / `-700`, `hover:bg-green-700` | `bg-clay` (button) **or** `bg-primary` (brand surface/logo) | CTA→clay, brand accent→primary |
| `ring-green-500`, `border-green-500` / `-600` | `ring-primary` / `border-primary` | focus rings = brand |
| `text-green-600` / `-700` / `-800` | `text-leaf` (badge/label) **or** `text-primary` (link/icon) | |
| `bg-green-50` / `-100` | `bg-primary/10` | tinted brand fill |
| `bg-red-50`, `text-red-*`, `border-red-*`, `bg-red-900` | `bg-error/10` / `text-error` / `border-error` | |
| `bg-yellow-50`, `text-yellow-900`, `amber-*` | `bg-warn/10` / `text-warn` **or** `tertiary` | warning→warn, honey accent→tertiary |
| `text-blue-*`, `bg-blue-*` | `text-sky` / `bg-sky/10` | water/info accent |
| `purple-*` | `berry` | social/community |
| `dark:<color>` variants | **delete** | `--gt-*` flips under `[data-mode]`; `bg-surface` is correct in both |
| screen/card padding `p-4`/`p-6`/`px-4` (where density-responsive) | `p-card` / `px-screen` / `gap-gapy` | structural spacing stays Tailwind numeric |

---

## Branch Setup

- [ ] Confirm you are on the web feature branch (already created):

```bash
git branch --show-current     # expect: feat/green-thumb-web-phase-a
cd web && npm install         # ensure deps present
```

---

## Task 1: Token foundation (colors · density · radius · shadows) + ThemePreviewPage

Establishes the runtime theming layer and proves it with a real-browser test. Front-loads the hardest problem (learning J).

**Files:**

- Modify: `web/src/index.css` (replace the dead `@theme` block entirely)
- Create: `web/src/pages/debug/ThemePreviewPage.tsx`
- Modify: `web/src/App.tsx` (add DEV-only `/debug/theme` route)
- Create: `web/e2e/green-thumb-theme.spec.ts`

- [ ] **Step 1 — Write the failing Playwright test**

```ts
// web/e2e/green-thumb-theme.spec.ts
import { test, expect } from '@playwright/test';

// Set theme data-attributes on <html> exactly as ThemeContext will (Task 3).
async function setTheme(page, attrs: { palette?: string; mode?: string; density?: string }) {
  await page.evaluate((a) => {
    const el = document.documentElement;
    if (a.palette) el.dataset.palette = a.palette; else delete el.dataset.palette;
    if (a.mode) el.dataset.mode = a.mode; else delete el.dataset.mode;
    if (a.density) el.dataset.density = a.density; else delete el.dataset.density;
  }, attrs);
}

test.describe('Green Thumb runtime tokens', () => {
  test.beforeEach(async ({ page }) => { await page.goto('/debug/theme'); });

  test('default (loam light) surface resolves', async ({ page }) => {
    await setTheme(page, {});
    await expect(page.getByTestId('probe-surface')).toHaveCSS('background-color', 'rgb(246, 240, 226)');
  });

  test('palette switch changes resolved color', async ({ page }) => {
    await setTheme(page, { palette: 'forest' });
    await expect(page.getByTestId('probe-surface')).toHaveCSS('background-color', 'rgb(15, 26, 18)');
    await setTheme(page, { palette: 'loam', mode: 'dark' });
    await expect(page.getByTestId('probe-surface')).toHaveCSS('background-color', 'rgb(18, 16, 10)');
  });

  test('forest+dark stays forest (cascade-bug guard)', async ({ page }) => {
    await setTheme(page, { palette: 'forest', mode: 'dark' });
    // MUST be forest #0F1A12, NOT loam-dark #12100A
    await expect(page.getByTestId('probe-surface')).toHaveCSS('background-color', 'rgb(15, 26, 18)');
  });

  test('density changes resolved padding (discriminating wiring)', async ({ page }) => {
    await setTheme(page, { density: 'compact' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '12px'); // ≠ cozy 16, ≠ comfortable 18
    await setTheme(page, { density: 'comfortable' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '18px');
  });

  test('alpha modifier resolves on a themed token (not transparent, not solid)', async ({ page }) => {
    await setTheme(page, {});
    const bg = await page.getByTestId('probe-alpha').evaluate(
      (el) => getComputedStyle(el).backgroundColor
    );
    // bg-clay/10 must compile to a partial color-mix of var(--gt-clay):
    expect(bg).not.toBe('rgba(0, 0, 0, 0)'); // modifier ignored → fully transparent
    expect(bg).not.toBe('rgb(201, 84, 42)'); // modifier dropped → solid clay #C9542A
  });
});
```

- [ ] **Step 2 — Run it to confirm it fails**

Run: `npm run test:e2e -- green-thumb-theme`
Expected: FAIL — route `/debug/theme` 404s / `probe-surface` not found.

- [ ] **Step 3 — Replace `web/src/index.css`**

```css
@import 'tailwindcss';

/* ───────── Green Thumb semantic vars · :root = loam · light · cozy ───────── */
:root {
  --gt-surface:#F6F0E2; --gt-surface-2:#ECE3CC; --gt-surface-3:#DDD0AE;
  --gt-ink:#1F1A12; --gt-ink-2:#4A3F2C; --gt-ink-3:#7C6E55;
  --gt-line:#D4C5A0; --gt-line-2:#BCA97E;
  --gt-primary:#4A7034; --gt-on-primary:#F6F0E2;
  --gt-secondary:#97B86A; --gt-tertiary:#E0B445;
  --gt-clay:#C9542A; --gt-on-clay:#FFF8EA;
  --gt-leaf:#C2D680; --gt-berry:#C45577; --gt-sky:#6FA0AA;
  --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
  --gt-pad-card:16px; --gt-pad-screen:16px; --gt-gap:12px;
  --gt-shadow-1:0 1px 0 rgba(27,34,24,.04), 0 2px 6px rgba(27,34,24,.05);
  --gt-shadow-2:0 2px 0 rgba(27,34,24,.05), 0 8px 22px rgba(27,34,24,.08);
  --gt-shadow-3:0 4px 0 rgba(27,34,24,.06), 0 18px 40px rgba(27,34,24,.14);
}

/* ───────── palette LIGHT blocks (forest is dark-only: this is its only set) ───────── */
[data-palette="garden"] {
  --gt-surface:#F4F1E4; --gt-surface-2:#ECE7D2; --gt-surface-3:#DFD9BD;
  --gt-ink:#102015; --gt-ink-2:#2E4233; --gt-ink-3:#5C6E5A;
  --gt-line:#D2CCAE; --gt-line-2:#B8B391;
  --gt-primary:#2F6B3A; --gt-on-primary:#F4F1E4;
  --gt-secondary:#7FA66B; --gt-tertiary:#E5B84B;
  --gt-clay:#D86B2C; --gt-on-clay:#FFF8EA;
  --gt-leaf:#A8CC6E; --gt-berry:#B8466A; --gt-sky:#6FA0AA;
  --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
}
[data-palette="forest"] {
  --gt-surface:#0F1A12; --gt-surface-2:#16241A; --gt-surface-3:#1F3024;
  --gt-ink:#E8F0D8; --gt-ink-2:#C2D2AC; --gt-ink-3:#87987C;
  --gt-line:#2A3A2F; --gt-line-2:#3D5142;
  --gt-primary:#B8DC7C; --gt-on-primary:#0F1A12;
  --gt-secondary:#A8CC6E; --gt-tertiary:#F0CC68;
  --gt-clay:#F0935A; --gt-on-clay:#0F1A12;
  --gt-leaf:#C8E198; --gt-berry:#E090A8; --gt-sky:#94BFC8;
  --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
}
[data-palette="heritage"] {
  --gt-surface:#F0EBDB; --gt-surface-2:#E4DBC2; --gt-surface-3:#D3C9AC;
  --gt-ink:#1A1F10; --gt-ink-2:#3A4128; --gt-ink-3:#756E50;
  --gt-line:#CFC4A2; --gt-line-2:#B8AC85;
  --gt-primary:#3D5A22; --gt-on-primary:#F0EBDB;
  --gt-secondary:#768B4E; --gt-tertiary:#C99B3A;
  --gt-clay:#B0481E; --gt-on-clay:#FFF8EA;
  --gt-leaf:#A4B86E; --gt-berry:#B8466A; --gt-sky:#6FA0AA;
  --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
}

/* ───────── dark COLOR blocks — palette-qualified (0,2,0) so they outrank the
   palette base block. A BARE [data-mode="dark"] color block would tie with
   [data-palette="forest"] and clobber it (cascade bug). Forest needs none. ───────── */
[data-palette="loam"][data-mode="dark"] {
  --gt-surface:#12100A; --gt-surface-2:#1C1810; --gt-surface-3:#272218;
  --gt-ink:#F2EBD8; --gt-ink-2:#D4C8A4; --gt-ink-3:#8A7E60;
  --gt-line:#2E2818; --gt-line-2:#423A26;
  --gt-primary:#B8D680; --gt-on-primary:#12100A;
  --gt-secondary:#A3C26C; --gt-tertiary:#E8C76B;
  --gt-clay:#E58A52; --gt-on-clay:#12100A;
  --gt-leaf:#CCE090; --gt-berry:#D286A2; --gt-sky:#9CC0CA;
  --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
}
[data-palette="garden"][data-mode="dark"],
[data-palette="heritage"][data-mode="dark"] {   /* heritage dark = garden dark (_gardenDark) */
  --gt-surface:#0E140F; --gt-surface-2:#161E18; --gt-surface-3:#1F2A21;
  --gt-ink:#EEF4E2; --gt-ink-2:#C8D5B8; --gt-ink-3:#8A9A7E;
  --gt-line:#2A3628; --gt-line-2:#3A4A37;
  --gt-primary:#A8CC6E; --gt-on-primary:#14180F;
  --gt-secondary:#9BBE82; --gt-tertiary:#E8C76B;
  --gt-clay:#E58A52; --gt-on-clay:#14180F;
  --gt-leaf:#BEDC8C; --gt-berry:#D286A2; --gt-sky:#9CC0CA;
  --gt-ok:#3F5D3F; --gt-warn:#C4A570; --gt-error:#B5451C;
}

/* dark SHADOWS — palette-independent → one bare block, ONLY shadow vars (no colors) */
[data-mode="dark"] {
  --gt-shadow-1:0 1px 0 rgba(0,0,0,.04), 0 2px 6px rgba(0,0,0,.05);
  --gt-shadow-2:0 2px 0 rgba(0,0,0,.05), 0 8px 22px rgba(0,0,0,.08);
  --gt-shadow-3:0 4px 0 rgba(0,0,0,.06), 0 18px 40px rgba(0,0,0,.14);
}

/* ───────── density blocks (cozy is the :root default) ───────── */
[data-density="comfortable"] { --gt-pad-card:18px; --gt-pad-screen:18px; --gt-gap:14px; }
[data-density="compact"]     { --gt-pad-card:12px; --gt-pad-screen:14px; --gt-gap:10px; }

/* ───────── register tokens → utilities resolve the var AT THE ELEMENT ───────── */
@theme inline {
  --color-surface: var(--gt-surface);
  --color-surface-2: var(--gt-surface-2);
  --color-surface-3: var(--gt-surface-3);
  --color-ink: var(--gt-ink);
  --color-ink-2: var(--gt-ink-2);
  --color-ink-3: var(--gt-ink-3);
  --color-line: var(--gt-line);
  --color-line-2: var(--gt-line-2);
  --color-primary: var(--gt-primary);
  --color-on-primary: var(--gt-on-primary);
  --color-secondary: var(--gt-secondary);
  --color-tertiary: var(--gt-tertiary);
  --color-clay: var(--gt-clay);
  --color-on-clay: var(--gt-on-clay);
  --color-leaf: var(--gt-leaf);
  --color-berry: var(--gt-berry);
  --color-sky: var(--gt-sky);
  --color-ok: var(--gt-ok);
  --color-warn: var(--gt-warn);
  --color-error: var(--gt-error);
  --spacing-card: var(--gt-pad-card);
  --spacing-screen: var(--gt-pad-screen);
  --spacing-gapy: var(--gt-gap);
  --shadow-1: var(--gt-shadow-1);
  --shadow-2: var(--gt-shadow-2);
  --shadow-3: var(--gt-shadow-3);
}

/* ───────── radius scale (constant across palettes → static; overrides Tailwind defaults) ───────── */
@theme {
  --radius-xs:6px; --radius-sm:10px; --radius-md:16px;
  --radius-lg:22px; --radius-xl:28px; --radius-pill:999px;
}

/* ───────── dark variant keyed to OUR toggle, not OS prefers-color-scheme ───────── */
@custom-variant dark (&:where([data-mode="dark"], [data-mode="dark"] *));

/* ───────── skip-nav (migrated off the hardcoded green) ───────── */
.skip-nav {
  position: absolute; top: -40px; left: 0;
  background: var(--gt-primary); color: var(--gt-on-primary);
  padding: 8px 16px; text-decoration: none; font-weight: 600;
  border-radius: 0 0 8px 0; z-index: 100; transition: top 0.2s;
}
.skip-nav:focus { top: 0; }
```

- [ ] **Step 4 — Create `web/src/pages/debug/ThemePreviewPage.tsx`** (minimal probe; expanded to 24 combos in Task 12)

```tsx
// Dev-only probe: exercises the core token utilities so Tailwind generates
// them, and gives Playwright stable testids to assert resolution against.
export default function ThemePreviewPage() {
  return (
    <div className="bg-surface text-ink p-screen min-h-screen">
      <div data-testid="probe-surface" className="bg-surface p-card rounded-md shadow-2">surface</div>
      <div data-testid="probe-surface-2" className="bg-surface-2">surface-2</div>
      <div data-testid="probe-clay" className="bg-clay text-on-clay">clay</div>
      <div data-testid="probe-primary" className="bg-primary text-on-primary">primary</div>
      <div data-testid="probe-secondary" className="bg-secondary">secondary</div>
      <div data-testid="probe-tertiary" className="bg-tertiary">tertiary</div>
      <p data-testid="probe-ink" className="text-ink">ink</p>
      <p data-testid="probe-ink-2" className="text-ink-2">ink-2</p>
      <p data-testid="probe-ink-3" className="text-ink-3">ink-3</p>
      <p data-testid="probe-leaf" className="text-leaf">leaf</p>
      <p data-testid="probe-berry" className="text-berry">berry</p>
      <p data-testid="probe-sky" className="text-sky">sky</p>
      <p data-testid="probe-error" className="text-error">error</p>
      <div data-testid="probe-line" className="border border-line">line</div>
      <div data-testid="probe-pad" className="p-card">pad</div>
      <div data-testid="probe-alpha" className="bg-clay/10">alpha</div>
    </div>
  );
}
```

- [ ] **Step 5 — Add the DEV-only route to `web/src/App.tsx`**

Add the lazy import near the other lazy imports:

```tsx
const ThemePreviewPage = lazy(() => import('./pages/debug/ThemePreviewPage'));
```

Add inside `<Routes>` (top level, no layout needed):

```tsx
{import.meta.env.DEV && (
  <Route path="/debug/theme" element={<ThemePreviewPage />} />
)}
```

- [ ] **Step 6 — Run the Playwright test to verify it passes**

Run: `npm run test:e2e -- green-thumb-theme`
Expected: PASS — all four tests green (default, palette switch, forest+dark guard, density).

- [ ] **Step 7 — Verify the build still type-checks**

Run: `npm run type-check`
Expected: zero errors.

- [ ] **Step 8 — Commit**

```bash
git add src/index.css src/pages/debug/ThemePreviewPage.tsx src/App.tsx e2e/green-thumb-theme.spec.ts
git commit -m "feat(web): Green Thumb token foundation + runtime theming + debug probe"
```

---

## Task 2: Typography foundation (Bricolage Grotesque · Geist · Geist Mono)

**Files:**

- Create: `web/public/fonts/` woff2 files
- Modify: `web/src/index.css` (add `@font-face`, font families, body font, heading classes)
- Create: `web/src/pages/debug/ThemePreviewPage.tsx` test additions are in Task 12; here add a font probe
- Modify: `web/e2e/green-thumb-theme.spec.ts` (font-resolution test)

- [ ] **Step 1 — Add the font files**

Download OFL woff2 builds and place them exactly here:

```text
web/public/fonts/BricolageGrotesque-SemiBold.woff2   # github.com/ateliertriay/bricolage (OFL)
web/public/fonts/Geist-Regular.woff2                 # github.com/vercel/geist-font (OFL)
web/public/fonts/Geist-Medium.woff2
web/public/fonts/Geist-SemiBold.woff2
web/public/fonts/GeistMono-Regular.woff2
```

- [ ] **Step 2 — Write the failing font test (append to the Playwright spec)**

```ts
// append inside web/e2e/green-thumb-theme.spec.ts
test('display headings use Bricolage Grotesque', async ({ page }) => {
  await page.goto('/debug/theme');
  const family = await page.getByTestId('probe-display').evaluate(
    (el) => getComputedStyle(el).fontFamily
  );
  expect(family).toContain('Bricolage Grotesque');
});
```

- [ ] **Step 3 — Run it to confirm it fails**

Run: `npm run test:e2e -- green-thumb-theme`
Expected: FAIL — `probe-display` not found / family does not contain "Bricolage Grotesque".

- [ ] **Step 4 — Append font setup to `web/src/index.css`** (after the `@import`, before `:root`)

```css
@font-face { font-family:"Bricolage Grotesque"; src:url("/fonts/BricolageGrotesque-SemiBold.woff2") format("woff2"); font-weight:600; font-style:normal; font-display:swap; }
@font-face { font-family:"Geist"; src:url("/fonts/Geist-Regular.woff2")  format("woff2"); font-weight:400; font-display:swap; }
@font-face { font-family:"Geist"; src:url("/fonts/Geist-Medium.woff2")   format("woff2"); font-weight:500; font-display:swap; }
@font-face { font-family:"Geist"; src:url("/fonts/Geist-SemiBold.woff2") format("woff2"); font-weight:600; font-display:swap; }
@font-face { font-family:"Geist Mono"; src:url("/fonts/GeistMono-Regular.woff2") format("woff2"); font-weight:400; font-display:swap; }
```

Add to the existing `@theme inline { … }` block:

```css
  --font-display: "Bricolage Grotesque", Georgia, serif;
  --font-sans: "Geist", system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;
```

Append heading classes and base body font at the end of the file:

```css
@layer base { body { font-family: var(--font-sans); } }

@layer components {
  .gt-display { font-family: var(--font-display); font-style: italic; font-weight: 600; font-size: 2rem;     line-height: 1.02; letter-spacing: -0.02em; }
  .gt-h1      { font-family: var(--font-display); font-style: italic; font-weight: 600; font-size: 1.75rem;  line-height: 1.1;  letter-spacing: -0.02em; }
  .gt-h2      { font-family: var(--font-display); font-style: italic; font-weight: 600; font-size: 1.375rem; line-height: 1.15; letter-spacing: -0.02em; }
  .gt-h3      { font-family: var(--font-display); font-style: italic; font-weight: 600; font-size: 1.125rem; line-height: 1.2;  letter-spacing: -0.02em; }
}
```

- [ ] **Step 5 — Add a `probe-display` to `ThemePreviewPage.tsx`**

Add inside the page:

```tsx
      <h2 data-testid="probe-display" className="gt-display">Green Thumb</h2>
      <span data-testid="probe-mono" className="font-mono italic">Monstera deliciosa</span>
```

- [ ] **Step 6 — Run the test to verify it passes**

Run: `npm run test:e2e -- green-thumb-theme`
Expected: PASS — font family contains "Bricolage Grotesque".

- [ ] **Step 7 — Commit**

```bash
git add public/fonts src/index.css src/pages/debug/ThemePreviewPage.tsx e2e/green-thumb-theme.spec.ts
git commit -m "feat(web): Green Thumb type system — Bricolage, Geist, Geist Mono"
```

---

## Task 3: ThemeContext + localStorage

**Files:**

- Create: `web/src/contexts/ThemeContext.tsx`
- Create: `web/src/contexts/ThemeContext.test.tsx`
- Modify: `web/src/main.tsx` (wrap app in `ThemeProvider`)

- [ ] **Step 1 — Write the failing test**

```tsx
// web/src/contexts/ThemeContext.test.tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, useTheme } from './ThemeContext';

function Harness() {
  const { palette, density, mode, setPalette, setDensity, toggleMode } = useTheme();
  return (
    <div>
      <span data-testid="state">{`${palette}/${density}/${mode}`}</span>
      <button onClick={() => setPalette('forest')}>forest</button>
      <button onClick={() => setDensity('compact')}>compact</button>
      <button onClick={toggleMode}>toggle</button>
    </div>
  );
}
const renderHarness = () => render(<ThemeProvider><Harness /></ThemeProvider>);

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.palette;
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
  });

  it('applies defaults to <html> on mount', () => {
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('loam/cozy/light');
    expect(document.documentElement).toHaveAttribute('data-palette', 'loam');
    expect(document.documentElement).toHaveAttribute('data-density', 'cozy');
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });

  it('setPalette updates attribute and persists', async () => {
    renderHarness();
    await userEvent.click(screen.getByText('forest'));
    expect(document.documentElement).toHaveAttribute('data-palette', 'forest');
    expect(localStorage.getItem('gt-palette')).toBe('forest');
  });

  it('setDensity updates attribute and persists', async () => {
    renderHarness();
    await userEvent.click(screen.getByText('compact'));
    expect(document.documentElement).toHaveAttribute('data-density', 'compact');
    expect(localStorage.getItem('gt-density')).toBe('compact');
  });

  it('toggleMode flips mode and persists', async () => {
    renderHarness();
    await userEvent.click(screen.getByText('toggle'));
    expect(document.documentElement).toHaveAttribute('data-mode', 'dark');
    expect(localStorage.getItem('gt-mode')).toBe('dark');
  });

  it('reads persisted values on mount', () => {
    localStorage.setItem('gt-palette', 'garden');
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('garden/cozy/light');
    expect(document.documentElement).toHaveAttribute('data-palette', 'garden');
  });
});
```

- [ ] **Step 2 — Run it to confirm it fails**

Run: `npm run test -- ThemeContext`
Expected: FAIL — `./ThemeContext` module not found.

- [ ] **Step 3 — Implement `web/src/contexts/ThemeContext.tsx`**

```tsx
import {
  createContext, useContext, useState, useEffect, useCallback, type ReactNode,
} from 'react';

export type Palette = 'loam' | 'garden' | 'forest' | 'heritage';
export type Density = 'comfortable' | 'cozy' | 'compact';
export type Mode = 'light' | 'dark';

interface ThemeContextValue {
  palette: Palette; density: Density; mode: Mode;
  setPalette: (p: Palette) => void;
  setDensity: (d: Density) => void;
  setMode: (m: Mode) => void;
  toggleMode: () => void;
}

const PALETTES: readonly Palette[] = ['loam', 'garden', 'forest', 'heritage'];
const DENSITIES: readonly Density[] = ['comfortable', 'cozy', 'compact'];
const MODES: readonly Mode[] = ['light', 'dark'];
const KEYS = { palette: 'gt-palette', density: 'gt-density', mode: 'gt-mode' } as const;

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function read<T extends string>(key: string, fallback: T, valid: readonly T[]): T {
  try {
    const v = localStorage.getItem(key);
    return v && (valid as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}
function persist(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* ignore quota/denied */ }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [palette, setPaletteState] = useState<Palette>(() => read(KEYS.palette, 'loam', PALETTES));
  const [density, setDensityState] = useState<Density>(() => read(KEYS.density, 'cozy', DENSITIES));
  const [mode, setModeState] = useState<Mode>(() => read(KEYS.mode, 'light', MODES));

  useEffect(() => { document.documentElement.dataset.palette = palette; }, [palette]);
  useEffect(() => { document.documentElement.dataset.density = density; }, [density]);
  useEffect(() => { document.documentElement.dataset.mode = mode; }, [mode]);

  const setPalette = useCallback((p: Palette) => { setPaletteState(p); persist(KEYS.palette, p); }, []);
  const setDensity = useCallback((d: Density) => { setDensityState(d); persist(KEYS.density, d); }, []);
  const setMode = useCallback((m: Mode) => { setModeState(m); persist(KEYS.mode, m); }, []);
  const toggleMode = useCallback(() => setMode(mode === 'light' ? 'dark' : 'light'), [mode, setMode]);

  return (
    <ThemeContext.Provider value={{ palette, density, mode, setPalette, setDensity, setMode, toggleMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

// Only theme-control UI (Settings, theme toggle) uses this. Everything else
// renders correctly from the :root default with no provider (learning A).
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
```

- [ ] **Step 4 — Run the test to verify it passes**

Run: `npm run test -- ThemeContext`
Expected: PASS — all five cases.

- [ ] **Step 5 — Wrap the app in `web/src/main.tsx`**

Import and wrap the root render (outermost provider, above the router):

```tsx
import { ThemeProvider } from './contexts/ThemeContext';
// …
<ThemeProvider>
  {/* existing <App /> / <RouterProvider> tree */}
</ThemeProvider>
```

- [ ] **Step 6 — Verify type-check + the full unit suite**

Run: `npm run type-check && npm run test`
Expected: zero type errors; all tests pass.

- [ ] **Step 7 — Commit**

```bash
git add src/contexts/ThemeContext.tsx src/contexts/ThemeContext.test.tsx src/main.tsx
git commit -m "feat(web): ThemeContext — palette/density/mode + localStorage"
```

---

## Task 4: Primitives — ClayButton, GrainOverlay, Eyebrow + migrate `ui/`

**Files:**

- Create: `web/src/components/ui/ClayButton.tsx` + `ClayButton.test.tsx`
- Create: `web/src/components/ui/GrainOverlay.tsx` + `GrainOverlay.test.tsx`
- Create: `web/src/components/ui/Eyebrow.tsx` + `Eyebrow.test.tsx`
- Modify: `web/src/components/ui/{Button,Input,LoadingSpinner}.tsx`

- [ ] **Step 1 — Write the failing ClayButton test**

```tsx
// web/src/components/ui/ClayButton.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ClayButton from './ClayButton';

describe('ClayButton', () => {
  it('renders the label', () => {
    render(<ClayButton label="Get Started" />);
    expect(screen.getByText('Get Started')).toBeInTheDocument();
  });
  it('primary variant uses clay background', () => {
    render(<ClayButton label="X" />);
    expect(screen.getByRole('button')).toHaveClass('bg-clay');
  });
  it('secondary variant uses primary background', () => {
    render(<ClayButton label="X" variant="secondary" />);
    expect(screen.getByRole('button')).toHaveClass('bg-primary');
  });
  it('outline variant is transparent with a primary border', () => {
    render(<ClayButton label="X" variant="outline" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveClass('bg-transparent');
    expect(btn).toHaveClass('border-primary');
  });
  it('disabled is non-interactive and dropped of shadow/clay', () => {
    render(<ClayButton label="X" disabled />);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn).not.toHaveClass('shadow-2');
    expect(btn).not.toHaveClass('bg-clay');
  });
  it('fullWidth spans the container', () => {
    render(<ClayButton label="X" fullWidth />);
    expect(screen.getByRole('button')).toHaveClass('w-full');
  });
  it('renders a provided icon', () => {
    render(<ClayButton label="X" icon={<svg data-testid="ic" />} />);
    expect(screen.getByTestId('ic')).toBeInTheDocument();
  });
  it('loading shows a spinner, hides the label, sets aria-busy', () => {
    render(<ClayButton label="X" loading />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
    expect(screen.queryByText('X')).not.toBeInTheDocument();
    expect(btn.querySelector('.animate-spin')).toBeTruthy();
  });
});
```

- [ ] **Step 2 — Run it to confirm it fails**

Run: `npm run test -- ClayButton`
Expected: FAIL — `./ClayButton` not found.

- [ ] **Step 3 — Implement `web/src/components/ui/ClayButton.tsx`**

```tsx
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ClayVariant = 'primary' | 'secondary' | 'outline';
type ClaySize = 'sm' | 'md' | 'lg';

export interface ClayButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon?: ReactNode;
  fullWidth?: boolean;
  size?: ClaySize;
  variant?: ClayVariant;
  loading?: boolean;
}

const VARIANT: Record<ClayVariant, string> = {
  primary: 'bg-clay text-on-clay shadow-2',
  secondary: 'bg-primary text-on-primary shadow-2',
  outline: 'bg-transparent border border-primary text-primary',
};
const SIZE: Record<ClaySize, string> = {
  sm: 'px-4 py-2 text-sm',
  md: 'px-6 py-3 text-base',
  lg: 'px-8 py-4 text-base',
};

export default function ClayButton({
  label, icon, fullWidth = false, size = 'lg', variant = 'primary',
  loading = false, disabled, className = '', ...rest
}: ClayButtonProps) {
  const isDisabled = disabled || loading;
  const classes = [
    'inline-flex items-center justify-center gap-2 rounded-pill font-semibold tracking-[0.25px]',
    'min-h-[44px] transition-colors',
    fullWidth && 'w-full',
    isDisabled ? 'bg-surface-3 text-ink-3/40 cursor-not-allowed' : VARIANT[variant],
    SIZE[size],
    className,
  ].filter(Boolean).join(' ');

  return (
    <button {...rest} disabled={isDisabled} aria-busy={loading || undefined} className={classes}>
      {loading ? (
        <span aria-hidden="true" className="h-5 w-5 animate-spin rounded-full border-2 border-current/40 border-t-current" />
      ) : (
        <>
          {icon && <span aria-hidden="true">{icon}</span>}
          <span>{label}</span>
        </>
      )}
    </button>
  );
}
```

- [ ] **Step 4 — Run ClayButton tests to verify they pass**

Run: `npm run test -- ClayButton`
Expected: PASS — all eight cases.

- [ ] **Step 5 — Write the failing GrainOverlay + Eyebrow tests**

```tsx
// web/src/components/ui/GrainOverlay.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GrainOverlay from './GrainOverlay';

describe('GrainOverlay', () => {
  it('renders children', () => {
    render(<GrainOverlay><p>content</p></GrainOverlay>);
    expect(screen.getByText('content')).toBeInTheDocument();
  });
  it('renders a non-interactive, aria-hidden overlay', () => {
    render(<GrainOverlay><p>x</p></GrainOverlay>);
    const overlay = screen.getByTestId('grain-overlay');
    expect(overlay).toHaveAttribute('aria-hidden', 'true');
    expect(overlay).toHaveClass('pointer-events-none');
  });
});
```

```tsx
// web/src/components/ui/Eyebrow.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Eyebrow from './Eyebrow';

describe('Eyebrow', () => {
  it('renders uppercase muted text', () => {
    render(<Eyebrow>Plant Identification</Eyebrow>);
    const el = screen.getByText('Plant Identification');
    expect(el).toHaveClass('uppercase');
    expect(el).toHaveClass('text-ink-3');
  });
});
```

- [ ] **Step 6 — Run them to confirm they fail**

Run: `npm run test -- GrainOverlay Eyebrow`
Expected: FAIL — modules not found.

- [ ] **Step 7 — Implement GrainOverlay and Eyebrow**

```tsx
// web/src/components/ui/GrainOverlay.tsx
import type { ReactNode } from 'react';

const NOISE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E";

export default function GrainOverlay({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <div
        data-testid="grain-overlay"
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 opacity-[0.04] mix-blend-multiply dark:mix-blend-screen"
        style={{ backgroundImage: `url("${NOISE}")` }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
```

```tsx
// web/src/components/ui/Eyebrow.tsx
import type { ReactNode } from 'react';

export default function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p className={`font-sans font-semibold uppercase text-ink-3 text-[11px] leading-[1.4] tracking-[0.66px] ${className}`}>
      {children}
    </p>
  );
}
```

- [ ] **Step 8 — Migrate the three existing `ui/` components**

Read each, then apply the mapping. The known fix in `LoadingSpinner.tsx` (it references dead tokens today):

```tsx
// BEFORE: <div className="w-12 h-12 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
// AFTER:
<div className="w-12 h-12 border-4 border-line border-t-primary rounded-full animate-spin" />
```

Apply the mapping table to `Button.tsx` and `Input.tsx` (gray→ink/line, green→clay/primary, red→error, `rounded-*` values now come from the new scale automatically).

- [ ] **Step 9 — Run the full primitive + ui suite**

Run: `npm run test -- ClayButton GrainOverlay Eyebrow Button Input LoadingSpinner`
Expected: PASS (existing Button/Input/LoadingSpinner tests, if any, stay green).

- [ ] **Step 10 — Commit**

```bash
git add src/components/ui
git commit -m "feat(web): ClayButton, GrainOverlay, Eyebrow + migrate ui/ primitives"
```

---

## Task 5: Settings UI — palette / density / dark controls

The current `SettingsPage` is a "Coming Soon" placeholder. Read it first, then replace its body with working controls wired to `ThemeContext`.

**Files:**

- Modify: `web/src/pages/SettingsPage.tsx`
- Create: `web/src/pages/SettingsPage.test.tsx`

- [ ] **Step 1 — Write the failing test**

```tsx
// web/src/pages/SettingsPage.test.tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import SettingsPage from './SettingsPage';

const renderPage = () =>
  render(
    <ThemeProvider><BrowserRouter><SettingsPage /></BrowserRouter></ThemeProvider>
  );

describe('SettingsPage theme controls', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.palette;
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
  });

  it('renders four palette swatches', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /loam/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /garden/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /forest/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /heritage/i })).toBeInTheDocument();
  });

  it('clicking a swatch applies the palette to <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /forest/i }));
    expect(document.documentElement).toHaveAttribute('data-palette', 'forest');
  });

  it('changing density applies it to <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /compact/i }));
    expect(document.documentElement).toHaveAttribute('data-density', 'compact');
  });

  it('dark toggle flips mode on <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    expect(document.documentElement).toHaveAttribute('data-mode', 'dark');
  });
});
```

- [ ] **Step 2 — Run it to confirm it fails**

Run: `npm run test -- SettingsPage`
Expected: FAIL — controls not present (placeholder page).

- [ ] **Step 3 — Replace the SettingsPage body with theme controls**

Use these building blocks (keep the existing page shell/heading; replace the "Coming Soon" sections). `useTheme` provides state + setters.

```tsx
import { useTheme, type Palette, type Density } from '../contexts/ThemeContext';
import Eyebrow from '../components/ui/Eyebrow';

const PALETTE_SWATCH: Record<Palette, string> = {
  loam: '#C9542A', garden: '#D86B2C', forest: '#F0935A', heritage: '#B0481E',
};
const DENSITIES: Density[] = ['comfortable', 'cozy', 'compact'];

function ThemeControls() {
  const { palette, density, mode, setPalette, setDensity, toggleMode } = useTheme();
  return (
    <div className="space-y-8 p-screen">
      <section>
        <Eyebrow>Appearance</Eyebrow>
        <button
          onClick={toggleMode}
          className="mt-2 rounded-pill border border-line px-4 py-2 text-ink"
        >
          {mode === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
        </button>
      </section>

      <section>
        <Eyebrow>Palette</Eyebrow>
        <div className="mt-2 flex flex-wrap gap-2">
          {(Object.keys(PALETTE_SWATCH) as Palette[]).map((p) => (
            <button
              key={p}
              onClick={() => setPalette(p)}
              className={`flex items-center gap-2 rounded-sm px-3 py-2 capitalize ${
                palette === p ? 'border-2 border-primary font-bold' : 'border border-line'
              }`}
            >
              <span className="h-4 w-4 rounded-full" style={{ background: PALETTE_SWATCH[p] }} />
              {p}
            </button>
          ))}
        </div>
      </section>

      <section>
        <Eyebrow>Density</Eyebrow>
        <div className="mt-2 inline-flex rounded-pill border border-line p-1">
          {DENSITIES.map((d) => (
            <button
              key={d}
              onClick={() => setDensity(d)}
              className={`rounded-pill px-4 py-1 capitalize ${
                density === d ? 'bg-primary text-on-primary' : 'text-ink-3'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
```

Render `<ThemeControls />` inside the page. (`capitalize` makes the lowercase palette/density keys match the case-insensitive `/loam/i` test queries.)

- [ ] **Step 4 — Run the test to verify it passes**

Run: `npm run test -- SettingsPage`
Expected: PASS — all four cases.

- [ ] **Step 5 — Commit**

```bash
git add src/pages/SettingsPage.tsx src/pages/SettingsPage.test.tsx
git commit -m "feat(web): Settings page — live palette/density/dark controls"
```

---

## Migration tasks (6–11) — shared procedure

Each migration task follows the **same five steps**. The discriminating gate is a per-area grep that must reach **zero** legacy color classes (red→green), backed by the area's existing render tests staying green (regression safety, learning E). *(Verified at plan time: no `toMatchSnapshot`/`toMatchInlineSnapshot` tests exist in `web/src`, and no existing test asserts a legacy color class — so class-name swaps cannot break existing tests.)*

> **Per-area grep gate** (substitute the area's directories for `<DIRS>`):
>
> ```bash
> grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" <DIRS> --include="*.tsx" | grep -v ".test.tsx"
> ```

---

## Task 6: Layout (Header, Footer, UserMenu, layouts)

**Files:** `web/src/components/layout/{Header,Footer,UserMenu}.tsx`, `web/src/layouts/{RootLayout,ProtectedLayout}.tsx`. Existing test: `web/src/components/layout/Header.test.tsx`.

- [ ] **Step 1 — Run the grep gate to see the "red" baseline**

Run: `grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src/components/layout src/layouts --include="*.tsx" | grep -v ".test.tsx"`
Expected: prints N matches (red).

- [ ] **Step 2 — Read each file, then apply the mapping**

Worked example (`Header.tsx` brand link, illustrative — match what's actually there):

```tsx
// BEFORE: <Link className="text-xl font-bold text-green-600 hover:text-green-700">PlantID</Link>
// AFTER:
<Link className="gt-h3 text-primary hover:text-primary/80">PlantID</Link>
```

Apply across all five files: `gray-*→ink/line`, `green-*→primary` (brand) / `clay` (CTAs), `red-*→error`, remove `dark:` color variants, page background `bg-white/bg-gray-50 → bg-surface`.

- [ ] **Step 3 — Re-run the grep gate**

Run the Step 1 command. Expected: **zero** matches (green).

- [ ] **Step 4 — Run the layout tests (regression)**

Run: `npm run test -- Header`
Expected: PASS (existing tests unaffected by class swaps).

- [ ] **Step 5 — Commit**

```bash
git add src/components/layout src/layouts
git commit -m "refactor(web): migrate layout to Green Thumb tokens"
```

---

## Task 7: HomePage (+ GrainOverlay, Eyebrow, ClayButton)

HomePage is the one Splash/Home-style landing → it gains primitives, so it has real new-component assertions in addition to the grep gate.

**Files:** Modify `web/src/pages/HomePage.tsx`; create `web/src/pages/HomePage.test.tsx`.

- [ ] **Step 1 — Write the failing test**

```tsx
// web/src/pages/HomePage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import HomePage from './HomePage';

const renderHome = () => render(<BrowserRouter><HomePage /></BrowserRouter>);

describe('HomePage', () => {
  it('wraps content in a GrainOverlay', () => {
    renderHome();
    expect(screen.getByTestId('grain-overlay')).toBeInTheDocument();
  });
  it('renders a ClayButton CTA (pill, clay)', () => {
    renderHome();
    // the primary CTA button — match by its label text
    const cta = screen.getByRole('button', { name: /get started|identify/i });
    expect(cta).toHaveClass('rounded-pill');
  });
});
```

- [ ] **Step 2 — Run it to confirm it fails**

Run: `npm run test -- HomePage`
Expected: FAIL — no grain overlay / CTA not a ClayButton.

- [ ] **Step 3 — Migrate HomePage**

Read the current `HomePage.tsx` (it is data-driven — a `.map` over feature cards). Then:

- Import `GrainOverlay`, `Eyebrow`, `ClayButton`.
- Wrap the page's scroll content in `<GrainOverlay>…</GrainOverlay>`.
- Add an `<Eyebrow>` above the hero title; make the title use `gt-display`.
- Replace the hero CTA (`<Link className="bg-green-600 …">`) with `<ClayButton label="Get Started" fullWidth … />` (keep its navigation via `onClick`/wrapping `Link`).
- Apply the color mapping to the feature cards (`bg-white→bg-surface-2`, `text-gray-*→ink`, accent icons → `text-primary`/`text-sky`/`text-berry`/`text-tertiary`, card radius `rounded-lg`/shadow `shadow-1`, padding `p-card`).

- [ ] **Step 4 — Run the test + grep gate**

Run: `npm run test -- HomePage`
Then: `grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src/pages/HomePage.tsx`
Expected: tests PASS; grep zero.

- [ ] **Step 5 — Commit**

```bash
git add src/pages/HomePage.tsx src/pages/HomePage.test.tsx
git commit -m "feat(web): migrate HomePage to Green Thumb — GrainOverlay, Eyebrow, ClayButton"
```

---

## Task 8: Auth (Login, Signup)

**Files:** `web/src/pages/auth/{LoginPage,SignupPage}.tsx`.

- [ ] **Step 1 — Grep gate baseline**

Run: `grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src/pages/auth --include="*.tsx"`
Expected: N matches.

- [ ] **Step 2 — Read each, apply the mapping**

Swap form fields to use `bg-surface-2`/`border-line`/focus `ring-primary`; submit buttons → `ClayButton` (or `bg-clay`); error text → `text-error`; `bg-red-50 → bg-error/10`.

- [ ] **Step 3 — Re-run grep gate** → zero.

- [ ] **Step 4 — Regression**

Run: `npm run test`
Expected: PASS (no auth-page unit tests break).

- [ ] **Step 5 — Commit**

```bash
git add src/pages/auth
git commit -m "refactor(web): migrate auth pages to Green Thumb tokens"
```

---

## Task 9: Blog

**Files:** `web/src/components/{BlogCard,StreamFieldRenderer}.tsx`, `web/src/pages/{BlogListPage,BlogDetailPage,BlogPage,BlogPreview}.tsx`. Existing tests: `BlogCard.test.tsx`, `StreamFieldRenderer.test.tsx`.

- [ ] **Step 1 — Grep gate baseline**

Run: `grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src/components/BlogCard.tsx src/components/StreamFieldRenderer.tsx src/pages/BlogListPage.tsx src/pages/BlogDetailPage.tsx src/pages/BlogPage.tsx src/pages/BlogPreview.tsx`
Expected: N matches.

- [ ] **Step 2 — Read each, apply the mapping**

Card surfaces `bg-white→bg-surface-2`, `shadow→shadow-1`, headings `gt-h2`/`gt-h3`, body `text-ink-2`, links `text-primary`. StreamFieldRenderer prose colors → ink scale.

- [ ] **Step 3 — Re-run grep gate** → zero.

- [ ] **Step 4 — Regression**

Run: `npm run test -- BlogCard StreamFieldRenderer`
Expected: PASS.

- [ ] **Step 5 — Commit**

```bash
git add src/components/BlogCard.tsx src/components/StreamFieldRenderer.tsx src/pages/BlogListPage.tsx src/pages/BlogDetailPage.tsx src/pages/BlogPage.tsx src/pages/BlogPreview.tsx
git commit -m "refactor(web): migrate blog to Green Thumb tokens"
```

---

## Task 10: Forum (strip `dark:` variants here)

**Files:** `web/src/components/forum/{CategoryCard,ImageUploadWidget,PostCard,ThreadCard,TipTapEditor}.tsx`, `web/src/pages/forum/{CategoryListPage,SearchPage,ThreadDetailPage,ThreadListPage}.tsx`, **and the top-level `web/src/pages/ForumPage.tsx`**. Existing tests: `CategoryCard/ImageUploadWidget/PostCard/ThreadCard/TipTapEditor.test.tsx`, `CategoryListPage/SearchPage/ThreadDetailPage/ThreadListPage.test.tsx`. **The forum component/page files carry the `dark:` color variants — remove them; the `--gt-*` vars handle dark.**

- [ ] **Step 1 — Grep gate baseline (note the `dark:` count)**

Run: `grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src/components/forum src/pages/forum src/pages/ForumPage.tsx --include="*.tsx" | grep -v ".test.tsx"`
Expected: N matches (incl. `dark:` variants).

- [ ] **Step 2 — Read each, apply the mapping + delete `dark:` color variants**

Worked example (`ThreadCard.tsx`):

```tsx
// BEFORE: className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-200 dark:border-gray-700"
// AFTER:  (no dark: needed — vars flip under [data-mode])
className="bg-surface-2 text-ink border-line"
```

Apply to all nine files: tag/badge colors (`bg-green-100 text-green-800 → bg-primary/10 text-primary`, etc.), upvote/reply icons → `text-ink-3`, category accents → `text-sky`/`text-berry`/`text-tertiary`.

- [ ] **Step 3 — Re-run grep gate** → zero (including no `dark:` matches).

- [ ] **Step 4 — Regression (forum has the richest unit suite)**

Run: `npm run test -- forum`
Expected: PASS — all forum component + page tests stay green.

- [ ] **Step 5 — Commit**

```bash
git add src/components/forum src/pages/forum src/pages/ForumPage.tsx
git commit -m "refactor(web): migrate forum to Green Thumb tokens, drop dark: variants"
```

---

## Task 11: Diagnosis + Plant ID + Profile + ErrorBoundary

**Files:** `web/src/components/diagnosis/{DiagnosisCard,ReminderManager,SaveDiagnosisModal,StreamFieldEditor}.tsx`, `web/src/components/PlantIdentification/{FileUpload,IdentificationResults}.tsx`, `web/src/pages/diagnosis/{DiagnosisDetailPage,DiagnosisListPage}.tsx`, `web/src/pages/{IdentifyPage,ProfilePage}.tsx`, `web/src/components/ErrorBoundary.tsx`.

- [ ] **Step 1 — Grep gate baseline**

Run: `grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src/components/diagnosis src/components/PlantIdentification src/pages/diagnosis src/pages/IdentifyPage.tsx src/pages/ProfilePage.tsx src/components/ErrorBoundary.tsx --include="*.tsx" | grep -v ".test.tsx"`
Expected: N matches.

- [ ] **Step 2 — Read each, apply the mapping**

Identify/upload buttons → `ClayButton`; result confidence/"identified" badges → `bg-leaf`/`text-leaf`; care-instruction icons → `text-sky`/`text-ok`; filter/sort controls → `border-line`/`bg-surface-2`; error/empty states → `text-error`/`text-ink-3`. ProfilePage stat cards → `bg-surface-2`/`shadow-1`, headings `gt-h2`.

- [ ] **Step 3 — Re-run grep gate** → zero.

- [ ] **Step 4 — Regression + full unit suite**

Run: `npm run test`
Expected: PASS (whole Vitest suite).

- [ ] **Step 5 — Commit**

```bash
git add src/components/diagnosis src/components/PlantIdentification src/pages/diagnosis src/pages/IdentifyPage.tsx src/pages/ProfilePage.tsx src/components/ErrorBoundary.tsx
git commit -m "refactor(web): migrate diagnosis/plant-id/profile to Green Thumb tokens"
```

---

## Task 12: Debug preview page — all 24 combinations

Expand `ThemePreviewPage` into the matrix QA surface.

**Files:** Modify `web/src/pages/debug/ThemePreviewPage.tsx`; create `web/src/pages/debug/ThemePreviewPage.test.tsx`.

- [ ] **Step 1 — Write the failing test**

```tsx
// web/src/pages/debug/ThemePreviewPage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ThemePreviewPage from './ThemePreviewPage';

describe('ThemePreviewPage', () => {
  it('renders all 24 palette × density × mode combinations', () => {
    render(<ThemePreviewPage />);
    expect(screen.getAllByTestId('combo-card')).toHaveLength(24); // 4 × 3 × 2
  });
});
```

- [ ] **Step 2 — Run it to confirm it fails**

Run: `npm run test -- ThemePreviewPage`
Expected: FAIL — finds 0 (or 1) `combo-card`, not 24.

- [ ] **Step 3 — Implement the 24-combo grid** (each card a local data-attribute scope; keep one probe set per card so Playwright can read any cell)

```tsx
const PALETTES = ['loam', 'garden', 'forest', 'heritage'] as const;
const DENSITIES = ['comfortable', 'cozy', 'compact'] as const;
const MODES = ['light', 'dark'] as const;

function Swatches() {
  return (
    <div className="space-y-1">
      <h3 className="gt-h3">Aa Bricolage</h3>
      <div className="flex gap-1">
        <span className="rounded-sm bg-clay px-2 text-on-clay">clay</span>
        <span className="rounded-sm bg-primary px-2 text-on-primary">moss</span>
        <span className="rounded-sm bg-tertiary px-2">honey</span>
      </div>
      <div className="flex gap-1 text-xs">
        <span className="text-leaf">leaf</span><span className="text-berry">berry</span>
        <span className="text-sky">sky</span><span className="text-error">error</span>
      </div>
      <p className="font-mono italic text-ink-2">Monstera deliciosa</p>
      <p className="text-ink-3">muted ink-3</p>
    </div>
  );
}

// The probe section has NO local data-attributes, so it inherits palette/
// density/mode from <html>. KEEP its testids — green-thumb-theme.spec.ts
// (Tasks 1–2) drives <html> and asserts against these. Removing them breaks e2e.
function HtmlProbe() {
  return (
    <div className="bg-surface text-ink p-screen">
      <div data-testid="probe-surface" className="bg-surface p-card rounded-md shadow-2">surface</div>
      <div data-testid="probe-surface-2" className="bg-surface-2">surface-2</div>
      <div data-testid="probe-clay" className="bg-clay text-on-clay">clay</div>
      <div data-testid="probe-primary" className="bg-primary text-on-primary">primary</div>
      <p data-testid="probe-ink" className="text-ink">ink</p>
      <p data-testid="probe-ink-2" className="text-ink-2">ink-2</p>
      <p data-testid="probe-ink-3" className="text-ink-3">ink-3</p>
      <p data-testid="probe-leaf" className="text-leaf">leaf</p>
      <p data-testid="probe-berry" className="text-berry">berry</p>
      <p data-testid="probe-sky" className="text-sky">sky</p>
      <p data-testid="probe-error" className="text-error">error</p>
      <div data-testid="probe-line" className="border border-line">line</div>
      <div data-testid="probe-pad" className="p-card">pad</div>
      <div data-testid="probe-alpha" className="bg-clay/10">alpha</div>
      <h2 data-testid="probe-display" className="gt-display">Green Thumb</h2>
      <span data-testid="probe-mono" className="font-mono italic">Monstera deliciosa</span>
    </div>
  );
}

export default function ThemePreviewPage() {
  return (
    <div className="min-h-screen bg-neutral-100 p-4">
      {/* <html>-driven probe (testids for the Playwright theme spec) */}
      <HtmlProbe />
      {/* all 24 self-scoped combinations */}
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {PALETTES.flatMap((palette) =>
          DENSITIES.flatMap((density) =>
            MODES.map((mode) => (
              <div
                key={`${palette}-${density}-${mode}`}
                data-testid="combo-card"
                data-palette={palette}
                data-density={density}
                data-mode={mode}
                className="bg-surface text-ink p-card rounded-md shadow-2 border border-line"
              >
                <p className="text-[10px] uppercase tracking-wide text-ink-3">{palette}/{density}/{mode}</p>
                <Swatches />
              </div>
            ))
          )
        )}
      </div>
    </div>
  );
}
```

> The outer `bg-neutral-100` is an intentional, debug-only default-Tailwind class so the page chrome is visible regardless of theme — exclude `src/pages/debug/` from the Task 13 grep gate (it is dev-only and never shipped).

- [ ] **Step 4 — Run the test to verify it passes**

Run: `npm run test -- ThemePreviewPage`
Expected: PASS — 24 cards.

- [ ] **Step 5 — Commit**

```bash
git add src/pages/debug/ThemePreviewPage.tsx src/pages/debug/ThemePreviewPage.test.tsx
git commit -m "feat(web): debug theme preview — all 24 combinations"
```

---

## Task 13: Delete legacy — zero-reference gate

**Files:** Modify `web/src/index.css` (confirm no orphan tokens — they were removed in Task 1); any straggler component.

- [ ] **Step 1 — Run the global zero-reference grep (excluding the dev-only debug page)**

```bash
grep -rEn "(bg|text|border|ring|from|to|via)-(green|emerald|gray|slate|zinc|neutral|blue|red|amber|yellow|purple|indigo|teal|orange|rose|pink)-[0-9]+|dark:(bg|text|border)-" src --include="*.tsx" \
  | grep -v ".test.tsx" | grep -v "src/pages/debug/"
```

Expected: **zero** matches. If any remain, migrate them with the mapping table and re-run.

- [ ] **Step 2 — Confirm no orphan `@theme` tokens remain in `index.css`**

```bash
grep -nE "\-\-color-(primary-hover|primary-light|secondary|success|warning|info)|\-\-font-(xs|sm|base|lg|xl|2xl|3xl):" src/index.css
```

Expected: **zero** matches (removed in Task 1).

- [ ] **Step 3 — Run the full unit suite + type-check + lint**

Run: `npm run type-check && npm run lint && npm run test`
Expected: all green.

- [ ] **Step 4 — Commit (only if Step 1 found stragglers to remove)**

```bash
git add -A && git commit -m "chore(web): remove last legacy color classes — Green Thumb migration complete"
```

---

## Task 14: Final verification

- [ ] **Step 1 — Full unit suite**

Run: `npm run test`
Expected: all pass.

- [ ] **Step 2 — Type-check + lint**

Run: `npm run type-check && npm run lint`
Expected: zero errors, clean.

- [ ] **Step 3 — Playwright (theme + existing golden-path specs)**

Run: `npm run test:e2e`
Expected: `green-thumb-theme` green (color resolution, forest+dark guard, density, fonts); existing `forum-golden-path` / `forum-responsive` still pass.

- [ ] **Step 4 — Production build**

Run: `npm run build`
Expected: succeeds (type-check passes, no missing tokens).

- [ ] **Step 5 — Manual QA (the matrix can't be fully asserted in tests)**

```bash
npm run dev   # http://localhost:5174
```

Verify by hand:

- `/debug/theme` shows 24 correctly-styled combinations.
- Settings → switch palette/density/dark; the whole app re-themes **live** without reload; reload preserves the choice (localStorage).
- GrainOverlay visible on Home; absent elsewhere.
- Forest + dark renders forest colors (not loam-dark) on real pages.
- Headings render in Bricolage italic; scientific names in Geist Mono.

- [ ] **Step 6 — Open the PR**

```bash
git push -u origin feat/green-thumb-web-phase-a
gh pr create --title "Green Thumb web migration (Phase A)" --body "Re-themes and fully migrates the web app to the Green Thumb design system: runtime 4×3×light/dark token matrix, full mobile type system, 1095 legacy color classes migrated, legacy tokens deleted. Spec + plan under docs/superpowers/."
```

Review the diff, then enable auto-merge: `gh pr merge --auto --squash --delete-branch`.

---

## Success Criteria (from the spec)

1. The Task 13 zero-reference grep returns **zero** matches (excluding `src/pages/debug/`).
2. Old `@theme` block fully replaced; no orphan `--color-*`/`--font-*` tokens.
3. `npm run type-check` zero errors; `npm run lint` clean.
4. `npm run test` all pass (incl. ThemeContext attribute wiring, ClayButton, Settings, 24-combo count).
5. `npm run test:e2e -- green-thumb-theme` passes (color resolution + forest+dark guard + density + fonts).
6. `/debug/theme` shows all 24 combinations correctly styled.
7. Settings switches palette/density/dark live and persists across reload.
8. GrainOverlay on Home only.
9. No `dark:` color variants remain.
