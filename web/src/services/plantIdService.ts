/**
 * Plant Identification Service
 *
 * Handles plant identification, history, and saving to user collections.
 * Uses cookie-based JWT authentication with CSRF protection.
 */

import type {
  PlantIdentificationResult,
  Collection,
  UserPlant,
  IdentificationHistoryItem,
  SavePlantInput,
} from '../types/plantId';
import type { ApiError } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_VERSION = 'v1';

/**
 * Get CSRF token from Django cookies
 * Django sets csrftoken cookie that must be sent as X-CSRFToken header
 */
function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : null;
}

/**
 * Fetch CSRF token from Django backend
 * This endpoint sets the csrftoken cookie
 */
async function fetchCsrfToken(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/${API_VERSION}/users/csrf/`, {
      credentials: 'include',
    });
  } catch (error) {
    console.error('Failed to fetch CSRF token:', error);
  }
}

/**
 * Ensure CSRF token exists before making authenticated requests
 */
async function ensureCsrfToken(): Promise<void> {
  if (!getCsrfToken()) {
    await fetchCsrfToken();
  }
}

/**
 * Identify a plant from an uploaded image
 */
async function identifyPlant(imageFile: File): Promise<PlantIdentificationResult> {
  // Ensure CSRF token is available
  await ensureCsrfToken();

  const formData = new FormData();
  formData.append('image', imageFile);

  // Get CSRF token for Django CSRF protection
  const csrfToken = getCsrfToken();

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/${API_VERSION}/plant-identification/identify/`,
      {
        method: 'POST',
        credentials: 'include', // Send HttpOnly cookies for authentication
        headers: {
          // CRITICAL: Include CSRF token for Django CSRF middleware
          ...(csrfToken && { 'X-CSRFToken': csrfToken }),
        },
        body: formData, // FormData sets Content-Type automatically
      }
    );

    if (!response.ok) {
      const errorData: ApiError = await response.json();
      throw new Error(errorData.error || 'Failed to identify plant. Please try again.');
    }

    return response.json();
  } catch (error) {
    if (error instanceof Error && error.message) {
      throw error;
    }
    throw new Error('Failed to identify plant. Please try again.');
  }
}

/**
 * Get plant identification history
 */
async function getHistory(): Promise<IdentificationHistoryItem[]> {
  await ensureCsrfToken();
  const csrfToken = getCsrfToken();

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/${API_VERSION}/plant-identification/history/`,
      {
        credentials: 'include', // Send HttpOnly cookies
        headers: {
          ...(csrfToken && { 'X-CSRFToken': csrfToken }),
        },
      }
    );

    if (!response.ok) {
      throw new Error('Failed to load identification history');
    }

    return response.json();
  } catch {
    throw new Error('Failed to load identification history');
  }
}

/**
 * Save identified plant to user's collection
 */
async function saveToCollection(plantData: SavePlantInput): Promise<UserPlant> {
  await ensureCsrfToken();
  const csrfToken = getCsrfToken();

  try {
    // First, get user's collections to find the default one
    const collectionsResponse = await fetch(
      `${API_BASE_URL}/api/${API_VERSION}/users/collections/`,
      {
        credentials: 'include', // Send HttpOnly cookies
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken && { 'X-CSRFToken': csrfToken }),
        },
      }
    );

    if (!collectionsResponse.ok) {
      if (collectionsResponse.status === 401) {
        throw new Error('Authentication required to save plants');
      }
      throw new Error('Failed to fetch collections');
    }

    const collections: Collection[] = await collectionsResponse.json();

    if (!collections || collections.length === 0) {
      throw new Error('No collection found. Please create a collection first.');
    }

    // Use first collection (default "My Plants")
    const defaultCollection = collections[0];

    // Create UserPlant with the correct format
    const response = await fetch(
      `${API_BASE_URL}/api/${API_VERSION}/plant-identification/plants/`,
      {
        method: 'POST',
        credentials: 'include', // Send HttpOnly cookies
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken && { 'X-CSRFToken': csrfToken }),
        },
        body: JSON.stringify({
          collection: defaultCollection.id,
          nickname: plantData.plant_name,
          notes: plantData.description || '',
          care_instructions_json: {
            confidence: plantData.confidence,
            common_names: plantData.common_names || [],
            watering: plantData.watering || plantData.care_instructions?.watering || null,
            propagation: plantData.propagation_methods || plantData.care_instructions?.propagation || null,
            source: plantData.source,
          },
        }),
      }
    );

    if (!response.ok) {
      const errorData: ApiError = await response.json();
      throw new Error(errorData.error || 'Failed to save plant');
    }

    return response.json();
  } catch (error) {
    if (error instanceof Error && error.message) {
      throw error;
    }
    throw new Error('Failed to save plant to collection');
  }
}

export const plantIdService = {
  identifyPlant,
  getHistory,
  saveToCollection,
};
