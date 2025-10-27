# UI Modernization & Navigation Work Plan

**Project**: Plant ID Community Web Application
**Goal**: Implement consistent navigation, modern UI design, and authentication interface
**Status**: Planning
**Created**: October 25, 2025

---

## Executive Summary

### Current Issues Identified
1. ❌ **No consistent header/navigation** - Each page is standalone
2. ❌ **No authentication UI** - No login/logout interface
3. ❌ **Inconsistent page layouts** - Some pages have headers, some don't
4. ❌ **No shared layout structure** - Code duplication across pages
5. ❌ **No user account functionality** - Cannot see logged-in state

### Proposed Solution
Implement a modern, responsive UI with:
- Shared layout component with persistent header/footer
- Responsive navigation with mobile menu
- Authentication UI (login/signup/logout)
- Protected routes for user-specific features
- Consistent design system using Tailwind CSS 4
- WCAG 2.2 accessibility compliance

### Tech Stack
- **React 19** - Latest React features
- **React Router DOM v7.9.4** - Layout routes with `<Outlet />`
- **Tailwind CSS 4** - Modern design system with `@theme` directive
- **Vite 7** - Build tool
- **Lucide React** - Icon library (already installed)

---

## Implementation Phases

### 📋 Phase 1: Layout Infrastructure (Foundation)
**Estimated Time**: 2-3 hours
**Priority**: HIGH - Blocks all other UI work

#### Tasks

**1.1 Create RootLayout Component** ✅
- [ ] Create `/web/src/layouts/RootLayout.jsx`
- [ ] Add `<Outlet />` for child routes
- [ ] Include Header and Footer placeholders
- [ ] Use flexbox for sticky footer pattern

**Files to Create:**
```
/web/src/layouts/
├── RootLayout.jsx       # Main layout with header/footer
└── ProtectedLayout.jsx  # Auth-protected layout (Phase 3)
```

**Code Template:**
```jsx
// layouts/RootLayout.jsx
import { Outlet } from 'react-router-dom'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'

export default function RootLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
```

**1.2 Update App.jsx Routing** ✅
- [ ] Import `RootLayout`
- [ ] Wrap existing routes with layout route
- [ ] Test that header/footer persist across navigation

**Updated Structure:**
```jsx
// App.jsx
<Routes>
  <Route element={<RootLayout />}>
    <Route path="/" element={<HomePage />} />
    <Route path="/identify" element={<IdentifyPage />} />
    <Route path="/blog" element={<BlogListPage />} />
    <Route path="/blog/:slug" element={<BlogDetailPage />} />
    <Route path="/forum" element={<ForumPage />} />
  </Route>
</Routes>
```

**1.3 Clean Up Existing Pages** ✅
- [ ] Remove individual back links from pages
- [ ] Remove page-specific headers (IdentifyPage has one)
- [ ] Remove gradient backgrounds from pages (move to layout if needed)
- [ ] Ensure pages focus on content only

**Success Criteria:**
- ✅ Header and footer visible on all pages
- ✅ Navigation between pages preserves header/footer (no re-mount)
- ✅ All pages render correctly inside layout

---

### 📋 Phase 2: Responsive Header & Navigation
**Estimated Time**: 3-4 hours
**Priority**: HIGH - Core UX improvement

#### Tasks

**2.1 Create Header Component** ✅
- [ ] Create `/web/src/components/layout/Header.jsx`
- [ ] Add logo and app name
- [ ] Add desktop navigation (Identify, Blog, Community)
- [ ] Add mobile hamburger menu button
- [ ] Implement mobile menu with slide-in animation
- [ ] Add login/signup buttons (non-functional initially)

**Files to Create:**
```
/web/src/components/layout/
├── Header.jsx          # Main navigation header
├── Footer.jsx          # Footer component
└── UserMenu.jsx        # User dropdown menu (Phase 3)
```

**2.2 Desktop Navigation** ✅
- [ ] Use Tailwind `md:flex hidden` pattern for desktop-only nav
- [ ] Use `NavLink` from React Router for active states
- [ ] Style active links with green accent
- [ ] Add hover effects with smooth transitions

**2.3 Mobile Navigation** ✅
- [ ] Hamburger icon from Lucide React (`Menu`, `X` icons)
- [ ] Mobile menu with `useState` toggle
- [ ] Slide animation for menu open/close
- [ ] Close menu when link is clicked
- [ ] Click outside to close (useRef + useEffect)

