import { Loader2, Check } from 'lucide-react';
import Card from '../ui/Card';
import { getPlantKey } from '../../utils/plantUtils';
import type { PlantIdentificationResult } from '@/types';

interface IdentificationResultsProps {
  results: PlantIdentificationResult | null;
  loading: boolean;
  error: string | null;
  onSavePlant?: (plant: PlantIdentificationResult) => void;
  savedPlants?: Map<string, boolean>;
  savingPlant?: string | null;
}

/** Static, non-interactive percentage readout — never a Chip (button semantics). */
function ConfidencePill({
  value,
  tone = 'text-ink-2',
  suffix,
}: {
  value: number;
  tone?: string;
  suffix?: string;
}) {
  return (
    <span
      className={`shrink-0 rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[13px] tabular-nums ${tone}`}
    >
      {Math.round(value * 100)}%{suffix && <span className="sr-only"> {suffix}</span>}
    </span>
  );
}

export default function IdentificationResults({
  results,
  loading,
  error,
  onSavePlant,
  savedPlants,
  savingPlant,
}: IdentificationResultsProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
        <p className="text-lg font-medium text-ink">Analyzing your plant...</p>
        <p className="text-sm text-ink-2 mt-2">This may take a few seconds</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-error/10 border border-error/30 rounded-md p-6">
        <h3 className="text-lg font-semibold text-error mb-2">Identification Failed</h3>
        <p className="text-error">{error}</p>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-ink mb-4">Identification Results</h3>

        <div className="space-y-4">
          {results.suggestions?.map((suggestion, index) => (
            <Card key={index} className={`p-5 ${index === 0 ? 'border-primary/40' : ''}`}>
              <div className="flex items-start justify-between mb-2 gap-3">
                <div className="flex-1">
                  <h4 className="text-lg font-semibold text-ink">{suggestion.plant_name}</h4>
                  {suggestion.scientific_name && (
                    <p className="text-sm italic text-ink-2">{suggestion.scientific_name}</p>
                  )}
                </div>
                <ConfidencePill
                  value={suggestion.probability}
                  tone={index === 0 ? 'text-primary' : 'text-ink-2'}
                />
              </div>

              {suggestion.description && (
                <p className="text-ink-2 mt-2">{suggestion.description}</p>
              )}

              {suggestion.similar_images && suggestion.similar_images.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-ink-2 mb-2">Similar images:</p>
                  <div className="grid grid-cols-4 gap-2">
                    {suggestion.similar_images.slice(0, 4).map((img, idx) => (
                      <img
                        key={idx}
                        src={img.url}
                        alt={`Similar ${idx + 1}`}
                        className="w-full h-20 object-cover rounded-md"
                      />
                    ))}
                  </div>
                </div>
              )}

              {onSavePlant &&
                (() => {
                  const plantKey = getPlantKey(suggestion);
                  const isSaved = savedPlants?.has(plantKey);
                  const isSaving = savingPlant === plantKey;

                  return (
                    <button
                      onClick={() => onSavePlant(suggestion)}
                      disabled={isSaved || isSaving}
                      aria-busy={isSaving}
                      aria-label={
                        isSaved
                          ? `${suggestion.plant_name} saved to collection`
                          : `Save ${suggestion.plant_name} to collection`
                      }
                      className={`mt-4 w-full px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 flex items-center justify-center gap-2 ${
                        isSaved
                          ? 'bg-surface-3 text-ink-2 cursor-not-allowed'
                          : isSaving
                            ? 'bg-clay/80 text-on-clay cursor-wait'
                            : 'bg-clay text-on-clay hover:bg-clay/90 focus:ring-primary'
                      }`}
                    >
                      {isSaving && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
                      {isSaved && <Check className="w-4 h-4" aria-hidden="true" />}
                      {isSaved
                        ? 'Saved to Collection'
                        : isSaving
                          ? 'Saving...'
                          : 'Save to My Collection'}
                    </button>
                  );
                })()}
            </Card>
          ))}
        </div>
      </div>

      {results.disease_suggestions && results.disease_suggestions.length > 0 && (
        <div className="bg-warn/10 border border-warn/30 rounded-md p-6">
          <h4 className="text-lg font-semibold text-warn mb-3">Potential Health Issues</h4>
          <div className="space-y-3">
            {results.disease_suggestions.map((disease, index) => (
              <div
                key={index}
                className="bg-surface-2 p-4 rounded-md flex items-start justify-between gap-3"
              >
                <div>
                  <h5 className="font-medium text-ink">{disease.name}</h5>
                  {disease.description && (
                    <p className="text-sm text-ink-2 mt-1">{disease.description}</p>
                  )}
                </div>
                <ConfidencePill value={disease.probability} tone="text-warn" suffix="match" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
