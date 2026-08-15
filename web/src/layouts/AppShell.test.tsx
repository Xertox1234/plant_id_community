import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import AppShell from './AppShell';
import RailSlot, { RAIL_MEDIA_QUERY } from '../components/layout/RailSlot';
import * as notificationService from '../services/notificationService';

const mockAuth = {
  isAuthenticated: false,
  user: null as { username?: string } | null,
  logout: vi.fn(),
};
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => mockAuth }));
vi.mock('../services/notificationService', () => ({
  fetchUnreadCount: vi.fn(),
  fetchNotifications: vi.fn(),
  markNotificationsRead: vi.fn(),
}));
vi.mock('../components/layout/NotificationBell', () => ({
  default: () => <div data-testid="notification-bell" />,
}));
vi.mock('../components/layout/UserMenu', () => ({
  default: () => <div data-testid="user-menu" />,
}));
// AppShell's own wiring (open state + keyboard shortcut + pill) is under
// test here; CommandPalette's internals (search, keyboard nav, sections)
// have their own dedicated suite in CommandPalette.test.tsx.
vi.mock('../components/CommandPalette', () => ({
  default: ({ open }: { open: boolean }) =>
    open ? <div role="dialog" aria-label="Search" data-testid="command-palette" /> : null,
}));

const renderShell = (children: React.ReactNode = <p>page body</p>) =>
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AppShell>{children}</AppShell>
      </MemoryRouter>
    </ThemeProvider>
  );

beforeEach(() => {
  mockAuth.isAuthenticated = false;
  mockAuth.logout = vi.fn();
  localStorage.clear();
  delete document.documentElement.dataset.mode;
  vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(0);
  vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
    results: [],
    next: null,
    previous: null,
  });
  vi.mocked(notificationService.markNotificationsRead).mockResolvedValue(0);
});

describe('AppShell', () => {
  it('renders brand, nav, search, and the page body', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Houseplant MD home' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /search plants, posts, people/i })
    ).toBeInTheDocument();
    expect(screen.getByText('page body')).toBeInTheDocument();
    expect(document.getElementById('main-content')).not.toBeNull();
  });
  it('shows Sign up and Log in when logged out', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Sign up' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument();
  });
  it('RailSlot portals page content into the rail', () => {
    // RailSlot mounts its children only when the xl rail query matches — the
    // global setup.ts polyfill always reports false, so stub matchMedia
    // (defined writable there) for the wide-viewport behavior, then restore.
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query === RAIL_MEDIA_QUERY,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    try {
      renderShell(
        <RailSlot>
          <p>rail content</p>
        </RailSlot>
      );
      const rail = document.getElementById('app-rail');
      expect(rail).not.toBeNull();
      expect(rail).toHaveTextContent('rail content');
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('RailSlot mounts nothing below the xl breakpoint', () => {
    // Default polyfill: every query reports false → the hidden rail's
    // children (and their data fetches) must not mount at all.
    renderShell(
      <RailSlot>
        <p>rail content</p>
      </RailSlot>
    );
    expect(document.getElementById('app-rail')).not.toHaveTextContent('rail content');
  });

  it('drawer opens and closes', async () => {
    renderShell();
    const trigger = screen.getByRole('button', { name: 'Open menu' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(2);

    await userEvent.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1);
  });

  it('drawer closes on nav item click', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const [, drawerNav] = screen.getAllByRole('navigation', { name: 'Main' });
    await userEvent.click(within(drawerNav).getByRole('link', { name: 'Blog' }));

    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1);
  });

  it('theme toggle flips mode', async () => {
    renderShell();
    const toggle = screen.getByRole('button', { name: /switch to light mode/i });
    expect(toggle).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(toggle);
    const flipped = screen.getByRole('button', { name: /switch to dark mode/i });
    expect(flipped).toHaveAttribute('aria-pressed', 'false');
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });

  it('renders authenticated topbar', () => {
    mockAuth.isAuthenticated = true;
    renderShell();
    expect(screen.getByTestId('notification-bell')).toBeInTheDocument();
    expect(screen.getByTestId('user-menu')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign up' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
  });

  it('wires the logout button to AuthContext logout', async () => {
    mockAuth.isAuthenticated = true;
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: /log out/i }));
    expect(mockAuth.logout).toHaveBeenCalledTimes(1);
  });

  it('Escape closes the open drawer', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
  });

  it('clicking the drawer brand link closes the drawer', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    await userEvent.click(within(dialog).getByRole('link', { name: 'Houseplant MD home' }));

    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
  });

  it('open drawer has dialog role with aria-modal', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('locks body scroll while the drawer is open and restores it after close', async () => {
    renderShell();
    expect(document.body.style.overflow).toBe('');

    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(document.body.style.overflow).toBe('hidden');

    await userEvent.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(document.body.style.overflow).toBe('');
  });

  it('shows the unread count badge on the Forum nav item', async () => {
    mockAuth.isAuthenticated = true;
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(3);
    renderShell();
    const forumLinks = await screen.findAllByRole('link', { name: /Forum/ });
    expect(forumLinks.length).toBeGreaterThan(0);
    expect(within(forumLinks[0]).getByText('3')).toBeInTheDocument();
  });

  it('Ctrl+K opens the command palette', () => {
    renderShell();
    expect(screen.queryByTestId('command-palette')).not.toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });

    expect(screen.getByTestId('command-palette')).toBeInTheDocument();
  });

  it('clicking the search pill opens the command palette', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: /search plants, posts, people/i }));

    expect(screen.getByTestId('command-palette')).toBeInTheDocument();
  });
});
