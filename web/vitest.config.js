import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

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
        '**/*.test.{js,jsx}',
        '**/*.spec.{js,jsx}',
        '**/vite.config.js',
        '**/vitest.config.js',
      ],
      // Thresholds for failing tests if coverage is too low
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },

    // Test file patterns
    include: ['**/*.{test,spec}.{js,jsx}'],

    // Global test settings
    globals: true,

    // Reporters (console output format)
    reporters: ['verbose'],

    // Timeout for tests (10 seconds)
    testTimeout: 10000,

    // Mock reset behavior
    mockReset: true,
    restoreMocks: true,

    // Watch mode settings (for npm run test:watch)
    watch: {
      exclude: ['node_modules', 'dist'],
    },
  },

  // Resolve configuration (same as vite.config.js)
  resolve: {
    alias: {
      // Add path aliases if needed
      // '@': path.resolve(__dirname, './src'),
    },
  },
});
