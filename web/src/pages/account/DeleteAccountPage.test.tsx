import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import DeleteAccountPage from './DeleteAccountPage';
import {
  AccountDeletionError,
  requestAccountDeletion,
} from '../../services/accountDeletionService';

vi.mock('../../services/accountDeletionService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/accountDeletionService')>();
  return { ...actual, requestAccountDeletion: vi.fn() };
});
const request = vi.mocked(requestAccountDeletion);

const SENT = "If an account exists for that address, we've sent a link.";

function renderPage() {
  return render(
    <MemoryRouter>
      <DeleteAccountPage />
    </MemoryRouter>
  );
}

describe('DeleteAccountPage', () => {
  beforeEach(() => {
    request.mockReset();
  });

  it('explains the deletion and the subscription caveat', () => {
    renderPage();
    expect(
      screen.getByText(
        "This permanently deletes your account, plants, garden, scans and forum posts. It can't be undone."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Deleting your account doesn't cancel a Premium subscription. Cancel it in the App Store or Google Play."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(SENT)).not.toBeInTheDocument();
  });

  it('sends the email and shows the neutral message', async () => {
    request.mockResolvedValue();
    renderPage();
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send deletion link' }));
    expect(request).toHaveBeenCalledWith('a@b.com');
    expect(await screen.findByText(SENT)).toBeInTheDocument();
  });

  it('shows a rate-limit message on 429', async () => {
    request.mockRejectedValue(new AccountDeletionError('rate_limited', 'x'));
    renderPage();
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send deletion link' }));
    expect(await screen.findByText('Too many requests, try again later.')).toBeInTheDocument();
    expect(screen.queryByText(SENT)).not.toBeInTheDocument();
  });

  it('shows a generic error on other failures', async () => {
    request.mockRejectedValue(new AccountDeletionError('error', 'x'));
    renderPage();
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send deletion link' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i);
  });
});
