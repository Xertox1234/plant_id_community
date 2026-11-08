/**
 * /delete-account — public. A visitor who cannot sign in (or deleted the app)
 * asks for a deletion link by email. The answer never says whether the address
 * has an account.
 */
import { useState, type FormEvent } from 'react';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Input from '../../components/ui/Input';
import PageMeta from '../../components/PageMeta';
import {
  AccountDeletionError,
  requestAccountDeletion,
} from '../../services/accountDeletionService';

type Status = 'idle' | 'sending' | 'sent' | 'rate_limited' | 'error';

export default function DeleteAccountPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>('idle');

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setStatus('sending');
    try {
      await requestAccountDeletion(email.trim());
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
    <div className="mx-auto max-w-xl px-4 py-16">
      <PageMeta title="Delete account — Houseplant MD" />
      <Card radius="lg" className="flex flex-col gap-4 p-8">
        <h1 className="gt-h1 text-balance">Delete your account</h1>
        <p className="text-ink-2">
          This permanently deletes your account, plants, garden, scans and forum posts. It
          can&apos;t be undone.
        </p>
        <p className="text-ink-2">
          Deleting your account doesn&apos;t cancel a Premium subscription. Cancel it in the App
          Store or Google Play.
        </p>
        <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <Input
            type="email"
            name="email"
            label="Email address"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <div>
            <Button type="submit" loading={status === 'sending'} loadingText="Sending…">
              Send deletion link
            </Button>
          </div>
        </form>
        <p role="status" className="text-ink-2">
          {status === 'sent' && "If an account exists for that address, we've sent a link."}
        </p>
        {status === 'rate_limited' && (
          <p role="alert" className="text-body-sm text-error">
            Too many requests, try again later.
          </p>
        )}
        {status === 'error' && (
          <p role="alert" className="text-body-sm text-error">
            Something went wrong. Please try again.
          </p>
        )}
      </Card>
    </div>
  );
}
