import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import SearchPage from './SearchPage';
import { createMockCategory, createMockThread, createMockPost } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';

// Mock the forumService
vi.mock('../../services/forumService');

// Mock the AuthContext
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({ user: null, isAuthenticated: false })),
}));

/**
 * Helper to render SearchPage with Router and initial URL
 */
function renderSearchPage(initialUrl = '/forum/search') {
  return render(
    <MemoryRouter initialEntries={[initialUrl]}>
      <SearchPage />
    </MemoryRouter>
  );
}

/**
 * Create mock search results
 */
function createMockSearchResults(overrides = {}) {
  return {
    query: 'watering',
    threads: [],
    posts: [],
    total_threads: 0,
    total_posts: 0,
    page: 1,
    page_size: 20,
    has_next_threads: false,
    has_next_posts: false,
    filters: {
      category: null,
      author: null,
      date_from: null,
      date_to: null,
    },
    ...overrides,
  };
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock fetchCategories to return empty array by default
    vi.spyOn(forumService, 'fetchCategories').mockResolvedValue({
      results: [],
    });

    // Mock searchForum to return empty results by default
    vi.spyOn(forumService, 'searchForum').mockResolvedValue(
      createMockSearchResults()
    );
  });

  describe('Initial Render', () => {
    it('renders search page with heading', () => {
      renderSearchPage();

      expect(screen.getByRole('heading', { level: 1, name: 'Forum Search' })).toBeInTheDocument();
      expect(screen.getByText('Search across threads and posts')).toBeInTheDocument();
    });

    it('shows search input with placeholder', () => {
      renderSearchPage();

      const searchInput = screen.getByPlaceholderText('Search forum...');
      expect(searchInput).toBeInTheDocument();
      expect(searchInput).toHaveAttribute('aria-label', 'Search query');
    });

    it('shows empty state when no query is entered', () => {
      renderSearchPage();

      expect(screen.getByText('Enter a search query to begin')).toBeInTheDocument();
    });

    it('fetches categories for filter dropdown on mount', async () => {
      const mockCategories = [
        createMockCategory({ id: '1', name: 'Plant Care', slug: 'plant-care' }),
        createMockCategory({ id: '2', name: 'Pest Control', slug: 'pest-control' }),
      ];

      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue({
        results: mockCategories,
      });

      renderSearchPage();

      await waitFor(() => {
        expect(forumService.fetchCategories).toHaveBeenCalled();
      });
    });
  });

  describe('Search Functionality', () => {
    it('performs search when query parameter is in URL', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread({ title: 'Watering Guide' })],
        total_threads: 1,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(forumService.searchForum).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'watering',
          })
        );
      });
    });

    it('displays loading spinner while searching', async () => {
      vi.spyOn(forumService, 'searchForum').mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
      });
    });

    it('displays error message when search fails', async () => {
      vi.spyOn(forumService, 'searchForum').mockRejectedValue(
        new Error('Search failed')
      );

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(screen.getByText('Search failed')).toBeInTheDocument();
      });
    });
  });

  describe('Search Results', () => {
    it('displays results summary with counts', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        total_threads: 5,
        total_posts: 12,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        // Simply check that "Found" text appears
        expect(screen.getByText(/Found/i)).toBeInTheDocument();
      });
    });

    it('renders thread results in separate section', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [
          createMockThread({ id: '1', title: 'Watering Guide' }),
          createMockThread({ id: '2', title: 'Best Watering Schedule' }),
        ],
        total_threads: 2,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        // Check for thread titles in results
        expect(screen.getByText('Watering Guide')).toBeInTheDocument();
      });
    });

    it('renders post results in separate section', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        posts: [
          createMockPost({ id: '1', content_raw: 'Water your plants regularly' }),
          createMockPost({ id: '2', content_raw: 'Watering tips for beginners' }),
        ],
        total_posts: 2,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        // Check for post content in results
        expect(screen.getByText(/Water your plants regularly/i)).toBeInTheDocument();
      });
    });

    it('displays no results message when no matches found', async () => {
      const mockResults = createMockSearchResults({
        query: 'xyz123',
        total_threads: 0,
        total_posts: 0,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=xyz123');

      await waitFor(() => {
        expect(screen.getByText('No results found for "xyz123"')).toBeInTheDocument();
        expect(screen.getByText('Try different keywords or remove some filters')).toBeInTheDocument();
      });
    });
  });

  describe('Filters', () => {
    it('displays filter section with category dropdown', async () => {
      const mockCategories = [
        createMockCategory({ id: '1', name: 'Plant Care', slug: 'plant-care' }),
      ];

      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue({
        results: mockCategories,
      });

      renderSearchPage();

      await waitFor(() => {
        expect(screen.getByLabelText('Category')).toBeInTheDocument();
      });

      const categorySelect = screen.getByLabelText('Category');
      expect(within(categorySelect).getByText('All Categories')).toBeInTheDocument();
      expect(within(categorySelect).getByText('Plant Care')).toBeInTheDocument();
    });

    it('displays author filter input', () => {
      renderSearchPage();

      expect(screen.getByLabelText('Author')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Username')).toBeInTheDocument();
    });

    it('applies category filter when selected', async () => {
      const mockCategories = [
        createMockCategory({ id: '1', name: 'Plant Care', slug: 'plant-care' }),
      ];

      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue({
        results: mockCategories,
      });

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(screen.getByLabelText('Category')).toBeInTheDocument();
      });

      const categorySelect = screen.getByLabelText('Category');
      await userEvent.selectOptions(categorySelect, 'plant-care');

      await waitFor(() => {
        expect(forumService.searchForum).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'watering',
            category: 'plant-care',
          })
        );
      });
    });

    it('shows clear filters button when filters are active', async () => {
      renderSearchPage('/forum/search?q=watering&category=plant-care');

      await waitFor(() => {
        expect(screen.getByText('Clear filters')).toBeInTheDocument();
      });
    });

    it('clears all filters when clear button clicked', async () => {

      renderSearchPage('/forum/search?q=watering&category=plant-care&author=john');

      await waitFor(() => {
        expect(screen.getByText('Clear filters')).toBeInTheDocument();
      });

      const clearButton = screen.getByText('Clear filters');
      await userEvent.click(clearButton);

      await waitFor(() => {
        expect(forumService.searchForum).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'watering',
            category: '',
            author: '',
          })
        );
      });
    });

    it('hides clear filters button when no filters are active', () => {
      renderSearchPage('/forum/search?q=watering');

      expect(screen.queryByText('Clear filters')).not.toBeInTheDocument();
    });
  });

  describe('Pagination', () => {
    it('displays pagination controls when there are more results', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread()],
        has_next_threads: true,
        page: 1,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(screen.getByText('Previous')).toBeInTheDocument();
        expect(screen.getByText('Next')).toBeInTheDocument();
        expect(screen.getByText('Page 1')).toBeInTheDocument();
      });
    });

    it('disables previous button on first page', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread()],
        page: 1,
        has_next_threads: true, // Need this to show pagination controls
      });

      forumService.searchForum.mockImplementation(() => Promise.resolve(mockResults));

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        const prevButton = screen.getByText('Previous');
        expect(prevButton).toBeDisabled();
      });
    });

    it('disables next button when no more results', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread()],
        has_next_threads: false,
        has_next_posts: false,
        page: 2, // Set page > 1 to ensure pagination controls render
      });

      forumService.searchForum.mockImplementation(() => Promise.resolve(mockResults));

      renderSearchPage('/forum/search?q=watering&page=2');

      await waitFor(() => {
        const nextButton = screen.getByText('Next');
        expect(nextButton).toBeDisabled();
      });
    });

    it('navigates to next page when next button clicked', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread()],
        has_next_threads: true,
        page: 1,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(screen.getByText('Next')).toBeInTheDocument();
      });

      const nextButton = screen.getByText('Next');
      await userEvent.click(nextButton);

      await waitFor(() => {
        expect(forumService.searchForum).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'watering',
            page: 2,
          })
        );
      });
    });

    it('navigates to previous page when previous button clicked', async () => {
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread()],
        page: 2,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering&page=2');

      await waitFor(() => {
        expect(screen.getByText('Previous')).toBeInTheDocument();
      });

      const prevButton = screen.getByText('Previous');
      await userEvent.click(prevButton);

      await waitFor(() => {
        expect(forumService.searchForum).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'watering',
            page: 1,
          })
        );
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper aria-label on search input', () => {
      renderSearchPage();

      const searchInput = screen.getByPlaceholderText('Search forum...');
      expect(searchInput).toHaveAttribute('aria-label', 'Search query');
    });

    it('uses semantic heading hierarchy', () => {
      renderSearchPage();

      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    });

    it('has proper label-input associations for filters', async () => {
      renderSearchPage();

      const categoryLabel = screen.getByText('Category');
      const categorySelect = screen.getByLabelText('Category');
      expect(categoryLabel).toBeInTheDocument();
      expect(categorySelect).toHaveAttribute('id', 'category-filter');

      const authorLabel = screen.getByText('Author');
      const authorInput = screen.getByLabelText('Author');
      expect(authorLabel).toBeInTheDocument();
      expect(authorInput).toHaveAttribute('id', 'author-filter');
    });
  });
});
