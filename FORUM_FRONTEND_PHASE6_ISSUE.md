# Forum Frontend Phase 6: React Web Interface

## Overview

Implement React 19 web frontend for the forum, providing a complete Discourse-like community discussion platform. This phase builds on the production-ready backend API (Phase 2c: 96/96 tests passing, Grade A 95/100) to deliver core components, thread management, and post creation functionality.

**Target Users**: Web users on desktop and tablet devices
**Duration**: 2-3 weeks (Weeks 14-15 in master plan)
**Branch**: `feature/forum-phase6-frontend`
**Dependencies**: Phase 2c backend API (✅ complete)

---

## Problem Statement

Currently, the forum web interface shows only a "Coming soon..." placeholder despite having a fully functional backend API with:
- 6 database models (Category, Thread, Post, Attachment, Reaction, UserProfile)
- 12+ REST API endpoints with pagination, filtering, search
- Permissions system with trust levels
- 96/96 tests passing (100% test coverage)

**User Impact**: Web users cannot participate in forum discussions, limiting community engagement to mobile users once Flutter app is built.

---

## Proposed Solution

Build a React 19 web interface following the proven blog implementation pattern:
- **Core Components**: CategoryCard, ThreadCard, PostCard, TipTapEditor
- **Page Routes**: CategoryList (`/forum`), ThreadList (`/forum/:categorySlug`), ThreadDetail (`/forum/:categorySlug/:threadSlug`)
- **Features**: Search, filters, pagination, rich text editing, reactions
- **Security**: DOMPurify XSS protection, CSRF tokens, authentication checks
- **Performance**: Code splitting, memoization, lazy loading

---

## Technical Approach

### Architecture Pattern (Reference: Blog Implementation)

**Follow existing patterns from**:
```
BlogListPage → ThreadListPage     (search, filters, pagination)
BlogDetailPage → ThreadDetailPage   (breadcrumbs, metadata, content)
BlogCard → ThreadCard               (memoized, compact mode)
blogService.js → forumService.js    (API integration)
sanitize.js → Add FORUM preset      (XSS protection)
```

**Technology Stack**:
- React 19.1.1 (useOptimistic, Suspense)
- React Router 7.9.4 (nested routes, lazy loading)
- Tailwind CSS 4.1.16 (@theme directive)
- TipTap 2.x (rich text editor, replaces deprecated Draft.js)
- DOMPurify (XSS sanitization)
- Vitest + React Testing Library (component tests)

### Component Structure

```
web/src/
├── pages/forum/
│   ├── CategoryListPage.jsx       # /forum (categories overview)
│   ├── ThreadListPage.jsx         # /forum/:categorySlug (threads in category)
│   └── ThreadDetailPage.jsx       # /forum/:categorySlug/:threadSlug (posts)
│
├── components/forum/
│   ├── CategoryCard.jsx           # Category preview with stats
│   ├── ThreadCard.jsx             # Thread preview in list
│   ├── PostCard.jsx               # Single post with reactions
│   └── TipTapEditor.jsx           # Rich text editor wrapper
│
├── services/
│   └── forumService.js            # API integration layer
│
└── tests/
    └── forumUtils.js              # Mock data factories
```

### Backend API Endpoints (Already Implemented)

```
Base URL: /api/v1/forum/

Categories:
  GET /categories/              → List all
  GET /categories/tree/         → Hierarchical structure
  GET /categories/{slug}/       → Single category

Threads:
  GET /threads/                 → List (paginated, filtered)
  GET /threads/{slug}/          → Detail + first post
  POST /threads/                → Create (auth + trust_level)
  PATCH /threads/{slug}/        → Update (author or moderator)
  DELETE /threads/{slug}/       → Delete (author or moderator)

Posts:
  GET /posts/?thread={slug}     → Posts in thread
  POST /posts/                  → Create post (auth)
  PATCH /posts/{id}/            → Update (author or moderator)
  DELETE /posts/{id}/           → Soft delete

Reactions:
  POST /reactions/              → Add reaction (like/love/helpful/thanks)
  DELETE /reactions/{id}/       → Remove reaction
  GET /reactions/?post={id}     → Reactions on post
```

---

## Implementation Phases

### Phase 1: Foundation (Days 1-2)

**Goal**: Set up API integration and test utilities

