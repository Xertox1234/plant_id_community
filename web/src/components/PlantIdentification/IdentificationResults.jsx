import { Loader2 } from 'lucide-react'

export default function IdentificationResults({ results, loading, error }) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-12 h-12 text-green-600 animate-spin mb-4" />
        <p className="text-lg font-medium text-gray-900">
          Analyzing your plant...
        </p>
        <p className="text-sm text-gray-600 mt-2">
          This may take a few seconds
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-red-900 mb-2">
          Identification Failed
        </h3>
        <p className="text-red-700">{error}</p>
      </div>
    )
  }

  if (!results) {
    return null
  }

  return (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h3 className="text-2xl font-bold text-gray-900 mb-4">
          Identification Results
        </h3>

        <div className="space-y-4">
          {results.suggestions?.map((suggestion, index) => (
            <div
              key={index}
              className={`p-4 rounded-lg border ${
                index === 0
                  ? 'border-green-200 bg-green-50'
                  : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <h4 className="text-lg font-semibold text-gray-900">
                    {suggestion.plant_name}
                  </h4>
                  {suggestion.scientific_name && (
                    <p className="text-sm italic text-gray-600">
                      {suggestion.scientific_name}
                    </p>
                  )}
                </div>
                <div className="ml-4">
                  <div className="px-3 py-1 bg-green-600 text-white rounded-full text-sm font-medium">
                    {Math.round(suggestion.probability * 100)}%
                  </div>
                </div>
              </div>

              {suggestion.description && (
                <p className="text-gray-700 mt-2">{suggestion.description}</p>
              )}

              {suggestion.similar_images && suggestion.similar_images.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Similar images:
                  </p>
                  <div className="grid grid-cols-4 gap-2">
                    {suggestion.similar_images.slice(0, 4).map((img, idx) => (
                      <img
                        key={idx}
                        src={img.url}
                        alt={`Similar ${idx + 1}`}
                        className="w-full h-20 object-cover rounded-lg"
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {results.disease_suggestions && results.disease_suggestions.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
          <h4 className="text-lg font-semibold text-amber-900 mb-3">
            Potential Health Issues
          </h4>
          <div className="space-y-3">
            {results.disease_suggestions.map((disease, index) => (
              <div key={index} className="bg-white p-4 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-medium text-gray-900">{disease.name}</h5>
                  <span className="text-sm text-amber-700">
                    {Math.round(disease.probability * 100)}% match
                  </span>
                </div>
                {disease.description && (
                  <p className="text-sm text-gray-600">{disease.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
