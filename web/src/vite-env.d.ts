/// <reference types="vite/client" />

/**
 * TypeScript type definitions for Vite environment variables
 *
 * All environment variables must be prefixed with VITE_ to be exposed to the client.
 * See: https://vite.dev/guide/env-and-mode.html
 */

interface ImportMetaEnv {
  /**
   * Backend API base URL
   * @example "http://localhost:8000"
   */
  readonly VITE_API_URL: string;

  /**
   * Optional Sentry DSN for error tracking
   * @example "https://examplePublicKey@o0.ingest.sentry.io/0"
   */
  readonly VITE_SENTRY_DSN?: string;

  /**
   * Environment mode (automatically set by Vite)
   * @example "development" | "production" | "test"
   */
  readonly MODE: string;

  /**
   * Is development mode?
   */
  readonly DEV: boolean;

  /**
   * Is production mode?
   */
  readonly PROD: boolean;

  /**
   * Is server-side rendering?
   */
  readonly SSR: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
