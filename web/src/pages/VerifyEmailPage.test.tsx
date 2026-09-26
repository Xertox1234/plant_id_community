import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import VerifyEmailPage from './VerifyEmailPage';
import {
  VerificationError,
  confirmEmailVerification,
  resendVerificationEmail,
} from '../services/emailVerificationService';

const authState = vi.hoisted(() => ({
  user: { id: 7, email: 'ada@example.com', username: 'ada' } as {
    id: number;
    email: string;
    username?: string;
  } | null,
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: authState.user }),
}));

vi.mock('../services/emailVerificationService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/emailVerificationService')>();
  return { ...actual, confirmEmailVerification: vi.fn(), resendVerificationEmail: vi.fn() };
});

const confirm = vi.mocked(confirmEmailVerification);
const resend = vi.mocked(resendVerificationEmail);

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('VerifyEmailPage', () => {
  beforeEach(() => {
    confirm.mockReset();
    resend.mockReset();
    authState.user = { id: 7, email: 'ada@example.com', username: 'ada' };
  });

  it('does nothing on open; only the button confirms (mail scanners open links)', async () => {
    confirm.mockResolvedValue(undefined);
    renderAt('/verify-email?key=abc');

    expect(
      screen.getByRole('heading', { name: /confirm your email address/i })
    ).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: /confirm my email/i }));

    expect(confirm).toHaveBeenCalledWith('abc');
    expect(await screen.findByRole('heading', { name: /is confirmed/i })).toBeInTheDocument();
  });

  it('explains a bad link and offers a new one', async () => {
    confirm.mockRejectedValue(new VerificationError('invalid', 'bad'));
    resend.mockResolvedValue({ verified: false, sent: true });
    renderAt('/verify-email?key=abc');

    await userEvent.click(screen.getByRole('button', { name: /confirm my email/i }));
    expect(await screen.findByRole('heading', { name: /doesn.t work/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /send a new link/i }));
    expect(await screen.findByText(/sent a new link to ada@example.com/i)).toBeInTheDocument();
  });

  it('says so when the account has had every link it gets', async () => {
    // Todo 447 item 9: the backend caps verification mails per account.
    confirm.mockRejectedValue(new VerificationError('invalid', 'bad'));
    resend.mockResolvedValue({ verified: false, sent: false, limit_reached: true });
    renderAt('/verify-email?key=abc');

    await userEvent.click(screen.getByRole('button', { name: /confirm my email/i }));
    await userEvent.click(await screen.findByRole('button', { name: /send a new link/i }));

    expect(await screen.findByText(/as many links as we can for now/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send a new link/i })).toBeDisabled();
  });

  it('keeps the button after a transient failure', async () => {
    confirm.mockRejectedValue(new VerificationError('error', 'down'));
    renderAt('/verify-email?key=abc');

    await userEvent.click(screen.getByRole('button', { name: /confirm my email/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t confirm/i);
    expect(screen.getByRole('button', { name: /confirm my email/i })).toBeInTheDocument();
  });

  it('without a key, tells a new sign-up to check their inbox', () => {
    renderAt('/verify-email');

    expect(screen.getByRole('heading', { name: /confirm your email/i })).toBeInTheDocument();
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });

  it('names the account being confirmed', () => {
    renderAt('/verify-email?key=abc');

    expect(screen.getByText('ada')).toBeInTheDocument();
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
  });

  it('signed out, asks to sign in and offers no confirm button (the key alone is not enough)', () => {
    authState.user = null;
    renderAt('/verify-email?key=abc');

    expect(screen.getByRole('heading', { name: /sign in to confirm/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
    expect(screen.queryByRole('button', { name: /confirm my email/i })).not.toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });

  it('a session that lapsed before the click also asks to sign in', async () => {
    confirm.mockRejectedValue(new VerificationError('signin', 'no session'));
    renderAt('/verify-email?key=abc');

    await userEvent.click(screen.getByRole('button', { name: /confirm my email/i }));

    expect(await screen.findByRole('heading', { name: /sign in to confirm/i })).toBeInTheDocument();
  });
});
