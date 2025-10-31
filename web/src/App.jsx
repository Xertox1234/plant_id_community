import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import RootLayout from './layouts/RootLayout'
import ProtectedLayout from './layouts/ProtectedLayout'
import LoadingSpinner from './components/ui/LoadingSpinner'

// Eagerly load critical routes (HomePage, LoginPage, SignupPage)
import HomePage from './pages/HomePage'
import LoginPage from './pages/auth/LoginPage'
import SignupPage from './pages/auth/SignupPage'

// Lazy load non-critical routes for better initial load performance
const IdentifyPage = lazy(() => import('./pages/IdentifyPage'))
const BlogListPage = lazy(() => import('./pages/BlogListPage'))
const BlogDetailPage = lazy(() => import('./pages/BlogDetailPage'))
const BlogPreview = lazy(() => import('./pages/BlogPreview'))
const CategoryListPage = lazy(() => import('./pages/forum/CategoryListPage'))
const ThreadListPage = lazy(() => import('./pages/forum/ThreadListPage'))
const ThreadDetailPage = lazy(() => import('./pages/forum/ThreadDetailPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

/**
 * App Component
 *
 * Root application component with routing configuration.
 * - RootLayout: Provides header/footer for all routes
 * - ProtectedLayout: Wraps protected routes, redirects to login if not authenticated
 * - Lazy loading: Non-critical routes load on-demand to reduce initial bundle size
 */
function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        {/* Public routes with shared layout */}
        <Route element={<RootLayout />}>
          {/* Critical routes (eagerly loaded) */}
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* Non-critical routes (lazy loaded) */}
          <Route path="/identify" element={<IdentifyPage />} />
          <Route path="/blog" element={<BlogListPage />} />
          <Route path="/blog/:slug" element={<BlogDetailPage />} />
          <Route path="/blog/preview/:content_type/:token" element={<BlogPreview />} />
          <Route path="/forum" element={<CategoryListPage />} />
          <Route path="/forum/:categorySlug" element={<ThreadListPage />} />
          <Route path="/forum/:categorySlug/:threadSlug" element={<ThreadDetailPage />} />
        </Route>

        {/* Protected routes - requires authentication */}
        <Route element={<ProtectedLayout />}>
          <Route element={<RootLayout />}>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
