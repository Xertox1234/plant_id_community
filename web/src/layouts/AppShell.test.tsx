import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import AppShell from './AppShell';
import RailSlot from '../components/layout/RailSlot';

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: false, user: null, logout: vi.fn() }),
}));
vi.mock('../components/layout/NotificationBell', () => ({ default: () => null }));
vi.mock('../components/layout/UserMenu', () => ({ default: () => null }));

const renderShell = (children: React.ReactNode = <p>page body</p>) =>
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AppShell>{children}</AppShell>
      </MemoryRouter>
    </ThemeProvider>
  );

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
});
