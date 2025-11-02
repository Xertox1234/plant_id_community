/**
 * DiagnosisDetailPage Component
 *
 * Detailed view of a single diagnosis card with:
 * - Full care instructions (StreamField blocks)
 * - Treatment tracking and status updates
 * - Personal notes editing
 * - Reminder management
 * - Plant recovery tracking
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  fetchDiagnosisCard,
  updateDiagnosisCard,
  deleteDiagnosisCard,
  toggleFavorite,
  fetchReminders,
  createReminder,
} from '../../services/diagnosisService'
import logger from '../../utils/logger'

/**
 * Get status badge color based on treatment status
 */
function getStatusColor(status) {
  const colors = {
    not_started: 'bg-gray-100 text-gray-800',
    in_progress: 'bg-blue-100 text-blue-800',
    successful: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    monitoring: 'bg-yellow-100 text-yellow-800'
  }
  return colors[status] || 'bg-gray-100 text-gray-800'
}

/**
 * Get severity badge color
 */
function getSeverityColor(severity) {
  const colors = {
    mild: 'bg-green-50 text-green-700 ring-green-600/20',
    moderate: 'bg-yellow-50 text-yellow-700 ring-yellow-600/20',
    severe: 'bg-orange-50 text-orange-700 ring-orange-600/20',
    critical: 'bg-red-50 text-red-700 ring-red-600/20'
  }
  return colors[severity] || 'bg-gray-50 text-gray-700 ring-gray-600/20'
}

/**
 * Format date to readable string
 */
function formatDate(dateString) {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(date)
}

/**
 * Format datetime to readable string
 */
