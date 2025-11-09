import { useState, useEffect, FormEvent, ChangeEvent } from 'react'
import {
  fetchReminders,
  createReminder,
  snoozeReminder,
  cancelReminder,
  deleteReminder,
} from '../../services/diagnosisService'
import { logger } from '../../utils/logger'
import type { DiagnosisReminder, ReminderType, PaginatedRemindersResponse } from '@/types/diagnosis'

/**
 * Format date to readable string
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  // If within 7 days, show relative
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Tomorrow'
  if (diffDays > 0 && diffDays < 7) return `In ${diffDays} days`
  if (diffDays < 0 && diffDays > -7) return `${Math.abs(diffDays)} days ago`

  // Otherwise show full date
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
}

/**
 * Reminder type options
 */
const REMINDER_TYPES: Array<{ value: ReminderType; label: string }> = [
  { value: 'check_progress', label: 'Check Progress' },
  { value: 'treatment_step', label: 'Treatment Step' },
  { value: 'follow_up', label: 'Follow-up' },
  { value: 'reapply', label: 'Reapply Treatment' },
]

/**
 * Individual reminder card
 */
interface ReminderCardProps {
  reminder: DiagnosisReminder;
  onUpdate: (reminder: DiagnosisReminder) => void;
  onDelete: (uuid: string) => void;
}

