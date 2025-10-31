# Forum Frontend Phase 6 - Implementation Work File

**Status**: 🚀 Ready to Start
**Duration**: 2-3 weeks (Weeks 14-15)
**Branch**: `feature/forum-phase6-frontend`
**Issue**: [To be created]

---

## Quick Reference

### Backend API Endpoints (Already Complete)
```
Base: http://localhost:8000/api/v1/forum/

Categories:
  GET /categories/              → List all categories
  GET /categories/tree/         → Category hierarchy
  GET /categories/{slug}/       → Category detail

Threads:
  GET /threads/                 → List threads (paginated)
  GET /threads/{slug}/          → Thread detail
  POST /threads/                → Create thread (auth + trust_level)
  PATCH /threads/{slug}/        → Update thread (author or mod)
  DELETE /threads/{slug}/       → Delete thread (author or mod)
  GET /threads/pinned/          → Pinned threads
  GET /threads/recent/?days=7   → Recent threads

Posts:
  GET /posts/?thread={slug}     → Posts in thread (required)
  POST /posts/                  → Create post (auth)
  PATCH /posts/{id}/            → Update post (author or mod)
  DELETE /posts/{id}/           → Soft delete post

Reactions:
  POST /reactions/              → Add reaction (auth)
  DELETE /reactions/{id}/       → Remove reaction
  GET /reactions/?post={id}     → Reactions on post
```

### Component Patterns to Follow
- **BlogListPage** → ForumThreadList (pagination, filters, search)
- **BlogDetailPage** → ForumThreadDetail (breadcrumbs, metadata, content)
- **BlogCard** → ForumThreadCard (memoized, compact mode)
- **sanitize.js** → XSS protection (DOMPurify presets)
- **blogService.js** → forumService.js (API integration)

### Key Files to Reference
```
Patterns:
  web/src/pages/BlogListPage.jsx          (search, filters, pagination)
  web/src/pages/BlogDetailPage.jsx        (breadcrumbs, metadata, share)
  web/src/components/BlogCard.jsx         (memoization, PropTypes)
  web/src/services/blogService.js         (API service layer)
  web/src/utils/sanitize.js               (XSS protection)
  web/src/App.jsx                         (routing configuration)

Backend Reference:
  backend/apps/forum/models.py            (data models)
  backend/apps/forum/viewsets/            (API behavior)
  backend/apps/forum/serializers/         (API responses)
  backend/docs/forum/PHASE_2C_COMPLETE.md (API documentation)
```

---

## Week 14: Core Components & API Integration

### Day 1-2: Foundation Setup

#### Task 1.1: Install Dependencies
```bash
cd web
npm install @tiptap/react @tiptap/pm @tiptap/starter-kit
npm install @tiptap/extension-link @tiptap/extension-placeholder
npm install date-fns  # For date formatting (if not already installed)
```

**Verification**:
- [ ] `package.json` shows @tiptap packages
- [ ] `npm run dev` starts without errors

---

#### Task 1.2: Create Forum Service Layer

**File**: `web/src/services/forumService.js`

