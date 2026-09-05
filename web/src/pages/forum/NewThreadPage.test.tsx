import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import NewThreadPage from './NewThreadPage';
import { AnnouncerProvider } from '../../contexts/AnnouncerContext';
import { useAuth } from '../../contexts/AuthContext';
import * as forumService from '../../services/forumService';
import { draftKey, saveDraft, loadDraft } from '../../utils/forumDrafts';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: vi.fn(), useSearchParams: vi.fn() };
});

vi.mock('../../services/forumService');

vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));

// Defense-in-depth (todo 297): handleSubmit calls revalidateIdentity() after
// every create (published or pending). Resolving to the SAME identity
// `user` below means no drift is detected, preserving every existing
// test's navigate-on-success assertions.
const mockAuth = () =>
  ({
    user: { id: 1, username: 'test-user' },
    isAuthenticated: true,
    revalidateIdentity: vi.fn().mockResolvedValue({ id: 1, username: 'test-user' }),
  }) as unknown as ReturnType<typeof useAuth>;

// TipTap is heavy + jsdom-hostile — stub it to a textarea that emits paragraph HTML.
// `content` rides through as defaultValue so a restored draft is observable (M3).
vi.mock('../../components/forum/TipTapEditor', () => ({
  default: ({ content, onChange }: { content?: string; onChange?: (html: string) => void }) => (
    <textarea
      aria-label="body"
      defaultValue={content}
      onChange={(e) => onChange?.(`<p>${e.target.value}</p>`)}
    />
  ),
}));

let mockNavigate: ReturnType<typeof vi.fn>;

function renderPage() {
  return render(
    <MemoryRouter>
      <AnnouncerProvider>
        <NewThreadPage />
      </AnnouncerProvider>
    </MemoryRouter>
  );
}

