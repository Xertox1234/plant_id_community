/**
 * AuthContext Tests
 *
 * Tests for authentication context provider.
 * Priority: Phase 1 - Critical security component (authentication logic).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth, AuthErrorCode } from './AuthContext';
import * as authService from '../services/authService';
import type { User, LoginCredentials, SignupData } from '../types/auth';

// Mock the auth service
vi.mock('../services/authService');

// Mock logger to avoid console noise during tests
vi.mock('../utils/logger', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  },
}));

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initialization', () => {
    it('initializes with null user and loading state', () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isLoading).toBe(true);
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('loads stored user on mount', async () => {
      const mockUser: User = { id: 1, email: 'test@example.com', name: 'Test User' };
      vi.mocked(authService.getStoredUser).mockReturnValue(mockUser);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('verifies stored user with backend on mount', async () => {
      const storedUser: User = { id: 1, email: 'stored@example.com' };
      const currentUser: User = { id: 1, email: 'current@example.com', name: 'Updated' };

      vi.mocked(authService.getStoredUser).mockReturnValue(storedUser);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(currentUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should use backend-verified user, not stored user
      expect(result.current.user).toEqual(currentUser);
      expect(authService.getCurrentUser).toHaveBeenCalled();
    });

    it('handles initialization error gracefully', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('Login', () => {
    it('successfully logs in user', async () => {
      const credentials: LoginCredentials = { email: 'test@example.com', password: 'password123' };
      const mockUser: User = { id: 1, email: 'test@example.com', name: 'Test User' };

      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let loginResult;
      await act(async () => {
        loginResult = await result.current.login(credentials);
      });

      expect(loginResult.success).toBe(true);
      expect(loginResult.user).toEqual(mockUser);
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
      expect(authService.login).toHaveBeenCalledWith(credentials);
    });

    it('handles login failure', async () => {
      const credentials: LoginCredentials = { email: 'test@example.com', password: 'wrong' };
      const error = new Error('Invalid credentials');

      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockRejectedValue(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let loginResult;
      await act(async () => {
        loginResult = await result.current.login(credentials);
      });

      expect(loginResult.success).toBe(false);
      expect(loginResult.error?.message).toBe('Invalid credentials');
      expect(loginResult.error?.code).toBe(AuthErrorCode.INVALID_CREDENTIALS);
      expect(result.current.user).toBeNull();
      expect(result.current.error?.message).toBe('Invalid credentials');
      expect(result.current.error?.code).toBe(AuthErrorCode.INVALID_CREDENTIALS);
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('sets loading state during login', async () => {
      const credentials: LoginCredentials = { email: 'test@example.com', password: 'password123' };
      const mockUser: User = { id: 1, email: 'test@example.com' };

      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockImplementation(
        () => new Promise<User>((resolve) => setTimeout(() => resolve(mockUser), 100))
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      act(() => {
        result.current.login(credentials);
      });

      // Should be loading during login
      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('clears previous error on new login attempt', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);

      // First login fails
      vi.mocked(authService.login).mockRejectedValueOnce(new Error('First error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // First attempt
      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'wrong' });
      });

      expect(result.current.error?.message).toBe('First error');

      // Second login succeeds
      const mockUser: User = { id: 1, email: 'test@example.com' };
      vi.mocked(authService.login).mockResolvedValueOnce(mockUser);

      // Second attempt should clear error
      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'correct' });
      });

      expect(result.current.error).toBeNull();
      expect(result.current.user).toEqual(mockUser);
    });
  });

  describe('Signup', () => {
    it('successfully signs up new user', async () => {
      const userData: SignupData = {
        username: 'newuser',
        first_name: 'New',
        last_name: 'User',
        email: 'new@example.com',
        password: 'password123',
      };
      const mockUser: User = { id: 2, email: 'new@example.com', name: 'New User' };

      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.signup).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let signupResult;
      await act(async () => {
        signupResult = await result.current.signup(userData);
      });

      expect(signupResult.success).toBe(true);
      expect(signupResult.user).toEqual(mockUser);
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
      expect(authService.signup).toHaveBeenCalledWith(userData);
    });

    it('handles signup failure', async () => {
      const userData: SignupData = {
        username: 'newuser',
        first_name: 'New',
        last_name: 'User',
        email: 'existing@example.com',
        password: 'password123',
      };
      const error = new Error('Email already exists');

      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.signup).mockRejectedValue(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let signupResult;
      await act(async () => {
        signupResult = await result.current.signup(userData);
      });

      expect(signupResult.success).toBe(false);
      expect(signupResult.error?.message).toBe('Email already exists');
      expect(signupResult.error?.code).toBe(AuthErrorCode.EMAIL_EXISTS);
      expect(result.current.user).toBeNull();
      expect(result.current.error?.message).toBe('Email already exists');
      expect(result.current.error?.code).toBe(AuthErrorCode.EMAIL_EXISTS);
    });

    it('sets loading state during signup', async () => {
      const userData: SignupData = { username: 'test', first_name: 'Test', last_name: 'User', email: 'test@example.com', password: 'pass' };
      const mockUser: User = { id: 1, email: 'test@example.com' };

      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.signup).mockImplementation(
        () => new Promise<User>((resolve) => setTimeout(() => resolve(mockUser), 100))
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      act(() => {
        result.current.signup(userData);
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('Logout', () => {
    it('successfully logs out user', async () => {
      const mockUser: User = { id: 1, email: 'test@example.com' };

      vi.mocked(authService.getStoredUser).mockReturnValue(mockUser);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(mockUser);
      vi.mocked(authService.logout).mockResolvedValue();

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.error).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(authService.logout).toHaveBeenCalled();
    });

    it('clears user state even if logout API fails', async () => {
      const mockUser: User = { id: 1, email: 'test@example.com' };

      vi.mocked(authService.getStoredUser).mockReturnValue(mockUser);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(mockUser);
      vi.mocked(authService.logout).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      await act(async () => {
        await result.current.logout();
      });

      // Should still clear user state despite API error
      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('Context Value Memoization', () => {
    it('memoizes context value to prevent unnecessary re-renders', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);

      const { result, rerender } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const firstValue = result.current;

      // Re-render without state change
      rerender();

      // Value should be the same object (memoized)
      expect(result.current).toBe(firstValue);
    });
  });

  describe('Authentication State', () => {
    it('isAuthenticated is true when user exists', async () => {
      const mockUser: User = { id: 1, email: 'test@example.com' };
      vi.mocked(authService.getStoredUser).mockReturnValue(mockUser);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });
    });

    it('isAuthenticated is false when user is null', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
      });
    });
  });

  describe('Error Management', () => {
    it('clearError clears error state', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockRejectedValue(new Error('Invalid credentials'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Trigger error
      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'wrong' });
      });

      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.message).toBe('Invalid credentials');

      // Clear error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });

    it('error has correct structure with code and message', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockRejectedValue(new Error('Network error occurred'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'test' });
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.message).toBe('Network error occurred');
      expect(result.current.error?.code).toBe(AuthErrorCode.NETWORK_ERROR);
      expect(result.current.error?.details).toBeDefined();
    });
  });

  describe('Error Categorization', () => {
    it('handles ambiguous error messages correctly (specific before general)', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      // "Invalid session" should be SESSION_EXPIRED (not INVALID_CREDENTIALS)
      vi.mocked(authService.login).mockRejectedValue(new Error('Invalid session expired'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'test' });
      });

      expect(result.current.error?.code).toBe(AuthErrorCode.SESSION_EXPIRED);
      expect(result.current.error?.message).toBe('Invalid session expired');
    });

    it('defaults to UNKNOWN for unrecognized errors', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockRejectedValue(new Error('Something weird happened'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'test' });
      });

      expect(result.current.error?.code).toBe(AuthErrorCode.UNKNOWN);
      expect(result.current.error?.message).toBe('Something weird happened');
    });

    it('handles non-Error objects gracefully', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockRejectedValue('String error');

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'test' });
      });

      expect(result.current.error?.code).toBe(AuthErrorCode.UNKNOWN);
      expect(result.current.error?.message).toBe('Login failed. Please try again.');
    });

    it('categorizes rate limit errors correctly', async () => {
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockRejectedValue(new Error('Too many requests'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'test' });
      });

      expect(result.current.error?.code).toBe(AuthErrorCode.RATE_LIMITED);
    });
  });

  describe('Request ID Regeneration', () => {
    it('regenerates request ID on successful login', async () => {
      const mockUser: User = { id: 1, email: 'test@example.com' };
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockResolvedValue(mockUser);

      // Mock sessionStorage
      const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'password' });
      });

      // Should have removed request ID to force regeneration
      expect(removeItemSpy).toHaveBeenCalledWith('requestId');

      removeItemSpy.mockRestore();
    });

    it('regenerates request ID on successful signup', async () => {
      const mockUser: User = { id: 1, email: 'test@example.com' };
      vi.mocked(authService.getStoredUser).mockReturnValue(null);
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.signup).mockResolvedValue(mockUser);

      // Mock sessionStorage
      const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.signup({ username: 'test', first_name: 'Test', last_name: 'User', email: 'test@example.com', password: 'password' });
      });

      // Should have removed request ID to force regeneration
      expect(removeItemSpy).toHaveBeenCalledWith('requestId');

      removeItemSpy.mockRestore();
    });
  });
});
