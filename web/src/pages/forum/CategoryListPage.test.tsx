import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import CategoryListPage from './CategoryListPage';
import { createMockCategory } from '../../tests/forumUtils';
import type { Category } from '../../types/forum';
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
 * The forum home payload: boards plus the CMS welcome copy, in one response
 * (todo 278 L2 — `GET boards/` returns `{results, intro}`).
 */
function indexPayload(categories: Category[], intro = '') {
  return { categories, intro };
}

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
    vi.spyOn(forumService, 'fetchForumIndex').mockImplementation(() => new Promise(() => {}));

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

    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(mockCategories));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('Plant Care')).toBeInTheDocument();
    });

    expect(screen.getByText('Tips for plant care')).toBeInTheDocument();
    expect(screen.getByText('Plant Identification')).toBeInTheDocument();
    expect(screen.getByText('Help identify plants')).toBeInTheDocument();
  });

  it('renders page header with title and description', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('Community Forums')).toBeInTheDocument();
    });

    expect(screen.getByText(/Connect with fellow plant enthusiasts/i)).toBeInTheDocument();
    // H9: the route sets a descriptive document title (React 19 metadata).
    expect(document.title).toContain('Community Forums');
  });

  it('displays error message when API call fails', async () => {
    const errorMessage = 'Failed to load categories';

    vi.spyOn(forumService, 'fetchForumIndex').mockRejectedValue(new Error(errorMessage));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText(/Error loading categories/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('recovers via Retry after a failed load (audit H18)', async () => {
    const fetchSpy = vi
      .spyOn(forumService, 'fetchForumIndex')
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(
        indexPayload([createMockCategory({ id: 'cat-1', name: 'Plant Care' })])
      );

    renderCategoryListPage();

    // First load fails → error panel with a Retry button.
    const retry = await screen.findByRole('button', { name: /retry/i });
    // Retry re-runs the fetch; the second attempt succeeds and renders content.
    await userEvent.click(retry);

    await waitFor(() => expect(screen.getByText('Plant Care')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it('shows empty state when no categories exist', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('No boards yet')).toBeInTheDocument();
    });

    // Audit L2: the empty state explains what the forum is for and offers a
    // way onward, instead of reading as a broken page.
    expect(screen.getByText(/This community is just getting started/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /identify a plant/i })).toHaveAttribute(
      'href',
      '/identify'
    );
  });

  it('renders the CMS welcome copy as HTML (audit L2)', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
      indexPayload([], '<p>Welcome! Please read the <a href="/rules">rules</a>.</p>')
    );

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText(/Welcome!/)).toBeInTheDocument());
    // Rendered as markup, not escaped text — the link is a real anchor.
    expect(screen.getByRole('link', { name: 'rules' })).toHaveAttribute('href', '/rules');
  });

  it('sanitizes the CMS welcome copy before rendering it', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
      indexPayload([], '<p>Hi</p><img src="x" onerror="window.__xss = true">')
    );

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText('Hi')).toBeInTheDocument());
    // The backend sanitizes too; this is the second layer, and the one that
    // protects against a compromised/mis-implemented first layer.
    expect(document.querySelector('img[onerror]')).toBeNull();
  });

  it('renders no welcome block when the CMS intro is empty', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([], ''));

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText('No boards yet')).toBeInTheDocument());
    expect(document.querySelector('.prose')).toBeNull();
  });

  it('calls fetchForumIndex on mount', async () => {
    const fetchSpy = vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));

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

    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(mockCategories));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });

    expect(screen.getByText('Category 2')).toBeInTheDocument();
    expect(screen.getByText('Category 3')).toBeInTheDocument();
  });

  it('hides loading spinner after data loads', async () => {
    const mockCategories = [createMockCategory()];

    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(mockCategories));

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

    vi.spyOn(forumService, 'fetchForumIndex').mockRejectedValue(new Error(errorMessage));

    renderCategoryListPage();

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalled();
    });

    // Check that error was logged with correct format
    expect(logger.error).toHaveBeenCalledWith(
      'Error loading forum categories',
      expect.objectContaining({
        component: 'CategoryListPage',
        error: expect.any(Error),
      })
    );
  });
});
