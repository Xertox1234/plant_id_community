# Forum Phase 6 Polish - Patterns Codified

**Session**: Forum Phase 6 Polish (PR #59)
**Date**: October 31, 2025
**Source**: Compacted session summary + file analysis
**Patterns Added**: 5 new patterns (40-44) to code-review-specialist

## Overview

This document captures patterns learned from implementing pagination, writing 50 tests, and fixing bugs during Forum Phase 6 Polish. These patterns have been codified into the code-review-specialist agent (patterns 40-44).

## Pattern 40: React Router v6+ Testing - useParams() Mocking ⭐ NEW - IMPORTANT

### Problem
React Router v6+ changed internal implementation, making `useParams()` difficult to mock in tests. Tests using MemoryRouter show `useParams()` returning `undefined`, causing API calls with undefined parameters.

### Why This Happens
- React Router v6+ internals changed from v5
- MemoryRouter doesn't automatically populate useParams()
- Direct mocking of useParams() hook doesn't work reliably
- Must mock the entire react-router module

### Anti-Pattern (Fails)
```javascript
// ❌ WRONG: Trying to spy on useParams directly
import { useParams } from 'react-router';
vi.spyOn(useParams).mockReturnValue({ categorySlug: 'plant-care' });
// This doesn't work - useParams is not a mockable object
```

### Anti-Pattern (Incomplete)
```javascript
// ❌ INCOMPLETE: Only mocking some router hooks
vi.mock('react-router', () => ({
  useParams: vi.fn(() => ({ categorySlug: 'plant-care' })),
  // Missing: Link, useNavigate, other components/hooks
}));
// This breaks components using Link or other router features
```

### Correct Pattern
```javascript
// ✅ CORRECT: Mock entire module with all necessary exports
import { MemoryRouter } from 'react-router';
import * as ReactRouter from 'react-router';

// Mock useParams while preserving other exports
vi.spyOn(ReactRouter, 'useParams').mockReturnValue({
  categorySlug: 'plant-care',
  threadSlug: 'watering-tips'
});

// Render with MemoryRouter for routing context
render(
  <MemoryRouter initialEntries={['/forum/plant-care/watering-tips']}>
    <ThreadDetailPage />
  </MemoryRouter>
);
```

### Alternative Pattern (Full Module Mock)
```javascript
// ✅ ALSO CORRECT: Mock module with automatic passthrough
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useParams: vi.fn(() => ({
      categorySlug: 'plant-care',
      threadSlug: 'watering-tips'
    })),
  };
});
```

### Reusable Test Helper
```javascript
// tests/routerUtils.js
export function setupRouterMocks(params = {}) {
  const defaultParams = {
    categorySlug: 'plant-care',
    threadSlug: 'test-thread'
  };

  vi.spyOn(ReactRouter, 'useParams').mockReturnValue({
    ...defaultParams,
    ...params
  });
}

// Usage in test file:
beforeEach(() => {
  setupRouterMocks({ categorySlug: 'identification' });
});
```

### Impact
- **Forum Phase 6 Polish**: 11 test failures (Router mocking infrastructure issue)
- **Not logic errors**: Actual component code is correct
- **Code Review Note**: "Infrastructure issue specific to test environment"

### Reference
- **File**: `web/src/pages/forum/ThreadDetailPage.test.jsx`
- **Error**: `expected fetchCategory to be called with 'plant-care', Received: undefined`
- **PR**: #59 (Forum Phase 6 Polish)

---

## Pattern 41: HTML Validation - Nested Anchor Tags ⭐ NEW - BLOCKER

### Problem
HTML validation error: `<a>` cannot be a descendant of `<a>`. React Router `<Link>` renders as `<a>` tag, so nesting Links violates HTML spec.

### Why This is Invalid
- HTML spec disallows `<a>` as descendant of `<a>`
- Causes unpredictable click behavior (which link activates?)
- Browser behavior varies when nested anchors clicked
- Accessibility issues for screen readers

### Common Scenario
Category cards with subcategory links - tempting to wrap entire card in Link, but subcategories need their own Links.

### Anti-Pattern (BLOCKER)
```javascript
// ❌ BLOCKER: Subcategory links nested inside main category link
function CategoryCard({ category }) {
  return (
    <Link to={`/forum/${category.slug}`} className="category-card">
      <h3>{category.name}</h3>
      <p>{category.description}</p>

      {/* These Links are INSIDE parent Link - invalid HTML! */}
      {category.children?.map(child => (
        <Link key={child.id} to={`/forum/${child.slug}`}>
          {child.name}
        </Link>
      ))}
    </Link>
  );
}
```

### Error Message
```
Warning: validateDOMNesting(...): <a> cannot appear as a descendant of <a>.
In HTML, <a> cannot be a descendant of <a>.
```

### Correct Pattern (Separate Clickable Areas)
```javascript
// ✅ CORRECT: Subcategories outside main Link wrapper
function CategoryCard({ category }) {
  return (
    <div className="category-card">
      {/* Main category link - standalone */}
      <Link to={`/forum/${category.slug}`} className="category-header">
        <h3>{category.name}</h3>
        <p>{category.description}</p>
      </Link>

      {/* Subcategories - separate Links, not nested */}
      {category.children && (
        <div className="subcategories">
          {category.children.map(child => (
            <Link key={child.id} to={`/forum/${child.slug}`}>
              {child.name}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Alternative Pattern (Clickable Card with Exception)
```javascript
// ✅ ALSO CORRECT: Card clickable except subcategory area
function CategoryCard({ category }) {
  const navigate = useNavigate();

  const handleCardClick = (e) => {
    // Don't navigate if clicking inside subcategories area
    if (e.target.closest('.subcategories')) return;
    navigate(`/forum/${category.slug}`);
  };

  return (
    <div className="category-card" onClick={handleCardClick}>
      <h3>{category.name}</h3>
      <p>{category.description}</p>

      <div className="subcategories" onClick={(e) => e.stopPropagation()}>
        {category.children?.map(child => (
          <Link key={child.id} to={`/forum/${child.slug}`}>
            {child.name}
          </Link>
        ))}
      </div>
    </div>
  );
}
```

### Impact
- **HTML Invalid**: Fails W3C validation
- **UX Broken**: Unpredictable click behavior
- **Accessibility**: Screen readers announce incorrectly
- **Browser Dependent**: Some browsers may not fire inner link clicks
- **Grade Penalty**: -5 points (invalid HTML structure)

### Reference
- **File**: `web/src/components/forum/CategoryCard.jsx` (lines 15-73)
- **Fixed In**: Forum Phase 6 Polish (PR #59)
- **Before**: Subcategories nested inside main Link
- **After**: Separate clickable areas with proper HTML structure

---

## Pattern 42: Context Hook Export Pattern - useContext Wrapper ⭐ NEW - BLOCKER

### Problem
Missing custom hook export prevents context consumption. Build fails with "No matching export" error when components try to import `useAuth` hook.

### Why Wrapper Hooks Are Needed
- Provides better error messages (usage outside provider)
- Enables type checking without extra null checks
- Centralizes context validation logic
- Prevents direct useContext usage spreading in codebase

### Anti-Pattern (Missing Hook Export)
```javascript
// ❌ BLOCKER: Only exports context, not the hook
// AuthContext.jsx
import { createContext, useContext, useState } from 'react';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const value = { user, setUser };
  return <AuthContext value={value}>{children}</AuthContext>;
}