**2.4 Sticky Header** ✅
- [ ] Add `sticky top-0 z-50` classes
- [ ] White background with subtle border
- [ ] Shadow on scroll (optional enhancement)

**2.5 Accessibility** ✅
- [ ] Add `aria-label` to menu button
- [ ] Add `aria-expanded` state
- [ ] Ensure keyboard navigation works
- [ ] Test with screen reader

**Code Reference:**
```jsx
// Key Tailwind classes for sticky header
className="bg-white border-b border-gray-200 sticky top-0 z-50"

// Responsive pattern
<div className="hidden md:flex items-center gap-8">
  {/* Desktop nav */}
</div>
<button className="md:hidden">
  {/* Mobile menu button */}
</button>
```

**Success Criteria:**
- ✅ Header visible on all pages
- ✅ Desktop navigation shows 3+ links
- ✅ Mobile menu toggles correctly
- ✅ Active page highlighted
- ✅ Header stays at top when scrolling

---

### 📋 Phase 3: Authentication System
**Estimated Time**: 4-5 hours
**Priority**: HIGH - Required for user features

#### Tasks

**3.1 Create Authentication Context** ✅
- [ ] Create `/web/src/contexts/AuthContext.jsx`
- [ ] Implement login, logout, signup functions
- [ ] Store user state in context
- [ ] Add loading and error states
- [ ] Persist auth with localStorage (or cookies)

**Files to Create:**
```
/web/src/
├── contexts/
│   └── AuthContext.jsx     # Auth state management
├── hooks/
│   └── useAuth.js          # Custom hook for auth
└── services/
    └── authService.js      # API integration
```

**3.2 Create Auth Service** ✅
- [ ] Create `/web/src/services/authService.js`
- [ ] Implement `login(credentials)` API call
- [ ] Implement `signup(userData)` API call
- [ ] Implement `logout()` API call
- [ ] Implement `getCurrentUser()` for session check
- [ ] Handle JWT token storage (HttpOnly cookies preferred)

**Backend Integration:**
```javascript
// authService.js - API endpoints
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

POST ${API_URL}/api/v1/users/login/
POST ${API_URL}/api/v1/users/signup/
POST ${API_URL}/api/v1/users/logout/
GET  ${API_URL}/api/v1/users/me/
```

**3.3 Create useAuth Hook** ✅
- [ ] Create `/web/src/hooks/useAuth.js`
- [ ] Export hook that consumes AuthContext
- [ ] Throw error if used outside provider
- [ ] Type-safe return value

**3.4 Wrap App with AuthProvider** ✅
- [ ] Update `/web/src/main.jsx`
- [ ] Wrap `<App />` with `<AuthProvider>`
- [ ] Test auth state persistence

**Code Template:**
```jsx
// main.jsx
import { AuthProvider } from './contexts/AuthContext'

root.render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
)
```

**Success Criteria:**
- ✅ Auth context accessible in all components
- ✅ User state persists across page refreshes
- ✅ Login/logout state updates immediately
- ✅ Error handling works correctly

---

### 📋 Phase 4: Login & Signup Pages
**Estimated Time**: 3-4 hours
**Priority**: HIGH - User-facing auth

#### Tasks

**4.1 Create LoginPage** ✅
- [ ] Create `/web/src/pages/auth/LoginPage.jsx`
- [ ] Email/password form with validation
- [ ] Error message display
- [ ] Loading state during submission
- [ ] Redirect to home after successful login
- [ ] "Sign up" link for new users

**Files to Create:**
```
/web/src/pages/auth/
├── LoginPage.jsx
└── SignupPage.jsx
```

**4.2 Create SignupPage** ✅
- [ ] Create `/web/src/pages/auth/SignupPage.jsx`
- [ ] Name, email, password form
- [ ] Password confirmation field
- [ ] Client-side validation
- [ ] Error handling
- [ ] Redirect to home after signup
- [ ] "Log in" link for existing users

**4.3 Form Components** ✅
- [ ] Create reusable `Input` component
- [ ] Create reusable `Button` component
- [ ] Add form validation utilities
- [ ] Add error message component

**4.4 Update Header** ✅
- [ ] Show login/signup buttons when logged out
- [ ] Show user menu when logged in
- [ ] Test state transitions

