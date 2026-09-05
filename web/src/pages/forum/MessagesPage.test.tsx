import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import MessagesPage from './MessagesPage';
import * as messageService from '../../services/messageService';
import * as forumService from '../../services/forumService';
import { ForumApiError } from '../../services/forumService';
import type { Conversation, ForumAuthor } from '../../types/forum';

vi.mock('../../services/messageService');
// The New group form's member picker searches through forumService; keep the
// real ForumApiError so status branching in the form is exercised for real.
vi.mock('../../services/forumService', async () => {
  const actual = await vi.importActual<typeof import('../../services/forumService')>(
    '../../services/forumService'
  );
  return { ...actual, searchForumUsers: vi.fn() };
});
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, user: { id: 1, username: 'me' } }),
}));

const me: ForumAuthor = { username: 'me', display_name: 'Me', avatar: null, trust_level: 1 };
const ada: ForumAuthor = { username: 'ada', display_name: 'Ada L.', avatar: null, trust_level: 2 };
const grace: ForumAuthor = { username: 'grace', display_name: '', avatar: null, trust_level: 0 };
const linus: ForumAuthor = {
  username: 'linus',
  display_name: 'Linus',
  avatar: null,
  trust_level: 1,
};
const mary: ForumAuthor = { username: 'mary', display_name: 'Mary', avatar: null, trust_level: 1 };

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
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
    unread_count: 0,
    last_message: {
      body: 'See you at the swap',
      is_mine: false,
      sender: ada,
      created_at: '2026-09-02T00:00:00Z',
    },
    ...overrides,
  };
}

function makeGroup(overrides: Partial<Conversation> = {}): Conversation {
  return makeConversation({
    id: 12,
    kind: 'group',
    title: 'Seed swap committee',
    other_participant: null,
    participants: [me, ada, grace],
    participant_count: 3,
    created_by: me,
    can_manage: true,
    last_message: {
      body: 'Bring seeds',
      is_mine: false,
      sender: ada,
      created_at: '2026-09-02T00:00:00Z',
    },
    ...overrides,
  });
}

const page = (results: Conversation[], next: string | null = null) => ({
  results,
  next,
  previous: null,
});

