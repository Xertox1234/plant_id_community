import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FinishSignupPage from './FinishSignupPage';

const { mockFinish, mockRefreshUser, mockNavigate } = vi.hoisted(() => ({
  mockFinish: vi.fn(),
  mockRefreshUser: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock('../../services/authService', async () => {
  const actual = await vi.importActual<typeof import('../../services/authService')>(
    '../../services/authService'
  );
  return { ...actual, finishOAuthSignup: mockFinish };
});
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ refreshUser: mockRefreshUser }),
}));
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

import { OAuthFinishError } from '../../services/authService';

function renderPage() {
  return render(
    <MemoryRouter>
      <FinishSignupPage />
    </MemoryRouter>
  );
}

const tick = () => fireEvent.click(screen.getByRole('checkbox'));
const finish = () => fireEvent.click(screen.getByRole('button', { name: 'Finish signing up' }));

describe('FinishSignupPage', () => {
  beforeEach(() => {
    mockFinish.mockReset();
    mockRefreshUser.mockReset();
    mockNavigate.mockReset();
  });

  it('shows the checkbox and keeps the button disabled until it is ticked', () => {
    renderPage();
    const button = screen.getByRole('button', { name: 'Finish signing up' });
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(button).toBeDisabled();
    tick();
    expect(button).toBeEnabled();
  });

  it('refreshes the user and goes home on success', async () => {
    mockFinish.mockResolvedValue(undefined);
    mockRefreshUser.mockResolvedValue({ id: 1 });
    renderPage();
    tick();
    finish();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }));
    expect(mockFinish).toHaveBeenCalledTimes(1);
    expect(mockRefreshUser).toHaveBeenCalledTimes(1);
  });

  it.each(['signup_expired', 'signup_failed'])(
    'shows the expired message with a sign-in link on %s',
    async (code) => {
      mockFinish.mockRejectedValue(new OAuthFinishError(code, 400, 'x'));
      renderPage();
      tick();
      finish();
      expect(
        await screen.findByText('Your sign-up expired. Please sign in again.')
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
      expect(mockNavigate).not.toHaveBeenCalled();
    }
  );

  it('shows the server message on consent_required', async () => {
    mockFinish.mockRejectedValue(
      new OAuthFinishError('consent_required', 428, 'You must accept to continue.')
    );
    renderPage();
    tick();
    finish();
    expect(await screen.findByText('You must accept to continue.')).toBeInTheDocument();
  });

  it('shows a rate-limit message on 429', async () => {
    mockFinish.mockRejectedValue(new OAuthFinishError(undefined, 429, 'x'));
    renderPage();
    tick();
    finish();
    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
  });
});
