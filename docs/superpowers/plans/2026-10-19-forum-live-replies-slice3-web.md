# Live Forum Replies, Slice 3 (Web) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in reader with a topic open in the React web app sees new replies, edits, deletes and topic changes live over the slice 2 socket. A per-browser "Live updates" switch turns it off. Two toasts ship with it: the first-time "Turn off" toast, and the signed-out "missing out" toast.

**Architecture:**

- A framework-free socket client (`services/forumLiveSocket.ts`) owns connect, backoff, heartbeat and the close-code rules.
- A hook (`hooks/useTopicLive.ts`) binds it to React and batches events.
- `ThreadDetailPage` applies the events through the state it already has (posts, pill, flash, poll), and turns the 30 s poll off while the socket is connected.
- The setting and the toast flags live in a small `localStorage` store read with `useSyncExternalStore`. It needs no provider, so every existing test renders unchanged.

**Tech Stack:** React 19, TypeScript, Vitest + Testing Library (jsdom), Tailwind 4 (Canopy tokens). There are no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-18-forum-live-replies-design.md`, sections "How it behaves", "The setting", §4 "Client fetch after an event", §5 "Web client" and "Testing → Web".

**Server contract (live in prod since #1159; the client must match it exactly):**

- **URL:** `wss://api.houseplant-md.com/ws/forum/topics/<topic_id>/`. Note there is **no `/api/v1`**. Auth is the `access_token` cookie, which the browser sends on the handshake.
- **Server → client:** `{"v":1,"type":T,"topic_id":int,"post_id":int}`.
  - `T` is one of `post.created`, `post.updated`, `post.removed`, `topic.updated`, `topic.removed`.
  - `topic.*` events carry no `post_id`.
  - `{"v":1,"type":"pong"}` answers a ping.
- **Client → server:** only `{"type":"ping"}`.
- **Close codes.** The server accepts and then closes, so the code reaches the client:
  - 4503: flag off. This is **every** connection in prod until slice 5.
  - 4401: no valid user.
  - 4404: topic not visible, or removed. The server sends `topic.removed` and then closes with 4404.
  - 4429: socket cap reached.
  - A handshake refused for a bad Origin arrives as close 1006 with no code.
- **Refetch:** `GET /api/v1/forum/posts/<id>/` returns the post exactly as the post list does. It returns 404 when the viewer can't see it.

## Global Constraints

- Signed-out readers never open a socket and never see the "N new replies" button (O10).
- No auto-scroll unless the reader is already at the bottom with every page loaded (anti-goal "page jumping").
- Retry is silent. Exponential backoff with jitter starts at about 1 s and is capped at about 30 s. There is no error banner unless the topic itself fails.
- The poll runs only while the socket isn't connected (spec §5). It also runs for signed-out readers.
- Setting: named **"Live updates"**, on by default, stored in `localStorage` with try/catch, default on if unreadable. It has no backend field.
- Toast copy, verbatim:
  - *"Replies now appear live."* with the button **Turn off**;
  - *"Live updates off · Undo"*;
  - signed out: *"New replies are coming in. Sign in or sign up to follow along live."* with **Sign in** and **Sign up**.
