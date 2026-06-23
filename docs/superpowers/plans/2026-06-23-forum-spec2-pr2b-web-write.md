# Forum Spec 2 — PR-2b (Web Write Client) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the React web forum **write** client off the retired machina dialect onto the new `wagtail_forum` REST routes (landed in PR-2a, PR #395) and re-enable the compose/reply/edit/delete/react UI.

**Architecture:** The read client already speaks the new API (Phase 1). This PR rewrites the *write* functions in `forumService.ts` to the PR-2a contract, adjusts the TS types, adds a `NewThreadPage` compose route, and wires reply/edit/delete/react into `ThreadDetailPage` + `PostCard`. The post body is StreamField JSON (`[{type:'paragraph', value:'<p>…</p>'}]`); the composer reuses the existing `TipTapEditor` (HTML out → wrapped as one paragraph block). nh3 on the backend is the trust boundary.

**Tech Stack:** React 19 + TypeScript, React Router v6 (`react-router-dom`), TipTap, Vitest + Testing Library, Tailwind 4.

## Global Constraints

- **Web only.** Branch `feat/forum-spec2-pr2b-web-write` off `main` (disjoint from PR-2a's backend-only diff). PR is **owner-merge** — do NOT auto-arm merge.
- **Body contract:** every write sends `body: [{ type: 'paragraph', value: '<html>' }]`. A single paragraph `RichTextBlock` holds all rich text. nh3 server allowlist = `p,br,strong,b,em,i,u,ul,ol,li,a,code` — heading/quote/strike/codeblock degrade to plain text, so the composer toolbar is trimmed to the surviving marks.
- **Reaction contract:** request field is `type` (NOT `reaction_type`); response is `{ reaction_counts: {…}, reacted: bool }` (no `action`, no `user_reactions`).
- **Create responses are thin:** topic create → `{ id, slug, status }`; reply create → `{ id, status }`. `status` ∈ `published|pending`.
- **Pending ⇒ not live.** A `pending` new topic is `live=False`; `fetchThread(id)` 404s it. **Never navigate into a pending topic** — show an "awaiting moderation" confirmation instead. A `pending` reply must not be appended (the list only returns live posts).
- **Edit re-moderates by author trust** (backend). PATCH returns the full post (currently-live body) + `moderation_status`. Replace state with the returned post; if `pending`, also surface "edit awaiting moderation".
- **Capability flags:** drive edit/delete visibility off backend `post.can_edit` / `post.can_delete`. The client-side author check is dead (the mapper sets `post.author.id = ''`).
- **Auth:** cookie-JWT; `authenticatedFetch` already adds `X-CSRFToken` + `credentials:'include'`. No `Authorization` header.
- **Images are OUT OF SCOPE (PR-3).** Leave `uploadPostImage`/`deletePostImage`/`fetchPostImages`/`reorderPostImage`s and their tests untouched. They are not wired into any compose UI built here.
- **Gates (web CI):** `npm run type-check`, `npm run lint`, `npm run test` (vitest `--run`) must all pass. Run from `web/`.
- **TS conventions:** all source `.ts`/`.tsx`; import Router symbols from `react-router-dom`; avoid `any` (use `unknown`); debounce timers via `useRef`.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `web/src/services/forumService.ts` | modify | Rewrite `createThread`, `createPost`, `updatePost`, `deletePost`, `toggleReaction`; delete `fetchReactions`; add `toBodyBlocks` helper. |
| `web/src/types/forum.ts` | modify | Update `ReactionToggleResult`, `UpdatePostInput`; add `CreateTopicInput`/`CreateReplyInput`/`EditPostResult`/`CreateTopicResult`/`CreateReplyResult`. |
| `web/src/services/forumService.test.ts` | modify | Rewrite write-fn tests to the new contract; delete the `fetchReactions` test + import. |
| `web/src/pages/forum/NewThreadPage.tsx` | create | Compose a new topic; on success branch on `status`. |
| `web/src/pages/forum/NewThreadPage.test.tsx` | create | Render, submit, published→navigate, pending→notice. |
| `web/src/App.tsx` | modify | Add `/forum/new-thread` route (static; outranks `/:categorySlug`). |
| `web/src/pages/forum/ThreadDetailPage.tsx` | modify | Reply composer + edit/delete/react wiring; remove read-only notice; hide composer when locked/closed. |
| `web/src/pages/forum/ThreadDetailPage.test.tsx` | modify | Cover reply/edit/delete/react flows. |
| `web/src/components/forum/PostCard.tsx` | modify | Gate edit/delete on `post.can_edit`/`post.can_delete`; drop dead `useAuth` author check. |
| `web/src/components/forum/PostCard.test.tsx` | modify | Assert capability-flag-driven visibility. |
| `web/src/components/forum/TipTapEditor.tsx` | modify | Trim toolbar to nh3-surviving marks (bold/italic/link/ul/ol/inline-code). |
| `web/src/components/forum/TipTapEditor.test.tsx` | modify | Drop assertions for removed toolbar buttons. |
| `todos/231-in_progress-p1-forum-spec2-read-api-web-client.md` | modify | Work-log: PR-2b landed; todo still open (PR-3 images). |

**Interfaces produced (shared across tasks):**

```ts
// types/forum.ts
export interface CreateTopicInput { boardSlug: string; title: string; content: string; }
export interface CreateReplyInput { thread: number; content: string; }
export interface UpdatePostInput { content: string; }                 // was { content_raw, content_format }
export interface CreateTopicResult { id: string; slug: string; status: 'published' | 'pending'; }
export interface CreateReplyResult { id: string; status: 'published' | 'pending'; }
export interface EditPostResult { post: Post; status: 'published' | 'pending'; }
export interface ReactionToggleResult { reaction_counts: Record<string, number>; reacted: boolean; }
```

```ts
// forumService.ts — body helper (single source of the block shape)
function toBodyBlocks(html: string): Array<{ type: 'paragraph'; value: string }> {
  return [{ type: 'paragraph', value: html }];
}
```

---

### Task 1: Service — reaction contract (`type` request, `{reaction_counts, reacted}` response)

**Files:**

- Modify: `web/src/services/forumService.ts` (`toggleReaction`, delete `fetchReactions` + `BackendReactionResponse`/`toCounts`)
- Modify: `web/src/types/forum.ts` (`ReactionToggleResult`)
- Test: `web/src/services/forumService.test.ts`

**Interfaces:**

- Produces: `toggleReaction(postId, reactionType) → Promise<ReactionToggleResult>` where the body sent is `{ type }` and the result is `{ reaction_counts, reacted }`.

- [ ] **Step 1: Update the test** — replace the `toggleReaction` test and DELETE the `fetchReactions` test + its import.

```ts
// remove `fetchReactions` from the import block at top of file
it('toggleReaction posts {type} and returns {reaction_counts, reacted}', async () => {
  fetchMock.mockResolvedValueOnce(okJson({ reaction_counts: { like: 3 }, reacted: true }));
  const r = await toggleReaction('50', 'like');
  expect(r).toEqual({ reaction_counts: { like: 3 }, reacted: true });
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toContain('/posts/50/reactions/');
  expect(opts.method).toBe('POST');
  expect(JSON.parse(opts.body)).toEqual({ type: 'like' });
});
```

- [ ] **Step 2: Run it — fails** (`cd web && npm run test -- forumService` → toggleReaction assertion fails; `fetchReactions` no longer exported).

- [ ] **Step 3: Implement** — replace the Reactions section of `forumService.ts`:

```ts
/** Toggle a reaction on a post; returns updated counts + this user's resulting state. */
export async function toggleReaction(
  postId: string,
  reactionType: string
): Promise<ReactionToggleResult> {
  return authenticatedFetch<ReactionToggleResult>(`${FORUM_BASE}/posts/${postId}/reactions/`, {
    method: 'POST',
    body: JSON.stringify({ type: reactionType }),
  });
}
```

Delete `fetchReactions`, `BackendReactionResponse`, and `toCounts`. Update `types/forum.ts`:

```ts
export interface ReactionToggleResult {
  reaction_counts: Record<string, number>;
  reacted: boolean;
}
```

- [ ] **Step 4: Run it — passes.**

- [ ] **Step 5: Commit** — `feat(231,pr2b): web reactions onto {type}/{reaction_counts,reacted} contract`

---

### Task 2: Service — create topic (`POST /boards/{slug}/topics/`)

**Files:**

- Modify: `web/src/services/forumService.ts` (`createThread`, add `toBodyBlocks`)
- Modify: `web/src/types/forum.ts` (`CreateTopicInput`, `CreateTopicResult`)
- Test: `web/src/services/forumService.test.ts`

**Interfaces:**

- Consumes: `slugifyTitle` from `../utils/forumUrls`.
- Produces: `createThread({ boardSlug, title, content }) → Promise<CreateTopicResult>`.

- [ ] **Step 1: Test** — replace the machina `createThread` test:

```ts
it('createThread posts to /boards/{slug}/topics/ with {title, slug, body[]}', async () => {
  fetchMock.mockResolvedValueOnce(okJson({ id: 12, slug: 'succulent-help', status: 'published' }));
  const r = await createThread({ boardSlug: 'plant-care', title: 'Succulent help!', content: '<p>hi</p>' });
  expect(r).toEqual({ id: '12', slug: 'succulent-help', status: 'published' });
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toContain('/boards/plant-care/topics/');
  expect(opts.method).toBe('POST');
  expect(JSON.parse(opts.body)).toEqual({
    title: 'Succulent help!',
    slug: 'succulent-help',
    body: [{ type: 'paragraph', value: '<p>hi</p>' }],
  });
});
```

- [ ] **Step 2: Run it — fails.**

- [ ] **Step 3: Implement** — add `toBodyBlocks` near the top of `forumService.ts` and import `slugifyTitle`:

```ts
import { slugifyTitle } from '../utils/forumUrls';

function toBodyBlocks(html: string): Array<{ type: 'paragraph'; value: string }> {
  return [{ type: 'paragraph', value: html }];
}

export async function createThread(data: CreateTopicInput): Promise<CreateTopicResult> {
  const { boardSlug, title, content } = data;
  const res = await authenticatedFetch<{ id: number; slug: string; status: 'published' | 'pending' }>(
    `${FORUM_BASE}/boards/${boardSlug}/topics/`,
    {
      method: 'POST',
      body: JSON.stringify({ title, slug: slugifyTitle(title), body: toBodyBlocks(content) }),
    }
  );
  return { id: String(res.id), slug: res.slug, status: res.status };
}
```

Add to `types/forum.ts`: `CreateTopicInput`, `CreateTopicResult` (see shared block). Remove the now-unused `mapTopicDetailToThread` import from `forumService.ts` **only if** no other function uses it (`fetchThread` still does — keep it).

- [ ] **Step 4: Run it — passes.**

- [ ] **Step 5: Commit** — `feat(231,pr2b): web createThread onto POST /boards/{slug}/topics/`

---

### Task 3: Service — create reply (`POST /topics/{id}/posts/`)

**Files:**

- Modify: `web/src/services/forumService.ts` (`createPost`)
- Modify: `web/src/types/forum.ts` (`CreateReplyInput`, `CreateReplyResult`)
- Test: `web/src/services/forumService.test.ts`

**Interfaces:**

- Produces: `createPost({ thread, content }) → Promise<CreateReplyResult>`.

- [ ] **Step 1: Test** — replace the machina `createPost` tests (the `/posts/create/` test and the missing-`{data}` test):

```ts
it('createPost posts to /topics/{id}/posts/ with {body[]}', async () => {
  fetchMock.mockResolvedValueOnce(okJson({ id: 51, status: 'pending' }));
  const r = await createPost({ thread: 12, content: '<p>hi</p>' });
  expect(r).toEqual({ id: '51', status: 'pending' });
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toContain('/topics/12/posts/');
  expect(opts.method).toBe('POST');
  expect(JSON.parse(opts.body)).toEqual({ body: [{ type: 'paragraph', value: '<p>hi</p>' }] });
});
```

Update the two "Error propagation" tests at the bottom that call `createPost({ thread: 12, content_raw: 'x' })` → `createPost({ thread: 12, content: 'x' })`.

- [ ] **Step 2: Run it — fails.**

- [ ] **Step 3: Implement:**

```ts
export async function createPost(data: CreateReplyInput): Promise<CreateReplyResult> {
  const { thread, content } = data;
  const res = await authenticatedFetch<{ id: number; status: 'published' | 'pending' }>(
    `${FORUM_BASE}/topics/${thread}/posts/`,
    { method: 'POST', body: JSON.stringify({ body: toBodyBlocks(content) }) }
  );
  return { id: String(res.id), status: res.status };
}
```

Add `CreateReplyInput`, `CreateReplyResult` to `types/forum.ts`. Remove the old `CreatePostInput` if unused (search first).

- [ ] **Step 4: Run it — passes.**

- [ ] **Step 5: Commit** — `feat(231,pr2b): web createPost onto POST /topics/{id}/posts/`

---

### Task 4: Service — edit (`PATCH /posts/{id}/`) + delete (`DELETE /posts/{id}/`)

**Files:**

- Modify: `web/src/services/forumService.ts` (`updatePost`, `deletePost`)
- Modify: `web/src/types/forum.ts` (`UpdatePostInput`, `EditPostResult`)
- Test: `web/src/services/forumService.test.ts`

**Interfaces:**

- Consumes: `mapPostToPost` (already imported).
- Produces: `updatePost(postId, { content }) → Promise<EditPostResult>`; `deletePost(postId) → Promise<void>`.

- [ ] **Step 1: Test** — replace the `updatePost` + `deletePost` tests:

```ts
it('updatePost PATCHes /posts/{id}/ with {body[]} and returns {post, status}', async () => {
  fetchMock.mockResolvedValueOnce(
    okJson({ ...backendPost, id: 50, topic_id: 77, moderation_status: 'published' })
  );
  const r = await updatePost('50', { content: '<p>edited</p>' });
  expect(r.status).toBe('published');
  expect(r.post.id).toBe('50');
  expect(r.post.thread).toBe('77');
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toContain('/posts/50/');
  expect(opts.method).toBe('PATCH');
  expect(JSON.parse(opts.body)).toEqual({ body: [{ type: 'paragraph', value: '<p>edited</p>' }] });
});

it('deletePost DELETEs /posts/{id}/ (no /delete/ suffix)', async () => {
  fetchMock.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined });
  await deletePost('50');
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toMatch(/\/posts\/50\/$/);
  expect(opts.method).toBe('DELETE');
});
```

- [ ] **Step 2: Run it — fails.**

- [ ] **Step 3: Implement:**

```ts
export async function updatePost(postId: string, data: UpdatePostInput): Promise<EditPostResult> {
  const res = await authenticatedFetch<BackendPost & { moderation_status: 'published' | 'pending' }>(
    `${FORUM_BASE}/posts/${postId}/`,
    { method: 'PATCH', body: JSON.stringify({ body: toBodyBlocks(data.content) }) }
  );
  return { post: mapPostToPost(res, String(res.topic_id)), status: res.moderation_status };
}

export async function deletePost(postId: string): Promise<void> {
  await authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/`, { method: 'DELETE' });
}
```

Update `types/forum.ts`: `UpdatePostInput = { content: string }`; add `EditPostResult`.

- [ ] **Step 4: Run it — passes.** Then run the **whole** service suite: `npm run test -- forumService` (all green; image tests untouched).

- [ ] **Step 5: Commit** — `feat(231,pr2b): web edit/delete onto PATCH+DELETE /posts/{id}/`

---

### Task 5: NewThread compose page + route

**Files:**

- Create: `web/src/pages/forum/NewThreadPage.tsx`
- Create: `web/src/pages/forum/NewThreadPage.test.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**

