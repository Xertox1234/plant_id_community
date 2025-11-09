import { useCallback } from 'react';
import { FallbackProps } from 'react-error-boundary';

/**
 * Error Fallback Component
 *
 * Displayed when an error is caught by the ErrorBoundary.
 * Provides user-friendly error message and recovery options.
 */
export function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const handleReload = useCallback(() => {
    window.location.href = '/';
  }, []);

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-50 px-4"
      role="alert"
    >
      <div className="max-w-md w-full bg-white rounded-lg shadow-xl p-8 text-center">
        {/* Error Icon */}
        <div className="mb-6">
          <svg
            className="mx-auto h-16 w-16 text-red-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Error Message */}
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Oops! Something went wrong
        </h1>
        <p className="text-gray-600 mb-6">
          We encountered an unexpected error. Don't worry, your data is safe.
        </p>

        {/* Error Details (only in development) */}
        {import.meta.env.DEV && error && (
          <details className="mb-6 text-left">
            <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900 mb-2">
              Technical Details
            </summary>
            <div className="bg-gray-100 rounded p-4 text-xs text-gray-800 font-mono overflow-auto max-h-40">
              <p className="font-bold mb-2">{error.message}</p>
              {error.stack && (
                <pre className="whitespace-pre-wrap break-words">
                  {error.stack}
                </pre>
              )}
            </div>
          </details>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={resetErrorBoundary}
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium shadow-md hover:shadow-lg"
            aria-label="Try again to recover from the error"
          >
            Try Again
          </button>
          <button
            onClick={handleReload}
            className="px-6 py-3 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors font-medium"
            aria-label="Go to home page"
          >
            Go Home
          </button>
        </div>

        {/* Help Text */}
        <p className="mt-6 text-sm text-gray-500">
          If this problem persists, please{' '}
          <a
            href="mailto:support@plantcommunity.com"
            className="text-green-600 hover:text-green-700 underline"
          >
            contact support
          </a>
        </p>
      </div>
    </div>
  );
}
