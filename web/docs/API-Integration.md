# API Integration Guide

Complete guide to backend API integration in the Plant ID Community web frontend.

## Overview

The web frontend communicates with a Django REST Framework backend running on port 8000. All API communication is handled through a centralized service layer using Axios.

## Architecture

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   React      │         │    Vite      │         │   Django     │
│  Component   │ ──────> │    Proxy     │ ──────> │   Backend    │
│              │         │  (Dev Only)  │         │  (Port 8000) │
└──────────────┘         └──────────────┘         └──────────────┘
       │                                                  │
       │                                                  │
       └──────> plantIdService.js <──────────────────────┘
                 (Axios wrapper)
```

## Service Layer

### File Structure

```
src/services/
└── plantIdService.js    # Backend API client
```

### Base Configuration

```javascript
// src/services/plantIdService.js
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Create axios instance with defaults
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,  // 30 second timeout
})
```

**Environment Configuration:**
```bash
# .env
VITE_API_URL=http://localhost:8000
```

## Development vs Production

### Development (Vite Proxy)

**Configuration** (`vite.config.js`):
```javascript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

**Benefits:**
- No CORS issues in development
- Frontend can use relative URLs: `/api/...`
- Backend runs on separate port (8000)
- Automatic request forwarding

**Request Flow:**
```
Browser: http://localhost:5173/api/identify/
    ↓
Vite Proxy forwards to:
    ↓
Backend: http://localhost:8000/api/identify/
```

### Production

**Configuration:**
```bash
# Set in hosting platform (Vercel, Netlify, etc.)
VITE_API_URL=https://api.plantcommunity.com
```

**Request Flow:**
```
Browser: https://plantcommunity.com
    ↓
Direct API calls to:
    ↓
Backend: https://api.plantcommunity.com/api/identify/
```

**CORS Requirements:**
```python
# backend/settings.py
CORS_ALLOWED_ORIGINS = [
    "https://plantcommunity.com",
    "https://www.plantcommunity.com",
]
```

## API Endpoints

### Health Check

**Endpoint:** `GET /api/plant-identification/identify/health/`

**Purpose:** Verify backend is running and APIs are available

**Request:**
```javascript
const response = await axios.get(
  `${API_BASE_URL}/api/plant-identification/identify/health/`
)
```

**Response:**
```json
{
  "status": "healthy",
  "plant_id_available": true,
  "plantnet_available": true,
  "redis_available": true,
  "timestamp": "2025-10-22T12:00:00Z"
}
```

**Usage in Frontend:**
```javascript
// Check backend health on app load
useEffect(() => {
  const checkHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/plant-identification/identify/health/`)
      console.log('Backend healthy:', response.data)
    } catch (error) {
      console.error('Backend not available:', error)
    }
  }
  checkHealth()
}, [])
```

### Plant Identification

**Endpoint:** `POST /api/plant-identification/identify/`

**Purpose:** Identify a plant from an uploaded image

**Request:**
```javascript
import { plantIdService } from '../services/plantIdService'

