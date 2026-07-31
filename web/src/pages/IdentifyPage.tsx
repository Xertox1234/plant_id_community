import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Users } from 'lucide-react';
import FileUpload from '../components/PlantIdentification/FileUpload';
import IdentificationResults from '../components/PlantIdentification/IdentificationResults';
import { plantIdService } from '../services/plantIdService';
import { uploadPostImage } from '../services/forumService';
import { useAuth } from '../contexts/AuthContext';
import { getPlantKey } from '../utils/plantUtils';
import type { PlantIdentificationResult } from '@/types';

/**
 * Mirrors the backend's WAGTAILFORUM_TOPIC_IDENTIFICATION_MAX_CANDIDATES
 * default. Trimming here keeps the create from 400ing on a payload the user
 * never chose to send; the server is still the authority.
 */
const MAX_ATTACHED_CANDIDATES = 3;

interface InfoCardProps {
  title: string;
  description: string;
  step: string;
}

/**
 * IdentifyPage Component
 *
 * Plant identification page with file upload and AI-powered results.
 * Page header and navigation now handled by RootLayout.
 */
export default function IdentifyPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [results, setResults] = useState<PlantIdentificationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null); // Separate error state for save operations
  const [savedPlants, setSavedPlants] = useState(new Map<string, boolean>()); // Track which plants have been saved
  const [savingPlant, setSavingPlant] = useState<string | null>(null); // Track which plant is currently being saved
  // "Ask the community" handoff (audit M6) — uploading the photo is a network
  // round-trip, so it gets its own pending + error state.
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setResults(null);
    setError(null);
    setSaveError(null);
  };

  const handleIdentify = async () => {
    if (!selectedFile) {
      return;
    }

    setLoading(true);
    setError(null);
    setSaveError(null);

    try {
      const data = await plantIdService.identifyPlant(selectedFile);
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  /**
   * "Ask the community" (audit M6) — hand this identification to the forum
   * composer.
   *
   * The photo is uploaded HERE, not in the composer: it means only serializable
   * JSON travels through router state, and an upload failure surfaces on the
   * page where the user just pressed the button instead of at submit time.
   * `POST /forum/images/` requires auth, so the sign-in check runs first —
   * anonymous identification is allowed in dev (DEBUG), and without this the
   * button would 401.
   */
  const handleAskCommunity = async () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/identify' } });
      return;
    }
    const suggestions = results?.suggestions ?? [];
    // Confidence is 0–1 server-side; clamp rather than let a stray value fail
    // the create with a 400 the user can do nothing about.
    const candidates = suggestions
      .filter((s) => !!s.plant_name)
      .slice(0, MAX_ATTACHED_CANDIDATES)
      .map((s) => {
        const raw = s.probability ?? s.confidence ?? 0;
        return {
          name: s.plant_name,
          scientific_name: s.scientific_name ?? '',
          confidence: Number.isFinite(raw) ? Math.min(1, Math.max(0, raw)) : 0,
        };
      });
    if (candidates.length === 0) return;

    setAskError(null);
    setAsking(true);
    try {
      // The photo is optional on the attachment, so a missing file is not an
      // error — the card renders text-only.
      const uploaded = selectedFile ? await uploadPostImage(selectedFile) : null;
      navigate('/forum/new-thread', {
        state: {
          identification: {
            image_id: uploaded?.id ?? null,
            provider: suggestions[0]?.source ?? '',
            candidates,
          },
          identificationPreviewUrl: uploaded?.url,
        },
      });
    } catch (err) {
      setAskError(err instanceof Error ? err.message : 'Could not attach this identification');
    } finally {
      setAsking(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setResults(null);
    setError(null);
    setSaveError(null);
  };

  const handleSavePlant = async (suggestion: PlantIdentificationResult) => {
    // Check authentication first
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/identify' } });
      return;
    }

    // Prevent duplicate saves
    const plantKey = getPlantKey(suggestion);
    if (savedPlants.has(plantKey)) {
      return; // Already saved
    }

    setSavingPlant(plantKey);
    setSaveError(null);

    try {
      // Use the plantIdService to save to collection
      await plantIdService.saveToCollection({
        plant_name: suggestion.plant_name,
        confidence: suggestion.confidence,
        common_names: suggestion.common_names,
        description: suggestion.description,
        watering: suggestion.watering,
        propagation_methods: suggestion.propagation_methods,
        care_instructions: suggestion.care_instructions,
        source: suggestion.source,
      });

      // Mark as saved (Map.set returns a new Map)
      setSavedPlants((prev) => new Map(prev).set(plantKey, true));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save plant to collection');
    } finally {
      setSavingPlant(null);
    }
  };

  return (
    <div className="bg-gradient-to-br from-primary/5 to-secondary/5">
      {/* Page Header */}
      <div className="bg-surface-2 border-b border-line">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-ink">AI Plant Identification</h1>
              <p className="text-ink-2 mt-1">Upload a photo to identify your plant instantly</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-surface-2 rounded-2xl shadow-sm border border-line p-8">
          {/* Upload Section */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-ink mb-4">Upload Your Plant Photo</h2>
            <FileUpload onFileSelect={handleFileSelect} />
          </div>

          {/* Identify Button */}
          {selectedFile && !results && (
            <div className="flex justify-center">
              <button
                onClick={handleIdentify}
                disabled={loading}
                className="px-8 py-3 bg-clay text-on-clay rounded-lg font-medium hover:bg-clay/90 disabled:bg-surface-3 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Identify Plant
                  </>
                )}
              </button>
            </div>
          )}

          {/* Save-failure live region, OUTSIDE the results block on purpose
              (audit M26). Nesting it in `{(results || loading || error) && …}`
              made it a persistent region with a non-persistent ancestor: pick a
              new file mid-save and that block unmounts, so the pending save's
              rejection had nowhere to land — the error was dropped silently for
              everyone, sighted or not. Unconditional here, so the node
              pre-exists its content in every path. */}
          <div
            aria-live="assertive"
            aria-atomic="true"
            className={
              saveError || askError
                ? 'mt-4 bg-error/10 border border-error/30 rounded-lg p-4'
                : 'sr-only'
            }
          >
            {/* Both write-path failures land in this ONE persistent region
                (the M26 lesson above). Only one of the two actions can be in
                flight at a time, so they cannot clobber each other. */}
            <p className="text-sm text-error">{saveError || askError}</p>
          </div>

          {/* Results Section */}
          {(results || loading || error) && (
            <div className="mt-8 pt-8 border-t border-line">
              <IdentificationResults
                results={results}
                loading={loading}
                error={error}
                onSavePlant={handleSavePlant}
                savedPlants={savedPlants}
                savingPlant={savingPlant}
              />

              {results && (
                <div className="mt-6 flex flex-wrap justify-center gap-3">
                  {/* Not sure? Take it to the forum with the result attached
                      (audit M6) — the app's flagship loop. */}
                  {!!results.suggestions?.length && (
                    <button
                      onClick={handleAskCommunity}
                      disabled={asking}
                      className="px-6 py-2 bg-clay text-on-clay rounded-lg font-medium hover:bg-clay/90 disabled:bg-surface-3 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                    >
                      <Users className="w-4 h-4" aria-hidden="true" />
                      {asking ? 'Preparing…' : 'Ask the community'}
                    </button>
                  )}
                  <button
                    onClick={handleReset}
                    className="px-6 py-2 bg-surface-3 text-ink-2 rounded-lg font-medium hover:bg-surface-3/80 transition-colors"
                  >
                    Identify Another Plant
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Info Cards */}
        <div className="mt-8 grid md:grid-cols-3 gap-6">
          <InfoCard
            title="Upload Photo"
            description="Take or upload a clear photo of your plant"
            step="1"
          />
          <InfoCard
            title="AI Analysis"
            description="Our AI identifies your plant using advanced recognition"
            step="2"
          />
          <InfoCard
            title="Get Results"
            description="Receive detailed information about your plant"
            step="3"
          />
        </div>
      </div>
    </div>
  );
}

function InfoCard({ title, description, step }: InfoCardProps) {
  return (
    <div className="bg-surface-2 rounded-xl p-6 border border-line">
      <div className="w-8 h-8 bg-primary/10 text-primary rounded-full flex items-center justify-center font-bold mb-3">
        {step}
      </div>
      <h3 className="font-semibold text-ink mb-2">{title}</h3>
      <p className="text-sm text-ink-2">{description}</p>
    </div>
  );
}
