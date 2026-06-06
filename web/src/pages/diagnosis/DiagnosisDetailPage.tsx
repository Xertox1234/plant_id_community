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

import { useState, useEffect, ChangeEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  fetchDiagnosisCard,
  updateDiagnosisCard,
  deleteDiagnosisCard,
  toggleFavorite,
  fetchReminders,
} from '../../services/diagnosisService';
import { logger } from '../../utils/logger';
import type {
  DiagnosisBlock,
  DiagnosisCard,
  DiagnosisReminder,
  TreatmentStatus,
  SeverityAssessment,
} from '@/types';

interface ReminderResults {
  results: DiagnosisReminder[];
}

/**
 * Get severity badge color
 */
function getSeverityColor(severity: SeverityAssessment): string {
  const colors: Record<SeverityAssessment, string> = {
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
    month: 'long',
    day: 'numeric',
  }).format(date);
}

/**
 * StreamField Block Renderer
 */
function StreamFieldBlockComponent({ block }: { block: DiagnosisBlock }) {
  switch (block.type) {
    case 'heading':
      return <h3 className="text-xl font-semibold text-ink mt-6 mb-3">{block.value}</h3>;

    case 'paragraph':
      return <p className="text-ink-2 mb-4 leading-relaxed">{block.value}</p>;

    case 'treatment_step': {
      const typedValue = block.value;
      return (
        <div className="bg-sky/10 border-l-4 border-sky p-4 mb-4">
          <div className="flex items-start">
            <svg
              className="w-5 h-5 text-sky mt-0.5 mr-3 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-sky mb-1">{typedValue.title}</h4>
              <p className="text-sky">{typedValue.description}</p>
              {typedValue.frequency && (
                <p className="text-sm text-sky mt-2">Frequency: {typedValue.frequency}</p>
              )}
            </div>
          </div>
        </div>
      );
    }

    case 'symptom_check': {
      const typedValue = block.value;
      return (
        <div className="bg-warn/10 border-l-4 border-warn p-4 mb-4">
          <div className="flex items-start">
            <svg
              className="w-5 h-5 text-warn mt-0.5 mr-3 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-warn mb-1">Symptom Check: {typedValue.symptom}</h4>
              <p className="text-warn">{typedValue.what_to_look_for}</p>
            </div>
          </div>
        </div>
      );
    }

    case 'prevention_tip':
      return (
        <div className="bg-leaf/10 border-l-4 border-leaf p-4 mb-4">
          <div className="flex items-start">
            <svg
              className="w-5 h-5 text-leaf mt-0.5 mr-3 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <h4 className="font-semibold text-leaf mb-1">Prevention Tip</h4>
              <p className="text-leaf">{block.value}</p>
            </div>
          </div>
        </div>
      );

    case 'list_block':
      return (
        <ul className="list-disc list-inside space-y-2 mb-4 text-ink-2">
          {block.value.items?.map((item, index) => (
            <li key={index} className="ml-4">
              {item}
            </li>
          ))}
        </ul>
      );

    case 'image': {
      const typedValue = block.value;
      return (
        <div className="mb-6">
          <img
            src={typedValue.url}
            alt={typedValue.alt_text || 'Care instruction image'}
            className="rounded-lg w-full max-w-2xl mx-auto"
          />
          {typedValue.caption && (
            <p className="text-sm text-ink-2 text-center mt-2 italic">{typedValue.caption}</p>
          )}
        </div>
      );
    }

    default:
      logger.warn('[StreamFieldBlock] Unknown block type', {
        component: 'StreamFieldBlock',
        context: { block },
      });
      return null;
  }
}

