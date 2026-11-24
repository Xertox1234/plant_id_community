import { Extension } from '@tiptap/react';
import type { Node as ProseMirrorNode } from '@tiptap/pm/model';
import { Fragment, Slice } from '@tiptap/pm/model';
import {
  NodeSelection,
  Plugin,
  PluginKey,
  Selection,
  TextSelection,
  type EditorState,
  type Transaction,
} from '@tiptap/pm/state';
import type { EditorView } from '@tiptap/pm/view';

/**
 * Locks the words of a quoted post (owner decision, audit F3: "must match").
 *
 * A blockquote that carries a `postId` is another member's text: the server
 * refuses one that is not in that post. So here it can be removed whole, moved
 * or undone, but never edited, and whatever is typed, pasted or inserted at it
 * lands outside it. A free-form quote (no `postId`) stays editable.
 *
 * Editor behaviour only: no schema, so it is not in forumEditorSchema.
 */

interface LockedQuote {
  from: number;
  to: number;
  node: ProseMirrorNode;
}

function lockedQuotes(doc: ProseMirrorNode): LockedQuote[] {
  const found: LockedQuote[] = [];
  doc.descendants((node, pos) => {
    if (!isLocked(node)) return true;
    found.push({ from: pos, to: pos + node.nodeSize, node });
    return false;
  });
  return found;
}

function isLocked(node: ProseMirrorNode | null | undefined): boolean {
  return node?.type.name === 'blockquote' && !!node.attrs.postId;
}

function quoteAround(doc: ProseMirrorNode, pos: number): LockedQuote | null {
  return lockedQuotes(doc).find((quote) => pos > quote.from && pos < quote.to) ?? null;
}

/** Same post, same content: marks and line breaks included. */
function quoteKey(node: ProseMirrorNode): string {
  return JSON.stringify([String(node.attrs.postId), node.content.toJSON()]);
}

/** `pos`, or the position just after the locked quote it falls in. */
export function positionOutsideLockedQuotes(doc: ProseMirrorNode, pos: number): number {
  return quoteAround(doc, pos)?.to ?? pos;
}

/**
 * Where an insert must go instead of the selection, or null when the
 * selection is clear of every locked quote.
 */
export function insertPositionAvoidingQuotes(state: EditorState): number | null {
  const { from, to, empty } = state.selection;
  if (state.selection instanceof NodeSelection || empty) return null;
  return lockedQuotes(state.doc).some((quote) => from < quote.to && to > quote.from)
    ? positionOutsideLockedQuotes(state.doc, to)
    : null;
}

/** Put the caret in the nearest text outside `quote`, adding a paragraph after it if needed. */
function moveOutOf(tr: Transaction, quote: LockedQuote, direction: 1 | -1): Transaction {
  const textFrom = (pos: number, dir: 1 | -1): Selection | null => {
    let at = pos;
    for (;;) {
      const found = Selection.findFrom(tr.doc.resolve(at), dir, true);
      if (!found) return null;
      const next = quoteAround(tr.doc, found.from);
      if (!next) return found;
      at = dir > 0 ? next.to : next.from;
    }
  };
  const target = (direction < 0 && textFrom(quote.from, -1)) || textFrom(quote.to, 1);
  if (target) return tr.setSelection(target);
  tr.insert(quote.to, tr.doc.type.schema.nodes.paragraph.create());
  return tr.setSelection(TextSelection.create(tr.doc, quote.to + 1));
}

/**
 * For a ranged text selection that reaches into a locked quote: the caret
 * after the quote when the range is inside one, otherwise the range deleted
 * with every quote it touches removed whole. Null when it touches none.
 */
function clearRange(state: EditorState): { tr: Transaction; inside: LockedQuote | null } | null {
  const { selection, doc } = state;
  if (selection.empty || !(selection instanceof TextSelection)) return null;
  const start = quoteAround(doc, selection.from);
  const end = quoteAround(doc, selection.to);
  if (!start && !end) return null;
  if (start && end && start.from === end.from) {
    return { tr: moveOutOf(state.tr, start, 1), inside: start };
  }
  const tr = state.tr.deleteRange(start ? start.from : selection.from, end ? end.to : selection.to);
  const caret = Selection.near(
    tr.doc.resolve(Math.min(tr.mapping.map(selection.from, -1), tr.doc.content.size)),
    start ? 1 : -1
  );
  const landed = quoteAround(tr.doc, caret.from);
  return { tr: landed ? moveOutOf(tr, landed, 1) : tr.setSelection(caret), inside: null };
}

/** The locked quote next to the caret, when Backspace/Delete would join into it. */
function adjacentQuote(state: EditorState, key: 'Backspace' | 'Delete'): number | null {
  const { $from, empty } = state.selection;
  if (!empty || !$from.parent.isTextblock || $from.depth === 0) return null;
  if (key === 'Backspace') {
    if ($from.parentOffset > 0) return null;
    const pos = $from.before();
    const before = state.doc.resolve(pos).nodeBefore;
    return before && isLocked(before) ? pos - before.nodeSize : null;
  }
  if ($from.parentOffset < $from.parent.content.size) return null;
  const pos = $from.after();
  return isLocked(state.doc.resolve(pos).nodeAfter) ? pos : null;
}

