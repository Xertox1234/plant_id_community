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
