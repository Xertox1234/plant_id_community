import { Outlet } from 'react-router-dom'
import Header from '../components/layout/Header'
import Footer from '../components/layout/Footer'

/**
 * RootLayout Component
 *
 * Main layout wrapper that provides consistent header and footer
 * across all public pages. Uses React Router's Outlet for child routes.
 */
export default function RootLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
