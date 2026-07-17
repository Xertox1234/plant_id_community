# Forum Wave 1 — Honesty & Polish Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web forum's existing features findable and truthful — honest search results, working search-result links, per-post permalinks, notification deep links, visible reactions for logged-out readers, mention styling, and draft autosave — with no new product features.

**Architecture:** Two small backend serializer/view extensions (search payload metadata + notification `post_id`), then web-only changes: the service/mapper layer consumes the new fields, SearchPage drops its decorative filters, PostCard/ThreadDetailPage/NotificationBell gain permalink & highlight affordances, and composers persist drafts to sessionStorage. No new models, no migrations, no new endpoints.

**Tech Stack:** Django/DRF + Wagtail search (package `wagtail_forum`), React 19 + TypeScript + Tailwind 4 + Vitest, TipTap 3 editor.

**Spec:** `docs/superpowers/specs/2026-07-17-forum-app-loop-roadmap-design.md` (Wave 1 section).

## Global Constraints

- Branch: `feat/forum-wave1-honesty-polish` cut fresh from `origin/main` (create via superpowers:using-git-worktrees at execution time). Never push to `main`.
- React Router imports come from `react-router-dom`, never `react-router` (silent runtime failure otherwise).
- User-generated HTML is always DOMPurify-sanitized before `dangerouslySetInnerHTML`; the mention transform in Task 5 runs strictly AFTER sanitization.
- Timer IDs in React use `useRef`, never `useState` (project gotcha #5).
- The edit-time formatter strips imports that are unused at format time — add an import in the SAME edit as its first usage.
- Backend: no magic numbers (module constants), bracketed log prefixes (`[SEARCH]` etc.), type hints on service methods.
- Backend venv: run commands as `cd backend && venv/bin/python -m pytest …`. Package API tests carry `pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")` — endpoints mount at root (e.g. `/search/`).
- Web gates: `npm run type-check`, `npm run lint`, `npm run test` (Vitest `--run`) must pass at every commit.
- The kimi-review commit hook is active; a `[CRITICAL]` finding blocks the commit — fix, don't bypass.

---

### Task 1: Backend — search results carry real topic metadata + board filter

The search API returns only `{id, slug, title}` per topic, forcing the frontend to fabricate "0 replies • 0 views • recently". Add real counts, activity time, and board identifiers (needed to build working links — today's search-result thread links are broken: `category.id` is empty so `threadPath` produces `/forum/-slug/...` which `parseLeadingId` rejects). Add an optional `board` (slug) query filter.

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py:832-873` (`SearchView`)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py` (append)

**Interfaces:**

- Produces (consumed by Task 3): topic entries `{id, slug, title, reply_count, view_count, last_post_at, board_id, board_slug}`; post entries `{id, topic_id, topic_title, topic_slug, board_id, board_slug, excerpt}`; query params `q` + optional `board` (board slug).

- [ ] **Step 1: Write the failing tests**

Append to `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py` (reuse the file's existing board/topic builder helpers if present — otherwise these are self-contained; match the file's existing imports):

```python
@pytest.mark.django_db
def test_search_topics_include_metadata_and_board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-meta"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general-meta"))
    topic = Topic.objects.create(
        board=board, title="Monstera propagation tips", slug="monstera-meta"
    )
    topic.reply_count = 3
    topic.view_count = 7
    topic.last_post_at = timezone.now()
    topic.save()

    resp = APIClient().get("/search/", {"q": "Monstera"})

    assert resp.status_code == 200
    entry = next(t for t in resp.data["topics"] if t["id"] == topic.id)
    assert entry["reply_count"] == 3
    assert entry["view_count"] == 7
    assert entry["last_post_at"] is not None
    assert entry["board_id"] == board.id
    assert entry["board_slug"] == "general-meta"


@pytest.mark.django_db
def test_search_board_filter_narrows_topics_and_posts():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-filter"))
    board_a = index.add_child(instance=ForumBoard(title="A", slug="board-a"))
    board_b = index.add_child(instance=ForumBoard(title="B", slug="board-b"))
    topic_a = Topic.objects.create(board=board_a, title="Fern care", slug="fern-a")
    topic_b = Topic.objects.create(board=board_b, title="Fern care", slug="fern-b")
    author = User.objects.create_user(username="fern_author")
    Post.objects.create(
        topic=topic_a,
        author=author,
        body=[{"type": "paragraph", "value": "<p>Fern watering schedule</p>"}],
    )
    Post.objects.create(
        topic=topic_b,
        author=author,
        body=[{"type": "paragraph", "value": "<p>Fern watering schedule</p>"}],
    )

    resp = APIClient().get("/search/", {"q": "Fern", "board": "board-a"})

    assert resp.status_code == 200
    assert {t["id"] for t in resp.data["topics"]} == {topic_a.id}
    assert all(p["board_slug"] == "board-a" for p in resp.data["posts"])
    post_entry = resp.data["posts"][0]
    assert post_entry["topic_slug"] == "fern-a"
    assert post_entry["board_id"] == board_a.id
```

If `timezone`, `User`, `Post`, or `APIClient` are not already imported at the top of the file, add them in the same edit (`from django.utils import timezone`, `from rest_framework.test import APIClient`, extend the existing `wagtail_forum.models` import, `User = get_user_model()` if absent).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py -q -k "metadata_and_board or board_filter"`
Expected: FAIL — `KeyError: 'reply_count'` (and `'board_slug'`).

- [ ] **Step 3: Implement in SearchView**

Replace the body of `SearchView.get` (`api/views.py:843-873`) with:

```python
    @extend_schema(
        responses={200: dict},
        description=(
            "Search live topic titles and post bodies. Query params: q "
            "(required), board (optional board slug filter)."
        ),
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        board_slug = request.query_params.get("board", "").strip()
        topics, posts = [], []
        if query:
            backend = get_search_backend()
            boards = _visible_boards()
            topic_qs = Topic.objects.filter(live=True, board__in=boards)
            post_qs = Post.objects.filter(
                live=True, topic__live=True, topic__board__in=boards
            )
            if board_slug:
                topic_qs = topic_qs.filter(board__slug=board_slug)
                post_qs = post_qs.filter(topic__board__slug=board_slug)
            topic_hits = backend.search(query, topic_qs.select_related("board"))
            for t in topic_hits[: self.MAX_RESULTS]:
                topics.append(
                    {
                        "id": t.id,
                        "slug": t.slug,
                        "title": t.title,
                        "reply_count": t.reply_count,
                        "view_count": t.view_count,
                        "last_post_at": (
                            t.last_post_at.isoformat() if t.last_post_at else None
                        ),
                        "board_id": t.board_id,
                        "board_slug": t.board.slug,
                    }
                )
            post_hits = backend.search(
                query, post_qs.select_related("topic", "topic__board")
            )
            for p in post_hits[: self.MAX_RESULTS]:
                posts.append(
                    {
                        "id": p.id,
                        "topic_id": p.topic_id,
                        "topic_title": p.topic.title,
                        "topic_slug": p.topic.slug,
                        "board_id": p.topic.board_id,
                        "board_slug": p.topic.board.slug,
                        "excerpt": (
                            plain_text_excerpt(p.body, self.MAX_EXCERPT_CHARS)
                            if p.body
                            else ""
                        ),
                    }
                )
        return Response({"topics": topics, "posts": posts})
```

Note: `select_related("board")` / `("topic", "topic__board")` prevents an N+1 on `board.slug` access — the prior code already had `select_related("topic")` for the same reason.

- [ ] **Step 4: Run tests to verify they pass, plus the whole search file**

Run: `cd backend && venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py -q`
Expected: PASS (all tests in the file, including pre-existing ones).

- [ ] **Step 5: Schema + system checks**

Run: `cd backend && venv/bin/python manage.py spectacular --file /dev/null && venv/bin/python manage.py check`
Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/views.py backend/packages/wagtail_forum/wagtail_forum/tests/api/test_search_sync.py
git commit -m "forum: search results carry topic metadata + board filter (wave 1.2)"
```

---

### Task 2: Backend — notification payload carries post_id

The `Notification` model has a `post` FK (`models/notifications.py:44`) but `NotificationSerializer` doesn't expose it, so the web bell can't deep-link to the post.

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:358-389` (`NotificationSerializer`)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py` (append)

**Interfaces:**

- Produces (consumed by Task 4): notification entries gain `"post_id": int | null`.

- [ ] **Step 1: Write the failing test**

Append to `test_notifications_api.py` (the file already has `_board`, `_topic_and_post`, `_notify` helpers and an authenticated-client pattern — mirror the existing list tests):

```python
@pytest.mark.django_db
def test_notification_list_includes_post_id():
    recipient = User.objects.create_user(username="postid_recipient")
    actor = User.objects.create_user(username="postid_actor")
    board = _board(slug="postid-board")
    topic, post = _topic_and_post(board, recipient, actor, slug="postid-t")
    _notify(recipient, actor, topic, post)

    client = APIClient()
    client.force_authenticate(user=recipient)
    resp = client.get("/notifications/")

    assert resp.status_code == 200
    assert resp.data["results"][0]["post_id"] == post.pk
```

(If the file's existing tests authenticate differently — e.g. `client.force_login` — copy that exact pattern instead.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py -q -k post_id`
Expected: FAIL — `KeyError: 'post_id'`.

- [ ] **Step 3: Implement**

In `api/serializers.py`, extend `NotificationSerializer`:

```python
class NotificationSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()
    # Deep-link target for clients (wave 1.3): the post this notification is
    # about, or null for a post-less verb.
    post_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ["id", "verb", "actor", "topic", "post_id", "created_at", "read_at"]
```

(Only the `post_id` field declaration and the `fields` list change; `get_actor`/`get_topic` stay as they are.)

- [ ] **Step 4: Run the notifications test file**

Run: `cd backend && venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/api/serializers.py backend/packages/wagtail_forum/wagtail_forum/tests/api/test_notifications_api.py
git commit -m "forum: expose post_id on notifications (wave 1.3 deep links)"
```

---

### Task 3: Web — honest search (service, mappers, types, SearchPage)

Consume Task 1's fields end-to-end. Drop the decorative author/date filters and the dead pagination; keep query + category (now actually filtering via `board`). One task because removing the option/response fields from the types breaks SearchPage compilation unless it's updated in the same change.

**Files:**

- Modify: `web/src/services/forumMappers.ts` (`BackendSearchTopic`, `BackendSearchPost`, `mapSearchTopicToThread`, `mapSearchPostToPost`)
- Modify: `web/src/services/forumService.ts:306-329` (`searchForum`)
- Modify: `web/src/types/forum.ts` (`SearchForumOptions`, `SearchForumResponse`, `Post` search-only fields)
- Modify: `web/src/pages/forum/SearchPage.tsx`
- Test: `web/src/services/forumMappers.test.ts`, `web/src/services/forumService.test.ts` (extend both)

**Interfaces:**

- Consumes: Task 1's search payload.
- Produces: `SearchForumOptions = { q: string; category?: string }` (category = board slug); `SearchForumResponse = { query, threads, posts, total_threads, total_posts }`; search-result `Thread`s have populated `category` (`id`/`slug` from board) + `post_count`/`view_count`/`last_activity_at`; search-result `Post`s carry `topic_title`, `topic_slug`, `board_id`, `board_slug`.

- [ ] **Step 1: Write the failing mapper/service tests**

In `forumMappers.test.ts`, add (top-level, matching the file's fixture style):

```typescript
const backendSearchTopic = {
  id: 31,
  slug: 'tomato-blight',
  title: 'Blight-resistant tomatoes',
  reply_count: 3,
  view_count: 12,
  last_post_at: '2026-07-01T10:00:00Z',
  board_id: 54,
  board_slug: 'general-discussion',
};

it('mapSearchTopicToThread carries real metadata and board identity', () => {
  const thread = mapSearchTopicToThread(backendSearchTopic);
  expect(thread.post_count).toBe(3);
  expect(thread.view_count).toBe(12);
  expect(thread.last_activity_at).toBe('2026-07-01T10:00:00Z');
  expect(thread.category.id).toBe('54');
  expect(thread.category.slug).toBe('general-discussion');
});

it('mapSearchPostToPost carries topic and board identity for links', () => {
  const post = mapSearchPostToPost({
    id: 9,
    topic_id: 31,
    topic_title: 'Blight-resistant tomatoes',
    topic_slug: 'tomato-blight',
    board_id: 54,
    board_slug: 'general-discussion',
    excerpt: 'Mountain Magic is the real answer',
  });
  expect(post.topic_slug).toBe('tomato-blight');
  expect(post.board_id).toBe(54);
  expect(post.board_slug).toBe('general-discussion');
});
```

In `forumService.test.ts`, extend the existing `searchForum` block: assert the request URL contains `board=general-discussion` when `category` is passed, and that the response's `total_threads` equals the returned array length (mock fetch with one topic in the new backend shape).

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/services/forumMappers.test.ts src/services/forumService.test.ts`
Expected: FAIL — new fields undefined / type errors.

- [ ] **Step 3: Implement mappers + types + service**

`forumMappers.ts` — extend the backend shapes and rewrite the two search mappers:

```typescript
export interface BackendSearchTopic {
  id: number;
  slug: string;
  title: string;
  reply_count: number;
  view_count: number;
  last_post_at: string | null;
  board_id: number;
  board_slug: string;
}

export interface BackendSearchPost {
  id: number;
  topic_id: number;
  topic_title: string;
  topic_slug: string;
  board_id: number;
  board_slug: string;
  excerpt: string;
}

export function mapSearchTopicToThread(t: BackendSearchTopic): Thread {
  return {
    id: String(t.id),
    title: t.title,
    slug: t.slug,
    category: { id: String(t.board_id), name: '', slug: t.board_slug, created_at: '' },
    author: authorFromString(null),
    created_at: t.last_post_at || '',
    last_activity_at: t.last_post_at || '',
    post_count: t.reply_count,
    view_count: t.view_count,
    is_active: true,
  };
}

export function mapSearchPostToPost(p: BackendSearchPost): Post {
  return {
    id: String(p.id),
    thread: String(p.topic_id),
    author: authorFromString(null),
    content_raw: p.excerpt,
    content_format: 'plain',
    body: [],
    created_at: '',
    is_active: true,
    reaction_counts: {},
    can_edit: false,
    can_delete: false,
    can_report: false,
    topic_title: p.topic_title,
    topic_slug: p.topic_slug,
    board_id: p.board_id,
    board_slug: p.board_slug,
  };
}
```

`types/forum.ts` — trim the search types and add the search-only `Post` fields next to the existing `topic_title`:

```typescript
export interface SearchForumOptions {
  q: string;
  /** Board slug — sent to the backend as ?board= */
  category?: string;
}

export interface SearchForumResponse {
  query: string;
  threads: Thread[];
  posts: Post[];
  total_threads: number;
  total_posts: number;
}
```

and inside `Post` (immediately after `topic_title?: string;`):

```typescript
  /** Search-result-only link identity (mapSearchPostToPost). */
  topic_slug?: string;
  board_id?: number;
  board_slug?: string;
```

`forumService.ts` — rewrite `searchForum`:

```typescript
export async function searchForum(options: SearchForumOptions): Promise<SearchForumResponse> {
  const { q, category } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  if (category) params.set('board', category);
  const data = await authenticatedFetch<{
    topics: BackendSearchTopic[];
    posts: BackendSearchPost[];
  }>(`${FORUM_BASE}/search/?${params}`);
  const threads = (data.topics || []).map(mapSearchTopicToThread);
  const posts = (data.posts || []).map(mapSearchPostToPost);
  // Result sets are server-capped at 50 each; lengths are the real totals up to that cap.
  return { query: q.trim(), threads, posts, total_threads: threads.length, total_posts: posts.length };
}
```

- [ ] **Step 4: Update SearchPage**

In `SearchPage.tsx`:

1. Delete the `author`, `dateFrom`, `dateTo`, `page`, `pageSize` param reads (lines 79-83) and their handlers `handleAuthorFilter` (214-229), `handleDateFilter` (231-245), `handlePageChange` + the `useHandlePageChange` import, and the `Pagination` import + render block (lines 504-513).
2. Delete the Author / From / To filter inputs (lines 332-373); keep the Category select, changing the grid to `grid-cols-1 md:grid-cols-2` and updating `hasActiveFilters` to `!!category`.
3. Call `searchForum({ q: query, category })` only, with `[query, category]` as the effect deps.
4. Thread results: the `ThreadCard` link now works (category is real). Keep `hideAuthor`.
5. Post results: replace the broken `const topicLink = \`/forum/-topic/${post.thread}\`;` with:

```typescript
import { threadPath } from '../../utils/forumUrls';
// …
const topicLink =
  post.board_id != null && post.board_slug && post.topic_slug
    ? `${threadPath(
        { id: String(post.board_id), slug: post.board_slug, name: post.board_slug },
        { id: post.thread, slug: post.topic_slug, title: post.topic_title || '' }
      )}#post-${post.id}`
    : `/forum`;
```

(Import `threadPath` in the same edit that uses it — formatter strips early imports.)

- [ ] **Step 5: Add a SearchPage component test**

Create `web/src/pages/forum/SearchPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SearchPage from './SearchPage';

vi.mock('../../services/forumService', () => ({
  searchForum: vi.fn().mockResolvedValue({
    query: 'tomato',
    threads: [
      {
        id: '31',
        title: 'Blight-resistant tomatoes',
        slug: 'tomato-blight',
        category: { id: '54', name: '', slug: 'general-discussion', created_at: '' },
        author: { id: '', username: '[deleted]', display_name: '[deleted]' },
        created_at: '2026-07-01T10:00:00Z',
        last_activity_at: '2026-07-01T10:00:00Z',
        post_count: 3,
        view_count: 12,
        is_active: true,
      },
    ],
    posts: [],
    total_threads: 1,
    total_posts: 0,
  }),
  fetchCategories: vi.fn().mockResolvedValue([]),
}));

describe('SearchPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders real counts and no decorative filters', async () => {
    render(
      <MemoryRouter initialEntries={['/forum/search?q=tomato']}>
        <SearchPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/Blight-resistant tomatoes/)).toBeInTheDocument());
    expect(screen.getByTitle('3 replies')).toBeInTheDocument();
    expect(screen.getByTitle('12 views')).toBeInTheDocument();
    expect(screen.queryByLabelText('Author')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run the web gates**

Run: `cd web && npm run type-check && npx vitest run src/services src/pages/forum/SearchPage.test.tsx`
Expected: type-check clean; tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/services/forumMappers.ts web/src/services/forumService.ts web/src/types/forum.ts web/src/pages/forum/SearchPage.tsx web/src/services/forumMappers.test.ts web/src/services/forumService.test.ts web/src/pages/forum/SearchPage.test.tsx
git commit -m "web/forum: honest search results, working links, real category filter (wave 1.2)"
```

---

### Task 4: Web — per-post permalinks + notification deep links

Surface the existing `#post-N` DOM anchors: a copy-link button on every post, notification clicks that land on the post, and scroll-highlight on arrival.

**Files:**

- Modify: `web/src/utils/forumUrls.ts` (add `postAnchor`)
- Modify: `web/src/types/notifications.ts` (add `post_id`)
- Modify: `web/src/components/layout/NotificationBell.tsx:129-137`
- Modify: `web/src/components/forum/PostCard.tsx` (copy-link button)
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx` (hash scroll + highlight)
- Test: `web/src/utils/forumUrls.test.ts`, new `web/src/components/forum/PostCard.test.tsx`

**Interfaces:**

- Consumes: Task 2's `post_id` field.
- Produces: `postAnchor(postId: number | string): string` in `utils/forumUrls.ts` (returns `#post-<id>`); `PostCard` renders a "Copy link" button for every post.

- [ ] **Step 1: Write the failing tests**

Append to `forumUrls.test.ts`:

```typescript
it('postAnchor builds a #post-N fragment', () => {
  expect(postAnchor(42)).toBe('#post-42');
  expect(postAnchor('42')).toBe('#post-42');
});
```

Create `web/src/components/forum/PostCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PostCard from './PostCard';
import type { Post } from '@/types';

const basePost: Post = {
  id: '21',
  thread: '28',
  author: { id: '', username: 'bob_botanist', display_name: 'bob_botanist' },
  content_raw: '',
  body: [{ type: 'paragraph', value: '<p>Classic earwig damage</p>' }],
  created_at: '2026-07-17T10:00:00Z',
  is_first_post: false,
  is_active: true,
  reaction_counts: {},
  can_edit: false,
  can_delete: false,
  can_report: false,
};

it('copies a permalink to the clipboard', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  render(<PostCard post={basePost} />);
  fireEvent.click(screen.getByRole('button', { name: /copy link/i }));
  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('#post-21'))
  );
  expect(await screen.findByText(/copied/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/utils/forumUrls.test.ts src/components/forum/PostCard.test.tsx`
Expected: FAIL — `postAnchor` not exported; no copy-link button.

- [ ] **Step 3: Implement `postAnchor` + type + bell navigation**

`utils/forumUrls.ts` — append:

```typescript
/** Fragment identifier for a specific post inside a thread page. */
export function postAnchor(postId: number | string): string {
  return `#post-${postId}`;
}
```

`types/notifications.ts` — in `ForumNotification`, after `topic`:

```typescript
  /** The post this notification is about, for deep links; null for post-less verbs. */
  post_id: number | null;
```

`NotificationBell.tsx` — extend the import (`import { threadPath, postAnchor } from '../../utils/forumUrls';`) and change the navigate call (lines 131-136) to:

```typescript
      navigate(
        threadPath(
          { id: String(topic.board_id), slug: topic.board_slug, name: topic.board_slug },
          { id: String(topic.id), slug: topic.slug, title: topic.title }
        ) + (notification.post_id != null ? postAnchor(notification.post_id) : '')
      );
```

- [ ] **Step 4: Implement the PostCard copy-link button**

In `PostCard.tsx`, add state + handler after the report state (line 52):

```typescript
  const [copiedLink, setCopiedLink] = useState(false);

  const handleCopyLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}#post-${post.id}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      window.prompt('Copy link:', url); // clipboard API unavailable (http, old browser)
    }
  };
```

Restructure the actions container (lines 138-159) so it always renders, with copy-link first:

```tsx
        <div className="flex gap-2 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
          <button
            onClick={handleCopyLink}
            className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-3 rounded inline-flex items-center"
            title="Copy link to this post"
            aria-label="Copy link to this post"
          >
            {copiedLink ? 'Copied ✓' : '🔗 Copy link'}
          </button>
          {showEdit && (
            /* existing Edit button unchanged */
          )}
          {showDelete && (
            /* existing Delete button unchanged */
          )}
        </div>
```

(Keep the existing Edit/Delete button JSX verbatim inside; only the wrapper's condition `{(showEdit || showDelete) && …}` is removed.)

- [ ] **Step 5: Implement arrival scroll + highlight in ThreadDetailPage**

In `ThreadDetailPage.tsx`: change the router import (line 2) to `import { useParams, Link, useLocation } from 'react-router-dom';`, add `const location = useLocation();` beside the other hooks (after line 56), and add this effect after the load effect (after line 137):

```typescript
  // Deep-link arrival: scroll to and briefly highlight #post-N once posts render.
  // If the target is on a later cursor page it simply isn't found — no error.
  useEffect(() => {
    if (loading) return;
    const match = /^#post-(\d+)$/.exec(location.hash);
    if (!match) return;
    const el = document.getElementById(`post-${match[1]}`);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.classList.add('ring-2', 'ring-primary', 'rounded-lg');
    const timer = setTimeout(
      () => el.classList.remove('ring-2', 'ring-primary', 'rounded-lg'),
      2500
    );
    return () => clearTimeout(timer);
  }, [loading, posts, location.hash]);
```

- [ ] **Step 6: Run gates**

Run: `cd web && npm run type-check && npx vitest run src/utils/forumUrls.test.ts src/components/forum/PostCard.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/utils/forumUrls.ts web/src/utils/forumUrls.test.ts web/src/types/notifications.ts web/src/components/layout/NotificationBell.tsx web/src/components/forum/PostCard.tsx web/src/components/forum/PostCard.test.tsx web/src/pages/forum/ThreadDetailPage.tsx
git commit -m "web/forum: post permalinks + notification deep links (wave 1.3)"
```

---

### Task 5: Web — mention styling in rendered posts

`@username` is stored as literal text; the editor styles it (`forumMentionNode.ts` uses `text-primary font-medium`) but rendered posts show plain text. Wrap mentions in styled spans — strictly AFTER DOMPurify sanitization, text nodes only, never inside links/code.

**Files:**

- Create: `web/src/utils/mentions.ts`
- Create: `web/src/utils/mentions.test.ts`
- Modify: `web/src/components/StreamFieldRenderer.tsx` (SafeHTML `postProcess` prop + `mentionHighlight` renderer prop)
- Modify: `web/src/components/forum/PostCard.tsx:164` (pass the flag)
- Test: extend `web/src/components/StreamFieldRenderer.test.tsx`

**Interfaces:**

- Produces: `highlightMentions(sanitizedHtml: string): string`; `StreamFieldRenderer` accepts optional `mentionHighlight?: boolean`.

- [ ] **Step 1: Write the failing util tests**

Create `web/src/utils/mentions.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { highlightMentions } from './mentions';

describe('highlightMentions', () => {
  it('wraps a mention in a styled span', () => {
    expect(highlightMentions('<p>Thanks @bob_botanist!</p>')).toBe(
      '<p>Thanks <span class="text-primary font-medium">@bob_botanist</span>!</p>'
    );
  });

  it('ignores email addresses', () => {
    expect(highlightMentions('<p>mail me at jdoe@example.com</p>')).toBe(
      '<p>mail me at jdoe@example.com</p>'
    );
  });

  it('does not touch text inside links or code', () => {
    const html = '<p><a href="https://x.test">@alice</a> and <code>@beta</code></p>';
    expect(highlightMentions(html)).toBe(html);
  });

  it('handles multiple mentions in one text node', () => {
    expect(highlightMentions('<p>@a and @b</p>')).toBe(
      '<p><span class="text-primary font-medium">@a</span> and <span class="text-primary font-medium">@b</span></p>'
    );
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/utils/mentions.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the util**

Create `web/src/utils/mentions.ts`:

```typescript
/**
 * Wrap @username mentions in styled spans, matching the composer's mention
 * styling (forumMentionNode.ts: text-primary font-medium).
 *
 * SECURITY: operates on ALREADY-SANITIZED HTML (call after createSafeMarkup),
 * walks text nodes only, and inserts only a span with a fixed class — it can
 * never introduce markup from user content.
 */

// A mention starts the string or follows whitespace/"(" — this skips emails,
// where "@" follows a word character.
const MENTION_RE = /(^|[\s(])@([A-Za-z0-9_]+)/g;

export function highlightMentions(sanitizedHtml: string): string {
  if (!sanitizedHtml.includes('@')) return sanitizedHtml;
  const doc = new DOMParser().parseFromString(
    `<div id="__mention_root">${sanitizedHtml}</div>`,
    'text/html'
  );
  const root = doc.getElementById('__mention_root');
  if (!root) return sanitizedHtml;
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const parent = (n as Text).parentElement;
    if (parent && !parent.closest('a, code, pre')) textNodes.push(n as Text);
  }
  for (const node of textNodes) {
    const text = node.textContent || '';
    MENTION_RE.lastIndex = 0;
    if (!MENTION_RE.test(text)) continue;
    const frag = doc.createDocumentFragment();
    let cursor = 0;
    MENTION_RE.lastIndex = 0;
    for (let m = MENTION_RE.exec(text); m; m = MENTION_RE.exec(text)) {
      const mentionStart = m.index + m[1].length;
      frag.appendChild(doc.createTextNode(text.slice(cursor, mentionStart)));
      const span = doc.createElement('span');
      span.className = 'text-primary font-medium';
      span.textContent = `@${m[2]}`;
      frag.appendChild(span);
      cursor = mentionStart + m[2].length + 1;
    }
    frag.appendChild(doc.createTextNode(text.slice(cursor)));
    node.replaceWith(frag);
  }
  return root.innerHTML;
}
```

- [ ] **Step 4: Run util tests**

Run: `cd web && npx vitest run src/utils/mentions.test.ts`
Expected: PASS.

- [ ] **Step 5: Wire into the renderer + PostCard**

`StreamFieldRenderer.tsx`:

**5a.** `SafeHTML` gains a post-sanitization hook:

```tsx
interface SafeHTMLProps {
  html: string;
  className?: string;
  /** Applied AFTER sanitization — must never introduce user-controlled markup. */
  postProcess?: (html: string) => string;
}

function SafeHTML({ html, className = '', postProcess }: SafeHTMLProps) {
  const safeMarkup = createSafeMarkup(html, SANITIZE_PRESETS.STREAMFIELD);
  const markup = postProcess ? { __html: postProcess(safeMarkup.__html) } : safeMarkup;
  return <div className={className} dangerouslySetInnerHTML={markup} />;
}
```

**5b.** Thread the flag through (imports `highlightMentions` in the same edit):

```tsx
import { highlightMentions } from '../utils/mentions';

interface StreamFieldRendererProps {
  blocks?: StreamFieldBlockType[] | null;
  /** Forum posts only: style @username mentions in paragraph blocks. */
  mentionHighlight?: boolean;
}

export default function StreamFieldRenderer({ blocks, mentionHighlight }: StreamFieldRendererProps) {
  if (!blocks || blocks.length === 0) return null;
  return (
    <div className="prose prose-lg max-w-none">
      {blocks.map((block, index) => (
        <StreamFieldBlock key={block.id || index} block={block} mentionHighlight={mentionHighlight} />
      ))}
    </div>
  );
}
```

**5c.** `StreamFieldBlock` accepts and uses it in the paragraph case only:

```tsx
function StreamFieldBlock({ block, mentionHighlight }: StreamFieldBlockProps & { mentionHighlight?: boolean }) {
  // …
    case 'paragraph':
      return (
        <SafeHTML
          html={block.value}
          className="mb-4 text-ink-2 leading-relaxed"
          postProcess={mentionHighlight ? highlightMentions : undefined}
        />
      );
```

**5d.** `PostCard.tsx:164` becomes `<StreamFieldRenderer blocks={post.body} mentionHighlight />`.

- [ ] **Step 6: Extend the renderer test**

Append to `StreamFieldRenderer.test.tsx`:

```tsx
it('styles mentions in paragraphs when mentionHighlight is set', () => {
  const { container } = render(
    <StreamFieldRenderer
      blocks={[{ type: 'paragraph', value: '<p>Thanks @bob_botanist!</p>' }]}
      mentionHighlight
    />
  );
  const span = container.querySelector('span.text-primary.font-medium');
  expect(span?.textContent).toBe('@bob_botanist');
});
```

- [ ] **Step 7: Run gates and commit**

Run: `cd web && npm run type-check && npx vitest run src/utils/mentions.test.ts src/components/StreamFieldRenderer.test.tsx`
Expected: PASS.

```bash
git add web/src/utils/mentions.ts web/src/utils/mentions.test.ts web/src/components/StreamFieldRenderer.tsx web/src/components/forum/PostCard.tsx
git commit -m "web/forum: style @mentions in rendered posts (wave 1.4)"
```

---

### Task 6: Web — reaction row de-clutter + logged-out visibility

Today every post shows four zero-count buttons, and logged-out readers see nothing at all (the row is gated on `onReact`). New behavior: at rest show only non-zero counts as pills (read-only when logged out), plus a single "add reaction" affordance for authenticated users that expands the full picker.

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx:167-184`
- Test: extend `web/src/components/forum/PostCard.test.tsx`

**Interfaces:**

- Consumes: existing `post.reaction_counts` + optional `onReact` prop. No API changes — `ThreadDetailPage` already passes `onReact` only when authenticated (line 453), which now doubles as the read-only switch.

- [ ] **Step 1: Write the failing tests**

Append to `PostCard.test.tsx`:

```tsx
it('shows non-zero reaction counts read-only when logged out (no onReact)', () => {
  render(<PostCard post={{ ...basePost, reaction_counts: { like: 2, love: 0 } }} />);
  expect(screen.getByText('2')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /add reaction/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /react love/i })).not.toBeInTheDocument();
});

it('hides zero counts at rest and expands the picker on demand', () => {
  const onReact = vi.fn();
  render(<PostCard post={{ ...basePost, reaction_counts: { like: 1 } }} onReact={onReact} />);
  expect(screen.queryByRole('button', { name: /react love/i })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /add reaction/i }));
  fireEvent.click(screen.getByRole('button', { name: /react love/i }));
  expect(onReact).toHaveBeenCalledWith('21', 'love');
});

it('renders no reaction row at all for a zero-reaction post viewed logged out', () => {
  render(<PostCard post={{ ...basePost, reaction_counts: {} }} />);
  expect(screen.queryByRole('button', { name: /add reaction/i })).not.toBeInTheDocument();
  expect(screen.queryByText('👍')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/components/forum/PostCard.test.tsx`
Expected: FAIL — current UI renders all four buttons whenever `onReact` exists and nothing without it.

- [ ] **Step 3: Implement**

In `PostCard.tsx`, add state next to the other `useState` calls:

```typescript
  const [showReactionPicker, setShowReactionPicker] = useState(false);
  const nonZeroReactions = REACTION_TYPES.filter((t) => (post.reaction_counts?.[t] ?? 0) > 0);
```

Replace the reactions block (lines 167-184) with:

```tsx
      {(onReact || nonZeroReactions.length > 0) && (
        <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-line">
          {nonZeroReactions.map((type) => (
            <button
              key={type}
              type="button"
              onClick={onReact ? () => onReact(post.id, type) : undefined}
              disabled={!onReact}
              className="inline-flex items-center gap-1 min-h-11 px-3 py-1 bg-surface-2 hover:bg-surface-3 rounded-full text-sm transition-colors disabled:cursor-default disabled:hover:bg-surface-2"
              aria-label={onReact ? `React ${type}` : `${post.reaction_counts?.[type]} ${type}`}
              title={onReact ? `React ${type}` : type}
            >
              <span>{getReactionEmoji(type)}</span>
              <span className="font-medium">{post.reaction_counts?.[type]}</span>
            </button>
          ))}
          {onReact && !showReactionPicker && (
            <button
              type="button"
              onClick={() => setShowReactionPicker(true)}
              className="inline-flex items-center min-h-11 px-3 py-1 text-ink-3 hover:bg-surface-3 rounded-full text-sm transition-colors"
              aria-label="Add reaction"
              title="Add reaction"
            >
              +🙂
            </button>
          )}
          {onReact &&
            showReactionPicker &&
            REACTION_TYPES.filter((t) => !nonZeroReactions.includes(t)).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => {
                  onReact(post.id, type);
                  setShowReactionPicker(false);
                }}
                className="inline-flex items-center min-h-11 px-3 py-1 bg-surface-2 hover:bg-surface-3 rounded-full text-sm transition-colors"
                aria-label={`React ${type}`}
                title={`React ${type}`}
              >
                {getReactionEmoji(type)}
              </button>
            ))}
        </div>
      )}
```

- [ ] **Step 4: Run gates and commit**

Run: `cd web && npm run type-check && npx vitest run src/components/forum/PostCard.test.tsx`
Expected: PASS.

```bash
git add web/src/components/forum/PostCard.tsx web/src/components/forum/PostCard.test.tsx
git commit -m "web/forum: reaction pills — non-zero at rest, read-only for anon (wave 1.5/1.6)"
```

---

### Task 7: Web — forum search entry point in the header

`/forum/search` exists but nothing links to it.

**Files:**

- Modify: `web/src/components/layout/Header.tsx`

**Interfaces:** none — pure markup.

- [ ] **Step 1: Implement**

In `Header.tsx`: add `Search` to the lucide import (line 3), then add a search icon link inside the right-hand group, immediately before `{isAuthenticated && <NotificationBell />}` (line 98):

```tsx
            <Link
              to="/forum/search"
              aria-label="Search the forum"
              title="Search the forum"
              className="p-2 rounded-lg text-ink-2 hover:text-primary hover:bg-surface transition-colors"
            >
              <Search className="w-5 h-5" />
            </Link>
```

And in the mobile menu, after the Community NavLink (line 191):

```tsx
            <NavLink
              to="/forum/search"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Search Forum
            </NavLink>
```

- [ ] **Step 2: Verify + commit**

Run: `cd web && npm run type-check && npm run lint`
Expected: clean. Visual check happens in Task 9's end-to-end pass.

```bash
git add web/src/components/layout/Header.tsx
git commit -m "web/forum: search entry point in header nav (wave 1.1)"
```

---

### Task 8: Web — composer draft autosave

Navigating away silently loses a half-written post. Persist drafts to sessionStorage: per-board for new threads, per-topic for replies; restore on mount; clear on successful submit.

**Files:**

- Create: `web/src/utils/forumDrafts.ts`
- Create: `web/src/utils/forumDrafts.test.ts`
- Modify: `web/src/pages/forum/NewThreadPage.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`

**Interfaces:**

- Produces: `draftKey(kind: 'reply' | 'new-thread', id: string): string`, `loadDraft(key: string): string | null`, `saveDraft(key: string, value: string): void` (empty value removes), `clearDraft(key: string): void`. All storage errors are swallowed (private-mode Safari, quota).

- [ ] **Step 1: Write the failing util tests**

Create `web/src/utils/forumDrafts.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { draftKey, loadDraft, saveDraft, clearDraft } from './forumDrafts';

describe('forumDrafts', () => {
  beforeEach(() => sessionStorage.clear());

  it('round-trips a draft', () => {
    const key = draftKey('reply', '28');
    saveDraft(key, '<p>half-written</p>');
    expect(loadDraft(key)).toBe('<p>half-written</p>');
    clearDraft(key);
    expect(loadDraft(key)).toBeNull();
  });

  it('saving an empty value removes the draft', () => {
    const key = draftKey('new-thread', '54');
    saveDraft(key, '<p>x</p>');
    saveDraft(key, '');
    expect(loadDraft(key)).toBeNull();
  });

  it('swallows storage errors', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    expect(() => saveDraft(draftKey('reply', '1'), 'x')).not.toThrow();
    spy.mockRestore();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/utils/forumDrafts.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the util**

Create `web/src/utils/forumDrafts.ts`:

```typescript
/**
 * Best-effort composer draft persistence (sessionStorage — survives navigation
 * within the tab, intentionally not across sessions). All storage failures are
 * swallowed: drafts are a convenience, never a correctness dependency.
 */

const PREFIX = 'forum-draft:';

export function draftKey(kind: 'reply' | 'new-thread', id: string): string {
  return `${PREFIX}${kind}:${id}`;
}

export function loadDraft(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function saveDraft(key: string, value: string): void {
  try {
    if (value) {
      sessionStorage.setItem(key, value);
    } else {
      sessionStorage.removeItem(key);
    }
  } catch {
    /* private mode / quota — best-effort only */
  }
}

export function clearDraft(key: string): void {
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}
```

- [ ] **Step 4: Run util tests**

Run: `cd web && npx vitest run src/utils/forumDrafts.test.ts`
Expected: PASS.

- [ ] **Step 5: Wire NewThreadPage**

In `NewThreadPage.tsx` (import `{ draftKey, loadDraft, saveDraft, clearDraft }` from `'../../utils/forumDrafts'` in the same edit as first usage):

**5a.** Derive the key and restore initial state (replace lines 30-31):

```typescript
  const newThreadDraftKey = draftKey('new-thread', categoryParam ?? 'unknown');
  const [title, setTitle] = useState(() => {
    try {
      return JSON.parse(loadDraft(newThreadDraftKey) || '{}').title || '';
    } catch {
      return '';
    }
  });
  const [body, setBody] = useState(() => {
    try {
      return JSON.parse(loadDraft(newThreadDraftKey) || '{}').body || '';
    } catch {
      return '';
    }
  });
```

**5b.** Persist on change — add after the load effect (after line 60):

```typescript
  // Persist the draft on every change; an all-empty draft is removed.
  useEffect(() => {
    const isEmpty = title.trim() === '' && isBlankHtml(body);
    saveDraft(newThreadDraftKey, isEmpty ? '' : JSON.stringify({ title, body }));
  }, [title, body, newThreadDraftKey]);
```

**5c.** Clear on success — in `handleSubmit`, immediately after `const res = await createThread({ … });` (line 75), add `clearDraft(newThreadDraftKey);`.

**5d.** TipTap `content` is init-only, but the restored `body` is set before first render (lazy `useState`), so the editor initializes with the draft — pass it as today: `<TipTapEditor content={body} onChange={setBody} … />` (no change needed on line 158).

- [ ] **Step 6: Wire the ThreadDetailPage reply composer**

In `ThreadDetailPage.tsx` (import the same four helpers in the edit that first uses them):

**6a.** Restore per-topic on navigation — inside the `loadData` effect, right after `currentTopicIdRef.current = topicId;` (line 96), add:

```typescript
    // Restore this topic's reply draft (per-topic key); remount the composer
    // so TipTap's init-only content picks it up.
    setReplyBody(topicId != null ? (loadDraft(draftKey('reply', String(topicId))) ?? '') : '');
    setComposerKey((k) => k + 1);
```

**6b.** Persist on change — replace the composer's `onChange={setReplyBody}` (line 506) with:

```tsx
            onChange={(html) => {
              setReplyBody(html);
              if (topicId != null) {
                saveDraft(draftKey('reply', String(topicId)), isBlankHtml(html) ? '' : html);
              }
            }}
```

**6c.** Clear on successful post — in `handleReply`, right after `const res = await createPost({ … });` (line 175), add:

```typescript
        if (topicId != null) clearDraft(draftKey('reply', String(topicId)));
```

- [ ] **Step 7: Run the full web gates**

Run: `cd web && npm run type-check && npm run lint && npm run test`
Expected: all clean/PASS (full suite — this is the last code task).

- [ ] **Step 8: Commit**

```bash
git add web/src/utils/forumDrafts.ts web/src/utils/forumDrafts.test.ts web/src/pages/forum/NewThreadPage.tsx web/src/pages/forum/ThreadDetailPage.tsx
git commit -m "web/forum: composer draft autosave via sessionStorage (wave 1.7)"
```

---

### Task 9: End-to-end verification + PR

Exercise every Wave 1 item in the running app (spec acceptance: "each item verified in the running app, not just tests"), then open the PR.

- [ ] **Step 1: Full backend + web gates**

```bash
cd backend && venv/bin/python -m pytest packages/wagtail_forum -q && venv/bin/python manage.py spectacular --file /dev/null
cd ../web && npm run type-check && npm run lint && npm run test
```

Expected: all pass.

- [ ] **Step 2: Live walkthrough (use the bundled `verify` skill / Playwright)**

Start Redis, `backend: venv/bin/python manage.py runserver 8000`, `web: npm run dev`. Then verify each item as a user:

1. Header shows a search icon → lands on `/forum/search`; mobile menu shows "Search Forum".
2. Search "tomato" (seed data exists in the local dev DB from the 2026-07-17 session — users `alice_gardener`/`bob_botanist`/`carol_composts`, password in that session's seed script): thread card shows REAL reply/view counts and its link opens the thread (previously 404'd).
3. Category filter actually narrows results (`?board=` visible in the network tab).
4. Logged out: bob's earwig post shows its 👍/💡 count pills, read-only; posts with no reactions show no row.
5. Logged in: pills + "+🙂" affordance; picker expands; toggling updates counts.
6. Hover a post → "🔗 Copy link"; paste the URL in a new tab → page scrolls to and highlights the post.
7. Click a notification in the bell → lands ON the post (hash + highlight), not just the thread top.
8. A post containing `@bob_botanist` renders the mention styled (primary color, medium weight).
9. Type a half reply, navigate away, come back → draft restored; post it → composer clears and the draft is gone. Same for a new-thread title+body.

Fix anything that fails before proceeding.

- [ ] **Step 3: Push branch + open PR**

```bash
git push -u origin feat/forum-wave1-honesty-polish
gh pr create --title "Forum Wave 1: honesty & polish sprint" --body "$(cat <<'EOF'
## Summary
Wave 1 of docs/superpowers/specs/2026-07-17-forum-app-loop-roadmap-design.md — makes existing forum features findable and truthful. No new product features, no migrations.

- Search results carry real metadata (was fabricated "0 replies • recently") + working links (were broken) + a real board filter
- Notifications deep-link to the post (#post-N + scroll highlight); per-post copy-link affordance
- @mentions styled in rendered posts (was plain text)
- Reaction counts visible to logged-out readers; zero-count buttons replaced with non-zero pills + add-reaction picker
- Forum search reachable from the header nav
- Composer drafts autosave to sessionStorage (no more silent data loss)

## Test plan
- Package API tests extended (search metadata/filter, notification post_id)
- New/extended Vitest suites: mappers, service, SearchPage, PostCard, mentions, drafts
- Live walkthrough of all 7 items against the dev stack

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Per the user's standing preference: present the PR diff for their review FIRST; only after they've reviewed, arm `gh pr merge --auto --squash --delete-branch`.

---

## Self-Review (completed at authoring time)

- **Spec coverage:** Wave 1 items 1→Task 7, 2→Tasks 1+3, 3→Tasks 2+4, 4→Task 5, 5→Task 6, 6→Task 6, 7→Task 8. Acceptance ("verified in the running app; search shows real counts; notification lands on the post") → Task 9.
- **Placeholders:** none — every code step carries the actual code.
- **Type consistency:** `postAnchor` (Tasks 4), `highlightMentions` (Task 5), `draftKey/loadDraft/saveDraft/clearDraft` (Task 8), and the search payload fields (Tasks 1↔3) are named identically at definition and use sites.
- **Known judgment calls:** search `total_*` remain array lengths (server caps at 50 — documented in code comment); deep links to posts beyond the first cursor page silently no-op (documented; full resolution needs jump-to-post pagination, out of Wave 1 scope).
