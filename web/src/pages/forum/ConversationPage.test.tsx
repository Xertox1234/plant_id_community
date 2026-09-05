import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom';
import ConversationPage from './ConversationPage';
import * as messageService from '../../services/messageService';
import { ForumApiError } from '../../services/forumService';
import type { Conversation, DirectMessage } from '../../types/forum';

vi.mock('../../services/messageService', async () => {
  const actual = await vi.importActual<typeof import('../../services/messageService')>(
    '../../services/messageService'
  );
  return {
    ...actual,
    fetchConversationWith: vi.fn(),
    fetchMessages: vi.fn(),
    sendMessage: vi.fn(),
    reportMessage: vi.fn(),
  };
});
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, user: { id: 1, username: 'me' } }),
}));
const announceMock = vi.hoisted(() => vi.fn());
vi.mock('../../contexts/AnnouncerContext', () => ({ useAnnounce: () => announceMock }));
const refreshMock = vi.hoisted(() => vi.fn());
vi.mock('../../contexts/UnreadNotificationsContext', () => ({
  useUnreadNotifications: () => ({
    unreadCount: 0,
    unreadConversations: 0,
    refresh: refreshMock,
    decrement: vi.fn(),
    clear: vi.fn(),
  }),
}));

const ada = { username: 'ada', display_name: 'Ada L.', avatar: null, trust_level: 2 };
const me = { username: 'me', display_name: 'Me', avatar: null, trust_level: 1 };

const conversation: Conversation = {
  id: 7,
  other_participant: ada,
  created_at: '2026-09-01T00:00:00Z',
  last_message_at: '2026-09-02T00:00:00Z',
  unread_count: 1,
  last_message: { body: 'newest', is_mine: false, created_at: '2026-09-02T00:00:00Z' },
};

function makeMessage(overrides: Partial<DirectMessage> = {}): DirectMessage {
  return {
    id: 1,
    conversation_id: 7,
    sender: ada,
    body: 'hello',
    created_at: '2026-09-02T00:00:00Z',
    ...overrides,
  };
}

// Newest first, as the API delivers it.
const newestPage = (results: DirectMessage[], next: string | null = null) => ({
  results,
  next,
  previous: null,
});

