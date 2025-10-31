import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter } from 'react-router';
import * as ReactRouter from 'react-router';
import ThreadListPage from './ThreadListPage';
import { createMockCategory, createMockThread } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';

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

    // Mock useParams to return categorySlug
    vi.spyOn(ReactRouter, 'useParams').mockReturnValue({
      categorySlug: 'plant-care'
    });
  });

  it('shows loading spinner while fetching data', () => {
    vi.spyOn(forumService, 'fetchCategory').mockImplementation(
      () => new Promise(() => {})
    );
    vi.spyOn(forumService, 'fetchThreads').mockImplementation(
      () => new Promise(() => {})
    );

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
    const fetchThreadsSpy = vi
      .spyOn(forumService, 'fetchThreads')
      .mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(fetchCategorySpy).toHaveBeenCalledWith('plant-care');
      expect(fetchThreadsSpy).toHaveBeenCalled();
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
      expect(screen.getByRole('heading', { name: 'Plant Care Tips' })).toBeInTheDocument();
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

    vi.spyOn(forumService, 'fetchCategory').mockRejectedValue(
      new Error(errorMessage)
    );
    vi.spyOn(forumService, 'fetchThreads').mockRejectedValue(
      new Error(errorMessage)
    );

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

  it('submits search form and updates URL params', async () => {
    const user = userEvent.setup();
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

    await user.type(searchInput, 'watering');
    await user.click(searchButton);

    // fetchThreads should be called again with search param
    await waitFor(() => {
      const calls = vi.mocked(forumService.fetchThreads).mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.search).toBe('watering');
    });
  });

  it('changes ordering when dropdown selection changes', async () => {
    const user = userEvent.setup();
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
    await user.selectOptions(orderingSelect, 'Most Viewed');

    // fetchThreads should be called with new ordering
    await waitFor(() => {
      const calls = vi.mocked(forumService.fetchThreads).mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.ordering).toBe('-view_count');
    });
  });

  it('displays active search filter with clear button', async () => {
    const user = userEvent.setup();
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage(['/forum/plant-care?search=watering']);

    await waitFor(() => {
      expect(screen.getByText(/Searching for:/i)).toBeInTheDocument();
    });

    expect(screen.getByText('watering')).toBeInTheDocument();

    const clearButton = screen.getByText('Clear');
    expect(clearButton).toBeInTheDocument();

    // Click clear button
    await user.click(clearButton);

    // Search should be cleared
    await waitFor(() => {
      const calls = vi.mocked(forumService.fetchThreads).mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.search).toBe('');
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
    expect(link).toHaveAttribute('href', '/forum/new-thread?category=plant-care');
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
