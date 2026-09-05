import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MessagesLink from './MessagesLink';
import { UnreadNotificationsProvider } from '../../contexts/UnreadNotificationsContext';
import * as notificationService from '../../services/notificationService';
import * as messageService from '../../services/messageService';

vi.mock('../../services/notificationService');
vi.mock('../../services/messageService');
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

function renderLink() {
  return render(
    <MemoryRouter>
      <UnreadNotificationsProvider>
        <MessagesLink />
      </UnreadNotificationsProvider>
    </MemoryRouter>
  );
}

describe('MessagesLink', () => {
  beforeEach(() => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(0);
    vi.mocked(messageService.fetchUnreadConversationCount).mockResolvedValue(0);
  });

  it('links to the inbox with no badge when nothing is unread', async () => {
    renderLink();
    const link = await screen.findByRole('link', { name: 'Messages' });
    expect(link).toHaveAttribute('href', '/messages');
    expect(screen.queryByTestId('messages-badge')).not.toBeInTheDocument();
  });

  it('shows the unread-conversation badge and says so in the label', async () => {
    vi.mocked(messageService.fetchUnreadConversationCount).mockResolvedValue(3);
    renderLink();
    expect(await screen.findByTestId('messages-badge')).toHaveTextContent('3');
    expect(screen.getByRole('link', { name: 'Messages (3 unread)' })).toBeInTheDocument();
  });

  it('caps the badge at "9+" and ignores the NOTIFICATION count', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(7);
    vi.mocked(messageService.fetchUnreadConversationCount).mockResolvedValue(12);
    renderLink();
    expect(await screen.findByTestId('messages-badge')).toHaveTextContent('9+');
    expect(screen.getByRole('link', { name: 'Messages (12 unread)' })).toBeInTheDocument();
  });

  it('shows no badge when only notifications are unread', async () => {
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(4);
    renderLink();
    await screen.findByRole('link', { name: 'Messages' });
    expect(screen.queryByTestId('messages-badge')).not.toBeInTheDocument();
  });
});
