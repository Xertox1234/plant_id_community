import Image from '@tiptap/extension-image';

/**
 * TipTap image node that carries the wagtail image id as `data-image-id` and
 * the decorative flag as `data-decorative`. The body serializer
 * (utils/forumBody) reads both, plus the node's own `alt`, to emit a backend
 * `image` block.
 *
 * Since the ImageBlock migration (todo 357) `alt` is NO LONGER display-only:
 * it belongs to the usage and is persisted with the block, which is what makes
 * alt editable after insert without re-uploading the image. `src` stays
 * display-only — the backend re-derives the rendition URL.
 *
 * Lives in its own module (not TipTapEditor.tsx) so the editor file can stay a
 * components-only export for react-refresh.
 */
export const ForumImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      imageId: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-image-id'),
        renderHTML: (attributes) =>
          attributes.imageId ? { 'data-image-id': attributes.imageId } : {},
      },
      // Stored as the string "true"/absent rather than a boolean, because this
      // round-trips through real DOM attributes on the way in and out.
      decorative: {
        default: false,
        parseHTML: (element) => element.getAttribute('data-decorative') === 'true',
        renderHTML: (attributes) => (attributes.decorative ? { 'data-decorative': 'true' } : {}),
      },
    };
  },
});
