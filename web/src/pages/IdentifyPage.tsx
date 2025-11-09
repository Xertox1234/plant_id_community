import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import FileUpload from '../components/PlantIdentification/FileUpload'
import IdentificationResults from '../components/PlantIdentification/IdentificationResults'
import { plantIdService } from '../services/plantIdService'
import { useAuth } from '../contexts/AuthContext'
import { getPlantKey } from '../utils/plantUtils'
import type { IdentificationResult, PlantSuggestion } from '@/types'

interface InfoCardProps {
  title: string
  description: string
  step: string
}

/**
 * IdentifyPage Component
 *
 * Plant identification page with file upload and AI-powered results.
 * Page header and navigation now handled by RootLayout.
 */
export default function IdentifyPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [results, setResults] = useState<IdentificationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null) // Separate error state for save operations
  const [savedPlants, setSavedPlants] = useState(new Map<string, boolean>()) // Track which plants have been saved
  const [savingPlant, setSavingPlant] = useState<string | null>(null) // Track which plant is currently being saved

  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file)
    setResults(null)
    setError(null)
    setSaveError(null)
  }

  const handleIdentify = async () => {
    if (!selectedFile) {
      return
    }

    setLoading(true)
    setError(null)
    setSaveError(null)

    try {
      const data = await plantIdService.identifyPlant(selectedFile)

      // Check if the response indicates failure
      if (data.success === false || data.error) {
        setError(data.error || 'Identification failed')
        setResults(null)
      } else {
        setResults(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setResults(null)
    setError(null)
    setSaveError(null)
  }

  const handleSavePlant = async (suggestion: PlantSuggestion) => {
    // Check authentication first
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/identify' } })
      return
    }

    // Prevent duplicate saves
    const plantKey = getPlantKey(suggestion)
    if (savedPlants.has(plantKey)) {
      return // Already saved
    }

    setSavingPlant(plantKey)
    setSaveError(null)

    try {
      // Use the plantIdService to save to collection
      await plantIdService.saveToCollection({
        plant_name: suggestion.plant_name,
        scientific_name: suggestion.scientific_name,
        confidence: suggestion.probability,
        common_names: suggestion.common_names || [],
        description: suggestion.description,
        watering: suggestion.watering,
        propagation_methods: suggestion.propagation_methods,
        care_instructions: suggestion.care_instructions,
        source: suggestion.source || 'plant_id',
      })

      // Mark as saved (Map.set returns a new Map)
      setSavedPlants(prev => new Map(prev).set(plantKey, true))
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save plant to collection')
    } finally {
      setSavingPlant(null)
    }
  }

  return (
    <div className="bg-gradient-to-br from-green-50 to-emerald-50">
      {/* Page Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-500 rounded-xl flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                AI Plant Identification
              </h1>
              <p className="text-gray-600 mt-1">
                Upload a photo to identify your plant instantly
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          {/* Upload Section */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Upload Your Plant Photo
            </h2>
            <FileUpload onFileSelect={handleFileSelect} />
          </div>

          {/* Identify Button */}
          {selectedFile && !results && (
            <div className="flex justify-center">
              <button
                onClick={handleIdentify}
                disabled={loading}
                className="px-8 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
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

          {/* Results Section */}
          {(results || loading || error) && (
            <div className="mt-8 pt-8 border-t border-gray-200">
              <IdentificationResults
                results={results}
                loading={loading}
                error={error}
                onSavePlant={handleSavePlant}
                savedPlants={savedPlants}
                savingPlant={savingPlant}
              />

              {saveError && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4" role="alert">
                  <p className="text-sm text-red-800">{saveError}</p>
                </div>
              )}

              {results && (
                <div className="mt-6 flex justify-center">
                  <button
                    onClick={handleReset}
                    className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
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
  )
}

function InfoCard({ title, description, step }: InfoCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 border border-gray-200">
      <div className="w-8 h-8 bg-green-100 text-green-600 rounded-full flex items-center justify-center font-bold mb-3">
        {step}
      </div>
      <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600">{description}</p>
    </div>
  )
}
