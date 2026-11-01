import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ForumUnlockForm from './ForumUnlockForm';
import * as forumService from '../../services/forumService';

vi.mock('../../services/forumService', async () => {
  const actual = await vi.importActual<typeof import('../../services/forumService')>(
    '../../services/forumService'
  );
  return { ...actual, unlockForum: vi.fn() };
});

// pragma: allowlist nextline secret
async function submit(password = 'secret') {
  await userEvent.type(screen.getByLabelText('Password'), password);
  await userEvent.click(screen.getByRole('button', { name: 'Unlock' }));
}

describe('ForumUnlockForm (todo 680)', () => {
  beforeEach(() => {
    vi.mocked(forumService.unlockForum).mockReset();
  });

  it('calls onUnlocked after a right password', async () => {
    vi.mocked(forumService.unlockForum).mockResolvedValue(undefined);
    const onUnlocked = vi.fn();
    render(<ForumUnlockForm slug="club" onUnlocked={onUnlocked} />);

    await submit();

    expect(forumService.unlockForum).toHaveBeenCalledWith('club', 'secret');
    expect(onUnlocked).toHaveBeenCalledTimes(1);
  });

  it.each([
    [400, 'That password is not right.'],
    [429, 'Too many wrong passwords. Try again later.'],
    [401, 'Sign in to open this forum.'],
    [403, 'Sign in to open this forum.'],
    [500, 'Could not unlock the forum. Try again.'],
  ])('a %i says "%s" and stays locked', async (status, message) => {
    vi.mocked(forumService.unlockForum).mockRejectedValue(
      new forumService.ForumApiError('nope', status)
    );
    const onUnlocked = vi.fn();
    render(<ForumUnlockForm slug="club" onUnlocked={onUnlocked} />);

    await submit();

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(onUnlocked).not.toHaveBeenCalled();
  });

  it('does not submit an empty password', async () => {
    render(<ForumUnlockForm slug="club" onUnlocked={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: 'Unlock' }));

    expect(forumService.unlockForum).not.toHaveBeenCalled();
  });
});
