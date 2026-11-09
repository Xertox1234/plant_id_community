/**
 * /delete-account/confirm?token=… — public: the emailed signed token is the
 * credential. Opening the page changes nothing (mail scanners open links too);
 * only the button schedules the deletion.
 *
 * The token is read once into state and the URL is then replaced without it,
 * so the credential leaves the address bar and the history entry.
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import PageMeta from '../../components/PageMeta';
import { useAuth } from '../../contexts/AuthContext';
import {
  AccountDeletionError,
  confirmAccountDeletion,
} from '../../services/accountDeletionService';
import { DANGER_BUTTON_CLASS } from '../../components/ui/dangerButton';

const LINK_INVALID_COPY = 'This link has expired or was already used. Request a new one.';

type View =
  | { kind: 'ready'; failed: boolean }
  | { kind: 'done' }
  | { kind: 'problem'; message: string; newLink: boolean };

export default function ConfirmDeleteAccountPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  // Lazy: read once, before the replace below drops it from the URL.
  const [token] = useState(() => params.get('token') ?? '');
  const { clearLocalSession } = useAuth();
  useEffect(() => {
    if (params.has('token')) navigate('/delete-account/confirm', { replace: true });
  }, [params, navigate]);
  const [view, setView] = useState<View>(
    token
      ? { kind: 'ready', failed: false }
      : { kind: 'problem', message: LINK_INVALID_COPY, newLink: true }
  );
  const [saving, setSaving] = useState(false);

  const confirm = async () => {
    setSaving(true);
    try {
      await confirmAccountDeletion(token);
      // The server already cleared the cookies; drop the local session without
      // calling the logout endpoint.
      clearLocalSession();
      setView({ kind: 'done' });
    } catch (err) {
      if (err instanceof AccountDeletionError && err.code === 'link_invalid') {
        setView({ kind: 'problem', message: err.message, newLink: true });
      } else if (err instanceof AccountDeletionError && err.code === 'contact_support') {
        setView({ kind: 'problem', message: err.message, newLink: false });
      } else {
        setView({ kind: 'ready', failed: true });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <PageMeta title="Confirm account deletion — Houseplant MD" />
      <Card radius="lg" className="flex flex-col gap-4 p-8">
        {view.kind === 'ready' && (
          <>
            <h1 className="gt-h1 text-balance">Delete your account?</h1>
            <p className="text-ink-2">This permanently deletes:</p>
            <ul className="list-disc pl-6 text-ink-2">
              <li>your account and profile</li>
              <li>your plants and garden</li>
              <li>your scans and photos</li>
              <li>your forum posts</li>
            </ul>
            <p className="text-ink-2">It can&apos;t be undone.</p>
            {view.failed && (
              <p role="alert" className="text-body-sm text-error">
                We couldn&apos;t delete your account just now. Please try again.
              </p>
            )}
            <div>
              <Button
                variant="outline"
                className={DANGER_BUTTON_CLASS}
                onClick={() => void confirm()}
                loading={saving}
                loadingText="Deleting…"
              >
                Delete my account
              </Button>
            </div>
          </>
        )}

        {view.kind === 'done' && (
          <>
            <h1 className="gt-h1 text-balance">Account deletion scheduled</h1>
            <p role="status" className="text-ink-2">
              Your account is being deleted. You&apos;ll get an email when it&apos;s done.
            </p>
          </>
        )}

        {view.kind === 'problem' && (
          <>
            <h1 className="gt-h1 text-balance">We can&apos;t delete this account</h1>
            <p className="text-ink-2">{view.message}</p>
            {view.newLink && (
              <Link to="/delete-account" className="font-semibold text-ink underline">
                Request a new link
              </Link>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
