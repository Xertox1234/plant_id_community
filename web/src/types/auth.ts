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
  first_name?: string;
  last_name?: string;
  trust_level?: 'new' | 'basic' | 'trusted' | 'veteran' | 'expert';
  date_joined?: string;
  is_active?: boolean;
}

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
  email: string;
  name: string;
  password: string;
}

/**
 * Authentication response
 */
export interface AuthResponse {
  user: User;
  token?: string;
}
