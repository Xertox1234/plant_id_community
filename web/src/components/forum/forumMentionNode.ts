import Mention from '@tiptap/extension-mention';
import type { SuggestionKeyDownProps, SuggestionProps } from '@tiptap/suggestion';
import { searchForumUsers } from '../../services/forumService';

const MAX_SUGGESTIONS = 8;
// Matches SearchPage.tsx's debounce window — same "live search as you type"
// shape, same rate-limit tier (mention_user_search: 30/m, forum_host/
// constants.py) as the box it's modeled on.
const SEARCH_DEBOUNCE_MS = 300;

interface MentionSuggestionItem {
  id: string;
  label: string;
}

type MentionSuggestionProps = SuggestionProps<MentionSuggestionItem, MentionSuggestionItem>;

// Module-level, not per-editor: `items` is created once when Mention.configure()
// runs (module load), before any editor instance exists to scope state to.
// Accepted tradeoff (todo 253 slice 4 review) — if two composers were ever
// mounted at once, a keystroke in one could cancel an in-flight debounce in
// the other; it self-heals on the next keystroke, never a wrong result.
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
// Bumped on every new search AND on every onExit, so a search whose session
// has already closed (Escape/blur, not just "superseded by a newer search")
// still resolves to [] instead of resurrecting a dropdown nothing will ever
// clean up.
let searchToken = 0;

export async function resolveMentionSuggestions({
  query,
}: {
  query: string;
}): Promise<MentionSuggestionItem[]> {
  if (!query) return [];
  const myToken = ++searchToken;
  if (debounceTimer) clearTimeout(debounceTimer);
  await new Promise<void>((resolve) => {
    debounceTimer = setTimeout(resolve, SEARCH_DEBOUNCE_MS);
  });
  if (myToken !== searchToken) return []; // superseded during the debounce wait
  try {
    const results = await searchForumUsers(query);
    if (myToken !== searchToken) return []; // superseded while the request was in flight
    return results.slice(0, MAX_SUGGESTIONS).map((u) => ({ id: u.username, label: u.username }));
  } catch {
    // A failed lookup just shows an empty list — never blocks typing.
    return [];
  }
}

/**
 * @mention composer autocomplete (todo 253 slice 4, H4).
 *
 * The backend sanitizer (wagtail_forum/api/sanitize.py) strips ALL structured
 * markup from stored post content — no span, no data-* attributes, only
 * href/title survive on <a>. Only the LITERAL "@username" text makes it to
 * the wire; the server resolves mentions with its own regex against
 * User.username, never trusting a client-supplied id (wagtail_forum/
 * mentions.py). No custom renderHTML/renderText here — the installed
 * 3.22.5 default (node_modules/@tiptap/extension-mention/dist/index.js)
 * already prepends the suggestion char ("@") AND correctly mergeAttributes()s
 * the HTMLAttributes below; a prior custom override duplicated the "@"
 * logic while hardcoding `{}` for attrs, silently dropping this styling
 * (todo 253 slice 4 review). Pinned by forumMentionNode.test.ts.
 */
export const ForumMention = Mention.configure({
  HTMLAttributes: {
    class: 'text-primary font-medium',
  },
  suggestion: {
    char: '@',
    items: resolveMentionSuggestions,
    render: () => {
      let dropdown: HTMLDivElement | null = null;
      let selectedIndex = 0;
      let currentItems: MentionSuggestionItem[] = [];
      let currentCommand: ((item: MentionSuggestionItem) => void) | null = null;
      let getClientRect: MentionSuggestionProps['clientRect'] = null;

      // No `props.mount()` auto-positioning helper in the installed
      // @tiptap/suggestion@3.22.5 (that API is a newer Tiptap addition) — the
      // installed version only exposes `clientRect`, so positioning is
      // manual: append to <body>, place just below the "@" trigger.
      const position = () => {
        if (!dropdown) return;
        const rect = getClientRect?.();
        if (!rect) return;
        dropdown.style.position = 'fixed';
        dropdown.style.top = `${rect.bottom + 4}px`;
        dropdown.style.left = `${rect.left}px`;
      };

      const paint = () => {
        if (!dropdown) return;
        dropdown.innerHTML = '';
        currentItems.forEach((item, index) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = `@${item.label}`;
          // min-h-11 (44px) tap target — matches PostCard.tsx's action-row
          // convention.
          button.className = `flex items-center w-full min-h-11 text-left px-3 text-sm ${
            index === selectedIndex ? 'bg-primary/20 text-ink' : 'text-ink-2 hover:bg-surface-3'
          }`;
          // mousedown (not click) fires before the editor's blur/selection
          // change, so preventDefault here keeps the caret in place for
          // `command` to replace the right range.
          button.addEventListener('mousedown', (event) => {
            event.preventDefault();
            currentCommand?.(item);
          });
          dropdown!.appendChild(button);
        });
      };

      // A stale onStart/onUpdate (its items() resolved after the session
      // that triggered it already exited or the editor was torn down) must
      // not create or repaint a dropdown nobody will ever clean up.
      const shouldRender = (props: MentionSuggestionProps) =>
        !props.editor.isDestroyed && props.items.length > 0;

      return {
        onStart: (props: MentionSuggestionProps) => {
          if (!shouldRender(props)) return;
          selectedIndex = 0;
          currentItems = props.items;
          currentCommand = props.command;
          getClientRect = props.clientRect;
          dropdown = document.createElement('div');
          dropdown.className =
            'z-50 min-w-[10rem] max-h-56 overflow-y-auto rounded-lg border border-line bg-surface-2 shadow-lg py-1';
          document.body.appendChild(dropdown);
          paint();
          position();
        },
        onUpdate: (props: MentionSuggestionProps) => {
          if (!shouldRender(props)) {
            dropdown?.remove();
            dropdown = null;
            return;
          }
          selectedIndex = 0;
          currentItems = props.items;
          currentCommand = props.command;
          getClientRect = props.clientRect;
          if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.className =
              'z-50 min-w-[10rem] max-h-56 overflow-y-auto rounded-lg border border-line bg-surface-2 shadow-lg py-1';
            document.body.appendChild(dropdown);
          }
          paint();
          position();
        },
        onKeyDown: ({ event }: SuggestionKeyDownProps) => {
          if (!currentItems.length) return false;
          if (event.key === 'ArrowDown') {
            selectedIndex = (selectedIndex + 1) % currentItems.length;
            paint();
            return true;
          }
          if (event.key === 'ArrowUp') {
            selectedIndex = (selectedIndex - 1 + currentItems.length) % currentItems.length;
            paint();
            return true;
          }
          if (event.key === 'Enter') {
            currentCommand?.(currentItems[selectedIndex]);
            return true;
          }
          // No Escape branch: @tiptap/suggestion's own handleKeyDown (dist/
          // index.js) calls renderer.onKeyDown and then unconditionally
          // calls dispatchExit -> renderer.onExit in the SAME synchronous
          // call, ignoring this handler's return value for Escape either
          // way — onExit below already tears the dropdown down, so a
          // separate branch here was dead weight (todo 253 slice 4 review,
          // verified against the installed plugin source).
          return false;
        },
        onExit: () => {
          searchToken++; // invalidate any in-flight resolveMentionSuggestions for this session
          dropdown?.remove();
          dropdown = null;
          currentItems = [];
          currentCommand = null;
          getClientRect = null;
        },
      };
    },
  },
});
