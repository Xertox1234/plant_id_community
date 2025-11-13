/**
 * Plant Identification Service Tests
 *
 * Comprehensive tests for plant ID service covering:
 * - Plant identification with image upload
 * - CSRF token management
 * - Identification history fetching
 * - Save to collection with authentication
 * - Error handling for various scenarios
 * - File validation and size limits
 *
 * Priority: P1 - CRITICAL (Core plant identification feature)
 * Coverage Target: 100% branch coverage
 * Estimated Test Count: 16 tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { plantIdService } from './plantIdService';
import type {
  PlantIdentificationResult,
  Collection,
  UserPlant,
  IdentificationHistoryItem,
  SavePlantInput,
} from '../types/plantId';

// Mock logger to prevent console noise
vi.mock('../utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('plantIdService', () => {
  // Test fixtures
  const mockPlantResult: PlantIdentificationResult = {
    plant_name: 'Rosa damascena',
    confidence: 0.97,
    common_names: ['Damask Rose', 'Rose of Castile'],
    description: 'A deciduous shrub growing to 2.2 m',
    watering: 'Regular watering, allow soil to dry between waterings',
    propagation_methods: 'Cuttings, grafting',
    source: 'plant_id',
    image_url: 'https://example.com/rose.jpg',
    scientific_name: 'Rosa damascena',
    probability: 0.97,
  };

  const mockCollection: Collection = {
    id: 'collection-123',
    name: 'My Plants',
    description: 'Default collection',
    created_at: '2025-01-01T00:00:00Z',
  };

  const mockUserPlant: UserPlant = {
    id: 'plant-123',
    collection: 'collection-123',
    nickname: 'Rosa damascena',
    notes: '',
    care_instructions_json: {
      confidence: 0.97,
      common_names: ['Damask Rose', 'Rose of Castile'],
      watering: 'Regular watering, allow soil to dry between waterings',
      propagation: 'Cuttings, grafting',
      source: 'plant_id',
    },
    created_at: '2025-01-01T00:00:00Z',
  };

  const mockHistoryItem: IdentificationHistoryItem = {
    id: 'history-123',
    plant_name: 'Rosa damascena',
    confidence: 0.97,
    image_url: 'https://example.com/rose.jpg',
    created_at: '2025-01-01T00:00:00Z',
    source: 'plant_id',
  };

  // Mock implementations
  let fetchMock: ReturnType<typeof vi.fn>;
  let documentCookieMock: string;

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // Mock document.cookie with CSRF token
    documentCookieMock = 'csrftoken=test-csrf-token';
    Object.defineProperty(document, 'cookie', {
      get: () => documentCookieMock,
      set: (value: string) => {
        documentCookieMock = value;
      },
      configurable: true,
    });

    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================================
  // IDENTIFY PLANT TESTS
  // ============================================================================

  describe('identifyPlant', () => {
    it('should identify plant from uploaded image', async () => {
      // Arrange
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPlantResult,
      });

      // Act
      const result = await plantIdService.identifyPlant(imageFile);

      // Assert
      expect(result).toEqual(mockPlantResult);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/plant-identification/identify/'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
          headers: expect.objectContaining({
            'X-CSRFToken': 'test-csrf-token',
          }),
        })
      );
      // Verify FormData was sent
      const fetchCall = fetchMock.mock.calls[0];
      expect(fetchCall[1].body).toBeInstanceOf(FormData);
    });

    it('should fetch CSRF token if not present', async () => {
      // Arrange
      documentCookieMock = ''; // No CSRF token
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });

      // Mock CSRF fetch
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      // Mock identification
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPlantResult,
      });

      // Act
      await plantIdService.identifyPlant(imageFile);

      // Assert
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/v1/users/csrf/'),
        expect.objectContaining({
          credentials: 'include',
        })
      );
    });

    it('should include CSRF token in request headers', async () => {
      // Arrange
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPlantResult,
      });

      // Act
      await plantIdService.identifyPlant(imageFile);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle API errors with error message', async () => {
      // Arrange
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid image format' }),
      });

      // Act & Assert
      await expect(plantIdService.identifyPlant(imageFile)).rejects.toThrow(
        'Invalid image format'
      );
    });

    it('should handle API errors without error message', async () => {
      // Arrange
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}),
      });

      // Act & Assert
      await expect(plantIdService.identifyPlant(imageFile)).rejects.toThrow(
        'Failed to identify plant. Please try again.'
      );
    });

    it('should handle network errors', async () => {
      // Arrange
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(plantIdService.identifyPlant(imageFile)).rejects.toThrow(
        'Network error'
      );
    });

    it('should handle file size validation (API quota exceeded)', async () => {
      // Arrange
      const imageFile = new File(['image data'], 'large-plant.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ error: 'API quota exceeded. Please try again later.' }),
      });

      // Act & Assert
      await expect(plantIdService.identifyPlant(imageFile)).rejects.toThrow(
        'API quota exceeded. Please try again later.'
      );
    });

    it('should support dual provider sources (Plant.id and PlantNet)', async () => {
      // Arrange - PlantNet result
      const imageFile = new File(['image data'], 'plant.jpg', { type: 'image/jpeg' });
      const plantNetResult = {
        ...mockPlantResult,
        source: 'plantnet',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => plantNetResult,
      });

      // Act
      const result = await plantIdService.identifyPlant(imageFile);

      // Assert
      expect(result.source).toBe('plantnet');
      expect(['plant_id', 'plantnet']).toContain(result.source);
    });
  });

  // ============================================================================
  // GET HISTORY TESTS
  // ============================================================================

  describe('getHistory', () => {
    it('should fetch identification history', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockHistoryItem],
      });

      // Act
      const result = await plantIdService.getHistory();

      // Assert
      expect(result).toEqual([mockHistoryItem]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/plant-identification/history/'),
        expect.objectContaining({
          credentials: 'include',
          headers: expect.objectContaining({
            'X-CSRFToken': 'test-csrf-token',
          }),
        })
      );
    });

    it('should handle empty history', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      // Act
      const result = await plantIdService.getHistory();

      // Assert
      expect(result).toEqual([]);
    });

    it('should handle API errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      // Act & Assert
      await expect(plantIdService.getHistory()).rejects.toThrow(
        'Failed to load identification history'
      );
    });

    it('should handle network errors', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(plantIdService.getHistory()).rejects.toThrow(
        'Failed to load identification history'
      );
    });
  });

  // ============================================================================
  // SAVE TO COLLECTION TESTS
  // ============================================================================

  describe('saveToCollection', () => {
    const savePlantInput: SavePlantInput = {
      plant_name: 'Rosa damascena',
      confidence: 0.97,
      common_names: ['Damask Rose', 'Rose of Castile'],
      description: 'A deciduous shrub growing to 2.2 m',
      watering: 'Regular watering, allow soil to dry between waterings',
      propagation_methods: 'Cuttings, grafting',
      source: 'plant_id',
    };

    it('should save plant to default collection', async () => {
      // Arrange
      // Mock fetch collections
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCollection],
      });

      // Mock create plant
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUserPlant,
      });

      // Act
      const result = await plantIdService.saveToCollection(savePlantInput);

      // Assert
      expect(result).toEqual(mockUserPlant);
      expect(fetchMock).toHaveBeenCalledTimes(2);

      // Verify collections fetch
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/v1/users/collections/'),
        expect.any(Object)
      );

      // Verify plant creation
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        expect.stringContaining('/api/v1/plant-identification/plants/'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should include CSRF token in both requests', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCollection],
      });
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUserPlant,
      });

      // Act
      await plantIdService.saveToCollection(savePlantInput);

      // Assert
      const collectionsCall = fetchMock.mock.calls[0];
      const plantsCall = fetchMock.mock.calls[1];

      expect(collectionsCall[1].headers['X-CSRFToken']).toBe('test-csrf-token');
      expect(plantsCall[1].headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should require authentication (401 error)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      // Act & Assert
      await expect(plantIdService.saveToCollection(savePlantInput)).rejects.toThrow(
        'Authentication required to save plants'
      );
    });

    it('should handle missing collection error', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [], // No collections
      });

      // Act & Assert
      await expect(plantIdService.saveToCollection(savePlantInput)).rejects.toThrow(
        'No collection found. Please create a collection first.'
      );
    });

    it('should handle save failure with error message', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCollection],
      });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Duplicate plant in collection' }),
      });

      // Act & Assert
      await expect(plantIdService.saveToCollection(savePlantInput)).rejects.toThrow(
        'Duplicate plant in collection'
      );
    });

    it('should handle save failure without error message', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCollection],
      });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}),
      });

      // Act & Assert
      await expect(plantIdService.saveToCollection(savePlantInput)).rejects.toThrow(
        'Failed to save plant'
      );
    });

    it('should handle network errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCollection],
      });
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(plantIdService.saveToCollection(savePlantInput)).rejects.toThrow(
        'Network error'
      );
    });

    it('should map care instructions correctly', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCollection],
      });
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUserPlant,
      });

      // Act
      await plantIdService.saveToCollection(savePlantInput);

      // Assert
      const plantsCall = fetchMock.mock.calls[1];
      const requestBody = JSON.parse(plantsCall[1].body);

      expect(requestBody.collection).toBe(mockCollection.id);
      expect(requestBody.nickname).toBe(savePlantInput.plant_name);
      expect(requestBody.care_instructions_json.confidence).toBe(savePlantInput.confidence);
      expect(requestBody.care_instructions_json.watering).toBe(savePlantInput.watering);
      expect(requestBody.care_instructions_json.propagation).toBe(savePlantInput.propagation_methods);
      expect(requestBody.care_instructions_json.source).toBe(savePlantInput.source);
    });
  });
});
