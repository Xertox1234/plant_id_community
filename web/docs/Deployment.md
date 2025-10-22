# Deployment Guide

Complete guide for deploying the Plant ID Community web frontend to production.

## Overview

The web frontend is a static React application that can be deployed to any static hosting platform. It requires a separate backend API server for full functionality.

## Build Process

### Production Build

```bash
# Navigate to web directory
cd web

# Install dependencies
npm install

# Create production build
npm run build
```

**Output:**
```
dist/
├── index.html                   # Entry HTML
├── assets/
│   ├── index-[hash].js          # Main bundle (~52KB gzipped)
│   ├── vendor-[hash].js         # Dependencies (~148KB gzipped)
│   └── index-[hash].css         # Tailwind CSS (~10KB gzipped)
└── vite.svg                     # Favicon
```

**Build Stats:**
- Total size: ~70KB gzipped
- Build time: 2-3 seconds
- ES modules, tree-shaken, minified

### Preview Build Locally

```bash
# Build first
npm run build

# Preview on http://localhost:4173
npm run preview
```

## Environment Configuration

### Required Environment Variables

```bash
# Production API URL (required)
VITE_API_URL=https://api.plantcommunity.com
```

### Optional Environment Variables

```bash
# Google Analytics (optional)
VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX

# Sentry error tracking (optional)
VITE_SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx

# Debug mode (optional, default: false)
VITE_DEBUG=false
```

## Deployment Platforms

### Vercel (Recommended)

**Why Vercel:**
- Zero configuration
- Automatic builds on git push
- Global CDN
- Free SSL certificates
- Preview deployments for PRs
- Excellent performance

#### Deployment Steps

1. **Install Vercel CLI** (optional)
   ```bash
   npm install -g vercel
   ```

2. **Connect Repository**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your Git repository
   - Select "web" as root directory

3. **Configure Build Settings**
   ```
   Framework Preset: Vite
   Build Command: npm run build
   Output Directory: dist
   Install Command: npm install
   ```

4. **Set Environment Variables**
   - Go to Project Settings → Environment Variables
   - Add `VITE_API_URL` with production backend URL
   - Add optional variables (GA, Sentry)

5. **Deploy**
   ```bash
   # Manual deploy via CLI
   cd web
   vercel

   # Or commit to main branch (auto-deploy)
   git push origin main
   ```

**Vercel Configuration File** (optional):
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "installCommand": "npm install"
}
```

**Custom Domain:**
```bash
# Add custom domain in Vercel dashboard
# DNS Configuration:
# CNAME plantcommunity.com → cname.vercel-dns.com
# A Record @ → 76.76.21.21
```

### Netlify

**Why Netlify:**
- Simple deployment
- Automatic HTTPS
- Form handling
- Serverless functions
- CDN distribution

#### Deployment Steps

1. **Connect Repository**
   - Go to [netlify.com](https://netlify.com)
   - Click "New site from Git"
   - Connect GitHub repository
   - Select "web" as base directory

2. **Configure Build**
   ```
   Base directory: web
   Build command: npm run build
   Publish directory: web/dist
   ```

3. **Set Environment Variables**
   - Go to Site Settings → Environment Variables
   - Add `VITE_API_URL`

4. **Deploy**
   - Click "Deploy site"
   - Or push to main branch for auto-deploy

**netlify.toml** (optional):
```toml
[build]
  base = "web"
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### Firebase Hosting

**Why Firebase:**
- Google infrastructure
- Easy integration with Firebase backend
- CDN distribution
- SSL included

#### Deployment Steps

1. **Install Firebase CLI**
   ```bash
   npm install -g firebase-tools
   ```

2. **Login and Initialize**
   ```bash
   firebase login
   cd web
   firebase init hosting
   ```

3. **Configuration**
   ```
   Public directory: dist
   Single-page app: Yes
   Rewrites: Yes
   ```

4. **Build and Deploy**
   ```bash
   npm run build
   firebase deploy --only hosting
   ```

**firebase.json**:
```json
{
  "hosting": {
    "public": "dist",
    "ignore": [
      "firebase.json",
      "**/.*",
      "**/node_modules/**"
    ],
    "rewrites": [
      {
        "source": "**",
        "destination": "/index.html"
      }
    ],
    "headers": [
      {
        "source": "**/*.@(jpg|jpeg|gif|png|svg|webp)",
        "headers": [
          {
            "key": "Cache-Control",
            "value": "max-age=31536000"
          }
        ]
      }
    ]
  }
}
```

