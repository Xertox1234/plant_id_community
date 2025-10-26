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
}) {
  const inputId = name || label?.toLowerCase().replace(/\s+/g, '-')

  // Input styles - red border on error
  const inputStyles = error
    ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
    : 'border-gray-300 focus:border-green-500 focus:ring-green-500'

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <label
          htmlFor={inputId}
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          {label}
          {required && <span className="text-red-500 ml-1" aria-label="required">*</span>}
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
          text-gray-900 placeholder-gray-400
          focus:outline-none focus:ring-2 focus:ring-offset-0
          disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed
          transition-colors
          ${inputStyles}
        `}
        {...props}
      />

      {error && (
        <p
          id={`${inputId}-error`}
          className="mt-1 text-sm text-red-600"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  )
}
