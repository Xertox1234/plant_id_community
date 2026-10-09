import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NewsletterSignup from './NewsletterSignup';
import { NewsletterSignupError, subscribeToNewsletter } from '../../services/newsletterService';

vi.mock('../../services/newsletterService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/newsletterService')>();
  return { ...actual, subscribeToNewsletter: vi.fn() };
});

const subscribe = vi.mocked(subscribeToNewsletter);

async function submit(email: string) {
  render(<NewsletterSignup idPrefix="test" />);
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
    render(<NewsletterSignup idPrefix="test" />);
    expect(screen.getByRole('button', { name: /subscribe/i })).toBeDisabled();
  });
});
