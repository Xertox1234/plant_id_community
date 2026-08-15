import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import AppShell from './AppShell';
import RailSlot from '../components/layout/RailSlot';

const mockAuth = {
  isAuthenticated: false,
  user: null as { username?: string } | null,
  logout: vi.fn(),
};
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => mockAuth }));
vi.mock('../components/layout/NotificationBell', () => ({
  default: () => <div data-testid="notification-bell" />,
}));
vi.mock('../components/layout/UserMenu', () => ({
  default: () => <div data-testid="user-menu" />,
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
});

describe('AppShell', () => {
  it('renders brand, nav, search, and the page body', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Houseplant MD home' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /search plants, posts, people/i })).toBeInTheDocument();
    expect(screen.getByText('page body')).toBeInTheDocument();
    expect(document.getElementById('main-content')).not.toBeNull();
  });
  it('shows Sign up and Log in when logged out', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Sign up' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument();
  });
  it('RailSlot portals page content into the rail', () => {
    renderShell(
      <RailSlot>
        <p>rail content</p>
      </RailSlot>
    );
    const rail = document.getElementById('app-rail');
    expect(rail).not.toBeNull();
    expect(rail).toHaveTextContent('rail content');
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
});