**Implementation**:
```javascript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

// Helper to get CSRF token from cookies
function getCsrfToken() {
  return document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
}

// Helper for authenticated requests
async function authenticatedFetch(url, options = {}) {
  const csrfToken = getCsrfToken();

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch all categories
 * @returns {Promise<Array>} Array of category objects
 */
export async function fetchCategories() {
  return authenticatedFetch(`${FORUM_BASE}/categories/`);
}

/**
 * Fetch category tree (hierarchical structure)
 * @returns {Promise<Array>} Array of categories with children
 */
export async function fetchCategoryTree() {
  return authenticatedFetch(`${FORUM_BASE}/categories/tree/`);
}

/**
 * Fetch single category by slug
 * @param {string} slug - Category slug
 * @returns {Promise<Object>} Category object
 */
export async function fetchCategory(slug) {
  return authenticatedFetch(`${FORUM_BASE}/categories/${slug}/`);
}

/**
 * Fetch threads with filters and pagination
 * @param {Object} options
 * @param {number} options.page - Page number (1-indexed)
 * @param {number} options.limit - Items per page
 * @param {string} options.category - Category slug filter
 * @param {string} options.search - Search query
 * @param {string} options.ordering - Sort order (-last_activity_at, -created_at, etc.)
 * @returns {Promise<Object>} { items: [], meta: { count, next, previous } }
 */
export async function fetchThreads({
  page = 1,
  limit = 20,
  category = '',
  search = '',
  ordering = '-last_activity_at'
} = {}) {
  const params = new URLSearchParams({
    page: page.toString(),
    limit: limit.toString(),
    ordering,
  });

  if (category) params.append('category', category);
  if (search) params.append('search', search);

  const data = await authenticatedFetch(`${FORUM_BASE}/threads/?${params}`);

  return {
    items: data.results || [],
    meta: {
      count: data.count || 0,
      next: data.next,
      previous: data.previous,
    },
  };
}

/**
 * Fetch single thread by slug
 * @param {string} slug - Thread slug
 * @returns {Promise<Object>} Thread object with first_post
 */
export async function fetchThread(slug) {
  return authenticatedFetch(`${FORUM_BASE}/threads/${slug}/`);
}

/**
 * Create new thread (requires authentication)
 * @param {Object} data
 * @param {string} data.title - Thread title
 * @param {string} data.category - Category UUID
 * @param {string} data.excerpt - Short excerpt
 * @param {string} data.first_post_content - First post content
 * @param {string} data.first_post_format - Content format (plain/markdown/rich)
 * @returns {Promise<Object>} Created thread object
 */
export async function createThread({
  title,
  category,
  excerpt,
  first_post_content,
  first_post_format = 'plain'
}) {
  return authenticatedFetch(`${FORUM_BASE}/threads/`, {
    method: 'POST',
    body: JSON.stringify({
      title,
      category,
      excerpt,
      first_post_content,
      first_post_format,
    }),
  });
}

/**
 * Fetch posts in a thread
 * @param {Object} options
 * @param {string} options.thread - Thread slug (required)
 * @param {number} options.page - Page number
 * @param {number} options.limit - Items per page
 * @param {string} options.ordering - Sort order (created_at, -created_at)
 * @returns {Promise<Object>} { items: [], meta: { count, next, previous } }
 */
export async function fetchPosts({
  thread,
  page = 1,
  limit = 20,
  ordering = 'created_at'
}) {
  if (!thread) {
    throw new Error('Thread slug is required');
  }

  const params = new URLSearchParams({
    thread,
    page: page.toString(),
    limit: limit.toString(),
    ordering,
  });

  const data = await authenticatedFetch(`${FORUM_BASE}/posts/?${params}`);

  return {
    items: data.results || [],
    meta: {
      count: data.count || 0,
      next: data.next,
      previous: data.previous,
    },
  };
}

/**
 * Create new post in a thread (requires authentication)
 * @param {Object} data
 * @param {string} data.thread - Thread UUID
 * @param {string} data.content_raw - Post content
 * @param {string} data.content_format - Content format (plain/markdown/rich)
 * @returns {Promise<Object>} Created post object
 */
export async function createPost({ thread, content_raw, content_format = 'plain' }) {
  return authenticatedFetch(`${FORUM_BASE}/posts/`, {
    method: 'POST',
    body: JSON.stringify({
      thread,
      content_raw,
      content_format,
    }),
  });
}

/**
 * Update existing post (requires author or moderator)
 * @param {string} postId - Post UUID
 * @param {Object} data
 * @param {string} data.content_raw - Updated content
 * @param {string} data.content_format - Content format
 * @returns {Promise<Object>} Updated post object
 */
export async function updatePost(postId, { content_raw, content_format }) {
  return authenticatedFetch(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({
      content_raw,
      content_format,
    }),
  });
}

/**
 * Soft delete post (requires author or moderator)
 * @param {string} postId - Post UUID
 * @returns {Promise<void>}
 */
export async function deletePost(postId) {
  return authenticatedFetch(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'DELETE',
  });
}

/**
 * Add reaction to post (requires authentication)
 * @param {Object} data
 * @param {string} data.post - Post UUID
 * @param {string} data.reaction_type - like/love/helpful/thanks
 * @returns {Promise<Object>} Created reaction object
 */
export async function addReaction({ post, reaction_type }) {
  return authenticatedFetch(`${FORUM_BASE}/reactions/`, {
    method: 'POST',
    body: JSON.stringify({
      post,
      reaction_type,
    }),
  });
}

/**
 * Remove reaction (requires authentication)
 * @param {string} reactionId - Reaction UUID
 * @returns {Promise<void>}
 */
export async function removeReaction(reactionId) {
  return authenticatedFetch(`${FORUM_BASE}/reactions/${reactionId}/`, {
    method: 'DELETE',
  });
}

/**
 * Fetch reactions for a post
 * @param {string} postId - Post UUID
 * @returns {Promise<Array>} Array of reaction objects
 */
export async function fetchReactions(postId) {
  return authenticatedFetch(`${FORUM_BASE}/reactions/?post=${postId}`);
}
```

**Verification**:
- [ ] File created at `web/src/services/forumService.js`
- [ ] All functions have JSDoc comments
- [ ] CSRF token handling included
- [ ] Error handling implemented

---

#### Task 1.3: Add Forum Sanitization Preset

**File**: `web/src/utils/sanitize.js`

**Add to existing SANITIZE_PRESETS object** (around line 130):
```javascript
  /**
   * FORUM: Rich forum posts with mentions, code blocks, images
   * Use for: Forum posts, thread content
   * Allows: FULL + mentions, code blocks, custom classes for syntax highlighting
   */
  FORUM: {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'blockquote', 'code', 'pre', 'img', 'span', 'div',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'class', 'src', 'alt', 'title',
      'data-mention', 'data-mention-id', // For @mentions
    ],
    ALLOWED_CLASSES: {
      span: ['mention'], // @mention styling
      code: ['language-*'], // Syntax highlighting
      div: ['code-block'], // Code block container
    },
    ALLOW_DATA_ATTR: false,
  },
```

**Verification**:
- [ ] New preset added without breaking existing presets
- [ ] Export includes FORUM preset

---

#### Task 1.4: Create Mock Data Factories

**File**: `web/src/tests/forumUtils.js`

**Implementation**:
```javascript
/**
 * Test utilities for forum components
 */

/**
 * Create mock category data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock category object
 */
export function createMockCategory(overrides = {}) {
  return {
    id: 'cat-123-uuid',
    name: 'Plant Care',
    slug: 'plant-care',
    description: 'Tips and advice for taking care of your plants',
    icon: '🌱',
    parent: null,
    children: [],
    thread_count: 42,
    post_count: 315,
    display_order: 1,
    is_active: true,
    ...overrides,
  };
}

/**
 * Create mock thread data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock thread object
 */
export function createMockThread(overrides = {}) {
  return {
    id: 'thread-456-uuid',
    title: 'How to water succulents?',
    slug: 'how-to-water-succulents',
    author: {
      id: 1,
      username: 'plantlover',
      display_name: 'Plant Lover',
    },
    category: {
      id: 'cat-123-uuid',
      name: 'Plant Care',
      slug: 'plant-care',
      icon: '🌱',
    },
    excerpt: 'Looking for advice on proper watering techniques for succulents.',
    is_pinned: false,
    is_locked: false,
    is_active: true,
    view_count: 240,
    post_count: 15,
    last_activity_at: '2025-10-30T10:30:00Z',
    created_at: '2025-10-28T14:20:00Z',
    ...overrides,
  };
}

/**
 * Create mock post data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock post object
 */
export function createMockPost(overrides = {}) {
  return {
    id: 'post-789-uuid',
    thread: {
      id: 'thread-456-uuid',
      title: 'How to water succulents?',
      slug: 'how-to-water-succulents',
    },
    author: {
      id: 1,
      username: 'plantlover',
      display_name: 'Plant Lover',
      trust_level: 'basic',
    },
    content_raw: '<p>Water sparingly, about once every 2-3 weeks.</p>',
    content_format: 'rich',
    is_first_post: false,
    is_active: true,
    reaction_counts: {
      like: 5,
      helpful: 3,
      love: 1,
      thanks: 2,
    },
    edited_at: null,
    edited_by: null,
    created_at: '2025-10-28T15:45:00Z',
    ...overrides,
  };
}

/**
 * Create mock reaction data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock reaction object
 */
export function createMockReaction(overrides = {}) {
  return {
    id: 'reaction-101-uuid',
    post: 'post-789-uuid',
    user: {
      id: 2,
      username: 'gardener',
      display_name: 'Green Gardener',
    },
    reaction_type: 'helpful',
    is_active: true,
    created_at: '2025-10-29T09:12:00Z',
    ...overrides,
  };
}
```

