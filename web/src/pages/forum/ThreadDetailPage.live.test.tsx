/**
 * ThreadDetailPage over the live socket (forum live replies, slice 3). The
 * mocks mirror ThreadDetailPage.test.tsx:1-87; the socket is the scriptable
 * fake in tests/fakeWebSocket.ts.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
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
vi.mock('../../services/forumService');
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

  it('a 4404 close shows "This topic is no longer available."', async () => {
    await loadAndOpen();
    act(() => live().serverClose(LIVE_CLOSE.notFound));
    expect(await screen.findByText('This topic is no longer available.')).toBeInTheDocument();
  });

  it('catch-up on reopen offers missed replies', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    scrolledUp();
    await loadAndOpen();
    act(() => live().serverClose(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(750);
    });
    expect(sockets).toHaveLength(2);
    vi.mocked(forumService.fetchThread).mockResolvedValue(baseThread({ post_count: 3 }));
    await act(async () => {
      live().open();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(await screen.findByRole('button', { name: 'Load 2 new replies' })).toBeInTheDocument();
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
});
