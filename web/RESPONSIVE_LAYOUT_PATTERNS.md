# Responsive Layout Patterns

**Last Updated**: October 31, 2025
**Context**: Fixes for text wrapping issues on narrow viewports

## Problem: Text Wrapping on Narrow Viewports

When building responsive layouts, text can wrap awkwardly with one word per line on very narrow viewports (e.g., <300px width). This creates a poor user experience.

### Root Cause
- Containers without minimum width constraints can collapse below readable dimensions
- Fixed font sizes don't scale appropriately across viewport sizes
- Max-width constraints without corresponding min-width can cause excessive text wrapping

## Solution: Minimum Width + Responsive Typography

### Pattern 1: Container Minimum Width

**Always set a minimum width on form containers to prevent collapse:**

```jsx
// ❌ BAD - Can collapse to unusable width
<div className="w-full max-w-md">
  <h1>Welcome back</h1>
  <p>Sign in to your PlantID account</p>
</div>

// ✅ GOOD - Prevents collapse below 280px
<div className="w-full max-w-md min-w-[280px]">
  <h1>Welcome back</h1>
  <p>Sign in to your PlantID account</p>
</div>
```

**Key Points:**
- `min-w-[280px]` is the minimum for readable forms on mobile
- Use arbitrary values `[280px]` when standard Tailwind sizes don't fit
- Always pair `max-w-*` with `min-w-[*px]` for form containers

### Pattern 2: Responsive Typography

**Use Tailwind responsive utilities to scale text appropriately:**

```jsx
// ❌ BAD - Fixed size doesn't adapt
<h1 className="text-3xl font-bold">Welcome back</h1>
<p className="text-base">Sign in to your account</p>

// ✅ GOOD - Scales down on mobile, up on larger screens
<h1 className="text-2xl sm:text-3xl font-bold">Welcome back</h1>
<p className="text-sm sm:text-base">Sign in to your account</p>
```

**Breakpoint Strategy:**
- **Mobile (default)**: Smaller text sizes (`text-sm`, `text-2xl`)
- **Tablet+ (`sm:` 640px+)**: Larger text sizes (`text-base`, `text-3xl`)
- Ensures readability at all viewport sizes

### Pattern 3: Space Utilities Over Manual Margins

**Use Tailwind's space utilities for consistent spacing:**

```jsx
// ❌ BAD - Manual margins can be inconsistent
<div className="text-center mb-8">
  <h1 className="mb-4">Welcome back</h1>
  <p className="mt-2">Sign in to your account</p>
</div>

// ✅ GOOD - Consistent spacing via space-y
<div className="text-center mb-8 space-y-2">
  <h1>Welcome back</h1>
  <p>Sign in to your account</p>
</div>
```

**Benefits:**
- `space-y-*` applies consistent vertical spacing between children
- Easier to maintain and adjust globally
- Prevents spacing inconsistencies

### Pattern 4: Avoid Overly Restrictive Max-Width on Text

**Don't constrain text width too much - let it flow naturally:**

```jsx
// ❌ BAD - Too narrow, causes awkward wrapping
<div className="text-center">
  <p className="text-gray-600 max-w-sm mx-auto">
    From AI-powered identification to community knowledge sharing
  </p>
</div>

// ✅ GOOD - Flows naturally within parent container
<div className="text-center">
  <p className="text-gray-600">
    From AI-powered identification to community knowledge sharing
  </p>
</div>
```

**Guidelines:**
- Only use `max-w-*` on text when you need multi-column layouts
- For centered text, let parent container control width
- Trust the parent's `max-w-md` to handle line length

## Complete Example: Auth Page Layout

```jsx
export default function LoginPage() {
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12 bg-gray-50">
      {/* Form container with min-width to prevent collapse */}
      <div className="w-full max-w-md min-w-[280px]">

        {/* Header with responsive typography */}
        <div className="text-center mb-8 space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
            Welcome back
          </h1>
          <p className="text-sm sm:text-base text-gray-600">
            Sign in to your PlantID account
          </p>
        </div>

        {/* Form card */}
        <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-8">
          {/* Form content */}
        </div>
      </div>
    </div>
  )
}
```

## Responsive Breakpoints Reference (Tailwind 4)

| Breakpoint | Min Width | Usage |
|------------|-----------|-------|
| (default)  | 0px       | Mobile-first base styles |
| `sm:`      | 640px     | Tablets and larger |
| `md:`      | 768px     | Desktop |
| `lg:`      | 1024px    | Large desktop |
| `xl:`      | 1280px    | Extra large screens |

## Testing Checklist

When implementing responsive layouts, test at these viewport widths:

- [ ] **280px** - Minimum mobile (iPhone SE in portrait)
- [ ] **375px** - Standard mobile (iPhone 12/13)
- [ ] **640px** - Tablet breakpoint (sm:)
- [ ] **768px** - Desktop breakpoint (md:)
- [ ] **1024px** - Large desktop (lg:)

## Common Mistakes to Avoid

1. **No minimum width** → Text wraps one word per line
2. **Fixed font sizes** → Doesn't scale for mobile
3. **Too many max-width constraints** → Overly restrictive layout
4. **Inconsistent spacing** → Use space-y utilities
5. **Forgetting to test narrow viewports** → Always test <320px width

## Implementation History

- **Oct 31, 2025**: Fixed auth pages (LoginPage, SignupPage) and HomePage
- **Commit**: `ccedb8e` - "fix: improve responsive layout for auth pages and homepage"
- **Files Modified**:
  - `web/src/pages/auth/LoginPage.jsx`
  - `web/src/pages/auth/SignupPage.jsx`
  - `web/src/pages/HomePage.jsx`

## Related Documentation

- [Tailwind CSS Responsive Design](https://tailwindcss.com/docs/responsive-design)
- [Tailwind CSS Min-Width](https://tailwindcss.com/docs/min-width)
- [Tailwind CSS Space](https://tailwindcss.com/docs/space)