// Missing: useAuth hook export!
```

### Build Error
```
No matching export in "src/contexts/AuthContext.jsx" for import "useAuth"
[vite] Error compiling application
```

### Correct Pattern (With Validation Hook)
```javascript
// ✅ CORRECT: Export context, provider, AND custom hook
import { createContext, useContext, useState } from 'react';

export const AuthContext = createContext(null);

/**
 * useAuth Hook
 *
 * Custom hook to consume AuthContext with validation.
 * Throws error if used outside of AuthProvider.
 *
 * @returns {Object} Auth context value
 * @throws {Error} If used outside AuthProvider
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const value = { user, setUser };
  return <AuthContext value={value}>{children}</AuthContext>;
}
```

### Usage Pattern (Consumer Component)
```javascript
// Consumer component
import { useAuth } from '../contexts/AuthContext';

function UserProfile() {
  const { user } = useAuth();  // ✅ Clean API, automatic validation

  if (!user) return <p>Please log in</p>;

  return <p>Welcome, {user.name}!</p>;
}
```

### Why NOT to Use Direct useContext (Anti-Pattern)
```javascript
// ❌ NOT RECOMMENDED: Direct useContext usage
import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';

function UserProfile() {
  const context = useContext(AuthContext);

  // Must manually check for null every time!
  if (context === null) {
    throw new Error('Must be within AuthProvider');
  }

  const { user } = context;
  // Rest of component...
}
```

### Complete Context Module Exports
```javascript
// Complete context module exports
export const AuthContext = createContext(null);  // Context itself
export function useAuth() { /* ... */ }          // Custom hook
export function AuthProvider({ children }) { /* ... */ }  // Provider

