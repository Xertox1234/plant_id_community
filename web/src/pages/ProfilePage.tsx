import { useAuth } from '../contexts/AuthContext'

/**
 * ProfilePage Component
 *
 * User profile page (placeholder for Phase 5).
 * Displays user information and provides profile management options.
 *
 * Features (planned):
 * - View and edit profile information
 * - Change password
 * - Upload profile picture
 * - Manage account preferences
 */
export default function ProfilePage() {
  const { user } = useAuth()

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Profile</h1>
        <p className="mt-2 text-gray-600">
          Manage your account information and preferences
        </p>
      </div>

      {/* Profile Card */}
      <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-8">
        {/* User Avatar */}
        <div className="flex items-center gap-6 mb-8">
          <div className="w-24 h-24 rounded-full bg-green-600 text-white flex items-center justify-center text-3xl font-bold">
            {user?.name?.substring(0, 2).toUpperCase() ||
              user?.email?.substring(0, 2).toUpperCase() ||
              'U'}
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{user?.name}</h2>
            <p className="text-gray-600">{user?.email}</p>
          </div>
        </div>

        {/* Profile Information */}
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Account Information
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Full Name
                </label>
                <p className="text-gray-900">{user?.name || 'Not set'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email Address
                </label>
                <p className="text-gray-900">{user?.email}</p>
              </div>
            </div>
          </div>

          {/* Placeholder Notice */}
          <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>Coming Soon:</strong> Profile editing, password change,
              and profile picture upload features will be available in a future
              update.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
