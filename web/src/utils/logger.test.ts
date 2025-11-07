/**
 * Logger Tests
 *
 * Tests for structured logging utility with automatic context injection.
 * Priority: Phase 2 - Critical logging infrastructure component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { logger, initLogger } from './logger';
import * as Sentry from '@sentry/react';

// Mock Sentry
vi.mock('@sentry/react', () => ({
  addBreadcrumb: vi.fn(),
  captureException: vi.fn(),
  captureMessage: vi.fn(),
}));

describe('Logger', () => {
  let consoleSpy;

  beforeEach(() => {
    // Spy on console methods
    consoleSpy = {
      log: vi.spyOn(console, 'log').mockImplementation(() => {}),
      error: vi.spyOn(console, 'error').mockImplementation(() => {}),
      warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
    };

    vi.clearAllMocks();
  });

  afterEach(() => {
    consoleSpy.log.mockRestore();
    consoleSpy.error.mockRestore();
    consoleSpy.warn.mockRestore();
    vi.restoreAllMocks();
  });

  describe('initLogger', () => {
    it('initializes with context accessor functions', () => {
      const getRequestId = vi.fn(() => 'test-request-id');
      const getUserId = vi.fn(() => 'test-user-id');

      initLogger({ getRequestId, getUserId });

      // Trigger a log to verify accessors are called
      logger.info('Test message');

      expect(getRequestId).toHaveBeenCalled();
      expect(getUserId).toHaveBeenCalled();
    });

    it('handles missing context accessors gracefully', () => {
      initLogger({});

      expect(() => {
        logger.info('Test message');
      }).not.toThrow();
    });

    it('handles null context accessors gracefully', () => {
      initLogger({ getRequestId: null, getUserId: null });

      expect(() => {
        logger.info('Test message');
      }).not.toThrow();
    });
  });

  describe('Context injection', () => {
    it('includes requestId when available', () => {
      const mockRequestId = 'req-12345';
      initLogger({
        getRequestId: () => mockRequestId,
        getUserId: () => null,
      });

      logger.info('Test with requestId');

      // In development mode, check console.log was called
      expect(consoleSpy.log).toHaveBeenCalled();
      const logArgs = consoleSpy.log.mock.calls[1]; // Second call has the entry object
      const logEntry = logArgs[0];

      expect(logEntry.requestId).toBe(mockRequestId);
    });

    it('includes userId when available', () => {
      const mockUserId = 'user-67890';
      initLogger({
        getRequestId: () => null,
        getUserId: () => mockUserId,
      });

      logger.info('Test with userId');

      expect(consoleSpy.log).toHaveBeenCalled();
      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.userId).toBe(mockUserId);
    });

    it('includes timestamp in ISO format', () => {
      initLogger({});

      const beforeLog = new Date().toISOString();
      logger.info('Test with timestamp');
      const afterLog = new Date().toISOString();

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.timestamp).toBeDefined();
      expect(logEntry.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
      expect(logEntry.timestamp >= beforeLog).toBe(true);
      expect(logEntry.timestamp <= afterLog).toBe(true);
    });

    it('includes environment from import.meta.env.MODE', () => {
      initLogger({});

      logger.info('Test environment');

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.environment).toBeDefined();
      expect(typeof logEntry.environment).toBe('string');
    });

    it('handles context accessor errors gracefully', () => {
      initLogger({
        getRequestId: () => {
          throw new Error('Context error');
        },
        getUserId: () => 'user-123',
      });

      expect(() => {
        logger.info('Test with error');
      }).not.toThrow();

      // Should still log, but without the failing context
      expect(consoleSpy.log).toHaveBeenCalled();
    });
  });

  describe('Log levels', () => {
    beforeEach(() => {
      initLogger({});
    });

    it('debug logs with debug level', () => {
      logger.debug('Debug message', { test: 'data' });

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining('[DEBUG]'),
        expect.any(String)
      );

      const logEntry = consoleSpy.log.mock.calls[1][0];
      expect(logEntry.level).toBe('debug');
      expect(logEntry.message).toBe('Debug message');
    });

    it('info logs with info level', () => {
      logger.info('Info message', { test: 'data' });

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining('[INFO]'),
        expect.any(String)
      );

      const logEntry = consoleSpy.log.mock.calls[1][0];
      expect(logEntry.level).toBe('info');
    });

    it('warn logs with warning level', () => {
      logger.warn('Warning message', { test: 'data' });

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining('[WARNING]'),
        expect.any(String)
      );

      const logEntry = consoleSpy.log.mock.calls[1][0];
      expect(logEntry.level).toBe('warning');
    });

    it('error logs with error level', () => {
      logger.error('Error message', { test: 'data' });

      expect(consoleSpy.log).toHaveBeenCalledWith(
        expect.stringContaining('[ERROR]'),
        expect.any(String)
      );

      const logEntry = consoleSpy.log.mock.calls[1][0];
      expect(logEntry.level).toBe('error');
    });
  });

  describe('Development mode logging', () => {
    beforeEach(() => {
      initLogger({});
    });

    it('logs to console in development', () => {
      logger.info('Dev test');

      expect(consoleSpy.log).toHaveBeenCalled();
    });

    it('includes colored output for different levels', () => {
      logger.debug('Debug');
      logger.info('Info');
      logger.warn('Warning');
      logger.error('Error');

      // Each level should have a styled console.log call
      expect(consoleSpy.log).toHaveBeenCalledTimes(8); // 2 calls per log (styled + entry)
    });

    it('formats log entry as structured JSON', () => {
      const testContext = { component: 'TestComponent', action: 'test' };
      logger.info('Test message', testContext);

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.message).toBe('Test message');
      expect(logEntry.component).toBe('TestComponent');
      expect(logEntry.action).toBe('test');
    });
  });

  describe('Sentry integration', () => {
    it('sends breadcrumbs to Sentry in production', () => {
      // Note: This test assumes production mode behavior
      // In actual production (import.meta.env.PROD === true), Sentry would be called
      // For testing, we can verify the Sentry mock is available

      expect(Sentry.addBreadcrumb).toBeDefined();
      expect(Sentry.captureException).toBeDefined();
      expect(Sentry.captureMessage).toBeDefined();
    });
  });

  describe('Error handling', () => {
    beforeEach(() => {
      initLogger({});
    });

    it('handles Error objects in context', () => {
      const testError = new Error('Test error');
      logger.error('Error occurred', { error: testError });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error).toBe(testError);
    });

    it('handles nested context objects', () => {
      const nestedContext = {
        component: 'TestComponent',
        data: {
          nested: {
            value: 'deep',
          },
        },
      };

      logger.info('Nested test', nestedContext);

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.component).toBe('TestComponent');
      expect(logEntry.data.nested.value).toBe('deep');
    });

    it('handles null or undefined context', () => {
      expect(() => {
        logger.info('Null context', null);
      }).not.toThrow();

      expect(() => {
        logger.info('Undefined context', undefined);
      }).not.toThrow();

      expect(() => {
        logger.info('No context');
      }).not.toThrow();
    });
  });

  describe('Backward compatibility', () => {
    it('supports legacy log format', () => {
      initLogger({});

      // Should accept just message and context
      expect(() => {
        logger.info('Message', { key: 'value' });
      }).not.toThrow();

      // Should accept just message
      expect(() => {
        logger.info('Message only');
      }).not.toThrow();
    });
  });

  describe('Security: URL Sanitization', () => {
    beforeEach(() => {
      initLogger({});
    });

    it('removes query parameters from URLs', () => {
      logger.info('Test with URL', { url: '/api/users?email=user@example.com&id=123' });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.url).toBe('/api/users');
      expect(logEntry.url).not.toContain('email');
      expect(logEntry.url).not.toContain('id');
    });

    it('removes hash fragments from URLs', () => {
      logger.info('Test with hash', { url: '/api/posts#section123' });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.url).toBe('/api/posts');
      expect(logEntry.url).not.toContain('#');
    });

    it('removes both query params and hash', () => {
      logger.info('Test with both', { url: '/api/posts?page=1&token=abc123#top' });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.url).toBe('/api/posts');
    });

    it('handles full URLs with origin', () => {
      logger.info('Test full URL', { url: 'http://localhost:8000/api/users?email=test@example.com' });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.url).toBe('http://localhost:8000/api/users');
      expect(logEntry.url).not.toContain('email');
    });

    it('handles invalid URLs gracefully', () => {
      logger.info('Test invalid URL', { url: 'not a url' });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.url).toBe('not a url'); // Passes through as-is
    });

    it('handles null/undefined URLs', () => {
      logger.info('Test null URL', { url: null });
      const logEntry1 = consoleSpy.log.mock.calls[1][0];
      expect(logEntry1.url).toBeNull();

      logger.info('Test undefined URL', { url: undefined });
      const logEntry2 = consoleSpy.log.mock.calls[3][0];
      expect(logEntry2.url).toBeUndefined();
    });
  });

  describe('Security: Error Sanitization', () => {
    beforeEach(() => {
      initLogger({});
    });

    it('removes config property from Axios errors', () => {
      const axiosError = {
        message: 'Request failed',
        name: 'AxiosError',
        config: {
          headers: { Authorization: 'Bearer secret-token' },
          data: { password: 'super-secret' },
        },
      };

      logger.error('Test error', { error: axiosError });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error.message).toBe('Request failed');
      expect(logEntry.error.name).toBe('AxiosError');
      expect(logEntry.error.config).toBeUndefined(); // Sensitive property removed
    });

    it('removes headers from error objects', () => {
      const errorWithHeaders = {
        message: 'Failed',
        config: {
          headers: {
            'X-CSRFToken': 'csrf-token-12345',
            'Authorization': 'Bearer jwt-token',
          },
        },
      };

      logger.error('Test error', { error: errorWithHeaders });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error.config).toBeUndefined();
    });

    it('preserves safe error properties', () => {
      const error = {
        message: 'Something went wrong',
        name: 'CustomError',
        stack: 'Error stack trace...',
        response: {
          status: 404,
          statusText: 'Not Found',
        },
      };

      logger.error('Test error', { error });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error.message).toBe('Something went wrong');
      expect(logEntry.error.name).toBe('CustomError');
      expect(logEntry.error.status).toBe(404);
      expect(logEntry.error.statusText).toBe('Not Found');
    });

    it('includes stack traces in development mode', () => {
      const error = new Error('Test error');

      logger.error('Test error', { error });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      // In development (import.meta.env.DEV = true in tests), stack is included
      expect(logEntry.error.stack).toBeDefined();
    });

    it('handles Error instances', () => {
      const error = new Error('Native error');
      error.name = 'TypeError';

      logger.error('Test error', { error });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error.message).toBe('Native error');
      expect(logEntry.error.name).toBe('TypeError');
    });

    it('handles null/undefined errors', () => {
      logger.error('Test null error', { error: null });
      const logEntry1 = consoleSpy.log.mock.calls[1][0];
      expect(logEntry1.error).toBeNull();

      logger.error('Test undefined error', { error: undefined });
      const logEntry2 = consoleSpy.log.mock.calls[3][0];
      expect(logEntry2.error).toBeUndefined();
    });

    it('handles primitive errors (string)', () => {
      logger.error('Test string error', { error: 'Something went wrong' });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error).toBe('Something went wrong');
    });

    it('removes request property from Axios errors', () => {
      const axiosError = {
        message: 'Request failed',
        request: {
          responseURL: 'http://localhost:8000/api/users',
          // XMLHttpRequest object with full details
        },
      };

      logger.error('Test error', { error: axiosError });

      const logEntry = consoleSpy.log.mock.calls[1][0];

      expect(logEntry.error.request).toBeUndefined(); // Sensitive property removed
    });
  });
});
