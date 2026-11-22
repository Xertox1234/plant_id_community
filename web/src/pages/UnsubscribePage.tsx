/**
 * Email unsubscribe (todo 408) — where the "Unsubscribe" link in our email
 * lands: /unsubscribe?token=<signed token>.
 *
 * Opening the page changes nothing (mail scanners open links too); only the
 * buttons do. Besides the link's own list, every link can stop all optional
 * email in one step (todo 703: CASL and CAN-SPAM). Public on purpose: the signed token is the credential, so it
 * works signed out, and every outcome points at Settings, where the same
 * choice can be changed back.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import PageMeta from '../components/PageMeta';
import { useOneTimeSearchParam } from '../hooks/useOneTimeSearchParam';
import {
  ALL_OPTIONAL_LIST,
  UnsubscribeError,
  checkUnsubscribe,
  confirmUnsubscribe,
  stopAllOptionalEmail,
  type EmailListState,
  type UnsubscribeFailure,
} from '../services/unsubscribeService';

type View =
  | { kind: 'loading' }
  | { kind: 'confirm'; state: EmailListState }
  | { kind: 'already'; state: EmailListState }
  | { kind: 'done'; state: EmailListState }
  | { kind: 'failed'; reason: UnsubscribeFailure };

function failureReason(err: unknown): UnsubscribeFailure {
  return err instanceof UnsubscribeError ? err.reason : 'error';
}

function SettingsLink() {
  return (
    <p className="text-body-sm text-ink-2">
      You can change which emails you get at any time in{' '}
      <Link to="/settings" className="font-semibold text-ink underline">
        Settings
      </Link>
      .
    </p>
  );
}

const FAILURE_COPY: Record<UnsubscribeFailure, { heading: string; body: string }> = {
  invalid: {
    heading: "This link isn't valid",
    body: 'It may have been copied incompletely. Nothing about your email was changed.',
  },
  expired: {
    heading: 'This link has expired',
    body: 'Unsubscribe links stop working after a while. Nothing about your email was changed.',
  },
  error: {
    heading: "We couldn't load this link",
    body: 'Something went wrong on our side. Nothing about your email was changed.',
  },
};

export default function UnsubscribePage() {
  // Held in state and stripped from the address bar once read (todo 706 M7).
  const token = useOneTimeSearchParam('token');
  const [view, setView] = useState<View>(() =>
    token ? { kind: 'loading' } : { kind: 'failed', reason: 'invalid' }
  );
  const [attempt, setAttempt] = useState(0);
  const [saving, setSaving] = useState<'one' | 'all' | null>(null);
  const [saveError, setSaveError] = useState(false);

  useEffect(() => {
    if (!token) return;
    let ignore = false;
    checkUnsubscribe(token)
      .then((state) => {
        if (!ignore) setView({ kind: state.subscribed ? 'confirm' : 'already', state });
      })
      .catch((err: unknown) => {
        if (!ignore) setView({ kind: 'failed', reason: failureReason(err) });
      });
    return () => {
      ignore = true;
    };
  }, [token, attempt]);

  const retry = () => {
    setView({ kind: 'loading' });
    setAttempt((n) => n + 1);
  };

  const act = useCallback(
    async (scope: 'one' | 'all') => {
      setSaving(scope);
      setSaveError(false);
      try {
        const state = await (scope === 'all'
          ? stopAllOptionalEmail(token)
          : confirmUnsubscribe(token));
        setView({ kind: 'done', state });
      } catch (err) {
        const reason = failureReason(err);
        // A link that went bad between loading and clicking (it expired) gets
        // the full explanation; a transient failure keeps the button to retry.
        if (reason === 'error') setSaveError(true);
        else setView({ kind: 'failed', reason });
      } finally {
        setSaving(null);
      }
    },
    [token]
  );

  // Offered with every link whose own list is narrower than "everything".
  const stopAll = (state: EmailListState) =>
    state.list === ALL_OPTIONAL_LIST ? null : (
      <div className="flex flex-col gap-2 border-t border-line pt-4">
        <p className="text-body-sm text-ink-2">
          Or stop every optional email from Houseplant MD: forum notifications, the forum digest and
          the blog newsletter. Account email, such as password resets, still arrives.
        </p>
        <div>
          <Button
            variant="secondary"
            onClick={() => act('all')}
            loading={saving === 'all'}
            disabled={saving !== null}
            loadingText="Stopping…"
          >
            Stop all optional email
          </Button>
        </div>
      </div>
    );

  const saveErrorLine = saveError && (
    <p role="alert" className="text-body-sm text-error">
      We couldn&apos;t unsubscribe you just now. Please try again.
    </p>
  );

  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <PageMeta title="Unsubscribe — Houseplant MD" />
      <Card radius="lg" className="flex flex-col gap-4 p-8">
        {view.kind === 'loading' && <LoadingSpinner />}

        {view.kind === 'confirm' && (
          <>
            <h1 className="gt-h1 text-balance">Unsubscribe from this email?</h1>
            <p className="text-ink-2">You&apos;ll stop getting:</p>
            <p className="font-semibold text-ink">{view.state.label}</p>
            {saveErrorLine}
            <div>
              <Button
                onClick={() => act('one')}
                loading={saving === 'one'}
                disabled={saving !== null}
                loadingText="Unsubscribing…"
              >
                Unsubscribe
              </Button>
            </div>
            {stopAll(view.state)}
            <SettingsLink />
          </>
        )}

        {view.kind === 'already' && (
          <>
            <h1 className="gt-h1 text-balance">You&apos;re already unsubscribed</h1>
            <p className="text-ink-2">
              You don&apos;t get this email:{' '}
              <span className="font-semibold">{view.state.label}</span>.
            </p>
            {saveErrorLine}
            {stopAll(view.state)}
            <SettingsLink />
          </>
        )}

        {view.kind === 'done' && (
          <>
            <h1 className="gt-h1 text-balance">You&apos;re unsubscribed</h1>
            <p className="text-ink-2">
              We won&apos;t send this email any more:{' '}
              <span className="font-semibold">{view.state.label}</span>.
            </p>
            {saveErrorLine}
            {stopAll(view.state)}
            <SettingsLink />
          </>
        )}

        {view.kind === 'failed' && (
          <>
            <h1 className="gt-h1 text-balance">{FAILURE_COPY[view.reason].heading}</h1>
            <p className="text-ink-2">{FAILURE_COPY[view.reason].body}</p>
            {view.reason === 'error' && (
              <div>
                <Button variant="secondary" onClick={retry}>
                  Try again
                </Button>
              </div>
            )}
            <SettingsLink />
          </>
        )}
      </Card>
    </div>
  );
}