- Timer ids live in `useRef` or a closure, never in `useState` (Critical Gotcha #5).
- Imports come from `react-router-dom`, never `react-router` (Gotcha #2).
- All new files are `.ts`/`.tsx`, and new shared types go in `src/types/`.
- A live region is always mounted and changes its text; it is never conditionally mounted (audit M26).
- There is no CSP anywhere: not in `wrangler.jsonc`, not in `index.html`, and `public/sw.js` has no fetch handler. So the spec's conditional `connect-src` step doesn't apply.

## Decisions this plan makes (the spec leaves them to the builder)

| # | Decision | Why |
|---|---|---|
| D1 | **4503 and 4429 are terminal** for the page visit: no retry, and the poll keeps running. | Slice 3 ships while the flag is off, so retrying 4503 would be a reconnect storm against prod. |
| D2 | **4401:** call `refreshAccessToken()` once, reconnect once. A second 4401 is terminal. | The access cookie lasts 15 min and is refreshed every 10 min. A socket opened just before a refresh can carry a stale cookie. |
| D3 | **4404**, at connect or after `topic.removed`: the page shows its existing `ForumErrorState` with the message "This topic is no longer available." | The spec's "existing topic unavailable state". The reply draft is already saved in localStorage per topic, so no text is lost. |
| D4 | **1006 or any other code:** backoff `delay = base/2 + random·base/2` with `base = min(30 000, 1000·2^attempt)`. `attempt` resets on every successful open. It retries forever at the cap. | The poll covers the gap. A misconfigured prod Origin (a slice 5 owner check) would retry every 15–30 s per open tab, which is cheap and silent. |
| D5 | **Heartbeat:** send a ping every 25 s. If no frame arrives within 10 s of a ping, close and reconnect. | uvicorn's protocol ping (20 s) keeps Cloudflare open, but a browser can't see protocol pings, so this is how a dead link is detected. |
| D6 | **A hidden tab keeps its socket.** | The spec closes on background only for mobile. The server cap is 10 sockets per user; past it, a tab gets 4429 and polls. |
| D7 | **Debounce 500 ms** applies to `topic.updated` refetches only. Post fetches are one per id, deduped. | Spec §4 "a burst … collapsed into one fetch". |
| D8 | **Catch-up:** on every socket `open`, run the poll's check once (a peek read) and apply the topic fields. That includes the first open, which covers the gap between page load and connect. | O9 "one catch-up fetch on resume or reconnect". |
| D9 | **The toast is local to the topic page,** with no app-wide provider. | All three toasts belong to this one page. A provider would be YAGNI. |
| D10 | **The setting is a store, not a context:** `useSyncExternalStore` over localStorage plus the `storage` event. | Works with no provider, so the 2346-line test file's render helper is untouched. Another tab's Turn off reaches this tab. |
| D11 | **Sign up** in the missing-out toast goes to `/signup`, which ends at `/verify-email`. Only **Sign in** returns to the topic (via `state.from`, which `LoginPage` honours). | Wiring a return path through email verification is out of scope. |

## Review Focus

1. **Prod flag-off.** Every connect gets 4503: the client must make exactly one attempt per page visit, and the poll must keep running. Pinned in Task 3 (`does not reconnect after 4503`) and Task 6 (`polls while the socket was refused`).
2. **A stray frame is ignored without fetching:** an event for another topic, `v !== 1`, an unknown type, bad JSON, or a binary frame. Pinned in Task 2 (`parseLiveEvent`) and Task 6 (`ignores an event for another topic`).
3. **Own-reply race.** The event for the reader's own reply arrives before or after `handleReply`'s refresh, and it must never show twice or add to the pill. Pinned in Task 6 (`own reply never counts`).
4. **Catch-up after a gap.** Replies that land while disconnected show up as the pill after reconnect. Pinned in Task 6 (`catch-up on reopen offers missed replies`).
5. **Removing the accepted answer** refetches the topic and clears the badge, and removing the post being edited closes the editor with a notice. Pinned in Task 6.

---

### Task 1: The "Live updates" setting store and the Settings switch

**Files:**

- Create: `web/src/utils/liveUpdatesStore.ts`, `web/src/utils/liveUpdatesStore.test.ts`
- Create: `web/src/components/settings/LiveUpdatesSection.tsx`, `web/src/components/settings/LiveUpdatesSection.test.tsx`
- Modify: `web/src/pages/SettingsPage.tsx`. Render `<LiveUpdatesSection />` directly after `<BrowserNotificationsSection />`.

**Interfaces:**

- Produces:
  - `useLiveUpdatesEnabled(): [boolean, (on: boolean) => void]`
  - `readLiveUpdatesEnabled(): boolean`
  - `takeLiveIntro(): boolean`: returns true exactly once per browser, and records it.
  - `mayShowMissingOut(now: number): boolean` and `markMissingOutShown(now: number): void`
  - the exported constants `LIVE_UPDATES_KEY = 'gt-live-updates'`, `LIVE_INTRO_KEY = 'gt-live-intro-shown'`, `MISSING_OUT_KEY = 'gt-live-missing-out-at'`, `MISSING_OUT_SESSION_KEY = 'gt-live-missing-out-session'`, `MISSING_OUT_QUIET_MS = 24 * 60 * 60 * 1000`.

- [ ] **Step 1: Write the failing store tests** (`liveUpdatesStore.test.ts`):
  - `defaults to on when nothing is stored`;
  - `defaults to on when localStorage throws`: use `vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error() })`;
  - `stores 'off' and reads it back`;
  - `a storage event from another tab updates the hook`: render the hook, dispatch `new StorageEvent('storage', { key: LIVE_UPDATES_KEY, newValue: 'off' })`, expect `false`;
  - `takeLiveIntro is true once, then false`;
  - `mayShowMissingOut is false after markMissingOutShown in the same session`;
  - `mayShowMissingOut is false within 24 h of the stored time even in a new session`: clear sessionStorage, set the time to `now - MISSING_OUT_QUIET_MS + 1`;
  - `mayShowMissingOut is true again after 24 h in a new session`.
- [ ] **Step 2: Run** `cd web && npx vitest run src/utils/liveUpdatesStore.test.ts`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement the store.**
  - Stored values: `'on'`/`'off'` for the setting; the intro flag `'1'`; the missing-out time is epoch ms as a string; the session flag `'1'` in sessionStorage.
  - Every read and write is wrapped in try/catch, as `ThemeContext.read`/`persist` do.
  - The hook uses `useSyncExternalStore`. Its subscribe adds an in-tab listener set and a `window` `storage` listener filtered to `LIVE_UPDATES_KEY`.
  - `mayShowMissingOut` is false if the session flag is set, or if the stored time is less than `MISSING_OUT_QUIET_MS` before `now`. `markMissingOutShown` sets both.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Write the failing section tests** (`LiveUpdatesSection.test.tsx`):
  - `renders a "Live updates" switch, on by default`: `getByRole('switch', { name: /live updates/i })` is checked;
  - `turning it off stores off`: `localStorage.getItem(LIVE_UPDATES_KEY) === 'off'`;
  - the detail text names this device.
- [ ] **Step 6: Implement `LiveUpdatesSection`.**
  - Use `<section className="p-screen" aria-label="Live updates">` with `<Eyebrow>Live updates</Eyebrow>`.
  - The input copies the `role="switch"` checkbox markup from `AccountNotificationSwitchesSection` (`SettingsPage.tsx:239-256`).
  - Detail copy: "Show new replies, edits and deletes in an open topic as they happen, in this browser. Off, topics check for new replies every 30 seconds."
- [ ] **Step 7: Run** `npx vitest run src/components/settings/LiveUpdatesSection.test.tsx src/pages/SettingsPage.test.tsx`. Expected: PASS.
- [ ] **Step 8: Commit:** `feat(web): per-browser Live updates setting (forum live replies, slice 3)`.

### Task 2: Event types, the parser and the single-post fetch

**Files:**

- Create: `web/src/types/forumLive.ts`
- Modify: `web/src/services/forumService.ts` (add `fetchPost` after `fetchPosts`), `web/src/services/forumService.test.ts`
- Create: `web/src/services/forumLiveSocket.ts` (the parser only in this task; Task 3 adds the client), `web/src/services/forumLiveSocket.test.ts`

**Interfaces:**

- Produces, in `types/forumLive.ts`:
  - `type LivePostEventType = 'post.created' | 'post.updated' | 'post.removed'`
  - `type LiveTopicEventType = 'topic.updated' | 'topic.removed'`
  - `type LiveEvent = { type: LivePostEventType; topicId: number; postId: string } | { type: LiveTopicEventType; topicId: number }`. `postId` is a string, because the page's `Post.id` is.
  - `type LiveStatus = 'off' | 'connecting' | 'live' | 'stopped' | 'gone'`
- Produces, in `forumLiveSocket.ts`: `parseLiveEvent(data: unknown): LiveEvent | 'pong' | null`.
- Produces, in `forumService.ts`: `fetchPost(postId: string): Promise<Post | null>`, which returns null on a 404.

- [ ] **Step 1: Write the failing parser tests.**
  - `parses each of the five types`.
  - `maps a pong`.
  - `null for v !== 1`, `null for an unknown type`, `null for bad JSON`, `null for non-string data (a Blob/ArrayBuffer)`.
  - `null for a post event with no integer post_id`, `null for a non-integer topic_id`.
  - `ignores extra fields`.
- [ ] **Step 2: Write the failing `fetchPost` tests.**
  - It requests `${API_ORIGIN}/api/v1/forum/posts/7/` with credentials, and maps through `mapPostToPost(res, String(res.topic_id))`.
  - It resolves to `null` on 404.
  - It rejects on 500.
- [ ] **Step 3: Run** `npx vitest run src/services/forumLiveSocket.test.ts src/services/forumService.test.ts`. Expected: FAIL.
- [ ] **Step 4: Implement both.**
  - `fetchPost` calls `authenticatedFetch` and catches a `ForumApiError` whose `status === 404`.
- [ ] **Step 5: Run it again.** Expected: PASS.
- [ ] **Step 6: Commit:** `feat(web): live event types, parser and single-post fetch`.

### Task 3: The socket client (connect, close codes, backoff, heartbeat)

**Files:**

- Modify: `web/src/services/forumLiveSocket.ts`, `web/src/services/forumLiveSocket.test.ts`
- Create: `web/src/tests/fakeWebSocket.ts`

**Interfaces:**

- Consumes: `parseLiveEvent` (Task 2) and `refreshAccessToken` from `services/authService`.
- Produces:
  - `openTopicLive(topicId: number, handlers: { onEvent(e: LiveEvent): void; onOpen(): void; onStatus(s: LiveStatus): void }): { close(): void }`
  - `liveTopicUrl(topicId: number): string`
  - the exported constants `LIVE_CLOSE = { disabled: 4503, unauthenticated: 4401, notFound: 4404, limited: 4429 }`, `BACKOFF_BASE_MS = 1000`, `BACKOFF_CAP_MS = 30_000`, `PING_INTERVAL_MS = 25_000`, `PONG_TIMEOUT_MS = 10_000`.
- Produces, in `tests/fakeWebSocket.ts`:
  - `installFakeWebSocket(): FakeWs[]`, which calls `vi.stubGlobal('WebSocket', …)` and returns the live instance list;
  - `FakeWs` has `url`, `sent: string[]`, `readyState`, `open()`, `message(obj | string)`, `serverClose(code)`, and `close()`, which records `closedByClient = true`.
- Call `installFakeWebSocket()` inside `beforeEach`, because the config's `mockReset: true` wipes module-scope setup.

- [ ] **Step 1: Write the failing tests.** Use `vi.useFakeTimers()`, with `Math.random` spied to `0.5` where a delay matters.
  - `liveTopicUrl maps http→ws and https→wss with no /api/v1`: assert `liveTopicUrl(12)` for both a `http://localhost:8000` and an `https://api.houseplant-md.com` origin. Inject the origin with `vi.stubEnv('VITE_API_URL', …)` and `vi.resetModules()`, or export a pure `toWsUrl(origin, id)` and test that.
  - `reports connecting, then live on open, and calls onOpen`.
  - `delivers parsed events and drops null ones`.
  - `does not reconnect after 4503`: serverClose(4503), advance `BACKOFF_CAP_MS * 4`, and expect one instance with status `'stopped'`.
  - `does not reconnect after 4429`: the same.
  - `4404 reports gone and does not reconnect`.
  - `4401 refreshes once and reconnects once; a second 4401 stops`: mock `refreshAccessToken` to resolve true. Expect 2 instances, then status `'stopped'`, and `refreshAccessToken` called once.
  - `1006 reconnects with backoff, resetting after a successful open`: with random 0.5, the first delay is 750 ms. No instance at 749, one at 750. The second failure waits 1500 ms. After an open and a close, the delay is 750 again.
  - `backoff is capped`: after 10 failures, the next delay is at most `BACKOFF_CAP_MS`.
  - `pings every 25 s and reconnects when no frame arrives within 10 s`.
  - `any frame clears the pong timer`.
  - `close() stops everything`: no reconnect, no timers left (`vi.getTimerCount() === 0`), status `'off'`.
- [ ] **Step 2: Run** `npx vitest run src/services/forumLiveSocket.test.ts`. Expected: FAIL.
- [ ] **Step 3: Implement `openTopicLive`.**
  - It is a closure with `ws`, `attempt`, `retriedAuth` and its timer ids. It has no class and no React.
  - Status transitions:
    - `connecting` on each `new WebSocket`;
    - `live` on `open`;
    - `stopped` after 4503, 4429 or a second 4401;
    - `gone` after 4404;
    - `off` after `close()`.
  - Binary frames reach `parseLiveEvent` and come back null.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): topic live socket client with close-code rules, backoff and heartbeat`.

### Task 4: `useTopicLive`, the React binding

**Files:**

- Create: `web/src/hooks/useTopicLive.ts`, `web/src/hooks/useTopicLive.test.tsx`

**Interfaces:**

- Consumes: `openTopicLive` (Task 3).
- Produces: `useTopicLive(opts: { topicId: number | null; enabled: boolean; onEvent: (e: LiveEvent) => void; onOpen: () => void }): { status: LiveStatus; connected: boolean }`.
  - `connected` is `status === 'live'`.
  - The callbacks are held in refs, so a new function each render never reconnects.
  - The socket reopens only when `topicId` or `enabled` changes.
  - `enabled` false, a null `topicId`, or unmount all call `close()`.

- [ ] **Step 1: Write the failing tests,** using the fake WebSocket helper:
  - `opens one socket when enabled`;
  - `no socket when disabled`;
  - `disabling closes the socket`: `closedByClient` is true and the status is `'off'`;
  - `changing topicId closes the old socket and opens one for the new id`;
  - `new callback identities do not reconnect`;
  - `unmount closes`;
  - `delivers events to the latest onEvent`.
- [ ] **Step 2: Run** `npx vitest run src/hooks/useTopicLive.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implement the hook.** It is a `useEffect` on `[topicId, enabled]` with `useState<LiveStatus>`.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): useTopicLive hook`.

### Task 5: `LiveToast`, the page's accessible toast

**Files:**

- Create: `web/src/components/forum/LiveToast.tsx`, `web/src/components/forum/LiveToast.test.tsx`

**Interfaces:**

- Produces:
  - `LiveToast({ toast, onDismiss }: { toast: LiveToastSpec | null; onDismiss(): void })`
  - `type LiveToastSpec = { id: string; message: string; actions: { label: string; onClick(): void }[] }`, exported from `types/forumLive.ts`
  - `LIVE_TOAST_MS = 10_000`

- [ ] **Step 1: Write the failing tests.**
  - `the status region is mounted while empty`: `getByRole('status')` exists with no text.
  - `shows the message and its action buttons`.
  - `an action calls onClick then onDismiss`.
  - `auto-dismisses after LIVE_TOAST_MS`.
  - `the timer pauses while the toast has focus or hover, and restarts on blur`.
  - `a new toast id restarts the timer`.
  - `has a Dismiss button`, with the accessible name "Dismiss".
- [ ] **Step 2: Run** `npx vitest run src/components/forum/LiveToast.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implement it.**
  - An always-mounted `role="status" aria-live="polite" aria-atomic="true"` wrapper, fixed at the bottom centre and above the pill (`z-20`). Canopy tokens: `canopy-card`, `shadow-2`, buttons through `Button` `variant="outline"`, `min-h-11`.
  - The timer id lives in a `useRef`.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): LiveToast for the topic page`.

### Task 6: Live events on `ThreadDetailPage`

**Files:**

- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`
- Create: `web/src/pages/forum/ThreadDetailPage.live.test.tsx`. Copy only the mocks and render helper from `ThreadDetailPage.test.tsx:1-87`, and do not append to that file. Add `installFakeWebSocket()` to `beforeEach`.