- Consumes: `createThread`, `fetchCategory` (service); `parseLeadingId`, `slugifyTitle`, `threadPath`, `categoryPath` (forumUrls); `TipTapEditor`.

**Behavior:**

- Read `?category=<idOrIdSlug>` from the query string. `parseLeadingId` → numeric board id → `fetchCategory(id)` → `{ id, slug, name }`.
- Form: title `<input>` + `TipTapEditor` (onChange → html state). Submit disabled while title empty OR content empty (`<p></p>`/whitespace).
- Submit → `createThread({ boardSlug: category.slug, title, content: html })`.
  - `status === 'published'` → `navigate(threadPath(category, { id: res.id, slug: res.slug }))`.
  - `status === 'pending'` → set a success notice ("Your topic was submitted and is awaiting moderation.") and `navigate(categoryPath(category))` (do NOT navigate into the pending — it 404s).
- Errors → surface `err.message`.

- [ ] **Step 1: Write the failing test** (`NewThreadPage.test.tsx`):

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import NewThreadPage from './NewThreadPage';
import * as svc from '../../services/forumService';

const navigate = vi.fn();
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
  useSearchParams: () => [new URLSearchParams('category=3-plant-care'), vi.fn()],
}));
// TipTap is heavy + jsdom-hostile — stub it to a textarea that emits HTML.
vi.mock('../../components/forum/TipTapEditor', () => ({
  default: ({ onChange }: { onChange?: (h: string) => void }) => (
    <textarea aria-label="body" onChange={(e) => onChange?.(`<p>${e.target.value}</p>`)} />
  ),
}));

