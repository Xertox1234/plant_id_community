import { afterEach, describe, expect, it } from 'vitest';
import { Editor, type JSONContent } from '@tiptap/react';
import Mention from '@tiptap/extension-mention';
import { NodeSelection, TextSelection } from '@tiptap/pm/state';
import { forumComposerExtensions } from './forumEditorSchema';
import { ForumQuoteLock, positionOutsideLockedQuotes } from './forumQuoteLock';
import { docToBodyBlocks, postQuoteNode } from '../../utils/forumBody';

/**
 * Owner decision (audit F3): the words in a quote of another member's post
 * must match that post, so the composer never lets them be edited.
 */
describe('ForumQuoteLock', () => {
  const p = (text?: string): JSONContent =>
    text ? { type: 'paragraph', content: [{ type: 'text', text }] } : { type: 'paragraph' };
  const quote = postQuoteNode(7, 'water weekly\n\nno more')!;
  const QUOTE_BLOCK = {
    type: 'post_quote',
    value: { post: 7, text: 'water weekly\n\nno more' },
  };
  let editor: Editor;

  function make(...content: JSONContent[]) {
    const element = document.createElement('div');
    document.body.appendChild(element);
    editor = new Editor({
      element,
      extensions: [...forumComposerExtensions(Mention), ForumQuoteLock],
      content: { type: 'doc', content },
    });
    return editor;
  }
  afterEach(() => {
    editor.destroy();
    document.body.innerHTML = '';
  });

  const blocks = () => docToBodyBlocks(editor.getJSON());
  /** The position just after `text` in the document. */
  function after(text: string): number {
    let found = -1;
    editor.state.doc.descendants((node, pos) => {
      const at = node.isText ? (node.text ?? '').indexOf(text) : -1;
      if (found < 0 && at >= 0) found = pos + at + text.length;
    });
    expect(found).toBeGreaterThan(-1);
    return found;
  }
  function select(from: number, to = from) {
    const { tr, doc } = editor.state;
    editor.view.dispatch(tr.setSelection(TextSelection.create(doc, from, to)));
  }
  /** Type as ProseMirror does: ask handleTextInput first, then insert. */
  function type(text: string) {
    const { view } = editor;
    const { from, to } = view.state.selection;
    const insert = () => view.state.tr.insertText(text, from, to);
    const handled = view.someProp('handleTextInput', (f) => f(view, from, to, text, insert));
    if (!handled) view.dispatch(insert());
  }
  function press(key: string) {
    const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
    return !!editor.view.someProp('handleKeyDown', (f) => f(editor.view, event));
  }

  // jsdom has no ClipboardEvent; ProseMirror only passes the event along.
  const paste = () => new Event('paste') as ClipboardEvent;

  it('typing at the end of the quote lands after it', () => {
    make(quote, p('mine'));
    select(after('no more'));
    type('X');
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>Xmine</p>' }]);
  });

  it('typing in the middle of the quote lands after it, making a paragraph if there is none', () => {
    make(quote);
    select(after('water'));
    type('X');
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>X</p>' }]);
  });

  it('two quotes in a row: the caret passes both', () => {
    make(quote, quote, p('mine'));
    select(after('water'));
    type('X');
    expect(blocks()).toEqual([
      QUOTE_BLOCK,
      QUOTE_BLOCK,
      { type: 'paragraph', value: '<p>Xmine</p>' },
    ]);
  });

  it('moving up out of a paragraph skips the quote to the text above it', () => {
    make(p('above'), quote, p('below'));
    select(after('below') - 5);
    select(after('no more'));
    expect(editor.state.selection.from).toBe(after('above'));
  });

  it("keeps text the browser typed in the quote while the editor's caret was elsewhere", () => {
    make(quote, p('mine'));
    select(after('mine'));
    const { view } = editor;
    const at = after('water');
    const insert = () => view.state.tr.insertText('X', at);
    expect(view.someProp('handleTextInput', (f) => f(view, at, at, 'X', insert))).toBe(true);
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>Xmine</p>' }]);
  });

  it('refuses a direct change inside the quote, whatever sends it', () => {
    make(quote, p('mine'));
    const at = after('water');
    editor.view.dispatch(editor.state.tr.insertText(' never', at));
    editor.view.dispatch(editor.state.tr.delete(at - 2, at));
    editor.view.dispatch(editor.state.tr.split(at));
    editor
      .chain()
      .setTextSelection({ from: at - 3, to: at })
      .toggleBold()
      .run();
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>mine</p>' }]);
  });

  it('refuses an attribution put on words the composer did not start with', () => {
    make(quote, p('invented'));
    editor.chain().setTextSelection(after('invented')).toggleBlockquote().run();
    editor.commands.updateAttributes('blockquote', { postId: '7' });
    // Then the empty paragraph TrailingNode keeps at the end.
    expect(blocks().slice(0, 2)).toEqual([QUOTE_BLOCK, { type: 'quote', value: 'invented' }]);
  });

  it('Backspace after the quote selects it, and again removes it; undo brings it back', () => {
    make(quote, p('mine'));
    select(after('mine') - 4);
    expect(press('Backspace')).toBe(true);
    expect(editor.state.selection).toBeInstanceOf(NodeSelection);
    press('Backspace');
    expect(blocks()).toEqual([{ type: 'paragraph', value: '<p>mine</p>' }]);
    editor.commands.undo();
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>mine</p>' }]);
  });

  it('Delete before the quote selects it', () => {
    make(p('above'), quote, p());
    select(after('above'));
    expect(press('Delete')).toBe(true);
    expect((editor.state.selection as NodeSelection).node.type.name).toBe('blockquote');
  });

  it('deleting a selection that runs into the quote removes the whole quote', () => {
    make(p('above'), quote, p('below'));
    select(after('abo'), after('water'));
    expect(press('Backspace')).toBe(true);
    expect(blocks()).toEqual([{ type: 'paragraph', value: '<p>abo</p><p>below</p>' }]);
  });

  it('typing over a selection that runs into the quote removes the whole quote', () => {
    make(p('above'), quote, p('below'));
    select(after('abo'), after('water'));
    type('X');
    expect(blocks()).toEqual([{ type: 'paragraph', value: '<p>aboX</p><p>below</p>' }]);
  });

  it('typing over words selected inside the quote keeps them and lands after it', () => {
    make(quote, p('mine'));
    select(after('wat'), after('water'));
    type('X');
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>Xmine</p>' }]);
  });

  it('pasted markup cannot attribute new words to a post', () => {
    make(quote, p());
    select(editor.state.doc.content.size - 1);
    editor.view.pasteHTML(
      '<blockquote data-post-id="7"><p>invented</p></blockquote><p>z</p>',
      paste()
    );
    expect(blocks().filter((b) => b.type === 'post_quote')).toEqual([QUOTE_BLOCK]);
    expect(JSON.stringify(blocks())).toContain('invented');
  });

  it('a paste aimed at the quote lands after it', () => {
    make(quote, p('mine'));
    select(after('wat'), after('water'));
    editor.view.pasteText('X', paste());
    expect(blocks()).toEqual([QUOTE_BLOCK, { type: 'paragraph', value: '<p>Xmine</p>' }]);
  });

  it('a free-form quote stays editable', () => {
    make({ type: 'blockquote', content: [p('my words')] }, p());
    select(after('my words'));
    type('!');
    expect(blocks()[0]).toEqual({ type: 'quote', value: 'my words!' });
  });

  it('moves an insert position out of the quote (a dropped or uploaded image)', () => {
    make(quote, p('mine'));
    const { doc } = editor.state;
    expect(positionOutsideLockedQuotes(doc, after('water'))).toBe(doc.child(0).nodeSize);
    expect(positionOutsideLockedQuotes(doc, after('mine'))).toBe(after('mine'));
  });
});
