import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import NewThreadPage from './NewThreadPage';
import * as forumService from '../../services/forumService';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: vi.fn(), useSearchParams: vi.fn() };
});

vi.mock('../../services/forumService');

// TipTap is heavy + jsdom-hostile — stub it to a textarea that emits paragraph HTML.
vi.mock('../../components/forum/TipTapEditor', () => ({
  default: ({ onChange }: { onChange?: (html: string) => void }) => (
    <textarea aria-label="body" onChange={(e) => onChange?.(`<p>${e.target.value}</p>`)} />
  ),
}));

let mockNavigate: ReturnType<typeof vi.fn>;

function renderPage() {
  return render(
    <MemoryRouter>
      <NewThreadPage />
    </MemoryRouter>
  );
}

describe('NewThreadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockNavigate = vi.fn();
    vi.mocked(ReactRouter.useNavigate).mockReturnValue(
      mockNavigate as unknown as ReturnType<typeof ReactRouter.useNavigate>
    );
    vi.mocked(ReactRouter.useSearchParams).mockReturnValue([
      new URLSearchParams('category=3-plant-care'),
      vi.fn(),
    ]);
    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue({
      id: '3',
      name: 'Plant Care',
      slug: 'plant-care',
      created_at: '',
    });
  });

  it('sets a descriptive document title (H9)', async () => {
    renderPage();
    await waitFor(() => expect(document.title).toContain('Start a New Thread'));
  });

  it('published topic → navigates into the new thread', async () => {
    vi.spyOn(forumService, 'createThread').mockResolvedValue({
      id: '12',
      slug: 'my-topic',
      status: 'published',
    });
    renderPage();
    await screen.findByText('Plant Care');
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith('/forum/3-plant-care/12-my-topic')
    );
  });

  it('pending topic → moderation notice, navigates to the board (not into the pending topic)', async () => {
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(forumService, 'createThread').mockResolvedValue({
      id: '12',
      slug: 'my-topic',
      status: 'pending',
    });
    renderPage();
    await screen.findByText('Plant Care');
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/forum/3-plant-care'));
    expect(forumService.createThread).toHaveBeenCalledWith({
      boardSlug: 'plant-care',
      title: 'My Topic',
      content: '<p>hello</p>',
    });
  });

  it('blocks submit until both title and body are filled', async () => {
    renderPage();
    await screen.findByText('Plant Care');
    expect(screen.getByRole('button', { name: /post|create|submit/i })).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    expect(screen.getByRole('button', { name: /post|create|submit/i })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    expect(screen.getByRole('button', { name: /post|create|submit/i })).toBeEnabled();
  });
});
