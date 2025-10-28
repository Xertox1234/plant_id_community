/**
 * AuthContext Tests
 *
 * Tests for authentication context provider.
 * Priority: Phase 1 - Critical security component (authentication logic).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { AuthProvider, AuthContext } from './AuthContext';
import * as authService from '../services/authService';

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
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      const { result } = renderHook(() => AuthContext.read(), {
        wrapper: AuthProvider,
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isLoading).toBe(true);
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('loads stored user on mount', async () => {
      const mockUser = { id: 1, email: 'test@example.com', name: 'Test User' };
      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => AuthContext.read(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('verifies stored user with backend on mount', async () => {
      const storedUser = { id: 1, email: 'stored@example.com' };
      const currentUser = { id: 1, email: 'current@example.com', name: 'Updated' };

      authService.getStoredUser.mockReturnValue(storedUser);
      authService.getCurrentUser.mockResolvedValue(currentUser);

      const { result } = renderHook(() => AuthContext.read(), {
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
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => AuthContext.read(), {
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
      const credentials = { email: 'test@example.com', password: 'password123' };
      const mockUser = { id: 1, email: 'test@example.com', name: 'Test User' };

      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);
      authService.login.mockResolvedValue(mockUser);

      const { result } = renderHook(() => AuthContext.read(), {
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
      const credentials = { email: 'test@example.com', password: 'wrong' };
      const error = new Error('Invalid credentials');

      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);
      authService.login.mockRejectedValue(error);

      const { result } = renderHook(() => AuthContext.read(), {
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
      expect(loginResult.error).toBe('Invalid credentials');
      expect(result.current.user).toBeNull();
      expect(result.current.error).toBe('Invalid credentials');
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('sets loading state during login', async () => {
      const credentials = { email: 'test@example.com', password: 'password123' };
      const mockUser = { id: 1, email: 'test@example.com' };

      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);
      authService.login.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockUser), 100))
      );

      const { result } = renderHook(() => AuthContext.read(), {
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
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      // First login fails
      authService.login.mockRejectedValueOnce(new Error('First error'));

      const { result } = renderHook(() => AuthContext.read(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // First attempt
      await act(async () => {
        await result.current.login({ email: 'test@example.com', password: 'wrong' });
      });

      expect(result.current.error).toBe('First error');

      // Second login succeeds
      const mockUser = { id: 1, email: 'test@example.com' };
      authService.login.mockResolvedValueOnce(mockUser);

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
      const userData = {
        name: 'New User',
        email: 'new@example.com',
        password: 'password123',
      };
      const mockUser = { id: 2, email: 'new@example.com', name: 'New User' };

      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);
      authService.signup.mockResolvedValue(mockUser);

      const { result } = renderHook(() => AuthContext.read(), {
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
      const userData = {
        name: 'New User',
        email: 'existing@example.com',
        password: 'password123',
      };
      const error = new Error('Email already exists');

      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);
      authService.signup.mockRejectedValue(error);

      const { result } = renderHook(() => AuthContext.read(), {
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
      expect(signupResult.error).toBe('Email already exists');
      expect(result.current.user).toBeNull();
      expect(result.current.error).toBe('Email already exists');
    });

    it('sets loading state during signup', async () => {
      const userData = { name: 'Test', email: 'test@example.com', password: 'pass' };
      const mockUser = { id: 1, email: 'test@example.com' };

      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);
      authService.signup.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockUser), 100))
      );

      const { result } = renderHook(() => AuthContext.read(), {
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
      const mockUser = { id: 1, email: 'test@example.com' };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);
      authService.logout.mockResolvedValue();

      const { result } = renderHook(() => AuthContext.read(), {
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
      const mockUser = { id: 1, email: 'test@example.com' };

      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);
      authService.logout.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => AuthContext.read(), {
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
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      const { result, rerender } = renderHook(() => AuthContext.read(), {
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
      const mockUser = { id: 1, email: 'test@example.com' };
      authService.getStoredUser.mockReturnValue(mockUser);
      authService.getCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => AuthContext.read(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });
    });

    it('isAuthenticated is false when user is null', async () => {
      authService.getStoredUser.mockReturnValue(null);
      authService.getCurrentUser.mockResolvedValue(null);

      const { result } = renderHook(() => AuthContext.read(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
      });
    });
  });
});
