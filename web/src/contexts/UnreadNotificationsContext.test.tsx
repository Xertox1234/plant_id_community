import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { UnreadNotificationsProvider, useUnreadNotifications } from './UnreadNotificationsContext';

const mockFetchUnreadCount = vi.fn();
vi.mock('../services/notificationService', () => ({
  fetchUnreadCount: (...args: unknown[]) => mockFetchUnreadCount(...args),
}));

let mockIsAuthenticated = true;
vi.mock('./AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

function Probe() {
  const { unreadCount, refresh, decrement, clear } = useUnreadNotifications();
  return (
    <div>
      <span data-testid="count">{unreadCount}</span>
      <button onClick={refresh}>refresh</button>
      <button onClick={decrement}>dec</button>
      <button onClick={clear}>clear</button>
    </div>
  );
}

describe('UnreadNotificationsContext', () => {
  beforeEach(() => {
    mockFetchUnreadCount.mockReset();
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
    expect(mockFetchUnreadCount).not.toHaveBeenCalled();
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
