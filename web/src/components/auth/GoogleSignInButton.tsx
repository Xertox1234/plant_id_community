import { useState } from 'react';
import { getGoogleOAuthUrl } from '../../services/authService';
import { logger } from '../../utils/logger';

interface GoogleSignInButtonProps {
  /** Visible button label. Defaults to "Sign in with Google". */
  label?: string;
  /** Disable the button (e.g. while a sibling form is submitting). */
  disabled?: boolean;
}

/**
 * Google "G" logo. Marked aria-hidden — the button text carries the label.
 */
function GoogleLogo() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.79-.07-1.54-.2-2.27H12v4.51h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.88c2.27-2.09 3.57-5.17 3.57-8.87z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.88-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09A12 12 0 0 0 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29A7.2 7.2 0 0 1 4.89 12c0-.8.14-1.57.38-2.29V6.62H1.29A12 12 0 0 0 0 12c0 1.94.46 3.77 1.29 5.38l3.98-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  );
}

/**
 * Initiates the backend Google OAuth flow.
 *
 * On click it asks the backend for the Google authorization URL and redirects
 * the browser to it. The backend callback then sets JWT cookies and redirects
 * to /auth/google/callback, which is handled by GoogleCallbackPage.
 */
export default function GoogleSignInButton({
  label = 'Sign in with Google',
  disabled = false,
}: GoogleSignInButtonProps) {
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setError(null);
    setIsRedirecting(true);
    try {
      const oauthUrl = await getGoogleOAuthUrl();
      // Full-page navigation hands off to Google; no state reset needed.
      window.location.assign(oauthUrl);
    } catch (err) {
      logger.error('[GoogleSignInButton] Failed to start Google sign-in', { error: err });
      setError('Could not start Google sign-in. Please try again.');
      setIsRedirecting(false);
    }
  };

  return (
    <div className="space-y-2">
      {error && (
        <div
          className="p-3 bg-error/10 border border-error rounded-lg text-ink text-sm"
          role="alert"
        >
          {error}
        </div>
      )}
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || isRedirecting}
        className="w-full inline-flex items-center justify-center gap-3 rounded-lg border border-line bg-surface px-4 py-2 text-base font-medium text-ink transition-colors hover:bg-surface-2 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <GoogleLogo />
        {isRedirecting ? 'Redirecting…' : label}
      </button>
    </div>
  );
}
