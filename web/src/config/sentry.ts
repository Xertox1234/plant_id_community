/**
 * Sentry Configuration
 *
 * Initializes Sentry for production error tracking.
 * Only active in production builds (import.meta.env.PROD).
 *
 * Environment Variables Required:
 * - VITE_SENTRY_DSN: Sentry Data Source Name (DSN)
 *   Get from: https://sentry.io/settings/projects/your-project/keys/
 *
 * @example
 * // In .env.production:
 * VITE_SENTRY_DSN=https://your-dsn@sentry.io/your-project-id
 */

import * as Sentry from '@sentry/react';
import type { BrowserOptions, Event, EventHint } from '@sentry/react';
import { logger } from '../utils/logger';

/**
 * Initialize Sentry error tracking
 * Call this once at app startup (main.tsx)
 */
export function initSentry(): void {
  // Only initialize in production
  if (!import.meta.env.PROD) {
    return;
  }

  const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;

  // If DSN not configured, log warning but don't fail
  // Note: This warning only appears in production if DSN is missing
  if (!sentryDsn) {
    if (import.meta.env.DEV) {
      // In development, we expect DSN to be missing, so no warning needed
      logger.info('Running in development mode - error tracking disabled', {
        component: 'SentryConfig',
        context: { mode: import.meta.env.MODE },
      });
    } else {
      // In production, missing DSN is a configuration issue
      logger.warn('VITE_SENTRY_DSN not configured - error tracking disabled', {
        component: 'SentryConfig',
        context: {
          mode: import.meta.env.MODE,
          remediation: 'Set VITE_SENTRY_DSN in .env.production to enable error tracking',
        },
      });
    }
    return;
  }

  const options: BrowserOptions = {
    dsn: sentryDsn,

    // Set environment (production, staging, etc.)
    environment: import.meta.env.MODE || 'production',

    // Performance monitoring (adjust as needed)
    tracesSampleRate: 0.1, // 10% of transactions

    // Release tracking (optional - useful for sourcemaps)
    // release: import.meta.env.VITE_APP_VERSION,

    // Ignore common errors that aren't actionable
    ignoreErrors: [
      // Browser extension errors
      'top.GLOBALS',
      'chrome-extension://',
      'moz-extension://',

      // Network errors (user's connection issue)
      'NetworkError',
      'Network request failed',

      // Cancelled requests (user navigated away)
      'AbortError',
    ],

    // Filter out non-error events
    beforeSend(event, hint): typeof event | null {
      // Don't send events without an exception
      if (!hint.originalException) {
        return null;
      }

      return event;
    },

    // Integration configuration
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        // Privacy settings for session replay
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],

    // Session replay configuration (optional - can be expensive)
    replaysSessionSampleRate: 0.1, // 10% of sessions
    replaysOnErrorSampleRate: 1.0, // 100% of sessions with errors
  };

  Sentry.init(options);
}

export default Sentry;