**Interfaces:**

- Consumes: `useTopicLive` (Task 4), `useLiveUpdatesEnabled` (Task 1), `fetchPost` (Task 2).
- Produces: the page-internal `isAtBottom(): boolean`, exported for the tests as `export const LIVE_AT_BOTTOM_PX = 120`. It returns `window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - LIVE_AT_BOTTOM_PX`. Tests set `window.innerHeight`, `window.scrollY` and `document.documentElement.scrollHeight` with `Object.defineProperty(..., { configurable: true, value })`.

The rules, in the order the page applies them. An event whose `topicId` differs from the topic on screen is dropped first.

| Event | Page does |
|---|---|
| `post.created` | Ignore it if the id is already in `posts` or in `ownReplyIdsRef`. **Else, if `nextCursorRef` is null and `isAtBottom()`:** call `fetchPost`, then append it (replacing the entry if that id arrived meanwhile), add it to `flashIds`, `setTotalPosts(n+1)`, and after render scroll to the bottom with `window.scrollTo({ top: document.documentElement.scrollHeight })`. A null fetch is dropped. **Else:** add the id to `liveNewIdsRef` (a Set) and `setNewReplyCount(Math.max(prev, liveNewIdsRef.current.size))`. |
| `post.updated` | Only when the post is in `posts`: call `fetchPost` and replace it in place. A null fetch is ignored. If it is the post being edited, replace the underlying post and leave the edit form alone. |
| `post.removed` | Remove it from `posts` and from `liveNewIdsRef`, and decrement `totalPosts` if it was a loaded non-first post. If it was `thread.solved_post_id`, run the topic refetch. If it was `editingPostId`, close the editor and `setNotice('This post was removed.')`. |
| `topic.updated` | Debounced 500 ms (`LIVE_TOPIC_DEBOUNCE_MS`, exported): `fetchThread(topicId, { peek: true })`, then `setThread(fresh)`. |
| `topic.removed` / status `'gone'` | `setError('This topic is no longer available.')`. |

