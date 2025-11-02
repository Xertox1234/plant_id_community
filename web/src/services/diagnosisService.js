/**
 * Diagnosis Card API Service
 *
 * Provides methods to interact with the plant diagnosis card API.
 * Handles authentication, error handling, and data transformation.
 */

import logger from '../utils/logger'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Get authentication headers with JWT token from cookies
 */
function getAuthHeaders() {
  const token = document.cookie
    .split('; ')
    .find(row => row.startsWith('access_token='))
    ?.split('=')[1]

  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  }
}

/**
 * Handle API response errors
 */
async function handleResponse(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: `Request failed with status ${response.status}`
    }))

    logger.error('[diagnosisService] API error:', {
      status: response.status,
      error
    })

    throw new Error(error.error || error.message || `Request failed with status ${response.status}`)
  }

  return response.json()
}

// =============================================================================
// Diagnosis Card API Methods
// =============================================================================

/**
 * Fetch user's diagnosis cards with optional filtering
 *
 * @param {Object} options - Query parameters
 * @param {string} options.treatment_status - Filter by status (not_started, in_progress, successful, failed, monitoring)
 * @param {boolean} options.is_favorite - Filter favorite cards only
 * @param {boolean} options.plant_recovered - Filter by recovery status
 * @param {string} options.disease_type - Filter by disease type (fungal, bacterial, viral, pest, nutrient, environmental)
 * @param {string} options.search - Search in plant names and disease names
 * @param {string} options.ordering - Sort order (e.g., -saved_at, disease_name)
 * @param {number} options.page - Page number for pagination
 * @returns {Promise<Object>} Paginated list of diagnosis cards
 */
export async function fetchDiagnosisCards(options = {}) {
  const params = new URLSearchParams()

  if (options.treatment_status) params.append('treatment_status', options.treatment_status)
  if (options.is_favorite !== undefined) params.append('is_favorite', options.is_favorite)
  if (options.plant_recovered !== undefined) params.append('plant_recovered', options.plant_recovered)
  if (options.disease_type) params.append('disease_type', options.disease_type)
  if (options.search) params.append('search', options.search)
  if (options.ordering) params.append('ordering', options.ordering)
  if (options.page) params.append('page', options.page)

  const queryString = params.toString()
  const url = `${API_URL}/api/plant-identification/diagnosis-cards/${queryString ? `?${queryString}` : ''}`

  logger.info('[diagnosisService] Fetching diagnosis cards', { options })

  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
    credentials: 'include'
  })

  return handleResponse(response)
}

/**
 * Fetch a single diagnosis card by UUID
 *
 * @param {string} uuid - Diagnosis card UUID
 * @returns {Promise<Object>} Diagnosis card detail with care instructions
 */
export async function fetchDiagnosisCard(uuid) {
  logger.info('[diagnosisService] Fetching diagnosis card', { uuid })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Create a new diagnosis card from a diagnosis result
 *
 * @param {Object} data - Diagnosis card data
 * @param {string} data.diagnosis_result - UUID of diagnosis result
 * @param {string} data.plant_scientific_name - Plant scientific name
 * @param {string} data.plant_common_name - Plant common name (optional)
 * @param {string} data.custom_nickname - Custom nickname (optional)
 * @param {string} data.disease_name - Disease name
 * @param {string} data.disease_type - Disease type
 * @param {string} data.severity_assessment - Severity (mild, moderate, severe, critical)
 * @param {number} data.confidence_score - Confidence score (0.0-1.0)
 * @param {Array} data.care_instructions - StreamField care instructions
 * @param {string} data.personal_notes - Personal notes (optional)
 * @param {string} data.treatment_status - Treatment status (optional, defaults to not_started)
 * @param {boolean} data.share_with_community - Share flag (optional)
 * @param {boolean} data.is_favorite - Favorite flag (optional)
 * @returns {Promise<Object>} Created diagnosis card
 */
export async function createDiagnosisCard(data) {
  logger.info('[diagnosisService] Creating diagnosis card', { data })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    }
  )

  return handleResponse(response)
}

/**
 * Update a diagnosis card
 *
 * @param {string} uuid - Diagnosis card UUID
 * @param {Object} data - Fields to update
 * @param {string} data.custom_nickname - Custom nickname
 * @param {Array} data.care_instructions - StreamField care instructions
 * @param {string} data.personal_notes - Personal notes
 * @param {string} data.treatment_status - Treatment status
 * @param {boolean} data.plant_recovered - Recovery status
 * @param {boolean} data.share_with_community - Share flag
 * @param {boolean} data.is_favorite - Favorite flag
 * @returns {Promise<Object>} Updated diagnosis card
 */
