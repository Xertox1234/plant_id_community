/**
 * Diagnosis Service Tests
 *
 * Comprehensive tests for diagnosis service covering:
 * - Diagnosis card CRUD operations
 * - Diagnosis reminder operations
 * - JWT Bearer token authentication
 * - Pagination and filtering
 * - Error handling
 *
 * Priority: P1 - CRITICAL (Core diagnosis feature)
 * Coverage Target: 100% branch coverage
 * Estimated Test Count: 18 tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchDiagnosisCards,
  fetchDiagnosisCard,
  createDiagnosisCard,
  updateDiagnosisCard,
  deleteDiagnosisCard,
  fetchFavoriteDiagnosisCards,
  fetchActiveTreatments,
  fetchSuccessfulTreatments,
  toggleFavorite,
  fetchReminders,
  createReminder,
  fetchUpcomingReminders,
  snoozeReminder,
  cancelReminder,
  acknowledgeReminder,
  deleteReminder,
} from './diagnosisService';
import type {
  DiagnosisCard,
  DiagnosisReminder,
  CreateDiagnosisCardInput,
  UpdateDiagnosisCardInput,
  CreateReminderInput,
  PaginatedDiagnosisCardsResponse,
  PaginatedRemindersResponse,
} from '../types/diagnosis';

// Mock logger to prevent console noise
vi.mock('../utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('diagnosisService', () => {
  // Test fixtures
  const mockDiagnosisCard: DiagnosisCard = {
    uuid: 'card-uuid-123',
    diagnosis_result: 'result-123',
    plant_scientific_name: 'Rosa damascena',
    plant_common_name: 'Damask Rose',
    custom_nickname: 'My Rose',
    display_name: 'My Rose',
    disease_name: 'Powdery Mildew',
    disease_type: 'fungal',
    disease_type_display: 'Fungal',
    severity_assessment: 'moderate',
    severity_display: 'Moderate',
    confidence_score: 0.92,
    care_instructions: [{ type: 'heading', value: 'Treatment Steps', id: '1' }],
    personal_notes: 'Started treatment on Monday',
    treatment_status: 'in_progress',
    treatment_status_display: 'In Progress',
    plant_recovered: false,
    share_with_community: false,
    is_favorite: false,
    saved_at: '2025-01-01T00:00:00Z',
    last_updated: '2025-01-02T00:00:00Z',
  };

  const mockReminder: DiagnosisReminder = {
    uuid: 'reminder-uuid-456',
    diagnosis_card: 'card-uuid-123',
    reminder_type: 'check_progress',
    reminder_type_display: 'Check Progress',
    reminder_title: 'Check plant progress',
    reminder_message: 'Check if symptoms have improved',
    scheduled_date: '2025-01-10T10:00:00Z',
    is_active: true,
    sent: false,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  };

  const mockPaginatedCards: PaginatedDiagnosisCardsResponse = {
    count: 1,
    next: null,
    previous: null,
    results: [mockDiagnosisCard],
  };

  const mockPaginatedReminders: PaginatedRemindersResponse = {
    count: 1,
    next: null,
    previous: null,
    results: [mockReminder],
  };

  // Mock implementations
  let fetchMock: ReturnType<typeof vi.fn>;
  let documentCookieMock: string;

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // Mock document.cookie with JWT access token
    documentCookieMock = 'access_token=test-jwt-token';
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
  // DIAGNOSIS CARD TESTS
  // ============================================================================

  describe('fetchDiagnosisCards', () => {
    it('should fetch diagnosis cards with default options', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPaginatedCards,
      });

      // Act
      const result = await fetchDiagnosisCards();

      // Assert
      expect(result).toEqual(mockPaginatedCards);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/plant-identification/diagnosis-cards/'),
        expect.objectContaining({
          method: 'GET',
          credentials: 'include',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer test-jwt-token',
          }),
        })
      );
    });

    it('should fetch diagnosis cards with filters', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPaginatedCards,
      });

      // Act
      await fetchDiagnosisCards({
        treatment_status: 'in_progress',
        is_favorite: true,
        disease_type: 'fungal',
        search: 'rose',
        page: 2,
      });

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const url = fetchCall[0];
      expect(url).toContain('treatment_status=in_progress');
      expect(url).toContain('is_favorite=true');
      expect(url).toContain('disease_type=fungal');
      expect(url).toContain('search=rose');
      expect(url).toContain('page=2');
    });

    it('should handle API errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Server error' }),
      });

      // Act & Assert
      await expect(fetchDiagnosisCards()).rejects.toThrow('Server error');
    });
  });

  describe('fetchDiagnosisCard', () => {
    it('should fetch a single diagnosis card by UUID', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDiagnosisCard,
      });

      // Act
      const result = await fetchDiagnosisCard('card-uuid-123');

      // Assert
      expect(result).toEqual(mockDiagnosisCard);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/card-uuid-123/'),
        expect.any(Object)
      );
    });

    it('should handle 404 not found errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Diagnosis card not found' }),
      });

      // Act & Assert
      await expect(fetchDiagnosisCard('invalid-uuid')).rejects.toThrow(
        'Diagnosis card not found'
      );
    });
  });

  describe('createDiagnosisCard', () => {
    const createInput: CreateDiagnosisCardInput = {
      diagnosis_result: 'result-123',
      plant_scientific_name: 'Rosa damascena',
      plant_common_name: 'Damask Rose',
      disease_name: 'Powdery Mildew',
      disease_type: 'fungal',
      severity_assessment: 'moderate',
      confidence_score: 0.92,
      care_instructions: [],
    };

    it('should create a new diagnosis card', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDiagnosisCard,
      });

      // Act
      const result = await createDiagnosisCard(createInput);

      // Assert
      expect(result).toEqual(mockDiagnosisCard);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            Authorization: 'Bearer test-jwt-token',
          }),
          body: JSON.stringify(createInput),
        })
      );
    });

    it('should handle validation errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid confidence score' }),
      });

      // Act & Assert
      await expect(createDiagnosisCard(createInput)).rejects.toThrow(
        'Invalid confidence score'
      );
    });
  });

  describe('updateDiagnosisCard', () => {
    const updateInput: UpdateDiagnosisCardInput = {
      custom_nickname: 'My Favorite Rose',
      treatment_status: 'successful',
      plant_recovered: true,
    };

    it('should update a diagnosis card', async () => {
      // Arrange
      const updatedCard = { ...mockDiagnosisCard, ...updateInput };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedCard,
      });

      // Act
      const result = await updateDiagnosisCard('card-uuid-123', updateInput);

      // Assert
      expect(result).toEqual(updatedCard);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/card-uuid-123/'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify(updateInput),
        })
      );
    });
  });

  describe('deleteDiagnosisCard', () => {
    it('should delete a diagnosis card', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
      });

      // Act
      await deleteDiagnosisCard('card-uuid-123');

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/card-uuid-123/'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });

    it('should handle delete errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ error: 'Permission denied' }),
      });

      // Act & Assert
      await expect(deleteDiagnosisCard('card-uuid-123')).rejects.toThrow(
        'Permission denied'
      );
    });
  });

  describe('fetchFavoriteDiagnosisCards', () => {
    it('should fetch favorite diagnosis cards', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPaginatedCards,
      });

      // Act
      const result = await fetchFavoriteDiagnosisCards();

      // Assert
      expect(result).toEqual(mockPaginatedCards);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/favorites/'),
        expect.any(Object)
      );
    });
  });

  describe('fetchActiveTreatments', () => {
    it('should fetch active treatment cards', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockDiagnosisCard],
      });

      // Act
      const result = await fetchActiveTreatments();

      // Assert
      expect(result).toEqual([mockDiagnosisCard]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/active_treatments/'),
        expect.any(Object)
      );
    });
  });

  describe('fetchSuccessfulTreatments', () => {
    it('should fetch successful treatment cards', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockDiagnosisCard],
      });

      // Act
      const result = await fetchSuccessfulTreatments();

      // Assert
      expect(result).toEqual([mockDiagnosisCard]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/successful_treatments/'),
        expect.any(Object)
      );
    });
  });

  describe('toggleFavorite', () => {
    it('should toggle favorite status', async () => {
      // Arrange
      const favoriteCard = { ...mockDiagnosisCard, is_favorite: true };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => favoriteCard,
      });

      // Act
      const result = await toggleFavorite('card-uuid-123');

      // Assert
      expect(result).toEqual(favoriteCard);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-cards/card-uuid-123/toggle_favorite/'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  // ============================================================================
  // DIAGNOSIS REMINDER TESTS
  // ============================================================================

  describe('fetchReminders', () => {
    it('should fetch reminders with default options', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPaginatedReminders,
      });

      // Act
      const result = await fetchReminders();

      // Assert
      expect(result).toEqual(mockPaginatedReminders);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-reminders/'),
        expect.any(Object)
      );
    });

    it('should fetch reminders with filters', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPaginatedReminders,
      });

      // Act
      await fetchReminders({
        diagnosis_card: 'card-uuid-123',
        is_active: true,
        sent: false,
        reminder_type: 'check_progress',
      });

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const url = fetchCall[0];
      expect(url).toContain('diagnosis_card=card-uuid-123');
      expect(url).toContain('is_active=true');
      expect(url).toContain('sent=false');
      expect(url).toContain('reminder_type=check_progress');
    });
  });

  describe('createReminder', () => {
    const reminderInput: CreateReminderInput = {
      diagnosis_card: 'card-uuid-123',
      reminder_type: 'check_progress',
      reminder_title: 'Check plant progress',
      scheduled_date: '2025-01-10T10:00:00Z',
    };

    it('should create a new reminder', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockReminder,
      });

      // Act
      const result = await createReminder(reminderInput);

      // Assert
      expect(result).toEqual(mockReminder);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-reminders/'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(reminderInput),
        })
      );
    });
  });

  describe('fetchUpcomingReminders', () => {
    it('should fetch upcoming reminders', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockReminder],
      });

      // Act
      const result = await fetchUpcomingReminders();

      // Assert
      expect(result).toEqual([mockReminder]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-reminders/upcoming/'),
        expect.any(Object)
      );
    });
  });

  describe('snoozeReminder', () => {
    it('should snooze a reminder with default hours', async () => {
      // Arrange
      const snoozedReminder = {
        ...mockReminder,
        snoozed_until: '2025-01-02T00:00:00Z',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => snoozedReminder,
      });

      // Act
      const result = await snoozeReminder('reminder-uuid-456');

      // Assert
      expect(result).toEqual(snoozedReminder);
      const fetchCall = fetchMock.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);
      expect(body.hours).toBe(24); // Default
    });

    it('should snooze a reminder with custom hours', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockReminder,
      });

      // Act
      await snoozeReminder('reminder-uuid-456', 48);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);
      expect(body.hours).toBe(48);
    });
  });

  describe('cancelReminder', () => {
    it('should cancel a reminder', async () => {
      // Arrange
      const cancelledReminder = { ...mockReminder, cancelled: true };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => cancelledReminder,
      });

      // Act
      const result = await cancelReminder('reminder-uuid-456');

      // Assert
      expect(result).toEqual(cancelledReminder);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-reminders/reminder-uuid-456/cancel/'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('acknowledgeReminder', () => {
    it('should acknowledge a sent reminder', async () => {
      // Arrange
      const acknowledgedReminder = { ...mockReminder, sent: true };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => acknowledgedReminder,
      });

      // Act
      const result = await acknowledgeReminder('reminder-uuid-456');

      // Assert
      expect(result).toEqual(acknowledgedReminder);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-reminders/reminder-uuid-456/acknowledge/'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('deleteReminder', () => {
    it('should delete a reminder', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
      });

      // Act
      await deleteReminder('reminder-uuid-456');

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/diagnosis-reminders/reminder-uuid-456/'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });

    it('should handle delete errors', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Reminder not found' }),
      });

      // Act & Assert
      await expect(deleteReminder('invalid-uuid')).rejects.toThrow(
        'Reminder not found'
      );
    });
  });

  // ============================================================================
  // AUTHENTICATION TESTS
  // ============================================================================

  describe('authentication', () => {
    it('should omit Authorization header when token is missing', async () => {
      // Arrange
      documentCookieMock = ''; // No access token
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPaginatedCards,
      });

      // Act
      await fetchDiagnosisCards();

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers.Authorization).toBeUndefined();
    });
  });
});