**Verification**:
- [ ] File created at `web/src/tests/forumUtils.js`
- [ ] All factories match backend API response structure
- [ ] JSDoc comments included

---

### Day 3-4: Category & Thread Card Components

#### Task 2.1: Create CategoryCard Component

**File**: `web/src/components/forum/CategoryCard.jsx`

**Implementation**:
```javascript
import { memo } from 'react';
import { Link } from 'react-router';
import PropTypes from 'prop-types';

/**
 * CategoryCard Component
 *
 * Displays a forum category with stats and subcategories.
 * Used in category list view.
 */
function CategoryCard({ category }) {
  const hasChildren = category.children && category.children.length > 0;

  return (
    <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow">
      <Link
        to={`/forum/${category.slug}`}
        className="block p-6"
      >
        {/* Category Header */}
        <div className="flex items-start gap-4">
          {/* Icon */}
          {category.icon && (
            <div className="text-4xl" aria-hidden="true">
              {category.icon}
            </div>
          )}

          {/* Category Info */}
          <div className="flex-1">
            <h3 className="text-xl font-bold text-gray-900 hover:text-green-600 transition-colors">
              {category.name}
            </h3>

            {category.description && (
              <p className="text-gray-600 mt-1">
                {category.description}
              </p>
            )}

            {/* Stats */}
            <div className="flex gap-4 mt-3 text-sm text-gray-500">
              <span>
                <strong className="text-gray-700">{category.thread_count || 0}</strong> threads
              </span>
              <span>•</span>
              <span>
                <strong className="text-gray-700">{category.post_count || 0}</strong> posts
              </span>
            </div>
          </div>
        </div>

        {/* Subcategories (if any) */}
        {hasChildren && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-gray-500">Subcategories:</span>
              {category.children.map(child => (
                <Link
                  key={child.id}
                  to={`/forum/${child.slug}`}
                  className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-sm text-gray-700 rounded-full transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  {child.icon && <span className="mr-1">{child.icon}</span>}
                  {child.name}
                </Link>
              ))}
            </div>
          </div>
        )}
      </Link>
    </div>
  );
}

CategoryCard.propTypes = {
  category: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    slug: PropTypes.string.isRequired,
    description: PropTypes.string,
    icon: PropTypes.string,
    thread_count: PropTypes.number,
    post_count: PropTypes.number,
    children: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string.isRequired,
        name: PropTypes.string.isRequired,
        slug: PropTypes.string.isRequired,
        icon: PropTypes.string,
      })
    ),
  }).isRequired,
};

export default memo(CategoryCard);
```

**Verification**:
- [ ] File created at `web/src/components/forum/CategoryCard.jsx`
- [ ] Component is memoized
- [ ] PropTypes validation included
- [ ] Accessibility: proper link structure, aria-hidden for decorative icons

---

#### Task 2.2: Create ThreadCard Component

**File**: `web/src/components/forum/ThreadCard.jsx`

**Implementation**:
```javascript
import { memo, useMemo } from 'react';
import { Link } from 'react-router';
import PropTypes from 'prop-types';
import { formatDistanceToNow } from 'date-fns';

/**
 * ThreadCard Component
 *
 * Displays a thread preview in the thread list.
 * Shows title, excerpt, author, stats, and activity time.
 */
function ThreadCard({ thread, compact = false }) {
  // Memoize formatted date to prevent recalculation
  const formattedDate = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(thread.last_activity_at), {
        addSuffix: true
      });
    } catch (error) {
      console.error('[ThreadCard] Error formatting date:', error);
      return 'recently';
    }
  }, [thread.last_activity_at]);

  const threadUrl = `/forum/${thread.category.slug}/${thread.slug}`;

  return (
    <div className={`
      bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow
      ${thread.is_pinned ? 'border-l-4 border-yellow-500 bg-yellow-50' : ''}
      ${thread.is_locked ? 'opacity-75' : ''}
      ${compact ? 'p-3' : 'p-6'}
    `}>
      <Link to={threadUrl} className="block">
        {/* Badges */}
        <div className="flex gap-2 mb-2">
          {thread.is_pinned && (
            <span className="px-2 py-1 bg-yellow-200 text-yellow-900 text-xs font-semibold rounded">
              📌 Pinned
            </span>
          )}
          {thread.is_locked && (
            <span className="px-2 py-1 bg-gray-200 text-gray-700 text-xs font-semibold rounded">
              🔒 Locked
            </span>
          )}
        </div>

        {/* Thread Title */}
        <h3 className={`
          font-bold text-gray-900 hover:text-green-600 transition-colors
          ${compact ? 'text-lg mb-1' : 'text-xl mb-2'}
        `}>
          {thread.title}
        </h3>

        {/* Excerpt (not in compact mode) */}
        {!compact && thread.excerpt && (
          <p className="text-gray-600 mb-4 line-clamp-2">
            {thread.excerpt}
          </p>
        )}

        {/* Metadata */}
        <div className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
          {/* Author */}
          <span className="font-medium text-gray-700">
            {thread.author.display_name || thread.author.username}
          </span>

          <span aria-hidden="true">•</span>

          {/* Category (if compact) */}
          {compact && (
            <>
              <span>
                {thread.category.icon && <span className="mr-1">{thread.category.icon}</span>}
                {thread.category.name}
              </span>
              <span aria-hidden="true">•</span>
            </>
          )}

          {/* Stats */}
          <span title={`${thread.post_count} replies`}>
            💬 {thread.post_count || 0}
          </span>

          <span aria-hidden="true">•</span>

          <span title={`${thread.view_count} views`}>
            👁️ {thread.view_count || 0}
          </span>

          <span aria-hidden="true">•</span>

          {/* Last Activity */}
          <span title={new Date(thread.last_activity_at).toLocaleString()}>
            {formattedDate}
          </span>
        </div>
      </Link>
    </div>
  );
}

ThreadCard.propTypes = {
  thread: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    slug: PropTypes.string.isRequired,
    excerpt: PropTypes.string,
    author: PropTypes.shape({
      id: PropTypes.number.isRequired,
      username: PropTypes.string.isRequired,
      display_name: PropTypes.string,
    }).isRequired,
    category: PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      slug: PropTypes.string.isRequired,
      icon: PropTypes.string,
    }).isRequired,
    is_pinned: PropTypes.bool,
    is_locked: PropTypes.bool,
    is_active: PropTypes.bool,
    view_count: PropTypes.number,
    post_count: PropTypes.number,
    last_activity_at: PropTypes.string.isRequired,
    created_at: PropTypes.string,
  }).isRequired,
  compact: PropTypes.bool,
};

export default memo(ThreadCard);
```

