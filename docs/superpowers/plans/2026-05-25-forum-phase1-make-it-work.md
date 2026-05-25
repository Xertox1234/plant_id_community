# Forum Phase 1 — "Make It Work" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the abandoned React forum load and work end-to-end against the live django-machina + DRF backend, without changing the backend, via a translation-layer `forumService` and hybrid id+slug URLs (Option C).

**Architecture:** The backend serves an id-based, action-suffixed API with machina-shaped fields (`subject`/`poster`/`last_post_on`). The React app expects a clean slug-based domain model (`title`/`author`/`last_activity_at`). We bridge entirely on the frontend: pure mapper functions translate backend responses → React types, `forumService` calls the real endpoints, and URLs become id-anchored with a decorative slug (`/forum/{id}-{slug}/{id}-{slug}`) so lookups use the unambiguous integer id (machina slugs are **not** unique).

**Tech Stack:** React 19, TypeScript (tsconfig `strict: false`), Vitest (unit/component, `global.fetch` mock), Playwright (e2e), React Router (`react-router-dom`).

**Spec:** `docs/superpowers/specs/2026-05-25-forum-modernization-hardening-design.md`

---

## Backend contract (verified — the translation target)

All under `${VITE_API_URL}/api/v1/forum`. Global DRF pagination is on (`PageNumberPagination`, `PAGE_SIZE=20`), so `ListAPIView` endpoints return `{count, next, previous, results}`.

| Purpose | Method + path | Response envelope |
|---|---|---|
| List categories | `GET /categories/` | `{count,next,previous,results:[Forum]}` |
| Topics in category | `GET /categories/{forumId}/topics/` | `{count,next,previous,results:[Topic]}` |
| Create topic | `POST /categories/{forumId}/topics/create/` | `{message, topic:Topic, first_post_id}` |
| All topics | `GET /topics/?page=N` | `{count,next,previous,results:[Topic]}` |
| Topic detail (+first page posts) | `GET /topics/{id}/` | `{topic:Topic, posts:{results:[Post],count,current_page,total_pages,has_next,has_previous}}` |
| Posts in topic | `GET /posts/?topic={id}&page=N` | `{count,next,previous,results:[Post]}` |
| Create post | `POST /posts/create/` body `{topic, content, content_format}` | `{message, data:Post}` |
| Update post | `PATCH /posts/{id}/` body `{content, content_format}` | `{message, data:Post}` |
| Delete post | `DELETE /posts/{id}/delete/` | `{message}` (204) |
| Reactions (read) | `GET /posts/{id}/reactions/` | `{post_id, reactions:{type:{count,users}}, user_reactions:[type], total_reactions}` |
| Reaction toggle | `POST /posts/{id}/reactions/` body `{reaction_type}` | `{success, action:"added"\|"removed", reactions:{...}, user_reactions:[type], ...}` |
| List images | `GET /posts/{id}/images/` | `{post_id, images:[Image], count}` |
| Upload images | `POST /posts/{id}/images/upload/` form field **`images`** (multi) | `{message, images:[Image], post_id}` |
| Update image (alt/order) | `PATCH /posts/{id}/images/{imgId}/` | image dict |
| Delete image | `DELETE /posts/{id}/images/{imgId}/delete/` | `{message}` |
| Search | `GET /search/?q=` | `{query, topics:[Topic], posts:[Post]}` (top 10 each, no pagination) |

**Backend field shapes:**

- `Forum`: `{id, name, description, topics_count, posts_count, last_activity}` (no slug field in this serializer).
- `Topic`: `{id, subject, poster:User, forum:{id,name,slug}, created, posts_count, last_post_on, replies_count, views_count, last_poster?}` (Topic has **no** `slug` in serializer output).
- `Post`: `{id, content, poster:User, created, updated, rich_content, content_format, ai_assisted}`.
- `User`: `{id, username, first_name, last_name}`.
- `Image`: `{id, image_url, thumbnail_url, large_thumbnail_url, upload_order, alt_text, original_filename, file_size, file_size_mb, display_name, created_at}`.

## Known Phase-1 limitations (intentional — backend stays untouched)

- **Category tree is flat.** No backend tree endpoint; `fetchCategoryTree` returns the flat category list (no `children`).
- **`fetchCategory` does a full category-list fetch + in-memory filter by id** — the backend has no single-category detail endpoint. Fine at forum scale (categories are few); revisit only if the category count grows large.
- **Thread-list `search`/`ordering`/`limit` are not backend-supported** on `/categories/{id}/topics/`; only `page` is honored (fixed page size 20). In-category search and custom ordering are deferred. Cross-forum search uses the dedicated search page.
- **Image reorder** is implemented client-side as sequential `PATCH` calls to `/posts/{id}/images/{imgId}/` (no bulk reorder endpoint). On a mid-sequence failure the order may be left partially applied; the `ImageUploadWidget` reorder handler must re-fetch via `fetchPostImages` on error so the UI resyncs to the true server order rather than caching a partial reorder.
- **`file_size_mb` / `display_name`** from the backend image dict are intentionally not mapped — they're absent from the `Attachment` type and no component reads them (verified).
- **Search filters** (`category`/`author`/`date_*`) are ignored by the backend; passed through but non-functional until Phase 2+.

