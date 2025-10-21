import { useState, useCallback } from 'react'
import { Upload, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'

export default function FileUpload({ onFileSelect, maxSize = 10 * 1024 * 1024 }) {
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)

  const validateFile = (file) => {
    // Check file type
    if (!file.type.startsWith('image/')) {
      setError('Please upload an image file')
      return false
    }

    // Check file size (default 10MB)
    if (file.size > maxSize) {
      setError(`File size must be less than ${maxSize / 1024 / 1024}MB`)
      return false
    }

    setError(null)
    return true
  }

  const handleFile = (file) => {
    if (validateFile(file)) {
      // Create preview
      const reader = new FileReader()
      reader.onload = (e) => {
        setPreview(e.target.result)
      }
      reader.readAsDataURL(file)

      // Pass file to parent
      onFileSelect(file)
    }
  }

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }, [])

  const handleChange = (e) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const clearPreview = () => {
    setPreview(null)
    setError(null)
    onFileSelect(null)
  }

  return (
    <div className="w-full">
      {!preview ? (
        <div
          className={`relative border-2 border-dashed rounded-xl p-12 transition-colors ${
            dragActive
              ? 'border-green-500 bg-green-50'
              : error
              ? 'border-red-300 bg-red-50'
              : 'border-gray-300 hover:border-green-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="file-upload"
            accept="image/*"
            onChange={handleChange}
            className="hidden"
          />

          <label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center cursor-pointer"
          >
            <div className="w-16 h-16 mb-4 bg-green-100 rounded-full flex items-center justify-center">
              <Upload className="w-8 h-8 text-green-600" />
            </div>

            <p className="text-lg font-medium text-gray-900 mb-2">
              Drop your plant photo here
            </p>
            <p className="text-sm text-gray-600 mb-4">
              or click to browse your files
            </p>
            <p className="text-xs text-gray-500">
              PNG, JPG, WebP up to 10MB
            </p>
          </label>

          {error && (
            <div className="mt-4 flex items-center justify-center gap-2 text-red-600">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="relative">
          <img
            src={preview}
            alt="Plant preview"
            className="w-full h-96 object-cover rounded-xl"
          />
          <button
            onClick={clearPreview}
            className="absolute top-4 right-4 p-2 bg-white rounded-full shadow-lg hover:bg-gray-100 transition-colors"
            aria-label="Remove image"
          >
            <X className="w-5 h-5 text-gray-700" />
          </button>
        </div>
      )}
    </div>
  )
}
