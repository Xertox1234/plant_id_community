import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import MessagesPage from './MessagesPage';
import * as messageService from '../../services/messageService';
import type { Conversation } from '../../types/forum';

vi.mock('../../services/messageService');
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, user: { id: 1, username: 'me' } }),
}));

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 7,
    other_participant: { username: 'ada', display_name: 'Ada L.', avatar: null, trust_level: 2 },
    created_at: '2026-09-01T00:00:00Z',
    last_message_at: '2026-09-02T00:00:00Z',
    unread_count: 0,
    last_message: {
      body: 'See you at the swap',
      is_mine: false,
      created_at: '2026-09-02T00:00:00Z',
    },
    ...overrides,
  };
}

const page = (results: Conversation[], next: string | null = null) => ({
  results,
  next,
  previous: null,
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/messages']}>
      <MessagesPage />
    </MemoryRouter>
  );
}

describe('MessagesPage (todo 339)', () => {
  beforeEach(() => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(page([]));
  });

  it('shows a loading status, then one linked row per conversation with name, preview and time', async () => {
    vi.mocked(messageService.fetchConversations).mockResolvedValue(
      page([
        makeConversation(),
        makeConversation({
          id: 8,
          other_participant: { username: 'grace', display_name: '', avatar: null, trust_level: 0 },
          last_message: { body: 'Thanks!', is_mine: true, created_at: '2026-09-01T00:00:00Z' },
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
