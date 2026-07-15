import { describe, it, expect, vi } from 'vitest';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { ForumMention, resolveMentionSuggestions } from './forumMentionNode';
import { searchForumUsers } from '../../services/forumService';
import type { ForumUserSearchResult } from '../../services/forumService';

vi.mock('../../services/forumService');

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

/**
 * Pins the one thing that must not silently regress (todo 253 slice 4
 * review): the backend sanitizer strips all structured mention markup, so
 * ONLY the literal "@username" text surviving into the serialized body
 * lets the server-side regex parser resolve a mention at all. Tests the
 * extension directly (a headless Editor, not the full TipTapEditor
 * component) since that's the exact surface renderHTML/renderText control.
 */
describe('ForumMention', () => {
  function makeEditor() {
    return new Editor({
      extensions: [StarterKit, ForumMention],
      content: '<p></p>',
    });
  }

  it('serializes a selected mention as literal "@username", not just "username"', () => {
    const editor = makeEditor();
    editor.commands.insertContent({
      type: 'mention',
      attrs: { id: 'alice', label: 'alice' },
    });

    const html = editor.getHTML();
    expect(html).toContain('@alice');
    // Guards specifically against a config that drops the "@" prefix, which
    // would leave the span's text content as bare "alice".
    expect(html).not.toContain('>alice<');
    // The configured HTMLAttributes class must survive — a prior custom
    // renderHTML override hardcoded `{}` for attrs and silently discarded it
    // (todo 253 slice 4 review).
    expect(html).toContain('text-primary');

    editor.destroy();
  });

  it('getText() also includes the "@" (renderText, used outside getHTML())', () => {
    const editor = makeEditor();
    editor.commands.insertContent({
      type: 'mention',
      attrs: { id: 'bob', label: 'bob' },
    });

    expect(editor.getText()).toContain('@bob');

    editor.destroy();
  });
});

/**
 * resolveMentionSuggestions debounces (300ms, matching SearchPage.tsx) and
 * guards against out-of-order network responses: a search superseded by a
 * newer keystroke must resolve to [], even if ITS network response happens
 * to arrive after the newer search's (todo 253 slice 4 review — a naive
 * implementation could otherwise repaint/recreate the autocomplete dropdown
 * with stale results, or resurrect one after the session already exited).
 */
describe('resolveMentionSuggestions', () => {
  it('returns [] immediately for an empty query, with no debounce wait', async () => {
    const result = await resolveMentionSuggestions({ query: '' });
    expect(result).toEqual([]);
    expect(searchForumUsers).not.toHaveBeenCalled();
  });

  it('a stale in-flight search resolves to [] when a newer one supersedes it out of order', async () => {
    vi.useFakeTimers();
    try {
      const first = deferred<ForumUserSearchResult[]>();
      const second = deferred<ForumUserSearchResult[]>();
      vi.mocked(searchForumUsers)
        .mockReturnValueOnce(first.promise)
        .mockReturnValueOnce(second.promise);

      const firstCall = resolveMentionSuggestions({ query: 'al' });
      await vi.advanceTimersByTimeAsync(300); // first's debounce elapses; it's now awaiting searchForumUsers

      const secondCall = resolveMentionSuggestions({ query: 'ali' });
      await vi.advanceTimersByTimeAsync(300); // second's debounce elapses; it's now awaiting searchForumUsers too

      // Resolve OUT OF ORDER: the newer search's response arrives first.
      second.resolve([{ username: 'alice', display_name: 'Alice' }]);
      await expect(secondCall).resolves.toEqual([{ id: 'alice', label: 'alice' }]);

      first.resolve([{ username: 'alfred', display_name: 'Alfred' }]);
      await expect(firstCall).resolves.toEqual([]);
    } finally {
      vi.useRealTimers();
    }
  });
});
