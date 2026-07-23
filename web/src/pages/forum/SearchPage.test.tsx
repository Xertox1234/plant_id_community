import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import SearchPage from './SearchPage';
import { createMockCategory, createMockThread } from '../../tests/forumUtils';
import { mapSearchPostToPost } from '../../services/forumMappers';
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
    has_more_threads: false,
    has_more_posts: false,
    ...overrides,
  };
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock fetchCategories to return empty array by default
    vi.spyOn(forumService, 'fetchCategories').mockResolvedValue([]);

    // Mock searchForum to return empty results by default
    vi.spyOn(forumService, 'searchForum').mockResolvedValue(createMockSearchResults());
  });

  describe('Initial Render', () => {
    it('renders search page with heading', () => {
      renderSearchPage();

      expect(screen.getByRole('heading', { level: 1, name: 'Forum Search' })).toBeInTheDocument();
      expect(screen.getByText('Search across threads and posts')).toBeInTheDocument();
      // H9: the route sets a descriptive document title (React 19 metadata).
      expect(document.title).toContain('Forum Search');
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

      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue(mockCategories);

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
      vi.spyOn(forumService, 'searchForum').mockRejectedValue(new Error('Search failed'));

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
        // The summary now reads "Showing N …" (honest per-page count, not a total).
        expect(screen.getByText(/Showing/i)).toBeInTheDocument();
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

    it('does not render [deleted] author sentinel on search thread cards', async () => {
      // Search topics have no real author data; mapSearchTopicToThread produces a [deleted] sentinel.
      // ThreadCard with hideAuthor must not surface this sentinel as an author label.
      const deletedThread = createMockThread({
        id: '1',
        title: 'Watering Guide',
        author: { id: 0, email: '', username: '[deleted]', display_name: '[deleted]' },
      });
      const mockResults = createMockSearchResults({
        query: 'watering',
        threads: [deletedThread],
        total_threads: 1,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        expect(screen.getByText('Watering Guide')).toBeInTheDocument();
      });

      expect(screen.queryByText('[deleted]')).not.toBeInTheDocument();
    });

    it('renders post results as compact rows (excerpt + topic title link, no PostCard)', async () => {
      // Use real mapSearchPostToPost output — shape is {id, thread, author=[deleted], body=[], content_raw=excerpt, topic_title}
      // This matches what forumService.searchForum actually returns and would have shown "[deleted]" via PostCard.
      const post1 = mapSearchPostToPost({
        id: 1,
        topic_id: 42,
        topic_title: 'Watering Guide',
        topic_slug: 'watering-guide',
        board_id: 1,
        board_slug: 'plant-care',
        excerpt: 'Water your plants regularly',
      });
      const post2 = mapSearchPostToPost({
        id: 2,
        topic_id: 43,
        topic_title: 'Beginner Tips',
        topic_slug: 'beginner-tips',
        board_id: 1,
        board_slug: 'plant-care',
        excerpt: 'Watering tips for beginners',
      });
      const mockResults = createMockSearchResults({
        query: 'watering',
        posts: [post1, post2],
        total_posts: 2,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => {
        // Topic title rendered as a link
        expect(screen.getByRole('link', { name: /Watering Guide/i })).toBeInTheDocument();
        // Excerpt rendered as plain text
        expect(screen.getByText(/Water your plants regularly/i)).toBeInTheDocument();
      });

      // [deleted] sentinel must NOT appear — compact row does not render author
      expect(screen.queryByText('[deleted]')).not.toBeInTheDocument();
      // No empty PostCard author block (PostCard renders author.display_name in a specific element)
      expect(screen.queryByText('Test User')).not.toBeInTheDocument();
    });

    it('renders real counts and no decorative filters', async () => {
      const mockResults = createMockSearchResults({
        query: 'tomato',
        threads: [
          createMockThread({
            id: '31',
            title: 'Blight-resistant tomatoes',
            slug: 'tomato-blight',
            category: { id: '54', name: '', slug: 'general-discussion', created_at: '' },
            post_count: 3,
            view_count: 12,
          }),
        ],
        total_threads: 1,
      });

      vi.spyOn(forumService, 'searchForum').mockResolvedValue(mockResults);

      renderSearchPage('/forum/search?q=tomato');

      await waitFor(() =>
        expect(screen.getByText(/Blight-resistant tomatoes/)).toBeInTheDocument()
      );
      expect(screen.getByTitle('3 replies')).toBeInTheDocument();
      expect(screen.getByTitle('12 views')).toBeInTheDocument();
      expect(screen.queryByLabelText('Author')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('From')).not.toBeInTheDocument();
    });

    it('shows Load More when a section has_more, and appends the next page', async () => {
      const page1 = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread({ id: '1', title: 'Watering Guide' })],
        total_threads: 1,
        has_more_threads: true,
      });
      const page2 = createMockSearchResults({
        query: 'watering',
        threads: [createMockThread({ id: '2', title: 'Second Page Thread' })],
        total_threads: 1,
        has_more_threads: false,
      });
      const searchSpy = vi
        .spyOn(forumService, 'searchForum')
        .mockResolvedValueOnce(page1)
        .mockResolvedValueOnce(page2);

      renderSearchPage('/forum/search?q=watering');

      await waitFor(() => expect(screen.getByText('Watering Guide')).toBeInTheDocument());
      // First fetch is page 1.
      expect(searchSpy).toHaveBeenCalledWith(expect.objectContaining({ q: 'watering', page: 1 }));

      const loadMore = screen.getByRole('button', { name: /load more results/i });
      await userEvent.click(loadMore);

      // Load More requests page 2 and appends its results.
      await waitFor(() =>
        expect(searchSpy).toHaveBeenCalledWith(expect.objectContaining({ q: 'watering', page: 2 }))
      );
      // Query the ThreadCard heading specifically — the title also appears inside
      // the highlighted-match snippet (its excerpt matches the query).
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: 'Second Page Thread' })).toBeInTheDocument()
      );
      // The page-1 result is still present (appended, not replaced).
      expect(screen.getByRole('heading', { name: 'Watering Guide' })).toBeInTheDocument();
      // Page 2 has no more — the button is gone.
      expect(screen.queryByRole('button', { name: /load more results/i })).not.toBeInTheDocument();
    });

    it('shows Load More when only has_more_posts is true (posts section drives it)', async () => {
      // Covers the second operand of `has_more_threads || has_more_posts` — with
      // has_more_threads false, deleting `|| has_more_posts` would hide the button.
      const post1 = mapSearchPostToPost({
        id: 1,
        topic_id: 42,
        topic_title: 'Watering Guide',
        topic_slug: 'watering-guide',
        board_id: 1,
        board_slug: 'plant-care',
        excerpt: 'Water your plants',
      });
      const page1 = createMockSearchResults({
        query: 'watering',
        posts: [post1],
        total_posts: 1,
        has_more_threads: false,
        has_more_posts: true,
      });
      const page2 = createMockSearchResults({
        query: 'watering',
        posts: [
          mapSearchPostToPost({
            id: 2,
            topic_id: 43,
            topic_title: 'More watering',
            topic_slug: 'more-watering',
            board_id: 1,
            board_slug: 'plant-care',
            excerpt: 'even more watering',
          }),
        ],
        total_posts: 1,
        has_more_threads: false,
        has_more_posts: false,
      });
      const searchSpy = vi
        .spyOn(forumService, 'searchForum')
        .mockResolvedValueOnce(page1)
        .mockResolvedValueOnce(page2);

      renderSearchPage('/forum/search?q=watering');

      const loadMore = await screen.findByRole('button', { name: /load more results/i });
      await userEvent.click(loadMore);

      await waitFor(() =>
        expect(searchSpy).toHaveBeenCalledWith(expect.objectContaining({ q: 'watering', page: 2 }))
      );
      // Page 2 exhausts posts too — button disappears.
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: /load more results/i })).not.toBeInTheDocument()
      );
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
        expect(
          screen.getByText('Try different keywords or remove some filters')
        ).toBeInTheDocument();
      });
    });
  });

  describe('Filters', () => {
    it('displays filter section with category dropdown', async () => {
      const mockCategories = [
        createMockCategory({ id: '1', name: 'Plant Care', slug: 'plant-care' }),
      ];

      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue(mockCategories);

      renderSearchPage();

      await waitFor(() => {
        expect(screen.getByLabelText('Category')).toBeInTheDocument();
      });

      const categorySelect = screen.getByLabelText('Category');
      expect(within(categorySelect).getByText('All Categories')).toBeInTheDocument();
      expect(within(categorySelect).getByText('Plant Care')).toBeInTheDocument();
    });

    it('applies category filter when selected', async () => {
      const mockCategories = [
        createMockCategory({ id: '1', name: 'Plant Care', slug: 'plant-care' }),
      ];

      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue(mockCategories);

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
      renderSearchPage('/forum/search?q=watering&category=plant-care');

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
          })
        );
      });
    });

    it('hides clear filters button when no filters are active', () => {
      renderSearchPage('/forum/search?q=watering');

      expect(screen.queryByText('Clear filters')).not.toBeInTheDocument();
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
    });
  });
});
