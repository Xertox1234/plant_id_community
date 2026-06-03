import { Link } from 'react-router-dom';
import { useState, MouseEvent } from 'react';
import { toggleFavorite, deleteDiagnosisCard } from '../../services/diagnosisService';
import { logger } from '../../utils/logger';
import type { DiagnosisCard as DiagnosisCardType } from '@/types/diagnosis';

/**
 * Get status badge color based on treatment status
 */
function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    not_started: 'bg-surface-3 text-ink-2',
    in_progress: 'bg-sky/10 text-ink',
    successful: 'bg-leaf/10 text-ink',
    failed: 'bg-error/10 text-ink',
    monitoring: 'bg-warn/10 text-ink',
  };
  return colors[status] || 'bg-surface-3 text-ink-2';
}

/**
 * Get severity badge color
 */
function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
    mild: 'bg-leaf/10 text-ink ring-leaf/20',
    moderate: 'bg-warn/10 text-ink ring-warn/20',
    severe: 'bg-tertiary/10 text-ink ring-tertiary/20',
    critical: 'bg-error/10 text-ink ring-error/20',
  };
  return colors[severity] || 'bg-surface-2 text-ink-2 ring-line/20';
}

/**
 * Format date to readable string
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

interface DiagnosisCardProps {
  card: DiagnosisCardType;
  onUpdate?: (card: DiagnosisCardType) => void;
  onDelete?: (uuid: string) => void;
  compact?: boolean;
}

export default function DiagnosisCard({
  card,
  onUpdate,
  onDelete,
  compact = false,
}: DiagnosisCardProps) {
  const [isFavorite, setIsFavorite] = useState<boolean>(card.is_favorite);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isTogglingFavorite, setIsTogglingFavorite] = useState<boolean>(false);

  /**
   * Handle favorite toggle
   */
  const handleToggleFavorite = async (e: MouseEvent<HTMLButtonElement>): Promise<void> => {
    e.preventDefault(); // Prevent navigation
    e.stopPropagation();

    try {
      setIsTogglingFavorite(true);
      const updated = await toggleFavorite(card.uuid);
      setIsFavorite(updated.is_favorite);
      if (onUpdate) onUpdate(updated);
      logger.info('[DiagnosisCard] Toggled favorite', {
        uuid: card.uuid,
        isFavorite: updated.is_favorite,
      });
    } catch (error) {
      logger.error('[DiagnosisCard] Failed to toggle favorite:', error);
      alert('Failed to update favorite status. Please try again.');
    } finally {
      setIsTogglingFavorite(false);
    }
  };

  /**
   * Handle card deletion
   */
  const handleDelete = async (e: MouseEvent<HTMLButtonElement>): Promise<void> => {
    e.preventDefault();
    e.stopPropagation();

    if (!confirm(`Are you sure you want to delete this diagnosis for "${card.display_name}"?`)) {
      return;
    }

    try {
      setIsDeleting(true);
      await deleteDiagnosisCard(card.uuid);
      if (onDelete) onDelete(card.uuid);
      logger.info('[DiagnosisCard] Deleted card', { uuid: card.uuid });
    } catch (error) {
      logger.error('[DiagnosisCard] Failed to delete:', error);
      alert('Failed to delete diagnosis card. Please try again.');
      setIsDeleting(false);
    }
  };

  if (compact) {
    // Compact view for sidebars
    return (
      <Link
        to={`/diagnosis/${card.uuid}`}
        className="block p-3 rounded-lg border border-line hover:border-primary hover:shadow-sm transition-all"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-ink truncate text-sm">{card.display_name}</h4>
            <p className="text-xs text-ink-2 truncate mt-0.5">{card.disease_name}</p>
          </div>
          {isFavorite && (
            <svg
              className="w-4 h-4 text-tertiary flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          )}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(card.treatment_status)}`}
          >
            {card.treatment_status_display}
          </span>
        </div>
      </Link>
    );
  }

  // Full card view
  return (
    <div className="bg-surface-2 rounded-lg border border-line hover:border-primary hover:shadow-md transition-all overflow-hidden">
      <Link to={`/diagnosis/${card.uuid}`} className="block">
        {/* Header */}
        <div className="p-5 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-lg text-ink truncate">{card.display_name}</h3>
              {card.plant_scientific_name && card.plant_scientific_name !== card.display_name && (
                <p className="text-sm text-ink-3 italic truncate mt-0.5">
                  {card.plant_scientific_name}
                </p>
              )}
            </div>

            {/* Favorite button */}
            <button
              onClick={handleToggleFavorite}
              disabled={isTogglingFavorite}
              className="flex-shrink-0 p-1.5 rounded-full hover:bg-surface-3 transition-colors disabled:opacity-50"
              aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            >
              <svg
                className={`w-5 h-5 ${isFavorite ? 'text-tertiary fill-current' : 'text-ink-3'}`}
                fill={isFavorite ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                />
              </svg>
            </button>
          </div>

          {/* Disease information */}
          <div className="mt-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-error/10 text-ink ring-1 ring-inset ring-error/30">
                {card.disease_name}
              </span>
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ring-1 ring-inset ${getSeverityColor(card.severity_assessment)}`}
              >
                {card.severity_display}
              </span>
              {card.disease_type_display && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-surface-3 text-ink-2">
                  {card.disease_type_display}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-surface border-t border-line">
          <div className="flex items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-4">
              {/* Treatment status */}
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded text-xs font-medium ${getStatusColor(card.treatment_status)}`}
              >
                {card.treatment_status_display}
              </span>

              {/* Confidence score */}
              <span className="text-ink-2">
                {Math.round(card.confidence_score * 100)}% confidence
              </span>
            </div>

            {/* Saved date */}
            <span className="text-ink-3 text-xs">Saved {formatDate(card.saved_at)}</span>
          </div>

          {/* Plant recovery indicator */}
          {card.plant_recovered !== null && (
            <div className="mt-2 pt-2 border-t border-line">
              {card.plant_recovered ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-leaf">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Plant recovered
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Still treating
                </span>
              )}
            </div>
          )}
        </div>
      </Link>

      {/* Action buttons */}
      <div className="px-5 py-3 bg-surface-2 border-t border-line">
        <div className="flex items-center justify-between gap-2">
          <Link
            to={`/diagnosis/${card.uuid}`}
            className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-primary text-sm font-medium rounded-md text-primary bg-surface-2 hover:bg-primary/10 transition-colors"
          >
            View Details
          </Link>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="px-4 py-2 border border-error/30 text-sm font-medium rounded-md text-error bg-surface-2 hover:bg-error/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}