function GroupPageStub() {
  const { id } = useParams<{ id: string }>();
  return <p>group page {id}</p>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/messages']}>
      <Routes>
        <Route path="/messages" element={<MessagesPage />} />
        <Route path="/messages/group/:id" element={<GroupPageStub />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('MessagesPage (todo 339)', () => {
  beforeEach(() => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(page([]));
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([]);
  });

  it('shows a loading status, then one linked row per conversation with name, preview and time', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([
        makeConversation(),
        makeConversation({
          id: 8,
          other_participant: { username: 'grace', display_name: '', avatar: null, trust_level: 0 },
          last_message: {
            body: 'Thanks!',
            is_mine: true,
            sender: me,
            created_at: '2026-09-01T00:00:00Z',
          },
        }),
      ])
    );
    renderPage();
    expect(screen.getByRole('status', { name: 'Loading messages…' })).toBeInTheDocument();

    const list = await screen.findByRole('list', { name: 'Conversations' });
    const rows = within(list).getAllByRole('link');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute('href', '/messages/ada');
    expect(rows[0]).toHaveTextContent('Ada L.');
    expect(rows[0]).toHaveTextContent('See you at the swap');
    expect(rows[0]).not.toHaveTextContent('You:');
    expect(within(rows[0]).getByText(/ago/)).toBeInTheDocument();
    // No display name → the username; own last message → "You: " prefix.
    expect(rows[1]).toHaveAttribute('href', '/messages/grace');
    expect(rows[1]).toHaveTextContent('grace');
    expect(rows[1]).toHaveTextContent('You: Thanks!');
    expect(rows[1]).toHaveAttribute('data-kind', 'direct');
    expect(messageService.fetchConversations).toHaveBeenCalledWith();
  });

  it('marks unread rows: count badge, bold name, and the count in the accessible name', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([makeConversation({ unread_count: 3 }), makeConversation({ id: 9, unread_count: 0 })])
    );
    renderPage();
    const unreadRow = await screen.findByRole('link', { name: 'Ada L. (3 unread)' });
    expect(unreadRow).toHaveAttribute('data-unread', 'true');
    expect(within(unreadRow).getByText('3')).toBeInTheDocument();
    expect(within(unreadRow).getByText('Ada L.')).toHaveClass('font-semibold');

    const readRow = screen.getByRole('link', { name: 'Ada L.' });
    expect(readRow).not.toHaveAttribute('data-unread');
    expect(within(readRow).getByText('Ada L.')).not.toHaveClass('font-semibold');
  });

  it('shows the empty state when there are no conversations', async () => {
    renderPage();
    expect(await screen.findByText('No messages yet.')).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Conversations' })).not.toBeInTheDocument();
  });

  it('offers Load more only while a next cursor exists, and appends the next page', async () => {
    const cursor = 'http://localhost:8000/api/v1/forum/conversations/?cursor=abc';
    vi.mocked(messageService.fetchConversations)
      .mockResolvedValueOnce(page([makeConversation()], cursor))
      .mockResolvedValueOnce(
        page([
          makeConversation({
            id: 8,
            other_participant: {
              username: 'grace',
              display_name: 'Grace',
              avatar: null,
              trust_level: 0,
            },
          }),
        ])
      );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Load more' }));

    expect(messageService.fetchConversations).toHaveBeenLastCalledWith(cursor);
    const list = await screen.findByRole('list', { name: 'Conversations' });
    expect(within(list).getAllByRole('link')).toHaveLength(2);
    expect(within(list).getAllByRole('link')[1]).toHaveTextContent('Grace');
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });

  it('shows the error with a working Retry', async () => {
    vi.mocked(messageService.fetchConversations)
      .mockRejectedValueOnce(new Error('HTTP 500'))
      .mockResolvedValueOnce(page([makeConversation()]));
    renderPage();

    expect(await screen.findByText('HTTP 500')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByRole('link', { name: 'Ada L.' })).toBeInTheDocument();
    expect(screen.queryByText('HTTP 500')).not.toBeInTheDocument();
    expect(messageService.fetchConversations).toHaveBeenCalledTimes(2);
  });

  it('a Load more failure lands in the live region and keeps the loaded rows', async () => {
    vi.mocked(messageService.fetchConversations)
      .mockResolvedValueOnce(page([makeConversation()], 'http://x/cursor'))
      .mockRejectedValueOnce(new Error('HTTP 502'));
    renderPage();

    const loadMore = await screen.findByRole('button', { name: 'Load more' });
    // Persistent live region: present and EMPTY before the failure — a
    // conditionally mounted alert would pass the after-the-fact check too.
    const region = document.querySelector('[aria-live="polite"]');
    expect(region).not.toBeNull();
    expect(region).toHaveTextContent('');
    await userEvent.click(loadMore);

    expect(await screen.findByText('HTTP 502')).toBeInTheDocument();
    expect(document.querySelector('[aria-live="polite"]')).toBe(region);
    expect(screen.getByRole('link', { name: 'Ada L.' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeEnabled();
  });
});

describe('MessagesPage groups (todo 350)', () => {
  beforeEach(() => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(page([]));
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([]);
  });

  it('renders a group whose last sender has left, and never reads through the null sender', async () => {
    // `last_message.sender` is null once that member leaves the group — an
    // unguarded read here used to crash the whole inbox (react review).
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([
        makeGroup({
          last_message: {
            body: 'Bring seeds',
            is_mine: false,
            sender: null,
            created_at: '2026-09-02T00:00:00Z',
          },
        }),
      ])
    );
    renderPage();

    const row = await screen.findByRole('link', { name: 'Seed swap committee (group of 3)' });
    expect(row).toHaveTextContent('Former member: Bring seeds');
  });

  it('degrades a direct row with no other participant on its own terms — no group link, no crash', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([makeConversation({ other_participant: null })])
    );
    renderPage();

    const row = await screen.findByLabelText('Unavailable conversation');
    expect(row).toHaveTextContent('See you at the swap');
    expect(row.tagName).toBe('DIV'); // not a Link, and never the group path
    expect(screen.queryByRole('link', { name: /group of/ })).not.toBeInTheDocument();
  });

  it('returns focus to the New group toggle when the form is cancelled', async () => {
    renderPage();
    const toggle = await screen.findByRole('button', { name: 'New group' });
    await userEvent.click(toggle);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('form', { name: 'New group' })).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it('renders a group row: title, a three-avatar stack with +N (the viewer left out), a sender-prefixed preview, and the group link', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([
        makeGroup({ participants: [me, ada, grace, linus, mary], participant_count: 5 }),
        makeConversation(),
      ])
    );
    renderPage();

    const row = await screen.findByRole('link', { name: 'Seed swap committee (group of 5)' });
    expect(row).toHaveAttribute('href', '/messages/group/12');
    expect(row).toHaveAttribute('data-kind', 'group');
    expect(row).toHaveTextContent('Seed swap committee');
    expect(row).toHaveTextContent('Ada L.: Bring seeds');
    // Four others: three avatars shown, the fourth folded into "+1".
    expect(row.querySelectorAll('img')).toHaveLength(3);
    expect(within(row).getByText('+1')).toBeInTheDocument();
    expect(row).not.toHaveAttribute('data-unread');
    // The direct row is untouched by the group rendering.
    const direct = screen.getByRole('link', { name: 'Ada L.' });
    expect(direct).toHaveAttribute('href', '/messages/ada');
    expect(direct).toHaveTextContent('See you at the swap');
    expect(direct).not.toHaveTextContent('Ada L.:');
  });

  it('a group preview the viewer sent reads "You: …", and the unread count joins the accessible name', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([
        makeGroup({
          unread_count: 2,
          last_message: {
            body: 'On my way',
            is_mine: true,
            sender: me,
            created_at: '2026-09-02T00:00:00Z',
          },
        }),
      ])
    );
    renderPage();

    const row = await screen.findByRole('link', {
      name: 'Seed swap committee (group of 3, 2 unread)',
    });
    expect(row).toHaveTextContent('You: On my way');
    expect(row).toHaveAttribute('data-unread', 'true');
    expect(within(row).getByText('2')).toBeInTheDocument();
    // Two others, no fold.
    expect(row.querySelectorAll('img')).toHaveLength(2);
    expect(within(row).queryByText(/^\+\d/)).not.toBeInTheDocument();
  });

  it('a sender without a display name is prefixed by username', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([
        makeGroup({
          last_message: {
            body: 'ok',
            is_mine: false,
            sender: grace,
            created_at: '2026-09-02T00:00:00Z',
          },
        }),
      ])
    );
    renderPage();
    expect(await screen.findByRole('link', { name: /Seed swap committee/ })).toHaveTextContent(
      'grace: ok'
    );
  });

  it('New group: toggles the form, POSTs exactly {title, usernames, body}, and navigates to the new group', async () => {
    vi.mocked(messageService.createGroupConversation).mockResolvedValue(makeGroup());
    renderPage();
    await screen.findByText('No messages yet.');

    const toggle = screen.getByRole('button', { name: 'New group' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('form', { name: 'New group' })).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const form = screen.getByRole('form', { name: 'New group' });
    expect(document.getElementById(toggle.getAttribute('aria-controls') ?? '')).toContainElement(
      form
    );

    await userEvent.type(screen.getByLabelText('Group name'), '  Seed swap committee ');
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}grace,');
    expect(screen.getByRole('button', { name: 'Remove ada' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove grace' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('First message'), '  hello all  ');
    await userEvent.click(screen.getByRole('button', { name: 'Create group' }));

    expect(messageService.createGroupConversation).toHaveBeenCalledTimes(1);
    expect(messageService.createGroupConversation).toHaveBeenCalledWith({
      title: 'Seed swap committee',
      usernames: ['ada', 'grace'],
      body: 'hello all',
    });
    expect(await screen.findByText('group page 12')).toBeInTheDocument();
  });

  it('a 400 on create lands the server’s generic member line in the form’s always-mounted live region and keeps the draft', async () => {
    vi.mocked(messageService.createGroupConversation).mockRejectedValue(
      new ForumApiError('One of the members cannot be added.', 400)
    );
    renderPage();
    await screen.findByText('No messages yet.');
    await userEvent.click(screen.getByRole('button', { name: 'New group' }));
    const form = screen.getByRole('form', { name: 'New group' });
    // The form's own notice region is the last live region in the form (the
    // title Input owns the first); present and EMPTY before the failure.
    const regions = form.querySelectorAll('[aria-live="polite"]');
    const region = regions[regions.length - 1];
    expect(region).toHaveClass('sr-only');
    expect(region).toBeEmptyDOMElement();

    await userEvent.type(screen.getByLabelText('Group name'), 'Seed swap committee');
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}ghost{Enter}');
    await userEvent.type(screen.getByLabelText('First message'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Create group' }));

    expect(await screen.findByText('One of the members cannot be added.')).toBeInTheDocument();
    expect(region).toHaveTextContent('One of the members cannot be added.');
    expect(screen.getByLabelText('Group name')).toHaveValue('Seed swap committee');
    expect(screen.getByRole('button', { name: 'Remove ghost' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create group' })).toBeEnabled();
    expect(screen.queryByText(/group page/)).not.toBeInTheDocument();
  });

  it('a 429 on create reads the Retry-After seconds into the notice, never the envelope text', async () => {
    vi.mocked(messageService.createGroupConversation).mockRejectedValue(
      new ForumApiError('Request was throttled.', 429, 900)
    );
    renderPage();
    await screen.findByText('No messages yet.');
    await userEvent.click(screen.getByRole('button', { name: 'New group' }));
    await userEvent.type(screen.getByLabelText('Group name'), 'Seed swap committee');
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}grace{Enter}');
    await userEvent.type(screen.getByLabelText('First message'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Create group' }));

    expect(
      await screen.findByText("You're creating groups too quickly — try again in 15 minutes.")
    ).toBeInTheDocument();
    expect(screen.queryByText('Request was throttled.')).not.toBeInTheDocument();
  });

  it('a 429 without Retry-After falls back to "later"', async () => {
    vi.mocked(messageService.createGroupConversation).mockRejectedValue(
      new ForumApiError('Request was throttled.', 429)
    );
    renderPage();
    await screen.findByText('No messages yet.');
    await userEvent.click(screen.getByRole('button', { name: 'New group' }));
    await userEvent.type(screen.getByLabelText('Group name'), 'Seed swap committee');
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}grace{Enter}');
    await userEvent.type(screen.getByLabelText('First message'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Create group' }));

    expect(
      await screen.findByText("You're creating groups too quickly — try again later.")
    ).toBeInTheDocument();
  });

  it('the form is disabled while the create is in flight, and Cancel closes it', async () => {
    vi.mocked(messageService.createGroupConversation).mockImplementation(
      () => new Promise(() => {}) // never settles
    );
    renderPage();
    await screen.findByText('No messages yet.');
    await userEvent.click(screen.getByRole('button', { name: 'New group' }));
    await userEvent.type(screen.getByLabelText('Group name'), 'Seed swap committee');
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}grace{Enter}');
    await userEvent.type(screen.getByLabelText('First message'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Create group' }));

    expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled();
    expect(screen.getByLabelText('Group name')).toBeDisabled();
    expect(screen.getByLabelText('First message')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();

    // A fresh form: Cancel closes it and collapses the toggle.
    vi.mocked(messageService.createGroupConversation).mockReset();
    await userEvent.click(screen.getByRole('button', { name: 'New group' }));
    expect(screen.queryByRole('form', { name: 'New group' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'New group' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('form', { name: 'New group' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New group' })).toHaveAttribute(
      'aria-expanded',
      'false'
    );
  });
});
