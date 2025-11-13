/**
 * Authentication Service Tests
 *
 * Comprehensive tests for auth service covering:
 * - Login flow with CSRF protection
 * - Registration with validation
 * - Logout and session cleanup
 * - Current user fetching
 * - Error handling and network failures
 *
 * Priority: P1 - CRITICAL (Authentication is core to application security)
 * Coverage Target: 100% branch coverage
 * Estimated Test Count: 18 tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { login, signup, logout, getCurrentUser, getStoredUser } from './authService';
import type { User, LoginCredentials, SignupData, AuthResponse } from '../types/auth';

// Mock logger to prevent console noise in tests
vi.mock('../utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('authService', () => {
  // Test fixtures
  const mockUser: User = {
    id: 1,
    email: 'test@example.com',
    username: 'testuser',
    name: 'Test User',
    display_name: 'TestUser',
    trust_level: 'basic',
    date_joined: '2025-01-01T00:00:00Z',
    is_active: true,
    is_staff: false,
    is_moderator: false,
  };

  const mockLoginCredentials: LoginCredentials = {
    email: 'test@example.com',
    password: 'testpassword123',
  };

  const mockSignupData: SignupData = {
    username: 'testuser',
    first_name: 'Test',
    last_name: 'User',
    email: 'test@example.com',
    password: 'testpassword123',
  };

  const mockAuthResponse: AuthResponse = {
    user: mockUser,
  };

  // Mock implementations
  let fetchMock: ReturnType<typeof vi.fn>;
  let sessionStorageMock: {
    getItem: ReturnType<typeof vi.fn>;
    setItem: ReturnType<typeof vi.fn>;
    removeItem: ReturnType<typeof vi.fn>;
    clear: ReturnType<typeof vi.fn>;
  };
  let documentCookieMock: string;

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // Mock sessionStorage
    sessionStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'sessionStorage', {
      value: sessionStorageMock,
      writable: true,
    });

    // Mock document.cookie
    documentCookieMock = 'csrftoken=test-csrf-token';
    Object.defineProperty(document, 'cookie', {
      get: () => documentCookieMock,
      set: (value: string) => {
        documentCookieMock = value;
      },
      configurable: true,
    });

    // Clear all mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================================
  // LOGIN TESTS
  // ============================================================================

  describe('login', () => {
    it('should authenticate with valid credentials', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      const result = await login(mockLoginCredentials);

      // Assert
      expect(result).toEqual(mockUser);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/login/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-CSRFToken': 'test-csrf-token',
          }),
          credentials: 'include',
          body: JSON.stringify(mockLoginCredentials),
        })
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(mockUser)
      );
    });

    it('should fetch CSRF token if not present in cookie', async () => {
      // Arrange
      documentCookieMock = ''; // No CSRF token

      // Mock CSRF fetch
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      // Mock login
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await login(mockLoginCredentials);

      // Assert
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/v1/auth/csrf/'),
        expect.objectContaining({
          method: 'GET',
          credentials: 'include',
        })
      );
    });

    it('should handle invalid credentials (401)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ message: 'Invalid email or password' }),
      });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow(
        'Invalid email or password'
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalled();
    });

    it('should handle network errors with retry logic', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Network error');
      expect(sessionStorageMock.setItem).not.toHaveBeenCalled();
    });

    it('should include CSRF token in request headers', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await login(mockLoginCredentials);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle missing error message gracefully', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}), // No message
      });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Login failed');
    });
  });

  // ============================================================================
  // SIGNUP TESTS
  // ============================================================================

  describe('signup', () => {
    it('should create new user account', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      const result = await signup(mockSignupData);

      // Assert
      expect(result).toEqual(mockUser);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/register/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-CSRFToken': 'test-csrf-token',
          }),
          credentials: 'include',
          body: JSON.stringify(mockSignupData),
        })
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(mockUser)
      );
    });

    it('should validate CSRF token is present', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await signup(mockSignupData);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle duplicate email error (409)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ message: 'Email already exists' }),
      });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow('Email already exists');
      expect(sessionStorageMock.setItem).not.toHaveBeenCalled();
    });

    it('should handle validation errors (400)', async () => {
      // Arrange
      const validationError = {
        error: {
          message: 'Password must be at least 8 characters',
        },
      };
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => validationError,
      });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow(
        'Password must be at least 8 characters'
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalled();
    });

    it('should handle non-JSON error responses', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow(
        'Signup failed with status 500'
      );
    });

    it('should fetch CSRF token if not present', async () => {
      // Arrange
      documentCookieMock = ''; // No CSRF token

      // Mock CSRF fetch
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      // Mock signup
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await signup(mockSignupData);

      // Assert
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/v1/auth/csrf/'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // LOGOUT TESTS
  // ============================================================================

  describe('logout', () => {
    it('should clear sessionStorage and call logout endpoint', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      // Act
      await logout();

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/logout/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-CSRFToken': 'test-csrf-token',
          }),
          credentials: 'include',
        })
      );
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should clear sessionStorage even if API fails', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      // Act
      await logout();

      // Assert
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should clear sessionStorage even on network error', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(logout()).rejects.toThrow('Network error');
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });
  });

  // ============================================================================
  // GET CURRENT USER TESTS
  // ============================================================================

  describe('getCurrentUser', () => {
    it('should fetch user profile with valid authentication', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/user/'),
        expect.objectContaining({
          method: 'GET',
          credentials: 'include',
        })
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(mockUser)
      );
    });

    it('should return null and clear sessionStorage if not authenticated (401)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toBeNull();
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should fallback to sessionStorage on network error', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));
      sessionStorageMock.getItem.mockReturnValueOnce(JSON.stringify(mockUser));

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(sessionStorageMock.getItem).toHaveBeenCalledWith('user');
    });

    it('should return null if sessionStorage fallback is empty', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));
      sessionStorageMock.getItem.mockReturnValueOnce(null);

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toBeNull();
    });
  });

  // ============================================================================
  // GET STORED USER TESTS (Synchronous)
  // ============================================================================

  describe('getStoredUser', () => {
    it('should return user from sessionStorage', () => {
      // Arrange
      sessionStorageMock.getItem.mockReturnValueOnce(JSON.stringify(mockUser));

      // Act
      const result = getStoredUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(sessionStorageMock.getItem).toHaveBeenCalledWith('user');
    });

    it('should return null if sessionStorage is empty', () => {
      // Arrange
      sessionStorageMock.getItem.mockReturnValueOnce(null);

      // Act
      const result = getStoredUser();

      // Assert
      expect(result).toBeNull();
    });

    it('should handle invalid JSON gracefully', () => {
      // Arrange
      sessionStorageMock.getItem.mockReturnValueOnce('invalid-json');

      // Act
      const result = getStoredUser();

      // Assert
      expect(result).toBeNull();
    });
  });
});