**Verification**:
- [ ] File created at `web/src/components/forum/ThreadCard.jsx`
- [ ] Component is memoized
- [ ] Compact mode supported
- [ ] Date formatting with error handling
- [ ] PropTypes validation included

---

### Day 5-6: Category & Thread List Pages

#### Task 3.1: Create CategoryListPage

**File**: `web/src/pages/forum/CategoryListPage.jsx`

**Implementation**:
```javascript
import { useState, useEffect } from 'react';
import { fetchCategoryTree } from '../../services/forumService';
import CategoryCard from '../../components/forum/CategoryCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';

/**
 * CategoryListPage Component
 *
 * Forum homepage - displays all top-level categories.
 * Route: /forum
 */
export default function CategoryListPage() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await fetchCategoryTree();
        setCategories(data);
      } catch (err) {
        console.error('[CategoryListPage] Error loading categories:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadCategories();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          <strong>Error loading categories:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">
          Community Forums
        </h1>
        <p className="text-lg text-gray-600">
          Connect with fellow plant enthusiasts, share knowledge, and get help with your plants.
        </p>
      </div>

      {/* Categories List */}
      {categories.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">No categories available yet.</p>
          <p className="text-sm mt-2">Check back soon!</p>
        </div>
      ) : (
        <div className="space-y-4">
          {categories.map(category => (
            <CategoryCard key={category.id} category={category} />
          ))}
        </div>
      )}
    </div>
  );
}
```

**Verification**:
- [ ] File created at `web/src/pages/forum/CategoryListPage.jsx`
- [ ] Loading, error, and empty states handled
- [ ] Responsive layout with max-width container
- [ ] Accessibility: semantic HTML, proper headings

---

#### Task 3.2: Create ThreadListPage

**File**: `web/src/pages/forum/ThreadListPage.jsx`

**Implementation**:
```javascript
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router';
import { fetchThreads, fetchCategory } from '../../services/forumService';
import ThreadCard from '../../components/forum/ThreadCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';

/**
 * ThreadListPage Component
 *
 * Displays threads in a category with search, filters, and pagination.
 * Route: /forum/:categorySlug
 */
export default function ThreadListPage() {
  const { categorySlug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [category, setCategory] = useState(null);
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalCount, setTotalCount] = useState(0);

  // Get search params
  const page = parseInt(searchParams.get('page') || '1', 10);
  const search = searchParams.get('search') || '';
  const ordering = searchParams.get('order') || '-last_activity_at';

  const limit = 20;

  // Load category and threads
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load category info and threads in parallel
        const [categoryData, threadsData] = await Promise.all([
          fetchCategory(categorySlug),
          fetchThreads({
            category: categorySlug,
            page,
            limit,
            search,
            ordering
          }),
        ]);

        setCategory(categoryData);
        setThreads(threadsData.items);
        setTotalCount(threadsData.meta.count);
      } catch (err) {
        console.error('[ThreadListPage] Error loading data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [categorySlug, page, search, ordering]);

  // Handle search form submission
  const handleSearch = useCallback((e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const searchQuery = formData.get('search');

    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      if (searchQuery) {
        newParams.set('search', searchQuery);
      } else {
        newParams.delete('search');
      }
      newParams.set('page', '1'); // Reset to page 1
      return newParams;
    });
  }, [setSearchParams]);

  // Handle ordering change
  const handleOrderChange = useCallback((e) => {
    const newOrder = e.target.value;
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      newParams.set('order', newOrder);
      newParams.set('page', '1'); // Reset to page 1
      return newParams;
    });
  }, [setSearchParams]);

  // Handle pagination
  const handlePageChange = useCallback((newPage) => {
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      newParams.set('page', newPage.toString());
      return newParams;
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [setSearchParams]);

  // Calculate pagination
  const totalPages = useMemo(() => {
    return Math.ceil(totalCount / limit);
  }, [totalCount, limit]);

  if (loading && !category) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !category) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-gray-600" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-green-600">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-gray-900">
            {category?.name}
          </li>
        </ol>
      </nav>

      {/* Category Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          {category?.icon && (
            <span className="text-4xl" aria-hidden="true">
              {category.icon}
            </span>
          )}
          <h1 className="text-4xl font-bold text-gray-900">
            {category?.name}
          </h1>
        </div>

        {category?.description && (
          <p className="text-lg text-gray-600">
            {category.description}
          </p>
        )}
      </div>

      {/* Toolbar */}
      <div className="mb-6 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="flex gap-2">
            <input
              type="search"
              name="search"
              placeholder="Search threads..."
              defaultValue={search}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
            <Button type="submit" variant="primary">
              Search
            </Button>
          </div>
        </form>

        {/* Sort & New Thread Button */}
        <div className="flex gap-2">
          <select
            value={ordering}
            onChange={handleOrderChange}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
          >
            <option value="-last_activity_at">Recent Activity</option>
            <option value="-created_at">Newest First</option>
            <option value="created_at">Oldest First</option>
            <option value="-view_count">Most Viewed</option>
            <option value="-post_count">Most Replies</option>
          </select>

          <Link to={`/forum/new-thread?category=${categorySlug}`}>
            <Button variant="primary">
              + New Thread
            </Button>
          </Link>
        </div>
      </div>

      {/* Active Filters */}
      {search && (
        <div className="mb-4 flex items-center gap-2">
          <span className="text-sm text-gray-600">
            Searching for: <strong>{search}</strong>
          </span>
          <button
            onClick={() => {
              setSearchParams(prev => {
                const newParams = new URLSearchParams(prev);
                newParams.delete('search');
                newParams.set('page', '1');
                return newParams;
              });
            }}
            className="text-sm text-red-600 hover:text-red-700 underline"
          >
            Clear
          </button>
        </div>
      )}

      {/* Threads List */}
      {loading ? (
        <LoadingSpinner />
      ) : threads.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">No threads found.</p>
          <p className="text-sm mt-2">
            {search ? 'Try a different search query.' : 'Be the first to start a discussion!'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {threads.map(thread => (
            <ThreadCard key={thread.id} thread={thread} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-8 flex justify-center items-center gap-2">
          <Button
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            variant="outline"
          >
            Previous
          </Button>

          <span className="px-4 py-2 text-gray-700">
            Page {page} of {totalPages}
          </span>

          <Button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            variant="outline"
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
```

