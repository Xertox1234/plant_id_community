/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
  ReactNode,
} from 'react';
import * as authService from '../services/authService';
import {
  resetComposeAssistAvailability,
  resetPlantCareAskAvailability,
} from '../services/forumService';
import { logger } from '../utils/logger';
import { rotateRequestId } from '../utils/requestId';
import { clearAllDrafts } from '../utils/forumDrafts';
import { AuthErrorCode } from '../types/auth';
import type { User, LoginCredentials, SignupData, AuthError } from '../types/auth';

// Token refresh interval: 10 minutes (before 15-minute expiry)
// SECURITY: OWASP recommends 15-minute access tokens
const TOKEN_REFRESH_INTERVAL = 10 * 60 * 1000; // 10 minutes in milliseconds

// Minimum gap between focus-triggered identity revalidations (todo 297) — a
// window switched back to repeatedly (alt-tabbing) must not spam
// GET /api/v1/auth/user/ on every focus/visibilitychange event.
const FOCUS_REVALIDATE_MIN_INTERVAL = 30 * 1000; // 30 seconds

// Re-export all auth types for convenience (single import source)
export type { User, LoginCredentials, SignupData, AuthError } from '../types/auth';
export { AuthErrorCode } from '../types/auth';

/**
 * Convert any error to structured AuthError
 * Extracts error code from known error messages for better categorization
 */
function toAuthError(err: unknown, defaultMessage: string): AuthError {
  if (!err) {
    return {
      message: defaultMessage,
      code: AuthErrorCode.UNKNOWN,
    };
  }

  const message = err instanceof Error ? err.message : defaultMessage;
  const lowerMessage = message.toLowerCase();

  // Categorize based on error message patterns
  // IMPORTANT: Check specific patterns BEFORE general ones to avoid misclassification
  let code = AuthErrorCode.UNKNOWN;

  // Check specific patterns first
  if (lowerMessage.includes('expired') || lowerMessage.includes('session')) {
    code = AuthErrorCode.SESSION_EXPIRED;
  } else if (lowerMessage.includes('rate') || lowerMessage.includes('too many')) {
    code = AuthErrorCode.RATE_LIMITED;
  } else if (lowerMessage.includes('exists') || lowerMessage.includes('already')) {
    code = AuthErrorCode.EMAIL_EXISTS;
  } else if (lowerMessage.includes('network') || lowerMessage.includes('fetch')) {
    code = AuthErrorCode.NETWORK_ERROR;
  } else if (lowerMessage.includes('validation')) {
    code = AuthErrorCode.VALIDATION_ERROR;
  } else if (lowerMessage.includes('invalid') || lowerMessage.includes('incorrect')) {
    // Check "invalid" last since it's general (e.g., "invalid session" should be SESSION_EXPIRED)
    code = AuthErrorCode.INVALID_CREDENTIALS;
  }

  return {
    message,
    code,
    details: err instanceof Error ? { name: err.name, stack: err.stack } : undefined,
  };
}

/**
 * Authentication operation result
 */
export interface AuthResult {
  success: boolean;
  user?: User;
  error?: AuthError;
}

/**
 * AuthContext value type
 *
 * Provides authentication state and methods throughout the app.
 */
export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  error: AuthError | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<AuthResult>;
  logout: () => Promise<void>;
  signup: (userData: SignupData) => Promise<AuthResult>;
  /**
   * Re-read the current user from the backend and sync context state.
   * Used after the Google OAuth callback, where the JWT cookies are already
   * set by the backend redirect but context state has not yet caught up.
   */
  refreshUser: () => Promise<User | null>;
  /** Rotation-free identity re-fetch (todo 297) — see the implementation's docstring. */
  revalidateIdentity: () => Promise<User | null>;
  clearError: () => void;
}

/**
 * AuthContext
 *
 * Provides authentication state and methods throughout the app.
 * Uses React 19's createContext which can be used directly as a provider.
 *
 * Context Value:
 * - user: Current user object or null
 * - isLoading: Boolean indicating auth state is being determined
 * - error: Structured error object if auth operation failed
 * - isAuthenticated: Boolean indicating if user is logged in
 * - login(credentials): Function to log in
 * - logout(): Function to log out
 * - signup(userData): Function to sign up
 * - clearError(): Function to manually clear error state
 *
 * Note: eslint-disable for react-refresh is intentional - this file exports
 * both the context and provider, which is a common and acceptable pattern.
 */
