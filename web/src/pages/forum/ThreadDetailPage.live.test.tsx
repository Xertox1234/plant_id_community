/**
 * ThreadDetailPage over the live socket (forum live replies, slice 3). The
 * mocks mirror ThreadDetailPage.test.tsx:1-87; the socket is the scriptable
 * fake in tests/fakeWebSocket.ts.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadDetailPage, {
  LIVE_AT_BOTTOM_PX,
  LIVE_TOPIC_DEBOUNCE_MS,
  NEW_REPLIES_POLL_INTERVAL_MS,
} from './ThreadDetailPage';
import { createMockThread, createMockPost } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';
import * as blogService from '../../services/blogService';
import { useAuth } from '../../contexts/AuthContext';
import { AnnouncerProvider } from '../../contexts/AnnouncerContext';
import { liveTopicUrl, LIVE_CLOSE } from '../../services/forumLiveSocket';
import { refreshAccessToken } from '../../services/authService';
import {
  LIVE_UPDATES_KEY,
  MISSING_OUT_QUIET_MS,
  readLiveUpdatesEnabled,
} from '../../utils/liveUpdatesStore';
import { LIVE_TOAST_MS } from '../../components/forum/LiveToast';
import { installFakeWebSocket, type FakeWs } from '../../tests/fakeWebSocket';
import type { JSONContent } from '@tiptap/react';
import type { Post, Thread } from '@/types';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: vi.fn(), useNavigate: vi.fn() };
});
vi.mock('../../services/forumService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/forumService')>();
  const mocked = Object.fromEntries(
    Object.entries(actual).map(([k, v]) => [k, typeof v === 'function' ? vi.fn() : v])
  );
  // The real class: the page branches on `instanceof` and `.status`.
  return { ...mocked, ForumApiError: actual.ForumApiError };
});
vi.mock('../../services/blogService');
vi.mock('../../services/authService', () => ({ refreshAccessToken: vi.fn() }));
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('../../components/forum/TipTapEditor', async () => {
  const { generateHTML } = await import('@tiptap/react');
  const { FORUM_SCHEMA_EXTENSIONS } = await import('../../components/forum/forumEditorSchema');
  const { isBlankDoc, toComposerDoc } = await import('../../utils/forumBody');
  return {
    default: ({
      content,
      onChange,
      placeholder,
    }: {
      content?: JSONContent;
      onChange?: (doc: JSONContent) => void;
      placeholder?: string;
    }) => (
      <textarea
        aria-label={placeholder || 'body'}
        defaultValue={
          content && !isBlankDoc(content) ? generateHTML(content, FORUM_SCHEMA_EXTENSIONS) : ''
        }
        onChange={(e) => onChange?.(toComposerDoc(`<p>${e.target.value}</p>`))}
      />
    ),
  };
});

const mockAuth = (isAuthenticated: boolean) =>
  ({
    user: isAuthenticated ? { id: 1 } : null,
    isAuthenticated,
    revalidateIdentity: vi.fn().mockResolvedValue(isAuthenticated ? { id: 1 } : null),
  }) as unknown as ReturnType<typeof useAuth>;

const post = (id: string, text: string, extra: Partial<Post> = {}) =>
  createMockPost({
    id,
    body: [{ id: `b${id}`, type: 'paragraph', value: `<p>${text}</p>` }],
    ...extra,
  });

const page = (items: Post[], next: string | null = null) => ({
  items,
  meta: { count: 0, next, previous: null },
});

const baseThread = (overrides: Partial<Thread> = {}) =>
  createMockThread({ slug: 'watering-tips', post_count: 1, ...overrides });

const initialPosts = () => [
  post('1', 'Opening post', { is_first_post: true }),
  post('2', 'Reply two'),
];

function setLayout({ scrollY }: { scrollY: number }) {
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 });
  Object.defineProperty(window, 'scrollY', { configurable: true, value: scrollY });
  Object.defineProperty(document.documentElement, 'scrollHeight', {
    configurable: true,
    value: 2000,
  });
}
const atBottom = () => setLayout({ scrollY: 2000 - 800 - LIVE_AT_BOTTOM_PX / 2 });
const scrolledUp = () => setLayout({ scrollY: 0 });

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/forum/plant-care/watering-tips']}>
      <AnnouncerProvider>
        <ThreadDetailPage />
      </AnnouncerProvider>
    </MemoryRouter>
  );
}

const navigate = vi.fn();

describe('ThreadDetailPage live updates', () => {
  let sockets: FakeWs[];
  const live = () => sockets[sockets.length - 1];
  const send = (frame: Record<string, unknown>) =>
    act(async () => {
      live().message({ v: 1, topic_id: 12, ...frame });
      await vi.advanceTimersByTimeAsync(0);
    });
  const peekCalls = () =>
    vi.mocked(forumService.fetchThread).mock.calls.filter((c) => c[1]?.peek).length;

  async function loadAndOpen() {
    renderPage();
    await screen.findByText('Opening post');
    await waitFor(() => expect(sockets.length).toBe(1));
    await act(async () => {
      live().open();
      await vi.advanceTimersByTimeAsync(0);
    });
    // useScrollToTop scrolled on mount; only what follows is the live path's.
    vi.mocked(window.scrollTo).mockClear();
  }

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    localStorage.clear();
    sessionStorage.clear();
    sockets = installFakeWebSocket();
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '12-watering-tips',
    });
    vi.mocked(useAuth).mockReturnValue(mockAuth(true));
    vi.mocked(ReactRouter.useNavigate).mockReturnValue(navigate);
    vi.mocked(forumService.fetchThreads).mockResolvedValue({
      items: [],
      meta: { next: null, count: 0 },
    });
    vi.mocked(blogService.fetchPopularPosts).mockResolvedValue([]);
    vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread());
    vi.mocked(forumService.fetchPosts).mockResolvedValue(page(initialPosts()));
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    HTMLElement.prototype.scrollIntoView = vi.fn();
    atBottom();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('opens a socket for a signed-in reader once the topic loads', async () => {
    renderPage();
    await screen.findByText('Opening post');
    await waitFor(() => expect(sockets).toHaveLength(1));
    expect(sockets[0].url).toBe(liveTopicUrl(12));
  });

  it('no socket when signed out', async () => {
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    renderPage();
    await screen.findByText('Opening post');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(sockets).toHaveLength(0);
  });

  it('no socket when the Live updates setting is off', async () => {
    localStorage.setItem(LIVE_UPDATES_KEY, 'off');
    renderPage();
    await screen.findByText('Opening post');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(sockets).toHaveLength(0);
  });

  it('polls while the socket was refused', async () => {
    renderPage();
    await screen.findByText('Opening post');
    await waitFor(() => expect(sockets).toHaveLength(1));
    act(() => live().serverClose(LIVE_CLOSE.disabled));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    expect(forumService.fetchThread).toHaveBeenLastCalledWith(12, { peek: true });
    expect(sockets).toHaveLength(1);
  });

  it('does not poll while connected', async () => {
    await loadAndOpen();
    // The one catch-up read on open (D8).
    expect(peekCalls()).toBe(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS * 2);
    });
    expect(peekCalls()).toBe(1);
  });

  it('appends and flashes a reply when at the bottom with all pages loaded', async () => {
    vi.mocked(forumService.fetchPost).mockResolvedValue(post('3', 'Live reply'));
    await loadAndOpen();
    await send({ type: 'post.created', post_id: 3 });
    expect(await screen.findByText('Live reply')).toBeInTheDocument();
    expect(document.getElementById('post-3')).toHaveClass('canopy-flash');
    expect(forumService.fetchPost).toHaveBeenCalledWith('3');
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 2000 });
    expect(screen.getByText(/2 replies/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
  });

  it('offers a pill instead when scrolled up', async () => {
    scrolledUp();
    await loadAndOpen();
    await send({ type: 'post.created', post_id: 3 });
    expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
    expect(forumService.fetchPost).not.toHaveBeenCalled();
    expect(window.scrollTo).not.toHaveBeenCalled();
  });

  it('offers a pill when later pages are not loaded', async () => {
    vi.mocked(forumService.fetchPosts).mockResolvedValue(page(initialPosts(), 'next-cursor'));
    await loadAndOpen();
    await send({ type: 'post.created', post_id: 3 });
    expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
    expect(forumService.fetchPost).not.toHaveBeenCalled();
  });

  it('two events for the same id count once', async () => {
    scrolledUp();
    await loadAndOpen();
    await send({ type: 'post.created', post_id: 3 });
    await send({ type: 'post.created', post_id: 3 });
    await send({ type: 'post.created', post_id: 2 });
    expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
  });

  it('ignores an event for another topic', async () => {
    scrolledUp();
    await loadAndOpen();
    await send({ type: 'post.created', topic_id: 99, post_id: 3 });
    await send({ type: 'topic.removed', topic_id: 99 });
    expect(forumService.fetchPost).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    expect(screen.getByText('Opening post')).toBeInTheDocument();
  });

  describe('own reply never counts', () => {
    const withReply = () => page([...initialPosts(), post('3', 'My reply')]);

    async function submitReply() {
      await userEvent.type(screen.getByLabelText('Write a reply...'), 'My reply');
      await userEvent.click(screen.getByRole('button', { name: 'Post Reply' }));
    }

    it('when the event arrives while the reply is still posting', async () => {
      scrolledUp();
      let resolveCreate: (v: { id: string; status: 'published' }) => void = () => {};
      vi.mocked(forumService.createPost).mockReturnValue(
        new Promise((resolve) => {
          resolveCreate = resolve;
        })
      );
      await loadAndOpen();
      await submitReply();
      await send({ type: 'post.created', post_id: 3 });
      vi.mocked(forumService.fetchPosts).mockResolvedValue(withReply());
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      await act(async () => {
        resolveCreate({ id: '3', status: 'published' });
        await vi.advanceTimersByTimeAsync(0);
      });
      await screen.findByText('My reply');
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument()
      );
      expect(screen.getAllByText('My reply')).toHaveLength(1);
    });

    it('when the event arrives after the refresh', async () => {
      atBottom();
      vi.mocked(forumService.createPost).mockResolvedValue({ id: '3', status: 'published' });
      await loadAndOpen();
      vi.mocked(forumService.fetchPosts).mockResolvedValue(withReply());
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      await submitReply();
      await screen.findByText('My reply');
      scrolledUp();
      await send({ type: 'post.created', post_id: 3 });
      expect(forumService.fetchPost).not.toHaveBeenCalled();
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
      expect(screen.getAllByText('My reply')).toHaveLength(1);
    });
  });

  it('edit replaces the post in place', async () => {
    vi.mocked(forumService.fetchPost).mockResolvedValue(post('2', 'Reply two, edited'));
    await loadAndOpen();
    await send({ type: 'post.updated', post_id: 2 });
    expect(await screen.findByText('Reply two, edited')).toBeInTheDocument();
    expect(screen.queryByText('Reply two')).not.toBeInTheDocument();
    expect(window.scrollTo).not.toHaveBeenCalled();
  });

  it('post.updated for a post that is not loaded makes no fetch', async () => {
    await loadAndOpen();
    await send({ type: 'post.updated', post_id: 99 });
    expect(forumService.fetchPost).not.toHaveBeenCalled();
  });

  it('delete removes the post', async () => {
    await loadAndOpen();
    await send({ type: 'post.removed', post_id: 2 });
    await waitFor(() => expect(screen.queryByText('Reply two')).not.toBeInTheDocument());
    expect(screen.getByText(/0 replies/)).toBeInTheDocument();
  });

  it('removing the accepted answer refetches the topic and clears the ring', async () => {
    vi.mocked(forumService.fetchThread).mockResolvedValue(
      baseThread({ is_solved: true, solved_post_id: 2 })
    );
    await loadAndOpen();
    expect(screen.getByText('Accepted answer')).toBeInTheDocument();
    const before = peekCalls();
    vi.mocked(forumService.fetchThread).mockResolvedValue(
      baseThread({ is_solved: false, solved_post_id: null })
    );
    await send({ type: 'post.removed', post_id: 2 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_TOPIC_DEBOUNCE_MS);
    });
    expect(peekCalls()).toBe(before + 1);
    expect(screen.queryByText('Accepted answer')).not.toBeInTheDocument();
  });

  it('removing the post being edited closes the editor with a notice', async () => {
    vi.mocked(forumService.fetchPosts).mockResolvedValue(
      page([
        post('1', 'Opening post', { is_first_post: true }),
        post('2', 'Reply two', { can_edit: true }),
      ])
    );
    await loadAndOpen();
    await userEvent.click(screen.getByTitle('Edit post'));
    expect(await screen.findByLabelText('body')).toBeInTheDocument();
    await send({ type: 'post.removed', post_id: 2 });
    await waitFor(() => expect(screen.queryByLabelText('body')).not.toBeInTheDocument());
    expect(screen.getByText('This post was removed.')).toBeInTheDocument();
  });

  it('topic.updated bursts collapse into one peek fetch within 500 ms', async () => {
    expect(LIVE_TOPIC_DEBOUNCE_MS).toBe(500);
    await loadAndOpen();
    const before = peekCalls();
    vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ title: 'Renamed topic' }));
    await send({ type: 'topic.updated' });
    await send({ type: 'topic.updated' });
    await send({ type: 'topic.updated' });
    expect(peekCalls()).toBe(before);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_TOPIC_DEBOUNCE_MS);
    });
    expect(peekCalls()).toBe(before + 1);
    expect(await screen.findByRole('heading', { name: 'Renamed topic' })).toBeInTheDocument();
  });

  it('topic.removed shows "This topic is no longer available."', async () => {
    await loadAndOpen();
    await send({ type: 'topic.removed' });
    expect(await screen.findByText('This topic is no longer available.')).toBeInTheDocument();
  });

  describe('a 4404 close (audit F37)', () => {
    // The server keeps the socket shut for a password forum the reader may
    // still read over REST, so the close alone never means "gone".
    const close4404 = () =>
      act(async () => {
        live().serverClose(LIVE_CLOSE.notFound);
        await vi.advanceTimersByTimeAsync(0);
      });
    const GONE = 'This topic is no longer available.';

    it.each([404, 403])('shows gone when REST confirms with a %i', async (status) => {
      await loadAndOpen();
      vi.mocked(forumService.fetchThread).mockRejectedValue(
        new forumService.ForumApiError('No.', status)
      );
      await close4404();
      expect(await screen.findByText(GONE)).toBeInTheDocument();
    });

    it('keeps the thread and the 30 s poll when REST still serves the topic', async () => {
      await loadAndOpen();
      const before = peekCalls();
      await close4404();
      expect(peekCalls()).toBe(before + 1);
      expect(screen.queryByText(GONE)).not.toBeInTheDocument();
      expect(screen.getByText('Opening post')).toBeInTheDocument();
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
      expect(sockets).toHaveLength(1);
    });

    it.each([
      ['a network error', () => new TypeError('Failed to fetch')],
      ['a 500', () => new forumService.ForumApiError('Boom', 500)],
      ['a 401', () => new forumService.ForumApiError('Expired', 401)],
    ])('keeps the thread when the check fails with %s', async (_name, makeError) => {
      await loadAndOpen();
      vi.mocked(forumService.fetchThread).mockRejectedValue(makeError());
      await close4404();
      expect(screen.queryByText(GONE)).not.toBeInTheDocument();
      expect(screen.getByText('Opening post')).toBeInTheDocument();

      // The check was inconclusive, so the poll is what learns it is gone.
      vi.mocked(forumService.fetchThread).mockRejectedValue(
        new forumService.ForumApiError('No.', 404)
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(await screen.findByText(GONE)).toBeInTheDocument();
    });
  });

  it('catch-up on reopen offers missed replies', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    scrolledUp();
    await loadAndOpen();
    act(() => live().serverClose(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(sockets).toHaveLength(2);
    vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
    vi.mocked(forumService.fetchPosts).mockResolvedValue(
      page([...initialPosts(), post('3', 'New three'), post('4', 'New four')])
    );
    await act(async () => {
      live().open();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(await screen.findByRole('button', { name: 'Load 2 new replies' })).toBeInTheDocument();
  });

  describe('F39 catch-up reconciles by post id', () => {
    async function reopen() {
      act(() => live().serverClose(1006));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      expect(sockets).toHaveLength(2);
      await act(async () => {
        live().open();
        await vi.advanceTimersByTimeAsync(0);
      });
    }

    beforeEach(() => {
      vi.spyOn(Math, 'random').mockReturnValue(0.5);
      scrolledUp();
    });

    it('a missed delete plus a missed reply drops the one and offers the other', async () => {
      await loadAndOpen();
      // Same count as before: count arithmetic alone would offer nothing.
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 1 }));
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([post('1', 'Opening post', { is_first_post: true }), post('3', 'Reply three')])
      );
      await reopen();
      await waitFor(() => expect(screen.queryByText('Reply two')).not.toBeInTheDocument());
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
      expect(screen.queryByText('Reply three')).not.toBeInTheDocument();
    });

    it('a missed edit is refreshed in place when the peek shows activity', async () => {
      await loadAndOpen();
      // An edit alone moves neither count nor activity (no walk then); here
      // other activity landed too, so the walk runs and carries the edit.
      vi.mocked(forumService.fetchThread).mockResolvedValue(
        baseThread({ post_count: 1, last_activity_at: '2026-11-26T12:00:00Z' })
      );
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([post('1', 'Opening post', { is_first_post: true }), post('2', 'Reply two, edited')])
      );
      await reopen();
      expect(await screen.findByText('Reply two, edited')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    });

    it('a failed walk drops nothing', async () => {
      await loadAndOpen();
      vi.mocked(forumService.fetchPosts).mockRejectedValue(new Error('network down'));
      await reopen();
      expect(screen.getByText('Reply two')).toBeInTheDocument();
    });

    it('a walk cut short at the page bound drops nothing', async () => {
      await loadAndOpen();
      // Every page says there is more: the walk stops at its bound, unfinished.
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([post('1', 'Opening post', { is_first_post: true })], 'more')
      );
      await reopen();
      expect(screen.getByText('Reply two')).toBeInTheDocument();
    });

    it('keeps offering your own reply whose refresh failed', async () => {
      vi.mocked(forumService.createPost).mockResolvedValue({ id: '3', status: 'published' });
      await loadAndOpen();
      vi.mocked(forumService.fetchPosts).mockRejectedValueOnce(new Error('network down'));
      await userEvent.type(screen.getByLabelText('Write a reply...'), 'My reply');
      await userEvent.click(screen.getByRole('button', { name: 'Post Reply' }));
      await screen.findByRole('button', { name: 'Load 1 new reply' });
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([...initialPosts(), post('3', 'My reply')])
      );
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      await reopen();
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
    });

    function deferred<T>() {
      let resolve: (value: T) => void = () => {};
      const promise = new Promise<T>((r) => {
        resolve = r;
      });
      return { promise, resolve };
    }
    // A peek that shows activity (same count): the walk runs.
    const activePeek = () =>
      baseThread({ post_count: 1, last_activity_at: '2026-11-26T12:00:00Z' });

    it('an own edit saved while the walk runs is not overwritten by its older copy', async () => {
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([
          post('1', 'Opening post', { is_first_post: true }),
          post('2', 'Reply two', { can_edit: true }),
        ])
      );
      vi.mocked(forumService.updatePost).mockResolvedValue({
        post: post('2', 'Reply two, mine', { can_edit: true }),
        status: 'published',
      });
      await loadAndOpen();
      vi.mocked(forumService.fetchThread).mockResolvedValue(activePeek());
      const walk = deferred<ReturnType<typeof page>>();
      vi.mocked(forumService.fetchPosts).mockReturnValueOnce(walk.promise);
      await reopen();
      expect(forumService.fetchPosts).toHaveBeenCalledTimes(2);
      await userEvent.click(screen.getByTitle('Edit post'));
      const box = await screen.findByLabelText('body');
      await userEvent.clear(box);
      await userEvent.type(box, 'Reply two, mine');
      await userEvent.click(screen.getByRole('button', { name: /^Save$/i }));
      expect(await screen.findByText('Reply two, mine')).toBeInTheDocument();
      await act(async () => {
        walk.resolve(
          page([
            post('1', 'Opening post', { is_first_post: true }),
            post('2', 'Reply two', { can_edit: true }),
          ])
        );
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(screen.getByText('Reply two, mine')).toBeInTheDocument();
      expect(screen.queryByText(/^Reply two$/)).not.toBeInTheDocument();
    });

    it('a post.updated applied while the walk runs is not overwritten by its older copy', async () => {
      await loadAndOpen();
      vi.mocked(forumService.fetchThread).mockResolvedValue(activePeek());
      const walk = deferred<ReturnType<typeof page>>();
      vi.mocked(forumService.fetchPosts).mockReturnValueOnce(walk.promise);
      await reopen();
      vi.mocked(forumService.fetchPost).mockResolvedValue(post('2', 'Reply two, live edit'));
      await send({ type: 'post.updated', post_id: 2 });
      expect(await screen.findByText('Reply two, live edit')).toBeInTheDocument();
      await act(async () => {
        walk.resolve(page(initialPosts()));
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(screen.getByText('Reply two, live edit')).toBeInTheDocument();
    });

    it('a live insert committed with the walk is never offered as a ghost pill', async () => {
      atBottom();
      await loadAndOpen();
      vi.mocked(forumService.fetchThread).mockResolvedValue(activePeek());
      const walk = deferred<ReturnType<typeof page>>();
      vi.mocked(forumService.fetchPosts).mockReturnValueOnce(walk.promise);
      await reopen();
      const reply = deferred<Post>();
      vi.mocked(forumService.fetchPost).mockReturnValueOnce(reply.promise);
      await send({ type: 'post.created', post_id: 3 });
      // Both land in one flush: the insert, then the walk that already has it.
      await act(async () => {
        reply.resolve(post('3', 'Live reply'));
        walk.resolve(page([...initialPosts(), post('3', 'Live reply')]));
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(await screen.findByText('Live reply')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    });

    it('an unchanged peek walks no pages', async () => {
      await loadAndOpen();
      const calls = vi.mocked(forumService.fetchPosts).mock.calls.length;
      const peeks = peekCalls();
      await reopen();
      expect(peekCalls()).toBe(peeks + 1);
      expect(forumService.fetchPosts).toHaveBeenCalledTimes(calls);
    });

    it.each([
      LIVE_CLOSE.disabled,
      LIVE_CLOSE.limited,
      LIVE_CLOSE.notFound,
      LIVE_CLOSE.unauthenticated,
    ])('a socket refused with %i walks no pages', async (code) => {
      vi.mocked(refreshAccessToken).mockResolvedValue(false);
      await loadAndOpen();
      act(() => live().serverClose(1006));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      vi.mocked(forumService.fetchThread).mockResolvedValue(activePeek());
      const calls = vi.mocked(forumService.fetchPosts).mock.calls.length;
      await act(async () => {
        live().open();
        live().serverClose(code);
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(forumService.fetchPosts).toHaveBeenCalledTimes(calls);
    });
  });

  it('loading new replies jumps to and flashes the first new one', async () => {
    scrolledUp();
    await loadAndOpen();
    await send({ type: 'post.created', post_id: 3 });
    vi.mocked(forumService.fetchPosts).mockResolvedValue(
      page([...initialPosts(), post('3', 'New three'), post('4', 'New four')])
    );
    vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
    await userEvent.click(await screen.findByRole('button', { name: 'Load 1 new reply' }));
    await screen.findByText('New three');
    const first = document.getElementById('post-3');
    expect(first).toHaveClass('canopy-flash');
    expect(document.getElementById('post-4')).toHaveClass('canopy-flash');
    expect(document.getElementById('post-2')).not.toHaveClass('canopy-flash');
    await waitFor(() =>
      expect(vi.mocked(HTMLElement.prototype.scrollIntoView).mock.contexts).toContain(first)
    );
  });

  describe('toasts and locking (Task 7)', () => {
    const INTRO = 'Replies now appear live.';
    const MISSING_OUT = 'New replies are coming in. Sign in or sign up to follow along live.';

    it('the first live reply shows the intro toast once per browser', async () => {
      scrolledUp();
      await loadAndOpen();
      expect(screen.queryByText(INTRO)).not.toBeInTheDocument();
      await send({ type: 'post.created', post_id: 3 });
      expect(await screen.findByText(INTRO)).toBeInTheDocument();
    });

    it('a live insert at the bottom shows the intro toast too', async () => {
      vi.mocked(forumService.fetchPost).mockResolvedValue(post('3', 'Live reply'));
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      await screen.findByText('Live reply');
      expect(await screen.findByText(INTRO)).toBeInTheDocument();
    });

    it('does not show the intro toast again after a remount', async () => {
      scrolledUp();
      const view = renderPage();
      await screen.findByText('Opening post');
      await waitFor(() => expect(sockets.length).toBe(1));
      await act(async () => {
        live().open();
        await vi.advanceTimersByTimeAsync(0);
      });
      await send({ type: 'post.created', post_id: 3 });
      expect(await screen.findByText(INTRO)).toBeInTheDocument();
      view.unmount();
      renderPage();
      await screen.findByText('Opening post');
      await waitFor(() => expect(sockets.length).toBe(2));
      await act(async () => {
        live().open();
        await vi.advanceTimersByTimeAsync(0);
      });
      await send({ type: 'post.created', post_id: 4 });
      await screen.findByRole('button', { name: 'Load 1 new reply' });
      expect(screen.queryByText(INTRO)).not.toBeInTheDocument();
    });

    it('Turn off closes the socket, resumes polling and offers Undo', async () => {
      scrolledUp();
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      await userEvent.click(await screen.findByRole('button', { name: 'Turn off' }));
      expect(readLiveUpdatesEnabled()).toBe(false);
      expect(sockets[0].closedByClient).toBe(true);
      expect(await screen.findByText('Live updates off')).toBeInTheDocument();
      const before = peekCalls();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(peekCalls()).toBe(before + 1);
    });

    it('Undo turns live updates back on and reconnects', async () => {
      scrolledUp();
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      await userEvent.click(await screen.findByRole('button', { name: 'Turn off' }));
      await userEvent.click(await screen.findByRole('button', { name: 'Undo' }));
      expect(readLiveUpdatesEnabled()).toBe(true);
      await waitFor(() => expect(sockets).toHaveLength(2));
    });

    it('the poll pill never shows for a signed-out reader', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(false));
      renderPage();
      await screen.findByText('Opening post');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(peekCalls()).toBe(1);
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    });

    it('a signed-out reader gets the missing-out toast, at most once per session and not again within 24 h', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(false));
      const view = renderPage();
      await screen.findByText('Opening post');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(await screen.findByText(MISSING_OUT)).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(LIVE_TOAST_MS);
      });
      expect(screen.queryByText(MISSING_OUT)).not.toBeInTheDocument();
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 4 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(screen.queryByText(MISSING_OUT)).not.toBeInTheDocument();

      // A new tab session the next morning, still within 24 h: nothing.
      view.unmount();
      sessionStorage.clear();
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread());
      const again = renderPage();
      await screen.findByText('Opening post');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(screen.queryByText(MISSING_OUT)).not.toBeInTheDocument();

      // Past 24 h, in a new session: it may show again.
      again.unmount();
      sessionStorage.clear();
      vi.setSystemTime(Date.now() + MISSING_OUT_QUIET_MS);
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread());
      renderPage();
      await screen.findByText('Opening post');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      expect(await screen.findByText(MISSING_OUT)).toBeInTheDocument();
    });

    it('Sign in navigates to /login with state.from set to this topic', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(false));
      renderPage();
      await screen.findByText('Opening post');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
      expect(navigate).toHaveBeenCalledWith('/login', {
        state: { from: { pathname: '/forum/plant-care/watering-tips' } },
      });
    });

    it('Sign up navigates to /signup', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(false));
      renderPage();
      await screen.findByText('Opening post');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
      });
      await userEvent.click(await screen.findByRole('button', { name: 'Sign up' }));
      expect(navigate).toHaveBeenCalledWith('/signup');
    });

    it('locking while typing keeps the text and disables Post Reply', async () => {
      await loadAndOpen();
      await userEvent.type(screen.getByLabelText('Write a reply...'), 'Half a thought');
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ is_locked: true }));
      await send({ type: 'topic.updated' });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(LIVE_TOPIC_DEBOUNCE_MS);
      });
      expect(await screen.findByText(/This thread is locked/)).toBeInTheDocument();
      expect(screen.getByLabelText('Write a reply...')).toHaveValue('Half a thought');
      expect(screen.getByRole('button', { name: 'Post Reply' })).toBeDisabled();
    });

    it('a locked thread with an empty draft shows only the notice', async () => {
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ is_locked: true }));
      renderPage();
      expect(await screen.findByText(/This thread is locked/)).toBeInTheDocument();
      expect(screen.queryByLabelText('Write a reply...')).not.toBeInTheDocument();
    });
  });

  describe('final-review fixes', () => {
    it('#1 own reply racing ahead of createPost never reaches the pill or the intro toast', async () => {
      scrolledUp();
      let resolveCreate: (v: { id: string; status: 'published' }) => void = () => {};
      vi.mocked(forumService.createPost).mockReturnValue(
        new Promise((resolve) => {
          resolveCreate = resolve;
        })
      );
      await loadAndOpen();
      await userEvent.type(screen.getByLabelText('Write a reply...'), 'My reply');
      await userEvent.click(screen.getByRole('button', { name: 'Post Reply' }));
      await send({ type: 'post.created', post_id: 3 });
      // Mid-window: the event is ours, not someone else's reply.
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
      expect(screen.queryByText('Replies now appear live.')).not.toBeInTheDocument();
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([...initialPosts(), post('3', 'My reply')])
      );
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      await act(async () => {
        resolveCreate({ id: '3', status: 'published' });
        await vi.advanceTimersByTimeAsync(0);
      });
      await screen.findByText('My reply');
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
      expect(screen.queryByText('Replies now appear live.')).not.toBeInTheDocument();
    });

    it("#1 someone else's reply during a pending (moderated) post is still offered", async () => {
      scrolledUp();
      let resolveCreate: (v: { id: string; status: 'pending' }) => void = () => {};
      vi.mocked(forumService.createPost).mockReturnValue(
        new Promise((resolve) => {
          resolveCreate = resolve;
        })
      );
      await loadAndOpen();
      await userEvent.type(screen.getByLabelText('Write a reply...'), 'Held reply');
      await userEvent.click(screen.getByRole('button', { name: 'Post Reply' }));
      await send({ type: 'post.created', post_id: 4 });
      await act(async () => {
        resolveCreate({ id: '3', status: 'pending' });
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
    });

    it('#2 live replies after a catch-up add to the pill', async () => {
      vi.spyOn(Math, 'random').mockReturnValue(0.5);
      scrolledUp();
      await loadAndOpen();
      act(() => live().serverClose(1006));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([...initialPosts(), post('3', 'New three'), post('4', 'New four')])
      );
      await act(async () => {
        live().open();
        await vi.advanceTimersByTimeAsync(0);
      });
      await screen.findByRole('button', { name: 'Load 2 new replies' });
      await send({ type: 'post.created', post_id: 9 });
      expect(await screen.findByRole('button', { name: 'Load 3 new replies' })).toBeInTheDocument();
    });

    it('#3 a reply is not inserted at the bottom while earlier ones wait in the pill', async () => {
      scrolledUp();
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      await screen.findByRole('button', { name: 'Load 1 new reply' });
      atBottom();
      await send({ type: 'post.created', post_id: 4 });
      expect(await screen.findByRole('button', { name: 'Load 2 new replies' })).toBeInTheDocument();
      expect(forumService.fetchPost).not.toHaveBeenCalled();
    });

    it('#9 a reader who scrolls up before the reply arrives is not pulled down', async () => {
      let resolveFetch: (p: Post) => void = () => {};
      vi.mocked(forumService.fetchPost).mockReturnValue(
        new Promise((resolve) => {
          resolveFetch = resolve;
        })
      );
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      scrolledUp();
      await act(async () => {
        resolveFetch(post('3', 'Late reply'));
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
      expect(screen.queryByText('Late reply')).not.toBeInTheDocument();
      expect(window.scrollTo).not.toHaveBeenCalled();
    });
  });

  describe('F44 a restored reply goes in its place, and the pill counts on reconnect', () => {
    // Server order is (created_at, id); a restored reply keeps its old created_at.
    const at = (minute: number) => `2026-11-24T10:0${minute}:00Z`;
    const opening = () => post('1', 'Opening post', { is_first_post: true, created_at: at(0) });
    const four = () => post('4', 'Reply four', { created_at: at(2) });
    const restored = () => post('3', 'Restored three', { created_at: at(1) });
    const ACTIVITY = '2026-11-24T10:02:00Z';

    beforeEach(() => {
      vi.mocked(forumService.fetchPosts).mockResolvedValue(page([opening(), four()]));
    });

    it('a post.created older than the last loaded post is offered, then loaded in order and flashed', async () => {
      vi.mocked(forumService.fetchPost).mockResolvedValue(restored());
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      expect(forumService.fetchPost).toHaveBeenCalledWith('3');
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
      expect(screen.queryByText('Restored three')).not.toBeInTheDocument();
      expect(window.scrollTo).not.toHaveBeenCalled();

      vi.mocked(forumService.fetchPosts).mockResolvedValue(page([opening(), restored(), four()]));
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      await userEvent.click(screen.getByRole('button', { name: 'Load 1 new reply' }));
      await screen.findByText('Restored three');
      const three = document.getElementById('post-3') as HTMLElement;
      const fourEl = document.getElementById('post-4') as HTMLElement;
      // In the middle, above reply four, as the server pages it.
      expect(three.compareDocumentPosition(fourEl) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(three).toHaveClass('canopy-flash');
      expect(fourEl).not.toHaveClass('canopy-flash');
      await waitFor(() =>
        expect(vi.mocked(HTMLElement.prototype.scrollIntoView).mock.contexts).toContain(three)
      );
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    });

    it('a post.created newer than the last loaded post still appends', async () => {
      vi.mocked(forumService.fetchPost).mockResolvedValue(
        post('5', 'Newest five', { created_at: at(3) })
      );
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 5 });
      expect(await screen.findByText('Newest five')).toBeInTheDocument();
      expect(document.getElementById('post-5')).toHaveClass('canopy-flash');
      expect(window.scrollTo).toHaveBeenCalledWith({ top: 2000 });
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    });

    it('a reconnect whose peek counts only the replies already in the pill walks no pages', async () => {
      vi.spyOn(Math, 'random').mockReturnValue(0.5);
      // Pinned: the mock's default moves with the clock.
      vi.mocked(forumService.fetchThread).mockResolvedValue(
        baseThread({ last_activity_at: ACTIVITY })
      );
      scrolledUp();
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      await screen.findByRole('button', { name: 'Load 1 new reply' });
      act(() => live().serverClose(1006));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      expect(sockets).toHaveLength(2);
      // loaded (1 reply) + pill (1); last_activity_at as before.
      vi.mocked(forumService.fetchThread).mockResolvedValue(
        baseThread({ post_count: 2, last_activity_at: ACTIVITY })
      );
      const calls = vi.mocked(forumService.fetchPosts).mock.calls.length;
      const peeks = peekCalls();
      await act(async () => {
        live().open();
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(peekCalls()).toBe(peeks + 1);
      expect(forumService.fetchPosts).toHaveBeenCalledTimes(calls);
      expect(screen.getByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
    });
  });

  describe('forum audit lows (F13, F38, F40)', () => {
    async function confirmDeleteOf(postId: string) {
      const article = document.getElementById(`post-${postId}`) as HTMLElement;
      await userEvent.click(within(article).getByTitle('Delete post'));
      const dialog = await screen.findByRole('dialog');
      await userEvent.click(within(dialog).getByRole('button', { name: /^delete$/i }));
    }

    it('F13 deleting the accepted answer with live updates off clears the solved state', async () => {
      localStorage.setItem(LIVE_UPDATES_KEY, 'off');
      vi.mocked(forumService.fetchThread).mockResolvedValue(
        baseThread({
          is_solved: true,
          solved_post_id: 2,
          // The topic-level surface that reads solved_post_id (the post's own
          // ring leaves with the post).
          identification: {
            image: { id: 7, url: 'http://x/plant.jpg', alt: 'plant.jpg', width: 800, height: 600 },
            provider: 'plant_id',
            candidates: [
              {
                name: 'Swiss cheese plant',
                scientific_name: 'Monstera deliciosa',
                confidence: 0.8,
              },
            ],
            created_at: '2026-07-31T10:00:00Z',
          },
        })
      );
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([
          post('1', 'Opening post', { is_first_post: true }),
          post('2', 'Reply two', { can_delete: true }),
        ])
      );
      vi.mocked(forumService.deletePost).mockResolvedValue(undefined);
      renderPage();
      await screen.findByText('Opening post');
      expect(screen.getByText('See the accepted answer')).toBeInTheDocument();
      await confirmDeleteOf('2');
      await waitFor(() => expect(screen.queryByText('Reply two')).not.toBeInTheDocument());
      expect(screen.queryByText('See the accepted answer')).not.toBeInTheDocument();
      expect(sockets).toHaveLength(0);
    });

    it('F38 deleting your own reply while live counts it once, and no ghost pill follows', async () => {
      vi.spyOn(Math, 'random').mockReturnValue(0.5);
      scrolledUp();
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 2 }));
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([
          post('1', 'Opening post', { is_first_post: true }),
          post('2', 'Reply two', { can_delete: true }),
          post('3', 'Reply three'),
        ])
      );
      let resolveDelete: () => void = () => {};
      vi.mocked(forumService.deletePost).mockReturnValue(
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        })
      );
      await loadAndOpen();
      expect(screen.getByText(/2 replies/)).toBeInTheDocument();
      await confirmDeleteOf('2');
      // The socket frame beats the DELETE response.
      await send({ type: 'post.removed', post_id: 2 });
      await act(async () => {
        resolveDelete();
        await vi.advanceTimersByTimeAsync(0);
      });
      await waitFor(() => expect(screen.queryByText('Reply two')).not.toBeInTheDocument());
      expect(screen.getByText(/\b1 replies/)).toBeInTheDocument();
      // A later catch-up with the server's count offers nothing.
      vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 1 }));
      vi.mocked(forumService.fetchPosts).mockResolvedValue(
        page([post('1', 'Opening post', { is_first_post: true }), post('3', 'Reply three')])
      );
      act(() => live().serverClose(1006));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      await act(async () => {
        live().open();
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    });

    it('F40 a failed fetch after post.created at the bottom offers the pill instead', async () => {
      vi.mocked(forumService.fetchPost).mockRejectedValue(new Error('network down'));
      await loadAndOpen();
      await send({ type: 'post.created', post_id: 3 });
      expect(await screen.findByRole('button', { name: 'Load 1 new reply' })).toBeInTheDocument();
      expect(forumService.fetchPost).toHaveBeenCalledWith('3');
    });
  });
});
