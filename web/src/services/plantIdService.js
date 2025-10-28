import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_VERSION = 'v1'

export const plantIdService = {
  /**
   * Identify a plant from an uploaded image
   * @param {File} imageFile - The plant image file
   * @returns {Promise} Plant identification results
   */
  identifyPlant: async (imageFile) => {
    const formData = new FormData()
    formData.append('image', imageFile)

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/${API_VERSION}/plant-identification/identify/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )
      return response.data
    } catch (error) {
      if (error.response?.data?.error) {
        throw new Error(error.response.data.error)
      }
      throw new Error('Failed to identify plant. Please try again.')
    }
  },

  /**
   * Get plant identification history
   * @returns {Promise} Array of past identifications
   */
  getHistory: async () => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/${API_VERSION}/plant-identification/history/`
      )
      return response.data
    } catch {
      throw new Error('Failed to load identification history')
    }
  },

  /**
   * Save identified plant to collection
   * @param {number} identificationId - The identification ID
   * @returns {Promise}
   */
  saveToCollection: async (identificationId) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/${API_VERSION}/plant-identification/save/`,
        { identification_id: identificationId }
      )
      return response.data
    } catch {
      throw new Error('Failed to save plant to collection')
    }
  },
}