**Tasks**:
1. **Install Dependencies**
   ```bash
   npm install @tiptap/react @tiptap/pm @tiptap/starter-kit
   npm install @tiptap/extension-link @tiptap/extension-placeholder
   npm install date-fns  # If not already installed
   ```

2. **Create Forum Service** (`web/src/services/forumService.js`):
   - `fetchCategories()`, `fetchCategoryTree()`, `fetchCategory(slug)`
   - `fetchThreads(options)`, `fetchThread(slug)`, `createThread(data)`
   - `fetchPosts(options)`, `createPost(data)`, `updatePost()`, `deletePost()`
   - `addReaction()`, `removeReaction()`, `fetchReactions()`
   - CSRF token handling, authentication headers
   - Error handling, JSDoc documentation

3. **Add XSS Protection** (`web/src/utils/sanitize.js`):
   ```javascript
   FORUM: {
     ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li',
                     'h2', 'h3', 'blockquote', 'code', 'pre', 'img'],
     ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt', 'title'],
     ALLOWED_CLASSES: { code: ['language-*'] },
   }
   ```

4. **Create Test Utilities** (`web/src/tests/forumUtils.js`):
   - `createMockCategory(overrides)`
   - `createMockThread(overrides)`
   - `createMockPost(overrides)`
   - `createMockReaction(overrides)`

**Deliverables**:
- [ ] `forumService.js` with 12+ API functions
- [ ] FORUM sanitization preset
- [ ] Mock data factories
- [ ] All dependencies installed

---

### Phase 2: Category & Thread Components (Days 3-4)

**Goal**: Build reusable card components

**Tasks**:
1. **CategoryCard Component** (`web/src/components/forum/CategoryCard.jsx`):
   - Category icon, name, description
   - Thread count, post count stats
   - Subcategories list
   - Link to `/forum/{slug}`
   - Memoized, PropTypes validation

2. **ThreadCard Component** (`web/src/components/forum/ThreadCard.jsx`):
   - Thread title, excerpt, author
   - Pinned/locked badges
   - Post count, view count, last activity
   - Compact mode support
   - Date formatting with `date-fns`
   - Memoized, PropTypes validation

**Deliverables**:
- [ ] CategoryCard component
- [ ] ThreadCard component
- [ ] Components follow blog pattern (memoization, PropTypes)

---

### Phase 3: List Pages (Days 5-6)

**Goal**: Category and thread listing with search/filters

**Tasks**:
1. **CategoryListPage** (`web/src/pages/forum/CategoryListPage.jsx`):
   - Fetch categories from `/categories/tree/`
   - Display with CategoryCard components
   - Loading spinner, error handling
   - Empty state message

2. **ThreadListPage** (`web/src/pages/forum/ThreadListPage.jsx`):
   - Fetch category and threads
   - Breadcrumb navigation: Forums › Category
   - Search form (query parameter)
   - Sort dropdown (recent, newest, popular)
   - Pagination (20 threads per page)
   - "New Thread" button (protected route)
   - Active filters display with clear button

3. **Update Routing** (`web/src/App.jsx`):
   ```javascript
   const CategoryListPage = lazy(() => import('./pages/forum/CategoryListPage'));
   const ThreadListPage = lazy(() => import('./pages/forum/ThreadListPage'));

   // Routes:
   { path: '/forum', element: <Suspense><CategoryListPage /></Suspense> }
   { path: '/forum/:categorySlug', element: <Suspense><ThreadListPage /></Suspense> }
   ```

4. **Update Navigation** (`web/src/components/layout/Header.jsx`):
   - Add "Forum" link to main navigation
   - Active state styling

**Deliverables**:
- [ ] CategoryListPage with loading/error states
- [ ] ThreadListPage with search, filters, pagination
- [ ] Routes configured with lazy loading
- [ ] Forum link in navigation header

---

### Phase 4: Post Components (Days 7-8)

**Goal**: Post display and rich text editor

**Tasks**:
1. **PostCard Component** (`web/src/components/forum/PostCard.jsx`):
   - Author avatar, display name, trust level badge
   - Post content (sanitized HTML with FORUM preset)
   - Reaction counts (like, love, helpful, thanks)
   - Edit/delete buttons (author or moderator only)
   - "Original Post" badge for first post
   - Edited timestamp and editor info
   - Memoized, PropTypes validation

2. **TipTapEditor Component** (`web/src/components/forum/TipTapEditor.jsx`):
   - TipTap initialization with StarterKit
   - Toolbar: Bold, Italic, Headings, Lists, Quotes, Links
   - Placeholder text
   - HTML output sanitization
   - `onChange` callback for parent component
   - Editable/read-only modes

