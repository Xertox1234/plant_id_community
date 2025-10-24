import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import IdentifyPage from './pages/IdentifyPage'
import BlogPage from './pages/BlogPage'
import BlogPreview from './pages/BlogPreview'
import ForumPage from './pages/ForumPage'

function App() {
  return (
    <div className="min-h-screen bg-white">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/identify" element={<IdentifyPage />} />
        <Route path="/blog" element={<BlogPage />} />
        <Route path="/blog/preview/:content_type/:token" element={<BlogPreview />} />
        <Route path="/forum" element={<ForumPage />} />
      </Routes>
    </div>
  )
}

export default App
