import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { UnreadNotificationsProvider, useUnreadNotifications } from './UnreadNotificationsContext';

const mockFetchUnreadCount = vi.fn();
vi.mock('../services/notificationService', () => ({
  fetchUnreadCount: (...args: unknown[]) => mockFetchUnreadCount(...args),
}));
const mockFetchUnreadConversationCount = vi.fn();
vi.mock('../services/messageService', () => ({
  fetchUnreadConversationCount: (...args: unknown[]) => mockFetchUnreadConversationCount(...args),
}));

let mockIsAuthenticated = true;
vi.mock('./AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

function Probe() {
  const { unreadCount, unreadConversations, refresh, decrement, clear } = useUnreadNotifications();
  return (
    <div>
      <span data-testid="count">{unreadCount}</span>
      <span data-testid="conversations">{unreadConversations}</span>
      <button onClick={refresh}>refresh</button>
      <button onClick={decrement}>dec</button>
      <button onClick={clear}>clear</button>
    </div>
  );
}

describe('UnreadNotificationsContext', () => {
  beforeEach(() => {
    mockFetchUnreadCount.mockReset();
    mockFetchUnreadConversationCount.mockReset();
    mockFetchUnreadConversationCount.mockResolvedValue(0);
    mockIsAuthenticated = true;
  });

  it('polls the unread count when authenticated', async () => {
    mockFetchUnreadCount.mockResolvedValue(4);
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('4'));
    expect(mockFetchUnreadCount).toHaveBeenCalled();
  });

  it('does not fetch and reports 0 when unauthenticated', async () => {
    mockIsAuthenticated = false;
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    expect(screen.getByTestId('count')).toHaveTextContent('0');
    expect(screen.getByTestId('conversations')).toHaveTextContent('0');
    expect(mockFetchUnreadCount).not.toHaveBeenCalled();
    expect(mockFetchUnreadConversationCount).not.toHaveBeenCalled();
  });

  it('polls the DM unread count in the SAME tick as notifications (todo 339)', async () => {
    vi.useFakeTimers();
    try {
      mockFetchUnreadCount.mockResolvedValue(2);
      mockFetchUnreadConversationCount.mockResolvedValue(5);
      render(
        <UnreadNotificationsProvider>
          <Probe />
        </UnreadNotificationsProvider>
      );
      await vi.waitFor(() => expect(screen.getByTestId('conversations')).toHaveTextContent('5'));
      expect(screen.getByTestId('count')).toHaveTextContent('2');
      expect(mockFetchUnreadCount).toHaveBeenCalledTimes(1);
      expect(mockFetchUnreadConversationCount).toHaveBeenCalledTimes(1);

      // One interval → exactly one more request on EACH endpoint, no second stream.
      await vi.advanceTimersByTimeAsync(30_000);
      expect(mockFetchUnreadCount).toHaveBeenCalledTimes(2);
      expect(mockFetchUnreadConversationCount).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('a failing DM count leaves the notification badge intact, and vice versa', async () => {
    mockFetchUnreadCount.mockResolvedValue(3);
    mockFetchUnreadConversationCount.mockRejectedValue(new Error('HTTP 500'));
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('3'));
    expect(screen.getByTestId('conversations')).toHaveTextContent('0');

    // Next refresh: notifications fail, DMs succeed — the DM badge still lands
    // and the notification count is kept, not blanked.
    mockFetchUnreadCount.mockRejectedValue(new Error('HTTP 500'));
    mockFetchUnreadConversationCount.mockResolvedValue(4);
    act(() => screen.getByText('refresh').click());
    await waitFor(() => expect(screen.getByTestId('conversations')).toHaveTextContent('4'));
    expect(screen.getByTestId('count')).toHaveTextContent('3');
  });

  it('logging out zeroes the DM count and discards an in-flight poll', async () => {
    let resolveInFlight: (count: number) => void = () => {};
    mockFetchUnreadCount.mockResolvedValue(1);
    mockFetchUnreadConversationCount
      .mockResolvedValueOnce(2)
      .mockImplementationOnce(() => new Promise<number>((resolve) => (resolveInFlight = resolve)));
    const { rerender } = render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('conversations')).toHaveTextContent('2'));

    act(() => screen.getByText('refresh').click()); // poll now in flight
    mockIsAuthenticated = false;
    rerender(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    expect(screen.getByTestId('conversations')).toHaveTextContent('0');

    await act(async () => resolveInFlight(9)); // stale response lands
    expect(screen.getByTestId('conversations')).toHaveTextContent('0');
  });

  it('decrement floors at 0 and clear resets', async () => {
    mockFetchUnreadCount.mockResolvedValue(1);
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));
    act(() => screen.getByText('dec').click());
    expect(screen.getByTestId('count')).toHaveTextContent('0');
    act(() => screen.getByText('dec').click());
    expect(screen.getByTestId('count')).toHaveTextContent('0');
    act(() => screen.getByText('clear').click());
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });

  it('renders with safe defaults when no provider is mounted', () => {
    render(<Probe />);
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });

  it('an in-flight poll response cannot resurrect a cleared badge', async () => {
    let resolveInFlight: (count: number) => void = () => {};
    mockFetchUnreadCount
      .mockResolvedValueOnce(5)
      .mockImplementationOnce(() => new Promise<number>((resolve) => (resolveInFlight = resolve)));
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('5'));

    act(() => screen.getByText('refresh').click()); // poll now in flight
    act(() => screen.getByText('clear').click()); // user marks all read
    expect(screen.getByTestId('count')).toHaveTextContent('0');

    await act(async () => resolveInFlight(5)); // stale response lands
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });

  it('an in-flight poll response cannot overwrite a decrement', async () => {
    let resolveInFlight: (count: number) => void = () => {};
    mockFetchUnreadCount
      .mockResolvedValueOnce(5)
      .mockImplementationOnce(() => new Promise<number>((resolve) => (resolveInFlight = resolve)));
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('5'));

    act(() => screen.getByText('refresh').click());
    act(() => screen.getByText('dec').click());
    expect(screen.getByTestId('count')).toHaveTextContent('4');

    await act(async () => resolveInFlight(5));
    expect(screen.getByTestId('count')).toHaveTextContent('4');
  });
});