These are documented, not silent — surface them in the PR description.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `web/src/utils/forumUrls.ts` | Create | `slugifyTitle`, `parseLeadingId`, `categoryPath`, `threadPath` — hybrid id+slug URL building/parsing |
| `web/src/utils/forumUrls.test.ts` | Create | Unit tests for URL helpers |
| `web/src/services/forumMappers.ts` | Create | Pure functions: backend shapes → React types |
| `web/src/services/forumMappers.test.ts` | Create | Unit tests for mappers |
| `web/src/services/forumService.ts` | Rewrite | Translation-layer API client using mappers |
| `web/src/services/forumService.test.ts` | Rewrite | Tests asserting real endpoints + mapped output |
| `web/src/types/forum.ts` | Modify | Add `ReactionToggleResult`; align `ReactionSummary` |
| `web/src/components/forum/CategoryCard.tsx` | Modify | Use `categoryPath()` for links |
| `web/src/components/forum/ThreadCard.tsx` | Modify | Use `threadPath()` for link |
| `web/src/pages/forum/ThreadListPage.tsx` | Modify | Parse forum id from route param |
| `web/src/pages/forum/ThreadDetailPage.tsx` | Modify | Parse topic id from route param; wire reactions |
| `web/src/components/forum/PostCard.tsx` | Modify | Wire reaction buttons to an `onReact` handler |
| `web/e2e/forum-golden-path.spec.ts` | Create | Playwright e2e for the golden path |

Run all web commands from `web/`. Type-check gate: `npm run type-check` must pass (zero errors).

---

## Task 1: URL helper (`forumUrls.ts`)

**Files:**

- Create: `web/src/utils/forumUrls.ts`
- Test: `web/src/utils/forumUrls.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// web/src/utils/forumUrls.test.ts
import { describe, it, expect } from 'vitest';
import { slugifyTitle, parseLeadingId, categoryPath, threadPath } from './forumUrls';
import type { Category, Thread } from '../types/forum';

describe('forumUrls', () => {
  it('slugifies titles', () => {
    expect(slugifyTitle('How to care for Succulents?!')).toBe('how-to-care-for-succulents');
    expect(slugifyTitle('  Multiple   spaces ')).toBe('multiple-spaces');
    expect(slugifyTitle('')).toBe('topic');
  });

  it('parses the leading integer id from an id-slug param', () => {
    expect(parseLeadingId('12-how-to-care')).toBe(12);
    expect(parseLeadingId('7')).toBe(7);
    expect(parseLeadingId('not-a-number')).toBeNull();
  });

  it('builds id-anchored category and thread paths', () => {
    const category = { id: '3', name: 'Plant Care', slug: 'plant-care' } as Category;
    const thread = { id: '12', title: 'Succulent help', slug: 'succulent-help', category } as Thread;
    expect(categoryPath(category)).toBe('/forum/3-plant-care');
    expect(threadPath(category, thread)).toBe('/forum/3-plant-care/12-succulent-help');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/utils/forumUrls.test.ts`
Expected: FAIL — `forumUrls` module not found.

- [ ] **Step 3: Write the implementation**

```typescript
// web/src/utils/forumUrls.ts
import type { Category, Thread } from '../types/forum';

/** Lowercase, hyphenate, strip non-alphanumerics. Falls back to "topic" when empty. */
export function slugifyTitle(input: string): string {
  const slug = (input || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'topic';
}

/** Extract the leading integer id from an "id-slug" route param. Returns null if absent. */
export function parseLeadingId(param: string | undefined): number | null {
  if (!param) return null;
  const id = parseInt(param.split('-')[0], 10);
  return Number.isNaN(id) ? null : id;
}

/** /forum/{id}-{slug} — id is the lookup key, slug is decorative. */
export function categoryPath(category: Pick<Category, 'id' | 'slug' | 'name'>): string {
  const slug = category.slug || slugifyTitle(category.name);
  return `/forum/${category.id}-${slug}`;
}

/** /forum/{catId}-{catSlug}/{topicId}-{topicSlug} */
export function threadPath(
  category: Pick<Category, 'id' | 'slug' | 'name'>,
  thread: Pick<Thread, 'id' | 'slug' | 'title'>
): string {
  const tSlug = thread.slug || slugifyTitle(thread.title);
  return `${categoryPath(category)}/${thread.id}-${tSlug}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/utils/forumUrls.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/utils/forumUrls.ts web/src/utils/forumUrls.test.ts
git commit -m "feat(forum): add hybrid id+slug URL helpers"
```

---

## Task 2: Type adjustments (`types/forum.ts`)

The translation layer needs a result type for the reaction toggle and a normalized reaction summary. The existing `Reaction` CRUD type is no longer produced by the backend (toggle model), but leave it in place — `PostCard` uses `reaction_counts` (a `Record<string, number>`), which we keep.

**Files:**

- Modify: `web/src/types/forum.ts`

- [ ] **Step 1: Add the new types at the end of the file**

```typescript
// web/src/types/forum.ts  (append)

/** Result of toggling a reaction on a post (backend toggle endpoint). */
export interface ReactionToggleResult {
  action: 'added' | 'removed';
  reaction_type: string;
  /** Map of reaction_type -> count, e.g. { like: 5, love: 2 } */
  reaction_counts: Record<string, number>;
  /** Reaction types the current user currently has active on this post */
  user_reactions: string[];
}
```

- [ ] **Step 2: Verify type-check passes**

Run: `cd web && npm run type-check`
Expected: PASS (zero errors).

- [ ] **Step 3: Commit**

```bash
git add web/src/types/forum.ts
git commit -m "feat(forum): add ReactionToggleResult type"
```

---

## Task 3: Mapper functions (`forumMappers.ts`)

Pure, side-effect-free translation from backend shapes to React types. Coerce ids to strings (React types use `id: string`), derive display names and decorative slugs.

**Files:**

- Create: `web/src/services/forumMappers.ts`
- Test: `web/src/services/forumMappers.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// web/src/services/forumMappers.test.ts
import { describe, it, expect } from 'vitest';
import {
  mapUser,
  mapForumToCategory,
  mapTopicToThread,
  mapPostToPost,
  mapImageToAttachment,
} from './forumMappers';

