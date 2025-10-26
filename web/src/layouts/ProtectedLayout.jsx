import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

/**
 * ProtectedLayout Component
 *
 * Wrapper for protected routes that require authentication.
 * Redirects unauthenticated users to login page with return URL.
 *
 * Features:
 * - Authentication check using AuthContext
 * - Loading state during auth verification
 * - Redirect to /login with return URL for post-login navigation
 * - Renders nested routes via <Outlet /> when authenticated
 *
 * @example
 * <Route element={<ProtectedLayout />}>
 *   <Route path="/profile" element={<ProfilePage />} />
 * </Route>
 */
export default function ProtectedLayout() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center" role="status" aria-live="polite">
          <div
            className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"
            aria-hidden="true"
          />
          <p className="mt-4 text-gray-600">Loading authentication...</p>
        </div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  // Save current location to redirect back after login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Render protected content
  return <Outlet />
}
