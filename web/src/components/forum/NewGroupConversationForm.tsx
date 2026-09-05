import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { X } from 'lucide-react';
import { ForumApiError, searchForumUsers } from '../../services/forumService';
import type { ForumUserSearchResult } from '../../services/forumService';
import {
  createGroupConversation,
  GROUP_MAX_OTHERS,
  GROUP_MIN_OTHERS,
  GROUP_TITLE_MAX_LENGTH,
  MESSAGE_MAX_LENGTH,
} from '../../services/messageService';
import { useAuth } from '../../contexts/AuthContext';
import { logger } from '../../utils/logger';
import Button from '../ui/Button';
import Input from '../ui/Input';
import type { Conversation } from '../../types/forum';

// Same window and rate-limit tier as the @mention autocomplete
// (mention_user_search: 30/m) — the picker is the same "search as you type"
// against the same endpoint, minus the TipTap plumbing.
const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_MIN_CHARS = 2;
const MAX_SUGGESTIONS = 6;

/** A typed username: trimmed, without a leading "@" or a trailing separator. */
function normalizeUsername(raw: string): string {
  return raw.trim().replace(/^@/, '').replace(/,+$/, '').trim();
}

function sameUser(a: string, b: string): boolean {
  return a.localeCompare(b, undefined, { sensitivity: 'accent' }) === 0;
}

function describeWait(seconds: number): string {
  if (seconds < 60) return `${seconds} second${seconds === 1 ? '' : 's'}`;
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} minute${minutes === 1 ? '' : 's'}`;
}

/**
 * Notice text for a failed create. Branches on the STATUS (docs/rules/react.md):
 * a 429 carries the dm_group_create bucket's Retry-After, a 400 is the server's
 * own line — the generic "One of the members cannot be added." (no oracle on
 * which member) or the spam screen's reason — rendered verbatim.
 */
function describeCreateError(err: unknown): string {
  if (err instanceof ForumApiError) {
    if (err.status === 429) {
      return err.retryAfter !== null
        ? `You're creating groups too quickly — try again in ${describeWait(err.retryAfter)}.`
        : "You're creating groups too quickly — try again later.";
    }
    return err.message;
  }
  return err instanceof Error ? err.message : 'Failed to create the group';
}

interface MemberPickerProps {
  members: string[];
  draft: string;
  onDraftChange: (value: string) => void;
  /** Returns false when the username was refused (empty, you, a duplicate, at cap). */
  onAdd: (username: string) => boolean;
  onRemove: (username: string) => void;
  /** The viewer — never offered as a suggestion; they are in every group they create. */
  viewerUsername: string | undefined;
  disabled: boolean;
}

/**
 * Username chips with a debounced suggestion list under the input. Enter or
 * a comma commits the typed name; Backspace on an empty input drops the last
 * chip. At the cap the input stays mounted and focusable (`aria-disabled` +
 * `readOnly`, never `disabled`) so the person who just added the seventh
 * member does not lose their place, and the hint says why nothing happens.
 */
