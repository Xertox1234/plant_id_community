/**
 * RequestContext Tests
 *
 * Tests for distributed tracing request ID context.
 * Priority: Phase 2 - Critical logging infrastructure component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from 'react';
import { renderHook } from '@testing-library/react';
import { RequestProvider, useRequestId } from './RequestContext';
import { resetRequestId, rotateRequestId } from '../utils/requestId';

// Mock crypto.randomUUID
const mockUUID = 'test-uuid-1234-5678-abcd';
const mockRandomUUID = vi.fn(() => mockUUID);

// Store original crypto
const originalCrypto = global.crypto;

describe('RequestContext', () => {
  beforeEach(() => {
    // Clear sessionStorage before each test
    sessionStorage.clear();
    resetRequestId();
    vi.clearAllMocks();

    // Reset mock implementation
    mockRandomUUID.mockClear().mockReturnValue(mockUUID);

    // Mock crypto.randomUUID
    Object.defineProperty(global.crypto, 'randomUUID', {
      value: mockRandomUUID,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();

    // Restore original crypto
    if (originalCrypto) {
      Object.defineProperty(global, 'crypto', {
        value: originalCrypto,
        writable: true,
        configurable: true,
      });
    }

    // Restore original Storage prototype methods
    vi.unstubAllEnvs();
  });

  describe('RequestProvider', () => {
    it('generates new request ID when sessionStorage is empty', () => {
      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result.current).toBe(mockUUID);
      expect(mockRandomUUID).toHaveBeenCalledTimes(1);
      expect(sessionStorage.getItem('requestId')).toBe(mockUUID);
    });

    it('retrieves existing request ID from sessionStorage', () => {
      const existingId = 'existing-request-id-9999';
      sessionStorage.setItem('requestId', existingId);

      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result.current).toBe(existingId);
      expect(mockRandomUUID).not.toHaveBeenCalled();
    });

    it('persists request ID across multiple renders', () => {
      const { result, rerender } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      const firstId = result.current;

      // Rerender the hook
      rerender();

      expect(result.current).toBe(firstId);
      expect(sessionStorage.getItem('requestId')).toBe(firstId);
    });

    it('handles sessionStorage errors gracefully', () => {
      // Mock sessionStorage.getItem to throw error (private browsing mode)
      const originalGetItem = Storage.prototype.getItem;
      const originalSetItem = Storage.prototype.setItem;

      Storage.prototype.getItem = vi.fn(() => {
        throw new Error('QuotaExceededError');
      }) as typeof Storage.prototype.getItem;
      Storage.prototype.setItem = vi.fn(() => {
        throw new Error('QuotaExceededError');
      }) as typeof Storage.prototype.setItem;

      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      // Should still generate a UUID because sessionStorage.getItem throws,
      // triggering the in-memory fallback path.
      expect(result.current).toBeTruthy();
      expect(typeof result.current).toBe('string');

      // Restore original
      Storage.prototype.getItem = originalGetItem;
      Storage.prototype.setItem = originalSetItem;
    });

    it('keeps the fallback request ID stable across rerenders when sessionStorage fails', () => {
      // Mock sessionStorage.getItem to throw error (private browsing mode)
      const originalGetItem = Storage.prototype.getItem;
      const originalSetItem = Storage.prototype.setItem;

      Storage.prototype.getItem = vi.fn(() => {
        throw new Error('QuotaExceededError');
      }) as typeof Storage.prototype.getItem;
      Storage.prototype.setItem = vi.fn(() => {
        throw new Error('QuotaExceededError');
      }) as typeof Storage.prototype.setItem;

      const { result, rerender } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      const firstId = result.current;

      rerender();

      expect(result.current).toBe(firstId);
      expect(mockRandomUUID).toHaveBeenCalledTimes(1);

      Storage.prototype.getItem = originalGetItem;
      Storage.prototype.setItem = originalSetItem;
    });

    it('memoizes the request ID value', () => {
      const { result, rerender } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      const firstValue = result.current;
      rerender();
      const secondValue = result.current;

      // Should be the exact same reference (memoized)
      expect(firstValue).toBe(secondValue);
    });

    it('updates context consumers when the shared request ID rotates', () => {
      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      const firstId = result.current;
      const rotatedId = 'rotated-request-id-1234';
      mockRandomUUID.mockReturnValueOnce(rotatedId);

      act(() => {
        rotateRequestId();
      });

      expect(result.current).toBe(rotatedId);
      expect(result.current).not.toBe(firstId);
      expect(sessionStorage.getItem('requestId')).toBe(rotatedId);
    });
  });

  describe('useRequestId hook', () => {
    it('throws error when used outside RequestProvider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useRequestId());
      }).toThrow('useRequestId must be used within a RequestProvider');

      consoleSpy.mockRestore();
    });

    it('returns request ID when used within RequestProvider', () => {
      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result.current).toBeTruthy();
      expect(typeof result.current).toBe('string');
      expect(result.current.length).toBeGreaterThan(0);
    });
  });

  describe('UUID generation', () => {
    it('uses crypto.randomUUID when available', () => {
      // Clear sessionStorage to force new UUID generation
      sessionStorage.clear();

      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result.current).toBe(mockUUID);
      expect(mockRandomUUID).toHaveBeenCalled();
    });

    it('falls back to crypto.getRandomValues when randomUUID is not available', () => {
      sessionStorage.clear();

      const getRandomValues = vi.fn((array: Uint8Array) => {
        array.set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
        return array;
      });

      Object.defineProperty(global, 'crypto', {
        value: { getRandomValues },
        writable: true,
        configurable: true,
      });

      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result.current).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f');
      expect(getRandomValues).toHaveBeenCalledTimes(1);
    });

    it('falls back to a non-crypto request ID when Web Crypto is not available', () => {
      sessionStorage.clear();

      Object.defineProperty(global, 'crypto', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      const { result } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result.current).toMatch(/^request-[a-z0-9]+-[a-z0-9]+$/);
    });
  });

  describe('SessionStorage persistence', () => {
    it('persists across page refreshes', () => {
      // First render - generates new ID
      const { result: result1 } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });
      const firstId = result1.current;

      // Simulate page refresh by unmounting and remounting
      const { result: result2 } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      // Should retrieve the same ID from sessionStorage
      expect(result2.current).toBe(firstId);
    });

    it('clears when sessionStorage is cleared', () => {
      // Clear and generate first ID
      sessionStorage.clear();
      const { result: result1 } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });
      const firstId = result1.current;

      // Verify first ID was stored
      expect(sessionStorage.getItem('requestId')).toBe(firstId);

      // Clear sessionStorage
      sessionStorage.clear();

      // Mock a different UUID for the second generation
      const newMockUUID = 'new-uuid-9999';
      mockRandomUUID.mockReturnValueOnce(newMockUUID);

      // New render - should generate new ID
      const { result: result2 } = renderHook(() => useRequestId(), {
        wrapper: RequestProvider,
      });

      expect(result2.current).toBe(newMockUUID);
      expect(result2.current).not.toBe(firstId);
      expect(result2.current).toBeTruthy();
    });
  });
});