export const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * useAuth Hook
 *
 * Custom hook to consume AuthContext.
 * Provides a cleaner API for accessing auth state and methods.
 *
 * @returns Auth context value
 * @throws Error if used outside of AuthProvider
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

/**
 * AuthProvider props
 */
export interface AuthProviderProps {
  children: ReactNode;
}

/**
 * AuthProvider Component
 *
 * Wraps the app to provide authentication context to all children.
 * Handles authentication state, persistence, and API calls.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AuthError | null>(null);

  // Use ref for refresh timer to avoid memory leaks and prevent re-renders
  const refreshTimerRef = useRef<number | null>(null);

  // Timestamp of the last focus-triggered revalidation — useRef (gotcha 5),
  // not useState, so the debounce check itself never causes a re-render.
  const lastFocusRevalidateRef = useRef<number>(0);

  // Initialize auth state on mount
  useEffect(() => {
    async function initAuth() {
      try {
        // First, try to get stored user for immediate UI update
        const storedUser = authService.getStoredUser();
        if (storedUser) {
          setUser(storedUser);
        }

        // Then verify with backend to ensure session is still valid
        const currentUser = await authService.getCurrentUser();
        setUser(currentUser);
      } catch (err) {
        logger.error('[AuthContext] Auth initialization failed', { error: err });
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    initAuth();
  }, []);

  // Composer drafts are keyed by topic/board, not account, and sessionStorage
  // outlives every identity change in this tab (audit 2026-09-04 L4). logout()
  // clears them, but a swap can also arrive passively — a focus revalidation
  // that finds another account's cookie, or an expired session followed by a
  // different login — so reconcile here on the identity itself. Only a change
  // BETWEEN two real accounts clears: the first identity after mount (a reload)
  // and an expire → same-account re-login must keep the draft.
  const draftsOwnerIdRef = useRef<number | null>(null);
  useEffect(() => {
    const nextId = user?.id ?? null;
    if (nextId === null) return;
    if (draftsOwnerIdRef.current !== null && draftsOwnerIdRef.current !== nextId) {
      clearAllDrafts();
    }
    draftsOwnerIdRef.current = nextId;
  }, [user?.id]);

  // Clear per-account API capability latches whenever the identity changes.
  // One effect keyed on the user id rather than a call in each of login/register/
  // logout/refresh, so a future auth path cannot forget it. The forum
  // compose-assist latch caches "this account is not premium" for the session, so
  // it must not outlive the account: without this, a non-premium user who clicks
  // AI assist, then upgrades or logs out and back in as someone else in the same
  // SPA session, keeps a disabled button the server would now allow
  // (todo 275 code review).
  // The plant-care ask latch (todo 289) is the same kind of session-scoped
  // "this account can't" fact — and it also covers 401, so signing in must
  // clear it or the panel stays disabled for the now-authenticated user.
  useEffect(() => {
    resetComposeAssistAvailability();
    resetPlantCareAskAvailability();
  }, [user?.id]);

  // Automatic token refresh for authenticated users
  // SECURITY: OWASP-compliant 15-minute access tokens require automatic refresh
  useEffect(() => {
    // Only set up refresh if user is authenticated
    if (!user) {
      // Clear any existing timer if user logs out
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      return;
    }

    logger.info('[AuthContext] Setting up automatic token refresh (10-minute interval)');

    // Set up automatic token refresh every 10 minutes
    refreshTimerRef.current = window.setInterval(async () => {
      logger.info('[AuthContext] Refreshing access token...');
      const success = await authService.refreshAccessToken();

      if (!success) {
        logger.warn('[AuthContext] Token refresh failed - logging out user');
        // Token refresh failed - log out user
        setUser(null);
        setError({
          message: 'Your session has expired. Please log in again.',
          code: AuthErrorCode.SESSION_EXPIRED,
        });
        // Clear refresh timer
        if (refreshTimerRef.current) {
          clearInterval(refreshTimerRef.current);
          refreshTimerRef.current = null;
        }
      }
    }, TOKEN_REFRESH_INTERVAL);

    // Cleanup on unmount or when user changes
    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [user]); // Re-run when user changes (login/logout)

  /**
   * Re-fetch the server-side identity and reconcile local state ONLY on an
   * actual change (todo 297) — compares by `id` (always present on `User`),
   * not `username` (optional; a response missing it would otherwise make
   * the drift check a silent no-op). Deliberately does NOT rotate the
   * request ID like `refreshUser` below does: that's correct for a real
   * session-start event (login/signup/OAuth) but would fragment the trace
   * of routine activity here — a background focus poll (no rotation
   * wanted on the common no-drift case) AND a write-defense check (rotating
   * on every successful post, not just a detected drift, would be noise).
   * Shared by the focus-revalidation effect below and the write-defense
   * call sites in NewThreadPage/ThreadDetailPage.
   */
  const revalidateIdentity = useCallback(async (): Promise<User | null> => {
    const currentUser = await authService.getCurrentUser();
    setUser((prevUser) => {
      const prevId = prevUser?.id ?? null;
      const nextId = currentUser?.id ?? null;
      // Reconcile only on an actual identity change — an unconditional
      // setUser() here would re-render on every focus for no reason.
      return prevId === nextId ? prevUser : currentUser;
    });
    return currentUser;
  }, []);

  // Revalidate identity on tab focus (todo 297). The cookie-jar identity can
  // change in another tab of the same browser profile (re-login as a
  // different account) — without this, the header keeps showing the stale
  // user while the server attributes every write to the NEW cookie identity
  // (live prod incident 2026-08-13: header showed one user, a forum reply
  // was created as another). Mounted unconditionally (not gated on `user`)
  // so both directions work: an already-logged-in tab picking up a switch to
  // a different account, and a logged-out tab picking up a login elsewhere.
  useEffect(() => {
    const revalidate = () => {
      const now = Date.now();
      if (now - lastFocusRevalidateRef.current < FOCUS_REVALIDATE_MIN_INTERVAL) {
        return; // debounced — too soon since the last check
      }
      // Set before the await: a focus event and the immediately-following
      // visibilitychange event must collapse into one fetch, not two.
      lastFocusRevalidateRef.current = now;

      revalidateIdentity().catch((err) => {
        logger.error('[AuthContext] Focus identity revalidation failed', { error: err });
      });
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        revalidate();
      }
    };

    window.addEventListener('focus', revalidate);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('focus', revalidate);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [revalidateIdentity]);

  /**
   * Login user with email and password
   * Regenerates request ID on successful login for per-user session tracing
   */
  const login = async (credentials: LoginCredentials): Promise<AuthResult> => {
    setIsLoading(true);
    setError(null);

    try {
      const userData = await authService.login(credentials);
      setUser(userData);

      // Regenerate request ID for new user session (better distributed tracing)
      rotateRequestId();

      return { success: true, user: userData };
    } catch (err) {
      const authError = toAuthError(err, 'Login failed. Please try again.');
      setError(authError);
      return { success: false, error: authError };
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Sign up new user
   * Regenerates request ID on successful signup for per-user session tracing
   */
  const signup = async (userData: SignupData): Promise<AuthResult> => {
    setIsLoading(true);
    setError(null);

    try {
      const newUser = await authService.signup(userData);
      setUser(newUser);

      // Regenerate request ID for new user session (better distributed tracing)
      rotateRequestId();

      return { success: true, user: newUser };
    } catch (err) {
      const authError = toAuthError(err, 'Signup failed. Please try again.');
      setError(authError);
      return { success: false, error: authError };
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Logout current user
   * Clears user state and calls logout API
   */
  const logout = async (): Promise<void> => {
    try {
      await authService.logout();
      setUser(null);
      setError(null);
    } catch (err) {
      logger.error('[AuthContext] Logout failed', { error: err });
      // Still clear user state even if API fails
      setUser(null);
    }
  };

  /**
   * Re-read the current user from the backend and sync context state.
   * The OAuth callback lands here after the backend has already set JWT cookies,
   * so this re-fetch (a GET against /api/v1/auth/user/) is what populates the
   * authenticated user into context. Returns the user (or null) for the caller
   * to branch on. Rotates the request ID on success, matching login/signup.
   */
  const refreshUser = async (): Promise<User | null> => {
    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
      if (currentUser) {
        rotateRequestId();
      }
      return currentUser;
    } catch (err) {
      logger.error('[AuthContext] refreshUser failed', { error: err });
      setUser(null);
      return null;
    }
  };

  /**
   * Manually clear error state
   * Useful for dismissing error messages in UI
   */
  const clearError = () => {
    setError(null);
  };

  // Memoize context value to prevent unnecessary re-renders
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      error,
      isAuthenticated: !!user,
      login,
      logout,
      signup,
      refreshUser,
      revalidateIdentity,
      clearError,
    }),
    [user, isLoading, error, revalidateIdentity]
  );

  // React 19: Use AuthContext directly as provider
  return <AuthContext value={value}>{children}</AuthContext>;
}
