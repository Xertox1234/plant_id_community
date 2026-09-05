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
    fetchConversation: vi.fn(),
    fetchMessages: vi.fn(),
    sendMessage: vi.fn(),
    sendConversationMessage: vi.fn(),
    addParticipant: vi.fn(),
    removeParticipant: vi.fn(),
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

const grace = { username: 'grace', display_name: 'Grace', avatar: null, trust_level: 1 };

const conversation: Conversation = {
  id: 7,
  kind: 'direct',
  title: '',
  other_participant: ada,
  participants: [me, ada],
  participant_count: 2,
  created_by: null,
  can_manage: false,
  created_at: '2026-09-01T00:00:00Z',
  last_message_at: '2026-09-02T00:00:00Z',
  unread_count: 1,
  last_message: { body: 'newest', is_mine: false, sender: ada, created_at: '2026-09-02T00:00:00Z' },
};

// A group the viewer belongs to but did not create (Ada did).
const group: Conversation = {
  id: 12,
  kind: 'group',
  title: 'Seed swap committee',
  other_participant: null,
  participants: [ada, me, grace],
  participant_count: 3,
  created_by: ada,
  can_manage: false,
  created_at: '2026-09-01T00:00:00Z',
  last_message_at: '2026-09-02T00:00:00Z',
  unread_count: 0,
  last_message: { body: 'newest', is_mine: false, sender: ada, created_at: '2026-09-02T00:00:00Z' },
};
// The same group as its creator sees it.
const ownedGroup: Conversation = {
  ...group,
  participants: [me, ada, grace],
  created_by: me,
  can_manage: true,
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

function renderGroupPage(id: number | string = 12) {
  return render(
    <MemoryRouter initialEntries={[`/messages/group/${id}`]}>
      <Routes>
        <Route path="/messages" element={<p>inbox stub</p>} />
        <Route path="/messages/group/:id" element={<ConversationPage />} />
        <Route path="/messages/:username" element={<ConversationPage />} />
      </Routes>
    </MemoryRouter>
  );
}

/** Open the members panel (the header toggle) and return its list. */
async function openMembersPanel(count: number) {
  await userEvent.click(screen.getByRole('button', { name: `Members (${count})` }));
  return screen.getByRole('list', { name: 'Manage members' });
}

describe('ConversationPage (todo 339)', () => {
  beforeEach(() => {
    vi.mocked(messageService.fetchConversationWith).mockResolvedValue(conversation);
    vi.mocked(messageService.fetchMessages).mockResolvedValue(newestPage([]));
    vi.mocked(messageService.sendMessage).mockResolvedValue(makeMessage({ id: 99, sender: me }));
    vi.mocked(messageService.reportMessage).mockResolvedValue(undefined);
  });

  it('a direct thread never touches the group resolver or the id send endpoint', async () => {
    renderPage();
    await userEvent.type(await screen.findByPlaceholderText('Message Ada L.…'), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(messageService.sendMessage).toHaveBeenCalledWith('ada', 'hi'));
    expect(messageService.fetchConversation).not.toHaveBeenCalled();
    expect(messageService.sendConversationMessage).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /^Members \(/ })).not.toBeInTheDocument();
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

describe('ConversationPage groups (todo 350)', () => {
  beforeEach(() => {
    vi.mocked(messageService.fetchConversation).mockResolvedValue(group);
    vi.mocked(messageService.fetchMessages).mockResolvedValue(newestPage([]));
    vi.mocked(messageService.sendConversationMessage).mockResolvedValue(
      makeMessage({ id: 99, conversation_id: 12, sender: me })
    );
    vi.mocked(messageService.addParticipant).mockResolvedValue(ownedGroup);
    vi.mocked(messageService.removeParticipant).mockResolvedValue(undefined);
  });

  it('resolves by id, shows the title and the members row with the creator marked, and names the sender once per run', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(
      newestPage([
        makeMessage({ id: 4, conversation_id: 12, sender: grace, body: 'fourth' }),
        makeMessage({ id: 3, conversation_id: 12, sender: me, body: 'third (mine)' }),
        makeMessage({ id: 2, conversation_id: 12, sender: ada, body: 'second' }),
        makeMessage({ id: 1, conversation_id: 12, sender: ada, body: 'first' }),
      ])
    );
    renderGroupPage();

    expect(await screen.findByRole('heading', { name: 'Seed swap committee' })).toBeInTheDocument();
    expect(messageService.fetchConversation).toHaveBeenCalledWith(12);
    expect(messageService.fetchConversationWith).not.toHaveBeenCalled();
    expect(messageService.fetchMessages).toHaveBeenCalledWith(12);
    expect(refreshMock).toHaveBeenCalled();

    const members = within(screen.getByRole('list', { name: 'Members' })).getAllByRole('listitem');
    expect(members.map((li) => li.textContent)).toEqual(['Ada L.creator', 'You', 'Grace']);
    expect(screen.getByRole('button', { name: 'Members (3)' })).toHaveAttribute(
      'aria-expanded',
      'false'
    );

    const items = messageItems();
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining('first'),
      expect.stringContaining('second'),
      expect.stringContaining('third (mine)'),
      expect.stringContaining('fourth'),
    ]);
    // Ada's run carries her name once; the viewer's own message none; Grace's starts a new run.
    expect(within(items[0]).getByRole('link', { name: 'Ada L.' })).toHaveAttribute(
      'href',
      '/forum/users/ada'
    );
    expect(within(items[1]).queryByRole('link')).not.toBeInTheDocument();
    expect(items[2]).toHaveAttribute('data-mine', 'true');
    expect(within(items[2]).queryByRole('link')).not.toBeInTheDocument();
    expect(within(items[3]).getByRole('link', { name: 'Grace' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Message Seed swap committee…')).toBeInTheDocument();
  });

  it('sends through the conversation-id endpoint, never the username one', async () => {
    renderGroupPage();
    const composer = await screen.findByPlaceholderText('Message Seed swap committee…');
    await userEvent.type(composer, '  hi all  ');
    vi.mocked(messageService.sendConversationMessage).mockResolvedValue(
      makeMessage({ id: 99, conversation_id: 12, sender: me, body: 'hi all' })
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(messageService.sendConversationMessage).toHaveBeenCalledTimes(1);
    expect(messageService.sendConversationMessage).toHaveBeenCalledWith(12, 'hi all');
    expect(messageService.sendMessage).not.toHaveBeenCalled();
    await waitFor(() => expect(messageItems()).toHaveLength(1));
    expect(messageItems()[0]).toHaveTextContent('hi all');
    expect(messageItems()[0]).toHaveAttribute('data-mine', 'true');
    expect(composer).toHaveValue('');
    expect(announceMock).toHaveBeenCalledWith('Message sent.', 'polite');
  });

  it('a 403 on a group send shows the group notice, not DRF’s default detail', async () => {
    vi.mocked(messageService.sendConversationMessage).mockRejectedValue(
      new ForumApiError('You cannot message this group.', 403)
    );
    renderGroupPage();
    await userEvent.type(await screen.findByPlaceholderText('Message Seed swap committee…'), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText("You can't message this group.")).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Message Seed swap committee…')).toHaveValue('hi');
  });

  it('a member (not the creator) sees Leave group but neither Remove nor Add member', async () => {
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    expect(screen.queryByRole('list', { name: 'Manage members' })).not.toBeInTheDocument();

    const panel = await openMembersPanel(3);
    expect(screen.getByRole('button', { name: 'Members (3)' })).toHaveAttribute(
      'aria-expanded',
      'true'
    );
    expect(within(panel).getAllByRole('listitem')).toHaveLength(3);
    expect(within(panel).getByRole('link', { name: 'Ada L.' })).toHaveAttribute(
      'href',
      '/forum/users/ada'
    );
    expect(screen.queryByRole('button', { name: /^Remove / })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Add member')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Leave group' })).toBeEnabled();
  });

  it('the creator (can_manage) sees Remove for every other member and Add member, but no Leave group', async () => {
    vi.mocked(messageService.fetchConversation).mockResolvedValue(ownedGroup);
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    const panel = await openMembersPanel(3);

    const removes = within(panel).getAllByRole('button', { name: /^Remove / });
    expect(removes.map((b) => b.getAttribute('aria-label'))).toEqual([
      'Remove Ada L.',
      'Remove Grace',
    ]);
    // Never for yourself.
    expect(screen.queryByRole('button', { name: 'Remove You' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove Me' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Add member')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Leave group' })).not.toBeInTheDocument();
    const members = within(screen.getByRole('list', { name: 'Members' })).getAllByRole('listitem');
    expect(members[0]).toHaveTextContent('Youcreator');
  });

  it('Remove DELETEs the member and drops them locally after the 204', async () => {
    vi.mocked(messageService.fetchConversation).mockResolvedValue(ownedGroup);
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    const panel = await openMembersPanel(3);

    await userEvent.click(within(panel).getByRole('button', { name: 'Remove Grace' }));

    expect(messageService.removeParticipant).toHaveBeenCalledWith(12, 'grace');
    await waitFor(() => expect(within(panel).getAllByRole('listitem')).toHaveLength(2));
    expect(within(panel).queryByText('@grace')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Members (2)' })).toBeInTheDocument();
    const members = within(screen.getByRole('list', { name: 'Members' })).getAllByRole('listitem');
    expect(members.map((li) => li.textContent)).toEqual(['Youcreator', 'Ada L.']);
    expect(announceMock).toHaveBeenCalledWith('Removed grace from the group.', 'polite');
    // No re-resolve: the 204 is the source of truth.
    expect(messageService.fetchConversation).toHaveBeenCalledTimes(1);
  });

  it('Add member POSTs the username and replaces the row from the response', async () => {
    const linus = { username: 'linus', display_name: 'Linus', avatar: null, trust_level: 1 };
    vi.mocked(messageService.fetchConversation).mockResolvedValue(ownedGroup);
    vi.mocked(messageService.addParticipant).mockResolvedValue({
      ...ownedGroup,
      participants: [...ownedGroup.participants, linus],
      participant_count: 4,
    });
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    await openMembersPanel(3);

    const input = screen.getByLabelText('Add member');
    expect(input).not.toHaveAttribute('aria-disabled');
    expect(input).toHaveAccessibleDescription('Up to 8 members, including you.');
    await userEvent.type(input, '@linus');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));

    expect(messageService.addParticipant).toHaveBeenCalledWith(12, 'linus');
    expect(await screen.findByRole('button', { name: 'Members (4)' })).toBeInTheDocument();
    expect(
      within(screen.getByRole('list', { name: 'Manage members' })).getByText('@linus')
    ).toBeInTheDocument();
    expect(input).toHaveValue('');
    expect(announceMock).toHaveBeenCalledWith('Added linus to the group.', 'polite');
  });

  it('at the cap the Add member field stays focusable but is aria-disabled with a hint, and adds nothing', async () => {
    const extras = ['u4', 'u5', 'u6', 'u7', 'u8'].map((username) => ({
      username,
      display_name: '',
      avatar: null,
      trust_level: 0,
    }));
    vi.mocked(messageService.fetchConversation).mockResolvedValue({
      ...ownedGroup,
      participants: [...ownedGroup.participants, ...extras],
      participant_count: 8,
    });
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    await openMembersPanel(8);

    const input = screen.getByLabelText('Add member');
    expect(input).toHaveAttribute('aria-disabled', 'true');
    expect(input).toHaveAttribute('readonly');
    expect(input).toHaveAccessibleDescription('This group is full (8 members).');
    await userEvent.click(input);
    expect(input).toHaveFocus();
    await userEvent.type(input, 'u9');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(messageService.addParticipant).not.toHaveBeenCalled();
  });

  it('a failed add lands the server’s message in the notice region and keeps the typed name', async () => {
    vi.mocked(messageService.fetchConversation).mockResolvedValue(ownedGroup);
    vi.mocked(messageService.addParticipant).mockRejectedValue(
      new ForumApiError('One of the members cannot be added.', 400)
    );
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    await openMembersPanel(3);
    const region = document.querySelector('[aria-live="polite"][aria-atomic="true"]');
    expect(region).toBeEmptyDOMElement();

    await userEvent.type(screen.getByLabelText('Add member'), 'ghost');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));

    expect(await screen.findByText('One of the members cannot be added.')).toBeInTheDocument();
    expect(region).toHaveTextContent('One of the members cannot be added.');
    expect(screen.getByLabelText('Add member')).toHaveValue('ghost');
    expect(screen.getByRole('button', { name: 'Add' })).toBeEnabled();
  });

  it('Leave group confirms, DELETEs the viewer, announces, and returns to the inbox', async () => {
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    await openMembersPanel(3);
    await userEvent.click(screen.getByRole('button', { name: 'Leave group' }));

    const dialog = screen.getByRole('dialog', { name: 'Leave this group?' });
    expect(messageService.removeParticipant).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Leave' }));

    expect(messageService.removeParticipant).toHaveBeenCalledWith(12, 'me');
    expect(await screen.findByText('inbox stub')).toBeInTheDocument();
    expect(announceMock).toHaveBeenCalledWith('You left Seed swap committee.', 'polite');
  });

  it('cancelling the Leave dialog leaves the group alone', async () => {
    renderGroupPage();
    await screen.findByRole('heading', { name: 'Seed swap committee' });
    await openMembersPanel(3);
    await userEvent.click(screen.getByRole('button', { name: 'Leave group' }));
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' })
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(messageService.removeParticipant).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Seed swap committee' })).toBeInTheDocument();
  });

  it('a group with no inbox row (removed, never a member, bad id) shows the unavailable state', async () => {
    vi.mocked(messageService.fetchConversation).mockResolvedValue(null);
    renderGroupPage();

    expect(await screen.findByText(/This group isn't available/)).toBeInTheDocument();
    expect(messageService.fetchMessages).not.toHaveBeenCalled();
    expect(screen.queryByPlaceholderText(/^Message /)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '← Back to messages' })).toHaveAttribute(
      'href',
      '/messages'
    );
  });

  it('a non-numeric id never hits the resolver', async () => {
    renderGroupPage('nope');
    expect(await screen.findByText(/This group isn't available/)).toBeInTheDocument();
    expect(messageService.fetchConversation).not.toHaveBeenCalled();
  });
});