describe('forumMappers', () => {
  it('maps a backend user to a forum author with a display name', () => {
    expect(mapUser({ id: 1, username: 'jdoe', first_name: 'Jane', last_name: 'Doe' })).toMatchObject({
      id: '1',
      username: 'jdoe',
      display_name: 'Jane Doe',
    });
    expect(mapUser({ id: 2, username: 'nobody', first_name: '', last_name: '' }).display_name).toBe(
      'nobody'
    );
    expect(mapUser(null)).toBeNull();
  });

  it('maps a forum to a category (renames counts, derives slug)', () => {
    const c = mapForumToCategory({
      id: 3,
      name: 'Plant Care',
      description: 'Tips',
      topics_count: 10,
      posts_count: 42,
      last_activity: '2026-01-02T00:00:00Z',
    });
    expect(c).toMatchObject({
      id: '3',
      name: 'Plant Care',
      slug: 'plant-care',
      thread_count: 10,
      post_count: 42,
    });
  });

  it('maps a topic to a thread (subject->title, last_post_on->last_activity_at)', () => {
    const t = mapTopicToThread({
      id: 12,
      subject: 'Succulent help',
      poster: { id: 1, username: 'jdoe', first_name: 'Jane', last_name: 'Doe' },
      forum: { id: 3, name: 'Plant Care', slug: 'plant-care' },
      created: '2026-01-01T00:00:00Z',
      posts_count: 5,
      last_post_on: '2026-01-02T00:00:00Z',
      replies_count: 4,
      views_count: 99,
    });
    expect(t).toMatchObject({
      id: '12',
      title: 'Succulent help',
      slug: 'succulent-help',
      category: { id: '3', name: 'Plant Care', slug: 'plant-care' },
      last_activity_at: '2026-01-02T00:00:00Z',
      post_count: 5,
      view_count: 99,
    });
    expect(t.author?.display_name).toBe('Jane Doe');
  });

  it('maps a post (content->content_raw, created->created_at)', () => {
    const p = mapPostToPost(
      {
        id: 50,
        content: '<p>hello</p>',
        poster: { id: 1, username: 'jdoe', first_name: '', last_name: '' },
        created: '2026-01-01T00:00:00Z',
        updated: '2026-01-01T00:00:00Z',
        content_format: 'html',
      },
      '12'
    );
    expect(p).toMatchObject({
      id: '50',
      thread: '12',
      content_raw: '<p>hello</p>',
      content_format: 'html',
      reaction_counts: {},
    });
  });

  it('maps an image to an attachment (image_url->image, upload_order->display_order)', () => {
    const a = mapImageToAttachment({
      id: 7,
      image_url: 'http://x/a.jpg',
      thumbnail_url: 'http://x/a_t.jpg',
      large_thumbnail_url: 'http://x/a_l.jpg',
      upload_order: 2,
      alt_text: 'a plant',
      original_filename: 'a.jpg',
      file_size: 1234,
      created_at: '2026-01-01T00:00:00Z',
    });
    expect(a).toMatchObject({
      id: '7',
      image: 'http://x/a.jpg',
      image_url: 'http://x/a.jpg',
      thumbnail_url: 'http://x/a_t.jpg',
      display_order: 2,
      alt_text: 'a plant',
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/services/forumMappers.test.ts`
Expected: FAIL — `forumMappers` not found.

- [ ] **Step 3: Write the implementation**

```typescript
// web/src/services/forumMappers.ts
import { slugifyTitle } from '../utils/forumUrls';
import type { Category, Thread, Post, Attachment } from '../types/forum';

// Backend response shapes (machina-flavored). Kept local — internal to the service layer.
export interface BackendUser {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
}
export interface BackendForum {
  id: number;
  name: string;
  description?: string;
  topics_count?: number;
  posts_count?: number;
  last_activity?: string | null;
  slug?: string | null;
}
export interface BackendTopic {
  id: number;
  subject: string;
  poster: BackendUser | null;
  forum: { id: number; name: string; slug?: string | null } | null;
  created: string;
  posts_count?: number;
  last_post_on?: string | null;
  replies_count?: number;
  views_count?: number;
}
export interface BackendPost {
  id: number;
  content: string;
  poster: BackendUser | null;
  created: string;
  updated?: string;
  content_format?: string;
}
export interface BackendImage {
  id: number;
  image_url?: string | null;
  thumbnail_url?: string | null;
  large_thumbnail_url?: string | null;
  upload_order?: number;
  alt_text?: string;
  original_filename?: string;
  file_size?: number;
  created_at?: string;
}

type ForumAuthor = Thread['author'];

export function mapUser(u: BackendUser | null): ForumAuthor | null {
  if (!u) return null;
  const fullName = [u.first_name, u.last_name].filter(Boolean).join(' ').trim();
  // tsconfig strict:false — return the fields the forum UI reads.
  return {
    id: String(u.id),
    username: u.username,
    display_name: fullName || u.username,
  } as ForumAuthor;
}

export function mapForumToCategory(f: BackendForum): Category {
  return {
    id: String(f.id),
    name: f.name,
    slug: f.slug || slugifyTitle(f.name),
    description: f.description,
    thread_count: f.topics_count ?? 0,
    post_count: f.posts_count ?? 0,
    created_at: f.last_activity || '',
  };
}

export function mapTopicToThread(t: BackendTopic): Thread {
  const category: Category = t.forum
    ? {
        id: String(t.forum.id),
        name: t.forum.name,
        slug: t.forum.slug || slugifyTitle(t.forum.name),
        created_at: '',
      }
    : { id: '', name: '', slug: '', created_at: '' };
  return {
    id: String(t.id),
    title: t.subject,
    slug: slugifyTitle(t.subject),
    category,
    author: mapUser(t.poster) as Thread['author'],
    created_at: t.created,
    last_activity_at: t.last_post_on || t.created,
    post_count: t.posts_count ?? 0,
    view_count: t.views_count ?? 0,
    is_pinned: false,
    is_locked: false,
    is_active: true,
  };
}

export function mapPostToPost(p: BackendPost, threadId: string): Post {
  return {
    id: String(p.id),
    thread: threadId,
    author: mapUser(p.poster) as Post['author'],
    content_raw: p.content,
    content_html: p.content,
    content_format: p.content_format || 'html',
    created_at: p.created,
    updated_at: p.updated,
    is_active: true,
    reaction_counts: {},
  };
}

export function mapImageToAttachment(img: BackendImage): Attachment {
  return {
    id: String(img.id),
    image: img.image_url || undefined,
    image_url: img.image_url || undefined,
    thumbnail_url: img.thumbnail_url || undefined,
    image_thumbnail: img.thumbnail_url || undefined,
    thumbnail: img.thumbnail_url || undefined,
    large_url: img.large_thumbnail_url || undefined,
    display_order: img.upload_order,
    alt_text: img.alt_text,
    original_filename: img.original_filename,
    file_size: img.file_size,
    created_at: img.created_at,
    uploaded_at: img.created_at,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/services/forumMappers.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/services/forumMappers.ts web/src/services/forumMappers.test.ts
git commit -m "feat(forum): add backend->frontend mapper functions"
```

---

## Task 4: Rewrite `forumService.ts` as a translation layer

Keep the same exported function names the pages already import where possible, but point them at the real endpoints and map responses. Change reaction functions to the toggle model and fix image endpoints/field name.

**Files:**

- Rewrite: `web/src/services/forumService.ts`

- [ ] **Step 1: Replace the entire file contents**

```typescript
// web/src/services/forumService.ts
/**
 * Forum API Service — translation layer.
 *
 * The backend serves an id-based, machina-shaped API; this module calls those
 * real endpoints and maps responses to the clean React domain types.
 * Lookups use integer ids (parsed from hybrid id+slug route params).
 *
 * Cookie-based JWT auth with CSRF on mutating requests.
 */
import { getCsrfToken } from '../utils/csrf';
import {
  mapForumToCategory,
  mapTopicToThread,
  mapPostToPost,
  mapImageToAttachment,
  type BackendForum,
  type BackendTopic,
  type BackendPost,
  type BackendImage,
} from './forumMappers';
import type {
  Category,
  Thread,
  Post,
  Attachment,
  PaginatedResponse,
  UpdatePostInput,
  SearchForumOptions,
  SearchForumResponse,
  ReactionToggleResult,
} from '../types/forum';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

interface DrfPage<T> {
  results?: T[];
  count?: number;
  next?: string | null;
  previous?: string | null;
}

async function authenticatedFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------

export async function fetchCategories(): Promise<Category[]> {
  const data = await authenticatedFetch<DrfPage<BackendForum>>(`${FORUM_BASE}/categories/`);
  return (data.results || []).map(mapForumToCategory);
}

/** No backend tree endpoint — returns the flat list (no children). */
export async function fetchCategoryTree(): Promise<Category[]> {
  return fetchCategories();
}

/** Resolve a single category by its integer id (from the hybrid route param). */
export async function fetchCategory(forumId: number): Promise<Category> {
  const categories = await fetchCategories();
  const match = categories.find((c) => c.id === String(forumId));
  if (!match) throw new Error('Category not found');
  return match;
}

// ---------------------------------------------------------------------------
// Threads (topics)
// ---------------------------------------------------------------------------

export async function fetchThreads(
  options: { page?: number; category?: number } = {}
): Promise<PaginatedResponse<Thread>> {
  const { page = 1, category } = options;
  const params = new URLSearchParams({ page: String(page) });
  const path =
    category != null
      ? `${FORUM_BASE}/categories/${category}/topics/?${params}`
      : `${FORUM_BASE}/topics/?${params}`;
  const data = await authenticatedFetch<DrfPage<BackendTopic>>(path);
  return {
    items: (data.results || []).map(mapTopicToThread),
    meta: { count: data.count || 0, next: data.next, previous: data.previous },
  };
}

export async function fetchThread(topicId: number): Promise<Thread> {
  const data = await authenticatedFetch<{ topic: BackendTopic }>(
    `${FORUM_BASE}/topics/${topicId}/`
  );
  return mapTopicToThread(data.topic);
}

export async function createThread(data: {
  title: string;
  category: number;
  first_post_content: string;
  first_post_format?: string;
}): Promise<Thread> {
  const { title, category, first_post_content, first_post_format = 'plain' } = data;
  const res = await authenticatedFetch<{ topic: BackendTopic }>(
    `${FORUM_BASE}/categories/${category}/topics/create/`,
    {
      method: 'POST',
      body: JSON.stringify({ subject: title, content: first_post_content, content_format: first_post_format }),
    }
  );
  return mapTopicToThread(res.topic);
}

// ---------------------------------------------------------------------------
// Posts
// ---------------------------------------------------------------------------

export async function fetchPosts(
  options: { thread: number; page?: number }
): Promise<PaginatedResponse<Post>> {
  const { thread, page = 1 } = options;
  if (thread == null) throw new Error('Thread id is required');
  const params = new URLSearchParams({ topic: String(thread), page: String(page) });
  const data = await authenticatedFetch<DrfPage<BackendPost>>(`${FORUM_BASE}/posts/?${params}`);
  return {
    items: (data.results || []).map((p) => mapPostToPost(p, String(thread))),
    meta: { count: data.count || 0, next: data.next, previous: data.previous },
  };
}

export async function createPost(data: {
  thread: number;
  content_raw: string;
  content_format?: string;
}): Promise<Post> {
  const { thread, content_raw, content_format = 'plain' } = data;
  const res = await authenticatedFetch<{ data: BackendPost }>(`${FORUM_BASE}/posts/create/`, {
    method: 'POST',
    body: JSON.stringify({ topic: thread, content: content_raw, content_format }),
  });
  return mapPostToPost(res.data, String(thread));
}

export async function updatePost(postId: string, data: UpdatePostInput): Promise<Post> {
  const { content_raw, content_format } = data;
  const res = await authenticatedFetch<{ data: BackendPost }>(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ content: content_raw, content_format }),
  });
  return mapPostToPost(res.data, '');
}

export async function deletePost(postId: string): Promise<void> {
  await authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/delete/`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Reactions (toggle model)
// ---------------------------------------------------------------------------

interface BackendReactionResponse {
  reactions?: Record<string, { count: number; users: unknown[] }>;
  user_reactions?: string[];
  action?: 'added' | 'removed';
  reaction_type?: string;
}

function toCounts(r: BackendReactionResponse): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const [type, info] of Object.entries(r.reactions || {})) counts[type] = info.count;
  return counts;
}

/** Toggle a reaction on a post; returns updated counts + the user's active reactions. */
export async function toggleReaction(
  postId: string,
  reactionType: string
): Promise<ReactionToggleResult> {
  const res = await authenticatedFetch<BackendReactionResponse>(
    `${FORUM_BASE}/posts/${postId}/reactions/`,
    { method: 'POST', body: JSON.stringify({ reaction_type: reactionType }) }
  );
  return {
    action: res.action || 'added',
    reaction_type: res.reaction_type || reactionType,
    reaction_counts: toCounts(res),
    user_reactions: res.user_reactions || [],
  };
}

/** Read reaction counts + the current user's active reactions for a post. */
export async function fetchReactions(
  postId: string
): Promise<{ reaction_counts: Record<string, number>; user_reactions: string[] }> {
  const res = await authenticatedFetch<BackendReactionResponse>(
    `${FORUM_BASE}/posts/${postId}/reactions/`
  );
  return { reaction_counts: toCounts(res), user_reactions: res.user_reactions || [] };
}

// ---------------------------------------------------------------------------
// Images
// ---------------------------------------------------------------------------

export async function fetchPostImages(postId: string): Promise<Attachment[]> {
  const data = await authenticatedFetch<{ images: BackendImage[] }>(
    `${FORUM_BASE}/posts/${postId}/images/`
  );
  return (data.images || []).map(mapImageToAttachment);
}

export async function uploadPostImage(postId: string, imageFile: File): Promise<Attachment> {
  const csrfToken = await getCsrfToken();
  const formData = new FormData();
  formData.append('images', imageFile); // backend expects the plural field name
  const response = await fetch(`${FORUM_BASE}/posts/${postId}/images/upload/`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json', ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  const data = (await response.json()) as { images: BackendImage[] };
  return mapImageToAttachment(data.images[0]);
}

export async function deletePostImage(postId: string, attachmentId: string): Promise<void> {
  await authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/images/${attachmentId}/delete/`, {
    method: 'DELETE',
  });
}

/** No bulk reorder endpoint — PATCH upload_order on each image in sequence. */
export async function reorderPostImages(
  postId: string,
  attachmentIds: string[]
): Promise<Attachment[]> {
  for (let i = 0; i < attachmentIds.length; i++) {
    await authenticatedFetch<unknown>(`${FORUM_BASE}/posts/${postId}/images/${attachmentIds[i]}/`, {
      method: 'PATCH',
      body: JSON.stringify({ upload_order: i }),
    });
  }
  return fetchPostImages(postId);
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export async function searchForum(options: SearchForumOptions): Promise<SearchForumResponse> {
  const { q } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  const data = await authenticatedFetch<{ topics: BackendTopic[]; posts: BackendPost[] }>(
    `${FORUM_BASE}/search/?${params}`
  );
  const threads = (data.topics || []).map(mapTopicToThread);
  const posts = (data.posts || []).map((p) => mapPostToPost(p, ''));
  return {
    query: q.trim(),
    threads,
    posts,
    total_threads: threads.length,
    total_posts: posts.length,
    has_next_threads: false,
    has_next_posts: false,
    page: 1,
    page_size: threads.length + posts.length,
  } as SearchForumResponse;
}
```

> Note on `updatePost`: the backend update response does not echo the topic id, so the mapped post's `thread` is `''`. **Verified harmless** — a grep of `components/forum` and `pages/forum` finds **no** reads of `post.thread`; `PostCard` reads `author`/`content_raw`/`reaction_counts`/`created_at` only, and the pages already hold the thread context in their own state.

- [ ] **Step 2: Verify type-check passes**

Run: `cd web && npm run type-check`
Expected: PASS. If `SearchForumResponse` is missing fields used above, widen it in `types/forum.ts` (it already includes `threads`, `posts`, `total_threads`, `total_posts`, `has_next_threads`, `has_next_posts`, `page`, `page_size` per existing tests).

- [ ] **Step 3: Commit**

```bash
git add web/src/services/forumService.ts
git commit -m "feat(forum): rewrite forumService as translation layer over real API"
```

---

## Task 5: Rewrite `forumService.test.ts`

Replace the old (imagined-contract) tests with ones asserting the real endpoints and the mapped output. Reuse the existing `global.fetch` + CSRF mock harness.

**Files:**

- Rewrite: `web/src/services/forumService.test.ts`

- [ ] **Step 1: Replace the entire file contents**

```typescript
// web/src/services/forumService.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchCategories,
  fetchCategory,
  fetchThreads,
  fetchThread,
  createThread,
  fetchPosts,
  createPost,
  updatePost,
  deletePost,
  toggleReaction,
  fetchReactions,
  uploadPostImage,
  deletePostImage,
  searchForum,
} from './forumService';
import { clearCsrfToken } from '../utils/csrf';

const backendUser = { id: 1, username: 'jdoe', first_name: 'Jane', last_name: 'Doe' };
const backendForum = {
  id: 3,
  name: 'Plant Care',
  description: 'Tips',
  topics_count: 2,
  posts_count: 9,
  last_activity: '2026-01-02T00:00:00Z',
};
const backendTopic = {
  id: 12,
  subject: 'Succulent help',
  poster: backendUser,
  forum: { id: 3, name: 'Plant Care', slug: 'plant-care' },
  created: '2026-01-01T00:00:00Z',
  posts_count: 5,
  last_post_on: '2026-01-02T00:00:00Z',
  replies_count: 4,
  views_count: 99,
};
const backendPost = {
  id: 50,
  content: '<p>hello</p>',
  poster: backendUser,
  created: '2026-01-01T00:00:00Z',
  updated: '2026-01-01T00:00:00Z',
  content_format: 'html',
};

let fetchMock: ReturnType<typeof vi.fn>;
let cookie: string;

beforeEach(() => {
  fetchMock = vi.fn();
  global.fetch = fetchMock as unknown as typeof fetch;
  cookie = 'csrftoken=test-csrf-token';
  Object.defineProperty(document, 'cookie', {
    get: () => cookie,
    set: (v: string) => {
      cookie = v;
    },
    configurable: true,
  });
  clearCsrfToken();
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  const meta = document.createElement('meta');
  meta.setAttribute('name', 'csrf-token');
  meta.setAttribute('content', 'test-csrf-token');
  document.head.appendChild(meta);
  vi.clearAllMocks();
});

afterEach(() => {
  clearCsrfToken();
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  vi.restoreAllMocks();
});

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

describe('forumService (translation layer)', () => {
  it('fetchCategories unwraps DRF results and maps fields', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendForum], count: 1 }));
    const result = await fetchCategories();
    expect(result[0]).toMatchObject({ id: '3', name: 'Plant Care', thread_count: 2, post_count: 9 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/forum/categories/'),
      expect.objectContaining({ credentials: 'include' })
    );
  });

  it('fetchCategory resolves by integer id from the list', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendForum], count: 1 }));
    const c = await fetchCategory(3);
    expect(c.id).toBe('3');
  });

  it('fetchThreads hits the category topics endpoint and maps topics->threads', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendTopic], count: 1, next: null, previous: null }));
    const result = await fetchThreads({ category: 3, page: 1 });
    expect(result.items[0]).toMatchObject({ id: '12', title: 'Succulent help', post_count: 5 });
    expect(result.meta.count).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/categories/3/topics/?page=1'),
      expect.any(Object)
    );
  });

  it('fetchThreads without category hits /topics/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendTopic], count: 1 }));
    await fetchThreads({ page: 2 });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/topics/?page=2'), expect.any(Object));
  });

  it('fetchThread unwraps {topic} from the detail endpoint', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ topic: backendTopic, posts: { results: [], count: 0 } }));
    const t = await fetchThread(12);
    expect(t).toMatchObject({ id: '12', title: 'Succulent help' });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/topics/12/'), expect.any(Object));
  });

  it('createThread posts subject/content to the create endpoint', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ message: 'ok', topic: backendTopic, first_post_id: 50 }));
    const t = await createThread({
      title: 'Succulent help',
      category: 3,
      first_post_content: 'hello',
      first_post_format: 'html',
    });
    expect(t.id).toBe('12');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/categories/3/topics/create/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({ subject: 'Succulent help', content: 'hello' });
  });

  it('fetchPosts queries by topic id and maps posts', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendPost], count: 1 }));
    const result = await fetchPosts({ thread: 12, page: 1 });
    expect(result.items[0]).toMatchObject({ id: '50', thread: '12', content_raw: '<p>hello</p>' });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('topic=12'), expect.any(Object));
  });

  it('createPost posts to /posts/create/ and unwraps {data}', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ message: 'ok', data: backendPost }));
    const p = await createPost({ thread: 12, content_raw: 'hi', content_format: 'html' });
    expect(p.id).toBe('50');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/create/');
    expect(JSON.parse(opts.body)).toMatchObject({ topic: 12, content: 'hi' });
  });

  it('updatePost PATCHes content and unwraps {data}', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ message: 'ok', data: { ...backendPost, content: '<p>edited</p>' } }));
    const p = await updatePost('50', { content_raw: '<p>edited</p>', content_format: 'html' });
    expect(p.content_raw).toBe('<p>edited</p>');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/');
    expect(opts.method).toBe('PATCH');
  });

  it('deletePost hits the /delete/ suffix endpoint', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined });
    await deletePost('50');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/posts/50/delete/'),
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('toggleReaction posts reaction_type and normalizes counts', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ success: true, action: 'added', reaction_type: 'like', reactions: { like: { count: 3, users: [] } }, user_reactions: ['like'] })
    );
    const r = await toggleReaction('50', 'like');
    expect(r).toMatchObject({ action: 'added', reaction_counts: { like: 3 }, user_reactions: ['like'] });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/reactions/');
    expect(JSON.parse(opts.body)).toEqual({ reaction_type: 'like' });
  });

  it('fetchReactions normalizes counts and user_reactions', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ post_id: 50, reactions: { like: { count: 3, users: [] } }, user_reactions: [], total_reactions: 3 })
    );
    const r = await fetchReactions('50');
    expect(r.reaction_counts).toEqual({ like: 3 });
  });

  it('uploadPostImage sends FormData with the plural field name to images/upload/', async () => {
    const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' });
    fetchMock.mockResolvedValueOnce(
      okJson({ message: 'ok', images: [{ id: 7, image_url: 'http://x/a.jpg', thumbnail_url: 'http://x/t.jpg', upload_order: 0 }], post_id: 50 })
    );
    const a = await uploadPostImage('50', file);
    expect(a).toMatchObject({ id: '7', image_url: 'http://x/a.jpg', display_order: 0 });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/images/upload/');
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body as FormData).has('images')).toBe(true);
  });

  it('deletePostImage hits the images/{id}/delete/ endpoint', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined });
    await deletePostImage('50', '7');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/posts/50/images/7/delete/'),
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('searchForum maps topics->threads and posts->posts', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ query: 'succ', topics: [backendTopic], posts: [backendPost] }));
    const r = await searchForum({ q: 'succ' });
    expect(r.threads[0].id).toBe('12');
    expect(r.posts[0].id).toBe('50');
    expect(r.total_threads).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/search/?q=succ'), expect.any(Object));
  });

  it('searchForum rejects empty queries', async () => {
    await expect(searchForum({ q: '   ' })).rejects.toThrow('Search query is required');
  });

  it('propagates backend errors with detail', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 429, json: async () => ({ detail: 'Rate limit exceeded' }) });
    await expect(createPost({ thread: 12, content_raw: 'x' })).rejects.toThrow('Rate limit exceeded');
  });
});
```

- [ ] **Step 2: Run the service + mapper + url tests**

Run: `cd web && npx vitest run src/services/forumService.test.ts src/services/forumMappers.test.ts src/utils/forumUrls.test.ts`
Expected: PASS (all). Fix mapping mismatches until green.

- [ ] **Step 3: Commit**

```bash
git add web/src/services/forumService.test.ts
git commit -m "test(forum): rewrite forumService tests for the real API contract"
```

---

## Task 6: Hybrid links in card components

**Files:**

- Modify: `web/src/components/forum/CategoryCard.tsx`
- Modify: `web/src/components/forum/ThreadCard.tsx`

- [ ] **Step 1: Update `CategoryCard.tsx`**

Add the import and replace both hard-coded `/forum/${...slug}` links.

```typescript
// near the other imports
import { categoryPath } from '../../utils/forumUrls';
```

Replace the top-level category link (was `to={`/forum/${category.slug}`}`):

```tsx
<Link to={categoryPath(category)}>
```

Replace the child category link (was `to={`/forum/${child.slug}`}`):

```tsx
<Link to={categoryPath(child)}>
```

- [ ] **Step 2: Update `ThreadCard.tsx`**

```typescript
// near the other imports
import { threadPath } from '../../utils/forumUrls';
```

Replace the URL construction (was `const threadUrl =`/forum/${thread.category.slug}/${thread.slug}`;`):

```typescript
const threadUrl = threadPath(thread.category, thread);
```

- [ ] **Step 3: Run component tests**

Run: `cd web && npx vitest run src/components/forum/CategoryCard.test.tsx src/components/forum/ThreadCard.test.tsx`
Expected: these tests reference link hrefs; update any asserted href to the new `/{id}-{slug}` form, then PASS.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/forum/CategoryCard.tsx web/src/components/forum/ThreadCard.tsx web/src/components/forum/CategoryCard.test.tsx web/src/components/forum/ThreadCard.test.tsx
git commit -m "feat(forum): build hybrid id+slug links in forum cards"
```

