/**
 * Blog newsletter signup (todo 409). Sits in the blog list's right rail and
 * under each article.
 *
 * A successful request only means a confirmation email MAY have been sent:
 * the backend answers the same for every address (so nobody can learn who is
 * subscribed), and the subscription starts when the emailed link is used.
 */
import { useState, type FormEvent } from 'react';
import Button from '../ui/Button';
import Input from '../ui/Input';
import {
  NewsletterSignupError,
  subscribeToNewsletter,
  type SignupFailure,
} from '../../services/newsletterService';

const FAILURE_COPY: Record<SignupFailure, string> = {
  invalid_email: 'Enter a valid email address.',
  rate_limited: 'Too many attempts from here. Please try again later.',
  error: "We couldn't sign you up just now. Please try again.",
};

interface NewsletterSignupProps {
  /** Distinguishes the field's id when the form appears twice on a page. */
  idPrefix: string;
}

export default function NewsletterSignup({ idPrefix }: NewsletterSignupProps) {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<SignupFailure | null>(null);
  const [sent, setSent] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setFailure(null);
    try {
      await subscribeToNewsletter(email.trim());
      setSent(true);
    } catch (err) {
      setFailure(err instanceof NewsletterSignupError ? err.reason : 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Always mounted: a live region that appears together with its text
          is often not announced. */}
      <p role="status" className={sent ? 'text-body-sm text-ink-2' : 'sr-only'}>
        {sent &&
          "Check your inbox: if that address can join, we've sent it a link to confirm. Nothing arrives until the link is used."}
      </p>
      {!sent && (
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <p className="text-body-sm text-ink-2">
            New posts from the blog, once a week. No more than that.
          </p>
          <Input
            type="email"
            name={`${idPrefix}-newsletter-email`}
            label="Email address"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            // Only a bad address is the field's fault; the rest get their own line.
            error={failure === 'invalid_email' ? FAILURE_COPY[failure] : undefined}
            required
          />
          {failure && failure !== 'invalid_email' && (
            <p role="alert" className="text-body-sm text-error">
              {FAILURE_COPY[failure]}
            </p>
          )}
          <div>
            <Button
              type="submit"
              loading={submitting}
              loadingText="Sending…"
              disabled={!email.trim()}
            >
              Subscribe
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
