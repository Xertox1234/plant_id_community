import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import {
  AccountDeletionError,
  requestAccountDeletion,
} from '../../services/accountDeletionService';
import Button from '../ui/Button';
import ConfirmDialog from '../ui/ConfirmDialog';

export const DANGER_BUTTON_CLASS = 'border-error text-error hover:bg-error/10';

type Status = 'idle' | 'sending' | 'sent' | 'rate_limited' | 'error';

/**
 * Settings > Delete account. Nothing is deleted here: the button emails the
 * signed-in address a link, and the deletion is confirmed on /delete-account/confirm.
 */
export default function DeleteAccountSection() {
  const { user } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [status, setStatus] = useState<Status>('idle');

  const send = async () => {
    setConfirming(false);
    if (!user?.email) return;
    setStatus('sending');
    try {
      await requestAccountDeletion(user.email);
      setStatus('sent');
    } catch (err) {
      setStatus(
        err instanceof AccountDeletionError && err.code === 'rate_limited'
          ? 'rate_limited'
          : 'error'
      );
    }
  };

  return (
    <section className="p-screen" aria-labelledby="delete-account-heading">
      <h2
        id="delete-account-heading"
        className="font-sans font-semibold uppercase text-ink-3 text-micro leading-[1.4] tracking-[0.66px]"
      >
        Delete account
      </h2>
      <p className="mt-3 text-sm text-ink-3">
        This permanently deletes your account, plants, garden, scans and forum posts. It can&apos;t
        be undone.
      </p>
      <div className="mt-4">
        <Button
          variant="outline"
          className={DANGER_BUTTON_CLASS}
          onClick={() => setConfirming(true)}
          loading={status === 'sending'}
          loadingText="Sending…"
          disabled={!user?.email}
        >
          Email me a deletion link
        </Button>
      </div>
      <p role="status" className="mt-3 text-sm text-ink-2">
        {status === 'sent' && 'Check your email for a link to finish deleting your account.'}
      </p>
      {status === 'rate_limited' && (
        <p role="alert" className="mt-3 text-sm text-error">
          Too many requests, try again later.
        </p>
      )}
      {status === 'error' && (
        <p role="alert" className="mt-3 text-sm text-error">
          Something went wrong. Please try again.
        </p>
      )}
      <ConfirmDialog
        open={confirming}
        title="Email me a deletion link?"
        message={`We'll email a link to ${user?.email ?? 'your address'}. Your account is only deleted after you open it and confirm.`}
        confirmLabel="Send link"
        onConfirm={() => void send()}
        onCancel={() => setConfirming(false)}
      />
    </section>
  );
}
