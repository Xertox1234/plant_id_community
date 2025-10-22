# Styling Guide

Complete guide to styling conventions and Tailwind CSS usage in the Plant ID Community web frontend.

## Overview

The web frontend uses Tailwind CSS 4 for all styling. No custom CSS files, CSS modules, or CSS-in-JS libraries are used.

## Tailwind CSS 4

### Configuration

**File:** `tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',  // Main brand color
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
      },
    },
  },
  plugins: [],
}
```

### Import

**File:** `src/index.css`

```css
/* Tailwind CSS imports only */
@import "tailwindcss";
```

**No custom CSS:** All styling is done via Tailwind utility classes.

## Design System

### Color Palette

#### Primary Colors (Green)

Used for branding, CTAs, and positive actions.

| Name | Hex | Usage |
|------|-----|-------|
| `primary-50` | `#f0fdf4` | Light backgrounds, hovers |
| `primary-100` | `#dcfce7` | Subtle backgrounds |
| `primary-600` | `#16a34a` | **Primary brand color** |
| `primary-700` | `#15803d` | Hover states |
| `primary-900` | `#14532d` | Dark text |

**Usage:**
```javascript
className="bg-primary-600 text-white"        // Button primary
className="hover:bg-primary-700"             // Button hover
className="bg-gradient-to-br from-primary-50 to-emerald-50"  // Hero background
```

#### Semantic Colors

| Purpose | Tailwind Class | Hex | Usage |
|---------|---------------|-----|-------|
| Success | `text-green-600` | `#16a34a` | Success messages |
| Error | `text-red-600` | `#dc2626` | Error messages |
| Warning | `text-yellow-600` | `#ca8a04` | Warnings |
| Info | `text-blue-600` | `#2563eb` | Information |

#### Grayscale

| Name | Usage |
|------|-------|
| `gray-50` | Light backgrounds |
| `gray-100` | Borders, subtle dividers |
| `gray-300` | Borders, disabled states |
| `gray-600` | Secondary text |
| `gray-900` | Primary text |
| `white` | Cards, containers |
| `black` | Overlays (with opacity) |

### Typography

#### Font Stack

**Default (System Fonts):**
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif
```

**No custom fonts** - Uses OS-native fonts for best performance.

#### Text Sizes

| Class | Size | Line Height | Usage |
|-------|------|-------------|-------|
| `text-xs` | 12px | 16px | Labels, captions |
| `text-sm` | 14px | 20px | Secondary text |
| `text-base` | 16px | 24px | Body text |
| `text-lg` | 18px | 28px | Large body |
| `text-xl` | 20px | 28px | Small headings |
| `text-2xl` | 24px | 32px | Section headings |
| `text-3xl` | 30px | 36px | Page headings |
| `text-4xl` | 36px | 40px | Large headings |
| `text-5xl` | 48px | 1 | Hero text |

**Usage:**
```javascript
<h1 className="text-5xl font-bold">Hero Heading</h1>
<h2 className="text-3xl font-semibold">Section Heading</h2>
<p className="text-base text-gray-600">Body text</p>
<span className="text-sm text-gray-500">Caption</span>
```

#### Font Weights

| Class | Weight | Usage |
|-------|--------|-------|
| `font-normal` | 400 | Body text |
| `font-medium` | 500 | Emphasized text |
| `font-semibold` | 600 | Subheadings |
| `font-bold` | 700 | Headings |

### Spacing

Tailwind uses a consistent 4px-based scale.

| Class | Size | Usage |
|-------|------|-------|
| `p-1` | 4px | Tight padding |
| `p-2` | 8px | Small padding |
| `p-4` | 16px | Standard padding |
| `p-6` | 24px | Card padding |
| `p-8` | 32px | Section padding |
| `p-12` | 48px | Large section padding |
| `p-16` | 64px | Extra large padding |

**Margin** uses same scale with `m-*` prefix.
**Gap** for flexbox/grid uses same scale with `gap-*`.

**Common Spacing Patterns:**
```javascript
// Card
className="p-6"              // 24px padding