Other changes:

- **Hook inputs:** the hook runs with `enabled = isAuthenticated && liveEnabled && thread != null && !error && !loading`.
- **Poll gating:** add `connected` to the poll effect's early return and its deps (`:347`).
- **Catch-up (D8):** factor the poll's `check` body into a `useCallback` named `checkForNewReplies(requestTopicId)`. The interval and `onOpen` both call it. On `onOpen` it also calls `setThread(fresh)`.
- **Own reply:** `handleReply` adds `res.id` to `ownReplyIdsRef` before its refresh, and clears `liveNewIdsRef` where it already calls `setNewReplyCount(0)`.
- **O4, jump and highlight:** `handleLoadNewReplies` records the ids that weren't loaded before, adds them to `flashIds`, and after render scrolls `#post-<first new id>` into view (`block: 'start'`). This also upgrades the poll path. `flashIds` is `string[]` state cleared `CANOPY_FLASH_MS` after its last change (a timer in a ref or the effect closure). The post wrapper's class becomes `canopy-flash` when `justPostedId === post.id || flashIds.includes(post.id)`. Navigating clears `flashIds`, `liveNewIdsRef` and `ownReplyIdsRef` in the load effect's reset block (`:213-248`).

- [ ] **Step 1: Write the failing tests** (`ThreadDetailPage.live.test.tsx`), all signed in unless named:
  - `opens a socket for a signed-in reader once the topic loads`: `liveTopicUrl(12)`.
  - `no socket when signed out`, and `no socket when the Live updates setting is off`.
  - `polls while the socket was refused`: serverClose(4503), advance `NEW_REPLIES_POLL_INTERVAL_MS`, expect `fetchThread` called with `{ peek: true }`.
  - `does not poll while connected`: open, advance 2 intervals, expect no peek call except the one catch-up from `onOpen`.
  - `appends and flashes a reply when at the bottom with all pages loaded`: the new post renders and its wrapper has `canopy-flash`; `window.scrollTo` is called.
  - `offers a pill instead when scrolled up`, and `offers a pill when later pages are not loaded`: `Load 1 new reply`, with no `fetchPost` call.
  - `two events for the same id count once`.
  - `ignores an event for another topic`: no fetch, no pill.
  - `own reply never counts`. Two orders:
    - the event arrives while `createPost` is pending;
    - the event arrives after the refresh.

    Both end with no pill and the post shown once.
  - `edit replaces the post in place`. `post.updated` for a post that isn't loaded makes no fetch.
  - `delete removes the post`. Removing the accepted answer refetches the topic and clears the solution ring. Removing the post being edited closes the editor and shows "This post was removed.".
  - `topic.updated bursts collapse into one peek fetch within 500 ms`, and the header shows the new title.
  - `topic.removed shows "This topic is no longer available."`. The same for a 4404 close.
  - `catch-up on reopen offers missed replies`: open, serverClose(1006), advance the backoff, reopen. The peek returns `post_count + 2`, and the pill shows `Load 2 new replies`.
  - `loading new replies jumps to and flashes the first new one`: `scrollIntoView` is called on `#post-<first new id>`.