// Optionally export types (TypeScript):
export type AuthContextType = { /* ... */ };
```

### Impact
- **Build Failure**: "No matching export" error prevents build
- **Runtime Errors**: Components can't access context
- **Developer Experience**: Poor error messages without validation
- **Code Quality**: Scattered useContext calls instead of centralized hook
- **Grade Penalty**: -10 points (breaks application, build failure)

### Reference
- **File**: `web/src/contexts/AuthContext.jsx` (lines 35-43)
- **Fixed In**: Commit `de551be` (Forum Phase 6 Polish)
- **Error**: Frontend build failed on server startup
- **Fix**: Added useAuth hook export with validation

---

## Pattern 43: Incremental Pagination - Load More vs Replace ⭐ NEW - IMPORTANT

### Problem
Pagination strategy affects UX and performance. Full page replacement loses context and scroll position. Users become disoriented.

### When to Use Incremental Pagination (Load More)
- ✅ Long feeds (social media, forums, comments)
- ✅ Users want to scroll through content continuously
- ✅ Context is important (previous items stay visible)
- ✅ Mobile-first design (infinite scroll pattern)
- ✅ Preserves scroll position and user's place

### When to Use Page Replacement (Page Numbers)
- ✅ Search results (users jump to specific pages)
- ✅ Data tables with sorting/filtering
- ✅ Known total number of pages
- ✅ Users need to reference specific pages

### Anti-Pattern (Replacing All Data)
```javascript
// ❌ WRONG: Full replacement loses previous posts
const handleLoadMore = async () => {
  const nextPage = currentPage + 1;
  const newData = await fetchPosts({ page: nextPage, limit: 20 });

  setPosts(newData.items);  // ❌ Replaces, doesn't append
  setCurrentPage(nextPage);
};
// User loses context, scroll jumps to top
```

### Correct Pattern (Incremental Append)
```javascript
// ✅ CORRECT: Append new posts, preserve existing
const [posts, setPosts] = useState([]);
const [currentPage, setCurrentPage] = useState(1);
const [totalPosts, setTotalPosts] = useState(0);
const [loadingMore, setLoadingMore] = useState(false);
const postsPerPage = 20;

const handleLoadMore = useCallback(async () => {
  try {
    setLoadingMore(true);
    const nextPage = currentPage + 1;

    const postsData = await fetchPosts({
      thread: threadSlug,
      page: nextPage,
      limit: postsPerPage,
    });

    // ✅ Append new posts to existing
    setPosts(prev => [...prev, ...postsData.items]);
    setCurrentPage(nextPage);
  } catch (err) {
    console.error('Load more failed:', err);
  } finally {
    setLoadingMore(false);
  }
}, [currentPage, threadSlug]);

// Load More button with remaining count
const remainingPosts = totalPosts - posts.length;

return (
  <>
    {posts.map(post => <PostCard key={post.id} post={post} />)}

    {remainingPosts > 0 && (
      <Button onClick={handleLoadMore} loading={loadingMore}>
        Load More Posts ({remainingPosts} remaining)
      </Button>
    )}
  </>
);
```

### State Management for Incremental Pagination
```javascript
// Required state variables
const [posts, setPosts] = useState([]);           // Accumulated posts
const [currentPage, setCurrentPage] = useState(1); // Current page number
const [totalPosts, setTotalPosts] = useState(0);   // Total from API
const [loadingMore, setLoadingMore] = useState(false); // Loading state
const postsPerPage = 20;  // Constant, not state

