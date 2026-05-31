import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

// Vitest configuration
// https://vitest.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  test: {
    // Testing environment (jsdom for React components)
    environment: 'jsdom',

    // Setup files to run before tests
    setupFiles: ['./src/tests/setup.ts'],

    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      exclude: [
        'node_modules/',
        'src/tests/',
        '**/*.test.{js,jsx,ts,tsx}',
        '**/*.spec.{js,jsx,ts,tsx}',
        '**/vite.config.{js,ts}',
        '**/vitest.config.{js,ts}',
      ],
      // Advisory thresholds — enforced locally when running `npm run test:coverage`
      // but NOT checked in CI (web-ci.yml runs `vitest --run` without --coverage).
      // Treat these as a local development signal, not a merge gate.
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },

    // Test file patterns (now includes TypeScript)
    // Only include src/ tests to exclude E2E tests (e2e/ uses Playwright)
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],

    // Global test settings
    globals: true,

    // Reporters (console output format)
    reporters: ['verbose'],

    // Timeout for tests (10 seconds)
    testTimeout: 10000,

    // Mock reset behavior
    mockReset: true,
    restoreMocks: true,
  },

  // Resolve configuration (same as vite.config.ts)
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
