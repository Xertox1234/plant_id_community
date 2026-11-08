import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ConfirmDeleteAccountPage from './ConfirmDeleteAccountPage';
import {
  AccountDeletionError,
  confirmAccountDeletion,
} from '../../services/accountDeletionService';

vi.mock('../../services/accountDeletionService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/accountDeletionService')>();
  return { ...actual, confirmAccountDeletion: vi.fn() };
});
const clearLocalSession = vi.fn();
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ clearLocalSession }),
}));
const confirm = vi.mocked(confirmAccountDeletion);

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/delete-account/confirm" element={<ConfirmDeleteAccountPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ConfirmDeleteAccountPage', () => {
  beforeEach(() => {
    confirm.mockReset();
    clearLocalSession.mockReset();
  });

  it('never auto-submits: the button must be pressed', async () => {
    renderAt('/delete-account/confirm?token=tok');
    expect(await screen.findByRole('button', { name: 'Delete my account' })).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
    expect(screen.getByText(/plants/i)).toBeInTheDocument();
  });

  it('on 202 shows the done message and clears the local session', async () => {
    confirm.mockResolvedValue('scheduled');
    renderAt('/delete-account/confirm?token=tok');
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account' }));
    expect(confirm).toHaveBeenCalledWith('tok');
    expect(
      await screen.findByText("Your account is being deleted. You'll get an email when it's done.")
    ).toBeInTheDocument();
    expect(clearLocalSession).toHaveBeenCalledTimes(1);
  });

  it('on link_invalid shows the server message and a link to request a new one', async () => {
    confirm.mockRejectedValue(new AccountDeletionError('link_invalid', 'Expired, ask again.'));
    renderAt('/delete-account/confirm?token=tok');
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account' }));
    expect(await screen.findByText('Expired, ask again.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /new link/i })).toHaveAttribute(
      'href',
      '/delete-account'
    );
    expect(clearLocalSession).not.toHaveBeenCalled();
  });

  it('on contact_support shows the server message', async () => {
    confirm.mockRejectedValue(
      new AccountDeletionError('contact_support', 'Please contact support.')
    );
    renderAt('/delete-account/confirm?token=tok');
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account' }));
    expect(await screen.findByText('Please contact support.')).toBeInTheDocument();
  });

  it('on a generic failure keeps the button so the user can retry', async () => {
    confirm.mockRejectedValue(new AccountDeletionError('error', 'x'));
    renderAt('/delete-account/confirm?token=tok');
    await userEvent.click(screen.getByRole('button', { name: 'Delete my account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/try again/i);
    expect(screen.getByRole('button', { name: 'Delete my account' })).toBeInTheDocument();
  });

  it('without a token shows the link_invalid copy and never calls the API', () => {
    renderAt('/delete-account/confirm');
    expect(
      screen.getByText('This link has expired or was already used. Request a new one.')
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /new link/i })).toHaveAttribute(
      'href',
      '/delete-account'
    );
    expect(screen.queryByRole('button', { name: 'Delete my account' })).not.toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });
});
