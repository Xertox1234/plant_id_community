import { useState, FormEvent, ChangeEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { getEmailError, getPasswordError, getPasswordConfirmError } from '../../utils/validation';
import { sanitizeInput, sanitizeError } from '../../utils/sanitize';
import { logger } from '../../utils/logger';

interface FormData {
  username: string;
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

interface FormErrors {
  username?: string;
  firstName?: string;
  lastName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

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
  const navigate = useNavigate();
  const { signup } = useAuth();

  const [formData, setFormData] = useState<FormData>({
    username: '',
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  /**
   * Handle input changes and clear field-specific errors
   */
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;

    // Sanitize input to prevent XSS
    const sanitizedValue = sanitizeInput(value);

    setFormData((prev) => ({
      ...prev,
      [name]: sanitizedValue,
    }));

    // Clear error for this field when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({
        ...prev,
        [name]: undefined,
      }));
    }

    // Clear server error when user modifies form
    if (serverError) {
      setServerError(null);
    }
  };

  /**
   * Validate form fields
   * @returns {boolean} True if form is valid
   */
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Username validation (required)
    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (formData.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.username)) {
      newErrors.username = 'Username can only contain letters, numbers, underscores, and hyphens';
    }

    const emailError = getEmailError(formData.email);
    if (emailError) {
      newErrors.email = emailError;
    }

    const passwordError = getPasswordError(formData.password);
    if (passwordError) {
      newErrors.password = passwordError;
    }

    const confirmPasswordError = getPasswordConfirmError(
      formData.password,
      formData.confirmPassword
    );
    if (confirmPasswordError) {
      newErrors.confirmPassword = confirmPasswordError;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setServerError(null);

    // Validate form
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await signup({
        username: formData.username,
        first_name: formData.firstName, // Backend expects snake_case
        last_name: formData.lastName, // Backend expects snake_case
        email: formData.email,
        password: formData.password,
        confirmPassword: formData.confirmPassword,
      });

      if (result.success) {
        // Redirect to home page after successful signup
        navigate('/', { replace: true });
      } else {
        // Show error from backend (sanitized to prevent XSS)
        const rawError = result.error || 'Signup failed. Please try again.';
        setServerError(String(sanitizeError(rawError)));
      }
    } catch (error) {
      logger.error('[SignupPage] Signup error:', error);
      setServerError('An unexpected error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12 bg-surface">
      <div className="w-full max-w-md min-w-[280px]">
        {/* Header */}
        <div className="text-center mb-8 space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-ink">Create an account</h1>
          <p className="text-sm sm:text-base text-ink-3">
            Join PlantID to identify plants and track your garden
          </p>
        </div>

        {/* Signup Form */}
        <div className="bg-surface-2 shadow-sm border border-line rounded-lg p-8">
          <form onSubmit={handleSubmit} className="space-y-6" noValidate>
            {/* Server Error */}
            {serverError && (
              <div
                className="p-4 bg-error/10 border border-error rounded-lg text-error text-sm"
                role="alert"
              >
                {serverError}
              </div>
            )}

            {/* Username Field */}
            <Input
              type="text"
              label="Username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              error={errors.username}
              placeholder="johndoe"
              required
              autoComplete="username"
              disabled={isSubmitting}
            />

            {/* First Name Field */}
            <Input
              type="text"
              label="First name"
              name="firstName"
              value={formData.firstName}
              onChange={handleChange}
              error={errors.firstName}
              placeholder="John"
              autoComplete="given-name"
              disabled={isSubmitting}
            />

            {/* Last Name Field */}
            <Input
              type="text"
              label="Last name"
              name="lastName"
              value={formData.lastName}
              onChange={handleChange}
              error={errors.lastName}
              placeholder="Doe"
              autoComplete="family-name"
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
              placeholder="At least 14 characters"
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
            <span className="text-ink-3">Already have an account? </span>
            <Link
              to="/login"
              className="font-medium text-primary hover:text-primary/80 transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>

        {/* Terms Notice */}
        <p className="mt-6 text-xs text-center text-ink-3">
          By creating an account, you agree to our{' '}
          <span className="text-ink-2">Terms of Service</span> and{' '}
          <span className="text-ink-2">Privacy Policy</span>
        </p>
      </div>
    </div>
  );
}