beforeEach(() => {
  navigate.mockClear();
  vi.spyOn(svc, 'fetchCategory').mockResolvedValue({
    id: '3', name: 'Plant Care', slug: 'plant-care', created_at: '',
  });
});

it('published topic → navigates into the new thread', async () => {
  vi.spyOn(svc, 'createThread').mockResolvedValue({ id: '12', slug: 'my-topic', status: 'published' });
  render(<MemoryRouter><NewThreadPage /></MemoryRouter>);
  await screen.findByText('Plant Care');
  await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
  await userEvent.type(screen.getByLabelText('body'), 'hello');
  await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith('/forum/3-plant-care/12-my-topic')
  );
});

it('pending topic → shows moderation notice, does NOT navigate into it', async () => {
  vi.spyOn(svc, 'createThread').mockResolvedValue({ id: '12', slug: 'my-topic', status: 'pending' });
  render(<MemoryRouter><NewThreadPage /></MemoryRouter>);
  await screen.findByText('Plant Care');
  await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
  await userEvent.type(screen.getByLabelText('body'), 'hello');
  await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));
  await waitFor(() => expect(navigate).toHaveBeenCalledWith('/forum/3-plant-care'));
  expect(svc.createThread).toHaveBeenCalledWith({
    boardSlug: 'plant-care', title: 'My Topic', content: '<p>hello</p>',
  });
});
```

- [ ] **Step 2: Run it — fails** (no `NewThreadPage`).

- [ ] **Step 3: Implement `NewThreadPage.tsx`** — resolve category in `useEffect`, controlled title + editor html, submit handler branching on `status`. Use `LoadingSpinner`, `Button`, `logger`, match the surface styling of `ThreadListPage`. Guard empty body (`stripHtml(html).trim() === ''`). The submit button label includes "Post" (matches the test regex).

- [ ] **Step 4: Add the route** in `App.tsx` (lazy import + `<Route path="/forum/new-thread" element={<NewThreadPage />} />`). Place it among the forum routes; React Router v6 ranks the static segment above `/:categorySlug`, but add it **before** the param route anyway for clarity. Also remove the duplicate `/forum/search` route line while here.

- [ ] **Step 5: Run it — passes.** `npm run test -- NewThreadPage`.

- [ ] **Step 6: Commit** — `feat(231,pr2b): NewThread compose page + /forum/new-thread route`

---

### Task 6: ThreadDetailPage write wiring + PostCard capability flags

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx` + `PostCard.test.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx` + `ThreadDetailPage.test.tsx`
- Modify: `web/src/components/forum/TipTapEditor.tsx` + `TipTapEditor.test.tsx`

