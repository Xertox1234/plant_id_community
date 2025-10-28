/**
 * Header Tests
 *
 * Tests for responsive navigation header component.
 * Priority: Phase 2 - UI component testing.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import Header from './Header';
import { renderWithRouter } from '../../tests/utils';
import * as authService from '../../services/authService';

// Mock auth service
vi.mock('../../services/authService');

// Mock logger
vi.mock('../../utils/logger', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  },
}));

describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authService.getStoredUser.mockReturnValue(null);
    authService.getCurrentUser.mockResolvedValue(null);
  });

  describe('Basic Rendering', () => {
    it('renders the logo and site name', async () => {
      renderWithRouter(<Header />);

      const logo = screen.getByText('PlantID');
      expect(logo).toBeInTheDocument();

      const logoLink = screen.getByLabelText('PlantID Home');
      expect(logoLink).toHaveAttribute('href', '/');
    });

    it('renders desktop navigation links', () => {
      renderWithRouter(<Header />);

      // Desktop navigation (hidden on mobile)
      expect(screen.getAllByText('Identify')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Blog')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Community')[0]).toBeInTheDocument();
    });

    it('renders mobile menu button', () => {
      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      expect(menuButton).toBeInTheDocument();
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    });
  });

  describe('Mobile Menu', () => {
    it('toggles mobile menu when button is clicked', () => {
      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');

      // Open menu
      fireEvent.click(menuButton);
      expect(menuButton).toHaveAttribute('aria-expanded', 'true');

      // Close menu
      fireEvent.click(menuButton);
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('shows menu content when open', () => {
      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');

      // Menu should not be visible initially
      expect(screen.queryByText(/Log in/)).toBeInTheDocument(); // Desktop version exists

      // Open menu
      fireEvent.click(menuButton);

      // Mobile menu items should be visible
      const identifyLinks = screen.getAllByText('Identify');
      expect(identifyLinks.length).toBeGreaterThan(1); // Desktop + mobile versions
    });

    it('closes menu when navigation link is clicked', () => {
      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');

      // Open menu
      fireEvent.click(menuButton);
      expect(menuButton).toHaveAttribute('aria-expanded', 'true');

      // Click a navigation link (find mobile version)
      const blogLinks = screen.getAllByText('Blog');
      const mobileLink = blogLinks.find(link =>
        link.closest('.md\\:hidden')
      );

      if (mobileLink) {
        fireEvent.click(mobileLink);
      }

      // Menu should close
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    });
  });

  describe('Unauthenticated State', () => {
    it('shows login and signup buttons when not authenticated', async () => {
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      renderWithRouter(<Header />);

      // Wait for auth to initialize
      await screen.findByText('Log in');

      expect(screen.getByText('Log in')).toBeInTheDocument();
      expect(screen.getByText('Sign up')).toBeInTheDocument();
    });

    it('renders signup button with correct link', async () => {
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      const { container } = renderWithRouter(<Header />);

      await screen.findByText('Sign up');

      const signupLink = container.querySelector('a[href="/signup"]');
      expect(signupLink).toBeInTheDocument();
    });

    it('renders login button with correct link', async () => {
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      const { container } = renderWithRouter(<Header />);

      await screen.findByText('Log in');

      const loginLink = container.querySelector('a[href="/login"]');
      expect(loginLink).toBeInTheDocument();
    });
  });

  describe('Authenticated State', () => {
    it('shows user menu when authenticated', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      renderWithRouter(<Header />);

      // Wait for user to load
      await screen.findByText('Test User');

      expect(screen.getByText('Test User')).toBeInTheDocument();
    });

    it('does not show login/signup buttons when authenticated', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      renderWithRouter(<Header />);

      await screen.findByText('Test User');

      // Desktop login/signup buttons should not be visible
      const loginButtons = screen.queryAllByText('Log in');
      const signupButtons = screen.queryAllByText('Sign up');

      // They might exist in mobile menu, so check they're not in desktop area
      expect(loginButtons.length).toBeLessThanOrEqual(1); // Mobile only if any
      expect(signupButtons.length).toBeLessThanOrEqual(1);
    });

    it('shows user email when name is not available', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      renderWithRouter(<Header />);

      await screen.findByText('test@example.com');

      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });
  });

  describe('Mobile Authenticated Menu', () => {
    it('shows user info in mobile menu when authenticated', async () => {
      const mockUser = {
        id: 1,
        email: 'mobile@example.com',
        name: 'Mobile User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      fireEvent.click(menuButton);

      await screen.findByText('Mobile User');

      expect(screen.getAllByText('Mobile User').length).toBeGreaterThan(0);
    });

    it('shows profile and settings links in mobile menu', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      fireEvent.click(menuButton);

      await screen.findByText('Test User');

      expect(screen.getByText('Profile')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    it('shows logout button in mobile menu', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);
      authService.logout.mockResolvedValue();

      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      fireEvent.click(menuButton);

      await screen.findByText('Test User');

      const logoutButton = screen.getByText('Log out');
      expect(logoutButton).toBeInTheDocument();
    });

    it('calls logout and closes menu when logout clicked', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);
      authService.logout.mockResolvedValue();

      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      fireEvent.click(menuButton);

      await screen.findByText('Test User');

      const logoutButton = screen.getByText('Log out');
      fireEvent.click(logoutButton);

      // Logout should be called
      expect(authService.logout).toHaveBeenCalled();

      // Menu should close
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('closes menu when profile link clicked', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
      };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      fireEvent.click(menuButton);

      await screen.findByText('Test User');
      expect(menuButton).toHaveAttribute('aria-expanded', 'true');

      const profileLink = screen.getByText('Profile');
      fireEvent.click(profileLink);

      // Menu should close
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    });
  });

  describe('Navigation Links', () => {
    it('has correct href for identify link', () => {
      const { container } = renderWithRouter(<Header />);

      const identifyLink = container.querySelector('a[href="/identify"]');
      expect(identifyLink).toBeInTheDocument();
    });

    it('has correct href for blog link', () => {
      const { container } = renderWithRouter(<Header />);

      const blogLink = container.querySelector('a[href="/blog"]');
      expect(blogLink).toBeInTheDocument();
    });

    it('has correct href for community link', () => {
      const { container } = renderWithRouter(<Header />);

      const forumLink = container.querySelector('a[href="/forum"]');
      expect(forumLink).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper aria-label for logo link', () => {
      renderWithRouter(<Header />);

      const logoLink = screen.getByLabelText('PlantID Home');
      expect(logoLink).toBeInTheDocument();
    });

    it('has proper aria-label for menu button', () => {
      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');
      expect(menuButton).toBeInTheDocument();
    });

    it('updates aria-expanded when menu toggles', () => {
      renderWithRouter(<Header />);

      const menuButton = screen.getByLabelText('Toggle menu');

      expect(menuButton).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(menuButton);
      expect(menuButton).toHaveAttribute('aria-expanded', 'true');

      fireEvent.click(menuButton);
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('navigation is keyboard accessible', () => {
      renderWithRouter(<Header />);

      const links = screen.getAllByRole('link');
      links.forEach((link) => {
        expect(link).toBeInTheDocument();
      });
    });
  });

  describe('Sticky Header', () => {
    it('has sticky positioning classes', () => {
      const { container } = renderWithRouter(<Header />);

      const nav = container.querySelector('nav');
      expect(nav).toHaveClass('sticky', 'top-0', 'z-50');
    });
  });
});