**Verification**:
- [ ] File created at `web/src/pages/forum/ThreadListPage.jsx`
- [ ] Search, filter, pagination implemented
- [ ] Breadcrumb navigation
- [ ] "New Thread" button (links to protected route)
- [ ] Loading and error states

---

#### Task 3.3: Update Routing Configuration

**File**: `web/src/App.jsx`

**Add these routes** (after existing forum route around line 50):
```javascript
import { lazy, Suspense } from 'react';

// Lazy load forum components
const CategoryListPage = lazy(() => import('./pages/forum/CategoryListPage'));
const ThreadListPage = lazy(() => import('./pages/forum/ThreadListPage'));

// In routes array, replace existing ForumPage route:
{
  path: '/forum',
  element: (
    <Suspense fallback={<LoadingSpinner />}>
      <CategoryListPage />
    </Suspense>
  ),
},
{
  path: '/forum/:categorySlug',
  element: (
    <Suspense fallback={<LoadingSpinner />}>
      <ThreadListPage />
    </Suspense>
  ),
},
```

**Verification**:
- [ ] Routes added to `web/src/App.jsx`
- [ ] Lazy loading with Suspense
- [ ] LoadingSpinner fallback
- [ ] Navigate to `/forum` shows categories
- [ ] Navigate to `/forum/plant-care` shows threads

---

## Week 15: Thread Detail & Post Management

### Day 7-8: Post Components

#### Task 4.1: Create PostCard Component

**File**: `web/src/components/forum/PostCard.jsx`

```javascript
import { memo, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { formatDistanceToNow } from 'date-fns';
import { sanitizeHtml, SANITIZE_PRESETS } from '../../utils/sanitize';
import { useAuth } from '../../contexts/AuthContext';

/**
 * PostCard Component
 *
 * Displays a single post in a thread.
 * Includes author info, content, reactions, and edit/delete options.
 */
function PostCard({ post, onEdit, onDelete }) {
  const { user } = useAuth();
  const [showActions, setShowActions] = useState(false);

  const isAuthor = user && user.id === post.author.id;
  const isModerator = user && (user.is_staff || user.is_moderator);
  const canEdit = isAuthor || isModerator;

  // Memoize formatted date
  const formattedDate = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(post.created_at), { addSuffix: true });
    } catch {
      return 'recently';
    }
  }, [post.created_at]);

  // Sanitize content for display
  const sanitizedContent = useMemo(() => {
    return sanitizeHtml(post.content_raw, SANITIZE_PRESETS.FORUM);
  }, [post.content_raw]);

  return (
    <div
      className={`
        bg-white rounded-lg shadow-md p-6
        ${post.is_first_post ? 'border-l-4 border-green-500' : ''}
      `}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Post Header */}
      <div className="flex items-start justify-between mb-4">
        {/* Author Info */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
            <span className="text-xl font-bold text-green-700">
              {post.author.display_name?.[0] || post.author.username[0]}
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900">
                {post.author.display_name || post.author.username}
              </span>

              {post.author.trust_level && (
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded">
                  {post.author.trust_level}
                </span>
              )}

              {post.is_first_post && (
                <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded">
                  Original Post
                </span>
              )}
            </div>

            <div className="text-sm text-gray-500">
              <span title={new Date(post.created_at).toLocaleString()}>
                {formattedDate}
              </span>

              {post.edited_at && (
                <>
                  <span className="mx-1">•</span>
                  <span className="italic">
                    Edited {formatDistanceToNow(new Date(post.edited_at), { addSuffix: true })}
                    {post.edited_by && ` by ${post.edited_by.display_name || post.edited_by.username}`}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Actions (edit/delete) */}
        {canEdit && showActions && (
          <div className="flex gap-2">
            <button
              onClick={() => onEdit?.(post)}
              className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              title="Edit post"
            >
              ✏️ Edit
            </button>
            <button
              onClick={() => onDelete?.(post)}
              className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
              title="Delete post"
            >
              🗑️ Delete
            </button>
          </div>
        )}
      </div>

      {/* Post Content */}
      <div
        className="prose max-w-none mb-4"
        dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      />

      {/* Reactions */}
      {post.reaction_counts && Object.keys(post.reaction_counts).length > 0 && (
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          {Object.entries(post.reaction_counts).map(([type, count]) => (
            count > 0 && (
              <button
                key={type}
                className="flex items-center gap-1 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-sm transition-colors"
                title={`${count} ${type} reactions`}
              >
                <span>{getReactionEmoji(type)}</span>
                <span className="font-medium">{count}</span>
              </button>
            )
          ))}
        </div>
      )}
    </div>
  );
}

// Helper function for reaction emojis
function getReactionEmoji(type) {
  const emojis = {
    like: '👍',
    love: '❤️',
    helpful: '💡',
    thanks: '🙏',
  };
  return emojis[type] || '✨';
}

PostCard.propTypes = {
  post: PropTypes.shape({
    id: PropTypes.string.isRequired,
    author: PropTypes.shape({
      id: PropTypes.number.isRequired,
      username: PropTypes.string.isRequired,
      display_name: PropTypes.string,
      trust_level: PropTypes.string,
    }).isRequired,
    content_raw: PropTypes.string.isRequired,
    content_format: PropTypes.string,
    is_first_post: PropTypes.bool,
    is_active: PropTypes.bool,
    reaction_counts: PropTypes.object,
    created_at: PropTypes.string.isRequired,
    edited_at: PropTypes.string,
    edited_by: PropTypes.shape({
      username: PropTypes.string,
      display_name: PropTypes.string,
    }),
  }).isRequired,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
};

export default memo(PostCard);
```