// Container
className="px-4 py-8"        // 16px horizontal, 32px vertical

// Section
className="my-12"            // 48px vertical margin

// Grid gap
className="gap-6"            // 24px gap between items
```

### Borders & Radius

#### Border Width

```javascript
className="border"           // 1px border
className="border-2"         // 2px border
className="border-4"         // 4px border
```

#### Border Radius

| Class | Radius | Usage |
|-------|--------|-------|
| `rounded` | 4px | Subtle rounding |
| `rounded-md` | 6px | Medium rounding |
| `rounded-lg` | 8px | Buttons, inputs |
| `rounded-xl` | 12px | Cards, containers |
| `rounded-2xl` | 16px | Large cards |
| `rounded-full` | 9999px | Circles, pills |

**Common Patterns:**
```javascript
className="rounded-xl"       // Cards
className="rounded-lg"       // Buttons, inputs
className="rounded-full"     // Avatar, badge
```

### Shadows

| Class | Usage |
|-------|-------|
| `shadow-sm` | Subtle elevation |
| `shadow` | Default shadow |
| `shadow-md` | Medium elevation |
| `shadow-lg` | Cards, modals |
| `shadow-xl` | Large elevation |
| `shadow-2xl` | Maximum elevation |

**Drop Shadow:**
```javascript
className="drop-shadow-md"   // For images, icons
```

## Component Patterns

### Buttons

#### Primary Button

```javascript
<button className="
  bg-primary-600 text-white
  px-6 py-3
  rounded-lg
  font-semibold
  hover:bg-primary-700
  active:bg-primary-800
  disabled:bg-gray-400 disabled:cursor-not-allowed
  transition-colors duration-200
  flex items-center gap-2
">
  <Upload className="w-5 h-5" />
  Upload Image
</button>
```

#### Secondary Button

```javascript
<button className="
  border-2 border-primary-600 text-primary-600
  px-6 py-3
  rounded-lg
  font-semibold
  hover:bg-primary-50
  active:bg-primary-100
  transition-colors duration-200
">
  Cancel
</button>
```

#### Ghost Button

```javascript
<button className="
  text-primary-600
  px-4 py-2
  rounded-lg
  hover:bg-primary-50
  transition-colors duration-200
">
  Learn More
</button>
```

### Cards

```javascript
<div className="
  bg-white
  rounded-xl
  shadow-lg
  p-6
  border border-gray-100
  hover:shadow-xl
  transition-shadow duration-200
">
  <h3 className="text-xl font-semibold mb-2">Card Title</h3>
  <p className="text-gray-600">Card content</p>
</div>
```

### Forms

#### Input

```javascript
<input
  type="text"
  className="
    w-full
    px-4 py-2
    border-2 border-gray-300
    rounded-lg
    focus:border-primary-600 focus:outline-none
    disabled:bg-gray-100 disabled:cursor-not-allowed
    transition-colors duration-200
  "
  placeholder="Enter text..."
/>
```

#### File Input (Custom)

```javascript
<label className="
  block w-full
  border-2 border-dashed border-gray-300
  rounded-xl
  p-8
  text-center
  cursor-pointer
  hover:border-primary-600 hover:bg-primary-50
  transition-all duration-200
">
  <input type="file" className="hidden" />
  <Upload className="w-12 h-12 mx-auto mb-2 text-gray-400" />
  <p className="text-gray-600">Click or drag file to upload</p>
</label>
```

### Alerts

#### Success

```javascript
<div className="
  bg-green-50
  border-l-4 border-green-500
  p-4
  rounded-lg
  flex items-start gap-3
">
  <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
  <div>
    <h4 className="font-semibold text-green-900">Success!</h4>
    <p className="text-green-700">Plant identified successfully.</p>
  </div>
