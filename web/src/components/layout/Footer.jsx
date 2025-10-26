import { Link } from 'react-router-dom'

/**
 * Footer Component
 *
 * Site footer with links and copyright notice.
 * Responsive layout with flexbox.
 */
export default function Footer() {
  return (
    <footer className="bg-gray-50 border-t border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand Section */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-500 rounded-lg" />
              <span className="text-lg font-bold text-gray-900">PlantID</span>
            </div>
            <p className="text-sm text-gray-600">
              Discover the world of plants with AI-powered identification.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">Quick Links</h3>
            <ul className="space-y-2">
              <li>
                <Link to="/identify" className="text-sm text-gray-600 hover:text-green-600">
                  Identify Plant
                </Link>
              </li>
              <li>
                <Link to="/blog" className="text-sm text-gray-600 hover:text-green-600">
                  Blog
                </Link>
              </li>
              <li>
                <Link to="/forum" className="text-sm text-gray-600 hover:text-green-600">
                  Community
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal Links */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-4">Legal</h3>
            <ul className="space-y-2">
              <li>
                <span className="text-sm text-gray-400 cursor-not-allowed" aria-disabled="true">
                  Privacy Policy (Coming Soon)
                </span>
              </li>
              <li>
                <span className="text-sm text-gray-400 cursor-not-allowed" aria-disabled="true">
                  Terms of Service (Coming Soon)
                </span>
              </li>
              <li>
                <span className="text-sm text-gray-400 cursor-not-allowed" aria-disabled="true">
                  About Us (Coming Soon)
                </span>
              </li>
            </ul>
          </div>
        </div>

        {/* Copyright */}
        <div className="mt-8 pt-8 border-t border-gray-200">
          <p className="text-sm text-gray-500 text-center">
            © {new Date().getFullYear()} Plant ID Community. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