export async function updateDiagnosisCard(uuid, data) {
  logger.info('[diagnosisService] Updating diagnosis card', { uuid, data })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/`,
    {
      method: 'PATCH',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    }
  )

  return handleResponse(response)
}

/**
 * Delete a diagnosis card
 *
 * @param {string} uuid - Diagnosis card UUID
 * @returns {Promise<void>}
 */
export async function deleteDiagnosisCard(uuid) {
  logger.info('[diagnosisService] Deleting diagnosis card', { uuid })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: `Delete failed with status ${response.status}`
    }))
    throw new Error(error.error || error.message || 'Delete failed')
  }
}

/**
 * Fetch favorite diagnosis cards
 *
 * @returns {Promise<Object>} Paginated list of favorite cards
 */
export async function fetchFavoriteDiagnosisCards() {
  logger.info('[diagnosisService] Fetching favorite diagnosis cards')

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/favorites/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Fetch active treatment cards (in_progress status)
 *
 * @returns {Promise<Array>} List of active treatment cards
 */
export async function fetchActiveTreatments() {
  logger.info('[diagnosisService] Fetching active treatments')

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/active_treatments/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Fetch successful treatment cards (plant recovered)
 *
 * @returns {Promise<Array>} List of successful treatment cards
 */
export async function fetchSuccessfulTreatments() {
  logger.info('[diagnosisService] Fetching successful treatments')

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/successful_treatments/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Toggle favorite status of a diagnosis card
 *
 * @param {string} uuid - Diagnosis card UUID
 * @returns {Promise<Object>} Updated diagnosis card
 */
export async function toggleFavorite(uuid) {
  logger.info('[diagnosisService] Toggling favorite', { uuid })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-cards/${uuid}/toggle_favorite/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

// =============================================================================
// Diagnosis Reminder API Methods
// =============================================================================

/**
 * Fetch reminders with optional filtering
 *
 * @param {Object} options - Query parameters
 * @param {string} options.diagnosis_card - Filter by diagnosis card UUID
 * @param {boolean} options.is_active - Filter active reminders only
 * @param {boolean} options.sent - Filter by sent status
 * @param {string} options.reminder_type - Filter by type (check_progress, treatment_step, follow_up, reapply)
 * @returns {Promise<Object>} Paginated list of reminders
 */
export async function fetchReminders(options = {}) {
  const params = new URLSearchParams()

  if (options.diagnosis_card) params.append('diagnosis_card', options.diagnosis_card)
  if (options.is_active !== undefined) params.append('is_active', options.is_active)
  if (options.sent !== undefined) params.append('sent', options.sent)
  if (options.reminder_type) params.append('reminder_type', options.reminder_type)

  const queryString = params.toString()
  const url = `${API_URL}/api/plant-identification/diagnosis-reminders/${queryString ? `?${queryString}` : ''}`

  logger.info('[diagnosisService] Fetching reminders', { options })

  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
    credentials: 'include'
  })

  return handleResponse(response)
}

/**
 * Create a new reminder
 *
 * @param {Object} data - Reminder data
 * @param {string} data.diagnosis_card - Diagnosis card UUID
 * @param {string} data.reminder_type - Reminder type
 * @param {string} data.reminder_title - Title
 * @param {string} data.reminder_message - Message (optional)
 * @param {string} data.scheduled_date - ISO date string (future date)
 * @returns {Promise<Object>} Created reminder
 */
export async function createReminder(data) {
  logger.info('[diagnosisService] Creating reminder', { data })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(data)
    }
  )

  return handleResponse(response)
}

/**
 * Fetch upcoming reminders (next 30 days)
 *
 * @returns {Promise<Array>} List of upcoming reminders
 */
export async function fetchUpcomingReminders() {
  logger.info('[diagnosisService] Fetching upcoming reminders')

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/upcoming/`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Snooze a reminder
 *
 * @param {string} uuid - Reminder UUID
 * @param {number} hours - Hours to snooze (default 24)
 * @returns {Promise<Object>} Updated reminder
 */
export async function snoozeReminder(uuid, hours = 24) {
  logger.info('[diagnosisService] Snoozing reminder', { uuid, hours })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/snooze/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ hours })
    }
  )

  return handleResponse(response)
}

/**
 * Cancel a reminder
 *
 * @param {string} uuid - Reminder UUID
 * @returns {Promise<Object>} Updated reminder
 */
export async function cancelReminder(uuid) {
  logger.info('[diagnosisService] Cancelling reminder', { uuid })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/cancel/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Acknowledge a sent reminder
 *
 * @param {string} uuid - Reminder UUID
 * @returns {Promise<Object>} Updated reminder
 */
export async function acknowledgeReminder(uuid) {
  logger.info('[diagnosisService] Acknowledging reminder', { uuid })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/acknowledge/`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  return handleResponse(response)
}

/**
 * Delete a reminder
 *
 * @param {string} uuid - Reminder UUID
 * @returns {Promise<void>}
 */
export async function deleteReminder(uuid) {
  logger.info('[diagnosisService] Deleting reminder', { uuid })

  const response = await fetch(
    `${API_URL}/api/plant-identification/diagnosis-reminders/${uuid}/`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
      credentials: 'include'
    }
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: `Delete failed with status ${response.status}`
    }))
    throw new Error(error.error || error.message || 'Delete failed')
  }
}
