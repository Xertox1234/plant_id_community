import { Link } from 'react-router-dom'
import { useState, MouseEvent } from 'react'
import { toggleFavorite, deleteDiagnosisCard } from '../../services/diagnosisService'
import { logger } from '../../utils/logger'
import type { DiagnosisCard as DiagnosisCardType } from '@/types/diagnosis'

/**
 * Get status badge color based on treatment status
 */
function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
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
function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
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
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(date)
}

interface DiagnosisCardProps {
  card: DiagnosisCardType;
  onUpdate?: (card: DiagnosisCardType) => void;
  onDelete?: (uuid: string) => void;
  compact?: boolean;
}

export default function DiagnosisCard({ card, onUpdate, onDelete, compact = false }: DiagnosisCardProps) {
  const [isFavorite, setIsFavorite] = useState<boolean>(card.is_favorite)
  const [isDeleting, setIsDeleting] = useState<boolean>(false)
  const [isTogglingFavorite, setIsTogglingFavorite] = useState<boolean>(false)

  /**
   * Handle favorite toggle
   */
  const handleToggleFavorite = async (e: MouseEvent<HTMLButtonElement>): Promise<void> => {
    e.preventDefault() // Prevent navigation
    e.stopPropagation()

    try {
      setIsTogglingFavorite(true)
      const updated = await toggleFavorite(card.uuid)
      setIsFavorite(updated.is_favorite)
      if (onUpdate) onUpdate(updated)
      logger.info('[DiagnosisCard] Toggled favorite', { uuid: card.uuid, isFavorite: updated.is_favorite })
    } catch (error) {
      logger.error('[DiagnosisCard] Failed to toggle favorite:', error)
      alert('Failed to update favorite status. Please try again.')
    } finally {
      setIsTogglingFavorite(false)
    }
  }

  /**
   * Handle card deletion
   */
  const handleDelete = async (e: MouseEvent<HTMLButtonElement>): Promise<void> => {
    e.preventDefault()
    e.stopPropagation()

    if (!confirm(`Are you sure you want to delete this diagnosis for "${card.display_name}"?`)) {
      return
    }

    try {
      setIsDeleting(true)
      await deleteDiagnosisCard(card.uuid)
      if (onDelete) onDelete(card.uuid)
      logger.info('[DiagnosisCard] Deleted card', { uuid: card.uuid })
    } catch (error) {
      logger.error('[DiagnosisCard] Failed to delete:', error)
      alert('Failed to delete diagnosis card. Please try again.')
      setIsDeleting(false)
    }
  }

  if (compact) {
    // Compact view for sidebars
    return (
      <Link
        to={`/diagnosis/${card.uuid}`}
        className="block p-3 rounded-lg border border-gray-200 hover:border-green-500 hover:shadow-sm transition-all"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-gray-900 truncate text-sm">
              {card.display_name}
            </h4>
            <p className="text-xs text-gray-600 truncate mt-0.5">
              {card.disease_name}
            </p>
          </div>
          {isFavorite && (
            <svg className="w-4 h-4 text-yellow-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          )}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(card.treatment_status)}`}>
            {card.treatment_status_display}
          </span>
        </div>
      </Link>
    )
  }

  // Full card view
  return (
    <div className="bg-white rounded-lg border border-gray-200 hover:border-green-500 hover:shadow-md transition-all overflow-hidden">
      <Link to={`/diagnosis/${card.uuid}`} className="block">
        {/* Header */}
        <div className="p-5 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-lg text-gray-900 truncate">
                {card.display_name}
              </h3>
              {card.plant_scientific_name && card.plant_scientific_name !== card.display_name && (
                <p className="text-sm text-gray-500 italic truncate mt-0.5">
                  {card.plant_scientific_name}
                </p>
              )}
            </div>

            {/* Favorite button */}
            <button
              onClick={handleToggleFavorite}
              disabled={isTogglingFavorite}
              className="flex-shrink-0 p-1.5 rounded-full hover:bg-gray-100 transition-colors disabled:opacity-50"
              aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            >
              <svg
                className={`w-5 h-5 ${isFavorite ? 'text-yellow-400 fill-current' : 'text-gray-400'}`}
                fill={isFavorite ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
            </button>
          </div>

          {/* Disease information */}
          <div className="mt-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/10">
                {card.disease_name}
              </span>
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ring-1 ring-inset ${getSeverityColor(card.severity_assessment)}`}>
                {card.severity_display}
              </span>
              {card.disease_type_display && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                  {card.disease_type_display}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-gray-50 border-t border-gray-100">
          <div className="flex items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-4">
              {/* Treatment status */}
              <span className={`inline-flex items-center px-2.5 py-1 rounded text-xs font-medium ${getStatusColor(card.treatment_status)}`}>
                {card.treatment_status_display}
              </span>

              {/* Confidence score */}
              <span className="text-gray-600">
                {Math.round(card.confidence_score * 100)}% confidence
              </span>
            </div>

            {/* Saved date */}
            <span className="text-gray-500 text-xs">
              Saved {formatDate(card.saved_at)}
            </span>
          </div>

          {/* Plant recovery indicator */}
          {card.plant_recovered !== null && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              {card.plant_recovered ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-green-700">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Plant recovered
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs text-gray-600">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  Still treating
                </span>
              )}
            </div>
          )}
        </div>
      </Link>

      {/* Action buttons */}
      <div className="px-5 py-3 bg-white border-t border-gray-100">
        <div className="flex items-center justify-between gap-2">
          <Link
            to={`/diagnosis/${card.uuid}`}
            className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-green-600 text-sm font-medium rounded-md text-green-600 bg-white hover:bg-green-50 transition-colors"
          >
            View Details
          </Link>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="px-4 py-2 border border-red-300 text-sm font-medium rounded-md text-red-600 bg-white hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}
