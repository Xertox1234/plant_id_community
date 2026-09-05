import { Extension } from '@tiptap/react';

/**
 * Lets the composer's blockquote carry a quoted post id as `data-post-id`
 * (todo 342). The body serializer (utils/forumBody) turns such a blockquote
 * into a `post_quote` block and writes one back with the attribute on
 * re-edit; without this, ProseMirror's schema drops the unknown attribute on
 * parse and every quote silently degrades to a free-form `quote`.
 *
 * A global attribute on StarterKit's own `blockquote` node rather than a
 * re-declared Blockquote: `@tiptap/extension-blockquote` is only a transitive
 * dependency here, and `addGlobalAttributes` attaches to the existing type by
 * name (verified against the installed `@tiptap/core` — the same merge path
 * TextAlign uses). Keeps the toolbar's toggleBlockquote/isActive untouched.
 *
 * Lives in its own module (not TipTapEditor.tsx) so the editor file can stay a
 * components-only export for react-refresh, and so the forumBody round-trip
 * test can build a headless editor with exactly this extension.
 */
export const ForumBlockquoteAttrs = Extension.create({
  name: 'forumBlockquoteAttrs',
  addGlobalAttributes() {
    return [
      {
        types: ['blockquote'],
        attributes: {
          postId: {
            default: null,
            parseHTML: (element) => element.getAttribute('data-post-id'),
            renderHTML: (attributes) =>
              attributes.postId ? { 'data-post-id': attributes.postId } : {},
          },
        },
      },
    ];
  },
});
