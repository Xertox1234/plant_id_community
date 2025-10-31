# React Forum Interface Best Practices Research

**Research Date**: October 30, 2025
**Purpose**: Guide implementation of React Forum Frontend with CategoryList, ThreadList, ThreadDetail, PostCard, PostEditor components and routing.

---

## Table of Contents

1. [React 19 Patterns (2024-2025)](#1-react-19-patterns-2024-2025)
2. [Forum UI/UX Best Practices](#2-forum-uiux-best-practices)
3. [Accessibility for Forums (WCAG 2.2)](#3-accessibility-for-forums-wcag-22)
4. [Performance Optimization](#4-performance-optimization)
5. [Security Considerations](#5-security-considerations)
6. [Implementation Recommendations](#6-implementation-recommendations)
7. [Recommended Libraries & Tools](#7-recommended-libraries--tools)

---

## 1. React 19 Patterns (2024-2025)

### Modern React Patterns for Forum UIs

**Authority Level**: Official React documentation + industry best practices

#### Key Patterns for Forums

**1. Compound Components Pattern**
- **Use Case**: Complex forum components (thread cards, category lists)
- **Benefits**: Break down components into smaller, manageable pieces with shared state
- **Example**: ThreadCard with ThreadCard.Header, ThreadCard.Body, ThreadCard.Actions
- **Source**: [Telerik - React Design Patterns 2025](https://www.telerik.com/blogs/react-design-patterns-best-practices)
- **Rationale**: Forums have many composite UI elements that benefit from internal state management

**2. Custom Hooks Pattern**
- **Use Case**: Reusable logic (vote handling, post editing, real-time updates)
- **Benefits**: Encapsulate and share functionality between components
- **Examples**:
  - `useThreadSubscription()` - Real-time thread updates
  - `useVoting()` - Upvote/downvote logic
  - `usePostEditor()` - Rich text editor state
- **Source**: [UXPin - React Design Patterns](https://www.uxpin.com/studio/blog/react-design-patterns/)
- **Rationale**: Most powerful React pattern for sharing logic across forum features

**3. Context API for Global State**
- **Use Case**: User authentication, theme, notification state
- **Benefits**: Avoid prop drilling across deep component trees
- **Implementation**: AuthContext, ForumContext, NotificationContext
- **Source**: [Bacancy - React Architecture Patterns 2025](https://www.bacancytechnology.com/blog/react-architecture-patterns-and-best-practices)
- **Rationale**: Forums need user state accessible throughout the component tree

**4. React 19 useOptimistic Hook**
- **Use Case**: Instant UI feedback for votes, posts, reactions
- **Benefits**: Show UI changes immediately before server confirms
- **Official Docs**: [React.dev - useOptimistic](https://react.dev/reference/react/useOptimistic)
- **Code Pattern**:
```javascript
const [optimisticVotes, addOptimisticVote] = useOptimistic(
  votes,
  (state, newVote) => [...state, newVote]
);
```
- **Rationale**: Makes forum interactions feel instant and responsive

**5. React 19 Form Actions**
- **Use Case**: Post submission, reply creation, editing
- **Benefits**: Automatic pending states, error handling, optimistic updates
- **Official Docs**: [React.dev - Form Actions](https://react.dev/blog/2024/04/25/react-19#actions)
- **Feature**: `useActionState` hook manages form state transitions
- **Rationale**: Simplifies async form workflows common in forums

---

### List Virtualization for Large Datasets

**Authority Level**: Official library documentation + performance benchmarks

#### Why Virtualization Matters

**Problem**: Rendering 1,000+ threads/posts causes lag and memory issues
**Solution**: Only render visible items + small buffer
**Performance**: 100x+ improvement for large lists

#### Recommended Library: TanStack Virtual

**Library**: `@tanstack/react-virtual`
**Status**: Actively maintained, modern React support
**Comparison**: Preferred over `react-window` and deprecated `react-virtualized`

**Key Advantages**:
- Framework-agnostic (React, Vue, Solid, Svelte)
- No built-in styling (full customization control)
- Dynamic item sizing support
- Horizontal and vertical virtualization
- **Source**: [Medium - TanStack Virtual Optimization](https://medium.com/@sanjivchaudhary416/from-lag-to-lightning-how-tanstack-virtual-optimizes-1000s-of-items-smoothly-24f0998dc444)

**When to Use**:
- Thread lists with 100+ items
- Long post threads with nested replies
- Category listings with many subcategories
- **Source**: [Medium - Optimizing Large Datasets](https://medium.com/@eva.matova6/optimizing-large-datasets-with-virtualized-lists-70920e10da54)

**Basic Implementation**:
```javascript
import { useVirtualizer } from '@tanstack/react-virtual';

function ThreadList({ threads }) {
  const parentRef = React.useRef();

  const virtualizer = useVirtualizer({
    count: threads.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80, // Estimated row height
    overscan: 5, // Buffer items above/below viewport
  });

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <ThreadCard
            key={threads[virtualRow.index].id}
            thread={threads[virtualRow.index]}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

**Alternative**: `react-window` (lighter, simpler API for fixed-size lists)
**Comparison Source**: [npm-compare - Virtualization Libraries](https://npm-compare.com/@tanstack/react-virtual,react-infinite-scroll-component,react-virtualized,react-window)

---

### Real-Time Updates: Polling vs WebSockets

**Authority Level**: Industry consensus from 2024 discussions

#### WebSockets (Recommended for Forums)

**Best For**: Chat, real-time notifications, live thread updates
**Protocol**: Full-duplex, bidirectional communication
**Latency**: Lowest latency due to persistent connection
**Use Cases**:
- Live comment updates
- Real-time vote counts
- Typing indicators
- Online user presence
- **Source**: [DEV - WebSockets vs SSE vs Polling](https://dev.to/crit3cal/websockets-vs-server-sent-events-vs-polling-a-full-stack-developers-guide-to-real-time-3312)

**When to Choose WebSockets**:
- Need bi-directional communication
- Frequent updates (multiple per minute)
- Building chat or collaborative features
- **Source**: [VideoSDK - Long Polling vs WebSockets](https://www.videosdk.live/developer-hub/websocket/long-polling-vs-websocket)

#### Polling (Acceptable Alternative)

**Best For**: Simpler implementation, infrequent updates
**Pattern**: Regular interval requests (e.g., every 30 seconds)
**Downsides**: Higher server load, higher latency, more bandwidth
**Use Cases**:
- Notification checks (low frequency)
- Thread view count updates
- Non-critical updates
- **Source**: [Merge Society - WebSocket vs Polling 2025](https://www.mergesociety.com/code-report/websocket-polling)

**When to Choose Polling**:
- Updates less than once per minute
- Simpler infrastructure requirements
- Fallback for WebSocket failures
- **Source**: [Ably - WebSockets vs Long Polling](https://ably.com/blog/websockets-vs-long-polling)

#### Server-Sent Events (SSE) - Middle Ground

**Pattern**: One-way server-to-client updates
**Best For**: Notifications, feed updates, live scores
**Advantage**: Simpler than WebSockets, better than polling
**Limitation**: Server-to-client only (no client-to-server messages)
**Source**: [DEV - SSE Over WebSockets](https://dev.to/okrahul/real-time-updates-in-web-apps-why-i-chose-sse-over-websockets-k8k)

**Recommendation for This Project**:
- **Primary**: WebSockets for real-time thread/post updates
- **Fallback**: Polling for older browsers or connection failures
- **Implementation**: Django Channels for WebSocket support

---

## 2. Forum UI/UX Best Practices

### Thread Hierarchy Navigation

**Authority Level**: UX Stack Exchange discussions + established forum patterns

#### Breadcrumb Navigation

**Purpose**: Show user's location in category → subcategory → thread hierarchy
**Pattern**: Location-based breadcrumbs (not historical)
**Source**: [Smashing Magazine - Breadcrumbs UX](https://www.smashingmagazine.com/2022/04/breadcrumbs-ux-design/)

**Example Structure**:
```
Home > Plant Care > Tropical Plants > "How to care for Monstera" thread
```

**Best Practices**:
- Current page not clickable (displayed differently)
- Clear visual separators (>, /, or →)
- Located just below top-level navigation
- Show full hierarchy (don't truncate middle levels)
- **Source**: [Interaction Design Foundation - Breadcrumbs](https://www.interaction-design.org/literature/article/help-users-retrace-their-steps-with-breadcrumbs)

**When to Use**:
- Multi-level category structures (3+ levels)
- E-commerce-style browsing
- Users entering from search engines
- **Source**: [Pencil & Paper - Breadcrumbs Guide](https://www.pencilandpaper.io/articles/breadcrumbs-ux)

**When NOT to Use**:
- Single-level forums (no hierarchy)
- Linear navigation flows
- Mobile screens (consider mobile-specific patterns)

#### Nested Reply Handling

**Challenge**: Deeply nested threads become unreadable
**Solution Patterns**:

1. **Limited Indentation** (Recommended)
   - Stop indenting after 3-5 levels
   - Use visual indicators (arrows, lines) to show relationships
   - **Source**: [UX Stack Exchange - Forum Thread Display](https://ux.stackexchange.com/questions/19879/a-better-way-to-display-a-forum-thread)

2. **Collapse/Expand Controls**
   - Allow collapsing entire reply chains
   - "Show X more replies" buttons
   - Preserve context when expanded

3. **Thread View Toggle**
   - Flat view (chronological)
   - Nested view (reply hierarchy)
   - Mixed view (collapse old threads)

**Implementation Pattern**:
```javascript
// Stop indenting after maxDepth
const getIndentLevel = (depth) => Math.min(depth, MAX_INDENT_DEPTH);
const indentStyle = { marginLeft: `${getIndentLevel(depth) * 24}px` };
```

---

### Pagination vs Infinite Scroll

**Authority Level**: Nielsen Norman Group + UX research

#### When to Use Pagination (Recommended for Forums)

**Best For**: Goal-oriented searching, comparison tasks
**Use Cases**:
- Thread search results
- User profile post history
- Archive browsing
- **Source**: [Nielsen Norman Group - Infinite Scrolling](https://www.nngroup.com/articles/infinite-scrolling-tips/)

**Advantages**:
- Allows users to return to specific pages
- Better for accessibility (keyboard/screen reader users)
- Footer remains accessible
- SEO-friendly (distinct URLs per page)
- **Source**: [UX Planet - Infinite Scroll vs Pagination](https://uxplanet.org/ux-infinite-scrolling-vs-pagination-1030d29376f1)

**Implementation Best Practices**:
- Show total results count
- Allow jumping to specific pages
- Preserve scroll position on back navigation
- Display current page and total pages
- **Source**: [UX Patterns - Pagination](https://uxpatterns.dev/patterns/navigation/pagination)

#### When to Use Infinite Scroll

**Best For**: Continuous browsing, entertainment content
**Use Cases**:
- Main forum feed (new posts)
- Activity streams
- Image galleries
- **Source**: [LogRocket - Pagination vs Infinite Scroll](https://blog.logrocket.com/ux-design/pagination-vs-infinite-scroll-ux/)

**Accessibility Issues**:
- Screen reader challenges with dynamic content
- Difficult footer access
- Performance issues on slow connections
- Keyboard navigation problems
- **Source**: [Smashing Magazine - Infinite Scroll UX](https://www.smashingmagazine.com/2022/03/designing-better-infinite-scroll/)

**Best Practices IF Using Infinite Scroll**:
- Change URL as new items load
- Provide "Load More" button option
- Make footer accessible (sticky or relocated)
- Use ARIA live regions for screen readers
- Implement virtual scrolling for performance
- **Source**: [Interaction Design Foundation - Infinite Scrolling](https://www.interaction-design.org/literature/topics/infinite-scrolling)

#### Hybrid Approach (Best of Both)

**Pattern**: Pagination + "Load More" button
**Benefits**:
- User control over loading
- Easy footer access
- Works on slow connections
- Better accessibility
- **Source**: [Built In - Infinite Scroll Pros/Cons](https://builtin.com/articles/infinite-scroll)

**Recommendation for This Project**:
- **Thread Lists**: Pagination (20-50 threads per page)
- **Post Lists**: Hybrid (10-20 posts, then "Load More")
- **Activity Feed**: Infinite scroll (non-critical browsing)

---

### Mobile Responsive Layout

**Authority Level**: 2024 React development guides

#### Mobile-First Approach (Recommended)

**Framework**: Tailwind CSS v4 (mobile-first breakpoint system)
**Pattern**: Unprefixed utilities = mobile, prefixed = larger screens
**Source**: [Tailwind CSS - Responsive Design](https://tailwindcss.com/docs/responsive-design)

**Example**:
```javascript
// Mobile: vertical stack, Tablet: 2 columns, Desktop: 3 columns
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {threads.map(thread => <ThreadCard key={thread.id} thread={thread} />)}
</div>
```

#### Mobile Navigation Patterns

**1. Hamburger Menu** (Standard for complex navigation)
- Use for 5+ navigation items
- Place in top-left or top-right
- Include clear close button
- **Source**: [Mobile Responsive React Templates](https://reactemplates.com/blog/mobile-responsive-react-templates-best-practices-guide/)

**2. Bottom Navigation Bar** (Alternative for primary actions)
- 3-5 key actions
- Easy thumb reach (bottom 1/3 of screen)
- Fixed position
- Best for mobile apps
- **Source**: [DHiWise - React Mobile Responsiveness](https://www.dhiwise.com/post/the-ultimate-guide-to-achieving-react-mobile-responsiveness)

#### Touch Target Sizing

**Minimum Size**: 44x44 pixels (WCAG guideline)
**Applies To**: Buttons, links, vote controls, action menus
**Spacing**: 8px minimum between touch targets
**Source**: [Keitaro - React UX Best Practices](https://www.keitaro.com/insights/2024/01/30/building-responsive-and-user-friendly-web-applications-with-react/)

**Implementation**:
```javascript
// Ensure minimum touch target size
<button className="min-h-[44px] min-w-[44px] p-2">
  <ThumbsUpIcon />
</button>
```

#### Responsive Layout Tools

**Recommended Libraries**:
- **Tailwind CSS** - Utility-first, mobile-first breakpoints
- **CSS Grid + Flexbox** - Modern layout primitives
- **React Responsive** - Media query hooks for React
- **Source**: [DEV - Modern Layout Design 2025](https://dev.to/er-raj-aryan/modern-layout-design-techniques-in-reactjs-2025-guide-3868)

**Component Libraries**:
- **Preline UI** - Tailwind components (responsive, accessible)
- **Konsta UI** - Mobile-first Tailwind components
- **Meraki UI** - RTL support, dark mode, responsive
- **Source**: [Preline UI](https://preline.co/), [Konsta UI](https://konstaui.com/)

---

### Reaction System UI Patterns

**Authority Level**: UX Stack Exchange community consensus

#### Upvote/Downvote Button Order

**Recommended Pattern**: Upvote before downvote (left-to-right or top-to-bottom)
**Reasoning**: Encourages positive feedback, follows reading patterns
**Source**: [UX Stack Exchange - Upvote/Downvote Order](https://ux.stackexchange.com/questions/58344/upvote-downvote-button-order)

**Layout Options**:
```
Horizontal:  [↑ 42] [↓]        (Most common)
Vertical:    ↑                  (Reddit-style)
             42
             ↓
```

#### Color Scheme Recommendations

**Modern Approach**: Neutral colors (avoid red/green)
**Reasoning**:
- Better for colorblind users
- Less judgmental (not absolute good/bad)
- Calmer user experience
- **Source**: [UX Stack Exchange - Like/Dislike Display](https://ux.stackexchange.com/questions/111366/like-dislike-display-order)

**Examples**:
- YouTube: Gray (inactive), Blue (active) - no red
- Reddit: Gray (inactive), Orange (upvote), Blue (downvote)
- Avoid: Red/Green combinations

#### Reaction Types

**Simple**: Like only (Facebook-style)
**Binary**: Like/Dislike or Upvote/Downvote
**Multi-reaction**: Multiple emoji reactions (Slack, Discord)

**Recommendation**: Binary upvote/downvote for forums
**Reasoning**:
- 5-star systems mostly receive 1-star or 5-star (binary anyway)
- Simpler cognitive load
- Clear ranking for sorting
- **Source**: [Medium - Dislike Button Community Platforms](https://medium.com/@juliawarmuth/why-you-never-should-put-a-dislike-button-to-a-community-platform-58d7ff734d24)

#### Accessibility Considerations

**Requirements**:
- High-contrast focus indicators
- Tooltip showing exact vote count on hover
- Keyboard navigation support (Space/Enter to toggle)
- ARIA labels for screen readers
- **Source**: [Creative Bloq - Like Functionality UI](https://www.creativebloq.com/netmag/ui-design-pattern-tips-functionality-121413498)

**Implementation**:
```javascript
<button
  className="vote-button"
  onClick={handleUpvote}
  aria-label={`Upvote (current votes: ${votes})`}
  aria-pressed={hasUpvoted}
>
  <ArrowUpIcon aria-hidden="true" />
  <span>{votes}</span>
</button>
```

---

## 3. Accessibility for Forums (WCAG 2.2)

### Keyboard Navigation Requirements

**Authority Level**: W3C WCAG 2.2 official guidelines

#### Core Keyboard Navigation (Level A)

**Requirement**: All functionality must be operable via keyboard
**Standard**: WCAG 2.1.1 Keyboard
**Source**: [W3C - Understanding Keyboard](https://www.w3.org/WAI/WCAG21/Understanding/keyboard.html)

**Essential Keys for Forums**:
- **Tab**: Move focus forward through interactive elements
- **Shift + Tab**: Move focus backward
- **Enter/Return**: Activate buttons, links, submit forms
- **Space**: Toggle checkboxes, activate buttons
- **Arrow Keys**: Navigate within dropdowns, radio groups, nested replies
- **Escape**: Close modals, dialogs, dropdowns
- **Source**: [Stark - WCAG Keyboard Accessible](https://www.getstark.co/wcag-explained/operable/keyboard-accessible/)

#### Focus Indicators (Level AA)

**WCAG 2.4.7 Focus Visible**: All keyboard-focused elements must be visibly indicated
**WCAG 2.4.11 Focus Appearance (New in 2.2)**:
- Minimum contrast ratio of 3:1 against unfocused state
- Minimum 2px border thickness (or equivalent)
- **Source**: [Accessibility Works - WCAG 2.2 Guide](https://www.accessibility.works/blog/wcag-2-2-guide/)

**Implementation**:
```css
/* Strong focus indicator */
.thread-link:focus {
  outline: 3px solid #0066CC;
  outline-offset: 2px;
}

/* Or with Tailwind */
className="focus:ring-4 focus:ring-blue-500 focus:outline-none"
```

#### Forum-Specific Keyboard Actions

**Thread Navigation**:
- Tab through thread cards
- Enter to open thread
- Escape to return to thread list

**Nested Reply Navigation**:
- Arrow keys to navigate between replies
- Enter to expand/collapse threads
- Tab to move through reply actions (vote, reply, edit)
- **Source**: [UXPin - WCAG 2.1.1 Keyboard](https://www.uxpin.com/studio/blog/wcag-211-keyboard-accessibility-explained/)

**Post Editor**:
- Tab to formatting buttons
- Ctrl+B for bold, Ctrl+I for italic (common shortcuts)
- Escape to cancel editing
- Ctrl+Enter to submit post

---

### Focus Management for Modals

**Authority Level**: React accessibility guides + W3C recommendations

#### Modal Dialog Requirements

**1. Focus Trapping** (Critical)
- Move focus inside modal when opened
- Trap focus within modal (Tab cycles inside only)
- Return focus to trigger element when closed
- **Source**: [LogRocket - Accessible Modal Focus Trap](https://blog.logrocket.com/build-accessible-modal-focus-trap-react/)

**Recommended Library**: `focus-trap-react`
```javascript
import FocusTrap from 'focus-trap-react';

function PostEditorModal({ isOpen, onClose }) {
  return (
    <FocusTrap active={isOpen}>
      <dialog
        open={isOpen}
        aria-labelledby="modal-title"
        aria-modal="true"
      >
        <h2 id="modal-title">Edit Post</h2>
        {/* Modal content */}
        <button onClick={onClose}>Cancel</button>
        <button onClick={handleSubmit}>Save</button>
      </dialog>
    </FocusTrap>
  );
}
```
**Source**: [DHiWise - Focus Trap React Guide](https://www.dhiwise.com/post/mastering-accessibility-with-focus-trap-react)

**2. ARIA Attributes**
- `role="dialog"` (or use `<dialog>` element)
- `aria-modal="true"`
- `aria-labelledby` (reference to title)
- `aria-describedby` (reference to description)
- **Source**: [React Modal - Accessibility](https://reactcommunity.org/react-modal/accessibility/)

**3. Keyboard Shortcuts**
- **Escape**: Close modal (WCAG recommendation)
- **Enter**: Submit form (if applicable)
- **Source**: [UXPin - Accessible Modals Focus Traps](https://www.uxpin.com/studio/blog/how-to-build-accessible-modals-with-focus-traps/)

**4. HTML Dialog Element** (Modern Approach)

**Benefits**: Built-in focus management, backdrop, ESC handling
**Source**: [Tinloof - Accessible React Modal](https://tinloof.com/blog/how-to-create-an-accessible-react-modal)

```javascript
function PostEditorModal({ isOpen, onClose }) {
  const dialogRef = useRef();

  useEffect(() => {
    if (isOpen) {
      dialogRef.current?.showModal(); // Native focus management
    } else {
      dialogRef.current?.close();
    }
  }, [isOpen]);

  return (
    <dialog ref={dialogRef} onClose={onClose}>
      <form method="dialog">
        <h2>Edit Post</h2>
        {/* Content */}
        <button value="cancel">Cancel</button>
        <button value="submit">Save</button>
      </form>
    </dialog>
  );
}
```

---

### Screen Reader Optimization

#### ARIA Live Regions for Dynamic Content

**Use Cases**:
- New post notifications
- Vote count updates
- Loading states
- Form validation errors

**Pattern**:
```javascript
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {newPostCount > 0 && `${newPostCount} new posts available`}
</div>
```

**ARIA Live Types**:
- `aria-live="polite"`: Announce after current speech
- `aria-live="assertive"`: Interrupt and announce immediately
- `aria-atomic="true"`: Read entire region (not just changes)
- **Source**: [A Drop in Calm - Modal Focus Trap](https://adropincalm.com/blog/modal-focus-trap-in-javascript-and-react/)

#### Semantic HTML

**Use Proper Elements**:
- `<nav>` for navigation menus
- `<article>` for thread cards
- `<button>` for actions (not `<div onclick>`)
- `<a>` for links (not `<button onclick="navigate">`)
- `<form>` for post submission

**Landmark Regions**:
```javascript
<nav aria-label="Forum categories">...</nav>
<main>
  <article aria-labelledby="thread-title">
    <h1 id="thread-title">Thread Title</h1>
    {/* Thread content */}
  </article>
</main>
<aside aria-label="Related threads">...</aside>
```

#### Skip Links

**Purpose**: Allow keyboard users to skip navigation
**Pattern**:
```javascript
<a href="#main-content" className="sr-only focus:not-sr-only">
  Skip to main content
</a>
<main id="main-content">...</main>
```
**Source**: Existing project implementation (`web/src/layouts/RootLayout.jsx`)

---

### Testing Recommendations

**Manual Testing**:
- Keyboard-only navigation (unplug mouse)
- Screen reader testing (NVDA, VoiceOver, JAWS)
- High contrast mode
- Browser zoom to 200%

**Automated Testing**:
- **Axe DevTools** (browser extension)
- **Lighthouse** (Chrome DevTools)
- **eslint-plugin-jsx-a11y** (linting)
- **jest-axe** (unit tests)
- **Source**: [Nutrient - Accessible Modals React](https://pspdfkit.com/blog/2018/building-accessible-modals-with-react/)

---

## 4. Performance Optimization

### Code Splitting and Lazy Loading

**Authority Level**: Official React documentation + 2024 optimization guides

#### Route-Based Code Splitting (Essential)

**Pattern**: Split each route into separate bundle chunks
**Benefits**: Smaller initial bundle, faster Time to Interactive
**Source**: [Web.dev - Code Splitting Suspense](https://web.dev/code-splitting-suspense/)

**Implementation**:
```javascript
import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';

// Lazy load route components
const CategoryList = lazy(() => import('./pages/CategoryList'));
const ThreadList = lazy(() => import('./pages/ThreadList'));
const ThreadDetail = lazy(() => import('./pages/ThreadDetail'));
const PostEditor = lazy(() => import('./components/PostEditor'));

function ForumRoutes() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/forum" element={<CategoryList />} />
        <Route path="/forum/:categoryId" element={<ThreadList />} />
        <Route path="/forum/thread/:threadId" element={<ThreadDetail />} />
        <Route path="/forum/post/new" element={<PostEditor />} />
      </Routes>
    </Suspense>
  );
}
```
**Source**: [UI.dev - React Router Code Splitting](https://ui.dev/react-router-code-splitting)

**Best Practices**:
- Use route-based splitting first (max size reduction)
- Add component-based splitting for heavy features
- Provide meaningful loading states
- Handle lazy loading errors with Error Boundaries
- **Source**: [Medium - Optimizing React Apps](https://medium.com/@ignatovich.dm/optimizing-react-apps-with-code-splitting-and-lazy-loading-e8c8791006e3)

#### Dynamic Imports for Heavy Dependencies

**Use Case**: Load DOMPurify, rich text editors on-demand
**Source**: Existing project pattern (`web/src/utils/domSanitizer.js`)

```javascript
// Load DOMPurify only when needed
export async function sanitizeHTML(dirty, preset = 'default') {
  const DOMPurify = await import('dompurify');
  return DOMPurify.default.sanitize(dirty, PRESETS[preset]);
}
```

**Benefits**:
- 22.57 kB saved in main bundle (project measurement)
- Faster initial page load
- Better Core Web Vitals scores
- **Source**: Project docs - `UI_MODERNIZATION_COMPLETE.md`

---

### Image Optimization

**Authority Level**: 2024 React optimization guides

#### Lazy Loading Images

**Native Approach** (Preferred):
```javascript
<img
  src={post.imageUrl}
  alt={post.imageAlt}
  loading="lazy"  // Browser native lazy loading
  decoding="async"
/>
```
**Source**: [Stack Overflow - React Image Lazy Loading](https://stackoverflow.com/questions/69054825/how-should-i-implement-lazy-loading-for-my-images-in-react)

**Browser Support**: All major browsers (2024)
**Firefox Bug**: Place `loading` before `src` attribute

#### Responsive Images

**Use srcset for Multiple Sizes**:
```javascript
<img
  src="post-image-800.jpg"
  srcSet="
    post-image-400.jpg 400w,
    post-image-800.jpg 800w,
    post-image-1200.jpg 1200w
  "
  sizes="(max-width: 768px) 400px, 800px"
  alt="Post image"
  loading="lazy"
/>
```
**Source**: [ImageKit - React Image Optimization](https://imagekit.io/blog/react-image-optimization/)

#### Modern Image Formats

**Recommended**: WebP, AVIF (fallback to JPEG/PNG)
**Savings**: 25-35% smaller than JPEG at same quality
**Source**: [Uploadcare - React Image Optimization](https://uploadcare.com/blog/react-image-optimization-techniques/)

**Implementation**:
```javascript
<picture>
  <source srcSet="image.avif" type="image/avif" />
  <source srcSet="image.webp" type="image/webp" />
  <img src="image.jpg" alt="Fallback" loading="lazy" />
</picture>
```

#### Image Upload Compression

**Existing Pattern**: Canvas-based client-side compression
**Configuration**:
- Max dimension: 1200px
- Quality: 85%
- Auto-compress files > 2MB
- **Source**: Project file `web/src/utils/imageCompression.js`

**Performance Impact**: 85% faster uploads (40-80s → 3-5s for 10MB images)

#### Recommended Libraries

- **react-lazy-load-image-component**: Built-in optimization features
- **react-lazyload**: Simple lazy loading wrapper
- **next/image**: Best-in-class (if using Next.js)
- **Source**: [DEV - Image Lazy Loading 2024](https://dev.to/sundarbadagala081/image-lazy-loading-31jb)

---

### Caching Strategy with TanStack Query

**Authority Level**: TanStack Query official documentation + 2024 community guides

#### Why TanStack Query for Forums

**Benefits**:
- Automatic caching and refetching
- Optimistic updates
- Pagination support
- Infinite scroll support
- Request deduplication
- Background refetching

**Source**: [TanStack Query Documentation](https://tanstack.com/query/latest/docs/framework/react/guides/caching)

#### Cache Configuration for Forum Data

```javascript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cache for 5 minutes
      staleTime: 5 * 60 * 1000,
      // Keep unused data for 10 minutes
      cacheTime: 10 * 60 * 1000,
      // Refetch on window focus
      refetchOnWindowFocus: true,
      // Retry failed requests
      retry: 1,
    },
  },
});

// Category list (rarely changes)
const CATEGORY_STALE_TIME = 30 * 60 * 1000; // 30 minutes

// Thread list (moderate updates)
const THREAD_LIST_STALE_TIME = 5 * 60 * 1000; // 5 minutes

// Thread detail (frequent updates - votes, new posts)
const THREAD_DETAIL_STALE_TIME = 1 * 60 * 1000; // 1 minute
```

**Source**: [Ackee - Cache Manipulation in TanStack Query](https://www.ackee.agency/blog/options-for-manipulating-cache-in-tanstack-query)

#### Mutation Updates

**Pattern**: Update cache after mutations (create/edit/delete posts)

```javascript
import { useMutation, useQueryClient } from '@tanstack/react-query';

function useCreatePost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (newPost) => api.createPost(newPost),

    // Optimistic update (instant UI feedback)
    onMutate: async (newPost) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries(['thread', newPost.threadId]);

      // Snapshot previous value
      const previousThread = queryClient.getQueryData(['thread', newPost.threadId]);

      // Optimistically update cache
      queryClient.setQueryData(['thread', newPost.threadId], (old) => ({
        ...old,
        posts: [...old.posts, { ...newPost, id: 'temp-id', createdAt: new Date() }],
      }));

      return { previousThread };
    },

    // Rollback on error
    onError: (err, newPost, context) => {
      queryClient.setQueryData(
        ['thread', newPost.threadId],
        context.previousThread
      );
    },

    // Refetch after success
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries(['thread', variables.threadId]);
    },
  });
}
```

**Source**: [TanStack Query - Optimistic Updates](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)

#### Cache Invalidation Strategies

**1. Invalidation** (Most Common)
- Marks data as stale
- Triggers refetch if query is active
- **Use for**: Post creation, editing, deletion

```javascript
queryClient.invalidateQueries(['threads', categoryId]);
```

**2. setQueryData** (Direct Update)
- Immediately updates cache
- No refetch required
- **Use for**: Vote updates, reaction toggles

```javascript
queryClient.setQueryData(['post', postId], (old) => ({
  ...old,
  votes: old.votes + 1,
}));
```

**Important**: Always use immutable updates (don't mutate in place)
**Source**: [TanStack Query - Updates from Mutations](https://tanstack.com/query/v4/docs/react/guides/updates-from-mutation-responses)

#### Pagination Support

```javascript
import { useQuery } from '@tanstack/react-query';

function useThreadList(categoryId, page = 1) {
  return useQuery({
    queryKey: ['threads', categoryId, page],
    queryFn: () => fetchThreads(categoryId, page),
    keepPreviousData: true, // Keep old data while fetching new page
  });
}
```

**Source**: [djamware - React Query Tutorial 2024](https://www.djamware.com/post/688ecf617a49f1456836fd14/react-query-tanstack-tutorial-fetching-caching-and-mutations-made-easy)

---

### Client-Side Rate Limiting

**Authority Level**: Industry best practices

#### Debouncing (Search Input)

**Use Case**: Delay search API calls until user stops typing
**Pattern**: Wait X milliseconds after last keystroke

```javascript
import { useState, useEffect } from 'react';
import { useDebouncedValue } from './hooks/useDebouncedValue';

function ThreadSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebouncedValue(searchTerm, 500); // 500ms delay

  useEffect(() => {
    if (debouncedSearch) {
      // API call happens here
      searchThreads(debouncedSearch);
    }
  }, [debouncedSearch]);

  return (
    <input
      type="search"
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search threads..."
    />
  );
}
```

**Hook Implementation**:
```javascript
import { useState, useEffect } from 'react';

function useDebouncedValue(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}
```

**Source**: [DEV - Debouncing and Throttling React](https://dev.to/abhishekrawe/debouncing-and-throttling-in-reactjs-4fhf)

#### Throttling (Vote Buttons, Scroll Events)

**Use Case**: Limit function calls to once per X milliseconds
**Pattern**: Execute immediately, then ignore calls for X ms

```javascript
import { useRef } from 'react';

function useThrottle(callback, delay) {
  const lastRan = useRef(Date.now());

  return (...args) => {
    if (Date.now() - lastRan.current >= delay) {
      callback(...args);
      lastRan.current = Date.now();
    }
  };
}

// Usage
function VoteButton({ postId }) {
  const handleVote = useThrottle((type) => {
    // API call
    api.vote(postId, type);
  }, 1000); // Max 1 vote per second

  return <button onClick={() => handleVote('up')}>Upvote</button>;
}
```

**Source**: [Medium - Client-Side Rate Limiting](https://medium.com/@sterling.benjamin/debounce-throttle-rate-limit-controlling-the-api-firehose-f9de4fa9fe2c)

#### Button Disabling (Form Submission)

**Use Case**: Prevent multiple form submissions
**Pattern**: Disable button while API request is pending

```javascript
import { useState } from 'react';

function PostEditorForm() {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      await api.createPost(formData);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Posting...' : 'Post'}
      </button>
    </form>
  );
}
```

**Source**: [GeeksforGeeks - Debouncing Throttling React Hooks](https://www.geeksforgeeks.org/reactjs/how-to-use-debouncing-and-throttling-with-react-hooks/)

**Library Option**: Lodash `debounce` and `throttle` utilities
**Source**: [CodingDeft - React Debounce Throttle](https://www.codingdeft.com/posts/react-debounce-throttle/)

---

## 5. Security Considerations

### XSS Prevention in User-Generated Content

**Authority Level**: Security research + React security guides

#### DOMPurify Integration (Required)

**Library**: `dompurify` (maintained by CURE53 security team)
**Use Case**: Sanitize all rich text content from users
**Source**: [StackHawk - React XSS Guide](https://www.stackhawk.com/blog/react-xss-guide-examples-and-prevention/)

**Centralized Sanitization Pattern** (Existing Project):
```javascript
// web/src/utils/sanitize.js
import DOMPurify from 'dompurify';

export const SANITIZE_PRESETS = {
  default: {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  },
  richText: {
    ALLOWED_TAGS: ['h1', 'h2', 'h3', 'p', 'br', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre'],
  },
  forum: {
    // Forum-specific sanitization rules
    ALLOWED_TAGS: ['b', 'i', 'u', 'a', 'p', 'br', 'blockquote', 'code', 'pre'],
    ALLOWED_ATTR: ['href'],
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick'],
  },
};

export function sanitizeForumPost(html) {
  return DOMPurify.sanitize(html, SANITIZE_PRESETS.forum);
}
```

**Component Usage**:
```javascript
import { sanitizeForumPost } from '../utils/sanitize';

function PostContent({ html }) {
  const cleanHTML = sanitizeForumPost(html);

  return (
    <div
      className="post-content"
      dangerouslySetInnerHTML={{ __html: cleanHTML }}
    />
  );
}
```

**Source**: Project implementation - `web/src/utils/sanitize.js`

#### Markdown Libraries (Safer Alternative)

**Recommended**: `react-markdown` (escapes HTML by default)
**Source**: [Medium - Avoiding XSS via Markdown](https://medium.com/javascript-security/avoiding-xss-via-markdown-in-react-91665479900)

**Benefits**:
- No HTML execution (tags displayed as text)
- No need for dangerouslySetInnerHTML
- Converts Markdown to JSX (not HTML strings)

```javascript
import ReactMarkdown from 'react-markdown';

function PostContent({ markdown }) {
  return (
    <ReactMarkdown
      components={{
        // Custom component rendering
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}
```

**Alternative**: `markdown-to-jsx` (converts to JSX, safer)
**Source**: [Pragmatic Web Security - React XSS dangerouslySetInnerHTML](https://pragmaticwebsecurity.com/articles/spasecurity/react-xss-part2)

#### Rich Text Editor Security

**Recommended Editors**:
- **Tiptap** - Modern, React-friendly, extensible
- **Slate** - Fully customizable, React components
- **Draft.js** - Facebook-maintained (mature, stable)

**Security Checklist**:
1. Sanitize output before storing in database
2. Sanitize again before rendering (defense in depth)
3. Disable HTML input mode if possible (Markdown only)
4. Implement Content Security Policy (CSP)
5. Keep DOMPurify updated (bypass fixes)

**DOMPurify Bypass Warning** (April 2024):
- Version <= 3.1.0 had bypass vulnerability
- Always use latest version
- **Source**: [Mizu.re - DOMPurify Bypasses](https://mizu.re/post/exploring-the-dompurify-library-bypasses-and-fixes)

#### Content Security Policy

**CSP Header**: Blocks inline scripts and unsafe eval
**Implementation**: Django settings or nginx config

```python
# Django settings.py
SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'strict-dynamic'"],
    'style-src': ["'self'", "'unsafe-inline'"],  # Tailwind needs this
    'img-src': ["'self'", "data:", "https:"],
    'connect-src': ["'self'", "wss://example.com"],  # WebSocket
}
```

**Source**: [PullRequest - Secure Markdown Rendering](https://www.pullrequest.com/blog/secure-markdown-rendering-in-react-balancing-flexibility-and-safety/)

---

### CSRF Protection with Django REST Framework

**Authority Level**: Django REST Framework official documentation

#### Session Authentication + CSRF

**Pattern**: Cookie-based authentication requires CSRF tokens
**Source**: [DRF - AJAX, CSRF & CORS](https://www.django-rest-framework.org/topics/ajax-csrf-cors/)

**React Implementation** (Existing Project Pattern):
```javascript
// Get CSRF token from cookie
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

// Include in POST/PUT/DELETE requests
async function createPost(postData) {
  const csrfToken = getCookie('csrftoken');

  const response = await fetch('/api/v1/forum/posts/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    credentials: 'include', // Send cookies
    body: JSON.stringify(postData),
  });

  return response.json();
}
```

**Source**: [TechieDialries - Django React Forms CSRF](https://www.techiediaries.com/django-react-forms-csrf-axios/)

#### Axios Configuration

**Automatic CSRF Handling**:
```javascript
import axios from 'axios';

axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';
axios.defaults.withCredentials = true;

// Now all axios requests include CSRF token automatically
```

**Source**: [Stack Overflow - Django CSRF React](https://stackoverflow.com/questions/50732815/how-to-use-csrf-token-in-django-restful-api-and-react)

#### Token Authentication Alternative

**JWT Tokens**: No CSRF protection needed
**Reasoning**: Tokens not stored in cookies (manual inclusion in headers)
**Source**: [Kyle Bebak - DRF Auth CSRF](https://kylebebak.github.io/post/django-rest-framework-auth-csrf)

**Current Project**: Uses JWT (no CSRF required for token-based endpoints)
**Forum Endpoints**: Should support both session + CSRF and JWT

---

### Input Validation

#### Client-Side Validation (react-hook-form)

**Library**: `react-hook-form` + `zod` schema validation
**Source**: [React Hook Form](https://react-hook-form.com/)

**Post Editor Example**:
```javascript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const postSchema = z.object({
  title: z.string()
    .min(5, 'Title must be at least 5 characters')
    .max(200, 'Title too long'),
  content: z.string()
    .min(10, 'Post content too short')
    .max(50000, 'Post content too long'),
  category: z.string().uuid('Invalid category'),
});

function PostEditorForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(postSchema),
    mode: 'onBlur', // Validate on blur (better UX than onChange)
  });

  const onSubmit = async (data) => {
    await api.createPost(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input
        {...register('title')}
        aria-invalid={errors.title ? 'true' : 'false'}
        aria-describedby="title-error"
      />
      {errors.title && (
        <span id="title-error" role="alert">
          {errors.title.message}
        </span>
      )}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Posting...' : 'Create Post'}
      </button>
    </form>
  );
}
```

**Source**: [LogRocket - React Hook Form Guide](https://blog.logrocket.com/react-hook-form-complete-guide/)

**Validation Best Practices**:
- Use `mode: 'onBlur'` for performance (not `onChange`)
- Provide clear error messages
- Use ARIA attributes for accessibility
- Always validate server-side (client validation can be bypassed)
- **Source**: [Full Stack Foundations - React Forms](https://www.fullstackfoundations.com/blog/react-forms-best-practices)

---

## 6. Implementation Recommendations

### React Router v6 Setup

**Authority Level**: Official React Router documentation

#### Nested Route Structure for Forums

```javascript
import { Routes, Route, Outlet } from 'react-router-dom';

function App() {
  return (
    <Routes>
      {/* Forum root with nested routes */}
      <Route path="/forum" element={<ForumLayout />}>
        <Route index element={<CategoryList />} />
        <Route path="category/:categoryId" element={<ThreadList />} />
        <Route path="thread/:threadId" element={<ThreadDetail />} />
        <Route path="thread/:threadId/edit" element={<ThreadEditor />} />
        <Route path="post/new" element={<PostEditor />} />
        <Route path="post/:postId/edit" element={<PostEditor />} />
      </Route>
    </Routes>
  );
}

function ForumLayout() {
  return (
    <div className="forum-layout">
      <ForumNavigation />
      <main>
        <Outlet /> {/* Renders matched child route */}
      </main>
      <ForumSidebar />
    </div>
  );
}
```

**Source**: [UI.dev - React Router Nested Routes](https://ui.dev/react-router-nested-routes)

#### Relative Routing (v6 Feature)

**All paths and links are relative to parent route**:
```javascript
// Inside ThreadList component (at /forum/category/:categoryId)
<Link to="thread/123">View Thread</Link>
// Links to: /forum/category/:categoryId/thread/123

// Navigate up one level
<Link to="..">Back to Categories</Link>
```

**Source**: [Remix - React Router v6](https://remix.run/blog/react-router-v6)

#### Route Parameters and Search Params

```javascript
import { useParams, useSearchParams } from 'react-router-dom';

function ThreadList() {
  const { categoryId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = searchParams.get('page') || '1';
  const sort = searchParams.get('sort') || 'recent';

  const handleSortChange = (newSort) => {
    setSearchParams({ page: '1', sort: newSort });
  };

  return (
    <div>
      <h1>Threads in Category {categoryId}</h1>
      <SortDropdown value={sort} onChange={handleSortChange} />
      <ThreadList category={categoryId} page={page} sort={sort} />
    </div>
  );
}
```

**Source**: [SitePoint - React Router v6 Guide](https://www.sitepoint.com/react-router-complete-guide/)

#### Protected Routes Pattern

```javascript
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}

// Usage
<Route element={<ProtectedRoute />}>
  <Route path="/forum/post/new" element={<PostEditor />} />
  <Route path="/forum/thread/:id/edit" element={<ThreadEditor />} />
</Route>
```

**Source**: Existing project pattern (`web/src/layouts/ProtectedLayout.jsx`)

---

### Component Architecture

#### Recommended Component Structure

```
src/
├── components/
│   ├── forum/
│   │   ├── CategoryCard.jsx          # Reusable category display
│   │   ├── ThreadCard.jsx            # Thread preview in list
│   │   ├── PostCard.jsx              # Individual post in thread
│   │   ├── PostEditor.jsx            # Rich text editor for posts
│   │   ├── VoteButton.jsx            # Upvote/downvote component
│   │   ├── ReactionButtons.jsx       # Like/helpful/etc reactions
│   │   └── SubscriptionButton.jsx    # Thread subscription toggle
│   ├── layout/
│   │   ├── ForumNavigation.jsx       # Forum-specific nav
│   │   └── ForumSidebar.jsx          # Popular threads, categories
│   └── ui/
│       ├── Button.jsx
│       ├── Modal.jsx
│       └── LoadingSpinner.jsx
├── pages/
│   ├── CategoryList.jsx              # Main forum page
│   ├── ThreadList.jsx                # Threads in category
│   ├── ThreadDetail.jsx              # Full thread with posts
│   └── UserProfile.jsx               # User's posts/threads
├── hooks/
│   ├── useVoting.js                  # Vote logic
│   ├── useThreadSubscription.js      # Real-time updates
│   ├── useInfiniteScroll.js          # Pagination helper
│   └── useDebouncedValue.js          # Search debounce
├── services/
│   ├── forumService.js               # API calls
│   └── websocketService.js           # WebSocket connection
├── contexts/
│   └── ForumContext.jsx              # Global forum state
└── utils/
    ├── sanitize.js                   # DOMPurify wrappers
    └── validation.js                 # Form validation
```

#### Component Design Patterns

**1. Container/Presentation Pattern**

```javascript
// Container (data fetching, logic)
function ThreadListContainer() {
  const { categoryId } = useParams();
  const { data, isLoading } = useQuery(['threads', categoryId],
    () => fetchThreads(categoryId)
  );

  if (isLoading) return <LoadingSpinner />;

  return <ThreadListPresentation threads={data.threads} />;
}

// Presentation (pure UI)
function ThreadListPresentation({ threads }) {
  return (
    <div className="thread-list">
      {threads.map(thread => (
        <ThreadCard key={thread.id} thread={thread} />
      ))}
    </div>
  );
}
```

**2. Compound Components** (for ThreadCard)

```javascript
function ThreadCard({ thread }) {
  return (
    <article className="thread-card">
      <ThreadCard.Header
        title={thread.title}
        author={thread.author}
        createdAt={thread.createdAt}
      />
      <ThreadCard.Body
        excerpt={thread.excerpt}
        tags={thread.tags}
      />
      <ThreadCard.Footer
        votes={thread.votes}
        replies={thread.replyCount}
        views={thread.viewCount}
      />
    </article>
  );
}

ThreadCard.Header = function ThreadCardHeader({ title, author, createdAt }) {
  return (
    <header>
      <h3>{title}</h3>
      <UserBadge user={author} timestamp={createdAt} />
    </header>
  );
};

ThreadCard.Body = function ThreadCardBody({ excerpt, tags }) {
  return (
    <div>
      <p>{excerpt}</p>
      {tags.map(tag => <Tag key={tag}>{tag}</Tag>)}
    </div>
  );
};

ThreadCard.Footer = function ThreadCardFooter({ votes, replies, views }) {
  return (
    <footer>
      <VoteCount count={votes} />
      <ReplyCount count={replies} />
      <ViewCount count={views} />
    </footer>
  );
};
```

---

### State Management Recommendations

#### Local State (useState, useReducer)

**Use For**: Component-specific state (form inputs, UI toggles)

```javascript
function PostEditor() {
  const [content, setContent] = useState('');
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  return (
    <div>
      <textarea value={content} onChange={(e) => setContent(e.target.value)} />
      <button onClick={() => setIsPreviewMode(!isPreviewMode)}>
        {isPreviewMode ? 'Edit' : 'Preview'}
      </button>
      {isPreviewMode && <MarkdownPreview content={content} />}
    </div>
  );
}
```

#### Context API (Global State)

**Use For**: User auth, theme, notification preferences

```javascript
// contexts/ForumContext.jsx
import { createContext, useContext, useState } from 'react';

const ForumContext = createContext();

export function ForumProvider({ children }) {
  const [subscriptions, setSubscriptions] = useState([]);
  const [notifications, setNotifications] = useState([]);

  const subscribeToThread = (threadId) => {
    setSubscriptions(prev => [...prev, threadId]);
  };

  return (
    <ForumContext.Provider value={{
      subscriptions,
      notifications,
      subscribeToThread,
    }}>
      {children}
    </ForumContext.Provider>
  );
}

export const useForum = () => useContext(ForumContext);
```

#### TanStack Query (Server State)

**Use For**: All API data (threads, posts, categories, votes)

```javascript
// hooks/useThread.js
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useThread(threadId) {
  return useQuery({
    queryKey: ['thread', threadId],
    queryFn: () => fetchThread(threadId),
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

export function useVoteOnPost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ postId, voteType }) => api.vote(postId, voteType),
    onMutate: async ({ postId, voteType }) => {
      // Optimistic update
      queryClient.setQueryData(['post', postId], (old) => ({
        ...old,
        votes: old.votes + (voteType === 'up' ? 1 : -1),
      }));
    },
    onSuccess: (data, { postId }) => {
      queryClient.invalidateQueries(['post', postId]);
    },
  });
}
```

---

## 7. Recommended Libraries & Tools

### Core Dependencies

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^6.28.0",

    "@tanstack/react-query": "^5.59.0",
    "@tanstack/react-virtual": "^3.10.8",

    "react-hook-form": "^7.53.1",
    "zod": "^3.23.8",
    "@hookform/resolvers": "^3.9.1",

    "dompurify": "^3.2.0",
    "react-markdown": "^9.0.1",

    "focus-trap-react": "^10.3.0",

    "tailwindcss": "^4.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.1",

    "eslint": "^9.15.0",
    "eslint-plugin-jsx-a11y": "^6.10.2",

    "vitest": "^2.1.5",
    "@testing-library/react": "^16.0.1",
    "jest-axe": "^9.0.0"
  }
}
```

