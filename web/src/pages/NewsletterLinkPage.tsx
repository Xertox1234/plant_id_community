/**
 * Where the blog newsletter's emailed links land (todo 409):
 * /newsletter/confirm?token=… and /newsletter/unsubscribe?token=….
 *
 * Opening the page changes nothing: mail scanners open every link in an
 * email, so a page that acted on load would let one subscribe a reader who
 * never asked. Only the button acts. Public on purpose: the signed token is
 * the credential, so it works signed out.
 */
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import PageMeta from '../components/PageMeta';
import {
  NewsletterLinkError,
  confirmNewsletter,
  unsubscribeNewsletter,
  type NewsletterLinkFailure,
} from '../services/newsletterService';

export type NewsletterLinkAction = 'confirm' | 'unsubscribe';

const COPY: Record<
  NewsletterLinkAction,
  {
    title: string;
    ask: string;
    explain: string;
    button: string;
    busy: string;
    done: string;
    doneBody: string;
  }
> = {
  confirm: {
    title: 'Confirm subscription',
    ask: 'Confirm your newsletter subscription?',
    explain: "You'll get new posts from the blog, once a week.",
    button: 'Confirm subscription',
    busy: 'Confirming…',
    done: "You're subscribed",
    doneBody:
      'New posts from the blog will arrive once a week. Every email has a link to unsubscribe.',
  },
  unsubscribe: {
    title: 'Unsubscribe',
    ask: 'Unsubscribe from the newsletter?',
    explain: "You'll stop getting the weekly email of new blog posts.",
    button: 'Unsubscribe',
    busy: 'Unsubscribing…',
    done: "You're unsubscribed",
    doneBody: "We won't send you the newsletter any more. You can sign up again on the blog.",
  },
};

const FAILURE_COPY: Record<NewsletterLinkFailure, { heading: string; body: string }> = {
  invalid: {
    heading: "This link isn't valid",
    body: 'It may have been copied incompletely, or replaced by a newer email. Nothing was changed.',
  },
  expired: {
    heading: 'This link has expired',
    body: 'Links from our emails stop working after a while. Nothing was changed.',
  },
  rate_limited: {
    heading: 'Too many attempts',
    body: 'Please wait a while, then open the link again. Nothing was changed.',
  },
  error: {
    heading: "We couldn't use this link",
    body: 'Something went wrong on our side. Nothing was changed.',
  },
};

type View = { kind: 'ask' } | { kind: 'done' } | { kind: 'failed'; reason: NewsletterLinkFailure };

export default function NewsletterLinkPage({ action }: { action: NewsletterLinkAction }) {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const copy = COPY[action];
  const [view, setView] = useState<View>(() =>
    token ? { kind: 'ask' } : { kind: 'failed', reason: 'invalid' }
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  const act = async () => {
    setSaving(true);
    setSaveError(false);
    try {
      await (action === 'confirm' ? confirmNewsletter(token) : unsubscribeNewsletter(token));
      setView({ kind: 'done' });
    } catch (err) {
      const reason = err instanceof NewsletterLinkError ? err.reason : 'error';
      // A transient failure keeps the button to retry; a bad link explains why.
      if (reason === 'error') setSaveError(true);
      else setView({ kind: 'failed', reason });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <PageMeta title={`${copy.title} — Houseplant MD`} />
      <Card radius="lg" className="flex flex-col gap-4 p-8">
        {view.kind === 'ask' && (
          <>
            <h1 className="gt-h1 text-balance">{copy.ask}</h1>
            <p className="text-ink-2">{copy.explain}</p>
            {saveError && (
              <p role="alert" className="text-body-sm text-error">
                That didn&apos;t work just now. Please try again.
              </p>
            )}
            <div>
              <Button onClick={act} loading={saving} loadingText={copy.busy}>
                {copy.button}
              </Button>
            </div>
          </>
        )}

        {view.kind === 'done' && (
          <>
            <h1 className="gt-h1 text-balance">{copy.done}</h1>
            <p className="text-ink-2">{copy.doneBody}</p>
            <p>
              <Link to="/blog" className="font-semibold text-ink underline">
                Back to the blog
              </Link>
            </p>
          </>
        )}

        {view.kind === 'failed' && (
          <>
            <h1 className="gt-h1 text-balance">{FAILURE_COPY[view.reason].heading}</h1>
            <p className="text-ink-2">{FAILURE_COPY[view.reason].body}</p>
            {action === 'confirm' && view.reason !== 'rate_limited' && (
              <p className="text-body-sm text-ink-2">
                You can ask for a new link from the{' '}
                <Link to="/blog" className="font-semibold text-ink underline">
                  blog
                </Link>
                .
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
