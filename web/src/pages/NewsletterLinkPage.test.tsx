import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import NewsletterLinkPage from './NewsletterLinkPage';
import {
  NewsletterLinkError,
  confirmNewsletter,
  unsubscribeNewsletter,
} from '../services/newsletterService';

vi.mock('../services/newsletterService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/newsletterService')>();
  return { ...actual, confirmNewsletter: vi.fn(), unsubscribeNewsletter: vi.fn() };
});

const confirm = vi.mocked(confirmNewsletter);
const unsubscribe = vi.mocked(unsubscribeNewsletter);

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Link to="/newsletter/confirm?token=second">second link</Link>
      <Routes>
        <Route path="/newsletter/confirm" element={<NewsletterLinkPage action="confirm" />} />
        <Route
          path="/newsletter/unsubscribe"
          element={<NewsletterLinkPage action="unsubscribe" />}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('NewsletterLinkPage', () => {
  beforeEach(() => {
    confirm.mockReset();
    unsubscribe.mockReset();
  });

  it('does nothing on load: only the button confirms', async () => {
    confirm.mockResolvedValue(true);
    renderAt('/newsletter/confirm?token=abc');

    expect(screen.getByRole('heading', { name: /confirm your newsletter/i })).toBeInTheDocument();
    // Mail scanners open links; opening the page must not subscribe anyone.
    expect(confirm).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: /confirm subscription/i }));
    expect(confirm).toHaveBeenCalledWith('abc');
    expect(await screen.findByRole('heading', { name: /you're subscribed/i })).toBeInTheDocument();
    expect(unsubscribe).not.toHaveBeenCalled();
  });

  it('unsubscribes only after the button', async () => {
    unsubscribe.mockResolvedValue(false);
    renderAt('/newsletter/unsubscribe?token=xyz');

    expect(unsubscribe).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: /unsubscribe/i }));
    expect(unsubscribe).toHaveBeenCalledWith('xyz');
    expect(
      await screen.findByRole('heading', { name: /you're unsubscribed/i })
    ).toBeInTheDocument();
  });

  it('explains a link without a token, without calling the API', () => {
    renderAt('/newsletter/confirm');
    expect(screen.getByRole('heading', { name: /isn't valid/i })).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('explains an expired link', async () => {
    confirm.mockRejectedValue(new NewsletterLinkError('expired', 'expired'));
    renderAt('/newsletter/confirm?token=old');
    await userEvent.click(screen.getByRole('button', { name: /confirm subscription/i }));
    expect(await screen.findByRole('heading', { name: /expired/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /blog/i })).toHaveAttribute('href', '/blog');
  });

  it('keeps the button after a transient failure', async () => {
    unsubscribe.mockRejectedValueOnce(new NewsletterLinkError('error', 'boom'));
    unsubscribe.mockResolvedValueOnce(false);
    renderAt('/newsletter/unsubscribe?token=xyz');

    await userEvent.click(screen.getByRole('button', { name: /unsubscribe/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/try again/i);
    await userEvent.click(screen.getByRole('button', { name: /unsubscribe/i }));
    expect(
      await screen.findByRole('heading', { name: /you're unsubscribed/i })
    ).toBeInTheDocument();
  });

  it('starts over when a second link opens on the same route', async () => {
    confirm.mockResolvedValue(true);
    renderAt('/newsletter/confirm?token=first');
    await userEvent.click(screen.getByRole('button', { name: 'Confirm subscription' }));
    expect(await screen.findByRole('heading', { name: "You're subscribed" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('link', { name: 'second link' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm subscription' }));
    expect(confirm).toHaveBeenLastCalledWith('second');
  });
});
