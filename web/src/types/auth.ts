/**
 * Authentication & User Types
 */

/**
 * User model (from Django backend)
 */
export interface User {
  id: number;
  email: string;
  username: string;
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
 * Signup data
 */
export interface SignupData {
  email: string;
  username: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

/**
 * Authentication response
 */
export interface AuthResponse {
  user: User;
  token?: string;
}
