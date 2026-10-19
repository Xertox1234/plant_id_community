import Eyebrow from '../ui/Eyebrow';
import { useLiveUpdatesEnabled } from '../../utils/liveUpdatesStore';

/**
 * "Live updates" for THIS browser (forum live replies, slice 3). Stored on the
 * device, not the account (owner decision O8); on by default. Off, an open
 * topic closes its socket at once and falls back to the 30-second check.
 */
export default function LiveUpdatesSection() {
  const [enabled, setEnabled] = useLiveUpdatesEnabled();
  return (
    <section className="p-screen" aria-label="Live updates">
      <Eyebrow>Live updates</Eyebrow>
      <label className="mt-3 flex min-h-11 items-start gap-3">
        <input
          type="checkbox"
          role="switch"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          aria-describedby="live-updates-detail"
          className="mt-1 h-5 w-5 accent-primary focus:ring-2 focus:ring-secondary focus:outline-none"
        />
        <span>
          <span className="block text-sm font-medium text-ink">Live updates</span>
          <span id="live-updates-detail" className="block text-sm text-ink-3">
            Show new replies, edits and deletes in an open topic as they happen, in this browser.
            Off, topics check for new replies every 30 seconds.
          </span>
        </span>
      </label>
    </section>
  );
}