---

## Task 7: Parse ids in route-driven pages

`ThreadListPage` and `ThreadDetailPage` receive `id-slug` params; parse the leading id and pass integers to the service.

> **No `App.tsx` route change is needed.** React Router matches dynamic segments by position, not by name — the existing `/forum/:categorySlug` and `/forum/:categorySlug/:threadSlug` already capture `"3-plant-care"` / `"12-succulent-help"`, and `parseLeadingId` extracts the id. The param name `categorySlug` becomes a slight misnomer; renaming to `:categoryIdSlug`/`:threadIdSlug` is **optional** cosmetic cleanup (would also require updating the `useParams` destructuring keys in both pages) and is not required for correctness.

**Files:**

- Modify: `web/src/pages/forum/ThreadListPage.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`

- [ ] **Step 1: Update `ThreadListPage.tsx`**

Add the import:

```typescript
import { parseLeadingId } from '../../utils/forumUrls';
```

After `const { categorySlug } = useParams<{ categorySlug: string }>();`, derive the id and use it for service calls (was `fetchCategory(categorySlug)` and `fetchThreads({ category: categorySlug, ... })`):

```typescript
const forumId = parseLeadingId(categorySlug);
// ...inside the loader, guard and call with the integer id:
if (forumId == null) {
  setError('Invalid category URL');
  return;
}
const [category, threadsData] = await Promise.all([
  fetchCategory(forumId),
  fetchThreads({ category: forumId, page }),
]);
```

