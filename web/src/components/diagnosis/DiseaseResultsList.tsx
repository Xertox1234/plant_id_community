import type { PlantDiseaseResult } from '@/types/diagnosis';

interface Props {
  results: PlantDiseaseResult[];
}

/**
 * Renders disease diagnosis results. A `system_message` result (the honest "service
 * unavailable / ask the community" fallback) is rendered as a notice, not a disease card.
 */
export default function DiseaseResultsList({ results }: Props) {
  if (results.length === 0) {
    return (
      <p className="text-ink-2" role="status">
        No diagnosis was produced. Please try a clearer photo and a fuller symptom description.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((r) => {
        if (r.diagnosis_source === 'system_message') {
          return (
            <div
              key={r.id}
              role="status"
              className="bg-surface-3 border border-line rounded-lg p-4 text-ink-2"
            >
              {r.notes}
            </div>
          );
        }
        return (
          <div
            key={r.id}
            className={`bg-surface-2 border rounded-xl p-5 ${
              r.is_primary ? 'border-primary' : 'border-line'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-ink">
                {r.suggested_disease_name || r.display_name || 'Unknown condition'}
              </h3>
              <span className="text-sm font-medium text-ink-2">
                {r.confidence_percentage}% confidence
              </span>
            </div>
            {r.severity_assessment && (
              <p className="mt-1 text-sm text-ink-2">Severity: {r.severity_assessment}</p>
            )}
            {r.symptoms_identified && (
              <p className="mt-3 text-sm text-ink">
                <span className="font-medium">Symptoms: </span>
                {r.symptoms_identified}
              </p>
            )}
            {r.immediate_actions && (
              <p className="mt-2 text-sm text-ink">
                <span className="font-medium">Immediate actions: </span>
                {r.immediate_actions}
              </p>
            )}
            {r.recommended_treatments && (
              <p className="mt-2 text-sm text-ink">
                <span className="font-medium">Recommended treatments: </span>
                {r.recommended_treatments}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