function renderPage(username = 'ada') {
  return render(
    <MemoryRouter initialEntries={[`/messages/${username}`]}>
      <Routes>
        <Route path="/messages/:username" element={<ConversationPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// Same page plus an in-app link to another member, for navigation-race tests.
function renderPageWithNavTo(username: string, other: string) {
  return render(
    <MemoryRouter initialEntries={[`/messages/${username}`]}>
      <Routes>
        <Route
          path="/messages/:username"
          element={
            <>
              <Link to={`/messages/${other}`}>go to {other}</Link>
              <ConversationPage />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

const messageItems = () =>
  within(screen.getByRole('list', { name: 'Messages' })).getAllByRole('listitem');

describe('ConversationPage (todo 339)', () => {
  beforeEach(() => {
    vi.mocked(messageService.fetchConversationWith).mockResolvedValue(conversation);
    vi.mocked(messageService.fetchMessages).mockResolvedValue(newestPage([]));
    vi.mocked(messageService.sendMessage).mockResolvedValue(makeMessage({ id: 99, sender: me }));
    vi.mocked(messageService.reportMessage).mockResolvedValue(undefined);
  });

  it('resolves the thread, renders the newest page oldest→newest, and refreshes the unread badge', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(
      newestPage([
        makeMessage({ id: 3, sender: me, body: 'third (mine)' }),
        makeMessage({ id: 2, body: 'second' }),
        makeMessage({ id: 1, body: 'first' }),
      ])
    );
    renderPage();
    expect(screen.getByRole('status', { name: 'Loading conversation…' })).toBeInTheDocument();

    await screen.findByRole('list', { name: 'Messages' });
    const items = messageItems();
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining('first'),
      expect.stringContaining('second'),
      expect.stringContaining('third (mine)'),
    ]);
    // Own messages are distinguished and carry no Report control.
    expect(items[2]).toHaveAttribute('data-mine', 'true');
    expect(within(items[2]).queryByRole('button', { name: /report/i })).not.toBeInTheDocument();
    expect(items[0]).not.toHaveAttribute('data-mine');
    expect(within(items[0]).getByRole('button', { name: /report/i })).toBeInTheDocument();

    expect(messageService.fetchConversationWith).toHaveBeenCalledWith('ada');
    expect(messageService.fetchMessages).toHaveBeenCalledWith(7);
    expect(refreshMock).toHaveBeenCalled();
    // Header links to the member's profile.
    expect(screen.getByRole('link', { name: 'Ada L.' })).toHaveAttribute(
      'href',
      '/forum/users/ada'
    );
    expect(screen.queryByRole('button', { name: 'Load older' })).not.toBeInTheDocument();
  });

  it('renders message bodies as plain text with line breaks preserved', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(
      newestPage([makeMessage({ body: 'line one\n<b>not bold</b>' })])
    );
    renderPage();
    const body = await screen.findByText(
      (_, el) => el?.textContent === 'line one\n<b>not bold</b>' && el.tagName === 'P'
    );
    expect(body).toHaveClass('whitespace-pre-wrap');
    expect(body.querySelector('b')).toBeNull();
  });

  it('Load older prepends the next (older) page', async () => {
    const cursor = 'http://localhost:8000/api/v1/forum/conversations/7/messages/?cursor=older';
    vi.mocked(messageService.fetchMessages)
      .mockResolvedValueOnce(
        newestPage(
          [makeMessage({ id: 4, body: 'fourth' }), makeMessage({ id: 3, body: 'third' })],
          cursor
        )
      )
      .mockResolvedValueOnce(
        newestPage([makeMessage({ id: 2, body: 'second' }), makeMessage({ id: 1, body: 'first' })])
      );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Load older' }));

    expect(messageService.fetchMessages).toHaveBeenLastCalledWith(7, cursor);
    await waitFor(() => expect(messageItems()).toHaveLength(4));
    expect(messageItems().map((li) => li.textContent)).toEqual([
      expect.stringContaining('first'),
      expect.stringContaining('second'),
      expect.stringContaining('third'),
      expect.stringContaining('fourth'),
    ]);
    expect(screen.queryByRole('button', { name: 'Load older' })).not.toBeInTheDocument();
  });

  it('Send is disabled while the draft is blank, posts the trimmed body, appends the reply and clears', async () => {
    renderPage();
    const composer = await screen.findByPlaceholderText('Message Ada L.…');
    const send = screen.getByRole('button', { name: 'Send' });
    expect(send).toBeDisabled();
    expect(screen.getByText(/0\/4000/)).toBeInTheDocument();
    expect(composer).toHaveAttribute('maxlength', '4000');

    await userEvent.type(composer, '  hi there  ');
    expect(send).toBeEnabled();
    vi.mocked(messageService.sendMessage).mockResolvedValue(
      makeMessage({ id: 99, sender: me, body: 'hi there' })
    );
    await userEvent.click(send);

    expect(messageService.sendMessage).toHaveBeenCalledWith('ada', 'hi there');
    await waitFor(() => expect(messageItems()).toHaveLength(1));
    expect(messageItems()[0]).toHaveTextContent('hi there');
    expect(messageItems()[0]).toHaveAttribute('data-mine', 'true');
    expect(composer).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(announceMock).toHaveBeenCalledWith('Message sent.', 'polite');
    // An existing thread is not re-resolved.
    expect(messageService.fetchConversationWith).toHaveBeenCalledTimes(1);
  });

  it('Cmd/Ctrl+Enter sends from the textarea', async () => {
    renderPage();
    const composer = await screen.findByPlaceholderText('Message Ada L.…');
    await userEvent.type(composer, 'quick{Meta>}{Enter}{/Meta}');
    await waitFor(() => expect(messageService.sendMessage).toHaveBeenCalledWith('ada', 'quick'));
  });

  it('a 403 on send shows the readable blocked notice, not DRF’s default detail', async () => {
    vi.mocked(messageService.sendMessage).mockRejectedValue(
      new ForumApiError('You do not have permission to perform this action.', 403)
    );
    renderPage();
    await userEvent.type(await screen.findByPlaceholderText('Message Ada L.…'), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText("You can't message this member.")).toBeInTheDocument();
    expect(screen.queryByText(/do not have permission/)).not.toBeInTheDocument();
    // The draft survives so the person can see what was refused.
    expect(screen.getByPlaceholderText('Message Ada L.…')).toHaveValue('hi');
    expect(screen.queryByRole('list', { name: 'Messages' })).not.toBeInTheDocument();
  });

  it('a 400 on send shows the server’s own message', async () => {
    vi.mocked(messageService.sendMessage).mockRejectedValue(
      new ForumApiError('This message looks like spam.', 400)
    );
    renderPage();
    await userEvent.type(await screen.findByPlaceholderText('Message Ada L.…'), 'BUY NOW');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('This message looks like spam.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled();
  });

  it('the notice region is mounted and empty before any failure (persistent live region)', async () => {
    renderPage();
    await screen.findByPlaceholderText('Message Ada L.…');
    const region = document.querySelector('[aria-live="polite"][aria-atomic="true"]');
    expect(region).not.toBeNull();
    expect(region).toHaveClass('sr-only');
    expect(region).toBeEmptyDOMElement();
  });

  it('reports another member’s message with a reason and optional detail, then shows Reported', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(
      newestPage([makeMessage({ id: 5, body: 'rude thing' })])
    );
    renderPage();
    await screen.findByText('rude thing');

    await userEvent.click(screen.getByRole('button', { name: /report/i }));
    await userEvent.selectOptions(screen.getByLabelText('Report reason'), 'abuse');
    await userEvent.type(screen.getByLabelText('Details (optional)'), 'name-calling');
    await userEvent.click(screen.getByRole('button', { name: 'Submit' }));

    expect(messageService.reportMessage).toHaveBeenCalledWith(5, 'abuse', 'name-calling');
    expect(await screen.findByText('Reported')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /report/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Report reason')).not.toBeInTheDocument();
  });

  it('a failed report keeps the form open and surfaces the reason', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(newestPage([makeMessage({ id: 5 })]));
    vi.mocked(messageService.reportMessage).mockRejectedValue(
      new ForumApiError('You cannot report your own message.', 400)
    );
    renderPage();
    await screen.findByRole('list', { name: 'Messages' });

    await userEvent.click(screen.getByRole('button', { name: /report/i }));
    await userEvent.click(screen.getByRole('button', { name: 'Submit' }));

    expect(await screen.findByText('You cannot report your own message.')).toBeInTheDocument();
    expect(screen.getByLabelText('Report reason')).toBeInTheDocument();
    expect(screen.queryByText('Reported')).not.toBeInTheDocument();
  });

  it('Cancel closes the report form without calling the service', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(newestPage([makeMessage({ id: 5 })]));
    renderPage();
    await screen.findByRole('list', { name: 'Messages' });

    await userEvent.click(screen.getByRole('button', { name: /report/i }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByLabelText('Report reason')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /report/i })).toBeInTheDocument();
    expect(messageService.reportMessage).not.toHaveBeenCalled();
  });

  it('no thread yet (404 → null): empty prompt, composer live, first send creates and re-resolves it', async () => {
    vi.mocked(messageService.fetchConversationWith)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(conversation);
    renderPage();

    expect(await screen.findByText('No messages yet — say hello.')).toBeInTheDocument();
    expect(messageService.fetchMessages).not.toHaveBeenCalled();
    expect(refreshMock).not.toHaveBeenCalled();
    // Header falls back to the URL username until the thread exists.
    expect(screen.getByRole('link', { name: 'ada' })).toHaveAttribute('href', '/forum/users/ada');

    const composer = screen.getByPlaceholderText('Message ada…');
    await userEvent.type(composer, 'hello!');
    vi.mocked(messageService.sendMessage).mockResolvedValue(
      makeMessage({ id: 42, sender: me, body: 'hello!' })
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(messageItems()).toHaveLength(1));
    expect(screen.queryByText('No messages yet — say hello.')).not.toBeInTheDocument();
    await waitFor(() => expect(messageService.fetchConversationWith).toHaveBeenCalledTimes(2));
    // Re-resolved: the header now carries the member's display name.
    expect(await screen.findByRole('link', { name: 'Ada L.' })).toBeInTheDocument();
  });

  it('shows the error state with a working Retry when the thread fails to load', async () => {
    vi.mocked(messageService.fetchConversationWith)
      .mockRejectedValueOnce(new ForumApiError('HTTP 500', 500))
      .mockResolvedValueOnce(conversation);
    renderPage();

    expect(await screen.findByText('HTTP 500')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/^Message /)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByPlaceholderText('Message Ada L.…')).toBeInTheDocument();
  });

  it('a late response for the previous member never renders into the current thread (identity-swap race)', async () => {
    const bob = { username: 'bob', display_name: 'Bob', avatar: null, trust_level: 1 };
    let resolveAda: (c: Conversation) => void = () => {};
    vi.mocked(messageService.fetchConversationWith).mockImplementation((username) =>
      username === 'ada'
        ? new Promise<Conversation>((resolve) => {
            resolveAda = resolve;
          })
        : Promise.resolve({ ...conversation, id: 8, other_participant: bob })
    );
    vi.mocked(messageService.fetchMessages).mockImplementation((id) =>
      Promise.resolve(
        newestPage([
          makeMessage({
            id: id === 8 ? 81 : 71,
            sender: id === 8 ? bob : ada,
            body: id === 8 ? 'from bob' : 'from ada',
          }),
        ])
      )
    );
    renderPageWithNavTo('ada', 'bob');

    await userEvent.click(screen.getByRole('link', { name: 'go to bob' }));
    expect(await screen.findByText('from bob')).toBeInTheDocument();

    // Ada's thread resolves late — it must be dropped, not painted over Bob's.
    resolveAda(conversation);
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText('from ada')).not.toBeInTheDocument();
    expect(screen.getByText('from bob')).toBeInTheDocument();
  });

  it('navigating away mid-send leaves the next thread’s composer enabled (no stuck flag)', async () => {
    const bob = { username: 'bob', display_name: 'Bob', avatar: null, trust_level: 1 };
    vi.mocked(messageService.fetchConversationWith).mockImplementation((username) =>
      Promise.resolve(
        username === 'ada' ? conversation : { ...conversation, id: 8, other_participant: bob }
      )
    );
    vi.mocked(messageService.sendMessage).mockImplementation(() => new Promise(() => {})); // never settles
    renderPageWithNavTo('ada', 'bob');
    await screen.findByRole('heading', { name: /Ada L\./ });
    await userEvent.type(screen.getByLabelText('Message'), 'hi ada');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(screen.getByLabelText('Message')).toBeDisabled();

    await userEvent.click(screen.getByRole('link', { name: 'go to bob' }));

    await screen.findByRole('heading', { name: /Bob/ });
    expect(screen.getByLabelText('Message')).toBeEnabled();
  });

  it('Load older never duplicates a message already on screen (merge by id)', async () => {
    const older = makeMessage({ id: 1, body: 'older' });
    const newest = makeMessage({ id: 2, body: 'newest' });
    vi.mocked(messageService.fetchMessages)
      .mockResolvedValueOnce(newestPage([newest], 'http://x/older'))
      // The older page overlaps: it returns `newest` again plus one older row.
      .mockResolvedValueOnce(newestPage([newest, older]));
    renderPage();
    await screen.findByText('newest');

    await userEvent.click(screen.getByRole('button', { name: 'Load older' }));

    await screen.findByText('older');
    expect(messageItems().map((li) => li.textContent)).toHaveLength(2);
    expect(screen.getAllByText('newest')).toHaveLength(1);
  });

  it('refocuses the composer after a successful send', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(newestPage([]));
    renderPage();
    await screen.findByRole('heading', { name: /Ada L\./ });
    const composer = screen.getByLabelText('Message');
    await userEvent.type(composer, 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    await screen.findByText('hello');
    expect(composer).toHaveFocus();
  });
});
