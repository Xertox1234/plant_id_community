import type { AnyExtension } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Mention from '@tiptap/extension-mention';
import { ForumBlockquoteAttrs } from './forumBlockquoteAttrs';
import { ForumImage } from './forumImageNode';

/**
 * The forum composer's document schema, in ONE place (todo 526).
 *
 * The composer's content contract is TipTap JSON: the editor takes a JSON
 * document and reports `getJSON()`, and utils/forumBody converts between that
 * document and the API's body blocks. The paragraph branches still cross an
 * HTML boundary (a `paragraph` block's value IS server-sanitized HTML), and
 * TipTap's `generateJSON` / `generateHTML` drop any node or attribute the
 * schema does not know. So the serializer must parse and print with exactly
 * the schema the live editor uses: a stored mention would otherwise vanish on
 * rehydrate, and a different Link config would change the paragraph HTML the
 * editor's own `getHTML()` produced before this change.
 *
 * Only schema-bearing extensions live here. Placeholder and the editor's
 * paste/drop props add no node, mark or attribute, so they stay in
 * TipTapEditor. The mention node is a parameter because the editor's one
 * carries the live suggestion dropdown (which imports forumService), while
 * the serializer needs the same node without it — `forumService` imports
 * nothing from here at runtime, and must not.
 */

/** The Link mark's rendered attributes — part of the paragraph HTML contract. */
export const FORUM_LINK_HTML_ATTRIBUTES = {
  class: 'text-primary hover:underline',
  target: '_blank',
  rel: 'noopener noreferrer',
};

/** The mention node's rendered attributes, shared with forumMentionNode. */
export const FORUM_MENTION_HTML_ATTRIBUTES = {
  class: 'text-primary font-medium',
};

/**
 * The composer's schema extensions, with `mention` as the mention node. The
 * editor passes its suggestion-wired ForumMention; FORUM_SCHEMA_EXTENSIONS
 * passes a schema-identical one without the dropdown.
 */
export function forumComposerExtensions(mention: AnyExtension): AnyExtension[] {
  return [
    StarterKit.configure({
      heading: {
        levels: [2, 3], // Only H2 and H3
      },
      // Disable the default Link from StarterKit to avoid duplicate
      link: false,
    }),
    Link.configure({
      openOnClick: false,
      HTMLAttributes: FORUM_LINK_HTML_ATTRIBUTES,
    }),
    ForumImage,
    mention,
    // Quoted-post id on blockquotes (todo 342) — see forumBlockquoteAttrs.
    ForumBlockquoteAttrs,
  ];
}

/** The schema the body serializer parses and prints with (utils/forumBody). */
export const FORUM_SCHEMA_EXTENSIONS: AnyExtension[] = forumComposerExtensions(
  Mention.configure({ HTMLAttributes: FORUM_MENTION_HTML_ATTRIBUTES })
);
