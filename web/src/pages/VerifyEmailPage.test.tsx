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
  user: { id: 7, email: 'ada@example.com' } as { id: number; email: string } | null,
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
    authState.user = { id: 7, email: 'ada@example.com' };
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

  it('asks a signed-out visitor to sign in before resending', async () => {
    authState.user = null;
    confirm.mockRejectedValue(new VerificationError('invalid', 'bad'));
    renderAt('/verify-email?key=abc');

    await userEvent.click(screen.getByRole('button', { name: /confirm my email/i }));

    expect(await screen.findByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
    expect(screen.queryByRole('button', { name: /send a new link/i })).not.toBeInTheDocument();
  });
});