**Verification**:
- [ ] Component created with XSS protection
- [ ] Shows edit/delete for authors/moderators
- [ ] Displays reaction counts
- [ ] Memoized for performance

---

#### Task 4.2: Create TipTap Editor Component

**File**: `web/src/components/forum/TipTapEditor.jsx`

```javascript
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import PropTypes from 'prop-types';

/**
 * TipTapEditor Component
 *
 * Rich text editor for forum posts using TipTap.
 * Provides basic formatting, links, and sanitization.
 */
export default function TipTapEditor({
  content = '',
  onChange,
  placeholder = 'Write your post...',
  editable = true,
  className = '',
}) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [2, 3], // Only H2 and H3
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-green-600 hover:underline',
          target: '_blank',
          rel: 'noopener noreferrer',
        },
      }),
      Placeholder.configure({
        placeholder,
      }),
    ],
    content,
    editable,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange?.(html);
    },
  });

  if (!editor) {
    return <div className="p-4 text-gray-500">Loading editor...</div>;
  }

  return (
    <div className={`border border-gray-300 rounded-lg overflow-hidden ${className}`}>
      {/* Toolbar */}
      {editable && (
        <div className="bg-gray-50 border-b border-gray-300 p-2 flex gap-1 flex-wrap">
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            isActive={editor.isActive('bold')}
            title="Bold (Ctrl+B)"
          >
            <strong>B</strong>
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            isActive={editor.isActive('italic')}
            title="Italic (Ctrl+I)"
          >
            <em>I</em>
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleStrike().run()}
            isActive={editor.isActive('strike')}
            title="Strikethrough"
          >
            <s>S</s>
          </ToolbarButton>

          <div className="w-px bg-gray-300 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            isActive={editor.isActive('heading', { level: 2 })}
            title="Heading 2"
          >
            H2
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            isActive={editor.isActive('heading', { level: 3 })}
            title="Heading 3"
          >
            H3
          </ToolbarButton>

          <div className="w-px bg-gray-300 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            isActive={editor.isActive('bulletList')}
            title="Bullet List"
          >
            •
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            isActive={editor.isActive('orderedList')}
            title="Numbered List"
          >
            1.
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            isActive={editor.isActive('blockquote')}
            title="Quote"
          >
            "
          </ToolbarButton>

          <div className="w-px bg-gray-300 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCode().run()}
            isActive={editor.isActive('code')}
            title="Inline Code"
          >
            {'</>'}
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            isActive={editor.isActive('codeBlock')}
            title="Code Block"
          >
            {'{ }'}
          </ToolbarButton>

          <div className="w-px bg-gray-300 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => {
              const url = window.prompt('Enter URL:');
              if (url) {
                editor.chain().focus().setLink({ href: url }).run();
              }
            }}
            isActive={editor.isActive('link')}
            title="Insert Link"
          >
            🔗
          </ToolbarButton>

          {editor.isActive('link') && (
            <ToolbarButton
              onClick={() => editor.chain().focus().unsetLink().run()}
              title="Remove Link"
            >
              ⛓️‍💥
            </ToolbarButton>
          )}
        </div>
      )}

      {/* Editor Content */}
      <EditorContent
        editor={editor}
        className="prose max-w-none p-4 min-h-[200px] focus:outline-none"
      />
    </div>
  );
}

// Toolbar button component
function ToolbarButton({ onClick, isActive, title, children }) {
  return (
    <button
      onClick={onClick}
      type="button"
      title={title}
      className={`
        px-3 py-1.5 rounded text-sm font-medium transition-colors
        ${isActive
          ? 'bg-green-200 text-green-900'
          : 'bg-white text-gray-700 hover:bg-gray-100'
        }
      `}
    >
      {children}
    </button>
  );
}

ToolbarButton.propTypes = {
  onClick: PropTypes.func.isRequired,
  isActive: PropTypes.bool,
  title: PropTypes.string,
  children: PropTypes.node.isRequired,
};

TipTapEditor.propTypes = {
  content: PropTypes.string,
  onChange: PropTypes.func,
  placeholder: PropTypes.string,
  editable: PropTypes.bool,
  className: PropTypes.string,
};
```

