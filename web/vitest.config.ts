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
    setupFiles: ['./src/tests/setup.js'],

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
      // Thresholds for failing tests if coverage is too low
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },

    // Test file patterns (now includes TypeScript)
    include: ['**/*.{test,spec}.{js,jsx,ts,tsx}'],

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
