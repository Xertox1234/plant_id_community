import { useState, FormEvent, ChangeEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { getEmailError, getPasswordError } from '../../utils/validation'
import { sanitizeInput, sanitizeError } from '../../utils/sanitize'
import { logger } from '../../utils/logger'

interface FormData {
  email: string
  password: string
}

interface FormErrors {
  email?: string
  password?: string
}

interface LocationState {
  from?: {
    pathname: string
  }
}

/**
 * LoginPage Component
 *
 * User login page with email/password authentication.
 * Features:
 * - Form validation with real-time feedback
 * - Loading state during submission
 * - Error handling for failed authentication
 * - Redirects to intended destination or home after login
 * - Link to signup page for new users
 */
export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  // Get the page user was trying to access (for redirect after login)
  const from = (location.state as LocationState)?.from?.pathname || '/'

  const [formData, setFormData] = useState<FormData>({
    email: '',
    password: '',
  })

  const [errors, setErrors] = useState<FormErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  /**
   * Handle input changes and clear field-specific errors
   */
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target

    // Sanitize input to prevent XSS
    const sanitizedValue = sanitizeInput(value)

    setFormData((prev) => ({
      ...prev,
      [name]: sanitizedValue,
    }))

    // Clear error for this field when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({
        ...prev,
        [name]: undefined,
      }))
    }

    // Clear server error when user modifies form
    if (serverError) {
      setServerError(null)
    }
  }

  /**
   * Validate form fields
   * @returns {boolean} True if form is valid
   */
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {}

    const emailError = getEmailError(formData.email)
    if (emailError) {
      newErrors.email = emailError
    }

    const passwordError = getPasswordError(formData.password)
    if (passwordError) {
      newErrors.password = passwordError
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setServerError(null)

    // Validate form
    if (!validateForm()) {
      return
    }

    setIsSubmitting(true)

    try {
      const result = await login({
        email: formData.email,
        password: formData.password,
      })

      if (result.success) {
        // Redirect to the page user was trying to access, or home
        navigate(from, { replace: true })
      } else {
        // Show error from backend (sanitized to prevent XSS)
        const rawError = result.error || 'Login failed. Please try again.'
        setServerError(String(sanitizeError(rawError)))
      }
    } catch (error) {
      logger.error('[LoginPage] Login error:', error)
      setServerError('An unexpected error occurred. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12 bg-gray-50">
      <div className="w-full max-w-md min-w-[280px]">
        {/* Header */}
        <div className="text-center mb-8 space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
            Welcome back
          </h1>
          <p className="text-sm sm:text-base text-gray-600">
            Sign in to your PlantID account
          </p>
        </div>

        {/* Login Form */}
        <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-8">
          <form onSubmit={handleSubmit} className="space-y-6" noValidate>
            {/* Server Error */}
            {serverError && (
              <div
                className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
                role="alert"
              >
                {serverError}
              </div>
            )}

            {/* Email Field */}
            <Input
              type="email"
              label="Email address"
              name="email"
              value={formData.email}
              onChange={handleChange}
              error={errors.email}
              placeholder="you@example.com"
              required
              autoComplete="email"
              disabled={isSubmitting}
            />

            {/* Password Field */}
            <Input
              type="password"
              label="Password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              error={errors.password}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
              disabled={isSubmitting}
            />

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={isSubmitting}
              disabled={isSubmitting}
              className="w-full"
            >
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          {/* Signup Link */}
          <div className="mt-6 text-center text-sm">
            <span className="text-gray-600">Don't have an account? </span>
            <Link
              to="/signup"
              className="font-medium text-green-600 hover:text-green-700 transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>

        {/* Additional Links (placeholder for future features) */}
        <div className="mt-4 text-center">
          <button
            type="button"
            className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
            disabled
            aria-disabled="true"
          >
            Forgot your password?
          </button>
        </div>
      </div>
    </div>
  )
}