**Deliverables**:
- [ ] PostCard component with XSS protection
- [ ] TipTapEditor component with toolbar
- [ ] Reaction display (functional toggle in Phase 7+)

---

### Phase 5: Thread Detail Page (Days 9-10)

**Goal**: Thread viewing and reply functionality

**Tasks**:
1. **ThreadDetailPage** (`web/src/pages/forum/ThreadDetailPage.jsx`):
   - Fetch thread and posts
   - Breadcrumb: Forums › Category › Thread
   - Thread header: title, author, stats, pinned/locked badges
   - Posts list with PostCard components
   - Reply form with TipTapEditor (authenticated users only)
   - "Log In" prompt for unauthenticated users
   - Locked thread message (no replies allowed)
   - Post submission with optimistic update
   - Scroll to new post after creation
   - Post deletion with confirmation

2. **Add Route**:
   ```javascript
   const ThreadDetailPage = lazy(() => import('./pages/forum/ThreadDetailPage'));

   { path: '/forum/:categorySlug/:threadSlug',
     element: <Suspense><ThreadDetailPage /></Suspense> }
   ```

**Deliverables**:
- [ ] ThreadDetailPage with posts list
- [ ] Reply form with authentication check
- [ ] Post deletion functionality
- [ ] Breadcrumb navigation

---

### Phase 6: Testing & Polish (Days 11-12)

**Goal**: Component tests and accessibility improvements

**Tasks**:
1. **Component Tests** (Vitest + React Testing Library):
   - `ThreadCard.test.jsx` - rendering, badges, stats, compact mode
   - `CategoryCard.test.jsx` - rendering, subcategories, stats
   - `PostCard.test.jsx` - content sanitization, reactions, edit/delete
   - `CategoryListPage.test.jsx` - loading, error, empty states
   - **Target**: 10+ tests, >70% coverage

2. **Accessibility Audit**:
   - Keyboard navigation: Tab, Enter, Space
   - ARIA attributes: `aria-label`, `aria-current`, `role`
   - Focus indicators: 3:1 contrast, visible outlines
   - Screen reader: semantic HTML, skip links

3. **Mobile Responsive**:
   - Test on mobile viewport (375px, 768px, 1024px)
   - Touch targets ≥44x44px
   - Responsive grid layouts
   - Mobile-friendly forms

4. **Security Verification**:
   - XSS protection on all user content
   - CSRF token in all POST/PATCH/DELETE requests
   - Authentication redirects work
   - No console errors with malicious input

**Deliverables**:
- [ ] 10+ component tests passing
- [ ] WCAG 2.2 AA compliance
- [ ] Mobile responsive design
- [ ] Zero console errors in production build

---

## Acceptance Criteria

### Functional Requirements

- [ ] **Browse Categories**: Users can view all forum categories with stats
- [ ] **View Threads**: Users can see threads in a category, sorted by activity
- [ ] **Search Threads**: Users can search threads by keyword
- [ ] **Filter Threads**: Users can sort by recent, newest, popular
- [ ] **Read Posts**: Users can view all posts in a thread
- [ ] **Create Threads**: Authenticated users can start new threads (requires trust_level)
- [ ] **Reply to Threads**: Authenticated users can post replies
- [ ] **Edit Posts**: Authors and moderators can edit posts
- [ ] **Delete Posts**: Authors and moderators can delete posts
- [ ] **Rich Text**: Users can format posts with bold, italic, headings, lists, links

### Non-Functional Requirements

**Security**:
- [ ] All user-generated content sanitized with DOMPurify
- [ ] CSRF protection on all write operations
- [ ] Authentication required for create/edit/delete
- [ ] No XSS vulnerabilities (test with `<script>alert('XSS')</script>`)

**Performance**:
- [ ] Initial bundle size <350 kB (with code splitting)
- [ ] Category list loads in <500ms (cached)
- [ ] Thread list pagination works smoothly
- [ ] Posts list handles 50+ posts without lag

**Accessibility (WCAG 2.2 AA)**:
- [ ] Keyboard navigation: full Tab/Enter/Space support
- [ ] Focus indicators: 3:1 contrast ratio, visible outlines
- [ ] Screen reader: semantic HTML (`<nav>`, `<main>`, `<article>`)
- [ ] ARIA attributes: `aria-label`, `aria-current`, `role`