### Rich Text Editor Options

**1. Tiptap** (Recommended for Modern React)
- **Pros**: React-friendly, extensible, active development
- **URL**: https://tiptap.dev/
- **License**: MIT
- **Use Case**: Full-featured WYSIWYG editor

**2. Slate**
- **Pros**: Fully customizable, React components
- **URL**: https://www.slatejs.org/
- **License**: MIT
- **Use Case**: Custom editing experiences

**3. Draft.js**
- **Pros**: Mature, Facebook-maintained
- **URL**: https://draftjs.org/
- **License**: MIT
- **Use Case**: Stable, production-tested

**4. SimpleMDE/EasyMDE** (Markdown-based)
- **Pros**: Simple, Markdown-focused
- **URL**: https://github.com/Ionaru/easy-markdown-editor
- **License**: MIT
- **Use Case**: Markdown forums (like Stack Overflow)

### Styling/UI Libraries

**1. Tailwind CSS v4** (Existing Project)
- Mobile-first responsive design
- Utility-first approach
- Dark mode support

**2. Tailwind Component Libraries**
- **Preline UI**: https://preline.co/ (responsive, accessible)
- **Konsta UI**: https://konstaui.com/ (mobile-first)
- **Meraki UI**: https://merakiui.com/ (RTL, dark mode)

