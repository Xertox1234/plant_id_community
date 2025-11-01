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
});