**Code Quality**:
- [ ] All components use PropTypes validation
- [ ] All expensive components are memoized
- [ ] All async operations have loading/error states
- [ ] JSDoc comments on all service functions
- [ ] No console warnings in production build

### Quality Gates

- [ ] **Tests**: 10+ component tests passing, >70% coverage
- [ ] **Code Review**: Grade A (90+/100)
- [ ] **Accessibility**: WCAG 2.2 AA compliance (jest-axe)
- [ ] **Security**: No vulnerabilities from XSS testing
- [ ] **Performance**: Lighthouse score >85 (mobile)

---

## Success Metrics

**Technical Metrics**:
- Bundle size: <350 kB total (with code splitting)
- First Contentful Paint: <2s on 3G
- Test coverage: >70% components, >80% utilities
- Zero console errors in production

**User Experience Metrics** (post-launch):
- Forum engagement: >50% plant ID users visit forum
- Thread creation: >10 threads/week
- Reply rate: >60% threads get replies within 24h
- Mobile usage: >40% forum traffic from mobile web

---

## Dependencies & Prerequisites

### Backend (Already Complete ✅)
- Phase 1: Models (6 models, 17 indexes, admin interface)
- Phase 2c: API + Permissions (96/96 tests, Grade A 95/100)
- Django 5.2 + DRF running on port 8000
- Redis caching configured

### Frontend Stack (Already Installed ✅)
- React 19.1.1
- React Router 7.9.4
- Tailwind CSS 4.1.16
- Vite 7.1.12
- Vitest 3.0.5

### New Dependencies (To Install)
- `@tiptap/react` - Rich text editor
- `@tiptap/pm` - ProseMirror core
- `@tiptap/starter-kit` - Basic extensions
- `@tiptap/extension-link` - Link support
- `@tiptap/extension-placeholder` - Placeholder text
- `date-fns` - Date formatting (if not already installed)

---

## Risk Analysis & Mitigation

### Risk 1: TipTap Learning Curve
**Impact**: Medium | **Probability**: Low