Breadcrumb/new-thread links that use `categorySlug` (the raw `id-slug` param) stay as-is.

- [ ] **Step 2: Update `ThreadDetailPage.tsx`**

Add the import:

```typescript
import { parseLeadingId } from '../../utils/forumUrls';
```

After `const { categorySlug, threadSlug } = useParams<...>();`, derive the topic id and use it (was `fetchThread(threadSlug)` / `fetchPosts({ thread: threadSlug, ... })`):

```typescript
const topicId = parseLeadingId(threadSlug);
// ...inside the loader, guard then:
if (topicId == null) return;
const [thread, postsData] = await Promise.all([
  fetchThread(topicId),
  fetchPosts({ thread: topicId, page: 1, limit: postsPerPage }),
]);
```

`createPost({ thread: thread.id, ... })` currently passes the string `thread.id`; change it to the numeric topic id:

```typescript
await createPost({ thread: topicId, content_raw: replyContent, content_format: 'html' });
```

(Also change `content_format: 'rich'` → `'html'` — the backend expects `plain`/`draftail`/`html`; TipTap emits HTML.)

Update the `useEffect` dependency array that listed `threadSlug` to also work with `topicId` (keep `threadSlug` so navigation re-fetches).

- [ ] **Step 3: Run page tests + type-check**