function handleKeyDown(view: EditorView, event: KeyboardEvent): boolean {
  const { state } = view;
  if (event.key !== 'Backspace' && event.key !== 'Delete' && event.key !== 'Enter') return false;
  const cleared = clearRange(state);
  if (cleared) {
    view.dispatch(
      cleared.inside && event.key !== 'Enter'
        ? state.tr.setSelection(NodeSelection.create(state.doc, cleared.inside.from))
        : cleared.tr
    );
    return true;
  }
  if (event.key === 'Enter') return false;
  const quotePos = adjacentQuote(state, event.key);
  if (quotePos === null) return false;
  view.dispatch(state.tr.setSelection(NodeSelection.create(state.doc, quotePos)).scrollIntoView());
  return true;
}

/** Drop the attribution from pasted quotes whose words this composer does not hold. */
function unlockUnknown(fragment: Fragment, known: ReadonlySet<string>): Fragment {
  const nodes: ProseMirrorNode[] = [];
  fragment.forEach((node) => {
    if (isLocked(node)) {
      nodes.push(
        known.has(quoteKey(node))
          ? node
          : node.type.create({ ...node.attrs, postId: null }, node.content, node.marks)
      );
    } else {
      nodes.push(node.isLeaf ? node : node.copy(unlockUnknown(node.content, known)));
    }
  });
  return Fragment.fromArray(nodes);
}

const quoteLockKey = new PluginKey<ReadonlySet<string>>('forumQuoteLock');

export const ForumQuoteLock = Extension.create({
  name: 'forumQuoteLock',
  // Before the keymaps that would join a paragraph into the quote.
  priority: 1000,
  addProseMirrorPlugins() {
    return [
      new Plugin<ReadonlySet<string>>({
        key: quoteLockKey,
        state: {
          // The quotes the document opened with. The Quote action remounts the
          // composer, so nothing legitimate adds one later; undo and a
          // cut-and-paste only bring these back.
          init: (_config, state) => new Set(lockedQuotes(state.doc).map((q) => quoteKey(q.node))),
          apply: (_tr, known) => known,
        },
        filterTransaction(tr, state) {
          if (!tr.docChanged) return true;
          const known = quoteLockKey.getState(state);
          return lockedQuotes(tr.doc).every((quote) => known?.has(quoteKey(quote.node)));
        },
        appendTransaction(transactions, oldState, newState) {
          const { selection } = newState;
          if (!selection.empty || !(selection instanceof TextSelection)) return null;
          const quote = quoteAround(newState.doc, selection.from);
          if (!quote) return null;
          // A caret moving up by keyboard goes above the quote; a click, or
          // anything from above, goes below it.
          const pointer = transactions.some((tr) => tr.getMeta('pointer'));
          const up = !pointer && oldState.selection.from >= quote.to;
          return moveOutOf(newState.tr, quote, up ? -1 : 1);
        },
        // ProseMirror writes the DOM selection only when the state's selection
        // changed, and a caret bounced straight back did not change it.
        view: () => ({
          update(view) {
            if (!view.hasFocus() || !view.state.selection.empty) return;
            const anchor = view.dom.ownerDocument.getSelection()?.anchorNode;
            const element = anchor instanceof Element ? anchor : anchor?.parentElement;
            const quote = element?.closest('blockquote[data-post-id]');
            if (quote && view.dom.contains(quote)) view.focus();
          },
        }),
        props: {
          handleKeyDown,
          handleTextInput(view, from, _to, text) {
            const cleared = clearRange(view.state);
            if (cleared) {
              view.dispatch(cleared.tr.insertText(text));
              return true;
            }
            // The browser's caret can still be in the quote when the state's
            // is not: keep what was typed, outside it.
            const quote = quoteAround(view.state.doc, from);
            if (!quote) return false;
            view.dispatch(moveOutOf(view.state.tr, quote, 1).insertText(text));
            return true;
          },
          handlePaste(view) {
            const cleared = clearRange(view.state);
            if (cleared) view.dispatch(cleared.tr);
            return false; // the paste itself goes on at the new caret
          },
          transformPasted(slice, view) {
            const known = quoteLockKey.getState(view.state) ?? new Set<string>();
            // A slice cut open through a quote must never keep its attribution:
            // it would merge into whatever it is pasted next to.
            const open = slice.openStart > 0 || slice.openEnd > 0;
            return new Slice(
              unlockUnknown(slice.content, open ? new Set() : known),
              slice.openStart,
              slice.openEnd
            );
          },
        },
      }),
    ];
  },
});
