import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import GoogleSignInButton from './GoogleSignInButton';

// Drive the service outcome. vi.hoisted: the vi.mock factory is hoisted above
// imports, so it can't close over a plain top-level const.
const { mockGetGoogleOAuthUrl } = vi.hoisted(() => ({ mockGetGoogleOAuthUrl: vi.fn() }));

vi.mock('../../services/authService', () => ({
  getGoogleOAuthUrl: mockGetGoogleOAuthUrl,
}));

vi.mock('../../utils/logger', () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

const OAUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&state=xyz';

describe('GoogleSignInButton', () => {
  const assignMock = vi.fn();
  let originalLocation: Location;

  beforeEach(() => {
    // jsdom makes window.location.assign non-configurable (can't be spied), so
    // replace the whole location property with a stub the component can call.
    originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { assign: assignMock, href: '' },
    });
    assignMock.mockReset();
    mockGetGoogleOAuthUrl.mockReset();
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  it('redirects the browser to the backend-provided Google OAuth URL on click', async () => {
    mockGetGoogleOAuthUrl.mockResolvedValue(OAUTH_URL);
    render(<GoogleSignInButton />);

    fireEvent.click(screen.getByRole('button', { name: 'Sign in with Google' }));

    await waitFor(() => expect(assignMock).toHaveBeenCalledWith(OAUTH_URL));
    expect(mockGetGoogleOAuthUrl).toHaveBeenCalledTimes(1);
  });

  it('shows an error and re-enables the button when initiation fails', async () => {
    mockGetGoogleOAuthUrl.mockRejectedValue(new Error('boom'));
    render(<GoogleSignInButton />);

    const button = screen.getByRole('button', { name: 'Sign in with Google' });
    fireEvent.click(button);

    expect(
      await screen.findByText('Could not start Google sign-in. Please try again.')
    ).toBeInTheDocument();
    expect(assignMock).not.toHaveBeenCalled();
    expect(button).not.toBeDisabled();
  });

  it('renders the provided label', () => {
    render(<GoogleSignInButton label="Sign up with Google" />);

    expect(screen.getByRole('button', { name: 'Sign up with Google' })).toBeInTheDocument();
  });

  it('is disabled when the disabled prop is set, independent of redirect state', () => {
    render(<GoogleSignInButton disabled />);

    expect(screen.getByRole('button', { name: 'Sign in with Google' })).toBeDisabled();
  });
});
