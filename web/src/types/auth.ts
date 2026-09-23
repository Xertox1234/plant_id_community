/**
 * Authentication & User Types
 */

/**
 * User model (from Django backend)
 */
export interface User {
  id: number;
  email: string;
  username?: string;
  name?: string; // Full name (may be used instead of first_name/last_name)
  display_name?: string; // Display name for forum/posts
  first_name?: string;
  last_name?: string;
  trust_level?: 'new' | 'basic' | 'trusted' | 'veteran' | 'expert';
  date_joined?: string;
  is_active?: boolean;
  is_staff?: boolean; // Django staff user
  is_moderator?: boolean; // Forum moderator
}

/**
 * The signed-in user's own profile, as GET /api/v1/auth/user/ returns it
 * (backend UserProfileSerializer). Only the fields the profile page uses.
 */
export interface UserProfile {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  display_name: string;
  bio: string;
  location: string;
  website: string;
}

/**
 * The fields the web profile page may change via PATCH /api/v1/auth/user/update/.
 * Email is deliberately absent: changing it needs re-verification, which the
 * backend does not do yet.
 */
export type ProfileUpdate = Partial<
  Pick<UserProfile, 'first_name' | 'last_name' | 'bio' | 'location' | 'website'>
>;

/**
 * Login credentials
 */
export interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Signup data (matches frontend form)
 */
export interface SignupData {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirmPassword?: string; // Optional for frontend validation
}

/**
 * Authentication response
 */
export interface AuthResponse {
  user: User;
  token?: string;
}

/**
 * Authentication error codes for categorization
 */
export enum AuthErrorCode {
  INVALID_CREDENTIALS = 'INVALID_CREDENTIALS',
  EMAIL_EXISTS = 'EMAIL_EXISTS',
  NETWORK_ERROR = 'NETWORK_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  SESSION_EXPIRED = 'SESSION_EXPIRED',
  RATE_LIMITED = 'RATE_LIMITED',
  UNKNOWN = 'UNKNOWN',
}

/**
 * Structured authentication error
 * Provides better debugging and error tracking (Sentry integration)
 */
export interface AuthError {
  message: string;
  code: AuthErrorCode;
  details?: Record<string, unknown>;
}