function ReminderCard({ reminder, onUpdate, onDelete }: ReminderCardProps) {
  const [isSnoozing, setIsSnoozing] = useState<boolean>(false)
  const [isCancelling, setIsCancelling] = useState<boolean>(false)
  const [isDeleting, setIsDeleting] = useState<boolean>(false)

  const handleSnooze = async (hours: number): Promise<void> => {
    try {
      setIsSnoozing(true)
      const updated = await snoozeReminder(reminder.uuid, hours)
      onUpdate(updated)
      logger.info('[ReminderCard] Snoozed reminder', { uuid: reminder.uuid, hours })
    } catch (err) {
      logger.error('[ReminderCard] Failed to snooze:', err)
      alert('Failed to snooze reminder. Please try again.')
    } finally {
      setIsSnoozing(false)
    }
  }

  const handleCancel = async (): Promise<void> => {
    if (!confirm('Are you sure you want to cancel this reminder?')) {
      return
    }

    try {
      setIsCancelling(true)
      const updated = await cancelReminder(reminder.uuid)
      onUpdate(updated)
      logger.info('[ReminderCard] Cancelled reminder', { uuid: reminder.uuid })
    } catch (err) {
      logger.error('[ReminderCard] Failed to cancel:', err)
      alert('Failed to cancel reminder. Please try again.')
    } finally {
      setIsCancelling(false)
    }
  }

  const handleDelete = async (): Promise<void> => {
    if (!confirm('Are you sure you want to delete this reminder permanently?')) {
      return
    }

    try {
      setIsDeleting(true)
      await deleteReminder(reminder.uuid)
      onDelete(reminder.uuid)
      logger.info('[ReminderCard] Deleted reminder', { uuid: reminder.uuid })
    } catch (err) {
      logger.error('[ReminderCard] Failed to delete:', err)
      alert('Failed to delete reminder. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }

  const isOverdue = new Date(reminder.scheduled_date) < new Date() && !reminder.sent
  const isSnoozed = reminder.snoozed_until && new Date(reminder.snoozed_until) > new Date()

  return (
    <div className={`border rounded-lg p-4 ${
      isOverdue ? 'bg-red-50 border-red-200' :
      isSnoozed ? 'bg-yellow-50 border-yellow-200' :
      'bg-white border-gray-200'
    }`}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1">
          <h4 className="font-semibold text-gray-900 mb-1">{reminder.reminder_title}</h4>
          {reminder.reminder_message && (
            <p className="text-sm text-gray-700 mb-2">{reminder.reminder_message}</p>
          )}
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <span className="inline-flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              {formatDate(reminder.scheduled_date)}
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
              {reminder.reminder_type_display}
            </span>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-2">
          {isOverdue && (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-700">
              Overdue
            </span>
          )}
          {isSnoozed && (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-700">
              Snoozed
            </span>
          )}
          {reminder.sent && (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">
              Sent
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      {reminder.is_active && !reminder.cancelled && (
        <div className="flex items-center gap-2 pt-3 border-t border-gray-200">
          <div className="flex-1 flex items-center gap-2">
            <button
              onClick={() => handleSnooze(24)}
              disabled={isSnoozing}
              className="text-sm text-gray-700 hover:text-gray-900 disabled:opacity-50"
            >
              Snooze 1 day
            </button>
            <span className="text-gray-300">|</span>
            <button
              onClick={() => handleSnooze(168)}
              disabled={isSnoozing}
              className="text-sm text-gray-700 hover:text-gray-900 disabled:opacity-50"
            >
              Snooze 1 week
            </button>
          </div>
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            className="text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
          >
            {isCancelling ? 'Cancelling...' : 'Cancel'}
          </button>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * Main ReminderManager Component
 */
interface ReminderManagerProps {
  diagnosisCardUuid: string;
}

export default function ReminderManager({ diagnosisCardUuid }: ReminderManagerProps) {
  const [reminders, setReminders] = useState<DiagnosisReminder[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Create reminder form
  const [showCreateForm, setShowCreateForm] = useState<boolean>(false)
  const [formData, setFormData] = useState({
    reminder_type: 'check_progress' as ReminderType,
    reminder_title: '',
    reminder_message: '',
    scheduled_date: '',
  })
  const [isCreating, setIsCreating] = useState<boolean>(false)

  /**
   * Load reminders
   */
  useEffect(() => {
    loadReminders()
  }, [diagnosisCardUuid])

  const loadReminders = async (): Promise<void> => {
    try {
      setLoading(true)
      setError(null)

      const data: PaginatedRemindersResponse = await fetchReminders({
        diagnosis_card: diagnosisCardUuid,
        is_active: true,
      })

      setReminders(data.results || [])
      logger.info('[ReminderManager] Loaded reminders', {
        count: data.results?.length || 0,
      })
    } catch (err) {
      const error = err as Error;
      logger.error('[ReminderManager] Failed to load reminders', { error })
      setError(error.message || 'Failed to load reminders')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Handle reminder update
   */
  const handleReminderUpdate = (updatedReminder: DiagnosisReminder): void => {
    setReminders(reminders.map(r =>
      r.uuid === updatedReminder.uuid ? updatedReminder : r
    ))
  }

  /**
   * Handle reminder deletion
   */
  const handleReminderDelete = (uuid: string): void => {
    setReminders(reminders.filter(r => r.uuid !== uuid))
  }

  /**
   * Handle create reminder
   */
  const handleCreateReminder = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault()

    if (!formData.reminder_title || !formData.scheduled_date) {
      alert('Please fill in all required fields')
      return
    }

    try {
      setIsCreating(true)

      const newReminder = await createReminder({
        diagnosis_card: diagnosisCardUuid,
        ...formData,
      })

      setReminders([...reminders, newReminder])
      setShowCreateForm(false)
      setFormData({
        reminder_type: 'check_progress',
        reminder_title: '',
        reminder_message: '',
        scheduled_date: '',
      })

      logger.info('[ReminderManager] Created reminder', { uuid: newReminder.uuid })
    } catch (err) {
      const error = err as Error;
      logger.error('[ReminderManager] Failed to create reminder', { error })
      alert(`Failed to create reminder: ${error.message}`)
    } finally {
      setIsCreating(false)
    }
  }

  /**
   * Get minimum date for reminder (tomorrow)
   */
  const getMinDate = (): string => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return tomorrow.toISOString().split('T')[0]
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          Reminders ({reminders.length})
        </h3>
        {!showCreateForm && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm font-medium"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Add Reminder
          </button>
        )}
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreateReminder} className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-medium text-gray-900">New Reminder</h4>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="text-gray-600 hover:text-gray-900"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div>
            <label htmlFor="reminder-type" className="block text-sm font-medium text-gray-700 mb-1">
              Reminder Type
            </label>
            <select
              id="reminder-type"
              value={formData.reminder_type}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => setFormData({ ...formData, reminder_type: e.target.value as ReminderType })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
            >
              {REMINDER_TYPES.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="reminder-title" className="block text-sm font-medium text-gray-700 mb-1">
              Title *
            </label>
            <input
              type="text"
              id="reminder-title"
              value={formData.reminder_title}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, reminder_title: e.target.value })}
              placeholder="e.g., Check for new growth"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
            />
          </div>

          <div>
            <label htmlFor="reminder-message" className="block text-sm font-medium text-gray-700 mb-1">
              Message (optional)
            </label>
            <textarea
              id="reminder-message"
              value={formData.reminder_message}
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setFormData({ ...formData, reminder_message: e.target.value })}
              placeholder="Additional notes or instructions..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
            />
          </div>

          <div>
            <label htmlFor="scheduled-date" className="block text-sm font-medium text-gray-700 mb-1">
              Scheduled Date *
            </label>
            <input
              type="date"
              id="scheduled-date"
              value={formData.scheduled_date}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, scheduled_date: e.target.value })}
              min={getMinDate()}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
            />
          </div>

          <div className="flex items-center gap-2 pt-2">
            <button
              type="submit"
              disabled={isCreating}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              {isCreating ? 'Creating...' : 'Create Reminder'}
            </button>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-4 border-green-500 border-t-transparent"></div>
          <p className="mt-2 text-sm text-gray-600">Loading reminders...</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
          <p className="text-red-700">{error}</p>
          <button
            onClick={loadReminders}
            className="mt-2 text-sm text-red-600 hover:text-red-700 font-medium"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Reminders List */}
      {!loading && !error && (
        <>
          {reminders.length === 0 ? (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
              <svg className="w-12 h-12 text-gray-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <p className="text-gray-600 mb-2">No active reminders</p>
              <p className="text-sm text-gray-500">
                Set reminders to track treatment progress and follow-up steps
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {reminders.map(reminder => (
                <ReminderCard
                  key={reminder.uuid}
                  reminder={reminder}
                  onUpdate={handleReminderUpdate}
                  onDelete={handleReminderDelete}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