**Form Validation Example:**
```javascript
// utils/validation.js
export function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

export function validatePassword(password) {
  return password.length >= 8
}
```

**Success Criteria:**
- ✅ Login form works end-to-end
- ✅ Signup form works end-to-end
- ✅ Validation errors display correctly
- ✅ User redirected after auth
- ✅ Header updates to show logged-in state

---

### 📋 Phase 5: Protected Routes & User Menu
**Estimated Time**: 2-3 hours
**Priority**: MEDIUM - Enhanced UX

#### Tasks

**5.1 Create ProtectedLayout** ✅
- [ ] Create `/web/src/layouts/ProtectedLayout.jsx`
- [ ] Check authentication state
- [ ] Redirect to `/login` if not authenticated
- [ ] Show loading spinner during check
- [ ] Render `<Outlet />` for protected content

**5.2 Create UserMenu Component** ✅
- [ ] Create `/web/src/components/layout/UserMenu.jsx`
- [ ] User avatar or initials
- [ ] Dropdown menu with Profile, Settings, Logout
- [ ] Click outside to close
- [ ] Smooth transitions

**5.3 Add Protected Routes** ✅
- [ ] Wrap private routes with `<ProtectedLayout>`
- [ ] Create placeholder pages for My Garden, Profile
- [ ] Test authentication redirects

**Protected Routes Example:**
```jsx
// App.jsx
<Route element={<ProtectedLayout />}>
  <Route element={<RootLayout />}>
    <Route path="/my-garden" element={<MyGardenPage />} />
    <Route path="/profile" element={<ProfilePage />} />
  </Route>
</Route>
```

**5.4 Update Header** ✅
- [ ] Replace login/signup buttons with `<UserMenu />` when authenticated
- [ ] Show user name or avatar
- [ ] Test logout flow

**Success Criteria:**
- ✅ Unauthenticated users redirected to login
- ✅ User menu displays for logged-in users
- ✅ Logout works correctly
- ✅ Protected pages accessible only when logged in

---

### 📋 Phase 6: UI Component Library
**Estimated Time**: 2-3 hours
**Priority**: MEDIUM - Code reusability

#### Tasks

**6.1 Create Button Component** ✅
- [ ] Create `/web/src/components/ui/Button.jsx`
- [ ] Variants: primary, secondary, outline, ghost
- [ ] Sizes: sm, md, lg
- [ ] Disabled state
- [ ] Loading state with spinner
- [ ] PropTypes documentation

**Files to Create:**
```
/web/src/components/ui/
├── Button.jsx
├── Input.jsx
├── Card.jsx
└── Badge.jsx
```

**6.2 Create Input Component** ✅
- [ ] Text, email, password types
- [ ] Label and error message support
- [ ] Focus states
- [ ] Required field indicator
- [ ] PropTypes

**6.3 Create Card Component** ✅
- [ ] Reusable card wrapper
- [ ] Variants: default, bordered, elevated
- [ ] Padding options
- [ ] Use in blog and feature cards

**6.4 Replace Hardcoded Components** ✅
- [ ] Update pages to use new UI components
- [ ] Update forms to use `<Input />`
- [ ] Update CTAs to use `<Button />`
- [ ] Test all pages still work

**Component API Example:**
```jsx
<Button variant="primary" size="md" loading={isSubmitting}>
  Submit
</Button>

<Input
  type="email"
  label="Email address"
  error={errors.email}
  required
/>
```

**Success Criteria:**
- ✅ All UI components reusable
- ✅ Consistent styling across app
- ✅ PropTypes documented
- ✅ No duplicate button/input code

---

### 📋 Phase 7: Design System & Polish
**Estimated Time**: 2-3 hours
**Priority**: LOW - Visual consistency

#### Tasks

**7.1 Tailwind Design Tokens** ✅
- [ ] Create `/web/src/styles/app.css` with `@theme` directive
- [ ] Define color palette (primary, secondary, gray scale)
- [ ] Define spacing scale
- [ ] Define border radius values
- [ ] Define typography scale

**Tailwind 4 Config Example:**
```css
/* app.css */
@theme {
  --color-primary: #16a34a;
  --color-primary-hover: #15803d;
  --color-secondary: #10b981;
  --color-gray-50: #f9fafb;
  --color-gray-900: #111827;

  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;

  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
}
```

