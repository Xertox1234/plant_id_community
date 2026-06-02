/**
 * Input Component
 *
 * Reusable input field with label, error message, and required indicator.
 * Supports text, email, password, and other HTML5 input types.
 *
 * @example
 * <Input
 *   type="email"
 *   label="Email address"
 *   value={email}
 *   onChange={(e) => setEmail(e.target.value)}
 *   error={errors.email}
 *   required
 * />
 */

import { InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export default function Input({
  type = 'text',
  label,
  name,
  value,
  onChange,
  error,
  required = false,
  placeholder,
  disabled = false,
  className = '',
  ...props
}: InputProps) {
  const inputId = name || label?.toLowerCase().replace(/\s+/g, '-');

  // Input styles - red border on error
  const inputStyles = error
    ? 'border-error focus:border-error focus:ring-error'
    : 'border-line-2 focus:border-primary focus:ring-primary';

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-ink-2 mb-1">
          {label}
          {required && (
            <span className="text-error ml-1" aria-label="required">
              *
            </span>
          )}
        </label>
      )}

      <input
        type={type}
        id={inputId}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className={`
          block w-full px-3 py-2
          border rounded-lg
          text-ink placeholder-ink-3
          focus:outline-none focus:ring-2 focus:ring-offset-0
          disabled:bg-surface-2 disabled:text-ink-3 disabled:cursor-not-allowed
          transition-colors
          ${inputStyles}
        `}
        {...props}
      />

      {error && (
        <p id={`${inputId}-error`} className="mt-1 text-sm text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
