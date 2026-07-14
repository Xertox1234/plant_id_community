import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import NotificationBell from './NotificationBell';
import * as notificationService from '../../services/notificationService';
import type { ForumNotification } from '../../types/notifications';

vi.mock('../../services/notificationService');

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderBell() {
  return render(
    <MemoryRouter>
      <NotificationBell />
    </MemoryRouter>
  );
}

function makeNotification(overrides: Partial<ForumNotification> = {}): ForumNotification {
  return {
    id: 1,
    verb: 'reply',
    actor: { username: 'ada', display_name: 'Ada', trust_level: 0 },
    topic: {
      id: 10,
      slug: 'watering-tips',
      title: 'Watering Tips',
      board_id: 3,
      board_slug: 'plant-care',
    },
    created_at: '2026-07-14T00:00:00Z',
    read_at: null,
    ...overrides,
  };
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(0);
    vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
      results: [],
      next: null,
      previous: null,
    });
    vi.mocked(notificationService.markNotificationsRead).mockResolvedValue(0);
  });

  it('renders no badge when unread count is zero', async () => {
    renderBell();
    await waitFor(() => {
      expect(notificationService.fetchUnreadCount).toHaveBeenCalled();
    });
    expect(screen.queryByTestId('notification-badge')).not.toBeInTheDocument();
  });

  it('renders the unread count badge', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(3);
    renderBell();
    expect(await screen.findByTestId('notification-badge')).toHaveTextContent('3');
  });

  it('caps the badge display at "9+"', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(42);
    renderBell();
    expect(await screen.findByTestId('notification-badge')).toHaveTextContent('9+');
  });

  it('polls unread count on an interval', async () => {
    vi.useFakeTimers();
    try {
      renderBell();
      await vi.waitFor(() => {
        expect(notificationService.fetchUnreadCount).toHaveBeenCalledTimes(1);
      });
      await vi.advanceTimersByTimeAsync(30_000);
      expect(notificationService.fetchUnreadCount).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('loads and displays notifications when opened', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(1);
    vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
      results: [makeNotification()],
      next: null,
      previous: null,
    });
    renderBell();

    await userEvent.click(await screen.findByLabelText(/notifications/i));

    expect(await screen.findByText('Ada replied to "Watering Tips"')).toBeInTheDocument();
  });

  it('shows an empty state when there are no notifications', async () => {
    renderBell();

    await userEvent.click(await screen.findByLabelText(/notifications/i));

    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument();
  });

  it('renders "[deleted]" when a notification has no actor', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(1);
    vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
      results: [makeNotification({ actor: null })],
      next: null,
      previous: null,
    });
    renderBell();

    await userEvent.click(await screen.findByLabelText(/notifications/i));

    expect(await screen.findByText('Someone replied to "Watering Tips"')).toBeInTheDocument();
  });

  it('mark all read clears the unread badge and marks rows read', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(1);
    vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
      results: [makeNotification()],
      next: null,
      previous: null,
    });
    vi.mocked(notificationService.markNotificationsRead).mockResolvedValue(1);
    renderBell();

    await userEvent.click(await screen.findByLabelText(/notifications/i));
    await screen.findByText('Ada replied to "Watering Tips"');

    await userEvent.click(screen.getByText('Mark all read'));

    expect(notificationService.markNotificationsRead).toHaveBeenCalledWith();
    await waitFor(() => {
      expect(screen.queryByTestId('notification-badge')).not.toBeInTheDocument();
    });
  });

  it('clicking a notification marks it read, clears the badge, and navigates to the topic', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(1);
    vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
      results: [makeNotification()],
      next: null,
      previous: null,
    });
    renderBell();

    await userEvent.click(await screen.findByLabelText(/notifications/i));
    await userEvent.click(await screen.findByText('Ada replied to "Watering Tips"'));

    expect(notificationService.markNotificationsRead).toHaveBeenCalledWith([1]);
    expect(mockNavigate).toHaveBeenCalledWith('/forum/3-plant-care/10-watering-tips');
    await waitFor(() => {
      expect(screen.queryByTestId('notification-badge')).not.toBeInTheDocument();
    });
  });

  it('does not mark an already-read notification read again on click', async () => {
    vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
      results: [makeNotification({ read_at: '2026-07-14T01:00:00Z' })],
      next: null,
      previous: null,
    });
    renderBell();

    await userEvent.click(await screen.findByLabelText(/notifications/i));
    await userEvent.click(await screen.findByText('Ada replied to "Watering Tips"'));

    expect(notificationService.markNotificationsRead).not.toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith('/forum/3-plant-care/10-watering-tips');
  });
});
