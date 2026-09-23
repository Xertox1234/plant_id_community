/**
 * requestId utility tests.
 *
 * These cases used to run through RequestProvider/useRequestId, which nothing
 * in the app read (every consumer calls getOrCreateRequestId directly). The
 * provider was removed in the 2026-09-23 dead-code audit (L12); the utility's
 * behaviour is pinned here instead.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getOrCreateRequestId, resetRequestId, rotateRequestId } from './requestId';

const mockUUID = 'test-uuid-1234-5678-abcd';
const mockRandomUUID = vi.fn(() => mockUUID);
const originalCrypto = global.crypto;

function breakSessionStorage() {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('QuotaExceededError');
  });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('QuotaExceededError');
  });
}

describe('requestId', () => {
  beforeEach(() => {
    sessionStorage.clear();
    resetRequestId();
    mockRandomUUID.mockClear().mockReturnValue(mockUUID);
    Object.defineProperty(global.crypto, 'randomUUID', {
      value: mockRandomUUID,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
    if (originalCrypto) {
      Object.defineProperty(global, 'crypto', {
        value: originalCrypto,
        writable: true,
        configurable: true,
      });
    }
  });

  it('generates a new request ID when sessionStorage is empty, and stores it', () => {
    expect(getOrCreateRequestId()).toBe(mockUUID);
    expect(mockRandomUUID).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem('requestId')).toBe(mockUUID);
  });

  it('returns the existing request ID from sessionStorage', () => {
    sessionStorage.setItem('requestId', 'existing-request-id-9999');

    expect(getOrCreateRequestId()).toBe('existing-request-id-9999');
    expect(mockRandomUUID).not.toHaveBeenCalled();
  });

  it('returns the same ID on repeated calls (persists across page refreshes)', () => {
    const first = getOrCreateRequestId();
    expect(getOrCreateRequestId()).toBe(first);
    expect(mockRandomUUID).toHaveBeenCalledTimes(1);
  });

  it('keeps a stable in-memory fallback when sessionStorage throws', () => {
    breakSessionStorage();

    const first = getOrCreateRequestId();
    expect(first).toBe(mockUUID);
    expect(getOrCreateRequestId()).toBe(first);
    expect(mockRandomUUID).toHaveBeenCalledTimes(1);
  });

  it('generates a new ID after sessionStorage is cleared and the cache reset', () => {
    const first = getOrCreateRequestId();
    sessionStorage.clear();
    resetRequestId();
    mockRandomUUID.mockReturnValueOnce('new-uuid-9999');

    const second = getOrCreateRequestId();
    expect(second).toBe('new-uuid-9999');
    expect(second).not.toBe(first);
  });

  it('rotateRequestId replaces the stored ID', () => {
    const first = getOrCreateRequestId();
    mockRandomUUID.mockReturnValueOnce('rotated-request-id-1234');

    expect(rotateRequestId()).toBe('rotated-request-id-1234');
    expect(getOrCreateRequestId()).toBe('rotated-request-id-1234');
    expect(sessionStorage.getItem('requestId')).not.toBe(first);
  });

  it('falls back to crypto.getRandomValues when randomUUID is not available', () => {
    const getRandomValues = vi.fn((array: Uint8Array) => {
      array.set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
      return array;
    });
    Object.defineProperty(global, 'crypto', {
      value: { getRandomValues },
      writable: true,
      configurable: true,
    });

    expect(getOrCreateRequestId()).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f');
    expect(getRandomValues).toHaveBeenCalledTimes(1);
  });

  it('falls back to a non-crypto request ID when Web Crypto is not available', () => {
    Object.defineProperty(global, 'crypto', {
      value: undefined,
      writable: true,
      configurable: true,
    });

    expect(getOrCreateRequestId()).toMatch(/^request-[a-z0-9]+-[a-z0-9]+$/);
  });
});