- [ ] **Step 2: Run** `npx vitest run src/pages/forum/ThreadDetailPage.live.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implement it,** per the table and the bullets above.
- [ ] **Step 4: Run** `npx vitest run src/pages/forum/`. Expected: PASS, the existing `ThreadDetailPage.test.tsx` included. A pre-existing test that breaks is a finding to fix in the page, not a test to edit. If a test really asserted old behaviour that the spec changes (for example the pill for signed-out readers in Task 7), ledger it as a ruling.
- [ ] **Step 5: Commit:** `feat(web): live replies, edits, deletes and topic changes on the topic page`.

### Task 7: The toasts, signed-out readers, and locked-while-typing

**Files:**

- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`, `web/src/pages/forum/ThreadDetailPage.live.test.tsx`

**Interfaces:**

- Consumes: `LiveToast` (Task 5), and `takeLiveIntro`, `mayShowMissingOut`, `markMissingOutShown` (Task 1).

The rules:

- **First-time toast (O12).** When a live reply is appended, or the pill appears from a live event (not the poll), and `takeLiveIntro()` returns true: show *"Replies now appear live."* with **Turn off**.
  - Turn off calls `setLiveEnabled(false)`. The hook closes the socket and the poll resumes. It then shows *"Live updates off · Undo"* with **Undo**, which calls `setLiveEnabled(true)`.
