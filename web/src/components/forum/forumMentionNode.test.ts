import { describe, it, expect, vi, afterEach } from 'vitest';
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

/**
 * The suggestion dropdown's DOM lifecycle (audit 2026-09-04 L5). ProseMirror's
 * suggestion plugin calls these render() callbacks against a MOUNTED
 * EditorView, which a headless Editor never has (web/docs/patterns/testing.md)
 * — so the callbacks are driven directly with the props shape the plugin
 * hands them. This is the only coverage the ~115 lines of dropdown
 * creation, positioning, keyboard navigation and teardown have.
 */
describe('ForumMention suggestion render() lifecycle', () => {
  type Item = { id: string; label: string };
  type Renderer = ReturnType<
    NonNullable<NonNullable<typeof ForumMention.options.suggestion>['render']>
  >;

  const items: Item[] = [
    { id: 'ada', label: 'ada' },
    { id: 'adele', label: 'adele' },
    { id: 'adrian', label: 'adrian' },
  ];

  function makeProps(overrides: Partial<{ items: Item[]; isDestroyed: boolean }> = {}) {
    const command = vi.fn();
    const props = {
      editor: { isDestroyed: overrides.isDestroyed ?? false },
      items: overrides.items ?? items,
      command,
      clientRect: () => ({ bottom: 100, left: 40 }) as DOMRect,
      query: 'ad',
      text: '@ad',
      range: { from: 0, to: 3 },
      decorationNode: null,
    };
    return { command, props: props as unknown as Parameters<Renderer['onStart']>[0] };
  }

  function dropdown(): HTMLDivElement | null {
    return document.body.querySelector<HTMLDivElement>('div.z-50');
  }

  function renderer(): Renderer {
    return ForumMention.options.suggestion!.render!() as Renderer;
  }

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('onStart mounts one button per item below the trigger, first item selected', () => {
    const r = renderer();
    r.onStart(makeProps().props);

    const el = dropdown();
    expect(el).not.toBeNull();
    expect(el!.style.position).toBe('fixed');
    expect(el!.style.top).toBe('104px');
    expect(el!.style.left).toBe('40px');
    const buttons = Array.from(el!.querySelectorAll('button'));
    expect(buttons.map((b) => b.textContent)).toEqual(['@ada', '@adele', '@adrian']);
    expect(buttons[0].className).toContain('bg-primary/20');
    expect(buttons[1].className).not.toContain('bg-primary/20');
  });

  it('arrow keys move the selection (wrapping) and Enter commits the selected item', () => {
    const r = renderer();
    const { command, props } = makeProps();
    r.onStart(props);

    expect(
      r.onKeyDown({ event: new KeyboardEvent('keydown', { key: 'ArrowDown' }) } as never)
    ).toBe(true);
    expect(dropdown()!.querySelectorAll('button')[1].className).toContain('bg-primary/20');
    r.onKeyDown({ event: new KeyboardEvent('keydown', { key: 'ArrowUp' }) } as never);
    r.onKeyDown({ event: new KeyboardEvent('keydown', { key: 'ArrowUp' }) } as never);
    expect(dropdown()!.querySelectorAll('button')[2].className).toContain('bg-primary/20');

    expect(r.onKeyDown({ event: new KeyboardEvent('keydown', { key: 'Enter' }) } as never)).toBe(
      true
    );
    expect(command).toHaveBeenCalledWith(items[2]);
    // Keys the dropdown does not own fall through to the editor.
    expect(r.onKeyDown({ event: new KeyboardEvent('keydown', { key: 'a' }) } as never)).toBe(false);
  });

  it('mousedown on an item commits it without stealing the caret', () => {
    const r = renderer();
    const { command, props } = makeProps();
    r.onStart(props);

    const event = new MouseEvent('mousedown', { cancelable: true, bubbles: true });
    dropdown()!.querySelectorAll('button')[1].dispatchEvent(event);

    expect(command).toHaveBeenCalledWith(items[1]);
    expect(event.defaultPrevented).toBe(true);
  });

  it('onUpdate repaints in place and onExit tears the dropdown down', () => {
    const r = renderer();
    r.onStart(makeProps().props);
    r.onUpdate(makeProps({ items: [items[0]] }).props);
    expect(dropdown()!.querySelectorAll('button')).toHaveLength(1);
    expect(document.body.querySelectorAll('div.z-50')).toHaveLength(1);

    r.onExit(makeProps().props);
    expect(dropdown()).toBeNull();
    // A stale keydown after exit is a no-op, not a crash on a removed node.
    expect(r.onKeyDown({ event: new KeyboardEvent('keydown', { key: 'Enter' }) } as never)).toBe(
      false
    );
  });

  it('never creates a dropdown for an empty list or a torn-down editor, and removes one on update', () => {
    const r = renderer();
    r.onStart(makeProps({ items: [] }).props);
    expect(dropdown()).toBeNull();
    r.onStart(makeProps({ isDestroyed: true }).props);
    expect(dropdown()).toBeNull();

    r.onStart(makeProps().props);
    expect(dropdown()).not.toBeNull();
    r.onUpdate(makeProps({ isDestroyed: true }).props);
    expect(dropdown()).toBeNull();
  });
});
