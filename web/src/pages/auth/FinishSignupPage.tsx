import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import Button from '../../components/ui/Button';
import ConsentCheckbox from '../../components/auth/ConsentCheckbox';
import { finishOAuthSignup, OAuthFinishError } from '../../services/authService';
import { logger } from '../../utils/logger';

const EXPIRED_MESSAGE = 'Your sign-up expired. Please sign in again.';
const RATE_LIMITED_MESSAGE = 'Too many attempts. Please wait a moment and try again.';
const GENERIC_MESSAGE = 'Something went wrong. Please try again.';

type Failure = { message: string; expired: boolean };

function toFailure(err: unknown): Failure {
  if (err instanceof OAuthFinishError) {
    // signup_failed (the account could not be created) reads the same to the
    // person: start over from the sign-in page.
    if (err.code === 'signup_expired' || err.code === 'signup_failed') {
      return { message: EXPIRED_MESSAGE, expired: true };
    }
    if (err.status === 429) return { message: RATE_LIMITED_MESSAGE, expired: false };
    if (err.code === 'consent_required') return { message: err.message, expired: false };
  }
  return { message: GENERIC_MESSAGE, expired: false };
}

/**
 * Last step of a first Google sign-up that arrived without consent. The backend
 * parked the verified Google profile in the session and redirected here; ticking
 * the box and pressing the button creates the account.
 */
export default function FinishSignupPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [accepted, setAccepted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!accepted || isSubmitting) return;
    setFailure(null);
    setIsSubmitting(true);
    try {
      await finishOAuthSignup();
      await refreshUser();
      navigate('/', { replace: true });
    } catch (err) {
      logger.error('[FinishSignupPage] Finish failed', { error: err });
      setFailure(toFailure(err));
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12 bg-surface">
      <div className="w-full max-w-md min-w-[280px]">
        <div className="text-center mb-8 space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-ink">One last step</h1>
          <p className="text-sm sm:text-base text-ink-3">
            Confirm the following to finish creating your account.
          </p>
        </div>

        <div className="bg-surface-2 shadow-sm border border-line rounded-lg p-8">
          <div
            aria-live="assertive"
            aria-atomic="true"
            className={
              failure
                ? 'mb-6 p-4 bg-error/10 border border-error rounded-lg text-ink text-sm'
                : 'sr-only'
            }
          >
            {failure?.message}
            {failure?.expired && (
              <>
                {' '}
                <Link to="/login" className="font-medium text-primary underline">
                  Sign in
                </Link>
              </>
            )}
          </div>
          <form onSubmit={handleSubmit} className="space-y-6">
            <ConsentCheckbox checked={accepted} onChange={setAccepted} disabled={isSubmitting} />
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={isSubmitting}
              disabled={!accepted || isSubmitting}
              className="w-full"
            >
              Finish signing up
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