- **Signed out (O10/O11).**
  - The pill wrapper renders only when `isAuthenticated`, but keeps its always-mounted region. The poll keeps running.
  - When a poll tick finds new replies for a signed-out reader and `mayShowMissingOut(Date.now())`: call `markMissingOutShown` and show *"New replies are coming in. Sign in or sign up to follow along live."*.
    - **Sign in** calls `navigate('/login', { state: { from: { pathname: location.pathname } } })`.
    - **Sign up** calls `navigate('/signup')`.
- **Locked while typing.** When `thread.is_locked`, a signed-in reader and `!isEmptyDoc(replyBody)`: render the composer with its text, show the existing locked notice above it, and disable **Post Reply**.
  - A locked thread with an empty draft keeps today's notice-only branch.

- [ ] **Step 1: Write the failing tests:**
  - `the first live reply shows the intro toast once per browser`. Remount and send another event: no toast.
  - `Turn off closes the socket, resumes polling and offers Undo`. Undo opens a new socket.
  - `the poll pill never shows for a signed-out reader`.
  - `a signed-out reader gets the missing-out toast, at most once per session and not again within 24 h`.
  - `Sign in navigates to /login with state.from set to this topic`.
  - `locking while typing keeps the text and disables Post Reply`: `topic.updated` → the peek returns `is_locked: true`.