**7.2 Footer Component** ✅
- [ ] Create `/web/src/components/layout/Footer.jsx`
- [ ] Add site links (About, Privacy, Terms)
- [ ] Add social media icons (optional)
- [ ] Copyright notice
- [ ] Responsive layout

**7.3 Consistent Page Spacing** ✅
- [ ] Add standard container classes
- [ ] Add consistent padding/margins
- [ ] Ensure all pages use same max-width
- [ ] Test responsive behavior

**7.4 Loading States** ✅
- [ ] Create loading spinner component
- [ ] Add to authentication flows
- [ ] Add to page transitions
- [ ] Consistent styling

**7.5 Error States** ✅
- [ ] Create error message component
- [ ] Style form validation errors
- [ ] Style API error messages
- [ ] 404 page (optional)

**Success Criteria:**
- ✅ Consistent colors across all pages
- ✅ Consistent spacing and typography
- ✅ Footer on all pages
- ✅ Professional, polished appearance

---

### 📋 Phase 8: Testing & Accessibility
**Estimated Time**: 2-3 hours
**Priority**: HIGH - Production readiness

#### Tasks

**8.1 Manual Testing** ✅
- [ ] Test all navigation links work
- [ ] Test login/logout flow end-to-end
- [ ] Test signup flow end-to-end
- [ ] Test protected routes redirect correctly
- [ ] Test mobile menu on real device
- [ ] Test responsive breakpoints (mobile, tablet, desktop)

**8.2 Keyboard Navigation** ✅
- [ ] Tab through all navigation links
- [ ] Enter/Space keys work on buttons
- [ ] Escape closes mobile menu
- [ ] Focus visible on all interactive elements

**8.3 Screen Reader Testing** ✅
- [ ] Test with VoiceOver (macOS) or NVDA (Windows)
- [ ] Verify ARIA labels announced correctly
- [ ] Verify link purposes clear
- [ ] Verify form labels associated

**8.4 Browser Testing** ✅
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

**8.5 Performance** ✅
- [ ] Check Lighthouse scores
- [ ] Optimize image loading
- [ ] Check bundle size
- [ ] Test on slow 3G network

**Testing Checklist:**
```
Desktop:
- [ ] Homepage loads correctly
- [ ] Navigation links work
- [ ] Login flow works
- [ ] Signup flow works
- [ ] Logout works
- [ ] Protected routes work

Mobile:
- [ ] Hamburger menu toggles
- [ ] Menu links work
- [ ] Forms usable on mobile
- [ ] Buttons tappable (44px min)
- [ ] Text readable (16px min)

Accessibility:
- [ ] Color contrast sufficient (4.5:1)
- [ ] Focus indicators visible
- [ ] Keyboard navigation works
- [ ] Screen reader announces correctly
- [ ] Semantic HTML used
```

**Success Criteria:**
- ✅ All features work on desktop and mobile
- ✅ Keyboard navigation fully functional
- ✅ Screen reader compatible
- ✅ Lighthouse accessibility score > 90
- ✅ No console errors

---

## File Structure After Implementation

```
/web/src/
├── components/
│   ├── layout/
│   │   ├── Header.jsx          ✅ Responsive nav with mobile menu
│   │   ├── Footer.jsx          ✅ Site footer
│   │   └── UserMenu.jsx        ✅ User dropdown menu
│   ├── ui/
│   │   ├── Button.jsx          ✅ Reusable button component
│   │   ├── Input.jsx           ✅ Reusable input component
│   │   ├── Card.jsx            ✅ Reusable card component
│   │   └── LoadingSpinner.jsx  ✅ Loading indicator
│   ├── BlogCard.jsx            (existing)
│   ├── StreamFieldRenderer.jsx (existing)
│   └── PlantIdentification/    (existing)
│       ├── FileUpload.jsx
│       └── IdentificationResults.jsx
├── pages/
│   ├── HomePage.jsx            (update: remove gradient, use layout)
│   ├── IdentifyPage.jsx        (update: remove header, use layout)
│   ├── BlogListPage.jsx        (update: use layout)
│   ├── BlogDetailPage.jsx      (update: use layout)
│   ├── ForumPage.jsx           (update: use layout)
│   ├── auth/
│   │   ├── LoginPage.jsx       ✅ NEW
│   │   └── SignupPage.jsx      ✅ NEW
│   ├── MyGardenPage.jsx        ✅ NEW (placeholder)
│   └── ProfilePage.jsx         ✅ NEW (placeholder)
├── layouts/
│   ├── RootLayout.jsx          ✅ NEW - Main layout with header/footer
│   └── ProtectedLayout.jsx     ✅ NEW - Auth-protected layout
├── contexts/
│   └── AuthContext.jsx         ✅ NEW - Auth state management
├── hooks/
│   └── useAuth.js              ✅ NEW - Auth hook
├── services/
│   ├── authService.js          ✅ NEW - Auth API calls
│   ├── blogService.js          (existing)
│   └── plantIdService.js       (existing)
├── utils/
│   ├── validation.js           ✅ NEW - Form validation
│   ├── formatDate.js           (existing)
│   └── sanitize.js             (existing)
├── styles/
│   └── app.css                 ✅ Update with @theme tokens
├── App.jsx                     ✅ Update with layout routes
└── main.jsx                    ✅ Update with AuthProvider
```

