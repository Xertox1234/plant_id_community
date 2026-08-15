/**
 * Button Component
 *
 * Reusable button with multiple variants, sizes, and states.
 * Supports loading state with visual feedback.
 *
 * @example
 * <Button variant="primary" size="md" onClick={handleClick}>
 *   Click me
 * </Button>
 *
 * @example
 * <Button variant="secondary" loading={isSubmitting} disabled>
 *   Submitting...
 * </Button>
 */

import { ButtonHTMLAttributes, ReactNode } from 'react';
import { buttonClassNames, type ButtonSize, type ButtonVariant } from './buttonStyles';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /**
   * Label shown in place of `children` while `loading` (e.g. "Posting…").
   * A visible label swap is the most reliable "busy" signal for screen readers
   * (audit 2026-07-11 L11); `aria-busy` is set alongside it either way.
   */
  loadingText?: ReactNode;
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  loadingText,
  disabled = false,
  type = 'button',
  onClick,
  className = '',
  ...props
}: ButtonProps) {
  const combinedClassName = buttonClassNames(variant, size, className);

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={combinedClassName}
      {...props}
    >
      {loading && (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {loading && loadingText !== undefined ? loadingText : children}
    </button>
  );
}
