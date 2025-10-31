import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      // Enforce structured logger usage (no console.log/error/warn)
      // Exceptions: logger.js (implements logger), sentry.js (config warnings)
      'no-console': 'error',
    },
  },
  {
    files: ['**/*.test.{js,jsx}', '**/tests/**/*.{js,jsx}', '**/test/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  // Allow console in logger.js (implements the logger) and sentry.js (config warnings)
  {
    files: ['**/utils/logger.js', '**/config/sentry.js'],
    rules: {
      'no-console': 'off',
    },
  },
])
