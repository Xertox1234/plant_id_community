import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import NewsletterSignup from './NewsletterSignup';
import { NewsletterSignupError, subscribeToNewsletter } from '../../services/newsletterService';

vi.mock('../../services/newsletterService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/newsletterService')>();
  return { ...actual, subscribeToNewsletter: vi.fn() };
});

const subscribe = vi.mocked(subscribeToNewsletter);

// The form links to the Privacy Policy, so it needs a router.
function renderForm() {
  return render(
    <MemoryRouter>
      <NewsletterSignup idPrefix="test" />
    </MemoryRouter>
  );
}

async function submit(email: string) {
  renderForm();
  await userEvent.type(screen.getByLabelText(/email address/i), email);
  await userEvent.click(screen.getByRole('button', { name: /subscribe/i }));
}

describe('NewsletterSignup', () => {
  beforeEach(() => {
    subscribe.mockReset();
  });

  it('sends the trimmed address and says to check the inbox', async () => {
    subscribe.mockResolvedValue(undefined);
    await submit('  reader@example.com ');

    expect(subscribe).toHaveBeenCalledWith('reader@example.com');
    // Never "you're subscribed": nothing starts until the emailed link is used.
    expect(await screen.findByRole('status')).toHaveTextContent(/check your inbox/i);
    expect(screen.queryByRole('button', { name: /subscribe/i })).not.toBeInTheDocument();
    // The button that had focus is gone; focus lands on the message, not <body>.
    expect(screen.getByRole('status')).toHaveFocus();
  });

  it('keeps the form and explains an invalid address', async () => {
    subscribe.mockRejectedValue(new NewsletterSignupError('invalid_email', 'bad'));
    await submit('nope');

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('button', { name: /subscribe/i })).toBeEnabled();
  });

  it('says to wait when rate limited', async () => {
    subscribe.mockRejectedValue(new NewsletterSignupError('rate_limited', 'slow'));
    await submit('reader@example.com');
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many attempts/i);
    // Not the field's error: the address itself may be fine.
    expect(screen.getByLabelText(/email address/i)).toHaveAttribute('aria-invalid', 'false');
  });

  it('does not submit an empty address', async () => {
    renderForm();
    expect(screen.getByRole('button', { name: /subscribe/i })).toBeDisabled();
  });

  // CASL s. 10(1) (todo 703): who is asking, a contact, and that the reader
  // can unsubscribe, shown where consent is asked for.
  it('says who is asking, how to reach them, and that the reader can unsubscribe', () => {
    renderForm();
    expect(screen.getByText(/sent by houseplant md/i)).toBeInTheDocument();
    expect(screen.getByText(/unsubscribe link, so you can stop at any time/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute(
      'href',
      '/privacy'
    );
  });
});
