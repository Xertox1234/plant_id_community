import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import CategoryListPage from './CategoryListPage';
import { createMockCategory } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';
import { logger } from '../../utils/logger';

// Mock the forumService
vi.mock('../../services/forumService');

// Mock logger
vi.mock('../../utils/logger', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

/**
 * Helper to render CategoryListPage with Router context
 */
function renderCategoryListPage() {
  return render(
    <BrowserRouter>
      <CategoryListPage />
    </BrowserRouter>
  );
}

describe('CategoryListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading spinner while fetching categories', () => {
    // Mock API to never resolve (stays in loading state)
    vi.spyOn(forumService, 'fetchCategoryTree').mockImplementation(
      () => new Promise(() => {})
    );

    renderCategoryListPage();

    // LoadingSpinner should be visible
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders categories when API call succeeds', async () => {
    const mockCategories = [
      createMockCategory({
        id: 'cat-1',
        name: 'Plant Care',
        description: 'Tips for plant care',
        thread_count: 50,
        post_count: 300,
      }),
      createMockCategory({
        id: 'cat-2',
        name: 'Plant Identification',
        description: 'Help identify plants',
        thread_count: 75,
        post_count: 500,
      }),
    ];

    vi.spyOn(forumService, 'fetchCategoryTree').mockResolvedValue(mockCategories);

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('Plant Care')).toBeInTheDocument();
    });

    expect(screen.getByText('Tips for plant care')).toBeInTheDocument();
    expect(screen.getByText('Plant Identification')).toBeInTheDocument();
    expect(screen.getByText('Help identify plants')).toBeInTheDocument();
  });

  it('renders page header with title and description', async () => {
    vi.spyOn(forumService, 'fetchCategoryTree').mockResolvedValue([]);

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('Community Forums')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Connect with fellow plant enthusiasts/i)
    ).toBeInTheDocument();
  });

  it('displays error message when API call fails', async () => {
    const errorMessage = 'Failed to load categories';

    vi.spyOn(forumService, 'fetchCategoryTree').mockRejectedValue(
      new Error(errorMessage)
    );

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText(/Error loading categories/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('shows empty state when no categories exist', async () => {
    vi.spyOn(forumService, 'fetchCategoryTree').mockResolvedValue([]);

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('No categories available yet.')).toBeInTheDocument();
    });

    expect(screen.getByText('Check back soon!')).toBeInTheDocument();
  });

  it('calls fetchCategoryTree on mount', async () => {
    const fetchSpy = vi.spyOn(forumService, 'fetchCategoryTree').mockResolvedValue([]);

    renderCategoryListPage();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    });
  });

  it('renders multiple categories in grid layout', async () => {
    const mockCategories = [
      createMockCategory({ id: 'cat-1', name: 'Category 1' }),
      createMockCategory({ id: 'cat-2', name: 'Category 2' }),
      createMockCategory({ id: 'cat-3', name: 'Category 3' }),
    ];

    vi.spyOn(forumService, 'fetchCategoryTree').mockResolvedValue(mockCategories);

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });

    expect(screen.getByText('Category 2')).toBeInTheDocument();
    expect(screen.getByText('Category 3')).toBeInTheDocument();
  });

  it('hides loading spinner after data loads', async () => {
    const mockCategories = [createMockCategory()];

    vi.spyOn(forumService, 'fetchCategoryTree').mockResolvedValue(mockCategories);

    renderCategoryListPage();

    // Initially should show loading
    expect(screen.getByRole('status')).toBeInTheDocument();

    // After loading, spinner should be gone
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
  });

  it('logs errors to console when API fails', async () => {
    const errorMessage = 'Network error';

    vi.spyOn(forumService, 'fetchCategoryTree').mockRejectedValue(
      new Error(errorMessage)
    );

    renderCategoryListPage();

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalled();
    });

    // Check that error was logged with correct format
    expect(logger.error).toHaveBeenCalledWith(
      'Error loading forum categories',
      expect.objectContaining({
        component: 'CategoryListPage',
        error: expect.any(Error)
      })
    );
  });
});
