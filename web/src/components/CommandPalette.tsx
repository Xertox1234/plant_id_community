import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, ScanSearch, Search, type LucideIcon } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import {
  fetchCategories,
  searchForum,
  searchForumUsers,
  type ForumUserSearchResult,
} from '../services/forumService';
import { categoryPath, threadPath, userProfilePath } from '../utils/forumUrls';
import { boardIdentity } from '../utils/forumTones';
import { useBodyScrollLock } from '../hooks/useBodyScrollLock';
import type { Category, Thread } from '../types/forum';

const MIN_QUERY_LENGTH = 2;
// CLAUDE.md gotcha: the debounce timer id lives in a ref, never useState —
// useState would re-render on every tick and recreate the callback.
const DEBOUNCE_MS = 250;
const RESULT_LIMIT = 5;

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

/** One activatable row, in the flat keyboard-navigation order. */
interface PaletteRow {
  id: string;
  to: string;
  label: string;
  secondary?: string;
  Icon?: LucideIcon;
}

/**
 * A search response tagged with the query that produced it. Rendering derives
 * the live `items` only when `q` still matches the current query — the single
 * fix for a class of staleness bugs (code review round 1, finding 1):
 * un-tagged results rendered under whatever query the user has since typed,
 * stayed in the keyboard-nav list after the JSX hid them once loading kicked
 * in (a DOM/aria-activedescendant mismatch), and a response for a
 * since-deleted (<2 char) query could resurrect rows for a query no longer
 * on screen. Binding results to `q` makes all three self-correct: a mismatch
 * against the CURRENT query always derives to empty, synchronously, with no
 * dependency on the loading/error flags.
 */
interface QueryResult<T> {
  q: string;
  items: T[];
}

/**
 * True for the DOMException `fetch()` (and `authenticatedFetch`, which
 * doesn't wrap it) rejects with when its request's AbortSignal fires — i.e.
 * a cancellation WE issued (a newer query superseding this one, or the
 * palette closing), never a real network/server failure.
 */
function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

/**
 * Cmd/Ctrl+K command palette (spec §8). Always mounted by AppShell — `open`
 * gates rendering internally so state (query, fetched boards) can reset
 * cleanly on every open without AppShell managing a mount/unmount lifecycle.
 */