Run: `cd web && npx vitest run src/pages/forum/ThreadListPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx && npm run type-check`
Expected: update test mocks to the new service signatures (integer ids, `{topic}` / `{data}` envelopes), then PASS with zero type errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/forum/ThreadListPage.tsx web/src/pages/forum/ThreadDetailPage.tsx web/src/pages/forum/ThreadListPage.test.tsx web/src/pages/forum/ThreadDetailPage.test.tsx
git commit -m "feat(forum): parse integer ids from hybrid route params"
```

---

## Task 8: Wire reactions (PostCard + ThreadDetailPage)

`PostCard` reaction buttons are display-only. Add an `onReact` callback prop; `ThreadDetailPage` supplies a handler that calls `toggleReaction` and updates the post's `reaction_counts`.

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`

- [ ] **Step 1: Add `onReact` to `PostCard`**

In the props interface add:

```typescript
onReact?: (postId: string, reactionType: string) => void;
```

For each reaction `<button>` (currently no handler), add the click + a stable type. Example for the "like" button:

```tsx
<button type="button" onClick={() => onReact?.(post.id, 'like')} aria-label="React like">
  👍 {post.reaction_counts?.like ?? 0}
</button>
```

Repeat for `love`, `helpful`, `thanks` (the four backend reaction types).

