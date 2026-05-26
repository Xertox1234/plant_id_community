import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadListPage from './ThreadListPage';
import { createMockCategory, createMockThread } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(),
  };
});

// Mock the forumService
vi.mock('../../services/forumService');

/**
 * Helper to render ThreadListPage with Router and URL params
 */
function renderThreadListPage(initialEntries = ['/forum/plant-care']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ThreadListPage />
    </MemoryRouter>
  );
}

describe('ThreadListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useParams to return a hybrid id-slug; lookups use the leading id.
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
    });
  });

  it('shows loading spinner while fetching data', () => {
    vi.spyOn(forumService, 'fetchCategory').mockImplementation(() => new Promise(() => {}));
    vi.spyOn(forumService, 'fetchThreads').mockImplementation(() => new Promise(() => {}));

    renderThreadListPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('fetches category and threads in parallel on mount', async () => {
    const mockCategory = createMockCategory({
      slug: 'plant-care',
      name: 'Plant Care',
    });
    const mockThreads = {
      items: [createMockThread({ id: '1', title: 'Test Thread' })],
      meta: { count: 1, next: null, previous: null },
    };

    const fetchCategorySpy = vi
      .spyOn(forumService, 'fetchCategory')
      .mockResolvedValue(mockCategory);
    const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(fetchCategorySpy).toHaveBeenCalledWith(3);
      expect(fetchThreadsSpy).toHaveBeenCalledWith({ category: 3, page: 1 });
    });
  });

  it('displays category name and description', async () => {
    const mockCategory = createMockCategory({
      slug: 'plant-care',
      name: 'Plant Care Tips',
      description: 'Learn how to care for your plants',
      icon: '🌱',
    });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'Plant Care Tips' })
      ).toBeInTheDocument();
    });

    expect(screen.getByText('Learn how to care for your plants')).toBeInTheDocument();
    expect(screen.getByText('🌱')).toBeInTheDocument();
  });

  it('renders threads when API call succeeds', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });
    const mockThreads = {
      items: [
        createMockThread({
          id: '1',
          title: 'How to water succulents?',
          excerpt: 'Looking for watering tips',
        }),
        createMockThread({
          id: '2',
          title: 'Best fertilizer for roses?',
          excerpt: 'Need fertilizer recommendations',
        }),
      ],
      meta: { count: 2, next: null, previous: null },
    };

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('How to water succulents?')).toBeInTheDocument();
    });

    expect(screen.getByText('Best fertilizer for roses?')).toBeInTheDocument();
  });

  it('displays error message when category fetch fails', async () => {
    const errorMessage = 'Category not found';

    vi.spyOn(forumService, 'fetchCategory').mockRejectedValue(new Error(errorMessage));
    vi.spyOn(forumService, 'fetchThreads').mockRejectedValue(new Error(errorMessage));

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText(/Error:/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('shows empty state when no threads exist', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('No threads found.')).toBeInTheDocument();
    });

    expect(screen.getByText(/Be the first to start a discussion!/i)).toBeInTheDocument();
  });

  it('renders breadcrumb navigation with Forums link', async () => {
    const mockCategory = createMockCategory({
      slug: 'plant-care',
      name: 'Plant Care',
    });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      const breadcrumb = screen.getByLabelText('Breadcrumb');
      expect(breadcrumb).toBeInTheDocument();
    });

    const breadcrumb = screen.getByLabelText('Breadcrumb');
    expect(breadcrumb).toHaveTextContent('Forums');
    expect(breadcrumb).toHaveTextContent('Plant Care');
  });

  // NOTE: in-category search/ordering are intentionally NOT API-backed in Phase 1
  // (the backend topics endpoint only honors `page`). These controls drive the URL
  // and the UI; the assertions below verify that surface, not a backend filter.
  it('submits search form and surfaces the active search filter', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search threads...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search threads...');
    const searchButton = screen.getByText('Search');

    await userEvent.type(searchInput, 'watering');
    await userEvent.click(searchButton);

    await waitFor(() => {
      expect(screen.getByText(/Searching for:/i)).toBeInTheDocument();
    });
    expect(screen.getByText('watering')).toBeInTheDocument();
  });

  it('changes ordering when dropdown selection changes', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Recent Activity')).toBeInTheDocument();
    });

    const orderingSelect = screen.getByDisplayValue('Recent Activity');
    await userEvent.selectOptions(orderingSelect, 'Most Viewed');

    await waitFor(() => {
      expect(screen.getByDisplayValue('Most Viewed')).toBeInTheDocument();
    });
  });

  it('displays active search filter with clear button', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage(['/forum/3-plant-care?search=watering']);

    await waitFor(() => {
      expect(screen.getByText(/Searching for:/i)).toBeInTheDocument();
    });

    expect(screen.getByText('watering')).toBeInTheDocument();

    const clearButton = screen.getByText('Clear');
    expect(clearButton).toBeInTheDocument();

    // Click clear button
    await userEvent.click(clearButton);

    // The active search filter is removed from the UI.
    await waitFor(() => {
      expect(screen.queryByText(/Searching for:/i)).not.toBeInTheDocument();
    });
  });

  it('renders pagination buttons when multiple pages exist', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: Array(20).fill(createMockThread()),
      meta: { count: 45, next: 'next-url', previous: null },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Previous')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
  });

  it('disables Previous button on first page', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: Array(20).fill(createMockThread()),
      meta: { count: 45 },
    });

    renderThreadListPage();

    await waitFor(() => {
      const previousButton = screen.getByText('Previous');
      expect(previousButton).toBeDisabled();
    });
  });

  it('renders New Thread button with correct link', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      const newThreadButton = screen.getByText('+ New Thread');
      expect(newThreadButton).toBeInTheDocument();
    });

    const link = screen.getByText('+ New Thread').closest('a');
    expect(link).toHaveAttribute('href', '/forum/new-thread?category=3-plant-care');
  });

  it('hides pagination when only one page exists', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [createMockThread()],
      meta: { count: 1 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText(/How to water succulents/i)).toBeInTheDocument();
    });

    expect(screen.queryByText('Previous')).not.toBeInTheDocument();
    expect(screen.queryByText('Next')).not.toBeInTheDocument();
  });

  it('shows different empty message for search with no results', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage(['/forum/plant-care?search=nonexistent']);

    await waitFor(() => {
      expect(screen.getByText('No threads found.')).toBeInTheDocument();
    });

    expect(screen.getByText(/Try a different search query/i)).toBeInTheDocument();
  });
});
