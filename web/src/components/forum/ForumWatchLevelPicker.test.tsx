import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ForumWatchLevelPicker from './ForumWatchLevelPicker';
import { WATCH_LEVEL_OPTIONS } from '../../utils/forumDisplay';
import * as forumService from '../../services/forumService';

vi.mock('../../services/forumService');

describe('ForumWatchLevelPicker (todo 672)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('offers the four levels plus Normal and shows the stored one', () => {
    render(<ForumWatchLevelPicker slug="ferns" level="watching_first_post" />);
    const select = screen.getByLabelText('Notifications');
    expect(select).toHaveValue('watching_first_post');
    expect(WATCH_LEVEL_OPTIONS.map((o) => o.value)).toEqual([
      '',
      'watching',
      'watching_first_post',
      'tracking',
      'muted',
    ]);
  });

  it('saves a new level and reports it', async () => {
    vi.mocked(forumService.setForumWatchLevel).mockResolvedValue('muted');
    const onChange = vi.fn();
    render(<ForumWatchLevelPicker slug="ferns" level={null} onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText('Notifications'), 'muted');

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('muted'));
    expect(forumService.setForumWatchLevel).toHaveBeenCalledWith('ferns', 'muted');
    expect(screen.getByLabelText('Notifications')).toHaveValue('muted');
  });

  it('clears the level with Normal', async () => {
    vi.mocked(forumService.setForumWatchLevel).mockResolvedValue(null);
    render(<ForumWatchLevelPicker slug="ferns" level="tracking" />);
    await userEvent.selectOptions(screen.getByLabelText('Notifications'), '');
    await waitFor(() =>
      expect(forumService.setForumWatchLevel).toHaveBeenCalledWith('ferns', null)
    );
    expect(screen.getByLabelText('Notifications')).toHaveValue('');
  });

  it('goes back to the stored level when the save fails', async () => {
    vi.mocked(forumService.setForumWatchLevel).mockRejectedValue(new Error('down'));
    render(<ForumWatchLevelPicker slug="ferns" level="tracking" />);
    await userEvent.selectOptions(screen.getByLabelText('Notifications'), 'watching');
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save');
    expect(screen.getByLabelText('Notifications')).toHaveValue('tracking');
  });
});
