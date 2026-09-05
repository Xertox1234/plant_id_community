import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NewGroupConversationForm from './NewGroupConversationForm';
import * as messageService from '../../services/messageService';
import * as forumService from '../../services/forumService';

vi.mock('../../services/messageService', async () => {
  const actual = await vi.importActual<typeof import('../../services/messageService')>(
    '../../services/messageService'
  );
  return { ...actual, createGroupConversation: vi.fn() };
});
vi.mock('../../services/forumService', async () => {
  const actual = await vi.importActual<typeof import('../../services/forumService')>(
    '../../services/forumService'
  );
  return { ...actual, searchForumUsers: vi.fn() };
});
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, user: { id: 1, username: 'me' } }),
}));

const onCreated = vi.fn();
const onCancel = vi.fn();

function renderForm() {
  return render(<NewGroupConversationForm onCreated={onCreated} onCancel={onCancel} />);
}

// The chip text sits on the span wrapping the icon-only Remove button.
const chips = () =>
  screen.queryAllByRole('button', { name: /^Remove / }).map((b) => b.closest('span')?.textContent);
const notice = () => {
  const form = screen.getByRole('form', { name: 'New group' });
  const regions = form.querySelectorAll('[aria-live="polite"]');
  return regions[regions.length - 1];
};

describe('NewGroupConversationForm (todo 350)', () => {
  beforeEach(() => {
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([]);
    vi.mocked(messageService.createGroupConversation).mockResolvedValue({
      id: 12,
      kind: 'group',
      title: 't',
      other_participant: null,
      participants: [],
      participant_count: 3,
      created_by: null,
      can_manage: true,
      created_at: '',
      last_message_at: '',
      unread_count: 0,
      last_message: null,
    });
  });

  it('adds a chip on Enter and on a comma, strips a leading @, and Backspace on an empty box removes the last chip', async () => {
    renderForm();
    const box = screen.getByLabelText('Members');
    await userEvent.type(box, '@ada{Enter}grace,');
    expect(chips()).toEqual(['@ada', '@grace']);
    expect(box).toHaveValue('');

    await userEvent.type(box, '{Backspace}');
    expect(chips()).toEqual(['@ada']);
    // Backspace with text in the box edits the text, never a chip.
    await userEvent.type(box, 'li{Backspace}');
    expect(chips()).toEqual(['@ada']);
    expect(box).toHaveValue('l');

    // The chip's own button removes it too and hands focus back to the box.
    await userEvent.click(screen.getByRole('button', { name: 'Remove ada' }));
    expect(chips()).toEqual([]);
    expect(box).toHaveFocus();
  });

  it('refuses you and duplicates (case-insensitively) with a reason in the live region', async () => {
    renderForm();
    const box = screen.getByLabelText('Members');
    expect(notice()).toBeEmptyDOMElement();

    await userEvent.type(box, 'me{Enter}');
    expect(notice()).toHaveTextContent(
      "You're in every group you create — no need to add yourself."
    );
    expect(chips()).toEqual([]);
    expect(box).toHaveValue('me');

    await userEvent.clear(box);
    await userEvent.type(box, 'ada{Enter}ADA{Enter}');
    expect(notice()).toHaveTextContent('@ADA is already in the list.');
    expect(chips()).toEqual(['@ada']);
  });

  it('suggests members from the user search after the debounce, hides chosen names and you, and a click adds the chip', async () => {
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([
      { username: 'ada', display_name: 'Ada L.' },
      { username: 'adam', display_name: '' },
      { username: 'me', display_name: 'Me' },
    ]);
    renderForm();
    const box = screen.getByLabelText('Members');
    await userEvent.type(box, 'adam{Enter}');
    expect(forumService.searchForumUsers).not.toHaveBeenCalled(); // "a" alone is below the minimum

    await userEvent.type(box, 'ad');
    const suggestion = await screen.findByRole('button', { name: 'Add ada' });
    expect(forumService.searchForumUsers).toHaveBeenLastCalledWith('ad', expect.any(AbortSignal));
    const list = screen.getByRole('listbox', { name: 'Suggested members' });
    expect(within(list).getAllByRole('button')).toHaveLength(1);
    expect(suggestion).toHaveTextContent('@ada');
    expect(suggestion).toHaveTextContent('Ada L.');
    expect(screen.queryByRole('button', { name: 'Add adam' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add me' })).not.toBeInTheDocument();

    await userEvent.click(suggestion);
    expect(chips()).toEqual(['@adam', '@ada']);
    expect(box).toHaveValue('');
    expect(box).toHaveFocus();
    await waitFor(() =>
      expect(screen.queryByRole('listbox', { name: 'Suggested members' })).not.toBeInTheDocument()
    );
  });

  it('moves through the suggestions with the arrow keys, takes the highlighted one on Enter, and closes on Escape', async () => {
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([
      { username: 'ada', display_name: 'Ada L.' },
      { username: 'adele', display_name: '' },
    ]);
    renderForm();
    const box = screen.getByLabelText('Members');
    await userEvent.type(box, 'ad');

    const listbox = await screen.findByRole('listbox', { name: 'Suggested members' });
    const options = within(listbox).getAllByRole('option');
    expect(options).toHaveLength(2);
    await userEvent.keyboard('{ArrowDown}{ArrowDown}');
    expect(options[1]).toHaveAttribute('aria-selected', 'true');
    expect(box).toHaveAttribute('aria-activedescendant', options[1].id);
    await userEvent.keyboard('{ArrowUp}');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');

    // Enter takes the HIGHLIGHTED suggestion, not the typed text.
    await userEvent.keyboard('{ArrowDown}{Enter}');
    expect(chips()).toEqual(['@adele']);
    expect(box).toHaveValue('');

    // Escape closes the list without submitting the form.
    await userEvent.type(box, 'ad');
    await screen.findByRole('listbox', { name: 'Suggested members' });
    await userEvent.keyboard('{Escape}');
    await waitFor(() =>
      expect(screen.queryByRole('listbox', { name: 'Suggested members' })).not.toBeInTheDocument()
    );
    expect(messageService.createGroupConversation).not.toHaveBeenCalled();
  });

  it('searches only once the query passes the minimum length, however long the debounce waits', async () => {
    // Waiting past the debounce on the REAL clock: the previous coverage
    // passed only because each keystroke cancelled the pending timer, never
    // because of the length guard (react review). Fake timers deadlock this
    // suite's other userEvent flows, so the wait is a real one.
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([]);
    renderForm();
    const box = screen.getByLabelText('Members');

    await userEvent.type(box, 'a');
    await new Promise((resolve) => setTimeout(resolve, 500));
    expect(forumService.searchForumUsers).not.toHaveBeenCalled();

    await userEvent.type(box, 'd');
    await waitFor(() => expect(forumService.searchForumUsers).toHaveBeenCalledTimes(1));
    expect(forumService.searchForumUsers).toHaveBeenLastCalledWith('ad', expect.any(AbortSignal));
  });

  it('a failed user search shows no suggestions and never blocks typing', async () => {
    vi.mocked(forumService.searchForumUsers).mockRejectedValue(new Error('HTTP 429'));
    renderForm();
    const box = screen.getByLabelText('Members');
    await userEvent.type(box, 'ad');
    await waitFor(() => expect(forumService.searchForumUsers).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByRole('listbox', { name: 'Suggested members' })).not.toBeInTheDocument();
    await userEvent.type(box, 'a{Enter}');
    expect(chips()).toEqual(['@ada']);
  });

  it('the seventh chip caps the picker: the box stays focusable but aria-disabled, with the limit hint', async () => {
    renderForm();
    const box = screen.getByLabelText('Members');
    expect(box).toHaveAccessibleDescription(
      '2–7 members besides you. Press Enter or a comma after each username.'
    );
    await userEvent.type(box, 'u1,u2,u3,u4,u5,u6,u7,');
    expect(chips()).toHaveLength(7);
    expect(box).toHaveAttribute('aria-disabled', 'true');
    expect(box).toHaveAttribute('readonly');
    expect(box).toHaveAccessibleDescription("That's the limit — 7 members besides you.");
    expect(box).toHaveFocus();

    await userEvent.type(box, 'u8{Enter}');
    expect(chips()).toHaveLength(7);
    expect(forumService.searchForumUsers).not.toHaveBeenCalled();

    // Dropping one reopens the box.
    await userEvent.click(screen.getByRole('button', { name: 'Remove u7' }));
    expect(box).not.toHaveAttribute('aria-disabled');
    await userEvent.type(box, 'u8{Enter}');
    expect(chips()).toEqual(['@u1', '@u2', '@u3', '@u4', '@u5', '@u6', '@u8']);
  });

  it('validates before posting — name, then at least two members, then the first message — and never calls the service early', async () => {
    renderForm();
    const create = screen.getByRole('button', { name: 'Create group' });

    await userEvent.click(create);
    expect(screen.getByText('Give the group a name.')).toBeInTheDocument();
    expect(screen.getByLabelText('Group name')).toHaveAttribute('aria-invalid', 'true');
    expect(messageService.createGroupConversation).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('Group name'), 'Seed swap');
    expect(screen.queryByText('Give the group a name.')).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}');
    await userEvent.click(create);
    expect(notice()).toHaveTextContent('Add at least 2 members besides you.');
    expect(messageService.createGroupConversation).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('Members'), 'grace{Enter}');
    await userEvent.click(create);
    expect(notice()).toHaveTextContent('Write the first message.');
    expect(messageService.createGroupConversation).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('First message'), 'hello');
    await userEvent.click(create);
    expect(messageService.createGroupConversation).toHaveBeenCalledWith({
      title: 'Seed swap',
      usernames: ['ada', 'grace'],
      body: 'hello',
    });
    await waitFor(() =>
      expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 12 }))
    );
    expect(notice()).toBeEmptyDOMElement();
  });

  it('a username still typed in the box is flushed into the members on submit', async () => {
    renderForm();
    await userEvent.type(screen.getByLabelText('Group name'), 'Seed swap');
    await userEvent.type(screen.getByLabelText('Members'), 'ada{Enter}grace');
    await userEvent.type(screen.getByLabelText('First message'), 'hello');
    await userEvent.click(screen.getByRole('button', { name: 'Create group' }));

    expect(messageService.createGroupConversation).toHaveBeenCalledWith({
      title: 'Seed swap',
      usernames: ['ada', 'grace'],
      body: 'hello',
    });
    expect(chips()).toEqual(['@ada', '@grace']);
    expect(screen.getByLabelText('Members')).toHaveValue('');
  });

  it('the title is capped at 80 characters and Cancel reports back', async () => {
    renderForm();
    expect(screen.getByLabelText('Group name')).toHaveAttribute('maxlength', '80');
    expect(screen.getByLabelText('First message')).toHaveAttribute('maxlength', '4000');
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
