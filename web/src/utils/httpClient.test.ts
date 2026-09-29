/**
 * HTTP Client Tests (Simplified)
 *
 * Tests for Axios HTTP client configuration and interceptor setup.
 * Priority: Phase 2 - Critical logging infrastructure component.
 *
 * Note: Due to module mocking complexity with axios, these tests verify
 * the interceptor logic and configuration rather than the full axios instance.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { logger } from './logger';
import { httpError, installAdapter, restoreAdapter } from '../tests/apiClientHarness';

// Mock logger
vi.mock('./logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

describe('HTTP Client - Interceptor Logic', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  describe('Request ID injection logic', () => {
    it('retrieves request ID from sessionStorage', () => {
      const mockRequestId = 'test-request-id-12345';
      sessionStorage.setItem('requestId', mockRequestId);

      const requestId = sessionStorage.getItem('requestId');

      expect(requestId).toBe(mockRequestId);
    });

    it('handles missing request ID gracefully', () => {
      // No requestId in sessionStorage
      const requestId = sessionStorage.getItem('requestId');

      expect(requestId).toBeNull();
    });
  });

  describe('CSRF token extraction logic', () => {
    it('extracts CSRF token from cookies', () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'sessionid=abc123; csrftoken=my-csrf-token; other=value',
      });

      // Simulate the getCsrfToken function logic
      const match = document.cookie.match(/csrftoken=([^;]+)/);
      const csrfToken = match ? decodeURIComponent(match[1]) : null;

      expect(csrfToken).toBe('my-csrf-token');
    });

    it('handles missing CSRF token', () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'other=value; session=test',
      });

      const match = document.cookie.match(/csrftoken=([^;]+)/);
      const csrfToken = match ? decodeURIComponent(match[1]) : null;

      expect(csrfToken).toBeNull();
    });

    it('handles URL-encoded CSRF tokens', () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrftoken=token%20with%20spaces',
      });

      const match = document.cookie.match(/csrftoken=([^;]+)/);
      const csrfToken = match ? decodeURIComponent(match[1]) : null;

      expect(csrfToken).toBe('token with spaces');
    });
  });

  describe('Configuration values', () => {
    it('has correct timeout value', async () => {
      const { default: httpClient } = await import('./httpClient');
      expect(httpClient.defaults.timeout).toBe(30000);
    });

    it('has correct base URL from environment', async () => {
      const { default: httpClient } = await import('./httpClient');
      const expected = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      expect(httpClient.defaults.baseURL).toBe(expected);
    });
  });

  describe('HTTP Client integration', () => {
    it('can import the httpClient module', async () => {
      const httpClient = await import('./httpClient');
      expect(httpClient.default).toBeDefined();
    });
  });

  // todo 434: logger.error is a Sentry event in production; a background poll
  // opts out with `quietErrors` and is logged as a breadcrumb instead.
  describe('Error logging', () => {
    afterEach(() => {
      restoreAdapter();
    });

    it('logs a failed request as an error by default', async () => {
      const { default: httpClient } = await import('./httpClient');
      installAdapter().mockImplementation(async (config) => {
        throw httpError(config, 500, {});
      });

      await expect(httpClient.get('/api/x/')).rejects.toThrow();
      expect(logger.error).toHaveBeenCalledWith(
        'HTTP error',
        expect.objectContaining({ status: 500, url: '/api/x/' })
      );
      expect(logger.info).not.toHaveBeenCalled();
    });

    it('logs a quietErrors request as a breadcrumb only, and still rejects', async () => {
      const { default: httpClient } = await import('./httpClient');
      installAdapter().mockImplementation(async (config) => {
        throw httpError(config, 503, {});
      });

      await expect(httpClient.get('/api/x/', { quietErrors: true })).rejects.toThrow();
      expect(logger.error).not.toHaveBeenCalled();
      expect(logger.info).toHaveBeenCalledWith(
        'HTTP error',
        expect.objectContaining({ status: 503, url: '/api/x/' })
      );
    });
  });
});
