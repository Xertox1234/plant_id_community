import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import UnsubscribePage from './UnsubscribePage';
import {
  UnsubscribeError,
  checkUnsubscribe,
  confirmUnsubscribe,
} from '../services/unsubscribeService';

vi.mock('../services/unsubscribeService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/unsubscribeService')>();
  return { ...actual, checkUnsubscribe: vi.fn(), confirmUnsubscribe: vi.fn() };
});

const check = vi.mocked(checkUnsubscribe);
const confirm = vi.mocked(confirmUnsubscribe);

const LABEL = 'Email for replies to topics you follow';
const subscribed = { list: 'forum_reply', label: LABEL, subscribed: true };
const unsubscribed = { ...subscribed, subscribed: false };

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/unsubscribe" element={<UnsubscribePage />} />
      </Routes>
    </MemoryRouter>
  );
}

function expectSettingsLink() {
  expect(screen.getByRole('link', { name: /settings/i })).toHaveAttribute('href', '/settings');
}

describe('UnsubscribePage', () => {
  beforeEach(() => {
    check.mockReset();
    confirm.mockReset();
  });

  it('asks before unsubscribing, and does nothing until confirmed', async () => {
    check.mockResolvedValue(subscribed);
    renderAt('/unsubscribe?token=abc');

    expect(await screen.findByRole('heading', { name: /unsubscribe/i })).toBeInTheDocument();
    expect(screen.getByText(LABEL)).toBeInTheDocument();
    expect(check).toHaveBeenCalledWith('abc');
    expect(confirm).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /unsubscribe/i })).toBeEnabled();
  });

  it('unsubscribes on confirm and says how to undo it', async () => {
    check.mockResolvedValue(subscribed);
    confirm.mockResolvedValue(unsubscribed);
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await screen.findByRole('button', { name: /unsubscribe/i }));

    expect(confirm).toHaveBeenCalledWith('abc');
    expect(await screen.findByRole('heading', { name: /unsubscribed/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /unsubscribe/i })).not.toBeInTheDocument();
    expectSettingsLink();
  });

  it('says so when the account is already unsubscribed', async () => {
    check.mockResolvedValue(unsubscribed);
    renderAt('/unsubscribe?token=abc');

    expect(
      await screen.findByRole('heading', { name: /already unsubscribed/i })
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /unsubscribe/i })).not.toBeInTheDocument();
    expectSettingsLink();
  });

  it('explains an invalid link and never calls the API without a token', async () => {
    renderAt('/unsubscribe');

    expect(await screen.findByRole('heading', { name: /link isn.t valid/i })).toBeInTheDocument();
    expect(check).not.toHaveBeenCalled();
    expectSettingsLink();
  });

  it('explains a forged or unknown link', async () => {
    check.mockRejectedValue(new UnsubscribeError('invalid', 'invalid'));
    renderAt('/unsubscribe?token=forged');

    expect(await screen.findByRole('heading', { name: /link isn.t valid/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /unsubscribe/i })).not.toBeInTheDocument();
    expectSettingsLink();
  });

  it('explains an expired link', async () => {
    check.mockRejectedValue(new UnsubscribeError('expired', 'expired'));
    renderAt('/unsubscribe?token=old');

    expect(await screen.findByRole('heading', { name: /link has expired/i })).toBeInTheDocument();
    expectSettingsLink();
  });

  it('offers a retry when the server cannot be reached', async () => {
    check.mockRejectedValueOnce(new UnsubscribeError('error', 'down'));
    check.mockResolvedValueOnce(subscribed);
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await screen.findByRole('button', { name: /try again/i }));

    expect(await screen.findByText(LABEL)).toBeInTheDocument();
    expect(check).toHaveBeenCalledTimes(2);
  });

  it('keeps the confirm step when the unsubscribe call fails', async () => {
    check.mockResolvedValue(subscribed);
    confirm.mockRejectedValueOnce(new UnsubscribeError('error', 'down'));
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await screen.findByRole('button', { name: /unsubscribe/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t unsubscribe/i);
    expect(screen.getByRole('button', { name: /unsubscribe/i })).toBeEnabled();
  });
});