**Verification**:
- [ ] TipTap installed and working
- [ ] Toolbar with formatting buttons
- [ ] Link support
- [ ] Placeholder text
- [ ] HTML output sanitized in PostCard

---

### Day 9-10: Thread Detail Page

#### Task 5.1: Create ThreadDetailPage

**File**: `web/src/pages/forum/ThreadDetailPage.jsx`

```javascript
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { fetchThread, fetchPosts, createPost, deletePost } from '../../services/forumService';
import { useAuth } from '../../contexts/AuthContext';
import PostCard from '../../components/forum/PostCard';
import TipTapEditor from '../../components/forum/TipTapEditor';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';

/**
 * ThreadDetailPage Component
 *
 * Displays a thread with its posts and allows replying.
 * Route: /forum/:categorySlug/:threadSlug
 */
export default function ThreadDetailPage() {
  const { categorySlug, threadSlug } = useParams();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();

  const [thread, setThread] = useState(null);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Reply form state
  const [replyContent, setReplyContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [replyError, setReplyError] = useState(null);

  // Load thread and posts
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [threadData, postsData] = await Promise.all([
          fetchThread(threadSlug),
          fetchPosts({ thread: threadSlug, limit: 100 }), // Load all posts (consider pagination later)
        ]);

        setThread(threadData);
        setPosts(postsData.items);
      } catch (err) {
        console.error('[ThreadDetailPage] Error loading data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [threadSlug]);

  // Handle reply submission
  const handleReplySubmit = useCallback(async (e) => {
    e.preventDefault();

    if (!isAuthenticated) {
      navigate('/login', { state: { from: window.location.pathname } });
      return;
    }

    if (!replyContent.trim()) {
      setReplyError('Reply content is required');
      return;
    }

    try {
      setIsSubmitting(true);
      setReplyError(null);

      const newPost = await createPost({
        thread: thread.id,
        content_raw: replyContent,
        content_format: 'rich', // TipTap outputs HTML
      });

      setPosts(prev => [...prev, newPost]);
      setReplyContent(''); // Clear editor

      // Scroll to new post
      setTimeout(() => {
        const element = document.getElementById(`post-${newPost.id}`);
        element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    } catch (err) {
      console.error('[ThreadDetailPage] Error creating post:', err);
      setReplyError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }, [isAuthenticated, navigate, replyContent, thread]);

  // Handle post deletion
  const handleDeletePost = useCallback(async (post) => {
    if (!window.confirm('Are you sure you want to delete this post?')) {
      return;
    }

    try {
      await deletePost(post.id);
      setPosts(prev => prev.filter(p => p.id !== post.id));
    } catch (err) {
      console.error('[ThreadDetailPage] Error deleting post:', err);
      alert(`Failed to delete post: ${err.message}`);
    }
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !thread) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          <strong>Error:</strong> {error || 'Thread not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-gray-600" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-green-600">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li>
            <Link
              to={`/forum/${categorySlug}`}
              className="hover:text-green-600"
            >
              {thread.category.name}
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-gray-900">
            {thread.title}
          </li>
        </ol>
      </nav>

      {/* Thread Header */}
      <div className="mb-8 bg-white rounded-lg shadow-md p-6">
        <div className="flex items-start gap-4 mb-4">
          {thread.category.icon && (
            <span className="text-4xl" aria-hidden="true">
              {thread.category.icon}
            </span>
          )}

          <div className="flex-1">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {thread.title}
            </h1>

            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span>
                by <strong className="text-gray-700">
                  {thread.author.display_name || thread.author.username}
                </strong>
              </span>
              <span>•</span>
              <span>💬 {posts.length} replies</span>
              <span>•</span>
              <span>👁️ {thread.view_count} views</span>
            </div>
          </div>

          {/* Badges */}
          <div className="flex gap-2">
            {thread.is_pinned && (
              <span className="px-3 py-1 bg-yellow-200 text-yellow-900 text-sm font-semibold rounded">
                📌 Pinned
              </span>
            )}
            {thread.is_locked && (
              <span className="px-3 py-1 bg-gray-200 text-gray-700 text-sm font-semibold rounded">
                🔒 Locked
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Posts List */}
      <div className="space-y-4 mb-8">
        {posts.map((post) => (
          <div key={post.id} id={`post-${post.id}`}>
            <PostCard
              post={post}
              onDelete={handleDeletePost}
            />
          </div>
        ))}
      </div>

      {/* Reply Form */}
      {!thread.is_locked && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-xl font-bold mb-4">Post Your Reply</h3>

          {!isAuthenticated ? (
            <div className="text-center py-8">
              <p className="text-gray-600 mb-4">
                You must be logged in to reply to this thread.
              </p>
              <Link to="/login" state={{ from: window.location.pathname }}>
                <Button variant="primary">Log In</Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleReplySubmit}>
              <TipTapEditor
                content={replyContent}
                onChange={setReplyContent}
                placeholder="Write your reply..."
                className="mb-4"
              />

              {replyError && (
                <div className="mb-4 p-3 bg-red-50 text-red-800 rounded">
                  {replyError}
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  type="submit"
                  variant="primary"
                  loading={isSubmitting}
                  disabled={!replyContent.trim()}
                >
                  {isSubmitting ? 'Posting...' : 'Post Reply'}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setReplyContent('')}
                  disabled={isSubmitting}
                >
                  Clear
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {thread.is_locked && (
        <div className="bg-gray-100 border border-gray-300 text-gray-700 px-6 py-4 rounded-lg text-center">
          🔒 This thread is locked. No new replies can be posted.
        </div>
      )}
    </div>
  );
}
```

**Verification**:
- [ ] Thread header with metadata
- [ ] Posts list with PostCard components
- [ ] Reply form with TipTap editor
- [ ] Authentication check
- [ ] Locked thread handling
- [ ] Breadcrumb navigation

---

### Day 11-12: Testing & Polish

#### Task 6.1: Create Component Tests

**File**: `web/src/components/forum/ThreadCard.test.jsx`