### Cloudflare Pages

**Why Cloudflare:**
- Fastest CDN
- DDoS protection
- Web Analytics included
- Unlimited bandwidth

#### Deployment Steps

1. **Connect Repository**
   - Go to [pages.cloudflare.com](https://pages.cloudflare.com)
   - Click "Create a project"
   - Connect GitHub

2. **Configure Build**
   ```
   Framework preset: Vite
   Build command: npm run build
   Build output directory: dist
   Root directory: web
   ```

3. **Environment Variables**
   - Add `VITE_API_URL`

4. **Deploy**
   - Push to main branch

## Backend Configuration

### CORS Setup

**Django Backend** must allow frontend origin:

```python
# backend/settings.py
CORS_ALLOWED_ORIGINS = [
    "https://plantcommunity.com",
    "https://www.plantcommunity.com",
]

# Or use wildcard (less secure)
CORS_ALLOW_ALL_ORIGINS = False  # Set to True only for development
```

### API Endpoints

Ensure backend is accessible at `VITE_API_URL`:

```bash
# Health check
curl https://api.plantcommunity.com/api/plant-identification/identify/health/

# Expected response
{
  "status": "healthy",
  "plant_id_available": true,
  "plantnet_available": true
}
```

## Performance Optimization

### CDN Configuration

**Cache Headers:**
```
# Static assets (CSS, JS, images)
Cache-Control: public, max-age=31536000, immutable

# HTML (index.html)
Cache-Control: no-cache
```

### Compression

Most platforms enable compression automatically:
- **Gzip**: ~70% size reduction
- **Brotli**: ~80% size reduction (preferred)

Verify compression:
```bash
curl -H "Accept-Encoding: br,gzip" -I https://plantcommunity.com
# Look for: Content-Encoding: br
```

### Image Optimization

**Client-side compression** already implemented (see [Performance.md](./Performance.md)).

For production, consider:
1. Image CDN (Cloudinary, imgix)
2. WebP/AVIF format support
3. Responsive images with srcset

## Monitoring

### Error Tracking (Sentry)

1. **Install Sentry**
   ```bash
   npm install @sentry/react
   ```

2. **Initialize** (`src/main.jsx`):
   ```javascript
   import * as Sentry from '@sentry/react'

   if (import.meta.env.PROD) {
     Sentry.init({
       dsn: import.meta.env.VITE_SENTRY_DSN,
       integrations: [
         new Sentry.BrowserTracing(),
         new Sentry.Replay(),
       ],
       tracesSampleRate: 0.1,
       replaysSessionSampleRate: 0.1,
       replaysOnErrorSampleRate: 1.0,
     })
   }
   ```

3. **Set environment variable**:
   ```bash
   VITE_SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
   ```

### Analytics (Google Analytics 4)

1. **Add GA4** (`index.html`):
   ```html
   <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
   <script>
     window.dataLayer = window.dataLayer || [];
     function gtag(){dataLayer.push(arguments);}
     gtag('js', new Date());
     gtag('config', 'G-XXXXXXXXXX');
   </script>
   ```

2. **Or use react-ga4**:
   ```bash
   npm install react-ga4
   ```

   ```javascript
   import ReactGA from 'react-ga4'

   if (import.meta.env.PROD) {
     ReactGA.initialize(import.meta.env.VITE_GA_MEASUREMENT_ID)
   }
   ```

### Performance Monitoring

**Lighthouse CI:**
```bash
npm install -g @lhci/cli

# Run Lighthouse
lhci autorun --upload.target=temporary-public-storage
```

**Web Vitals:**
```javascript
import { getCLS, getFID, getLCP } from 'web-vitals'

getCLS(console.log)
getFID(console.log)
getLCP(console.log)
```

## Security

### Content Security Policy

Add CSP headers via hosting platform:

**Vercel** (`vercel.json`):
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; img-src 'self' data: blob:; connect-src 'self' https://api.plantcommunity.com; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com;"
        }
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
    Content-Security-Policy = "default-src 'self'; img-src 'self' data: blob:; connect-src 'self' https://api.plantcommunity.com;"