// Derived values
const hasMore = posts.length < totalPosts;
const remainingCount = totalPosts - posts.length;
```

### Post Count Synchronization (CRUD Operations)
```javascript
// Update total count when posts created/deleted
const handleReplySubmit = async (content) => {
  const newPost = await createPost({ thread: thread.id, content });
  setPosts(prev => [...prev, newPost]);
  setTotalPosts(prev => prev + 1);  // ✅ Increment total
};

const handlePostDelete = async (postId) => {
  await deletePost(postId);
  setPosts(prev => prev.filter(p => p.id !== postId));
  setTotalPosts(prev => prev - 1);  // ✅ Decrement total
};
```

### Button UX Patterns
```javascript
// Show dynamic remaining count
<Button onClick={handleLoadMore} loading={loadingMore} disabled={loadingMore}>
  {loadingMore ? 'Loading...' : `Load More Posts (${remainingCount} remaining)`}
</Button>

// Auto-hide when all loaded
{posts.length < totalPosts && (
  <Button onClick={handleLoadMore}>Load More</Button>
)}

// Show "All posts loaded" message
{posts.length >= totalPosts && posts.length > 0 && (
  <p className="text-center text-gray-500">
    All posts loaded ({totalPosts} total)
  </p>
)}
```

### Impact
- **UX Poor**: Scroll jumps, context lost, disorienting experience
- **Performance**: Re-fetching same data wastefully
- **Accessibility**: Screen reader announces content replacement
- **Grade Penalty**: -3 points (suboptimal UX pattern)

### Reference
- **File**: `web/src/pages/forum/ThreadDetailPage.jsx` (lines 121-140)
- **Implemented In**: Forum Phase 6 Polish (PR #59)
- **Result**: Threads with 100+ posts load incrementally (20/page)

---

## Pattern 44: Django Test Data Generation - Idempotent Scripts ⭐ NEW - IMPORTANT

### Problem
Test data scripts that aren't idempotent create duplicate data on re-run. This clutters development databases and makes QA difficult.

### Why Idempotency Matters
- Scripts may fail mid-execution (need to re-run)
- Development databases are unstable (reset often)
- Team members run same scripts (different times)
- QA processes may require data refresh (not full reset)

### Anti-Pattern (Creates Duplicates)
```python
# ❌ WRONG: Creates duplicate data every run
def create_test_data():
    # Creates new user every time!
    test_user = User.objects.create(
        username='forum_tester',
        email='tester@example.com'
    )
    test_user.set_password('testpass123')
    test_user.save()

    # Creates duplicate category every time!
    category = Category.objects.create(
        name='Plant Care',
        slug='plant-care'
    )

    # Creates duplicate threads every time!
    for i in range(5):
        Thread.objects.create(
            title=f'Test Thread {i}',
            category=category,
            author=test_user
        )
```

### Correct Pattern (Idempotent with get_or_create)
```python
# ✅ CORRECT: Safe to run multiple times
def create_test_data():
    # Get existing or create new (idempotent)
    test_user, created = User.objects.get_or_create(
        username='forum_tester',
        defaults={
            'email': 'tester@example.com',
            'first_name': 'Forum',
            'last_name': 'Tester',
        }
    )
    if created:
        test_user.set_password('testpass123')
        test_user.save()
        print(f"   ✅ Created user: {test_user.username}")
    else:
        print(f"   ✅ Using existing user: {test_user.username}")

    # Idempotent category creation
    category, created = Category.objects.get_or_create(
        slug='plant-care',  # Unique identifier
        defaults={
            'name': 'Plant Care Tips',
            'description': 'Share plant care techniques',
            'icon': '🌱'
        }
    )
    status = "Created" if created else "Using existing"
    print(f"   ✅ {status}: {category.name}")

    # Idempotent thread creation
    thread, created = Thread.objects.get_or_create(
        slug='watering-tips',  # Unique identifier
        defaults={
            'title': 'Watering Tips for Beginners',
            'category': category,
            'author': test_user,
            'excerpt': 'Learn the basics of plant watering'
        }
    )

    # Check existing post count before creating more
    existing_posts = Post.objects.filter(thread=thread).count()
    target_posts = 35

    if existing_posts >= target_posts:
        print(f"   ✅ Thread already has {existing_posts} posts")
    else:
        posts_to_create = target_posts - existing_posts
        print(f"   Creating {posts_to_create} posts...")

        for i in range(posts_to_create):
            Post.objects.create(
                thread=thread,
                author=test_user,
                content_raw=f'<p>Test post #{existing_posts + i + 1}</p>'
            )
        print(f"   ✅ Created {posts_to_create} posts")
