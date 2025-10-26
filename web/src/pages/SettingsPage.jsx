/**
 * SettingsPage Component
 *
 * Application settings page (placeholder for Phase 5).
 * Allows users to configure app preferences and notifications.
 *
 * Features (planned):
 * - Email notifications preferences
 * - Privacy settings
 * - Theme preferences (light/dark mode)
 * - Language selection
 * - Account deletion
 */
export default function SettingsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="mt-2 text-gray-600">
          Manage your application preferences and account settings
        </p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-6">
        {/* Notifications Section */}
        <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Notifications
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">
                  Email Notifications
                </p>
                <p className="text-sm text-gray-600">
                  Receive updates about your plants and community activity
                </p>
              </div>
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed"
              >
                Coming Soon
              </button>
            </div>
          </div>
        </div>

        {/* Privacy Section */}
        <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Privacy</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">Profile Visibility</p>
                <p className="text-sm text-gray-600">
                  Control who can see your profile and plant collection
                </p>
              </div>
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed"
              >
                Coming Soon
              </button>
            </div>
          </div>
        </div>

        {/* Appearance Section */}
        <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Appearance
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">Theme</p>
                <p className="text-sm text-gray-600">
                  Choose between light and dark mode
                </p>
              </div>
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed"
              >
                Coming Soon
              </button>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="bg-white shadow-sm border border-red-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-red-900 mb-4">
            Danger Zone
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">Delete Account</p>
                <p className="text-sm text-gray-600">
                  Permanently delete your account and all associated data
                </p>
              </div>
              <button
                disabled
                className="px-4 py-2 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed"
              >
                Coming Soon
              </button>
            </div>
          </div>
        </div>

        {/* Placeholder Notice */}
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Coming Soon:</strong> Settings management features will be
            available in a future update. You can currently manage your profile
            information from the Profile page.
          </p>
        </div>
      </div>
    </div>
  )
}
