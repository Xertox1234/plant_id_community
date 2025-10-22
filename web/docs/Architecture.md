# Web Frontend Architecture

## Overview

The Plant ID Community web frontend is a React 19 single-page application (SPA) built with Vite. It serves as a companion to the Flutter mobile app, providing plant identification capabilities optimized for desktop browsers.

## Technology Stack

### Core Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.1.1 | UI framework with concurrent rendering |
| Vite | 7.1.7 | Build tool with fast HMR and optimized production builds |
| Tailwind CSS | 4.1.15 | Utility-first CSS framework (v4 with Vite plugin) |
| React Router | 7.9.4 | Client-side routing |
| Axios | 1.12.2 | HTTP client for API communication |
| Lucide React | 0.546.0 | Tree-shakeable icon library |

### Development Tools

- **ESLint 9** - Code quality with flat config format
- **React Refresh** - Fast component hot-reloading
- **Vite Dev Server** - Lightning-fast development experience

## Architecture Decisions

### Why React 19?

- **Concurrent Rendering**: Better performance for image-heavy workflows
- **Automatic Batching**: Optimized state updates during plant identification
- **useTransition**: Smooth UI during API calls
- **Server Components Ready**: Future SSR migration path

### Why Vite over Create React App?

- **10-100x faster** development server startup
- **Fast HMR**: Sub-second hot module replacement
- **Optimized builds**: Better code splitting and tree-shaking
- **Modern defaults**: ES modules, no polyfill bloat
- **Better DX**: Simpler configuration, fewer dependencies

### Why Tailwind CSS v4?

- **Utility-first**: Rapid UI development without CSS files
- **Vite plugin**: No PostCSS configuration required
- **Consistent design**: Easy theme customization
- **Production optimization**: Automatic purging of unused styles
- **Responsive by default**: Mobile-first breakpoints

### Why No State Management Library?

**Current Decision: Local State Only**

Rationale:
- Simple application with minimal shared state
- No complex data flows requiring Redux/Zustand
- Props drilling is minimal (max 1-2 levels)
- Authentication not yet implemented

**Future Consideration:**
- May add Context API or Zustand when implementing:
  - User authentication
  - Plant collections
  - Cross-component data sharing

## Application Architecture

### Component Hierarchy

```
App (Router Root)
│
├── HomePage
│   └── (Static content)
│
├── IdentifyPage
│   ├── FileUpload
│   │   └── (Handles image selection & compression)
│   └── IdentificationResults
│       └── (Displays AI results)
│
├── BlogPage (Placeholder)
└── ForumPage (Placeholder)
```

### Data Flow

```
┌─────────────────┐
│   User Action   │
│ (Upload Image)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FileUpload     │
│  Component      │
└────────┬────────┘
         │
         ├─► Image Compression (utils/imageCompression.js)
         │
         ▼
┌─────────────────┐
│ IdentifyPage    │
│ (Parent State)  │
└────────┬────────┘
         │
         ├─► API Service (services/plantIdService.js)
         │
         ▼
┌─────────────────┐
│ Django Backend  │
│ (via Vite Proxy)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Identification  │
│    Results      │
└─────────────────┘
```

### State Management Pattern

**Local Component State (useState)**

```javascript
// IdentifyPage.jsx - All state localized to page component
const [selectedFile, setSelectedFile] = useState(null)
const [results, setResults] = useState(null)
const [loading, setLoading] = useState(false)
const [error, setError] = useState(null)
```

**Props Down, Events Up**

```javascript
// Parent → Child: Props
<FileUpload
  onFileSelect={handleFileSelect}
  selectedFile={selectedFile}
/>

// Child → Parent: Callbacks
const handleFileSelect = (file) => {
  setSelectedFile(file)
  setError(null)
}
```

## Routing Architecture

### Client-Side Routing (React Router v7)

```javascript
// App.jsx
<Routes>
  <Route path="/" element={<HomePage />} />
  <Route path="/identify" element={<IdentifyPage />} />
  <Route path="/blog" element={<BlogPage />} />
  <Route path="/forum" element={<ForumPage />} />
</Routes>
```

**Current Routes:**
- `/` - Landing page with hero and features
- `/identify` - Plant identification workflow
- `/blog` - Blog placeholder (future Wagtail integration)
- `/forum` - Forum placeholder (future Django Machina integration)

**Future Routes:**
- `/login` - Authentication
- `/profile` - User profile
- `/collection` - User's plant collection
- `/history` - Identification history

### Navigation Pattern

- **Link components** for internal navigation (no page reload)
- **Browser back/forward** fully supported
- **Deep linking** enabled (shareable URLs)

## API Integration Architecture

### Backend Communication

**Development Proxy (Vite)**

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    }
  }
}
```

**Benefits:**
- No CORS issues in development
- Frontend uses relative URLs (`/api/...`)
- Backend runs on separate port
- Production uses environment variable

**Service Layer Pattern**

```javascript
// services/plantIdService.js
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const plantIdService = {
  identifyPlant: async (imageFile) => {
    const formData = new FormData()
    formData.append('image', imageFile)

    const response = await axios.post(
      `${API_BASE_URL}/api/plant-identification/identify/`,
      formData
    )
    return response.data
  }
}
```

**Key Patterns:**
- Centralized API client
- Environment-based configuration
- FormData for file uploads
- Error extraction and handling
- Response unwrapping (return `.data` directly)

### Error Handling Strategy

```javascript
// Centralized error extraction
try {
  const result = await plantIdService.identifyPlant(file)
  setResults(result)
} catch (error) {
  const errorMessage = error.response?.data?.error
    || error.message
    || 'Failed to identify plant'
  setError(errorMessage)
}
```

## Performance Architecture

### Image Compression Pipeline

**Client-Side Optimization (Week 2 Feature)**

```
User Selects Image (10MB)
         │
         ▼