**Interfaces:**

- Consumes: `createPost`, `updatePost`, `deletePost`, `toggleReaction` (service).

**6a — PostCard: drive edit/delete off capability flags.**

- [ ] **Step 1: Update `PostCard.test.tsx`** — assert Edit/Delete render when `post.can_edit`/`post.can_delete` true AND the handler is passed; absent when the flag is false. Remove any `useAuth`-mock-driven author assertions.
- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement** — in `PostCard.tsx` drop `useAuth`/`isAuthor`/`isModerator`/`canEdit`; gate per-button:
  - Edit button: `{post.can_edit && onEdit && (<button …>)}`
  - Delete button: `{post.can_delete && onDelete && (<button …>)}`
  - Wrap row in `{(post.can_edit || post.can_delete) && (onEdit || onDelete) && (…)}`.
  - Remove the now-unused `useAuth` import **in the same edit** (edit-time import strip).
- [ ] **Step 4: Run — passes.**

**6b — TipTapEditor: trim toolbar to nh3-surviving marks.**

- [ ] **Step 5: Update `TipTapEditor.test.tsx`** — drop assertions for H2/H3/strike/blockquote/code-block buttons (if any).
- [ ] **Step 6: Implement** — remove the H2, H3, strikethrough, blockquote, and code-block `ToolbarButton`s (keep bold, italic, bullet list, ordered list, inline code, link/unlink). Optionally disable `heading`/`strike`/`blockquote`/`codeBlock` in `StarterKit.configure` so keyboard shortcuts can't reintroduce them. Keep the component otherwise intact.
- [ ] **Step 7: Run TipTapEditor tests — pass.**