**Mitigation**:
- TipTap has excellent documentation (https://tiptap.dev)
- Similar to existing StreamFieldRenderer pattern
- Fallback: Use plain textarea, add rich text later

### Risk 2: XSS Vulnerabilities
**Impact**: High | **Probability**: Low

**Mitigation**:
- Use existing DOMPurify patterns from blog
- Add FORUM preset with strict allowlist
- Test with OWASP XSS payloads
- Code review focuses on sanitization

### Risk 3: Performance with Large Threads
**Impact**: Medium | **Probability**: Medium

**Mitigation**:
- Start with simple pagination (20 posts/page)
- Memoize all components
- Use React.lazy() for code splitting
- Future: Add virtualization (@tanstack/react-virtual) if needed

### Risk 4: Authentication Flow Complexity
**Impact**: Low | **Probability**: Low

**Mitigation**:
- Reuse existing AuthContext from blog
- CSRF token handling already implemented
- Redirect patterns proven in ProtectedLayout

---

## Future Considerations

**Phase 7 Enhancements** (post-MVP):
- Real-time updates (WebSockets)
- User mentions (@username)
- Image attachments in posts
- Thread subscriptions/notifications
- Moderation tools UI (lock/pin/delete)
- Advanced search with filters
- Reaction toggle functionality (currently display-only)

**Phase 8 Mobile App**:
- Adapt forum components for Flutter
- Offline reading with local storage
- Push notifications for replies
- Shared `ForumService` logic

**Phase 9 Analytics**:
- Track engagement metrics (DAU, threads/day, replies/thread)
- Admin dashboard for forum health
- Google Analytics 4 events

---

## Documentation Plan

### To Update
- [ ] `CLAUDE.md` - Add forum frontend section with component patterns
- [ ] `README.md` - Add "Community Forum" to features list
- [ ] `web/README.md` - Document forum routes and components
- [ ] Create `web/docs/Forum.md` - Component architecture guide

### To Create
- [ ] `FORUM_FRONTEND_PHASE6_COMPLETE.md` - Implementation summary
- [ ] Inline JSDoc comments on all service functions
- [ ] PropTypes validation on all components
- [ ] Component storybook (optional, if time permits)

---

## References & Research

### Internal References

**Backend API** (Production-Ready):
- Models: `backend/apps/forum/models.py` (624 lines, 6 models, 17 indexes)
- ViewSets: `backend/apps/forum/viewsets/thread_viewset.py` (conditional prefetching)
- Serializers: `backend/apps/forum/serializers/thread_serializer.py` (list/detail/create)
- Permissions: `backend/apps/forum/permissions.py` (IsAuthorOrModerator pattern)
- Tests: `backend/apps/forum/tests/test_thread_viewset.py` (23 tests passing)
- Documentation: `backend/docs/forum/PHASE_2C_COMPLETE.md` (API reference)

**Frontend Patterns** (Blog Implementation):
- BlogListPage: `web/src/pages/BlogListPage.jsx` (search, filters, pagination)
- BlogDetailPage: `web/src/pages/BlogDetailPage.jsx` (breadcrumbs, metadata)
- BlogCard: `web/src/components/BlogCard.jsx` (memoization, PropTypes)
- blogService: `web/src/services/blogService.js` (API integration)
- sanitize: `web/src/utils/sanitize.js` (5 DOMPurify presets)
- AuthContext: `web/src/contexts/AuthContext.jsx` (React 19 authentication)

**Testing Utilities**:
- Test utils: `web/src/tests/utils.jsx` (renderWithRouterOnly, createMockBlogPost)
- BlogCard tests: `web/src/components/BlogCard.test.jsx` (30 tests passing)

### External References

**Official Documentation**:
- [React 19 - useOptimistic](https://react.dev/reference/react/useOptimistic)
- [React Router v7 - Nested Routes](https://reactrouter.com/en/main/route/route)
- [TipTap - React Installation](https://tiptap.dev/docs/editor/getting-started/install/react)
- [DRF - Pagination](https://www.django-rest-framework.org/api-guide/pagination/)
- [Tailwind CSS 4 - @theme](https://tailwindcss.com/docs/theme)

**Best Practices**:
- [WCAG 2.2 - Keyboard Accessible](https://www.w3.org/WAI/WCAG22/quickref/#keyboard-accessible)
- [OWASP - XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [DOMPurify - Sanitization](https://github.com/cure53/DOMPurify)

### Related Work

**Previous Phases**:
- Issue #53 - Phase 1 Week 1-2: Foundation & Models (✅ complete)
- Issue #54 - Phase 1 Week 3-4: API Layer & Integration (✅ complete)
- `FORUM_PHASE1_FOUNDATION_STATUS.md` - Phase 1 summary
- `backend/docs/forum/PHASE_2C_COMPLETE.md` - Phase 2c summary

**Similar Features**:
- Blog implementation (Oct 24, 2025) - Full CRUD with XSS protection
- UI modernization (Oct 25, 2025) - Authentication, navigation, design system
- 25 TODO resolutions (Oct 27, 2025) - Bundle optimization, component tests

---

## Labels

- `enhancement` - New feature
- `frontend` - React web app
- `forum` - Community forum feature
- `phase-6` - Implementation phase 6
- `priority:high` - Core feature for community engagement

---

## Assignees

@Xertox1234 (repository owner)

---

## Milestone

**Forum MVP** - Target: Week 15 (2-3 weeks from start)

---

## Related Issues

- #52 - Complete Forum Implementation Work Plan
- #53 - Phase 1 Week 1-2: Foundation & Models (✅ closed)
- #54 - Phase 1 Week 3-4: API Layer & Integration (✅ closed)
- #55 - 📋 PROJECT BOARD: Forum Implementation Tracker

---

**Created**: 2025-10-30
**Last Updated**: 2025-10-30
**Status**: ✅ Ready to start - Backend complete, frontend workfile created
**Estimated Effort**: 60-80 hours (2-3 weeks with AI pair programming)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

## Quick Start Guide

1. **Read workfile**: `/FORUM_FRONTEND_PHASE6_WORKFILE.md` (step-by-step instructions)
2. **Create branch**: `git checkout -b feature/forum-phase6-frontend`
3. **Install dependencies**: `cd web && npm install @tiptap/react @tiptap/pm @tiptap/starter-kit`
4. **Start Day 1**: Follow "Task 1.1: Install Dependencies" in workfile
5. **Track progress**: Update this issue with checkboxes as tasks complete
6. **Submit PR**: When all acceptance criteria met, create PR referencing this issue

**Questions?** Comment on this issue or reference specific sections in `/FORUM_FRONTEND_PHASE6_WORKFILE.md`