- [ ] **Step 2: Handle reactions in `ThreadDetailPage`**

Import the toggle:

```typescript
import { toggleReaction } from '../../services/forumService';
```

Add a handler that optimistically updates the post list (posts are held in state as `Post[]`):

```typescript
const handleReact = async (postId: string, reactionType: string) => {
  if (!isAuthenticated) {
    navigate('/login', { state: { from: window.location.pathname } });
    return;
  }
  try {
    const result = await toggleReaction(postId, reactionType);
    setPosts((prev) =>
      prev.map((p) => (p.id === postId ? { ...p, reaction_counts: result.reaction_counts } : p))
    );
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Could not react');
  }
};
```

Pass it to each `<PostCard ... onReact={handleReact} />`.

- [ ] **Step 3: Run PostCard + page tests**

Run: `cd web && npx vitest run src/components/forum/PostCard.test.tsx src/pages/forum/ThreadDetailPage.test.tsx`
Expected: add a test asserting `onReact` fires with `(post.id, 'like')` on click; PASS.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/forum/PostCard.tsx web/src/components/forum/PostCard.test.tsx web/src/pages/forum/ThreadDetailPage.tsx web/src/pages/forum/ThreadDetailPage.test.tsx
git commit -m "feat(forum): wire post reactions to the toggle endpoint"
```

---

## Task 9: Full suite + type-check + lint

- [ ] **Step 1: Run the whole web test suite**

Run: `cd web && npm run test`
Expected: PASS (fix any remaining stragglers from renamed service functions — e.g. files importing `addReaction`/`removeReaction`/`fetchCategoryTree` with a slug).

- [ ] **Step 2: Type-check and lint**

Run: `cd web && npm run type-check && npm run lint`
Expected: zero type errors; lint clean.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A web/src
git commit -m "fix(forum): align remaining callers with the new service API"
```