**6c — ThreadDetailPage: reply + edit + delete + react.**

- [ ] **Step 8: Update `ThreadDetailPage.test.tsx`** — add cases: a reply submit calls `createPost` then refetches; a published reply appears; clicking a post's Delete calls `deletePost` and removes it; clicking a reaction calls `toggleReaction` and updates the count; the reply composer is hidden when `thread.is_locked`. Mock `TipTapEditor` to a textarea as in Task 5. Mock the service module.
- [ ] **Step 9: Run — fails.**
- [ ] **Step 10: Implement** — in `ThreadDetailPage.tsx`:
  - Remove the read-only "Replies are coming soon" notice.
  - **Reply composer** (hidden if `thread.is_locked`): `TipTapEditor` + Post button → `createPost({ thread: topicId, content: html })`. On `published` → re-run `fetchPosts({ thread: topicId })` and reset to first page (or append the refetched first page); on `pending` → toast "awaiting moderation", clear editor, do not append.
  - **`handleReact(postId, type)`** → `toggleReaction(postId, type)` → map result `reaction_counts` onto that post in `posts` state.
  - **`handleDelete(post)`** → `window.confirm` → `deletePost(post.id)` → filter it out of `posts`, decrement `totalPosts`.
  - **`handleEdit(post)`** → set an `editingPostId`; render an inline `TipTapEditor` seeded with `bodyToHtml(post.body)` (first paragraph block value); Save → `updatePost(post.id, { content })` → replace that post with `result.post`; if `result.status === 'pending'` toast "edit awaiting moderation". `bodyToHtml = (blocks) => blocks?.find(b => b.type === 'paragraph')?.value ?? ''`.
  - Pass `onEdit={handleEdit}` `onDelete={handleDelete}` `onReact={handleReact}` to each `PostCard`.