```

### Best Practices
```python
# 1. Use get_or_create with unique fields
user, created = User.objects.get_or_create(
    username='tester',  # Unique field
    defaults={'email': '...', 'first_name': '...'}  # Only used if created
)

# 2. Check counts before creating bulk data
existing_count = Post.objects.filter(thread=thread).count()
if existing_count < target_count:
    # Create only what's needed
    for i in range(target_count - existing_count):
        Post.objects.create(...)

# 3. Provide feedback on what was done
if created:
    print(f"   ✅ Created: {obj}")
else:
    print(f"   ✅ Using existing: {obj}")

# 4. Update counts/stats at end (not assume clean state)
thread.post_count = Post.objects.filter(thread=thread).count()
thread.save()
```

### Script Execution Pattern
```python
# Run via Django shell (loads Django environment)
# python manage.py shell < create_forum_test_data.py

def create_forum_test_data():
    print("\\n" + "="*70)
    print("🌱 Forum Test Data Generator")
    print("="*70 + "\\n")

    # All creation logic here...

    # Print summary
    print("\\n" + "="*70)
    print("✅ Test Data Generation Complete!")
    print("="*70)
    print(f"\\n📊 Summary:")
    print(f"   Users: {User.objects.count()}")
    print(f"   Categories: {Category.objects.count()}")
    print(f"   Threads: {Thread.objects.count()}")
    print(f"   Posts: {Post.objects.count()}")

# Auto-execute when run
if __name__ == '__main__':
    create_forum_test_data()
else:
    # When run via shell, execute automatically
    create_forum_test_data()
```

### Varied Content Generation
```python
# Generate realistic varied content
def generate_post_content(post_num, thread_title):
    content_templates = [
        f'<p>Post #{post_num} in "{thread_title}"</p>',
        f'<p><strong>Post #{post_num}:</strong> Great discussion!</p>',
        f'<p>Post #{post_num} with <em>formatting</em> and <code>code</code></p>',
        # ... more templates
    ]
    template_idx = post_num % len(content_templates)
    return content_templates[template_idx]
```

### Test Script Quality
```python
# Run twice and verify no duplicates
python manage.py shell < create_test_data.py
python manage.py shell < create_test_data.py  # Should show "Using existing"
```

### Impact
- **Development**: Duplicate data clutters database
- **Team**: Inconsistent test environments
- **QA**: Can't refresh data without full reset
- **Debugging**: Hard to reproduce issues with duplicate data
- **Grade Penalty**: -2 points (poor development tooling)

### Reference
- **File**: `backend/create_forum_test_data.py` (265 lines)
- **Created In**: Forum Phase 6 Polish (PR #59)
- **Test Data**: 6 threads (5, 20, 35, 75, 120, 25 posts), 281 total posts
- **Usage**: `python manage.py shell < create_forum_test_data.py`

---

## Summary

### Patterns Codified
5 new patterns added to code-review-specialist (patterns 40-44):

1. **React Router v6+ Testing** - useParams() mocking with vi.spyOn()
2. **HTML Validation** - Avoiding nested anchor tags
3. **Context Hook Export** - Proper useContext wrapper pattern
4. **Incremental Pagination** - Load More vs full page replacement
5. **Django Test Data** - Idempotent scripts with get_or_create()

### Impact
- **Code Review**: Automated detection of these patterns in future reviews
- **Team Knowledge**: Patterns documented for team reference
- **Quality**: Higher code quality through pattern enforcement
- **Consistency**: Standardized approaches across codebase

### Location
- **Agent Config**: `.claude/agents/code-review-specialist.md` (lines 3208-3344)
- **Documentation**: `backend/docs/development/FORUM_PHASE6_POLISH_PATTERNS_CODIFIED.md`
- **Total Patterns**: 44 (was 39)

### Session Context
- **PR**: #59 (Forum Phase 6 Polish)
- **Deliverables**: Pagination + 50 tests + bug fixes
- **Code Review**: Grade A (95/100)
- **Status**: Merged to main (commit 733183c)