---

## Task 10: Golden-path E2E (Playwright)

Prove the flow end-to-end against the running stack: backend (`:8000`, Redis up, `ENABLE_FORUM=True`) and web dev server (`:5174`). Requires at least one forum/category seeded.

> **Coverage split (intentional).** The *automated* e2e below covers the **unauthenticated browse path** (categories → category → topic → posts render) — the part that's stable to assert without a login fixture. The **authenticated** golden-path steps (reply → react → upload image) are covered by **manual verification** in Step 3. Extending the automated e2e with a login flow is a worthwhile follow-up once the login-page selectors are confirmed; it's deliberately out of this task to avoid guessing selectors.

**Files:**

- Create: `web/e2e/forum-golden-path.spec.ts`

- [ ] **Step 1: Write the E2E spec**

```typescript
// web/e2e/forum-golden-path.spec.ts
import { test, expect } from '@playwright/test';

// Assumes a seeded forum with >=1 category. Unauthenticated browse path only;
// reply/react/upload are covered by manual verification (see Task 10, Step 3).

test('forum public golden path: browse → open category → open topic', async ({ page }) => {
  await page.goto('/forum');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  // Open the first category, then the first thread.
  await page.locator('a[href^="/forum/"]').first().click();
  await expect(page).toHaveURL(/\/forum\/\d+-/); // id-anchored category URL

  const firstThread = page.locator('a[href*="/forum/"]').filter({ hasText: /.+/ }).first();
  await firstThread.click();
  await expect(page).toHaveURL(/\/forum\/\d+-.+\/\d+-/); // id-anchored thread URL

  // Posts render.
  await expect(page.locator('article, [data-testid="post-card"]').first()).toBeVisible();
});
```

- [ ] **Step 2: Run the E2E**

Run: `cd web && npm run test:e2e -- forum-golden-path`
Expected: PASS. If selectors don't match the rendered markup, adjust them to the actual DOM (this is the one place to inspect the running UI). Debug with `npm run test:e2e:ui`.

- [ ] **Step 3: Manual verification (golden path + reply + react + image)**

Start the stack and manually verify in a browser at `http://localhost:5174/forum`:
categories list → open category → open topic → post a reply → react to a post → upload an image. Confirm each works against the live backend. (Reply/react/upload require login.)

- [ ] **Step 4: Commit**

```bash
git add web/e2e/forum-golden-path.spec.ts
git commit -m "test(forum): add golden-path e2e for the working forum"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** Phase 1 spec bullets map to tasks — translation-layer service (T3–T5), hybrid id+slug URLs (T1, T6, T7), reactions toggle (T2, T8), image endpoint/field fix (T4), finish ThreadDetailPage flows (T7, T8), golden-path e2e + manual verify (T10). Phase 2 (security) and Phase 3 (responsive) are out of scope for this plan.
- **Type consistency:** service function names referenced in pages (`fetchCategory`, `fetchThreads`, `fetchThread`, `fetchPosts`, `createPost`, `deletePost`, `toggleReaction`, `uploadPostImage`, `deletePostImage`, `reorderPostImages`) match their definitions in Task 4. `ReactionToggleResult` (Task 2) is produced by `toggleReaction` (Task 4) and consumed in Task 8.
- **Known limitations** are documented up front (flat tree, unsupported thread-list search/ordering/limit, sequential reorder, ignored search filters) — to be carried into the PR description, not silently dropped.

## Definition of Done (Phase 1)

- `npm run test`, `npm run type-check`, `npm run lint` all green in `web/`.
- The golden path works end-to-end against the live backend (e2e + manual).
- No references remain to the old imagined endpoints (`/threads/`, `/reactions/{id}/`, `/upload_image/`, `fetchCategoryTree` by slug).