export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  // Whether the user has explicitly moved the roving cursor (arrow keys or
  // mouse hover) since the query last changed. While false, the EFFECTIVE
  // selection is `defaultIndex` below, not this raw `activeIndex` — see the
  // `defaultIndex` comment for why (code review finding #4).
  const [hasNavigated, setHasNavigated] = useState(false);
  const [visible, setVisible] = useState(false);

  const [categories, setCategories] = useState<Category[]>([]);
  const categoriesFetchedRef = useRef(false);

  const [topicsResult, setTopicsResult] = useState<QueryResult<Thread> | null>(null);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [topicsError, setTopicsError] = useState(false);

  const [peopleResult, setPeopleResult] = useState<QueryResult<ForumUserSearchResult> | null>(null);
  const [peopleLoading, setPeopleLoading] = useState(false);
  const [peopleError, setPeopleError] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Monotonic request epoch — a response only lands if no newer query has
  // been issued since (same class as PR #537's unread-badge fix).
  const epochRef = useRef(0);
  // One AbortController per issued query. The epoch guard above already
  // drops a stale RESPONSE from ever reaching state, but it does nothing to
  // stop the request itself — without this, a fast typist fires a full
  // in-flight fetch per keystroke that runs to completion server-side for no
  // UI benefit (and counts against rate limits). Aborting the previous
  // controller before creating a new one is the actual cancellation.
  const searchAbortControllerRef = useRef<AbortController | null>(null);

  const trimmedQuery = query.trim();
  const showTopics = trimmedQuery.length >= MIN_QUERY_LENGTH;
  const showPeople = isAuthenticated && showTopics;

  // Reset to a clean slate on every open.
  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActiveIndex(0);
    setHasNavigated(false);
    setTopicsResult(null);
    setTopicsError(false);
    setTopicsLoading(false);
    setPeopleResult(null);
    setPeopleError(false);
    setPeopleLoading(false);
    // Invalidate any in-flight response from a previous session.
    epochRef.current++;
  }, [open]);

  // Boards for Quick actions — fetched once on first open, not on every reopen.
  useEffect(() => {
    if (!open || categoriesFetchedRef.current) return;
    categoriesFetchedRef.current = true;
    fetchCategories()
      .then(setCategories)
      .catch(() => {
        // Allow a retry on the next open — transient failure, not permanent.
        categoriesFetchedRef.current = false;
      });
  }, [open]);

  // Initial focus + focus return, in one effect so the trigger is always
  // captured BEFORE focus moves into the palette's own input — a separate
  // "capture" effect ordered after "focus the input" would record the input
  // itself as the thing to return focus to.
  useEffect(() => {
    if (open) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
      inputRef.current?.focus();
    } else if (previouslyFocusedRef.current) {
      previouslyFocusedRef.current.focus();
      previouslyFocusedRef.current = null;
    }
  }, [open]);

  // Escape closes the palette.
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Body scroll lock while open — shared, ref-counted with AppShell's mobile
  // drawer (see useBodyScrollLock) so the two compose correctly when both
  // are open at once.
  useBodyScrollLock(open);

  // Entrance transition — a class flip one frame after mount so the
  // fade/scale actually animates instead of snapping to its end state.
  useEffect(() => {
    if (!open) {
      setVisible(false);
      return;
    }
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [open]);

  // Abort any in-flight search when the palette closes or the component
  // unmounts. The cleanup below runs on EVERY `open` transition (so closing
  // aborts) and once more on unmount (React always runs the last render's
  // cleanup then) — CommandPalette is normally kept mounted by AppShell with
  // `open` gating render internally, but this covers a genuine unmount too
  // (e.g. a test rendering it standalone).
  useEffect(() => {
    return () => {
      searchAbortControllerRef.current?.abort();
    };
  }, [open]);

  // Debounced, epoch-guarded search. Cleaned up on every query change and on
  // unmount alike (the timer effect's cleanup always runs).
  useEffect(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);

    if (!showTopics) {
      setTopicsResult(null);
      setTopicsError(false);
      setTopicsLoading(false);
      setPeopleResult(null);
      setPeopleError(false);
      setPeopleLoading(false);
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      const epoch = ++epochRef.current;
      // Snapshot the query THIS request is for — captured once, here, so the
      // result can be tagged with the query that produced it even if
      // `trimmedQuery` (closed over below) has since moved on.
      const requestQuery = trimmedQuery;

      // Cancel the previous in-flight request (if any) before issuing this
      // one. The epoch guard below still stands as defense-in-depth against
      // a response landing after a newer query has already superseded it —
      // this only stops the REQUEST itself from running to completion.
      searchAbortControllerRef.current?.abort();
      const controller = new AbortController();
      searchAbortControllerRef.current = controller;

      // Clear any stale results BEFORE issuing the fetches. Without this, an
      // identical-retype (delete a char, retype it — same final query text)
      // re-fetches while `topicsResult`/`peopleResult` still carry the PRIOR
      // response tagged with that same query, so the q-tag guard alone can't
      // tell it's stale: `topics`/`people` would keep resolving to the old
      // rows, keeping them in `flatRows` (and reachable via
      // aria-activedescendant) even though the JSX hides them behind
      // "Searching…" while `*Loading` is true — an aria-orphan reference.
      setTopicsResult(null);
      setPeopleResult(null);

      setTopicsLoading(true);
      setTopicsError(false);
      searchForum({ q: requestQuery, signal: controller.signal })
        .then((res) => {
          if (epoch !== epochRef.current) return;
          setTopicsResult({ q: requestQuery, items: res.threads.slice(0, RESULT_LIMIT) });
        })
        .catch((err) => {
          if (epoch !== epochRef.current) return;
          // We aborted our own, now-superseded/closed request — not a real
          // failure. Must never surface as "Search is unavailable".
          if (isAbortError(err)) return;
          setTopicsResult({ q: requestQuery, items: [] });
          setTopicsError(true);
        })
        .finally(() => {
          if (epoch !== epochRef.current) return;
          setTopicsLoading(false);
        });

      if (isAuthenticated) {
        setPeopleLoading(true);
        setPeopleError(false);
        searchForumUsers(requestQuery, controller.signal)
          .then((res) => {
            if (epoch !== epochRef.current) return;
            setPeopleResult({ q: requestQuery, items: res.slice(0, RESULT_LIMIT) });
          })
          .catch((err) => {
            if (epoch !== epochRef.current) return;
            if (isAbortError(err)) return;
            setPeopleResult({ q: requestQuery, items: [] });
            setPeopleError(true);
          })
          .finally(() => {
            if (epoch !== epochRef.current) return;
            setPeopleLoading(false);
          });
      } else {
        setPeopleResult(null);
        setPeopleError(false);
        setPeopleLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [trimmedQuery, showTopics, isAuthenticated]);

  // Reset to "no explicit selection" whenever the query changes, so an
  // arrow-key choice from a previous query never carries over to a
  // different result set. `activeIndex` itself is inert while
  // `hasNavigated` is false — `defaultIndex` below governs what's actually
  // selected until the user arrows or hovers.
  useEffect(() => {
    setActiveIndex(0);
    setHasNavigated(false);
  }, [trimmedQuery]);

  // Derive the live results from the tagged response — a mismatch against
  // the CURRENT query (still in flight, superseded, or dropped below the
  // minimum length) always yields empty, synchronously, independent of the
  // loading/error flags. See the QueryResult doc comment above.
  const topics = useMemo(
    () => (topicsResult && topicsResult.q === trimmedQuery ? topicsResult.items : []),
    [topicsResult, trimmedQuery]
  );
  const people = useMemo(
    () => (peopleResult && peopleResult.q === trimmedQuery ? peopleResult.items : []),
    [peopleResult, trimmedQuery]
  );

  const quickActionRows = useMemo<PaletteRow[]>(() => {
    const rows: PaletteRow[] = [
      { id: 'qa-identify', to: '/identify', label: 'Identify a plant', Icon: ScanSearch },
      { id: 'qa-new-thread', to: '/forum/new-thread', label: 'Start a thread', Icon: Plus },
    ];
    categories.forEach((category) => {
      rows.push({
        id: `qa-board-${category.id}`,
        to: categoryPath(category),
        label: category.name,
        Icon: boardIdentity(category.slug, category.name).Icon,
      });
    });
    return rows;
  }, [categories]);

  const topicRows = useMemo<PaletteRow[]>(() => {
    if (!showTopics) return [];
    const rows: PaletteRow[] = topics.map((thread) => ({
      id: `topic-${thread.id}`,
      to: threadPath(thread.category, thread),
      label: thread.title,
    }));
    rows.push({
      id: 'topic-search-everything',
      to: `/forum/search?q=${encodeURIComponent(trimmedQuery)}`,
      label: `Search everything for "${trimmedQuery}"`,
    });
    return rows;
  }, [showTopics, topics, trimmedQuery]);

  const peopleRows = useMemo<PaletteRow[]>(() => {
    if (!showPeople) return [];
    return people.map((person) => ({
      id: `person-${person.username}`,
      to: userProfilePath(person.username),
      label: person.display_name || person.username,
      secondary: `@${person.username}`,
    }));
  }, [showPeople, people]);

  const flatRows = useMemo(
    () => [...quickActionRows, ...topicRows, ...peopleRows],
    [quickActionRows, topicRows, peopleRows]
  );

  // Where the roving cursor sits BEFORE the user has explicitly moved it.
  // Quick actions are unfiltered and always head `flatRows`, so a fixed
  // `flatRows[0]` default is always "Identify a plant" — plain Enter would
  // fire that quick action even when the query has real topic hits sitting
  // right below it (code review finding #4). Once there's a query with at
  // least one real topic result, default to the TOP TOPIC row instead
  // (`topicRows` lists real hits before its trailing "Search everything…"
  // row, so index `quickActionRows.length` is always the top hit when one
  // exists). No query, or a query with zero topic hits (loading/error/empty)
  // — default stays the first quick action.
  const defaultIndex = showTopics && topics.length > 0 ? quickActionRows.length : 0;
  const effectiveIndex = hasNavigated ? activeIndex : defaultIndex;
  const clampedIndex = flatRows.length === 0 ? -1 : Math.min(effectiveIndex, flatRows.length - 1);
  const activeRow = clampedIndex >= 0 ? flatRows[clampedIndex] : undefined;

  const activate = (row: PaletteRow) => {
    navigate(row.to);
    onClose();
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (flatRows.length === 0) return;
      // Step from wherever the cursor is CURRENTLY shown (effectiveIndex),
      // not the possibly-stale raw activeIndex — the first arrow press
      // after a query change must move relative to the default-selected
      // row, not silently jump from an index left over from before.
      const next =
        e.key === 'ArrowDown'
          ? Math.min(effectiveIndex + 1, flatRows.length - 1)
          : Math.max(effectiveIndex - 1, 0);
      setHasNavigated(true);
      setActiveIndex(next);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeRow) activate(activeRow);
    }
  };

  // Tab/Shift+Tab wraps between the input and the last visible row instead
  // of leaving the dialog for the page behind it.
  const handlePanelKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'Tab') return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusables = panel.querySelectorAll<HTMLElement>('a[href], button, input');
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;

  const renderRow = (row: PaletteRow) => {
    const index = flatRows.indexOf(row);
    const selected = index === clampedIndex;
    const Icon = row.Icon;
    return (
      <Link
        key={row.id}
        id={row.id}
        to={row.to}
        aria-selected={selected}
        onClick={onClose}
        onMouseEnter={() => {
          setHasNavigated(true);
          setActiveIndex(index);
        }}
        className={`flex min-h-11 items-center gap-2.5 px-4 text-body-sm transition-colors ${
          selected ? 'bg-surface-2 text-ink' : 'text-ink-2 hover:bg-surface-2/70 hover:text-ink'
        }`}
      >
        {Icon && <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden="true" />}
        <span className="min-w-0 flex-1 truncate">{row.label}</span>
        {row.secondary && <span className="shrink-0 text-ink-3">{row.secondary}</span>}
      </Link>
    );
  };

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-abyss/70 transition-opacity duration-200 motion-reduce:transition-none"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative mx-auto mt-[12vh] w-full max-w-xl px-4">
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label="Search"
          onKeyDown={handlePanelKeyDown}
          className={`canopy-card w-full rounded-lg border border-line shadow-2 transition-all duration-200 motion-reduce:transition-none ${
            visible ? 'scale-100 opacity-100' : 'scale-95 opacity-0'
          }`}
        >
          <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
            <Search className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Search plants, posts, people…"
              aria-label="Search plants, posts, people"
              aria-activedescendant={activeRow?.id}
              autoComplete="off"
              className="w-full bg-transparent text-body text-ink outline-none placeholder:text-ink-3"
            />
          </div>
          <div className="max-h-[60vh] overflow-y-auto py-2">
            <div>
              <p className="gt-label px-4 pt-1 pb-1.5">Quick actions</p>
              {quickActionRows.map((row) => renderRow(row))}
            </div>

            {showTopics && (
              <div>
                <p className="gt-label px-4 pt-3 pb-1.5">Topics</p>
                {topicsLoading && <p className="px-4 py-2 text-body-sm text-ink-3">Searching…</p>}
                {!topicsLoading && topicsError && (
                  <p className="px-4 py-2 text-body-sm text-error">
                    Search is unavailable right now
                  </p>
                )}
                {!topicsLoading &&
                  !topicsError &&
                  topicRows.slice(0, topics.length).map((row) => renderRow(row))}
                {renderRow(topicRows[topicRows.length - 1])}
              </div>
            )}

            {showPeople && (
              <div>
                <p className="gt-label px-4 pt-3 pb-1.5">People</p>
                {peopleLoading && <p className="px-4 py-2 text-body-sm text-ink-3">Searching…</p>}
                {!peopleLoading && peopleError && (
                  <p className="px-4 py-2 text-body-sm text-error">
                    Search is unavailable right now
                  </p>
                )}
                {!peopleLoading && !peopleError && peopleRows.map((row) => renderRow(row))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
