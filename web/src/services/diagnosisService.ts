/**
 * Diagnosis Card API Service
 *
 * Provides methods to interact with the plant diagnosis card API.
 * Handles authentication, error handling, and data transformation.
 */

import { logger } from '../utils/logger';
import type {
  DiagnosisCard,
  DiagnosisReminder,
  CreateDiagnosisCardInput,
  UpdateDiagnosisCardInput,
  FetchDiagnosisCardsOptions,
  CreateReminderInput,
  FetchRemindersOptions,
  PaginatedDiagnosisCardsResponse,
  PaginatedRemindersResponse,
} from '../types/diagnosis';
import type { ApiError } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Get authentication headers with JWT token from cookies
 */
function getAuthHeaders(): Record<string, string> {
  const token = document.cookie
    .split('; ')
    .find(row => row.startsWith('access_token='))
    ?.split('=')[1];

  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
}

/**
 * Handle API response errors
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: `Request failed with status ${response.status}`
    }));

    logger.error('[diagnosisService] API error:', {
      status: response.status,
      error
    });

    throw new Error(error.error || error.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Diagnosis Card API Methods
// =============================================================================

/**
 * Fetch user's diagnosis cards with optional filtering
 */
export async function fetchDiagnosisCards(options: FetchDiagnosisCardsOptions = {}): Promise<PaginatedDiagnosisCardsResponse> {
  const params = new URLSearchParams();

  // String parameters: use falsy check (empty string is falsy, which we want to skip)
  if (options.treatment_status) params.append('treatment_status', options.treatment_status);
  if (options.disease_type) params.append('disease_type', options.disease_type);
  if (options.search) params.append('search', options.search);
  if (options.ordering) params.append('ordering', options.ordering);

  // Boolean parameters: MUST use !== undefined (false is a valid value)
  if (options.is_favorite !== undefined) params.append('is_favorite', options.is_favorite.toString());
  if (options.plant_recovered !== undefined) params.append('plant_recovered', options.plant_recovered.toString());

  // Number parameters: use falsy check when 0 is not a valid value (pagination starts at 1)
  if (options.page) params.append('page', options.page.toString());

  const queryString = params.toString();
  const url = `${API_URL}/api/plant-identification/diagnosis-cards/${queryString ? `?${queryString}` : ''}`;

  logger.info('[diagnosisService] Fetching diagnosis cards', { options });

  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
    credentials: 'include'
  });

  return handleResponse<PaginatedDiagnosisCardsResponse>(response);
}

/**
 * Fetch a single diagnosis card by UUID
 */
export async function fetchDiagnosisCard(uuid: string): Promise<DiagnosisCard> {
  logger.info('[diagnosisService] Fetching diagnosis card', { uuid });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisCard>(response);
}

/**
 * Create a new diagnosis card from a diagnosis result
 */
export async function createDiagnosisCard(data: CreateDiagnosisCardInput): Promise<DiagnosisCard> {
  logger.info('[diagnosisService] Creating diagnosis card', { data });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    }
  );

  return handleResponse<DiagnosisCard>(response);
}

/**
 * Update a diagnosis card
 */
export async function updateDiagnosisCard(uuid: string, data: UpdateDiagnosisCardInput): Promise<DiagnosisCard> {
  logger.info('[diagnosisService] Updating diagnosis card', { uuid, data });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/`,
    {
      method: 'PATCH',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    }
  );

  return handleResponse<DiagnosisCard>(response);
}

/**
 * Delete a diagnosis card
 */
export async function deleteDiagnosisCard(uuid: string): Promise<void> {
  logger.info('[diagnosisService] Deleting diagnosis card', { uuid });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: `Delete failed with status ${response.status}`
    }));
    throw new Error(error.error || error.detail || 'Delete failed');
  }
}

/**
 * Fetch favorite diagnosis cards
 */
export async function fetchFavoriteDiagnosisCards(): Promise<PaginatedDiagnosisCardsResponse> {
  logger.info('[diagnosisService] Fetching favorite diagnosis cards');

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/favorites/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<PaginatedDiagnosisCardsResponse>(response);
}

/**
 * Fetch active treatment cards (in_progress status)
 */
export async function fetchActiveTreatments(): Promise<DiagnosisCard[]> {
  logger.info('[diagnosisService] Fetching active treatments');

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/active_treatments/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisCard[]>(response);
}

/**
 * Fetch successful treatment cards (plant recovered)
 */
export async function fetchSuccessfulTreatments(): Promise<DiagnosisCard[]> {
  logger.info('[diagnosisService] Fetching successful treatments');

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/successful_treatments/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisCard[]>(response);
}

/**
 * Toggle favorite status of a diagnosis card
 */
export async function toggleFavorite(uuid: string): Promise<DiagnosisCard> {
  logger.info('[diagnosisService] Toggling favorite', { uuid });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/toggle_favorite/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisCard>(response);
}

// =============================================================================
// Diagnosis Reminder API Methods
// =============================================================================

/**
 * Fetch reminders with optional filtering
 */
export async function fetchReminders(options: FetchRemindersOptions = {}): Promise<PaginatedRemindersResponse> {
  const params = new URLSearchParams();

  // String parameters: use falsy check (empty string is falsy, which we want to skip)
  if (options.diagnosis_card) params.append('diagnosis_card', options.diagnosis_card);
  if (options.reminder_type) params.append('reminder_type', options.reminder_type);

  // Boolean parameters: MUST use !== undefined (false is a valid value)
  if (options.is_active !== undefined) params.append('is_active', options.is_active.toString());
  if (options.sent !== undefined) params.append('sent', options.sent.toString());

  const queryString = params.toString();
  const url = `${API_URL}/api/plant-identification/diagnosis-reminders/${queryString ? `?${queryString}` : ''}`;

  logger.info('[diagnosisService] Fetching reminders', { options });

  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
    credentials: 'include'
  });

  return handleResponse<PaginatedRemindersResponse>(response);
}

/**
 * Create a new reminder
 */
export async function createReminder(data: CreateReminderInput): Promise<DiagnosisReminder> {
  logger.info('[diagnosisService] Creating reminder', { data });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    }
  );

  return handleResponse<DiagnosisReminder>(response);
}

/**
 * Fetch upcoming reminders (next 30 days)
 */
export async function fetchUpcomingReminders(): Promise<DiagnosisReminder[]> {
  logger.info('[diagnosisService] Fetching upcoming reminders');

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/upcoming/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisReminder[]>(response);
}

/**
 * Snooze a reminder
 */
export async function snoozeReminder(uuid: string, hours: number = 24): Promise<DiagnosisReminder> {
  logger.info('[diagnosisService] Snoozing reminder', { uuid, hours });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/snooze/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ hours })
    }
  );

  return handleResponse<DiagnosisReminder>(response);
}

/**
 * Cancel a reminder
 */
export async function cancelReminder(uuid: string): Promise<DiagnosisReminder> {
  logger.info('[diagnosisService] Cancelling reminder', { uuid });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/cancel/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisReminder>(response);
}

/**
 * Acknowledge a sent reminder
 */
export async function acknowledgeReminder(uuid: string): Promise<DiagnosisReminder> {
  logger.info('[diagnosisService] Acknowledging reminder', { uuid });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/acknowledge/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  return handleResponse<DiagnosisReminder>(response);
}

/**
 * Delete a reminder
 */
export async function deleteReminder(uuid: string): Promise<void> {
  logger.info('[diagnosisService] Deleting reminder', { uuid });

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  );

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: `Delete failed with status ${response.status}`
    }));
    throw new Error(error.error || error.detail || 'Delete failed');
  }
}
