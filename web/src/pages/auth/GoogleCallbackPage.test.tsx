import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GoogleCallbackPage from './GoogleCallbackPage';

// useNavigate is asserted; keep the rest of react-router-dom real so
// useSearchParams reads the MemoryRouter location.
const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const { mockRefreshUser } = vi.hoisted(() => ({ mockRefreshUser: vi.fn() }));
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ refreshUser: mockRefreshUser }),
}));

vi.mock('../../utils/logger', () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <GoogleCallbackPage />
    </MemoryRouter>
  );
}

/**
 * The failure message renders twice on purpose (audit M26): once in the
 * persistent `aria-live` region that is mounted from the first paint — so
 * setting the error is a text SWAP a screen reader actually announces — and
 * once in the visible card. Asserting both copies is what keeps the announcer
 * from being silently deleted as a duplicate.
 */
async function expectErrorAnnounced(text: string) {
  const copies = await screen.findAllByText(text);
  expect(copies).toHaveLength(2);
  expect(copies.filter((el) => el.getAttribute('aria-live') === 'assertive')).toHaveLength(1);
}

describe('GoogleCallbackPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockRefreshUser.mockReset();
  });

  it('mounts the live region before there is an error to put in it (audit M26)', () => {
    // MDN: a live region must already exist in the DOM for a later content
    // change to be announced. Mounting it with the error is the anti-pattern.
    mockRefreshUser.mockReturnValue(new Promise(() => {})); // never settles — spinner state
    const { container } = renderAt('/auth/google/callback?success=true');

    const region = container.querySelector('[aria-live="assertive"]');
    expect(region).toBeInTheDocument();
    expect(region).toHaveTextContent('');
  });

  it('refreshes the user and routes home on ?success=true', async () => {
    mockRefreshUser.mockResolvedValue({ id: 1, username: 'newuser' });

    renderAt('/auth/google/callback?success=true');

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }));
    expect(mockRefreshUser).toHaveBeenCalledTimes(1);
  });

  it('maps a backend ?error code to a readable message and offers a route back to login', async () => {
    renderAt('/auth/google/callback?error=invalid_state');

    await expectErrorAnnounced(
      'Your sign-in session expired or could not be verified. Please try again.'
    );
    // AC#2 "returns to login": the error view links back to /login.
    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute(
      'href',
      '/login'
    );
    expect(mockRefreshUser).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows a generic message when neither success nor a known error is present', async () => {
    renderAt('/auth/google/callback');

    await expectErrorAnnounced('Google sign-in failed. Please try again.');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows an error when the session cannot be confirmed (refreshUser returns null)', async () => {
    mockRefreshUser.mockResolvedValue(null);

    renderAt('/auth/google/callback?success=true');

    await expectErrorAnnounced('We could not confirm your sign-in. Please try again.');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows an error when refreshUser rejects (exercises the catch path)', async () => {
    mockRefreshUser.mockRejectedValue(new Error('network'));

    renderAt('/auth/google/callback?success=true');

    await expectErrorAnnounced('We could not confirm your sign-in. Please try again.');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('treats an error code as failure even when success=true is also present', async () => {
    renderAt('/auth/google/callback?success=true&error=invalid_state');

    await expectErrorAnnounced(
      'Your sign-in session expired or could not be verified. Please try again.'
    );
    expect(mockRefreshUser).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
