import { useState, type FormEvent } from 'react';
import { Lock } from 'lucide-react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { ForumApiError, unlockForum } from '../../services/forumService';

interface ForumUnlockFormProps {
  slug: string;
  onUnlocked: () => void;
}

/**
 * The password form of a locked forum (todo 680; phpBB's forum password).
 * The unlock lasts for this browser session. Too many wrong passwords and
 * the backend answers 429 for a while.
 */
export default function ForumUnlockForm({ slug, onUnlocked }: ForumUnlockFormProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password) return;
    setSubmitting(true);
    setError(null);
    try {
      await unlockForum(slug, password);
      onUnlocked();
    } catch (err) {
      if (err instanceof ForumApiError && err.status === 429) {
        setError('Too many wrong passwords. Try again later.');
      } else if (err instanceof ForumApiError && err.status === 400) {
        setError('That password is not right.');
      } else if (err instanceof ForumApiError && (err.status === 401 || err.status === 403)) {
        setError('Sign in to open this forum.');
      } else {
        setError('Could not unlock the forum. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-card max-w-md">
      <form onSubmit={handleSubmit} noValidate>
        <p className="mb-3 flex items-center gap-2 text-ink-2">
          <Lock aria-hidden="true" className="h-4 w-4" />
          This forum needs a password.
        </p>
        <Input
          type="password"
          name="forum-password"
          label="Password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={error ?? undefined}
        />
        <Button type="submit" className="mt-3" loading={submitting} loadingText="Unlocking…">
          Unlock
        </Button>
      </form>
    </Card>
  );
}
