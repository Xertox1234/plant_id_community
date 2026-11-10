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
import { scrubBreadcrumb, scrubEvent, scrubRecordingEvent } from './sentryScrub';

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

  const openedWithQueryOrFragment = window.location.search !== '' || window.location.hash !== '';

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

      return scrubEvent(event);
    },

    // Query strings and fragments never leave the browser: three pages take a
    // single-use token in their address (see sentryScrub.ts).
    beforeSendTransaction: (event) => scrubEvent(event),
    beforeBreadcrumb: (breadcrumb) => scrubBreadcrumb(breadcrumb),

    // Integration configuration
    integrations: [
      Sentry.browserTracingIntegration(),
      // The replay library reads `location.href` itself for every snapshot
      // and passes only custom events to `beforeAddRecordingEvent`, so that
      // address cannot be scrubbed. A page opened with a query string or a
      // fragment (every emailed token link is one) is not recorded at all.
      // Checked once, at load: a token link is always a fresh page load.
      ...(openedWithQueryOrFragment
        ? []
        : [
            Sentry.replayIntegration({
              // Privacy settings for session replay
              maskAllText: true,
              blockAllMedia: true,
              beforeAddRecordingEvent: (event) => scrubRecordingEvent(event),
            }),
          ]),
    ],

    // Session replay configuration (optional - can be expensive)
    replaysSessionSampleRate: 0.1, // 10% of sessions
    replaysOnErrorSampleRate: 1.0, // 100% of sessions with errors
  };

  Sentry.init(options);

  // A replay's own event lists the pages visited; the hooks above do not see it.
  Sentry.addEventProcessor((event) => (event.type === 'replay_event' ? scrubEvent(event) : event));
}

export default Sentry;