**Total New Files**: ~15 files
**Total Updated Files**: ~8 files

---

## Priority Order (Suggested Implementation)

### Week 1: Foundation
1. **Phase 1** - Layout Infrastructure (RootLayout, update App.jsx)
2. **Phase 2** - Header & Navigation (responsive nav, mobile menu)

### Week 2: Authentication
3. **Phase 3** - Authentication System (context, service, hooks)
4. **Phase 4** - Login & Signup Pages (forms, validation)

### Week 3: Enhancements
5. **Phase 5** - Protected Routes & User Menu (ProtectedLayout, UserMenu)
6. **Phase 6** - UI Component Library (Button, Input, Card)

### Week 4: Polish
7. **Phase 7** - Design System & Polish (tokens, footer, consistency)
8. **Phase 8** - Testing & Accessibility (manual, keyboard, screen reader)

---

## Backend Requirements

### API Endpoints Needed

The backend already has authentication endpoints at `/api/v1/users/`. Verify these exist:

```
POST /api/v1/users/login/
- Body: { email, password }
- Response: { user, token }
- Sets HttpOnly cookie with JWT

POST /api/v1/users/signup/
- Body: { name, email, password }
- Response: { user, token }
- Sets HttpOnly cookie with JWT

POST /api/v1/users/logout/
- Clears HttpOnly cookie
- Response: { success: true }

GET /api/v1/users/me/
- Requires authentication (cookie)
- Response: { user }
```

### CORS Configuration

Already configured in `backend/plant_community_backend/settings.py`:
```python
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5174',  # React dev server
    'http://127.0.0.1:5174',
]
CORS_ALLOW_CREDENTIALS = True  # Required for cookies
```

### Session Management

Backend uses **Cookie-based JWT authentication** (Week 4 implementation):
- JWT tokens stored in HttpOnly cookies (XSS protection)
- Session timeout: 24 hours
- Token refresh on activity
- Account lockout after 10 failed attempts

---

## Testing Strategy

### Unit Tests (Vitest)
```bash
# Test individual components
npm run test

# Watch mode during development
npm run test:watch

# With coverage
npm run test:coverage
```

**Test Files to Create:**
```
/web/src/components/layout/__tests__/
├── Header.test.jsx
├── Footer.test.jsx
└── UserMenu.test.jsx

/web/src/components/ui/__tests__/
├── Button.test.jsx
└── Input.test.jsx

/web/src/contexts/__tests__/
└── AuthContext.test.jsx
```

### Integration Tests
- [ ] Test complete auth flow (signup → login → logout)
- [ ] Test protected route redirects
- [ ] Test navigation between pages
- [ ] Test mobile menu interactions

### E2E Tests (Optional - Playwright)
```bash
# Install Playwright
npm install -D @playwright/test

# Run E2E tests
npx playwright test
```

---

## Accessibility Checklist (WCAG 2.2 Level AA)

### Perceivable
- [ ] Color contrast ratio ≥ 4.5:1 for text
- [ ] Color is not the only visual means of conveying information
- [ ] Text can be resized up to 200% without loss of content
- [ ] Images have alt text (if applicable)

### Operable
- [ ] All functionality available via keyboard
- [ ] No keyboard trap (can navigate away from all elements)
- [ ] Skip navigation link (optional enhancement)
- [ ] Focus visible on all interactive elements
- [ ] Sufficient time for reading and using content
- [ ] Headings and labels describe topic or purpose