</div>
```

#### Error

```javascript
<div className="
  bg-red-50
  border-l-4 border-red-500
  p-4
  rounded-lg
  flex items-start gap-3
">
  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
  <div>
    <h4 className="font-semibold text-red-900">Error</h4>
    <p className="text-red-700">Failed to identify plant.</p>
  </div>
</div>
```

#### Warning

```javascript
<div className="
  bg-yellow-50
  border-l-4 border-yellow-400
  p-4
  rounded-lg
">
  <p className="text-yellow-700">Health issue detected</p>
</div>
```

### Loading States

#### Spinner

```javascript
<div className="flex items-center justify-center p-8">
  <div className="
    w-12 h-12
    border-4 border-primary-200
    border-t-primary-600
    rounded-full
    animate-spin
  "></div>
</div>
```

#### Skeleton

```javascript
<div className="animate-pulse">
  <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
  <div className="h-4 bg-gray-200 rounded w-1/2"></div>
</div>
```

### Badges

```javascript
<span className="
  inline-flex items-center
  px-3 py-1
  rounded-full
  text-sm font-medium
  bg-green-100 text-green-800
">
  High Confidence
</span>
```

**Color Variants:**
```javascript
// Success
className="bg-green-100 text-green-800"

// Warning
className="bg-yellow-100 text-yellow-800"

// Error
className="bg-red-100 text-red-800"

// Info
className="bg-blue-100 text-blue-800"
```

## Responsive Design

### Breakpoints

Tailwind uses mobile-first breakpoints:

| Prefix | Min Width | Device |
|--------|-----------|--------|
| (none) | 0px | Mobile |
| `sm:` | 640px | Large mobile |
| `md:` | 768px | Tablet |
| `lg:` | 1024px | Desktop |
| `xl:` | 1280px | Large desktop |
| `2xl:` | 1536px | Extra large |

### Usage Pattern

```javascript
<div className="
  grid
  grid-cols-1        // Mobile: 1 column
  md:grid-cols-2     // Tablet: 2 columns
  lg:grid-cols-3     // Desktop: 3 columns
  gap-4
  md:gap-6
">
  {/* Grid items */}
</div>
```

### Container

```javascript
<div className="
  container mx-auto     // Center container
  px-4                  // Padding on mobile
  md:px-6              // More padding on tablet
  lg:px-8              // Even more on desktop
  max-w-7xl            // Max width
">
  {/* Content */}
</div>
```

## Layout Patterns

### Flexbox

```javascript
// Horizontal layout
<div className="flex items-center gap-4">
  <Icon />
  <span>Text</span>
</div>

// Vertical layout
<div className="flex flex-col gap-2">
  <div>Item 1</div>
  <div>Item 2</div>
</div>

// Space between
<div className="flex items-center justify-between">
  <span>Left</span>
  <button>Right</button>
</div>

// Center
<div className="flex items-center justify-center min-h-screen">
  <div>Centered content</div>
</div>
```

### Grid

```javascript
// Equal columns
<div className="grid grid-cols-3 gap-6">
  <div>Column 1</div>
  <div>Column 2</div>
  <div>Column 3</div>
</div>

// Responsive grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  {items.map(item => <div key={item.id}>{item.name}</div>)}
</div>

// Auto-fit grid (responsive without breakpoints)
<div className="grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-4">
  {items.map(item => <div key={item.id}>{item.name}</div>)}
</div>
```

## Animations & Transitions

### Hover States

```javascript
className="
  hover:bg-primary-700
  hover:scale-105
  hover:shadow-lg
  transition-all duration-200
"
```

### Focus States

```javascript
className="
  focus:outline-none
  focus:ring-2 focus:ring-primary-600 focus:ring-offset-2
"
```

### Transitions

```javascript
// Colors
className="transition-colors duration-200"

// All properties
className="transition-all duration-300"

// Transform
className="transition-transform duration-200 hover:scale-105"

// Opacity
className="transition-opacity duration-300 hover:opacity-80"
```

### Animations

```javascript
// Spin (loading)
className="animate-spin"