describe('NewThreadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockNavigate = vi.fn();
    vi.mocked(useAuth).mockReturnValue(mockAuth());
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

  // Defense-in-depth (todo 297): the create already succeeded under whatever
  // identity the cookie carried by the time it landed — this can't be
  // prevented, only detected and disclosed instead of silently navigating
  // as if the ORIGINAL user posted it.
  it('shows an identity-drift notice instead of auto-navigating when the acting identity changed mid-submit', async () => {
    vi.spyOn(forumService, 'createThread').mockResolvedValue({
      id: '12',
      slug: 'my-topic',
      status: 'published',
    });
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: 'test-user' },
      isAuthenticated: true,
      revalidateIdentity: vi.fn().mockResolvedValue({ id: 2, username: 'someone-else' }),
    } as unknown as ReturnType<typeof useAuth>);

    renderPage();
    await screen.findByText('Plant Care');
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

    await screen.findByRole('heading', { name: /session changed/i });
    expect(screen.getByText(/posted as someone-else/i)).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: /view the topic/i })).toHaveAttribute(
      'href',
      '/forum/3-plant-care/12-my-topic'
    );
  });

  // A pending (untrusted-author) topic has no live URL yet — the drift
  // notice must not link into it, and must say it's pending, not published.
  it('shows an identity-drift notice with no live link when the drifted create was pending moderation', async () => {
    vi.spyOn(forumService, 'createThread').mockResolvedValue({
      id: '12',
      slug: 'my-topic',
      status: 'pending',
    });
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: 'test-user' },
      isAuthenticated: true,
      revalidateIdentity: vi.fn().mockResolvedValue({ id: 2, username: 'someone-else' }),
    } as unknown as ReturnType<typeof useAuth>);

    renderPage();
    await screen.findByText('Plant Care');
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

    await screen.findByRole('heading', { name: /session changed/i });
    expect(screen.getByText(/posted as someone-else/i)).toBeInTheDocument();
    expect(screen.getByText(/awaiting moderation/i)).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: /back to plant care/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /view the topic/i })).not.toBeInTheDocument();
  });

  it('announces a failed submit through the persistent live region (audit M4)', async () => {
    vi.spyOn(forumService, 'createThread').mockRejectedValue(new Error('Failed to create thread'));
    renderPage();
    await screen.findByText('Plant Care');
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

    // Both the banner and the announcer region carry the text.
    await screen.findAllByText('Failed to create thread');
    // The banner is conditionally mounted (never announced on its own); the
    // assertive announcer region carries the failure.
    await waitFor(() =>
      expect(document.querySelector('[data-announcer="assertive"]')).toHaveTextContent(
        'Failed to create thread'
      )
    );
  });

  it('a passive account swap empties the form and its stored draft (code review, L4)', async () => {
    const { rerender } = renderPage();
    await screen.findByText('Plant Care');
    await userEvent.type(screen.getByLabelText(/title/i), 'Account A title');
    await userEvent.type(screen.getByLabelText('body'), 'account A body');
    await waitFor(() =>
      expect(sessionStorage.getItem('forum-draft:new-thread:3-plant-care')).toContain(
        'Account A title'
      )
    );

    // A focus revalidation found another account's cookie: same page
    // instance, new identity.
    vi.mocked(useAuth).mockReturnValue({
      ...mockAuth(),
      user: { id: 2, username: 'someone-else' },
    } as unknown as ReturnType<typeof useAuth>);
    rerender(
      <MemoryRouter>
        <AnnouncerProvider>
          <NewThreadPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByLabelText(/title/i)).toHaveValue(''));
    expect(screen.getByLabelText('body')).toHaveValue('');
    expect(sessionStorage.getItem('forum-draft:new-thread:3-plant-care')).toBeNull();
  });

  it('pending topic → on-page moderation confirmation, no native alert, no navigation into it (M24)', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
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

    // A styled on-page confirmation replaces the old window.alert; we do NOT
    // navigate into the pending (live=False) topic — it would 404.
    await screen.findByRole('heading', { name: /awaiting moderation/i });
    expect(alertSpy).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: /back to plant care/i })).toBeInTheDocument();
    expect(forumService.createThread).toHaveBeenCalledWith({
      boardSlug: 'plant-care',
      title: 'My Topic',
      content: '<p>hello</p>',
      tags: [],
    });
  });

  describe('poll composer (audit M8)', () => {
    it('sends no poll key at all when the toggle is off', async () => {
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

      await waitFor(() => expect(forumService.createThread).toHaveBeenCalled());
      // The ordinary compose payload must be untouched by this feature.
      expect(forumService.createThread).toHaveBeenCalledWith(
        expect.not.objectContaining({ poll: expect.anything() })
      );
    });

    it('sends the question and options when the toggle is on', async () => {
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderPage();
      await screen.findByText('Plant Care');
      await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('checkbox', { name: /add a poll/i }));
      await userEvent.type(screen.getByLabelText(/poll question/i), 'Best soil?');
      await userEvent.type(screen.getByLabelText('Poll option 1'), 'Peat');
      await userEvent.type(screen.getByLabelText('Poll option 2'), 'Coir');
      await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

      await waitFor(() => expect(forumService.createThread).toHaveBeenCalled());
      expect(forumService.createThread).toHaveBeenCalledWith(
        expect.objectContaining({
          poll: { question: 'Best soil?', options: ['Peat', 'Coir'] },
        })
      );
    });

    it('sends max_choices only when it is above the single-choice default (todo 349)', async () => {
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderPage();
      await screen.findByText('Plant Care');
      await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('checkbox', { name: /add a poll/i }));
      await userEvent.type(screen.getByLabelText(/poll question/i), 'Pests seen?');
      await userEvent.type(screen.getByLabelText('Poll option 1'), 'Aphids');
      await userEvent.type(screen.getByLabelText('Poll option 2'), 'Mites');

      // The select only offers 1..filled options, so "3 of 2" cannot be
      // chosen; and blanking an option AFTER choosing 3 clamps the value
      // down with the list (review: a controlled value matching no option
      // would gate Post invisibly), so the payload carries the clamped 2.
      const choices = screen.getByLabelText(/choices per voter/i);
      expect(screen.queryByRole('option', { name: '3' })).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: /add option/i }));
      await userEvent.type(screen.getByLabelText('Poll option 3'), 'Scale');
      await userEvent.selectOptions(choices, '3');
      expect(choices).toHaveValue('3');
      await userEvent.clear(screen.getByLabelText('Poll option 3'));
      expect(choices).toHaveValue('2');
      await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

      await waitFor(() => expect(forumService.createThread).toHaveBeenCalled());
      expect(forumService.createThread).toHaveBeenCalledWith(
        expect.objectContaining({
          poll: { question: 'Pests seen?', options: ['Aphids', 'Mites', ''], max_choices: 2 },
        })
      );
    });

    it('disables Post when the poll toggle is on but the poll is left blank, so an otherwise-valid topic cannot 400 on an empty poll', async () => {
      vi.spyOn(forumService, 'createThread');
      renderPage();
      await screen.findByText('Plant Care');
      await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('checkbox', { name: /add a poll/i }));

      // Title + body are valid and the poll is untouched (its default two
      // blank option rows) — without folding poll validity into canSubmit,
      // this was clickable and took the WHOLE topic down with a 400.
      expect(screen.getByRole('button', { name: /post|create|submit/i })).toBeDisabled();
      await userEvent.type(screen.getByLabelText(/poll question/i), 'Best soil?');
      await userEvent.type(screen.getByLabelText('Poll option 1'), 'Peat');
      // Question filled but still fewer than two non-blank options — still
      // an invalid poll, still disabled.
      expect(screen.getByRole('button', { name: /post|create|submit/i })).toBeDisabled();

      await userEvent.type(screen.getByLabelText('Poll option 2'), 'Coir');
      expect(screen.getByRole('button', { name: /post|create|submit/i })).not.toBeDisabled();
      expect(forumService.createThread).not.toHaveBeenCalled();
    });

    it('adds an option row on demand, up to the server maximum', async () => {
      renderPage();
      await screen.findByText('Plant Care');
      await userEvent.click(screen.getByRole('checkbox', { name: /add a poll/i }));

      // Starts at the minimum viable poll: two rows.
      expect(screen.getAllByPlaceholderText(/^Option \d+$/)).toHaveLength(2);
      await userEvent.click(screen.getByRole('button', { name: /add option/i }));
      expect(screen.getAllByPlaceholderText(/^Option \d+$/)).toHaveLength(3);

      // Click up to the cap; the affordance then disappears rather than
      // offering a row the server would reject.
      for (let i = 3; i < 10; i += 1) {
        await userEvent.click(screen.getByRole('button', { name: /add option/i }));
      }
      expect(screen.getAllByPlaceholderText(/^Option \d+$/)).toHaveLength(10);
      expect(screen.queryByRole('button', { name: /add option/i })).not.toBeInTheDocument();
    });

    it('hides the poll fields until the toggle is switched on', async () => {
      renderPage();
      await screen.findByText('Plant Care');

      expect(screen.queryByLabelText(/poll question/i)).not.toBeInTheDocument();
    });

    it('converts a filled-in close time from local wall time to an ISO UTC string (todo 320 #7)', async () => {
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderPage();
      await screen.findByText('Plant Care');
      await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('checkbox', { name: /add a poll/i }));
      await userEvent.type(screen.getByLabelText(/poll question/i), 'Best soil?');
      await userEvent.type(screen.getByLabelText('Poll option 1'), 'Peat');
      await userEvent.type(screen.getByLabelText('Poll option 2'), 'Coir');
      const localValue = '2027-06-15T10:30';
      await userEvent.type(screen.getByLabelText(/closes/i), localValue);
      await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

      await waitFor(() => expect(forumService.createThread).toHaveBeenCalled());
      expect(forumService.createThread).toHaveBeenCalledWith(
        expect.objectContaining({
          poll: expect.objectContaining({
            // Not the raw local-time string: `datetime-local` carries no
            // timezone, so it must go through Date() before the server
            // (which stores/compares in UTC) sees it.
            closes_at: new Date(localValue).toISOString(),
          }),
        })
      );
    });

    it('omits closes_at entirely when the close-time field is left blank', async () => {
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderPage();
      await screen.findByText('Plant Care');
      await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('checkbox', { name: /add a poll/i }));
      await userEvent.type(screen.getByLabelText(/poll question/i), 'Best soil?');
      await userEvent.type(screen.getByLabelText('Poll option 1'), 'Peat');
      await userEvent.type(screen.getByLabelText('Poll option 2'), 'Coir');
      await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

      await waitFor(() => expect(forumService.createThread).toHaveBeenCalled());
      expect(forumService.createThread).toHaveBeenCalledWith(
        expect.objectContaining({
          poll: { question: 'Best soil?', options: ['Peat', 'Coir'] },
        })
      );
    });
  });

  it('offers a board picker when no ?category= is supplied, and lets you pick one (L4)', async () => {
    vi.mocked(ReactRouter.useSearchParams).mockReturnValue([new URLSearchParams(''), vi.fn()]);
    vi.spyOn(forumService, 'fetchCategories').mockResolvedValue([
      { id: '3', name: 'Plant Care', slug: 'plant-care', created_at: '' },
      { id: '4', name: 'Pests', slug: 'pests', created_at: '' },
    ]);
    vi.spyOn(forumService, 'createThread').mockResolvedValue({
      id: '12',
      slug: 'my-topic',
      status: 'published',
    });

    renderPage();

    // Picker appears (no dead-end error); submit is disabled until a board is chosen.
    const picker = await screen.findByLabelText('Board');
    expect(screen.getByRole('button', { name: /post|create|submit/i })).toBeDisabled();

    await userEvent.selectOptions(picker, '3');
    await userEvent.type(screen.getByLabelText(/title/i), 'My Topic');
    await userEvent.type(screen.getByLabelText('body'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));

    await waitFor(() =>
      expect(forumService.createThread).toHaveBeenCalledWith({
        boardSlug: 'plant-care',
        title: 'My Topic',
        content: '<p>hello</p>',
        tags: [],
      })
    );
  });

  it('restores a saved composer draft, then clears it once posted (M3)', async () => {
    // Wave 1 (#473) made composer state survive a refresh/back-nav within the
    // tab: the draft is written to sessionStorage on every keystroke and read
    // back on mount. This is the page-level proof — forumDrafts.test.ts covers
    // only the storage helper.
    const key = draftKey('new-thread', '3-plant-care');
    saveDraft(key, JSON.stringify({ title: 'Half-written topic', body: '<p>saved body</p>' }));
    vi.spyOn(forumService, 'createThread').mockResolvedValue({
      id: '12',
      slug: 'my-topic',
      status: 'published',
    });

    renderPage();
    await screen.findByText('Plant Care');

    expect(screen.getByLabelText(/title/i)).toHaveValue('Half-written topic');
    expect(screen.getByLabelText('body')).toHaveValue('<p>saved body</p>');

    // The restored values are real component state, not just rendered defaults:
    // posting without retyping sends them verbatim.
    await userEvent.click(screen.getByRole('button', { name: /post|create|submit/i }));
    await waitFor(() =>
      expect(forumService.createThread).toHaveBeenCalledWith({
        boardSlug: 'plant-care',
        title: 'Half-written topic',
        content: '<p>saved body</p>',
        tags: [],
      })
    );
    // Posted drafts must not resurrect on the next visit.
    expect(loadDraft(key)).toBeNull();
  });

  describe('"Ask the community" handoff (audit M6)', () => {
    const HANDOFF = {
      identification: {
        image_id: 42,
        provider: 'plant_id',
        candidates: [
          { name: 'Swiss cheese plant', scientific_name: 'Monstera deliciosa', confidence: 0.82 },
        ],
      },
      identificationPreviewUrl: 'http://localhost:8000/media/images/plant.jpg',
    };

    function renderWithHandoff(state: unknown) {
      return render(
        <MemoryRouter initialEntries={[{ pathname: '/forum/new-thread', state }]}>
          <AnnouncerProvider>
            <NewThreadPage />
          </AnnouncerProvider>
        </MemoryRouter>
      );
    }

    it('shows the attachment and sends it with the create', async () => {
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderWithHandoff(HANDOFF);
      await screen.findByText('Plant Care');

      // Visible before the user posts — it carries their photo, so attaching
      // it silently would be the wrong default.
      expect(screen.getByText(/identification attached/i)).toBeInTheDocument();
      expect(screen.getByText(/Swiss cheese plant \(82%\)/)).toBeInTheDocument();
      expect(screen.getByRole('img')).toHaveAttribute('src', HANDOFF.identificationPreviewUrl);

      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('button', { name: /post thread/i }));

      await waitFor(() =>
        expect(forumService.createThread).toHaveBeenCalledWith({
          boardSlug: 'plant-care',
          title: 'Is this Swiss cheese plant?',
          content: '<p>hello</p>',
          tags: [],
          identification: HANDOFF.identification,
        })
      );
    });

    it('completes the real flagship flow: no ?category=, pick a board, post', async () => {
      // The entry point navigates to a BARE /forum/new-thread — no
      // ?category= — so the live path is the board-picker one (L4), not the
      // pre-selected board every other test here mocks.
      vi.mocked(ReactRouter.useSearchParams).mockReturnValue([new URLSearchParams(''), vi.fn()]);
      vi.spyOn(forumService, 'fetchCategories').mockResolvedValue([
        { id: '3', name: 'Plant Care', slug: 'plant-care', created_at: '' },
      ]);
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderWithHandoff(HANDOFF);

      const picker = await screen.findByLabelText('Board');
      expect(screen.getByText(/identification attached/i)).toBeInTheDocument();

      await userEvent.selectOptions(picker, '3');
      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('button', { name: /post thread/i }));

      await waitFor(() =>
        expect(forumService.createThread).toHaveBeenCalledWith({
          boardSlug: 'plant-care',
          title: 'Is this Swiss cheese plant?',
          content: '<p>hello</p>',
          tags: [],
          identification: HANDOFF.identification,
        })
      );
    });

    it('suggests a title, which a saved draft still overrides', async () => {
      saveDraft(
        draftKey('new-thread', '3-plant-care'),
        JSON.stringify({ title: 'My own wording' })
      );
      renderWithHandoff(HANDOFF);
      await screen.findByText('Plant Care');

      expect(screen.getByLabelText(/title/i)).toHaveValue('My own wording');
    });

    it('lets the user drop the attachment before posting', async () => {
      vi.spyOn(forumService, 'createThread').mockResolvedValue({
        id: '12',
        slug: 'my-topic',
        status: 'published',
      });
      renderWithHandoff(HANDOFF);
      await screen.findByText('Plant Care');

      await userEvent.click(screen.getByRole('button', { name: /remove/i }));
      expect(screen.queryByText(/identification attached/i)).not.toBeInTheDocument();

      await userEvent.type(screen.getByLabelText('body'), 'hello');
      await userEvent.click(screen.getByRole('button', { name: /post thread/i }));

      await waitFor(() =>
        expect(forumService.createThread).toHaveBeenCalledWith(
          expect.not.objectContaining({ identification: expect.anything() })
        )
      );
    });

    it('degrades to a plain composer when there is no handoff (reload, direct visit)', async () => {
      renderWithHandoff(null);
      await screen.findByText('Plant Care');

      expect(screen.queryByText(/identification attached/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/title/i)).toHaveValue('');
    });

    it('ignores a malformed handoff rather than crashing mid-compose', async () => {
      renderWithHandoff({ identification: { candidates: 'not-an-array' } });
      await screen.findByText('Plant Care');

      expect(screen.queryByText(/identification attached/i)).not.toBeInTheDocument();
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
