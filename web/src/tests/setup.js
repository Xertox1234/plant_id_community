/**
 * Vitest Setup File
 *
 * This file runs before all tests to configure the testing environment.
 * It sets up DOM polyfills, global mocks, and test utilities.
 */

import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Cleanup after each test case (e.g., clearing jsdom)
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia (not available in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // Deprecated
    removeListener: vi.fn(), // Deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IntersectionObserver (not available in jsdom)
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
};

// Mock ResizeObserver (not available in jsdom)
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
};

// Mock scrollTo (not available in jsdom)
window.scrollTo = vi.fn();

// Mock HTMLElement.prototype.scrollIntoView
HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock navigator.share (for share button tests)
if (!navigator.share) {
  navigator.share = vi.fn().mockResolvedValue(undefined);
}

// Mock navigator.clipboard (for copy functionality tests)
if (!navigator.clipboard) {
  navigator.clipboard = {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
  };
}

// Suppress console errors during tests (optional - comment out to see errors)
// global.console = {
//   ...console,
//   error: vi.fn(),
//   warn: vi.fn(),
// };

// Add custom matchers if needed
// expect.extend({
//   toBeValidUrl(received) {
//     const pass = /^https?:\/\/.+/.test(received);
//     return {
//       pass,
//       message: () => `expected ${received} to be a valid URL`,
//     };
//   },
// });
