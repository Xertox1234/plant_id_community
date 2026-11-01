import { useState } from 'react';
import { setForumWatchLevel } from '../../services/forumService';
import { logger } from '../../utils/logger';
import { WATCH_LEVEL_OPTIONS } from '../../utils/forumDisplay';
import type { ForumWatchLevel } from '@/types';

interface ForumWatchLevelPickerProps {
  slug: string;
  level: ForumWatchLevel | null;
  /** Called with the stored level after a save succeeds. */
  onChange?: (level: ForumWatchLevel | null) => void;
}

/**
 * The signed-in member's watch level on one forum (todo 672). Saves on
 * change; a failed save goes back to the stored level and says so.
 */
export default function ForumWatchLevelPicker({
  slug,
  level,
  onChange,
}: ForumWatchLevelPickerProps) {
  const [value, setValue] = useState<ForumWatchLevel | ''>(level ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (next: ForumWatchLevel | '') => {
    const previous = value;
    setValue(next);
    setSaving(true);
    setError(null);
    try {
      const stored = await setForumWatchLevel(slug, next === '' ? null : next);
      setValue(stored ?? '');
      onChange?.(stored);
    } catch (err) {
      logger.error('Error saving forum watch level', {
        component: 'ForumWatchLevelPicker',
        error: err,
      });
      setValue(previous);
      setError('Could not save. Try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={`watch-level-${slug}`} className="gt-label">
        Notifications
      </label>
      <select
        id={`watch-level-${slug}`}
        value={value}
        disabled={saving}
        onChange={(e) => save(e.target.value as ForumWatchLevel | '')}
        className="min-h-11 rounded-pill border border-line bg-surface-2/60 px-4 py-2 text-body-sm text-ink focus:ring-2 focus:ring-secondary focus:outline-none"
      >
        {WATCH_LEVEL_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
    </div>
  );
}
