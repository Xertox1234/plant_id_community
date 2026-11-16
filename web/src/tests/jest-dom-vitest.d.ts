/**
 * Types for the jest-dom matchers (toBeInTheDocument, toHaveAttribute, ...)
 * under Vitest 5.
 *
 * Vitest 5 changed `Assertion<T>` to `Assertion<R, T>`, so the augmentation
 * that @testing-library/jest-dom 7.0.1 ships (`interface Assertion<T = any>`)
 * no longer merges, and its jest-global fallback is gone too. `Matchers<R, T>`
 * is Vitest's extension point: `Assertion` and `expect.*` asymmetric matchers
 * both extend it. The type parameters below must stay identical to Vitest's
 * own declaration or the merge fails.
 *
 * Delete this file once jest-dom's `/vitest` types support Vitest 5, and
 * import `@testing-library/jest-dom/vitest` in setup.ts instead.
 */
import 'vitest';
import type { TestingLibraryMatchers } from '@testing-library/jest-dom/matchers';

declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Matchers<
    R extends void | Promise<void> = void | Promise<void>,
    T = unknown,
  > extends TestingLibraryMatchers<unknown, R> {}
}