const result = await plantIdService.identifyPlant(imageFile)
```

**Implementation:**
```javascript
// src/services/plantIdService.js
export const plantIdService = {
  /**
   * Identify a plant from an image file
   * @param {File} imageFile - Image file to identify
   * @returns {Promise<Object>} Identification results
   */
  identifyPlant: async (imageFile) => {
    try {
      const formData = new FormData()
      formData.append('image', imageFile)

      const response = await axios.post(
        `${API_BASE_URL}/api/plant-identification/identify/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )

      return response.data
    } catch (error) {
      throw new Error(
        error.response?.data?.error ||
        'Failed to identify plant. Please try again.'
      )
    }
  }
}
```

**Request Details:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: FormData with image file
- Timeout: 30 seconds (API processing time)

**Response:**
```json
{
  "success": true,
  "plant_name": "Monstera Deliciosa",
  "scientific_name": "Monstera deliciosa",
  "confidence": 0.95,
  "suggestions": [
    {
      "plant_name": "Monstera Deliciosa",
      "scientific_name": "Monstera deliciosa",
      "probability": 0.95,
      "common_names": ["Swiss Cheese Plant", "Split-leaf Philodendron"],
      "description": "Tropical plant with distinctive split leaves...",
      "watering": "moderate",
      "source": "plant_id",
      "rank": 1,
      "similar_images": [
        "https://plant.id/media/imgs/...",
        "https://plant.id/media/imgs/..."
      ]
    },
    {
      "plant_name": "Pothos",
      "scientific_name": "Epipremnum aureum",
      "probability": 0.85,
      "common_names": ["Devil's Ivy"],
      "source": "plantnet",
      "rank": 2
    }
  ],
  "care_instructions": {
    "watering": "Moderate watering recommended",
    "light": "Bright indirect light",
    "temperature": "Room temperature (18-24°C)",
    "humidity": "Average humidity"
  },
  "disease_detection": {
    "is_healthy": true,
    "is_plant": true,
    "disease_name": null,
    "probability": null
  },
  "timing": {
    "total": 2.45
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "No plant found in image. Please upload a clearer photo.",
  "details": "Confidence too low"
}
```

## Usage Patterns

### Basic Usage in Component

```javascript
import { useState } from 'react'
import { plantIdService } from '../services/plantIdService'

function IdentifyPage() {
  const [file, setFile] = useState(null)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleIdentify = async () => {
    if (!file) return

    try {
      setLoading(true)
      setError(null)

      const data = await plantIdService.identifyPlant(file)
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <input
        type="file"
        accept="image/*"
        onChange={(e) => setFile(e.target.files[0])}
      />
      <button
        onClick={handleIdentify}
        disabled={!file || loading}
      >
        {loading ? 'Identifying...' : 'Identify Plant'}
      </button>

      {error && <div className="error">{error}</div>}
      {results && <ResultsDisplay results={results} />}
    </div>
  )
}
```

### With Loading States

```javascript
const handleIdentify = async () => {
  try {
    setLoading(true)
    setError(null)
    setResults(null)  // Clear previous results

    const data = await plantIdService.identifyPlant(file)

    // Successful identification
    setResults(data)
  } catch (err) {
    // Handle different error types
    if (err.response?.status === 413) {
      setError('Image file too large. Please compress the image.')
    } else if (err.response?.status === 429) {
      setError('Rate limit exceeded. Please try again later.')
    } else {
      setError(err.message || 'An unexpected error occurred')
    }
  } finally {
    setLoading(false)
  }
}
```

### With Progress Indication

```javascript
const handleIdentify = async () => {
  try {
    setLoading(true)
    setProgress('Uploading image...')

    const data = await plantIdService.identifyPlant(file)

    setProgress('Processing results...')
    // Artificial delay to show progress
    await new Promise(resolve => setTimeout(resolve, 500))

    setResults(data)
  } catch (err) {
    setError(err.message)
  } finally {
    setLoading(false)
    setProgress(null)
  }
}
```

## Error Handling

### Error Types

1. **Network Errors**
   ```javascript
   // Network connection failed
   {
     message: "Network Error",
     code: "ERR_NETWORK"
   }
   ```

2. **Timeout Errors**
   ```javascript
   // Request took longer than 30s
   {
     message: "timeout of 30000ms exceeded",
     code: "ECONNABORTED"
   }
   ```

3. **HTTP Errors**
   ```javascript
   // Backend returned error status
   {
     response: {
       status: 400,
       data: {
         error: "Invalid image format"
       }
     }
   }
   ```

### Error Extraction Pattern

```javascript
const getErrorMessage = (error) => {
  // Backend error message
  if (error.response?.data?.error) {
    return error.response.data.error
  }

  // Network error
  if (error.code === 'ERR_NETWORK') {
    return 'Unable to connect to server. Please check your internet connection.'
  }

  // Timeout error
  if (error.code === 'ECONNABORTED') {
    return 'Request timed out. Please try again with a smaller image.'
  }

  // HTTP status errors
  if (error.response?.status) {
    const statusMessages = {
      400: 'Invalid request. Please check your input.',
      413: 'Image file too large. Maximum size is 10MB.',
      429: 'Too many requests. Please wait a moment and try again.',
      500: 'Server error. Please try again later.',
    }
    return statusMessages[error.response.status] || 'An error occurred'
  }

  // Fallback
  return error.message || 'An unexpected error occurred'
}

// Usage
try {
  const result = await plantIdService.identifyPlant(file)
  setResults(result)
} catch (error) {
  const message = getErrorMessage(error)
  setError(message)
}
```

## Request Optimization

### Image Compression Before Upload

```javascript
import { compressImage, shouldCompressImage } from '../utils/imageCompression'

const handleIdentify = async () => {
  let fileToUpload = selectedFile

  // Compress large images
  if (shouldCompressImage(selectedFile)) {
    try {
      setProgress('Compressing image...')
      fileToUpload = await compressImage(selectedFile)
      console.log(`Compressed: ${selectedFile.size} → ${fileToUpload.size} bytes`)
    } catch (compressionError) {
      console.error('Compression failed:', compressionError)
      // Continue with original file
    }
  }

  setProgress('Uploading...')
  const result = await plantIdService.identifyPlant(fileToUpload)
  setResults(result)
}
```

**Benefits:**
- 85% size reduction (10MB → 800KB)
- 85% faster uploads
- Reduced backend processing time
- Lower bandwidth costs

### Request Cancellation

```javascript
import { useEffect, useRef } from 'react'

function IdentifyPage() {
  const abortControllerRef = useRef(null)

  const handleIdentify = async () => {
    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController()

    try {
      const formData = new FormData()
      formData.append('image', file)

      const response = await axios.post(
        `${API_BASE_URL}/api/plant-identification/identify/`,
        formData,
        {
          signal: abortControllerRef.current.signal
        }
      )

      setResults(response.data)
    } catch (error) {
      if (error.name === 'CanceledError') {
        console.log('Request cancelled')
        return
      }
      setError(getErrorMessage(error))
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  return (/* ... */)
}
```

## Future API Endpoints

### Planned Endpoints

1. **Get Identification History**
   ```javascript
   // GET /api/plant-identification/history/
   getHistory: async (userId, limit = 10) => {
     const response = await axios.get(
       `${API_BASE_URL}/api/plant-identification/history/`,
       { params: { user: userId, limit } }
     )
     return response.data
   }
   ```

2. **Save to Collection**
   ```javascript
   // POST /api/plant-identification/collection/
   saveToCollection: async (identificationId, notes = '') => {
     const response = await axios.post(
       `${API_BASE_URL}/api/plant-identification/collection/`,
       { identification_id: identificationId, notes }
     )
     return response.data
   }
   ```

3. **User Authentication**
   ```javascript
   // POST /api/auth/login/
   login: async (email, password) => {
     const response = await axios.post(
       `${API_BASE_URL}/api/auth/login/`,
       { email, password }
     )
     return response.data  // { token, user }
   }
   ```

## Testing API Integration

### Manual Testing

```javascript
// Test health endpoint
curl http://localhost:8000/api/plant-identification/identify/health/

// Test identify endpoint
curl -X POST \
  http://localhost:8000/api/plant-identification/identify/ \
  -F "image=@path/to/plant.jpg"
```

### Browser DevTools

1. **Network Tab**
   - Filter by "XHR" to see API calls
   - Check request headers, payload, response
   - Verify status codes (200, 400, 500)

2. **Console Tab**
   - Check for error logs
   - Verify API responses

## Best Practices

1. **Centralize API Logic**
   - All API calls in `services/`
   - No direct axios calls in components

2. **Error Handling**
   - Always extract error messages
   - Provide user-friendly messages
   - Log errors for debugging

3. **Loading States**
   - Show spinners during API calls
   - Disable buttons to prevent double-submit
   - Provide progress feedback

4. **Environment Variables**
   - Use `VITE_` prefix for client-side vars
   - Never commit `.env` files
   - Document required variables in `.env.example`

5. **Request Optimization**
   - Compress images before upload
   - Cancel requests on component unmount
   - Implement request debouncing for search

6. **Security**
   - Never store API keys in frontend
   - Use HTTPS in production
   - Validate file types and sizes

## Summary

The API integration follows these principles:

- **Centralized service layer** for maintainability
- **Comprehensive error handling** for reliability
- **Image optimization** for performance
- **Environment-based configuration** for flexibility
- **Clean separation** between UI and API logic

For implementation details, see:
- [Architecture.md](./Architecture.md) - Overall system design
- [Performance.md](./Performance.md) - Image compression details
- [Components.md](./Components.md) - Component usage