### Understandable
- [ ] Page language identified (`<html lang="en">`)
- [ ] Navigation consistent across pages
- [ ] Form inputs have associated labels
- [ ] Error messages clear and helpful
- [ ] Instructions provided where needed

### Robust
- [ ] Valid HTML (semantic elements)
- [ ] ARIA attributes used correctly
- [ ] Compatible with assistive technologies
- [ ] Name, role, value available for all UI components

**Testing Tools:**
- WAVE browser extension
- axe DevTools
- Lighthouse accessibility audit
- Screen reader (VoiceOver, NVDA)

---

## Performance Targets

### Lighthouse Scores (Target)
- Performance: ≥ 90
- Accessibility: ≥ 95
- Best Practices: ≥ 95
- SEO: ≥ 90

### Bundle Size
- Main bundle: < 200KB (gzipped)
- Use code splitting for large pages

### Load Times
- First Contentful Paint (FCP): < 1.5s
- Largest Contentful Paint (LCP): < 2.5s
- Time to Interactive (TTI): < 3.5s

---

## Success Metrics

### User Experience
- [ ] Users can navigate between all pages
- [ ] Users can log in and see their account
- [ ] Users can access protected features
- [ ] Mobile users can use hamburger menu
- [ ] Design feels modern and professional

### Technical
- [ ] No console errors or warnings
- [ ] All routes work correctly
- [ ] Authentication persists across refreshes
- [ ] Responsive at all breakpoints (320px - 1920px)
- [ ] Lighthouse scores meet targets

### Code Quality
- [ ] No duplicate navigation code
- [ ] Reusable UI components used throughout
- [ ] TypeScript types (if using TS)
- [ ] PropTypes documented
- [ ] Code follows project conventions

---

## Risk Mitigation

### Potential Issues

**1. Backend API not ready**
- **Mitigation**: Use mock API service with localStorage
- **Timeline**: 1 hour to create mock service

**2. CORS issues with cookies**
- **Mitigation**: Backend already configured, verify `CORS_ALLOW_CREDENTIALS = True`
- **Timeline**: 30 minutes to troubleshoot

**3. Mobile menu not working on real devices**
- **Mitigation**: Test early, use standard React patterns
- **Timeline**: 1 hour debugging

**4. Authentication state lost on refresh**
- **Mitigation**: Check cookie expiry, implement refresh token
- **Timeline**: 2 hours to debug and fix

**5. Accessibility issues**
- **Mitigation**: Use semantic HTML from start, test incrementally
- **Timeline**: Built into each phase

---

## Next Steps

### Immediate Actions (This Week)
1. **Review this plan** with team/stakeholders
2. **Set up development branch**: `git checkout -b feature/ui-modernization`
3. **Start Phase 1**: Create RootLayout and update App.jsx
4. **Test layout** works on all existing pages

### Questions to Answer
- [ ] Are backend auth endpoints ready?
- [ ] Do we need password reset functionality?
- [ ] Do we need email verification?
- [ ] What user profile fields are needed?
- [ ] Do we need social login (Google, GitHub)?

### Optional Enhancements (Future)
- Dark mode toggle
- User avatar upload
- Email notifications
- Remember me checkbox
- Password strength indicator
- Social authentication
- Two-factor authentication (2FA)

---

## Resources

### Documentation
- React Router v7: https://reactrouter.com/en/main
- Tailwind CSS 4: https://tailwindcss.com/docs
- React 19: https://react.dev/
- Lucide Icons: https://lucide.dev/

### Design Inspiration
- https://flowbite.com/docs/components/navbar/
- https://headlessui.com/
- https://www.radix-ui.com/

### Accessibility
- WCAG 2.2: https://www.w3.org/WAI/WCAG22/quickref/
- MDN Accessibility: https://developer.mozilla.org/en-US/docs/Web/Accessibility

---

## Conclusion

This plan provides a comprehensive, phased approach to modernizing the Plant ID Community web application UI. Each phase builds on the previous one, with clear success criteria and testing requirements.

**Estimated Total Time**: 20-25 hours of development work across 8 phases

**Key Benefits:**
- ✅ Consistent navigation across all pages
- ✅ Modern, professional UI
- ✅ Full authentication flow
- ✅ Protected routes for user features
- ✅ Responsive design (mobile-first)
- ✅ Accessible to all users
- ✅ Maintainable, reusable components

Once complete, the application will have a solid foundation for future feature development with a professional, user-friendly interface.
