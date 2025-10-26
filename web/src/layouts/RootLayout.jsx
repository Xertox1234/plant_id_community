import { Outlet } from 'react-router-dom'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'

/**
 * RootLayout Component
 *
 * Main layout wrapper that provides consistent header and footer
 * across all public pages. Uses React Router's Outlet for child routes.
 *
 * Includes skip navigation link for accessibility (keyboard users).
 */
export default function RootLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Skip Navigation Link - Accessibility feature for keyboard users */}
      <a href="#main-content" className="skip-nav">
        Skip to main content
      </a>

      <Header />
      <main id="main-content" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
