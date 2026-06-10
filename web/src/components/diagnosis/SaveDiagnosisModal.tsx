import { useState, FormEvent, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { createDiagnosisCard } from '../../services/diagnosisService';
import type {
  CreateDiagnosisCardInput,
  DiseaseType,
  SeverityAssessment,
} from '../../types/diagnosis';
import { logger } from '../../utils/logger';

interface DiseaseInfo {
  diagnosis_result_id?: string;
  disease_name: string;
  disease_type?: string;
  severity?: string;
  probability?: number;
  care_instructions?: unknown[];
  plant_name?: string;
}

interface IdentificationData {
  scientific_name?: string;
  plant_name?: string;
}

interface SaveDiagnosisModalProps {
  isOpen: boolean;
  onClose: () => void;
  diseaseInfo: DiseaseInfo | null;
  identificationData?: IdentificationData;
}

export default function SaveDiagnosisModal({
  isOpen,
  onClose,
  diseaseInfo,
  identificationData,
}: SaveDiagnosisModalProps) {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    custom_nickname: '',
    personal_notes: '',
  });
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Handle form submission
   */
  const handleSave = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();

    if (!diseaseInfo) {
      setError('No disease information available');
      return;
    }

    try {
      setIsSaving(true);
      setError(null);

      // Prepare diagnosis card data
      const cardData: CreateDiagnosisCardInput = {
        // diagnosis_result is optional - only include if we have an ID from backend
        ...(diseaseInfo.diagnosis_result_id && {
          diagnosis_result: diseaseInfo.diagnosis_result_id,
        }),
        plant_scientific_name:
          identificationData?.scientific_name || diseaseInfo.plant_name || 'Unknown',
        plant_common_name: identificationData?.plant_name || '',
        custom_nickname: formData.custom_nickname || '',
        disease_name: diseaseInfo.disease_name,
        // diseaseInfo carries these as loose strings from the diagnosis API;
        // narrow them to the create-input enums at this boundary.
        disease_type: (diseaseInfo.disease_type || 'environmental') as DiseaseType,
        severity_assessment: (diseaseInfo.severity || 'moderate') as SeverityAssessment,
        confidence_score: diseaseInfo.probability || 0.0,
        care_instructions: diseaseInfo.care_instructions || [],
        personal_notes: formData.personal_notes || '',
        treatment_status: 'not_started',
        share_with_community: false,
        is_favorite: false,
      };

      logger.info('[SaveDiagnosisModal] Creating diagnosis card', { cardData });

      const createdCard = await createDiagnosisCard(cardData);

      logger.info('[SaveDiagnosisModal] Card created successfully', { uuid: createdCard.uuid });

      // Navigate to the new diagnosis card
      navigate(`/diagnosis/${createdCard.uuid}`);
    } catch (err) {
      const error = err as Error;
      logger.error('[SaveDiagnosisModal] Failed to save diagnosis', { error });
      setError(error.message || 'Failed to save diagnosis card');
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 transition-opacity" onClick={onClose} />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-surface-2 rounded-lg shadow-xl max-w-md w-full p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-ink">Save as Diagnosis Card</h3>
            <button
              onClick={onClose}
              className="text-ink-3 hover:text-ink-2 transition-colors"
              aria-label="Close modal"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Disease Info Summary */}
          <div className="bg-warn/10 border border-warn/30 rounded-lg p-4 mb-6">
            <h4 className="font-semibold text-warn mb-2">
              {diseaseInfo?.disease_name || 'Unknown Disease'}
            </h4>
            <div className="text-sm text-warn space-y-1">
              <p>
                <span className="font-medium">Severity:</span> {diseaseInfo?.severity || 'Unknown'}
              </p>
              <p>
                <span className="font-medium">Confidence:</span>{' '}
                {diseaseInfo?.probability ? `${Math.round(diseaseInfo.probability * 100)}%` : 'N/A'}
              </p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSave} className="space-y-4">
            {/* Custom Nickname */}
            <div>
              <label htmlFor="nickname" className="block text-sm font-medium text-ink-2 mb-1">
                Custom Nickname (optional)
              </label>
              <input
                type="text"
                id="nickname"
                value={formData.custom_nickname}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setFormData({ ...formData, custom_nickname: e.target.value })
                }
                placeholder="e.g., Kitchen Aloe, Balcony Tomato"
                className="w-full px-3 py-2 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary"
              />
              <p className="text-xs text-ink-3 mt-1">Give this plant a memorable name</p>
            </div>

            {/* Personal Notes */}
            <div>
              <label htmlFor="notes" className="block text-sm font-medium text-ink-2 mb-1">
                Personal Notes (optional)
              </label>
              <textarea
                id="notes"
                value={formData.personal_notes}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
                  setFormData({ ...formData, personal_notes: e.target.value })
                }
                placeholder="Add any observations or notes about the plant's condition..."
                rows={4}
                className="w-full px-3 py-2 border border-line-2 rounded-md bg-surface-2 text-ink focus:ring-primary focus:border-primary"
              />
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-error/10 border border-error/30 rounded-md p-3">
                <p className="text-sm text-error">{error}</p>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={isSaving}
                className="flex-1 px-4 py-2 bg-clay text-on-clay rounded-md hover:bg-clay/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {isSaving ? 'Saving...' : 'Save & Track Treatment'}
              </button>
              <button
                type="button"
                onClick={onClose}
                disabled={isSaving}
                className="px-4 py-2 border border-line-2 rounded-md text-ink-2 hover:bg-surface transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
            </div>

            {/* Info Text */}
            <p className="text-xs text-ink-3 text-center">
              You'll be able to add care instructions and set reminders after saving
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