- [ ] **Step 2: Run** `npx vitest run src/pages/forum/ThreadDetailPage.live.test.tsx`. Expected: FAIL on the new tests.
- [ ] **Step 3: Implement it,** per the rules above.
- [ ] **Step 4: Run** `npx vitest run src/pages/forum/`. Expected: PASS. A pre-existing test that expected the pill while signed out gets a ledgered ruling and is updated, because O10 reverses that behaviour.
- [ ] **Step 5: Commit:** `feat(web): live-updates toasts, signed-out missing-out notice, locked-while-typing`.

### Task 8: Docs, the whole web gate, and a real two-browser smoke

**Files:**

- Modify: `backend/docs/patterns/domain/forum.md`. Add a "Web client" paragraph to "Live events over WebSockets": the close-code table D1–D4, the D8 catch-up, and the fact that the poll runs only while disconnected.
- Modify: `web/docs/patterns/react-typescript.md`. Add a short "WebSocket clients" entry: framework-free client plus a hook, callbacks in refs, `installFakeWebSocket` in `beforeEach`.
- Modify: `docs/LEARNINGS.md`. Append a 2026-10-19 entry: there's no `/api/v1` on the socket URL, 4503 is terminal while the flag is off, and the web app has no CSP.

- [ ] **Step 1: Run the full web gate,** with the output redirected to the workspace:
  `cd web && npm run type-check && npm run lint && npx vitest run && npm run check:classes`.
  Expected: every step exits 0, and Vitest reports 0 failed.
