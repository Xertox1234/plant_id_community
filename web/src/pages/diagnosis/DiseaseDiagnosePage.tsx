import { useState } from 'react';
import { Stethoscope } from 'lucide-react';
import FileUpload from '../../components/PlantIdentification/FileUpload';
import DiseaseResultsList from '../../components/diagnosis/DiseaseResultsList';
import { diseaseService } from '../../services/diseaseService';
import type { DiseaseDiagnosisResults as Results } from '../../types/diagnosis';

export default function DiseaseDiagnosePage() {
  const [file, setFile] = useState<File | null>(null);
  const [symptoms, setSymptoms] = useState('');
  const [condition, setCondition] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = !!file && symptoms.trim().length > 0 && !loading;

  const handleSubmit = async () => {
    if (!file || !symptoms.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const created = await diseaseService.submitDiagnosis({
        image: file,
        symptoms_description: symptoms.trim(),
        plant_condition: condition || undefined,
        location: location || undefined,
      });
      const res = await diseaseService.getDiagnosisResults(created.request_id);
      if (res.status === 'failed') {
        setError('Diagnosis unavailable — please try again.');
      } else {
        setResults(res);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Diagnosis unavailable — please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
          <Stethoscope className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-ink">Diagnose a sick plant</h1>
          <p className="text-ink-2 mt-1">Upload a photo and describe the symptoms.</p>
        </div>
      </div>

      <div className="bg-surface-2 rounded-2xl shadow-sm border border-line p-8 space-y-6">
        <FileUpload onFileSelect={setFile} />

        <div>
          <label htmlFor="symptoms" className="block font-medium text-ink mb-2">
            Symptoms <span className="text-error">*</span>
          </label>
          <textarea
            id="symptoms"
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-line bg-surface p-3 text-ink"
            placeholder="e.g. Yellow leaves with black spots, spreading from the bottom up"
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <input
            aria-label="Plant condition (optional)"
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
            className="rounded-lg border border-line bg-surface p-3 text-ink"
            placeholder="Plant condition (optional)"
          />
          <input
            aria-label="Location (optional)"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="rounded-lg border border-line bg-surface p-3 text-ink"
            placeholder="Location (optional)"
          />
        </div>

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="px-8 py-3 bg-clay text-on-clay rounded-lg font-medium hover:bg-clay/90 disabled:bg-surface-3 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Diagnosing…' : 'Diagnose'}
        </button>

        {error && (
          <div className="bg-error/10 border border-error/30 rounded-lg p-4" role="alert">
            <p className="text-sm text-error">{error}</p>
          </div>
        )}

        {results && (
          <div className="pt-4 border-t border-line">
            <h2 className="text-xl font-semibold text-ink mb-4">Diagnosis</h2>
            {results.status === 'needs_help' && (
              <p className="mb-4 text-sm text-ink-2" role="status">
                We couldn&apos;t confidently identify the issue. Consider posting in the community
                forum with your photo and symptoms.
              </p>
            )}
            <DiseaseResultsList results={results.results} />
          </div>
        )}
      </div>
    </div>
  );
}
