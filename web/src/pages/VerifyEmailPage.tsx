/**
 * Email verification (todo 446).
 *
 * - /verify-email?key=<signed key> — where the link in the verification email
 *   lands. Opening the page changes nothing, because mail scanners open links
 *   too; only the button confirms. Confirming also needs the session of the
 *   account the key names. Otherwise a victim clicking the link in their inbox
 *   would verify an attacker's pre-registered account. So a signed-out visitor
 *   is asked to sign in, and the card names the account being confirmed.
 * - /verify-email (no key) — where signup lands: "check your inbox", plus a
 *   resend button for the signed-in user.
 */
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import PageMeta from '../components/PageMeta';
import { useAuth } from '../contexts/AuthContext';
import {
  VerificationError,
  confirmEmailVerification,
  resendVerificationEmail,
} from '../services/emailVerificationService';

type ResendState = 'idle' | 'sending' | 'sent' | 'already' | 'failed' | 'limit';

function ResendLink() {
  const { user } = useAuth();
  const [state, setState] = useState<ResendState>('idle');

  if (!user) {
    return (
      <p className="text-body-sm text-ink-2">
        <Link to="/login" className="font-semibold text-ink underline">
          Sign in
        </Link>{' '}
        to get a new link.
      </p>
    );
  }

  const resend = async () => {
    setState('sending');
    try {
      const result = await resendVerificationEmail();
      setState(
        result.verified
          ? 'already'
          : result.sent
            ? 'sent'
            : result.limit_reached
              ? 'limit'
              : 'failed'
      );
    } catch {
      setState('failed');
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button
          variant="secondary"
          onClick={resend}
          loading={state === 'sending'}
          loadingText="Sending…"
          disabled={state === 'sent' || state === 'already' || state === 'limit'}
        >
          Send a new link
        </Button>
      </div>
      <p role="status" className="text-body-sm text-ink-2">
        {state === 'sent' && `We sent a new link to ${user.email}.`}
        {state === 'already' && 'Your email is already confirmed.'}
        {state === 'failed' && "We couldn't send a new link just now. Please try again later."}
        {state === 'limit' &&
          "We've already sent this account as many links as we can. Check your spam folder for an earlier one."}
      </p>
    </div>
  );
}

function CheckInbox() {
  const { user } = useAuth();
  return (
    <>
      <h1 className="gt-h1 text-balance">Confirm your email</h1>
      <p className="text-ink-2">
        We sent a link to {user?.email ? <strong>{user.email}</strong> : 'your email address'}. Open
        it and press the button to confirm the address is yours. Your account works in the meantime.
      </p>
      <ResendLink />
    </>
  );
}

type ConfirmView = 'ask' | 'done' | 'invalid' | 'signin';

function SignInFirst() {
  return (
    <>
      <h1 className="gt-h1 text-balance">Sign in to confirm your email</h1>
      <p className="text-ink-2">
        <Link to="/login" className="font-semibold text-ink underline">
          Sign in
        </Link>{' '}
        to the account this email is for, then open the link in the email again.
      </p>
    </>
  );
}

function ConfirmKey({ verificationKey }: { verificationKey: string }) {
  const { user } = useAuth();
  const [view, setView] = useState<ConfirmView>('ask');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  const confirm = async () => {
    setSaving(true);
    setSaveError(false);
    try {
      await confirmEmailVerification(verificationKey);
      setView('done');
    } catch (err) {
      if (err instanceof VerificationError && err.reason === 'invalid') setView('invalid');
      else if (err instanceof VerificationError && err.reason === 'signin') setView('signin');
      else setSaveError(true);
    } finally {
      setSaving(false);
    }
  };

  if (view === 'done') {
    return (
      <>
        <h1 className="gt-h1 text-balance">Your email is confirmed</h1>
        <p className="text-ink-2">Thanks. You can close this page.</p>
        <p>
          <Link to="/" className="font-semibold text-ink underline">
            Go to Houseplant MD
          </Link>
        </p>
      </>
    );
  }

  if (!user || view === 'signin') return <SignInFirst />;

  if (view === 'invalid') {
    return (
      <>
        <h1 className="gt-h1 text-balance">This link doesn&apos;t work</h1>
        <p className="text-ink-2">
          It may have expired (links last 3 days), already been used, or be for a different account
          than the one you&apos;re signed in to.
        </p>
        <ResendLink />
      </>
    );
  }

  return (
    <>
      <h1 className="gt-h1 text-balance">Confirm your email address?</h1>
      <p className="text-ink-2">
        Confirm that <strong>{user.email}</strong> belongs to the account you&apos;re signed in to
        {user.username ? (
          <>
            , <strong>{user.username}</strong>
          </>
        ) : null}
        .
      </p>
      {saveError && (
        <p role="alert" className="text-body-sm text-error">
          We couldn&apos;t confirm your email just now. Please try again.
        </p>
      )}
      <div>
        <Button onClick={confirm} loading={saving} loadingText="Confirming…">
          Confirm my email
        </Button>
      </div>
    </>
  );
}

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const key = params.get('key') ?? '';

  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <PageMeta title="Confirm your email — Houseplant MD" />
      <Card radius="lg" className="flex flex-col gap-4 p-8">
        {key ? <ConfirmKey verificationKey={key} /> : <CheckInbox />}
      </Card>
    </div>
  );
}