```javascript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import ThreadCard from './ThreadCard';
import { createMockThread } from '../../tests/forumUtils';

describe('ThreadCard', () => {
  const renderThreadCard = (thread) => {
    return render(
      <BrowserRouter>
        <ThreadCard thread={thread} />
      </BrowserRouter>
    );
  };

  it('renders thread title and excerpt', () => {
    const thread = createMockThread({
      title: 'Test Thread',
      excerpt: 'Test excerpt content',
    });

    renderThreadCard(thread);

    expect(screen.getByText('Test Thread')).toBeInTheDocument();
    expect(screen.getByText('Test excerpt content')).toBeInTheDocument();
  });

  it('shows pinned badge when thread is pinned', () => {
    const thread = createMockThread({ is_pinned: true });

    renderThreadCard(thread);

    expect(screen.getByText(/pinned/i)).toBeInTheDocument();
  });

  it('shows locked badge when thread is locked', () => {
    const thread = createMockThread({ is_locked: true });

    renderThreadCard(thread);

    expect(screen.getByText(/locked/i)).toBeInTheDocument();
  });

  it('displays thread stats correctly', () => {
    const thread = createMockThread({
      post_count: 15,
      view_count: 240,
    });

    renderThreadCard(thread);

    expect(screen.getByText(/15/)).toBeInTheDocument(); // Post count
    expect(screen.getByText(/240/)).toBeInTheDocument(); // View count
  });

  it('renders in compact mode', () => {
    const thread = createMockThread({ excerpt: 'Hidden in compact' });

    renderThreadCard(thread, true); // compact=true

    expect(screen.queryByText('Hidden in compact')).not.toBeInTheDocument();
  });
});
```

**More test files to create**:
- `web/src/components/forum/CategoryCard.test.jsx`
- `web/src/components/forum/PostCard.test.jsx`
- `web/src/pages/forum/CategoryListPage.test.jsx`

**Verification**:
- [ ] At least 10+ component tests written
- [ ] Tests pass: `npm run test`
- [ ] Test coverage >70%

---

#### Task 6.2: Update Navigation Header

**File**: `web/src/components/layout/Header.jsx`

**Add forum link to navigation** (around line 50):
```javascript
<Link
  to="/forum"
  className="text-gray-700 hover:text-green-600 px-3 py-2 rounded-md text-sm font-medium transition-colors"
>
  Forum
</Link>
```

**Verification**:
- [ ] Forum link appears in header
- [ ] Active state styling works
- [ ] Mobile menu includes forum link

---

## Completion Checklist

### Week 14 Deliverables
- [ ] forumService.js with all API functions
- [ ] FORUM sanitization preset
- [ ] Mock data factories (forumUtils.js)
- [ ] CategoryCard component
- [ ] ThreadCard component
- [ ] CategoryListPage
- [ ] ThreadListPage
- [ ] Routing configuration updated
- [ ] Navigation header updated

### Week 15 Deliverables
- [ ] PostCard component
- [ ] TipTapEditor component
- [ ] ThreadDetailPage
- [ ] Reply functionality
- [ ] Post deletion
- [ ] Component tests (10+ tests)
- [ ] XSS protection verified
- [ ] Mobile responsive design

### Code Quality
- [ ] All components use PropTypes
- [ ] All components are memoized where appropriate
- [ ] XSS protection on all user content
- [ ] Error handling on all API calls
- [ ] Loading states for all async operations
- [ ] Accessibility: keyboard navigation works
- [ ] Accessibility: ARIA attributes where needed

### Testing
- [ ] Run all tests: `npm run test`
- [ ] No console errors in browser
- [ ] Test in mobile viewport
- [ ] Test authentication flows
- [ ] Test with backend API (not mocks)

### Documentation
- [ ] Update CLAUDE.md with forum info
- [ ] Add forum section to README.md
- [ ] Document any new environment variables

---

## Troubleshooting

### Common Issues

**1. CORS Errors**
- Verify `VITE_API_URL` in `.env`
- Check Django CORS settings include port 5174
- Ensure cookies enabled in browser

**2. Authentication Not Working**
- Check JWT token in browser cookies
- Verify CSRF token in request headers
- Test login flow first

**3. TipTap Not Loading**
- Run `npm install` again
- Clear node_modules and reinstall
- Check browser console for errors

**4. Posts Not Displaying**
- Verify XSS sanitization not too strict
- Check API response structure matches PropTypes
- Test with simple plain text first

**5. Styling Issues**
- Run `npm run dev` to rebuild Tailwind
- Check Tailwind config includes forum files
- Verify CSS classes are valid Tailwind 4 syntax

---

## Performance Optimization (Optional)

### If Time Permits

**1. Virtualized Thread List** (for 100+ threads):
```bash
npm install @tanstack/react-virtual
```

**2. Optimistic Updates** (instant UI feedback):
- Use React 19 `useOptimistic` hook
- Update local state before API response
- Revert on error

**3. Image Lazy Loading**:
- Add `loading="lazy"` to images
- Use IntersectionObserver for custom loading

**4. Code Splitting**:
- Already implemented with lazy routes
- Consider splitting TipTap into separate chunk

---

## Next Steps After Phase 6

**Phase 7: Advanced Features** (optional):
- Real-time updates (WebSockets)
- Notifications system
- User mentions (@username)
- Image attachments
- Markdown support toggle
- Thread subscriptions
- Moderation tools UI

**Phase 8: Mobile App**:
- Adapt forum components for Flutter
- Implement offline reading
- Push notifications for replies

---

## Success Criteria

✅ **Phase 6 is complete when**:
1. Users can browse categories
2. Users can view threads in a category
3. Users can read thread posts
4. Authenticated users can create threads
5. Authenticated users can reply to threads
6. XSS protection works on all content
7. Mobile responsive design
8. 10+ component tests passing
9. No console errors in production build
10. Code review grade A (90+/100)

---

**Good luck! Follow this workfile step-by-step and you'll have a production-ready forum frontend in 2-3 weeks.** 🚀
