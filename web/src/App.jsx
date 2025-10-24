import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import IdentifyPage from './pages/IdentifyPage'
import BlogListPage from './pages/BlogListPage'
import BlogDetailPage from './pages/BlogDetailPage'
import BlogPreview from './pages/BlogPreview'
import ForumPage from './pages/ForumPage'

function App() {
  return (
    <div className="min-h-screen bg-white">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/identify" element={<IdentifyPage />} />
        <Route path="/blog" element={<BlogListPage />} />
        <Route path="/blog/:slug" element={<BlogDetailPage />} />
        <Route path="/blog/preview/:content_type/:token" element={<BlogPreview />} />
        <Route path="/forum" element={<ForumPage />} />
      </Routes>
    </div>
  )
}

export default App
