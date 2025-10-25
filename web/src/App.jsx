import { Routes, Route } from 'react-router-dom'
import RootLayout from './layouts/RootLayout'
import HomePage from './pages/HomePage'
import IdentifyPage from './pages/IdentifyPage'
import BlogListPage from './pages/BlogListPage'
import BlogDetailPage from './pages/BlogDetailPage'
import BlogPreview from './pages/BlogPreview'
import ForumPage from './pages/ForumPage'

/**
 * App Component
 *
 * Root application component with routing configuration.
 * Uses RootLayout for consistent header/footer across all public routes.
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
      </Route>
    </Routes>
  )
}

export default App
