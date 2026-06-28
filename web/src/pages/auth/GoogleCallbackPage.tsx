import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { logger } from '../../utils/logger';

/**
 * Readable messages for the backend's `?error=<code>` values
 * (see apps/users/oauth_views.py — oauth_callback).
 */
const ERROR_MESSAGES: Record<string, string> = {
  invalid_state: 'Your sign-in session expired or could not be verified. Please try again.',
  no_code: 'Google did not return an authorization code. Please try again.',
  user_data_failed: 'We could not read your Google profile. Please try again.',
  user_creation_failed: 'We could not finish creating your account. Please try again.',
  unsupported_provider: 'This sign-in method is not supported.',
  callback_failed: 'Something went wrong while signing you in. Please try again.',
  access_denied: 'You cancelled the Google sign-in.',
};

function messageForError(code: string | null): string {
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return 'Google sign-in failed. Please try again.';
}

/**
 * GoogleCallbackPage
 *
 * Landing page for the backend OAuth redirect
 * (`${FRONTEND_BASE_URL}/auth/google/callback?success=true | ?error=<code>`).
 * The backend has already set the JWT cookies by this point, so on success we
 * re-read the user into context (refreshUser) and route into the app; on error
 * we show the reason and offer a path back to /login.
 */
export default function GoogleCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { refreshUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  // Guard against the effect running twice (React 18 StrictMode double-invoke).
  const handledRef = useRef(false);

  useEffect(() => {
    if (handledRef.current) {
      return;
    }
    handledRef.current = true;

    const success = searchParams.get('success');
    const errorCode = searchParams.get('error');

    if (errorCode || success !== 'true') {
      setError(messageForError(errorCode));
      return;
    }

    (async () => {
      try {
        const user = await refreshUser();
        if (user) {
          navigate('/', { replace: true });
        } else {
          setError('We could not confirm your sign-in. Please try again.');
        }
      } catch (err) {
        logger.error('[GoogleCallbackPage] Failed to confirm session', { error: err });
        setError('We could not confirm your sign-in. Please try again.');
      }
    })();
  }, [searchParams, refreshUser, navigate]);

  if (error) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12 bg-surface">
        <div className="w-full max-w-md min-w-[280px] text-center">
          <div className="bg-surface-2 shadow-sm border border-line rounded-lg p-8 space-y-4">
            <h1 className="text-xl font-bold text-ink">Sign-in failed</h1>
            <div
              className="p-4 bg-error/10 border border-error rounded-lg text-ink text-sm"
              role="alert"
            >
              {error}
            </div>
            <Link
              to="/login"
              className="inline-block font-medium text-primary hover:text-primary/80 transition-colors"
            >
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <LoadingSpinner
      label="Signing you in…"
      className="min-h-[calc(100vh-4rem)] px-4 py-12 bg-surface"
    />
  );
}