export default function DiagnosisDetailPage() {
  const { uuid } = useParams<{ uuid: string }>();
  const navigate = useNavigate();

  // Card data
  const [card, setCard] = useState<DiagnosisCard | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode
  const [isEditingNotes, setIsEditingNotes] = useState<boolean>(false);
  const [editedNotes, setEditedNotes] = useState<string>('');
  const [isSavingNotes, setIsSavingNotes] = useState<boolean>(false);

  // Treatment status update
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);

  // Reminders
  const [reminders, setReminders] = useState<DiagnosisReminder[]>([]);

  const loadCard = async () => {
    if (!uuid) return;

    try {
      setLoading(true);
      setError(null);

      logger.info('[DiagnosisDetailPage] Loading card', { uuid });

      const data = (await fetchDiagnosisCard(uuid)) as DiagnosisCard;
      setCard(data);
      setEditedNotes(data.personal_notes || '');

      logger.info('[DiagnosisDetailPage] Card loaded', {
        component: 'DiagnosisDetailPage',
        context: { uuid, display_name: data.display_name },
      });
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to load card:', err);
      setError(err instanceof Error ? err.message : 'Failed to load diagnosis card');
    } finally {
      setLoading(false);
    }
  };

  const loadReminders = async () => {
    if (!uuid) return;

    try {
      const data = (await fetchReminders({
        diagnosis_card: uuid,
        is_active: true,
      })) as ReminderResults;
      setReminders(data.results || []);
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to load reminders:', err);
    }
  };

  /**
   * Load card data
   */
  useEffect(() => {
    loadCard();
    loadReminders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid]);

  /**
   * Handle favorite toggle
   */
  const handleToggleFavorite = async () => {
    if (!uuid) return;

    try {
      const updated = (await toggleFavorite(uuid)) as DiagnosisCard;
      setCard(updated);
      logger.info('[DiagnosisDetailPage] Toggled favorite', {
        uuid,
        isFavorite: updated.is_favorite,
      });
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to toggle favorite:', err);
      alert('Failed to update favorite status. Please try again.');
    }
  };

  /**
   * Handle treatment status update
   */
  const handleStatusUpdate = async (newStatus: TreatmentStatus) => {
    if (!uuid) return;

    try {
      setIsUpdatingStatus(true);
      const updated = (await updateDiagnosisCard(uuid, {
        treatment_status: newStatus,
      })) as DiagnosisCard;
      setCard(updated);
      logger.info('[DiagnosisDetailPage] Updated status', { uuid, status: newStatus });
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to update status:', err);
      alert('Failed to update treatment status. Please try again.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  /**
   * Handle plant recovery toggle
   */
  const handleRecoveryToggle = async () => {
    if (!card || !uuid) return;

    try {
      const newRecoveryStatus = card.plant_recovered === null ? true : !card.plant_recovered;
      const updated = (await updateDiagnosisCard(uuid, {
        plant_recovered: newRecoveryStatus,
      })) as DiagnosisCard;
      setCard(updated);
      logger.info('[DiagnosisDetailPage] Updated recovery status', {
        uuid,
        recovered: newRecoveryStatus,
      });
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to update recovery status:', err);
      alert('Failed to update recovery status. Please try again.');
    }
  };

  /**
   * Handle notes save
   */
  const handleSaveNotes = async () => {
    if (!uuid) return;

    try {
      setIsSavingNotes(true);
      const updated = (await updateDiagnosisCard(uuid, {
        personal_notes: editedNotes,
      })) as DiagnosisCard;
      setCard(updated);
      setIsEditingNotes(false);
      logger.info('[DiagnosisDetailPage] Saved notes', { uuid });
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to save notes:', err);
      alert('Failed to save notes. Please try again.');
    } finally {
      setIsSavingNotes(false);
    }
  };

  /**
   * Handle card deletion
   */
  const handleDelete = async () => {
    if (!card || !uuid) return;

    if (
      !confirm(
        `Are you sure you want to delete this diagnosis for "${card.display_name}"? This cannot be undone.`
      )
    ) {
      return;
    }

    try {
      await deleteDiagnosisCard(uuid);
      logger.info('[DiagnosisDetailPage] Deleted card', { uuid });
      navigate('/diagnosis');
    } catch (err) {
      logger.error('[DiagnosisDetailPage] Failed to delete:', err);
      alert('Failed to delete diagnosis card. Please try again.');
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-surface py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
            <p className="mt-4 text-ink-2">Loading diagnosis details...</p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !card) {
    return (
      <div className="min-h-screen bg-surface py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-error/10 border border-error/30 rounded-lg p-6 text-center">
            <svg
              className="w-12 h-12 text-error mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="text-lg font-semibold text-error mb-2">Failed to Load Diagnosis</h3>
            <p className="text-error mb-4">{error || 'Diagnosis card not found'}</p>
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={loadCard}
                className="px-4 py-2 bg-error text-white rounded-md hover:bg-error/90 transition-colors"
              >
                Try Again
              </button>
              <Link
                to="/diagnosis"
                className="px-4 py-2 border border-line-2 rounded-md text-ink-2 hover:bg-surface transition-colors"
              >
                Back to List
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm">
          <ol className="flex items-center space-x-2 text-ink-2">
            <li>
              <Link to="/diagnosis" className="hover:text-primary">
                My Diagnoses
              </Link>
            </li>
            <li className="flex items-center">
              <svg className="w-4 h-4 mx-2" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-ink">{card.display_name}</span>
            </li>
          </ol>
        </nav>

        {/* Header */}
        <div className="bg-surface-2 rounded-lg shadow-sm border border-line p-6 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-ink mb-2">{card.display_name}</h1>
              {card.plant_scientific_name && card.plant_scientific_name !== card.display_name && (
                <p className="text-lg text-ink-3 italic mb-4">{card.plant_scientific_name}</p>
              )}

              {/* Disease Information */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-error/10 text-ink ring-1 ring-inset ring-error/30">
                  {card.disease_name}
                </span>
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ring-1 ring-inset ${getSeverityColor(card.severity_assessment)}`}
                >
                  {card.severity_display}
                </span>
                {card.disease_type_display && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-surface-3 text-ink-2">
                    {card.disease_type_display}
                  </span>
                )}
                <span className="text-sm text-ink-2">
                  {Math.round(card.confidence_score * 100)}% confidence
                </span>
              </div>

              {/* Metadata */}
              <div className="text-sm text-ink-2 space-y-1">
                <p>Saved on {formatDate(card.saved_at)}</p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-start gap-2">
              <button
                onClick={handleToggleFavorite}
                className="p-2 rounded-full hover:bg-surface-3 transition-colors"
                aria-label={card.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
              >
                <svg
                  className={`w-6 h-6 ${card.is_favorite ? 'text-tertiary fill-current' : 'text-ink-3'}`}
                  fill={card.is_favorite ? 'currentColor' : 'none'}
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
              <button
                onClick={handleDelete}
                className="p-2 rounded-full text-error hover:bg-error/10 transition-colors"
                aria-label="Delete diagnosis"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Treatment Status */}
        <div className="bg-surface-2 rounded-lg shadow-sm border border-line p-6 mb-6">
          <h2 className="text-xl font-semibold text-ink mb-4">Treatment Status</h2>

          <div className="space-y-4">
            {/* Current Status */}
            <div>
              <label className="block text-sm font-medium text-ink-2 mb-2">Current Status</label>
              <select
                value={card.treatment_status}
                onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                  handleStatusUpdate(e.target.value as TreatmentStatus)
                }
                disabled={isUpdatingStatus}
                className="w-full px-4 py-2 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary disabled:opacity-50"
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
              <label className="block text-sm font-medium text-ink-2 mb-2">Plant Recovery</label>
              <button
                onClick={handleRecoveryToggle}
                className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
                  card.plant_recovered === true
                    ? 'bg-primary/10 text-primary hover:bg-primary/20'
                    : card.plant_recovered === false
                      ? 'bg-surface-2 text-ink-2 hover:bg-surface-3'
                      : 'bg-surface-2 text-ink-2 hover:bg-surface-3'
                }`}
              >
                {card.plant_recovered === true ? (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Plant Recovered
                  </>
                ) : card.plant_recovered === false ? (
                  <>
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Still Treating
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    Mark Recovery Status
                  </>
                )}
              </button>
            </div>

            {/* Active Reminders Count */}
            {reminders.length > 0 && (
              <div className="pt-4 border-t border-line">
                <p className="text-sm text-ink-2">
                  {reminders.length} active {reminders.length === 1 ? 'reminder' : 'reminders'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Care Instructions */}
        <div className="bg-surface-2 rounded-lg shadow-sm border border-line p-6 mb-6">
          <h2 className="text-xl font-semibold text-ink mb-6">Care Instructions</h2>

          {card.care_instructions && card.care_instructions.length > 0 ? (
            <div className="prose prose-green max-w-none">
              {card.care_instructions.map((block, index) => (
                <StreamFieldBlockComponent key={index} block={block as DiagnosisBlock} />
              ))}
            </div>
          ) : (
            <p className="text-ink-3 italic">No care instructions available for this diagnosis.</p>
          )}
        </div>

        {/* Personal Notes */}
        <div className="bg-surface-2 rounded-lg shadow-sm border border-line p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-ink">Personal Notes</h2>
            {!isEditingNotes && (
              <button
                onClick={() => setIsEditingNotes(true)}
                className="text-sm text-primary hover:text-primary/80 font-medium"
              >
                Edit
              </button>
            )}
          </div>

          {isEditingNotes ? (
            <div>
              <textarea
                value={editedNotes}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setEditedNotes(e.target.value)}
                rows={6}
                placeholder="Add your observations, progress notes, or reminders..."
                className="w-full px-4 py-3 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary"
              />
              <div className="flex items-center gap-2 mt-4">
                <button
                  onClick={handleSaveNotes}
                  disabled={isSavingNotes}
                  className="px-4 py-2 bg-clay text-on-clay rounded-md hover:bg-clay/90 transition-colors disabled:opacity-50"
                >
                  {isSavingNotes ? 'Saving...' : 'Save Notes'}
                </button>
                <button
                  onClick={() => {
                    setIsEditingNotes(false);
                    setEditedNotes(card.personal_notes || '');
                  }}
                  className="px-4 py-2 border border-line-2 rounded-md text-ink-2 hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div>
              {card.personal_notes ? (
                <p className="text-ink-2 whitespace-pre-wrap">{card.personal_notes}</p>
              ) : (
                <p className="text-ink-3 italic">
                  No personal notes yet. Click "Edit" to add your observations.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
