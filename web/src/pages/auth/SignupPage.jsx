import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import {
  getNameError,
  getEmailError,
  getPasswordError,
  getPasswordConfirmError,
} from '../../utils/validation'
import { sanitizeInput, sanitizeError } from '../../utils/sanitize'
import { logger } from '../../utils/logger'

/**
 * SignupPage Component
 *
 * User registration page with name, email, and password.
 * Features:
 * - Form validation with real-time feedback
 * - Password confirmation field
 * - Loading state during submission
 * - Error handling for failed registration
 * - Redirects to home after successful signup
 * - Link to login page for existing users
 */
export default function SignupPage() {
  const navigate = useNavigate()
  const { signup } = useAuth()

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  })

  const [errors, setErrors] = useState({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [serverError, setServerError] = useState(null)

  /**
   * Handle input changes and clear field-specific errors
   */
  const handleChange = (e) => {
    const { name, value } = e.target

    // Sanitize input to prevent XSS
    const sanitizedValue = sanitizeInput(value)

    setFormData((prev) => ({
      ...prev,
      [name]: sanitizedValue,
    }))

    // Clear error for this field when user starts typing
    if (errors[name]) {
      setErrors((prev) => ({
        ...prev,
        [name]: null,
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
  const validateForm = () => {
    const newErrors = {}

    const nameError = getNameError(formData.name)
    if (nameError) {
      newErrors.name = nameError
    }

    const emailError = getEmailError(formData.email)
    if (emailError) {
      newErrors.email = emailError
    }

    const passwordError = getPasswordError(formData.password)
    if (passwordError) {
      newErrors.password = passwordError
    }

    const confirmPasswordError = getPasswordConfirmError(
      formData.password,
      formData.confirmPassword
    )
    if (confirmPasswordError) {
      newErrors.confirmPassword = confirmPasswordError
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault()
    setServerError(null)

    // Validate form
    if (!validateForm()) {
      return
    }

    setIsSubmitting(true)

    try {
      const result = await signup({
        name: formData.name,
        email: formData.email,
        password: formData.password,
      })

      if (result.success) {
        // Redirect to home page after successful signup
        navigate('/', { replace: true })
      } else {
        // Show error from backend (sanitized to prevent XSS)
        const rawError = result.error || 'Signup failed. Please try again.'
        setServerError(sanitizeError(rawError))
      }
    } catch (error) {
      logger.error('[SignupPage] Signup error:', error)
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
            Create an account
          </h1>
          <p className="text-sm sm:text-base text-gray-600">
            Join PlantID to identify plants and track your garden
          </p>
        </div>

        {/* Signup Form */}
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

            {/* Name Field */}
            <Input
              type="text"
              label="Full name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              error={errors.name}
              placeholder="John Doe"
              required
              autoComplete="name"
              disabled={isSubmitting}
            />

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
              placeholder="At least 8 characters"
              required
              autoComplete="new-password"
              disabled={isSubmitting}
            />

            {/* Confirm Password Field */}
            <Input
              type="password"
              label="Confirm password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              error={errors.confirmPassword}
              placeholder="Re-enter your password"
              required
              autoComplete="new-password"
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
              {isSubmitting ? 'Creating account...' : 'Create account'}
            </Button>
          </form>

          {/* Login Link */}
          <div className="mt-6 text-center text-sm">
            <span className="text-gray-600">Already have an account? </span>
            <Link
              to="/login"
              className="font-medium text-green-600 hover:text-green-700 transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>

        {/* Terms Notice */}
        <p className="mt-6 text-xs text-center text-gray-500">
          By creating an account, you agree to our{' '}
          <span className="text-gray-700">Terms of Service</span> and{' '}
          <span className="text-gray-700">Privacy Policy</span>
        </p>
      </div>
    </div>
  )
}