- [ ] **Step 11: Run — passes.**

- [ ] **Step 12: Commit** — `feat(231,pr2b): wire reply/edit/delete/react into ThreadDetailPage + capability-flag PostCard`

---

### Task 7: Gate, machina sweep, work-log

**Files:**

- Modify: `todos/231-in_progress-p1-forum-spec2-read-api-web-client.md`

- [ ] **Step 1: Machina sweep** — confirm no machina **write** paths remain in the migrated functions:

```bash
cd web && grep -nE "topics/create/|posts/create/|posts/[^/]+/delete/|reaction_type|categories/[0-9]" src/services/forumService.ts
```

Expected: only the **image** functions may still match `…/delete/` (PR-3); the topic/reply/edit/reaction lines must be gone. If a non-image match remains, fix it.

- [ ] **Step 2: Full web gate:**

```bash
cd web && npm run type-check && npm run lint && npm run test -- --run
```

Expected: type-check 0 errors; lint clean; vitest all green.

- [ ] **Step 3: Work-log** — append a `### 2026-06-23 - PR-2b (web write client) landed — todo still OPEN` entry to todo 231: list the migrated write fns + contracts, the new compose page, the capability-flag wiring, the verification output, and "Still open: PR-3 (images) — `image` block render + `POST /topics/{id}/images/` + `validate_forum_body` relax; todo 231 archives after PR-3."

- [ ] **Step 4: Commit** — `docs(231,pr2b): work-log web write client; PR-3 images remain`

---

## Self-Review

- **Spec coverage:** Phase 2 client (create topic/reply, edit, delete, react, route rationalization consumed) ✓. Phase 3 images explicitly deferred ✓. Error surfacing via `authenticatedFetch` (unchanged) ✓. `can_edit`/`can_delete` consumed ✓. Cursor "Load More" already present (Phase 1) — untouched ✓.
- **Type consistency:** `CreateTopicInput`/`CreateReplyInput`/`UpdatePostInput`/`*Result` defined in Task 1's shared block, consumed by Tasks 2–6 ✓. `toBodyBlocks` defined once (Task 2) ✓.
- **Pending correctness:** new-topic pending → board nav, not thread nav (Task 5) ✓; pending reply not appended (Task 6) ✓.
- **No placeholders:** service-layer code is complete; UI tasks specify exact handlers + the `bodyToHtml`/`toBodyBlocks` shapes ✓.
