# Tailwind CSS 4 Patterns

**Stack**: Tailwind CSS 4, mobile-first responsive design

---

## Mobile-First Approach

Apply base styles for mobile, override for larger screens:

```tsx
// ✅ Mobile-first
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

// ❌ Desktop-first with mobile override (harder to maintain)
<div className="grid grid-cols-3 grid-cols-1-mobile gap-4">
```

---

## Minimum Tap Targets

Interactive elements must be at least 44×44px (Apple HIG / general web recommendation):

```tsx
<button className="min-h-[44px] min-w-[44px] px-4 py-2">Action</button>
```

---

## Dark Mode

Use Tailwind's `dark:` variant consistently. All new components must handle dark mode:

```tsx
<div className="bg-white text-gray-900 dark:bg-gray-800 dark:text-gray-100">
```

---

## Design System

Use design tokens from `tailwind.config.ts` rather than arbitrary values where possible:

```tsx
// ✅ Use configured scale
<p className="text-sm text-gray-600">

// ❌ Arbitrary values add maintenance burden
<p className="text-[13px] text-[#666]">
```

## Canopy Token Discipline: Semantic Tokens and Cascade Layers (PR #536/#537)

**Property positions use `--gt-*`, never raw `--canopy-*`.** The raw six-green
ramp is mode-blind — the same literal resolves in both `[data-mode]` states.
Only the `--gt-*` semantic layer re-resolves per mode (dark maps
`--gt-secondary` to sage; light maps it to an AA-darkened forest mix). The
canonical failure: PR #537's flash ring used `var(--canopy-sage)` and was
invisible (~1.4:1) on the light card gradient while looking perfect in dark.

```css
/* BROKEN — identical in both modes, fails contrast in one: */
.canopy-flash .canopy-card { box-shadow: 0 0 0 2px color-mix(in oklab, var(--canopy-sage) 55%, transparent); }
/* CORRECT — re-resolves per mode: */
.canopy-flash .canopy-card { box-shadow: 0 0 0 2px color-mix(in oklab, var(--gt-secondary) 55%, transparent); }
```

Raw ramp vars appear only on the right-hand side of the token-definition
blocks (`:root`, `[data-mode='light']`).

**Rules that must beat a Tailwind utility go unlayered.** With Tailwind 4's
fixed layer order (`theme, base, components, utilities`), anything in
`@layer components` loses to any utility on the same element, regardless of
specificity. Two shipped instances: the empty-rail hide rule losing to
`xl:flex` (PR #536), and the reduced-motion flash ring losing to the accepted
answer's `ring-*` box-shadow (PR #537). Author such rules outside every
`@layer`, with a comment explaining the cascade dependency — see
`.app-rail:not(:has(*))` and the static `.canopy-flash .canopy-card` rule in
`web/src/index.css`.