function formatDateTime(dateString) {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

/**
 * StreamField Block Renderer
 */
function StreamFieldBlock({ block }) {
  const { type, value } = block

  switch (type) {
    case 'heading':
      return <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">{value}</h3>

    case 'paragraph':
      return <p className="text-gray-700 mb-4 leading-relaxed">{value}</p>

    case 'treatment_step':
      return (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-blue-500 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-blue-900 mb-1">{value.title}</h4>
              <p className="text-blue-800">{value.description}</p>
              {value.frequency && (
                <p className="text-sm text-blue-700 mt-2">Frequency: {value.frequency}</p>
              )}
            </div>
          </div>
        </div>
      )

    case 'symptom_check':
      return (
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 mb-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-yellow-500 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-yellow-900 mb-1">Symptom Check: {value.symptom}</h4>
              <p className="text-yellow-800">{value.what_to_look_for}</p>
            </div>
          </div>
        </div>
      )

    case 'prevention_tip':
      return (
        <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-green-500 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-green-900 mb-1">Prevention Tip</h4>
              <p className="text-green-800">{value}</p>
            </div>
          </div>
        </div>
      )

    case 'list_block':
      return (
        <ul className="list-disc list-inside space-y-2 mb-4 text-gray-700">
          {value.items.map((item, index) => (
            <li key={index} className="ml-4">{item}</li>
          ))}
        </ul>
      )

    case 'image':
      return (
        <div className="mb-6">
          <img
            src={value.url}
            alt={value.alt_text || 'Care instruction image'}
            className="rounded-lg w-full max-w-2xl mx-auto"
          />
          {value.caption && (
            <p className="text-sm text-gray-600 text-center mt-2 italic">{value.caption}</p>
          )}
        </div>
      )

    default:
      logger.warn('[StreamFieldBlock] Unknown block type:', type)
      return null
  }
}

export default function DiagnosisDetailPage() {
  const { uuid } = useParams()
  const navigate = useNavigate()

  // Card data
  const [card, setCard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Edit mode
  const [isEditingNotes, setIsEditingNotes] = useState(false)
  const [editedNotes, setEditedNotes] = useState('')
  const [isSavingNotes, setIsSavingNotes] = useState(false)

  // Treatment status update
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)

  // Reminders
  const [reminders, setReminders] = useState([])
  const [showReminderForm, setShowReminderForm] = useState(false)

  /**
   * Load card data
   */
  useEffect(() => {
    loadCard()
    loadReminders()
  }, [uuid])

  const loadCard = async () => {
    try {
      setLoading(true)
      setError(null)

      logger.info('[DiagnosisDetailPage] Loading card', { uuid })

      const data = await fetchDiagnosisCard(uuid)
      setCard(data)
      setEditedNotes(data.personal_notes || '')

      logger.info('[DiagnosisDetailPage] Card loaded', { uuid, display_name: data.display_name })
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to load card:', err)
      setError(err.message || 'Failed to load diagnosis card')
    } finally {
      setLoading(false)
    }
  }

  const loadReminders = async () => {
    try {
      const data = await fetchReminders({ diagnosis_card: uuid, is_active: true })
      setReminders(data.results || [])
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to load reminders:', err)
    }
  }

  /**
   * Handle favorite toggle
   */
  const handleToggleFavorite = async () => {
    try {
      const updated = await toggleFavorite(uuid)
      setCard(updated)
      logger.info('[DiagnosisDetailPage] Toggled favorite', { uuid, isFavorite: updated.is_favorite })
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to toggle favorite:', err)
      alert('Failed to update favorite status. Please try again.')
    }
  }

  /**
   * Handle treatment status update
   */
  const handleStatusUpdate = async (newStatus) => {
    try {
      setIsUpdatingStatus(true)
      const updated = await updateDiagnosisCard(uuid, { treatment_status: newStatus })
      setCard(updated)
      logger.info('[DiagnosisDetailPage] Updated status', { uuid, status: newStatus })
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to update status:', err)
      alert('Failed to update treatment status. Please try again.')
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  /**
   * Handle plant recovery toggle
   */
  const handleRecoveryToggle = async () => {
    try {
      const newRecoveryStatus = card.plant_recovered === null ? true : !card.plant_recovered
      const updated = await updateDiagnosisCard(uuid, { plant_recovered: newRecoveryStatus })
      setCard(updated)
      logger.info('[DiagnosisDetailPage] Updated recovery status', { uuid, recovered: newRecoveryStatus })
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to update recovery status:', err)
      alert('Failed to update recovery status. Please try again.')
    }
  }

  /**
   * Handle notes save
   */
  const handleSaveNotes = async () => {
    try {
      setIsSavingNotes(true)
      const updated = await updateDiagnosisCard(uuid, { personal_notes: editedNotes })
      setCard(updated)
      setIsEditingNotes(false)
      logger.info('[DiagnosisDetailPage] Saved notes', { uuid })
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to save notes:', err)
      alert('Failed to save notes. Please try again.')
    } finally {
      setIsSavingNotes(false)
    }
  }

  /**
   * Handle card deletion
   */
  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete this diagnosis for "${card.display_name}"? This cannot be undone.`)) {
      return
    }

    try {
      await deleteDiagnosisCard(uuid)
      logger.info('[DiagnosisDetailPage] Deleted card', { uuid })
      navigate('/diagnosis')
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to delete:', err)
      alert('Failed to delete diagnosis card. Please try again.')
    }
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-green-500 border-t-transparent"></div>
            <p className="mt-4 text-gray-600">Loading diagnosis details...</p>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (error || !card) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <svg className="w-12 h-12 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Failed to Load Diagnosis</h3>
            <p className="text-red-700 mb-4">{error || 'Diagnosis card not found'}</p>
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={loadCard}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
              >
                Try Again
              </button>
              <Link
                to="/diagnosis"
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Back to List
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm">
          <ol className="flex items-center space-x-2 text-gray-600">
            <li>
              <Link to="/diagnosis" className="hover:text-green-600">
                My Diagnoses
              </Link>
            </li>
            <li className="flex items-center">
              <svg className="w-4 h-4 mx-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
              <span className="text-gray-900">{card.display_name}</span>
            </li>
          </ol>
        </nav>

        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">{card.display_name}</h1>
              {card.plant_scientific_name && card.plant_scientific_name !== card.display_name && (
                <p className="text-lg text-gray-500 italic mb-4">{card.plant_scientific_name}</p>
              )}

              {/* Disease Information */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/10">
                  {card.disease_name}
                </span>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ring-1 ring-inset ${getSeverityColor(card.severity_assessment)}`}>
                  {card.severity_display}
                </span>
                {card.disease_type_display && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-700">
                    {card.disease_type_display}
                  </span>
                )}
                <span className="text-sm text-gray-600">
                  {Math.round(card.confidence_score * 100)}% confidence
                </span>
              </div>

              {/* Metadata */}
              <div className="text-sm text-gray-600 space-y-1">
                <p>Saved on {formatDate(card.saved_at)}</p>
                {card.last_viewed_at && (
                  <p>Last viewed on {formatDate(card.last_viewed_at)}</p>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-start gap-2">
              <button
                onClick={handleToggleFavorite}
                className="p-2 rounded-full hover:bg-gray-100 transition-colors"
                aria-label={card.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
              >
                <svg
                  className={`w-6 h-6 ${card.is_favorite ? 'text-yellow-400 fill-current' : 'text-gray-400'}`}
                  fill={card.is_favorite ? 'currentColor' : 'none'}
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </svg>
              </button>
              <button
                onClick={handleDelete}
                className="p-2 rounded-full text-red-600 hover:bg-red-50 transition-colors"
                aria-label="Delete diagnosis"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Treatment Status */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Treatment Status</h2>

          <div className="space-y-4">
            {/* Current Status */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Current Status
              </label>
              <select
                value={card.treatment_status}
                onChange={(e) => handleStatusUpdate(e.target.value)}
                disabled={isUpdatingStatus}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500 disabled:opacity-50"
              >
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="successful">Successful</option>
                <option value="failed">Failed</option>
                <option value="monitoring">Monitoring</option>
              </select>
            </div>

            {/* Plant Recovery */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Plant Recovery
              </label>
              <button
                onClick={handleRecoveryToggle}
                className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
                  card.plant_recovered === true
                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                    : card.plant_recovered === false
                    ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {card.plant_recovered === true ? (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Plant Recovered
                  </>
                ) : card.plant_recovered === false ? (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    Still Treating
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Mark Recovery Status
                  </>
                )}
              </button>
            </div>

            {/* Active Reminders Count */}
            {reminders.length > 0 && (
              <div className="pt-4 border-t border-gray-200">
                <p className="text-sm text-gray-600">
                  {reminders.length} active {reminders.length === 1 ? 'reminder' : 'reminders'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Care Instructions */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Care Instructions</h2>

          {card.care_instructions && card.care_instructions.length > 0 ? (
            <div className="prose prose-green max-w-none">
              {card.care_instructions.map((block, index) => (
                <StreamFieldBlock key={index} block={block} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 italic">No care instructions available for this diagnosis.</p>
          )}
        </div>

        {/* Personal Notes */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Personal Notes</h2>
            {!isEditingNotes && (
              <button
                onClick={() => setIsEditingNotes(true)}
                className="text-sm text-green-600 hover:text-green-700 font-medium"
              >
                Edit
              </button>
            )}
          </div>

          {isEditingNotes ? (
            <div>
              <textarea
                value={editedNotes}
                onChange={(e) => setEditedNotes(e.target.value)}
                rows="6"
                placeholder="Add your observations, progress notes, or reminders..."
                className="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
              />
              <div className="flex items-center gap-2 mt-4">
                <button
                  onClick={handleSaveNotes}
                  disabled={isSavingNotes}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50"
                >
                  {isSavingNotes ? 'Saving...' : 'Save Notes'}
                </button>
                <button
                  onClick={() => {
                    setIsEditingNotes(false)
                    setEditedNotes(card.personal_notes || '')
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div>
              {card.personal_notes ? (
                <p className="text-gray-700 whitespace-pre-wrap">{card.personal_notes}</p>
              ) : (
                <p className="text-gray-500 italic">No personal notes yet. Click "Edit" to add your observations.</p>
              )}
            </div>
          )}
        </div>

        {/* Diagnosis Info */}
        {card.diagnosis_result_info && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Diagnosis Information</h2>
            <div className="space-y-2 text-sm text-gray-600">
              <p>
                <span className="font-medium">Source:</span>{' '}
                {card.diagnosis_result_info.diagnosis_source === 'plant_id' ? 'Plant.id' : 'PlantNet'}
              </p>
              <p>
                <span className="font-medium">Diagnosed on:</span>{' '}
                {formatDateTime(card.diagnosis_result_info.diagnosed_at)}
              </p>
              <Link
                to={`/results/${card.diagnosis_result_info.id}`}
                className="inline-flex items-center text-green-600 hover:text-green-700 font-medium mt-2"
              >
                View Original Diagnosis
                <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