function MemberPicker({
  members,
  draft,
  onDraftChange,
  onAdd,
  onRemove,
  viewerUsername,
  disabled,
}: MemberPickerProps) {
  const hintId = useId();
  const suggestionsId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [suggestions, setSuggestions] = useState<ForumUserSearchResult[]>([]);
  // Which suggestion the keyboard is on (-1 = none): a listbox needs a
  // roving `aria-activedescendant`, not mouse-only clicks (react review).
  const [activeIndex, setActiveIndex] = useState(-1);
  const atCap = members.length >= GROUP_MAX_OTHERS;

  // Timer and abort controller live in the effect closure (cleared on the
  // next keystroke and on unmount) — never a timer id in state.
  useEffect(() => {
    const query = normalizeUsername(draft);
    if (query.length < SEARCH_MIN_CHARS || atCap) {
      setSuggestions([]);
      return undefined;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const results = await searchForumUsers(query, controller.signal);
        if (controller.signal.aborted) return;
        setSuggestions(results);
      } catch {
        // A failed lookup shows no suggestions — typing a username still works.
        if (controller.signal.aborted) return;
        setSuggestions([]);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [draft, atCap]);

  // Filter at render time (not in the effect) so adding a chip never
  // re-issues the search for the text still in the box.
  const visibleSuggestions = suggestions
    .filter((u) => !members.some((m) => sameUser(m, u.username)))
    .filter((u) => !(viewerUsername && sameUser(viewerUsername, u.username)))
    .slice(0, MAX_SUGGESTIONS);

  const commitDraft = () => {
    if (onAdd(draft)) onDraftChange('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const count = visibleSuggestions.length;
    if (event.key === 'ArrowDown' && count > 0) {
      event.preventDefault();
      setActiveIndex((i) => (i + 1) % count);
    } else if (event.key === 'ArrowUp' && count > 0) {
      event.preventDefault();
      setActiveIndex((i) => (i <= 0 ? count - 1 : i - 1));
    } else if (event.key === 'Escape' && count > 0) {
      // Close the list without submitting the form.
      event.preventDefault();
      setSuggestions([]);
      setActiveIndex(-1);
    } else if (event.key === 'Enter' || event.key === ',') {
      // Enter must not submit the whole form from the picker; a comma is a
      // separator, never part of a username. With a highlighted suggestion,
      // Enter takes it instead of the typed text.
      event.preventDefault();
      const highlighted = activeIndex >= 0 ? visibleSuggestions[activeIndex] : undefined;
      if (highlighted) {
        if (onAdd(highlighted.username)) onDraftChange('');
        setActiveIndex(-1);
      } else {
        commitDraft();
      }
    } else if (event.key === 'Backspace' && draft === '' && members.length > 0) {
      onRemove(members[members.length - 1]);
    }
  };

  return (
    <div>
      <label htmlFor="group-members" className="block text-sm font-medium text-ink-2 mb-1">
        Members
      </label>
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line-2 bg-surface px-2 py-1.5 focus-within:ring-2 focus-within:ring-primary">
        {members.map((username) => (
          <span
            key={username}
            className="inline-flex items-center gap-1 rounded-pill border border-line bg-surface-2/60 pl-3 pr-1 text-body-sm text-ink-2"
          >
            @{username}
            <button
              type="button"
              onClick={() => {
                onRemove(username);
                inputRef.current?.focus();
              }}
              disabled={disabled}
              aria-label={`Remove ${username}`}
              className="inline-grid min-h-11 min-w-11 place-items-center rounded-pill text-ink-3 hover:bg-surface-2 hover:text-ink disabled:opacity-50"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id="group-members"
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={handleKeyDown}
          readOnly={atCap || disabled}
          aria-disabled={atCap || disabled || undefined}
          aria-describedby={hintId}
          role="combobox"
          aria-expanded={visibleSuggestions.length > 0}
          aria-controls={visibleSuggestions.length > 0 ? suggestionsId : undefined}
          aria-activedescendant={
            activeIndex >= 0 && visibleSuggestions.length > 0
              ? `${suggestionsId}-${activeIndex}`
              : undefined
          }
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          placeholder={atCap ? '' : members.length === 0 ? 'Type a username…' : 'Add another…'}
          className="min-w-[8rem] flex-1 border-0 bg-transparent px-1 py-1 text-ink placeholder-ink-3 focus:outline-none"
        />
      </div>
      <p id={hintId} className="mt-1 text-meta text-ink-3">
        {atCap
          ? `That's the limit — ${GROUP_MAX_OTHERS} members besides you.`
          : `${GROUP_MIN_OTHERS}–${GROUP_MAX_OTHERS} members besides you. Press Enter or a comma after each username.`}
      </p>
      {visibleSuggestions.length > 0 && (
        <ul
          id={suggestionsId}
          role="listbox"
          aria-label="Suggested members"
          className="mt-1 max-h-56 overflow-y-auto rounded-md border border-line bg-surface-2 py-1 shadow-2"
        >
          {visibleSuggestions.map((u, index) => (
            <li
              key={u.username}
              id={`${suggestionsId}-${index}`}
              role="option"
              aria-selected={index === activeIndex}
            >
              <button
                type="button"
                tabIndex={-1}
                onClick={() => {
                  if (onAdd(u.username)) onDraftChange('');
                  setActiveIndex(-1);
                  inputRef.current?.focus();
                }}
                disabled={disabled}
                aria-label={`Add ${u.username}`}
                className="flex w-full min-h-11 items-center gap-2 px-3 py-1.5 text-left text-body-sm text-ink hover:bg-surface-3 disabled:opacity-50"
              >
                <span className="font-medium">@{u.username}</span>
                {u.display_name && <span className="truncate text-ink-3">{u.display_name}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface NewGroupConversationFormProps {
  /** The created inbox row — the page navigates to it. */
  onCreated: (conversation: Conversation) => void;
  onCancel: () => void;
}

/**
 * Start a group conversation (todo 350): title, 2–7 other members, and the
 * first message — a group only exists once a message was sent, like a direct
 * thread. Every failure, validation or server, lands in one always-mounted
 * live region; the fields keep their text so the person can fix and resend.
 */
export default function NewGroupConversationForm({
  onCreated,
  onCancel,
}: NewGroupConversationFormProps) {
  const { user } = useAuth();
  const [title, setTitle] = useState('');
  const [titleError, setTitleError] = useState<string | undefined>(undefined);
  const [members, setMembers] = useState<string[]>([]);
  const [memberDraft, setMemberDraft] = useState('');
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const viewerUsername = user?.username;

  /** Add a typed/suggested username; false (with a notice) when refused. */
  const addMember = (raw: string): boolean => {
    const username = normalizeUsername(raw);
    if (!username) return false;
    if (members.length >= GROUP_MAX_OTHERS) {
      setNotice(`A group can have at most ${GROUP_MAX_OTHERS} members besides you.`);
      return false;
    }
    if (viewerUsername && sameUser(username, viewerUsername)) {
      setNotice("You're in every group you create — no need to add yourself.");
      return false;
    }
    if (members.some((m) => sameUser(m, username))) {
      setNotice(`@${username} is already in the list.`);
      return false;
    }
    setNotice(null);
    setMembers((prev) => [...prev, username]);
    return true;
  };

  const removeMember = (username: string) => {
    setMembers((prev) => prev.filter((m) => m !== username));
  };

  const handleSubmit = async () => {
    if (submitting) return;
    // A username still sitting in the picker counts — nobody should lose a
    // member because they reached for the submit button instead of Enter.
    let usernames = members;
    const leftover = normalizeUsername(memberDraft);
    if (leftover) {
      if (!addMember(leftover)) return;
      usernames = [...members, leftover];
      setMemberDraft('');
    }
    const trimmedTitle = title.trim();
    const trimmedBody = body.trim();
    if (!trimmedTitle) {
      setTitleError('Give the group a name.');
      return;
    }
    setTitleError(undefined);
    if (usernames.length < GROUP_MIN_OTHERS) {
      setNotice(`Add at least ${GROUP_MIN_OTHERS} members besides you.`);
      return;
    }
    if (!trimmedBody) {
      setNotice('Write the first message.');
      return;
    }
    setSubmitting(true);
    setNotice(null);
    try {
      const created = await createGroupConversation({
        title: trimmedTitle,
        usernames,
        body: trimmedBody,
      });
      onCreated(created);
    } catch (err) {
      logger.error('Error creating group conversation', {
        component: 'NewGroupConversationForm',
        error: err,
        context: { memberCount: usernames.length },
      });
      setNotice(describeCreateError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void handleSubmit();
      }}
      aria-label="New group"
      className="flex flex-col gap-4"
    >
      <Input
        label="Group name"
        name="group-title"
        value={title}
        onChange={(event) => {
          setTitle(event.target.value);
          if (titleError) setTitleError(undefined);
        }}
        error={titleError}
        maxLength={GROUP_TITLE_MAX_LENGTH}
        disabled={submitting}
        autoFocus
        autoComplete="off"
      />

      <MemberPicker
        members={members}
        draft={memberDraft}
        onDraftChange={setMemberDraft}
        onAdd={addMember}
        onRemove={removeMember}
        viewerUsername={viewerUsername}
        disabled={submitting}
      />

      <div>
        <label htmlFor="group-first-message" className="block text-sm font-medium text-ink-2 mb-1">
          First message
        </label>
        <textarea
          id="group-first-message"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          maxLength={MESSAGE_MAX_LENGTH}
          rows={3}
          disabled={submitting}
          placeholder="Say hello to everyone…"
          className="w-full rounded-md border border-line bg-surface-2/60 px-3 py-2 text-ink placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none disabled:opacity-60"
        />
        <span className="font-mono text-micro text-ink-3">{`${body.length}/${MESSAGE_MAX_LENGTH}`}</span>
      </div>

      {/* Persistent live region: always mounted so a text swap is announced;
          visually collapsed when empty (docs/rules/react.md). */}
      <p
        aria-live="polite"
        aria-atomic="true"
        className={notice ? 'text-sm text-error' : 'sr-only'}
      >
        {notice}
      </p>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCancel}
          disabled={submitting}
          className="min-h-11"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          loading={submitting}
          loadingText="Creating…"
          className="min-h-11"
        >
          Create group
        </Button>
      </div>
    </form>
  );
}