// Pulse (loading)
className="animate-pulse"

// Bounce
className="animate-bounce"
```

## Dark Mode (Future)

Tailwind supports dark mode with the `dark:` prefix:

```javascript
className="
  bg-white dark:bg-gray-900
  text-gray-900 dark:text-white
"
```

**Configuration:**
```javascript
// tailwind.config.js
export default {
  darkMode: 'class',  // or 'media'
  // ...
}
```

## Utility Class Organization

### Recommended Order

```javascript
className="
  // Layout
  block flex grid

  // Positioning
  relative absolute fixed

  // Sizing
  w-full h-screen

  // Spacing
  p-4 m-2 gap-4

  // Typography
  text-lg font-bold

  // Colors
  bg-white text-gray-900

  // Borders
  border-2 border-gray-300 rounded-xl

  // Effects
  shadow-lg opacity-90

  // Transitions
  transition-colors duration-200

  // Interactivity
  hover:bg-primary-700
  focus:outline-none
  active:scale-95
  disabled:opacity-50
"
```

### Extracting Common Patterns (Not Recommended)

**Avoid creating custom CSS classes** - use Tailwind utilities directly:

```javascript
// ❌ Avoid
// custom.css
.btn-primary {
  @apply bg-primary-600 text-white px-6 py-3 rounded-lg;
}

// ✅ Better: Use utilities directly
<button className="bg-primary-600 text-white px-6 py-3 rounded-lg">
  Button
</button>

// ✅ Best: Create React component
function Button({ children, ...props }) {
  return (
    <button
      className="bg-primary-600 text-white px-6 py-3 rounded-lg hover:bg-primary-700 transition-colors"
      {...props}
    >
      {children}
    </button>
  )
}
```

## Accessibility

### Focus Indicators

Always provide visible focus indicators:

```javascript
className="
  focus:outline-none
  focus:ring-2 focus:ring-primary-600 focus:ring-offset-2
"
```

### Screen Reader Only

```javascript
<span className="sr-only">
  Upload plant image for identification
</span>
```

### Contrast

Ensure sufficient color contrast:
- Text: 4.5:1 minimum
- Large text: 3:1 minimum
- Interactive elements: 3:1 minimum

## Performance

### Class Purging

Tailwind automatically removes unused classes in production:

```javascript
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  // Only classes used in these files are included in build
}
```

**Production Build:**
- Development CSS: ~3.5MB
- Production CSS: ~8-12KB (gzipped: ~2-3KB)

### JIT (Just-In-Time) Mode

Tailwind 4 uses JIT by default:
- Generate classes on-demand
- Faster build times
- Smaller development CSS

## Best Practices

1. **Mobile-First**
   - Start with mobile styles
   - Add breakpoint prefixes for larger screens

2. **Consistent Spacing**
   - Use Tailwind's spacing scale (4, 8, 12, 16...)
   - Avoid arbitrary values like `p-[13px]`

3. **Semantic Colors**
   - Use `primary-600` instead of `green-600` for brand color
   - Makes theme changes easier

4. **Composition Over Duplication**
   - Create React components for repeated patterns
   - Don't use `@apply` for custom classes

5. **Accessibility First**
   - Include focus states
   - Use semantic HTML
   - Provide ARIA labels

6. **Performance**
   - Keep class lists reasonable (<20 classes)
   - Use Tailwind's built-in utilities
   - Avoid inline styles

## Summary

The styling approach prioritizes:

1. **Utility-first** - All styling via Tailwind classes
2. **Consistency** - Design system with tokens
3. **Performance** - Automatic purging, JIT mode
4. **Maintainability** - Component composition over custom CSS
5. **Accessibility** - Focus states, semantic HTML
6. **Responsive** - Mobile-first breakpoints

For more information:
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Components.md](./Components.md) - Component patterns
- [Architecture.md](./Architecture.md) - System design
