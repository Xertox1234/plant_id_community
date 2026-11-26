/**
 * ConversationPage write safety: the compose action's Idempotency-Key (audit
 * F144), a stale-CSRF 403 that is not a "blocked" refusal (F143), and the
 * composer reset on an account swap (F88). Its own file because the swap test
 * needs a mutable `useAuth`, which the main test file mocks as a constant.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
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
const auth = vi.hoisted(() => ({
  user: { id: 1, username: 'me' } as { id: number; username: string },
}));
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, user: auth.user }),
}));
// Stable across renders: `refresh` is a dependency of the page's load().
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
  last_message: null,
} as unknown as Conversation;

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

const page = (results: DirectMessage[]) => ({ results, next: null, previous: null });

function ui() {
  return (
    <MemoryRouter initialEntries={['/messages/ada']}>
      <Routes>
        <Route path="/messages/:username" element={<ConversationPage />} />
      </Routes>
    </MemoryRouter>
  );
}

const composer = () => screen.findByPlaceholderText('Message Ada L.…');
const keyOfCall = (n: number) => vi.mocked(messageService.sendMessage).mock.calls[n][2];

beforeEach(() => {
  auth.user = { id: 1, username: 'me' };
  vi.mocked(messageService.fetchConversationWith).mockResolvedValue(conversation);
  vi.mocked(messageService.fetchMessages).mockResolvedValue(page([]));
  vi.mocked(messageService.reportMessage).mockResolvedValue(undefined);
});

describe('DM send Idempotency-Key (F144)', () => {
  it('a retry of the same text reuses the key; a success rotates it', async () => {
    vi.mocked(messageService.sendMessage)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(makeMessage({ id: 90, sender: me, body: 'hi' }))
      .mockResolvedValueOnce(makeMessage({ id: 91, sender: me, body: 'hi' }));
    render(ui());
    const box = await composer();
    await userEvent.type(box, 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Failed to fetch');
    // The lost response: the same draft goes again.
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(box).toHaveValue(''));
    // The same words, sent on purpose a second time, are a NEW message.
    await userEvent.type(box, 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(messageService.sendMessage).toHaveBeenCalledTimes(3));

    expect(typeof keyOfCall(0)).toBe('string');
    expect(keyOfCall(0)).not.toBe('');
    expect(keyOfCall(1)).toBe(keyOfCall(0));
    expect(keyOfCall(2)).not.toBe(keyOfCall(0));
  });

  it('editing the text after a failure sends a new key', async () => {
    vi.mocked(messageService.sendMessage)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(makeMessage({ id: 90, sender: me, body: 'hi!' }));
    render(ui());
    const box = await composer();
    await userEvent.type(box, 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Failed to fetch');
    await userEvent.type(box, '!');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(messageService.sendMessage).toHaveBeenCalledTimes(2));

    expect(typeof keyOfCall(1)).toBe('string');
    expect(keyOfCall(1)).not.toBe(keyOfCall(0));
  });
});

describe('a CSRF 403 is not a block (F143)', () => {
  it('a stale-token 403 that survived the retry does not say the member cannot be messaged', async () => {
    vi.mocked(messageService.sendMessage).mockRejectedValue(
      new ForumApiError('CSRF Failed: CSRF token incorrect.', 403)
    );
    render(ui());
    await userEvent.type(await composer(), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    await screen.findByText(/reload the page/i);
    expect(screen.queryByText("You can't message this member.")).not.toBeInTheDocument();
  });

  it('a blocked 403 still shows the blocked notice', async () => {
    vi.mocked(messageService.sendMessage).mockRejectedValue(
      new ForumApiError('You cannot message this user.', 403)
    );
    render(ui());
    await userEvent.type(await composer(), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText("You can't message this member.")).toBeInTheDocument();
  });
});

describe('account swap (F88)', () => {
  it('drops the previous account’s unsent draft and report state', async () => {
    vi.mocked(messageService.fetchMessages).mockResolvedValue(
      page([makeMessage({ id: 5, body: 'from ada' })])
    );
    const { rerender } = render(ui());
    const box = await composer();
    await userEvent.type(box, 'private words');
    // Report a message: the "Reported" mark is this account's state.
    const item = screen
      .getAllByRole('listitem')
      .find((li) => li.textContent?.includes('from ada'))!;
    await userEvent.click(within(item).getByRole('button', { name: /report/i }));
    await userEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await screen.findByText('Reported');

    // Another account signs in in another tab; focus revalidation swaps it.
    auth.user = { id: 2, username: 'other' };
    rerender(ui());

    await waitFor(() => expect(screen.getByPlaceholderText('Message Ada L.…')).toHaveValue(''));
    await screen.findByText('from ada');
    expect(screen.queryByText('Reported')).not.toBeInTheDocument();
  });

  it('a send after the swap does not reuse the previous account’s key', async () => {
    vi.mocked(messageService.sendMessage)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(makeMessage({ id: 90, sender: me, body: 'hi' }));
    const { rerender } = render(ui());
    await userEvent.type(await composer(), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Failed to fetch');

    auth.user = { id: 2, username: 'other' };
    rerender(ui());
    await waitFor(() => expect(screen.getByPlaceholderText('Message Ada L.…')).toHaveValue(''));
    await userEvent.type(screen.getByPlaceholderText('Message Ada L.…'), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(messageService.sendMessage).toHaveBeenCalledTimes(2));

    expect(typeof keyOfCall(1)).toBe('string');
    expect(keyOfCall(1)).not.toBe(keyOfCall(0));
  });
});
