import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DeleteAccountSection from './DeleteAccountSection';
import {
  AccountDeletionError,
  requestAccountDeletion,
} from '../../services/accountDeletionService';

vi.mock('../../services/accountDeletionService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/accountDeletionService')>();
  return { ...actual, requestAccountDeletion: vi.fn() };
});
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'jane@example.com' } }),
}));
const request = vi.mocked(requestAccountDeletion);

describe('DeleteAccountSection', () => {
  beforeEach(() => {
    request.mockReset();
  });

  it('shows the heading and explanation', () => {
    render(<DeleteAccountSection />);
    expect(screen.getByRole('heading', { name: 'Delete account' })).toBeInTheDocument();
    expect(
      screen.getByText(
        "This permanently deletes your account, plants, garden, scans and forum posts. It can't be undone."
      )
    ).toBeInTheDocument();
  });

  it('asks for confirmation before sending anything', async () => {
    render(<DeleteAccountSection />);
    await userEvent.click(screen.getByRole('button', { name: 'Email me a deletion link' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(request).not.toHaveBeenCalled();
  });

  it('on confirm requests deletion for the signed-in email', async () => {
    request.mockResolvedValue();
    render(<DeleteAccountSection />);
    await userEvent.click(screen.getByRole('button', { name: 'Email me a deletion link' }));
    await userEvent.click(screen.getByRole('button', { name: 'Send link' }));
    expect(request).toHaveBeenCalledWith('jane@example.com');
    expect(
      await screen.findByText('Check your email for a link to finish deleting your account.')
    ).toBeInTheDocument();
  });

  it('shows the rate-limit message on 429', async () => {
    request.mockRejectedValue(new AccountDeletionError('rate_limited', 'x'));
    render(<DeleteAccountSection />);
    await userEvent.click(screen.getByRole('button', { name: 'Email me a deletion link' }));
    await userEvent.click(screen.getByRole('button', { name: 'Send link' }));
    expect(await screen.findByText('Too many requests, try again later.')).toBeInTheDocument();
  });
});
