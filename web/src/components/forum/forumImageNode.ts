import Image from '@tiptap/extension-image';

/**
 * TipTap image node that carries the wagtail image id as `data-image-id`. The
 * body serializer (utils/forumBody) reads that id to emit a backend `image`
 * block; the rest of the <img> (src/alt) is display-only in the composer.
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
    };
  },
});