Check Size > 2MB?
         │
    Yes  │  No
         ▼     └─────► Use Original
Canvas Resize
 (max 1200px)
         │
         ▼
JPEG Compression
  (85% quality)
         │
         ▼
Compressed File (800KB)
         │
         ▼
Upload to Backend
```

**Performance Metrics:**
- **Size reduction**: 85% (10MB → 800KB)
- **Upload time**: 85% faster (40-80s → 3-5s)
- **Quality**: Maintained at 85% JPEG quality
- **Processing time**: <500ms for most images

### Code Splitting Strategy

**Vite Automatic Code Splitting**

```
dist/
├── index.html
└── assets/
    ├── index-[hash].js       # Main bundle
    ├── HomePage-[hash].js     # Route chunk
    ├── IdentifyPage-[hash].js # Route chunk
    └── vendor-[hash].js       # Dependencies
```

**Benefits:**
- Only load code for current route
- Shared dependencies in separate chunk
- Cache-friendly (hash-based filenames)
- Tree-shaking removes unused code

## Build Architecture

### Development Build

```bash
npm run dev
```

**Features:**
- Vite dev server on port 5173
- Fast HMR (<100ms reload)
- API proxy to Django backend
- Source maps for debugging
- ESLint on-the-fly

### Production Build

```bash
npm run build
```

**Optimizations:**
- Minification (Terser)
- Tree-shaking (removes unused exports)
- Code splitting by route
- CSS purging (unused Tailwind classes removed)
- Asset optimization (images, fonts)
- Gzip-ready output

**Output:**
```
dist/
├── index.html              # Entry point
├── assets/
│   ├── index-[hash].js     # ~50KB gzipped
│   ├── vendor-[hash].js    # ~150KB gzipped (React, Router)
│   └── index-[hash].css    # ~10KB gzipped (Tailwind)
└── vite.svg                # Favicon
```

## Security Architecture

### Environment Variables

**Safe Configuration:**

```javascript
// ✅ Safe: Only VITE_ prefix exposed to client
const API_URL = import.meta.env.VITE_API_URL

// ❌ Unsafe: Never store secrets in frontend
// const SECRET_KEY = import.meta.env.SECRET_KEY
```

**Best Practices:**
- All client environment variables prefixed with `VITE_`
- No API keys or secrets in frontend code
- Backend handles authentication tokens
- CORS configured on backend

### Content Security Policy (Future)

**Planned CSP Headers:**
```http
Content-Security-Policy:
  default-src 'self';
  img-src 'self' data: blob:;
  connect-src 'self' http://localhost:8000;
```

## Scalability Considerations

### Current Architecture Limits

**Designed For:**
- Small to medium traffic (< 10k DAU)
- Simple CRUD operations
- Static deployment (CDN)

**Not Optimized For:**
- Real-time features (no WebSockets)
- Complex data synchronization
- Offline-first (PWA features not implemented)

### Future Scaling Path

1. **Add Authentication**
   - JWT tokens from Django backend
   - Context API for user state
   - Protected routes

2. **Implement PWA**
   - Service Worker for offline mode
   - Cache API for images
   - Background sync for uploads

3. **Consider SSR/SSG**
   - Next.js migration for SEO
   - Server-side rendering for blog
   - Static generation for marketing pages

4. **Add State Management**
   - Zustand or Redux for complex state
   - Persist user data locally
   - Optimistic UI updates

## Testing Architecture (Planned)

### Unit Testing Strategy

**Recommended Stack:**
- **Vitest** - Fast, Vite-native test runner
- **React Testing Library** - Component testing
- **MSW** - API mocking

**Target Coverage:**
- Utilities: 100% (imageCompression.js)
- Services: 100% (plantIdService.js)
- Components: 80% (critical paths)

### E2E Testing Strategy (Future)

**Recommended:**
- **Playwright** - Cross-browser E2E testing
- **Critical flows** - Upload → Identify → Results

## Deployment Architecture

### Static Hosting (Recommended)

**Platforms:**
- **Vercel** - Zero-config, edge network
- **Netlify** - Continuous deployment, preview URLs
- **Firebase Hosting** - Google CDN, custom domains

**Deployment Process:**
```bash
# 1. Build production bundle
npm run build

# 2. Deploy dist/ to hosting platform
# (Vercel/Netlify auto-deploy from GitHub)

# 3. Set environment variables
VITE_API_URL=https://api.plantcommunity.com
```

### CDN Architecture

```
User Request
     │
     ▼
CDN Edge Location (Cached Static Assets)
     │
     └─► Origin (if cache miss)
         └─► Static Hosting (dist/)
```

## Monitoring & Observability (Planned)

### Error Tracking

**Planned Integration:**
- Sentry for error tracking
- Source maps for stack traces
- User context in error reports

### Analytics

**Planned Integration:**
- Google Analytics 4
- Custom events (plant identification success/failure)
- Performance metrics (Core Web Vitals)

## Summary

The web frontend architecture prioritizes:

1. **Developer Experience** - Fast builds, HMR, modern tooling
2. **Performance** - Image compression, code splitting, CDN
3. **Simplicity** - Local state, no over-engineering
4. **Scalability** - Clear upgrade path for future features

This architecture supports the current scope (plant identification companion) while remaining flexible for future expansion.
