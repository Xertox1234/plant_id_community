import { useEditor, EditorContent, Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import { ReactNode, useEffect, useRef, useState } from 'react';
import { uploadPostImage } from '../../services/forumService';
import { logger } from '../../utils/logger';
import { ForumImage } from './forumImageNode';

interface TipTapEditorProps {
  content?: string;
  onChange?: (html: string) => void;
  placeholder?: string;
  editable?: boolean;
  className?: string;
}

/**
 * TipTapEditor Component
 *
 * Rich text editor for forum posts using TipTap.
 * Provides basic formatting, links, and sanitization.
 */
export default function TipTapEditor({
  content = '',
  onChange,
  placeholder = 'Write your post...',
  editable = true,
  className = '',
}: TipTapEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [2, 3], // Only H2 and H3
        },
        // Disable the default Link from StarterKit to avoid duplicate
        link: false,
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-primary hover:underline',
          target: '_blank',
          rel: 'noopener noreferrer',
        },
      }),
      Placeholder.configure({
        placeholder,
      }),
      ForumImage,
    ],
    content,
    editable,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange?.(html);
    },
  });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);

  const handleImageSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-selecting the same file after an error
    if (!file || !editor) return;
    setImageError(null);
    setUploadingImage(true);
    try {
      const image = await uploadPostImage(file);
      // insertContent (not setImage) so the custom imageId attr rides along.
      editor
        .chain()
        .focus()
        .insertContent({
          type: 'image',
          attrs: { src: image.url, alt: image.alt, imageId: image.id },
        })
        .run();
    } catch (err) {
      logger.error('[forum] image upload failed', err);
      setImageError(err instanceof Error ? err.message : 'Image upload failed');
    } finally {
      setUploadingImage(false);
    }
  };

  // Cleanup: Destroy editor instance on unmount to prevent memory leak
  useEffect(() => {
    return () => {
      if (editor) {
        editor.destroy();
      }
    };
  }, [editor]);

  if (!editor) {
    return <div className="p-4 text-ink-3">Loading editor...</div>;
  }

  return (
    <div className={`border border-line-2 rounded-lg overflow-hidden ${className}`}>
      {/* Toolbar */}
      {editable && (
        <div className="bg-surface border-b border-line-2 p-2 flex gap-1 flex-wrap">
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            isActive={editor.isActive('bold')}
            title="Bold (Ctrl+B)"
          >
            <strong>B</strong>
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            isActive={editor.isActive('italic')}
            title="Italic (Ctrl+I)"
          >
            <em>I</em>
          </ToolbarButton>

          {/* Strike / headings / blockquote / code-block are intentionally
              omitted: the server's nh3 allowlist keeps only bold, italic, links,
              lists and inline code, so those marks would silently flatten to
              plain text (Spec 2 PR-3). */}

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            isActive={editor.isActive('bulletList')}
            title="Bullet List"
          >
            •
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            isActive={editor.isActive('orderedList')}
            title="Numbered List"
          >
            1.
          </ToolbarButton>

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCode().run()}
            isActive={editor.isActive('code')}
            title="Inline Code"
          >
            {'</>'}
          </ToolbarButton>

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => {
              const url = window.prompt('Enter URL:');
              if (url) {
                editor.chain().focus().setLink({ href: url }).run();
              }
            }}
            isActive={editor.isActive('link')}
            title="Insert Link"
          >
            🔗
          </ToolbarButton>

          {editor.isActive('link') && (
            <ToolbarButton
              onClick={() => editor.chain().focus().unsetLink().run()}
              title="Remove Link"
            >
              ⛓️‍💥
            </ToolbarButton>
          )}

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton onClick={() => fileInputRef.current?.click()} title="Insert image">
            {uploadingImage ? '⏳' : '🖼️'}
          </ToolbarButton>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            data-testid="forum-image-input"
            onChange={handleImageSelect}
          />
        </div>
      )}

      {imageError && (
        <p className="bg-surface border-b border-line-2 px-3 py-2 text-sm text-error" role="alert">
          {imageError}
        </p>
      )}

      {/* Editor Content */}
      <EditorContent
        editor={editor}
        className="prose max-w-none p-4 min-h-[200px] focus:outline-none dark:prose-invert"
      />
    </div>
  );
}

// Toolbar button component
interface ToolbarButtonProps {
  onClick: () => void;
  isActive?: boolean;
  title?: string;
  children: ReactNode;
}

function ToolbarButton({ onClick, isActive, title, children }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      type="button"
      title={title}
      // Glyph children ("B", "•") would otherwise BE the accessible name —
      // title never wins name-from-content (AccName 1.2; audit 2026-07-11 H19).
      aria-label={title}
      className={`
        px-3 py-1.5 rounded text-sm font-medium transition-colors
        ${isActive ? 'bg-primary/20 text-ink' : 'bg-surface-2 text-ink-2 hover:bg-surface-3'}
      `}
    >
      {children}
    </button>
  );
}