```

### HTTPS

All platforms provide free SSL certificates:
- Vercel: Automatic via Let's Encrypt
- Netlify: Automatic via Let's Encrypt
- Firebase: Automatic via Google
- Cloudflare: Automatic

**Force HTTPS:**
```javascript
// Redirect HTTP to HTTPS in production
if (import.meta.env.PROD && window.location.protocol !== 'https:') {
  window.location.href = 'https:' + window.location.href.substring(window.location.protocol.length)
}
```

## CI/CD Pipeline

### GitHub Actions (Example)

`.github/workflows/deploy.yml`:
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
    paths:
      - 'web/**'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd web
          npm ci

      - name: Build
        env:
          VITE_API_URL: ${{ secrets.VITE_API_URL }}
        run: |
          cd web
          npm run build

      - name: Run tests (future)
        run: |
          cd web
          npm run test

      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.ORG_ID }}
          vercel-project-id: ${{ secrets.PROJECT_ID }}
          working-directory: ./web
```

## Rollback Strategy

### Vercel

```bash
# List deployments
vercel ls

# Rollback to specific deployment
vercel rollback <deployment-url>
```

### Netlify

```bash
# Via Netlify CLI
netlify deploy --prod --alias previous-version

# Or in dashboard: Deploys → Select previous → Publish deploy
```

### Git-Based Rollback

```bash
# Revert to previous commit
git revert HEAD
git push origin main

# Automatic redeploy with previous code
```

## Pre-Deployment Checklist

- [ ] Environment variables configured
- [ ] Backend API accessible
- [ ] CORS properly configured
- [ ] Build succeeds locally (`npm run build`)
- [ ] Preview build works (`npm run preview`)
- [ ] All tests pass (when implemented)
- [ ] No console errors in production build
- [ ] Analytics configured
- [ ] Error tracking enabled
- [ ] Lighthouse score > 90
- [ ] Custom domain configured (if applicable)
- [ ] SSL certificate active
- [ ] Monitoring dashboards set up

## Post-Deployment Verification

```bash
# 1. Health check
curl https://plantcommunity.com

# 2. API connectivity
# Open browser console on site, check for API errors

# 3. Lighthouse audit
npx lighthouse https://plantcommunity.com --view

# 4. Check monitoring
# - Sentry dashboard
# - Google Analytics real-time
# - Hosting platform metrics

# 5. Test critical flows
# - Upload image
# - Identify plant
# - View results
```

## Troubleshooting

### Build Fails

**Error:** `npm run build` fails

**Solutions:**
```bash
# Clear cache
rm -rf node_modules dist
npm install
npm run build

# Check Node version
node --version  # Should be 18+

# Verbose output
npm run build -- --mode production --debug
```

### CORS Errors

**Error:** "No 'Access-Control-Allow-Origin' header"

**Solutions:**
1. Verify backend CORS configuration
2. Check `VITE_API_URL` is correct
3. Ensure backend is running
4. Check browser console for exact error

### 404 on Refresh

**Error:** Page refresh returns 404

**Solution:** Configure SPA fallback:

**Vercel** (`vercel.json`):
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

**Netlify** (`_redirects` in `public/`):
```
/*    /index.html   200
```

### Slow Loading

**Solutions:**
1. Verify CDN is working
2. Check network tab for large assets
3. Enable compression (Gzip/Brotli)
4. Optimize images
5. Run Lighthouse audit

## Cost Estimates

### Free Tier Limits

| Platform | Free Tier | Bandwidth | Builds |
|----------|-----------|-----------|--------|
| Vercel | 100 GB/month | Unlimited | Unlimited |
| Netlify | 100 GB/month | Unlimited | 300 min/month |
| Firebase | 10 GB/month | 360 MB/day | N/A |
| Cloudflare | Unlimited | Unlimited | 500 builds/month |

### Production Costs (Estimated)

**Assumptions:**
- 10,000 monthly active users
- 5 pages per session average
- 70KB average page size
- 50,000 page views/month

**Bandwidth:**
```
50,000 views × 70KB = 3.5GB/month
```

**All platforms: $0/month** (within free tier)

## Summary

**Recommended Setup:**
1. **Hosting**: Vercel (best DX, auto-deploy)
2. **Monitoring**: Sentry (errors) + GA4 (analytics)
3. **CDN**: Included with hosting platform
4. **SSL**: Automatic with hosting
5. **Deployment**: GitHub push → auto-deploy

**Deployment Time:**
- First deploy: ~15 minutes (including setup)
- Subsequent deploys: ~2 minutes (auto-deploy)

For more information:
- [Architecture.md](./Architecture.md) - System design
- [Performance.md](./Performance.md) - Optimization strategies
- [API-Integration.md](./API-Integration.md) - Backend setup
