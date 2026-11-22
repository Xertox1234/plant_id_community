import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom';
import UnsubscribePage from './UnsubscribePage';
import {
  UnsubscribeError,
  checkUnsubscribe,
  confirmUnsubscribe,
  stopAllOptionalEmail,
} from '../services/unsubscribeService';

vi.mock('../services/unsubscribeService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/unsubscribeService')>();
  return {
    ...actual,
    checkUnsubscribe: vi.fn(),
    confirmUnsubscribe: vi.fn(),
    stopAllOptionalEmail: vi.fn(),
  };
});

const check = vi.mocked(checkUnsubscribe);
const confirm = vi.mocked(confirmUnsubscribe);
const stopAll = vi.mocked(stopAllOptionalEmail);

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

// Todo 703 (CASL, CAN-SPAM): a signed-out visitor with any valid link can stop
// all optional email in one step, not only the link's own list.
describe('UnsubscribePage stop all optional email (todo 703)', () => {
  const ALL_LABEL =
    'All optional email: forum notifications, the forum digest and the blog newsletter';
  const allStopped = { list: 'all_optional', label: ALL_LABEL, subscribed: false };
  const stopAllButton = () => screen.findByRole('button', { name: /stop all optional email/i });

  beforeEach(() => {
    check.mockReset();
    confirm.mockReset();
    stopAll.mockReset();
  });

  it('stops all optional email in one click, signed out, with a single-list link', async () => {
    check.mockResolvedValue(subscribed);
    stopAll.mockResolvedValue(allStopped);
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await stopAllButton());

    expect(stopAll).toHaveBeenCalledTimes(1);
    expect(stopAll).toHaveBeenCalledWith('abc');
    // Not the single-list call: one step, one request.
    expect(confirm).not.toHaveBeenCalled();
    expect(await screen.findByRole('heading', { name: /unsubscribed/i })).toBeInTheDocument();
    expect(screen.getByText(ALL_LABEL)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop all optional email/i })
    ).not.toBeInTheDocument();
    expectSettingsLink();
  });

  it("is offered when the link's own list is already off", async () => {
    check.mockResolvedValue(unsubscribed);
    stopAll.mockResolvedValue(allStopped);
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await stopAllButton());
    expect(stopAll).toHaveBeenCalledWith('abc');
    expect(await screen.findByText(ALL_LABEL)).toBeInTheDocument();
  });

  it('is offered again after leaving one list', async () => {
    check.mockResolvedValue(subscribed);
    confirm.mockResolvedValue(unsubscribed);
    stopAll.mockResolvedValue(allStopped);
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await screen.findByRole('button', { name: /^unsubscribe$/i }));
    await userEvent.click(await stopAllButton());
    expect(stopAll).toHaveBeenCalledWith('abc');
  });

  it('is not repeated for a link that already means all optional email', async () => {
    check.mockResolvedValue({ ...allStopped, subscribed: true });
    renderAt('/unsubscribe?token=abc');

    expect(await screen.findByText(ALL_LABEL)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop all optional email/i })
    ).not.toBeInTheDocument();
  });

  it('keeps the choice when the call fails', async () => {
    check.mockResolvedValue(subscribed);
    stopAll.mockRejectedValueOnce(new UnsubscribeError('error', 'down'));
    renderAt('/unsubscribe?token=abc');

    await userEvent.click(await stopAllButton());

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t unsubscribe/i);
    expect(await stopAllButton()).toBeEnabled();
  });
});

// The token is single-use; it must leave the address bar and history once read
// (todo 706, audit M7). A real BrowserRouter, because MemoryRouter never
// touches window.location and would pass vacuously.
describe('UnsubscribePage address bar (todo 706)', () => {
  beforeEach(() => {
    check.mockReset();
    confirm.mockReset();
  });

  afterEach(() => {
    window.history.replaceState(null, '', '/');
  });

  function renderInBrowser(url: string) {
    window.history.pushState(null, '', url);
    return render(
      <BrowserRouter>
        <Routes>
          <Route path="/unsubscribe" element={<UnsubscribePage />} />
        </Routes>
      </BrowserRouter>
    );
  }

  it('removes the token from location.search and still unsubscribes with it', async () => {
    check.mockResolvedValue(subscribed);
    confirm.mockResolvedValue(unsubscribed);
    renderInBrowser('/unsubscribe?token=abc');

    await waitFor(() => expect(window.location.search).toBe(''));
    expect(window.location.pathname).toBe('/unsubscribe');
    expect(check).toHaveBeenCalledWith('abc');

    await userEvent.click(await screen.findByRole('button', { name: /unsubscribe/i }));
    expect(confirm).toHaveBeenCalledWith('abc');
  });

  it('replaces the history entry, so Back cannot bring the token back', async () => {
    check.mockResolvedValue(subscribed);
    const before = window.history.length;
    renderInBrowser('/unsubscribe?token=abc');

    await waitFor(() => expect(window.location.search).toBe(''));
    expect(window.history.length).toBe(before + 1);
  });
});