- [ ] **Step 2: Local live smoke.** Use a throwaway database: the dev DB lacks main's migrations, as in slice 2.
  1. Run `uvicorn` with `FORUM_LIVE_UPDATES_ENABLED=True` on :8000 against `plant_community_live_smoke`, detached per the project convention, and run Vite on :5174.
  2. Make two users. With Playwright MCP, sign in as user A in one context and user B in another, both on the same topic.
  3. Check each of these:
     - B replies → A's page shows it with no reload;
     - B edits → A sees the edit;
     - B deletes → it disappears;
     - A's intro toast appears once;
     - Turn off → B's next reply arrives only by the poll (advance or wait 30 s) or the pill;
     - with the flag off and uvicorn restarted, the socket closes 4503 and no retry follows (check the uvicorn log's `[FORUM_LIVE] refused … 4503` count stays 1 per page view).
  4. Drop the throwaway DB afterwards.
- [ ] **Step 3: Commit:** `docs(forum): live replies web client patterns + learnings (slice 3)`.

## Out of scope (later slices)

- Mobile (slice 4).
- The owner device check, and flipping `FORUM_LIVE_UPDATES_ENABLED` on (slice 5), with slice 5's gates from the slice 2 plan.
- A shared app-wide toast system. Reactions, presence and typing.
