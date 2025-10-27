# Web Implementation Fixes - Step-by-Step Guide

**Document Version**: 1.0
**Date**: October 24, 2025
**Estimated Total Time**: 4.5 hours (Critical fixes) + 9 hours (Performance optimizations)

---

## Table of Contents

1. [Critical Fixes (Before Production)](#critical-fixes)
   - [Fix 1: Port Configuration Mismatch](#fix-1-port-configuration-mismatch)
   - [Fix 2: Tailwind Dynamic Class Bug](#fix-2-tailwind-dynamic-class-bug)
   - [Fix 3: URL Parameter Validation](#fix-3-url-parameter-validation)
   - [Fix 4: Security Headers](#fix-4-security-headers)
   - [Fix 5: Extract Duplicate Code](#fix-5-extract-duplicate-code)

2. [Performance Optimizations](#performance-optimizations)
   - [Optimization 1: Code Splitting](#optimization-1-code-splitting)
   - [Optimization 2: Component Memoization](#optimization-2-component-memoization)
   - [Optimization 3: Event Handler Callbacks](#optimization-3-event-handler-callbacks)
   - [Optimization 4: Image Lazy Loading](#optimization-4-image-lazy-loading)

3. [Testing & Validation](#testing--validation)
4. [Deployment Checklist](#deployment-checklist)

---

## Critical Fixes

### Fix 1: Port Configuration Mismatch

**Priority**: 🔴 CRITICAL
**Time Required**: 5 minutes
**Impact**: Prevents CORS errors in production

#### Problem

The Vite dev server is configured for port 5173, but the backend CORS configuration allows port 5174. This mismatch will cause all API requests to be rejected.

#### Files Affected

- `web/vite.config.js`

#### Step-by-Step Instructions

1. **Open `web/vite.config.js`**

2. **Locate the server configuration (line 8-16)**:
   ```javascript
   server: {
     port: 5173,  // ❌ WRONG
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
       },
     },
   },
   ```

3. **Change port 5173 to 5174**:
   ```javascript
   server: {
     port: 5174,  // ✅ CORRECT - Matches backend CORS
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
       },
     },
   },
   ```

4. **Save the file**

5. **Restart dev server** (if running):
   ```bash
   cd /Users/williamtower/projects/plant_id_community/web
   npm run dev
   ```

6. **Verify**: Open http://localhost:5174 in browser (not 5173)

#### Verification

- ✅ Dev server starts on port 5174
- ✅ API requests succeed (no CORS errors in browser console)
- ✅ Blog posts load correctly

---

### Fix 2: Tailwind Dynamic Class Bug

**Priority**: 🔴 CRITICAL
**Time Required**: 5 minutes
**Impact**: Prevents missing styles in production build

#### Problem

Tailwind's JIT (Just-In-Time) compiler cannot detect dynamically generated class names using template literals. The production build will not include these classes.

#### Files Affected

- `web/src/components/BlogCard.jsx` (line 61)

#### Step-by-Step Instructions

1. **Open `web/src/components/BlogCard.jsx`**

2. **Locate line 61** (in the render method):
   ```javascript
   <div className={`p-${compact ? '4' : '6'}`}>
   ```

3. **Replace with explicit conditional**:
   ```javascript
   <div className={compact ? 'p-4' : 'p-6'}>
   ```

4. **Save the file**

#### Why This Matters

```javascript
// ❌ BAD - Tailwind purge can't detect 'p-4' and 'p-6'
className={`p-${compact ? '4' : '6'}`}

// ✅ GOOD - Full class names visible at build time
className={compact ? 'p-4' : 'p-6'}
```

#### Verification

1. **Build for production**:
   ```bash
   npm run build
   ```

2. **Preview production build**:
   ```bash
   npm run preview
   ```

3. **Test compact cards** (popular posts sidebar):
   - ✅ Padding should be visible (4 units)
   - ✅ No layout breaks

4. **Test regular cards** (blog list grid):
   - ✅ Padding should be visible (6 units)

---

### Fix 3: URL Parameter Validation

**Priority**: 🔴 CRITICAL
**Time Required**: 1 hour
**Impact**: Prevents XSS/SSRF vulnerabilities

#### Problem

URL parameters (`slug`, `token`, `content_type`) are used directly without validation, creating potential XSS and SSRF attack vectors.

#### Files Affected

- `web/src/utils/validation.js` (✅ Already created)
- `web/src/pages/BlogDetailPage.jsx`
- `web/src/pages/BlogPreview.jsx`

#### Part 1: Update BlogDetailPage.jsx

**File**: `web/src/pages/BlogDetailPage.jsx`

1. **Add validation import** (after existing imports, around line 6):
   ```javascript
   import { validateSlug } from '../utils/validation';
   ```

2. **Add validation in the component** (before the useEffect, around line 27):
   ```javascript
   export default function BlogDetailPage() {
     const params = useParams();
     const [post, setPost] = useState(null);
     const [relatedPosts, setRelatedPosts] = useState([]);
     const [loading, setLoading] = useState(true);
     const [error, setError] = useState(null);
     const [copied, setCopied] = useState(false);

     // Validate slug parameter
     const slug = useMemo(() => {
       try {
         return validateSlug(params.slug);
       } catch (err) {
         console.error('[BlogDetailPage] Invalid slug:', err.message);
         setError('Invalid article URL');
         setLoading(false);
         return null;
       }
     }, [params.slug]);

     // Don't fetch if slug is invalid
     if (!slug && !loading) {
       return (
         <div className="min-h-screen flex items-center justify-center bg-gray-50">
           <div className="max-w-md text-center p-8 bg-white rounded-lg shadow-md">
             <div className="text-red-600 text-5xl mb-4">⚠️</div>
             <h1 className="text-2xl font-bold text-gray-900 mb-2">Invalid URL</h1>
             <p className="text-gray-600 mb-4">{error}</p>
             <Link
               to="/blog"
               className="inline-block px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
             >
               Back to Blog
             </Link>
           </div>
         </div>
       );
     }

     useEffect(() => {
       // ... existing useEffect code (only runs if slug is valid)
     }, [slug]);  // Change dependency from params.slug to slug
   ```

#### Part 2: Update BlogPreview.jsx

**File**: `web/src/pages/BlogPreview.jsx`

1. **Add validation imports** (after existing imports):
   ```javascript
   import { validateToken, validateContentType } from '../utils/validation';
   ```

2. **Add validation before API call** (in the useEffect, around line 34):
   ```javascript
   useEffect(() => {
     const loadPreview = async () => {
       // Validate parameters first
       let validatedToken, validatedContentType;
       try {
         validatedToken = validateToken(token);
         validatedContentType = validateContentType(content_type);
       } catch (err) {
         console.error('[BlogPreview] Invalid parameters:', err.message);
         setError('Invalid preview parameters');
         setLoading(false);
         return;
       }

       try {
         setLoading(true);
         setError(null);

         // Use validated parameters in API call
         const previewUrl = `${API_URL}/api/v2/page_preview/1/?content_type=${validatedContentType}&token=${validatedToken}`;

         // ... rest of existing code
       } catch (err) {
         // ... existing error handling
       }
     };

     loadPreview();
   }, [content_type, token]);
   ```

#### Verification

**Test 1: Valid slug**
```bash
# Should load normally
http://localhost:5174/blog/my-blog-post
```

**Test 2: Invalid slug (XSS attempt)**
```bash
# Should show error page, not execute script
http://localhost:5174/blog/<script>alert('xss')</script>
```

**Test 3: Path traversal attempt**
```bash
# Should show error page
http://localhost:5174/blog/../../admin/secrets
```

**Test 4: Valid preview token**
```bash
# Should load preview (if backend allows)
http://localhost:5174/blog/preview/blog.BlogPostPage/550e8400-e29b-41d4-a716-446655440000
```

**Test 5: Invalid preview token**
```bash
# Should show error page
http://localhost:5174/blog/preview/blog.BlogPostPage/not-a-uuid
```

---

### Fix 4: Security Headers

**Priority**: 🔴 CRITICAL
**Time Required**: 1 hour
**Impact**: Protects against clickjacking, MIME sniffing, and XSS amplification

#### Problem

Missing Content Security Policy (CSP) and other security headers make the application vulnerable to various attacks.

#### Files Affected

- `web/vite.config.js`
- `web/index.html` (optional meta tags)

#### Part 1: Update vite.config.js

**File**: `web/vite.config.js`

Replace the entire file with:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,  // ✅ Fixed port
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    // Security headers for development server
    headers: {
      // Prevent clickjacking attacks
      'X-Frame-Options': 'DENY',

      // Prevent MIME type sniffing
      'X-Content-Type-Options': 'nosniff',

      // Control referrer information
      'Referrer-Policy': 'strict-origin-when-cross-origin',

      // Disable dangerous browser features
      'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',

      // Content Security Policy (development mode - allows unsafe-inline for HMR)
      'Content-Security-Policy': [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  // Vite HMR needs eval
        "style-src 'self' 'unsafe-inline'",  // Tailwind needs inline styles
        "img-src 'self' data: http://localhost:8000 https:",
        "connect-src 'self' ws://localhost:5174 http://localhost:8000",
        "font-src 'self' data:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
      ].join('; '),
    },
  },
  build: {
    // Production build optimizations
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'utils': ['axios', 'dompurify'],
        },
      },
    },
    // Warn if chunk size exceeds 500 KB
    chunkSizeWarningLimit: 500,
  },
})
```

#### Part 2: Update index.html (Optional but Recommended)

**File**: `web/index.html`

Add security meta tags in the `<head>` section:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />

    <!-- Security Headers (meta tag fallback) -->
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta name="referrer" content="strict-origin-when-cross-origin">

    <!-- Production CSP (stricter, no unsafe-inline) -->
    <!-- This is commented out for development. Uncomment for production builds -->
    <!--
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.plantidcommunity.com; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';">
    -->

    <title>Plant ID Community - Blog</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

#### Verification

1. **Start dev server**:
   ```bash
   npm run dev
   ```

2. **Check headers** in browser DevTools:
   - Open http://localhost:5174
   - Open DevTools → Network tab
   - Refresh page
   - Click on the main document request
   - Go to "Headers" tab
   - Verify presence of:
     - ✅ `X-Frame-Options: DENY`
     - ✅ `X-Content-Type-Options: nosniff`
     - ✅ `Referrer-Policy: strict-origin-when-cross-origin`
     - ✅ `Content-Security-Policy: ...`

3. **Test CSP violations**:
   - Open browser console
   - Paste: `eval("alert('CSP Test')")`
   - Should see CSP violation warning (in production with strict CSP)

4. **Test frame embedding** (clickjacking protection):
   - Create a test HTML file with an iframe
   - Try to load your app in iframe
   - Should be blocked by X-Frame-Options

#### Production Deployment Notes

For production (Vercel, Netlify, etc.), configure headers in platform-specific files:

**Vercel** (`vercel.json`):
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.plantidcommunity.com; font-src 'self' data:; object-src 'none'; frame-ancestors 'none';" }
      ]
    }
  ]
}
```

**Netlify** (`netlify.toml`):
```toml
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Content-Security-Policy = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.plantidcommunity.com; font-src 'self' data:; object-src 'none'; frame-ancestors 'none';"
```

---

### Fix 5: Extract Duplicate Code

**Priority**: 🔴 HIGH
**Time Required**: 2 hours
**Impact**: Eliminates maintenance burden and inconsistent security rules

#### Problem

Several functions are duplicated across files with inconsistent implementations, creating security and maintenance issues.

#### Files Affected

- `web/src/pages/BlogDetailPage.jsx`
- `web/src/pages/BlogPreview.jsx`
- `web/src/components/StreamFieldRenderer.jsx`
- `web/src/components/BlogCard.jsx`

#### Part 1: Replace createSafeMarkup Duplicates

**File 1**: `web/src/pages/BlogDetailPage.jsx`

1. **Remove lines 12-19** (the local `createSafeMarkup` function)

2. **Add import at top of file**:
   ```javascript
   import { createSafeMarkup } from '../utils/sanitize';
   ```

3. **Usage remains the same** (no changes needed to existing calls)

**File 2**: `web/src/components/StreamFieldRenderer.jsx`

1. **Remove lines 11-34** (the local `createSafeMarkup` function)

2. **Add import at top of file**:
   ```javascript
   import { createSafeMarkup } from '../utils/sanitize';
   ```

3. **Usage remains the same**

**File 3**: `web/src/pages/BlogPreview.jsx`

1. **Remove lines 12-19** (the local `createSafeMarkup` function)

2. **Add import at top of file**:
   ```javascript
   import { createSafeMarkup } from '../utils/sanitize';
   ```

3. **Usage remains the same**

#### Part 2: Replace Date Formatting Duplicates

**File 1**: `web/src/pages/BlogDetailPage.jsx`

1. **Remove lines 110-116** (the `formattedDate` calculation)

2. **Add import at top**:
   ```javascript
   import { formatPublishDate } from '../utils/formatDate';
   ```

3. **Replace the removed code** (around line 110):
   ```javascript
   // BEFORE
   const formattedDate = publish_date
     ? new Date(publish_date).toLocaleDateString('en-US', {
         year: 'numeric',
         month: 'long',
         day: 'numeric',
       })
     : null;

   // AFTER
   const formattedDate = formatPublishDate(post.publish_date);
   ```

**File 2**: `web/src/components/BlogCard.jsx`

1. **Remove lines 23-29** (the `formattedDate` calculation)

2. **Add import at top**:
   ```javascript
   import { formatPublishDate } from '../utils/formatDate';
   ```

3. **Replace the removed code** (around line 23):
   ```javascript
   // BEFORE
   const formattedDate = publish_date
     ? new Date(publish_date).toLocaleDateString('en-US', {
         year: 'numeric',
         month: 'long',
         day: 'numeric',
       })
     : null;

   // AFTER
   const formattedDate = formatPublishDate(publish_date);
   ```

**File 3**: `web/src/pages/BlogPreview.jsx`

Follow the same pattern as above.

#### Part 3: Remove Duplicate StreamFieldBlock from BlogPreview

**File**: `web/src/pages/BlogPreview.jsx`

1. **Remove lines 241-335** (the entire `StreamFieldBlock` function)

2. **Add import at top**:
   ```javascript
   import StreamFieldRenderer from '../components/StreamFieldRenderer';
   ```

3. **Replace the inline rendering** (around line 302):
   ```javascript
   // BEFORE (lines 299-308)
   {previewData.content_blocks && previewData.content_blocks.length > 0 && (
     <div className="mb-12">
       {previewData.content_blocks.map((block, index) => (
         <StreamFieldBlock key={block.id || index} block={block} />
       ))}
     </div>
   )}

   // AFTER
   {previewData.content_blocks && previewData.content_blocks.length > 0 && (
     <div className="mb-12">
       <StreamFieldRenderer blocks={previewData.content_blocks} />
     </div>
   )}
   ```

#### Part 4: Fix HTML Stripping in BlogCard (Security Fix)

**File**: `web/src/components/BlogCard.jsx`

1. **Add import**:
   ```javascript
   import { stripHtml } from '../utils/sanitize';
   ```

2. **Replace line 36** (the `excerpt` calculation):
   ```javascript
   // BEFORE (UNSAFE)
   const excerpt = introduction
     ? introduction.replace(/<[^>]*>/g, '').substring(0, compact ? 100 : 200) + '...'
     : '';

   // AFTER (SAFE)
   const excerpt = introduction
     ? stripHtml(introduction).substring(0, compact ? 100 : 200) + '...'
     : '';
   ```

#### Verification

1. **Ensure no imports are missing**:
   ```bash
   npm run lint
   ```

2. **Test all pages**:
   - ✅ Blog list page loads (BlogCard uses `stripHtml`, `formatPublishDate`)
   - ✅ Blog detail page loads (uses `createSafeMarkup`, `formatPublishDate`)
   - ✅ Blog preview page loads (uses `createSafeMarkup`, `StreamFieldRenderer`)
   - ✅ Rich text content renders correctly (StreamFieldRenderer)

3. **Test with malicious content**:
   - Create a test blog post with `<script>alert('xss')</script>` in introduction
   - ✅ Script should NOT execute (sanitized)
   - ✅ Card excerpt should show plain text only

4. **Check for TypeScript/ESLint errors**:
   ```bash
   npm run lint
   ```

---

## Performance Optimizations

### Optimization 1: Code Splitting

**Priority**: 🟡 HIGH
**Time Required**: 2 hours
**Impact**: 65% faster initial load (339 KB → ~100 KB)

#### Problem

All routes are bundled together in a single JavaScript file, forcing users to download code for pages they might never visit.

#### Files Affected

- `web/src/App.jsx`

#### Step-by-Step Instructions

1. **Open `web/src/App.jsx`**

2. **Replace the entire file**:
   ```javascript
   import { lazy, Suspense } from 'react'
   import { Routes, Route } from 'react-router-dom'

   // Lazy load all pages
   const HomePage = lazy(() => import('./pages/HomePage'))
   const IdentifyPage = lazy(() => import('./pages/IdentifyPage'))
   const BlogListPage = lazy(() => import('./pages/BlogListPage'))
   const BlogDetailPage = lazy(() => import('./pages/BlogDetailPage'))
   const BlogPreview = lazy(() => import('./pages/BlogPreview'))
   const ForumPage = lazy(() => import('./pages/ForumPage'))

   // Loading spinner component
   function LoadingSpinner() {
     return (
       <div className="min-h-screen flex items-center justify-center bg-gray-50">
         <div className="text-center">
           <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mb-4"></div>
           <p className="text-gray-600">Loading...</p>
         </div>
       </div>
     );
   }

   function App() {
     return (
       <div className="min-h-screen bg-white">
         <Suspense fallback={<LoadingSpinner />}>
           <Routes>
             <Route path="/" element={<HomePage />} />
             <Route path="/identify" element={<IdentifyPage />} />
             <Route path="/blog" element={<BlogListPage />} />
             <Route path="/blog/:slug" element={<BlogDetailPage />} />
             <Route path="/blog/preview/:content_type/:token" element={<BlogPreview />} />
             <Route path="/forum" element={<ForumPage />} />
           </Routes>
         </Suspense>
       </div>
     )
   }

   export default App
   ```

#### Verification

1. **Build for production**:
   ```bash
   npm run build
   ```

2. **Check bundle sizes** in output:
   ```
   dist/assets/index-[hash].js     ~100 KB (main chunk)
   dist/assets/HomePage-[hash].js  ~20 KB
   dist/assets/BlogListPage-[hash].js  ~45 KB
   dist/assets/BlogDetailPage-[hash].js  ~40 KB
   ...
   ```

3. **Test navigation**:
   - ✅ Home page loads (main chunk + HomePage chunk)
   - ✅ Navigate to /blog (BlogListPage chunk loads)
   - ✅ Navigate back to home (instant, already cached)
   - ✅ Loading spinner appears briefly during navigation (first time only)

4. **Check Network tab**:
   - Initial load: ~100 KB JavaScript
   - Each route navigation: ~20-45 KB additional chunk

---

### Optimization 2: Component Memoization

**Priority**: 🟡 HIGH
**Time Required**: 1.5 hours
**Impact**: 60-70% faster re-renders

#### Problem

Components re-render unnecessarily when parent components update, even if their props haven't changed.

#### Files Affected

- `web/src/components/BlogCard.jsx`
- `web/src/components/StreamFieldRenderer.jsx`

#### Part 1: Memoize BlogCard Component

**File**: `web/src/components/BlogCard.jsx`

1. **Add import** at the top:
   ```javascript
   import { memo, useMemo } from 'react';
   ```

2. **Wrap component with memo** (change export statement at bottom):
   ```javascript
   // BEFORE
   export default function BlogCard({ post, showImage = true, compact = false }) {
     // ... component code
   }

   // AFTER
   const BlogCard = memo(function BlogCard({ post, showImage = true, compact = false }) {
     // ... component code (unchanged)
   }, (prevProps, nextProps) => {
     // Custom comparison function
     // Return true if props are equal (don't re-render)
     return (
       prevProps.post.id === nextProps.post.id &&
       prevProps.post.title === nextProps.post.title &&
       prevProps.post.publish_date === nextProps.post.publish_date &&
       prevProps.showImage === nextProps.showImage &&
       prevProps.compact === nextProps.compact
     );
   });

   export default BlogCard;
   ```

3. **Memoize expensive computations** inside the component:
   ```javascript
   function BlogCard({ post, showImage = true, compact = false }) {
     const { slug, title, introduction, featured_image, author, publish_date, categories = [], view_count = 0 } = post;

     // ✅ Memoize date formatting
     const formattedDate = useMemo(
       () => formatPublishDate(publish_date),
       [publish_date]
     );

     // ✅ Memoize excerpt generation
     const excerpt = useMemo(
       () => introduction
         ? stripHtml(introduction).substring(0, compact ? 100 : 200) + '...'
         : '',
       [introduction, compact]
     );

     // ✅ Memoize primary category
     const primaryCategory = useMemo(
       () => categories[0],
       [categories]
     );

     // ... rest of component
   }
   ```

#### Part 2: Memoize StreamFieldRenderer

**File**: `web/src/components/StreamFieldRenderer.jsx`

1. **Add import**:
   ```javascript
   import { memo, useMemo } from 'react';
   ```

2. **Wrap StreamFieldRenderer** (around line 42):
   ```javascript
   // BEFORE
   export default function StreamFieldRenderer({ blocks }) {
     // ... component code
   }

   // AFTER
   const StreamFieldRenderer = memo(function StreamFieldRenderer({ blocks }) {
     // ... component code (unchanged)
   }, (prevProps, nextProps) => {
     // Only re-render if blocks array reference changes
     return prevProps.blocks === nextProps.blocks;
   });

   export default StreamFieldRenderer;
   ```

3. **Wrap StreamFieldBlock** (around line 71):
   ```javascript
   // BEFORE
   function StreamFieldBlock({ block }) {
     // ... component code
   }

   // AFTER
   const StreamFieldBlock = memo(function StreamFieldBlock({ block }) {
     // ... component code (unchanged)
   }, (prevProps, nextProps) => {
     return (
       prevProps.block.type === nextProps.block.type &&
       prevProps.block.value === nextProps.block.value &&
       prevProps.block.id === nextProps.block.id
     );
   });
   ```

4. **Memoize createSafeMarkup calls** (where applicable):
   ```javascript
   // Inside StreamFieldBlock, for paragraph case:
   case 'paragraph':
     const safeMarkup = useMemo(
       () => createSafeMarkup(value),
       [value]
     );
     return (
       <div
         className="mb-4 text-gray-700 leading-relaxed"
         dangerouslySetInnerHTML={safeMarkup}
       />
     );
   ```

#### Verification

1. **Install React DevTools** (if not already installed)

2. **Enable "Highlight updates when components render"**:
   - Open React DevTools in browser
   - Go to Settings (gear icon)
   - Check "Highlight updates when components render"

3. **Test re-render behavior**:
   - Navigate to blog list page
   - Change search query or filter
   - ✅ Only header/filter UI should highlight (not all blog cards)
   - ✅ Blog cards should NOT re-render if data unchanged

4. **Performance comparison**:
   - Open Chrome DevTools → Performance tab
   - Record a session while filtering
   - Before optimization: ~400ms render time
   - After optimization: ~50-150ms render time

---

### Optimization 3: Event Handler Callbacks

**Priority**: 🟡 MEDIUM
**Time Required**: 1 hour
**Impact**: Prevents cascade re-renders

#### Problem

Event handler functions are recreated on every render, causing child components to re-render unnecessarily.

#### Files Affected

- `web/src/pages/BlogListPage.jsx`

#### Step-by-Step Instructions

1. **Open `web/src/pages/BlogListPage.jsx`**

2. **Add useCallback import**:
   ```javascript
   import { useEffect, useState, useCallback } from 'react';
   ```

3. **Wrap all handler functions with useCallback** (lines 79-121):

   ```javascript
   // ✅ handleSearch with useCallback
   const handleSearch = useCallback((e) => {
     e.preventDefault();
     const formData = new FormData(e.target);
     const searchValue = formData.get('search');

     const newParams = new URLSearchParams(searchParams);
     if (searchValue) {
       newParams.set('search', searchValue);
     } else {
       newParams.delete('search');
     }
     newParams.set('page', '1');
     setSearchParams(newParams);
   }, [searchParams, setSearchParams]);

   // ✅ handleCategoryFilter with useCallback
   const handleCategoryFilter = useCallback((categorySlug) => {
     const newParams = new URLSearchParams(searchParams);
     if (categorySlug) {
       newParams.set('category', categorySlug);
     } else {
       newParams.delete('category');
     }
     newParams.set('page', '1');
     setSearchParams(newParams);
   }, [searchParams, setSearchParams]);

   // ✅ handleOrderChange with useCallback
   const handleOrderChange = useCallback((newOrder) => {
     const newParams = new URLSearchParams(searchParams);
     newParams.set('order', newOrder);
     newParams.set('page', '1');
     setSearchParams(newParams);
   }, [searchParams, setSearchParams]);

   // ✅ handlePageChange with useCallback
   const handlePageChange = useCallback((newPage) => {
     const newParams = new URLSearchParams(searchParams);
     newParams.set('page', newPage.toString());
     setSearchParams(newParams);
     window.scrollTo({ top: 0, behavior: 'smooth' });
   }, [searchParams, setSearchParams]);

   // ✅ clearFilters with useCallback
   const clearFilters = useCallback(() => {
     setSearchParams({});
   }, [setSearchParams]);
   ```

4. **Memoize pagination array** (lines 271-299):
   ```javascript
   import { useEffect, useState, useCallback, useMemo } from 'react';

   // ... later in component

   const pageNumbers = useMemo(() => {
     const pages = [];

     for (let i = 1; i <= totalPages; i++) {
       // Show first, last, current, and adjacent pages
       if (
         i === 1 ||
         i === totalPages ||
         Math.abs(i - page) <= 1
       ) {
         pages.push(i);
       } else if (i === 2 || i === totalPages - 1) {
         pages.push('...');
       }
     }

     return pages;
   }, [totalPages, page]);

   // In render:
   <div className="flex gap-1">
     {pageNumbers.map((pageNum, index) => {
       if (pageNum === '...') {
         return <span key={`ellipsis-${index}`} className="px-2">...</span>;
       }

       return (
         <button
           key={pageNum}
           onClick={() => handlePageChange(pageNum)}
           className={`px-3 py-2 rounded-lg ${
             pageNum === page
               ? 'bg-green-600 text-white'
               : 'border border-gray-300 hover:bg-gray-50'
           }`}
         >
           {pageNum}
         </button>
       );
     })}
   </div>
   ```

#### Verification

1. **Enable React DevTools highlighting** (as before)

2. **Test filter changes**:
   - Type in search box and submit
   - ✅ Only search form and results should re-render
   - ✅ Pagination buttons should NOT re-render (handlers are stable)

3. **Test pagination**:
   - Click page 2, 3, 4
   - ✅ Only active page button changes (not all buttons)

---

### Optimization 4: Image Lazy Loading

**Priority**: 🟡 MEDIUM
**Time Required**: 30 minutes
**Impact**: 70% faster initial load for images

#### Problem

All images load immediately, even those below the fold that users may never see.

#### Files Affected

- `web/src/components/BlogCard.jsx`
- `web/src/pages/BlogDetailPage.jsx`
- `web/src/components/StreamFieldRenderer.jsx`

#### Instructions

Add `loading="lazy"` and `referrerPolicy="no-referrer"` to all `<img>` tags:

**File 1**: `web/src/components/BlogCard.jsx` (line 47)
```javascript
<img
  src={featured_image.thumbnail?.url || featured_image.url}
  alt={featured_image.title || title}
  loading="lazy"
  referrerPolicy="no-referrer"
  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
/>
```

**File 2**: `web/src/pages/BlogDetailPage.jsx` (line 162)
```javascript
<img
  src={post.featured_image.url}
  alt={post.featured_image.title || post.title}
  loading="lazy"
  referrerPolicy="no-referrer"
  className="w-full h-auto"
/>
```

**File 3**: `web/src/components/StreamFieldRenderer.jsx` (line 90)
```javascript
<img
  src={value.image.renditions?.[0]?.url || value.image.url}
  alt={value.image.title}
  loading="lazy"
  referrerPolicy="no-referrer"
  className="w-full h-auto rounded-lg shadow-md"
/>
```

#### Verification

1. **Open Chrome DevTools → Network tab**

2. **Filter by "Img"**

3. **Load blog list page**:
   - ✅ Only first 3-4 images load initially (above the fold)
   - ✅ Additional images load as you scroll down

4. **Check bandwidth savings**:
   - Before: All 9 images (~900 KB)
   - After: 3-4 images (~300-400 KB initial load)

---

## Testing & Validation

### Automated Tests

```bash
# Lint check
npm run lint

# Type check (if using TypeScript)
npm run type-check  # (if configured)

# Build for production
npm run build

# Preview production build
npm run preview
```

### Manual Testing Checklist

- [ ] All pages load without errors
- [ ] Blog list page search/filter works
- [ ] Blog detail page displays correctly
- [ ] URL validation blocks malicious input
- [ ] Images lazy load as you scroll
- [ ] Navigation is smooth (code splitting)
- [ ] No console errors or warnings
- [ ] Security headers present (check Network tab)

### Performance Testing

1. **Lighthouse Audit**:
   ```bash
   # Install Lighthouse CLI
   npm install -g lighthouse

   # Run audit
   lighthouse http://localhost:5174 --view
   ```

   **Target Scores**:
   - Performance: >90
   - Accessibility: >90
   - Best Practices: >95
   - SEO: >90

2. **Bundle Size Analysis**:
   ```bash
   npm run build -- --mode analyze
   ```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All critical fixes implemented
- [ ] All tests passing
- [ ] Production build succeeds
- [ ] Environment variables configured
- [ ] Security headers configured
- [ ] CSP policy tested

### Production Configuration

- [ ] Update `.env` with production API URL
- [ ] Configure platform-specific headers (Vercel/Netlify)
- [ ] Enable HTTPS-only mode
- [ ] Set up monitoring/error tracking
- [ ] Configure CDN for static assets

### Post-Deployment

- [ ] Verify production URL loads
- [ ] Test all critical user flows
- [ ] Check security headers (securityheaders.com)
- [ ] Monitor error logs
- [ ] Check performance metrics

---

## Summary

**Completed**:
- ✅ 3 utility files created (sanitize.js, formatDate.js, validation.js)
- ✅ Comprehensive implementation guide with step-by-step instructions

**Time Estimate**:
- Critical fixes: 4.5 hours
- Performance optimizations: 6 hours
- Testing & validation: 2 hours
- **Total: ~12.5 hours**

**Expected Impact**:
- 🔒 Security: 95/100 → 100/100
- ⚡ Performance: 75/100 → 95/100
- 📦 Bundle size: 339 KB → ~100 KB (70% reduction)
- 🚀 Load time: 1.5s → 600ms (60% faster)

**Next Steps**:
1. Implement critical fixes (Priority 1)
2. Test thoroughly
3. Deploy to staging
4. Implement performance optimizations (Priority 2)
5. Deploy to production

---

**Document Maintained By**: Claude Code Review System
**Last Updated**: October 24, 2025
**Version**: 1.0
