import { Routes, Route } from 'react-router-dom'
import RootLayout from './layouts/RootLayout'
import ProtectedLayout from './layouts/ProtectedLayout'
import HomePage from './pages/HomePage'
import IdentifyPage from './pages/IdentifyPage'
import BlogListPage from './pages/BlogListPage'
import BlogDetailPage from './pages/BlogDetailPage'
import BlogPreview from './pages/BlogPreview'
import ForumPage from './pages/ForumPage'
import LoginPage from './pages/auth/LoginPage'
import SignupPage from './pages/auth/SignupPage'
import ProfilePage from './pages/ProfilePage'
import SettingsPage from './pages/SettingsPage'

/**
 * App Component
 *
 * Root application component with routing configuration.
 * - RootLayout: Provides header/footer for all routes
 * - ProtectedLayout: Wraps protected routes, redirects to login if not authenticated
 */
function App() {
  return (
    <Routes>
      {/* Public routes with shared layout */}
      <Route element={<RootLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/identify" element={<IdentifyPage />} />
        <Route path="/blog" element={<BlogListPage />} />
        <Route path="/blog/:slug" element={<BlogDetailPage />} />
        <Route path="/blog/preview/:content_type/:token" element={<BlogPreview />} />
        <Route path="/forum" element={<ForumPage />} />

        {/* Authentication routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>

      {/* Protected routes - requires authentication */}
      <Route element={<ProtectedLayout />}>
        <Route element={<RootLayout />}>
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