**3. Headless UI** (Accessible Components)
- **URL**: https://headlessui.com/
- **Components**: Modals, dropdowns, tabs (unstyled)
- **Accessibility**: Full WCAG 2.2 support

### Testing Libraries

**1. Vitest** (Existing Project)
- Fast, Vite-native test runner
- React Testing Library integration

**2. jest-axe** (Accessibility Testing)
- Automated a11y checks in tests
- Example:
```javascript
import { render } from '@testing-library/react';
import { axe } from 'jest-axe';

test('ThreadCard is accessible', async () => {
  const { container } = render(<ThreadCard thread={mockThread} />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

### Open Source Reference Projects

**GitHub Repositories** (for code reference):

1. **ReForum** (React + Redux)
   - URL: https://github.com/proshoumma/ReForum
   - Tech: React, Redux, Express, MongoDB
   - Features: OAuth, forum board

2. **React Reddit Clone**
   - URL: https://github.com/joriguzman/react-reddit
   - Tech: React
   - Features: Voting, nested comments

3. **cwellsx/view** (TypeScript)
   - URL: https://github.com/cwellsx/view
   - Tech: React, TypeScript
   - Features: Forum software

**Note**: Review code patterns, don't copy directly. Ensure compatibility with project stack.

---

## Summary of Key Recommendations

### Must Have (Priority 1)

1. **TanStack Virtual** for thread/post lists (100+ items)
2. **React Router v6** nested routes with lazy loading
3. **DOMPurify** sanitization for all user content
4. **react-hook-form + zod** for form validation
5. **TanStack Query** for API data caching
6. **Focus trap** for modals (accessibility)
7. **CSRF protection** for Django mutations
8. **Keyboard navigation** support (WCAG 2.1.1)
9. **Code splitting** by route
10. **Mobile-first** responsive design (Tailwind)

### Recommended (Priority 2)

1. **WebSockets** for real-time updates (Django Channels)
2. **Breadcrumb navigation** for deep hierarchies
3. **Pagination** (not infinite scroll) for thread lists
4. **Optimistic updates** for votes/reactions
5. **Image lazy loading** (native `loading="lazy"`)
6. **Debounced search** input
7. **Throttled vote buttons**
8. **ARIA live regions** for dynamic content
9. **Error boundaries** for lazy-loaded routes
10. **Virtual scrolling** for 1000+ item lists

### Optional (Priority 3)

1. **React Markdown** instead of HTML rich text
2. **Bottom navigation** for mobile (alternative to hamburger)
3. **Hybrid pagination** (Load More button)
4. **SSE** for real-time updates (simpler than WebSockets)
5. **Headless UI** components (pre-built accessibility)
6. **Tailwind UI component library** (Preline/Konsta)
7. **WebP/AVIF** image formats
8. **Service Worker** for offline support

---

## Authority Level Summary

**Tier 1 (Highest Authority)**:
- W3C WCAG 2.2 official guidelines
- Official React documentation (React 19)
- Official library documentation (TanStack, React Router, DRF)

**Tier 2 (Industry Standards)**:
- Nielsen Norman Group UX research
- Security research (CURE53, OWASP)
- MDN Web Docs

**Tier 3 (Community Consensus)**:
- Stack Overflow / UX Stack Exchange discussions
- Established patterns from popular forums (Reddit, Discourse)
- 2024 blog posts from recognized developers

**Tier 4 (Reference)**:
- Open source project examples
- Component library documentation
- Tutorial sites (LogRocket, DEV.to)

---

## Next Steps for Implementation

1. **Set up core routing structure** (React Router v6 nested routes)
2. **Implement base components** (CategoryList, ThreadList, ThreadDetail)
3. **Add TanStack Query** for API data management
4. **Integrate DOMPurify** for content sanitization
5. **Build PostEditor** with rich text support
6. **Add virtualization** for large lists
7. **Implement accessibility features** (keyboard nav, focus management)
8. **Set up WebSockets** for real-time updates
9. **Optimize performance** (code splitting, image lazy loading)
10. **Add comprehensive tests** (Vitest + jest-axe)

---

**Research Completed**: October 30, 2025
**Document Version**: 1.0
**Total Sources Referenced**: 50+ authoritative sources

