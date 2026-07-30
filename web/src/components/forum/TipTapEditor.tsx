import { useEditor, EditorContent, Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import { ReactNode, useEffect, useRef, useState } from 'react';
import {
  ComposeAssistError,
  improveDraft,
  isComposeAssistUnavailable,
  markComposeAssistUnavailable,
  uploadPostImage,
} from '../../services/forumService';
import { logger } from '../../utils/logger';
import { ForumImage } from './forumImageNode';
import { ForumMention } from './forumMentionNode';

// Client-side pre-upload limits — mirror wagtail_forum conf.py
// (IMAGE_MAX_SIZE_BYTES, IMAGE_ALLOWED_MIME_TYPES). Defense-in-depth: the
// server re-validates, but a fast local check avoids a wasted round-trip (M29).
const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
const IMAGE_LIMIT_HINT = 'JPEG, PNG, GIF or WebP, up to 10 MB';

/** Allow only http(s), mailto, or site-relative link targets (blocks javascript: etc.). */
function isAllowedLinkHref(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return false;
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) return true;
  try {
    return ['http:', 'https:', 'mailto:'].includes(new URL(trimmed).protocol);
  } catch {
    return false;
  }
}

interface TipTapEditorProps {
  content?: string;
  onChange?: (html: string) => void;
  placeholder?: string;
  editable?: boolean;
  className?: string;
  /** Focus the editor once it mounts — used to restore focus after posting (M25). */
  autoFocus?: boolean;
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
  autoFocus = false,
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
      ForumMention,
    ],
    content,
    editable,
    // TipTap applies this at creation; the composer remounts (key change) after
    // a reply, so a fresh instance with autoFocus lands the caret in it (M25).
    autofocus: autoFocus ? 'end' : false,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange?.(html);
    },
  });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  // AI assist (M14). `aiUnavailable` latches on a 403/503 so a user who cannot
  // use the feature (non-premium, or a deployment with the flag off) is not left
  // clicking a permanently dead button. Seeded from the service's session-scoped
  // latch, not just local state: this composer is REMOUNTED after every reply
  // (`key={composerKey}` in ThreadDetailPage), which would otherwise reset the
  // flag and re-offer the failing button on each one.
  const [aiWorking, setAiWorking] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiUnavailable, setAiUnavailable] = useState(isComposeAssistUnavailable);
  // Link editor: null = closed; a string is the in-progress href (styled input
  // that replaces the native window.prompt — M24).
  const [linkDraft, setLinkDraft] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);

  const handleImageSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-selecting the same file after an error
    if (!file || !editor) return;
    setImageError(null);
    // Client-side pre-check (M29) — fail fast on type/size before uploading.
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setImageError(`Unsupported image type. ${IMAGE_LIMIT_HINT}.`);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError(`Image is too large — ${IMAGE_LIMIT_HINT}.`);
      return;
    }
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

  // Ask the backend to rewrite the draft, then swap it in as PLAIN TEXT (M14).
  //
  // Plain text, not `insertContent(html)`: that parses its string argument as
  // HTML, so any markup a model emitted would become real document structure in
  // a post the user then publishes. Building paragraph nodes with `text` content
  // means model output can only ever be characters.
  //
  // The whole document is replaced in ONE chain, so it is a single undo step —
  // Ctrl+Z restores the original draft, which is what makes replacing (rather
  // than appending a second copy) safe. Note the rewrite is text-only, so any
  // images or link marks in the draft are dropped; undo is the escape hatch.
  const handleAiAssist = async () => {
    if (!editor || aiWorking) return;
    setAiError(null);
    const draft = editor.getHTML();
    setAiWorking(true);
    try {
      const improved = await improveDraft(draft);
      const paragraphs = improved
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => ({ type: 'paragraph', content: [{ type: 'text', text: line }] }));
      if (paragraphs.length === 0) {
        setAiError('AI assist returned nothing.');
        return;
      }
      // `scrollIntoView: false`: replacing the whole document would otherwise
      // scroll-jump the page to the caret right after a click the user made on
      // the toolbar directly above it. (It also keeps jsdom out of
      // prosemirror's `coordsAtPos`, which has no `getClientRects` there and
      // throws an unhandled error that fails the Vitest run.)
      editor
        .chain()
        .focus(null, { scrollIntoView: false })
        .selectAll()
        .insertContent(paragraphs)
        .run();
    } catch (err) {
      logger.error('[forum] AI compose assist failed', err);
      setAiError(err instanceof Error ? err.message : 'AI assist failed');
      // 403 (not premium) / 503 (disabled or provider down) can never succeed on
      // a retry from this session — stop offering the button, and remember it past
      // this composer's lifetime (it is remounted after every reply).
      if (err instanceof ComposeAssistError && err.permanent) {
        markComposeAssistUnavailable();
        setAiUnavailable(true);
      }
    } finally {
      setAiWorking(false);
    }
  };

  // Apply the link editor's URL: empty removes the link; an invalid target is
  // rejected with a message rather than silently linked (M24).
  const applyLink = () => {
    if (linkDraft === null || !editor) return;
    const href = linkDraft.trim();
    if (!href) {
      editor.chain().focus().unsetLink().run();
      setLinkDraft(null);
      setLinkError(null);
      return;
    }
    if (!isAllowedLinkHref(href)) {
      setLinkError('Enter a valid http(s), mailto:, or /relative link.');
      return;
    }
    editor.chain().focus().setLink({ href }).run();
    setLinkDraft(null);
    setLinkError(null);
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
              setLinkError(null);
              setLinkDraft(editor.getAttributes('link').href ?? '');
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

          {/* AI draft improvement (M14) — premium perk, server-gated. Once the
              server says this account/deployment can never use it, the button stays
              MOUNTED but permanently disabled rather than disappearing: unmounting
              a control the user just activated drops keyboard focus to <body> with
              nothing to return to, and shifts the toolbar under the pointer. */}
          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />
          <ToolbarButton
            onClick={handleAiAssist}
            disabled={aiWorking || aiUnavailable || editor.isEmpty}
            title={
              aiUnavailable
                ? 'AI assist is not available for this account'
                : aiWorking
                  ? 'Improving draft…'
                  : 'Improve draft with AI (premium; undo to revert)'
            }
          >
            {aiWorking ? '⏳' : '✨'}
          </ToolbarButton>
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_IMAGE_TYPES.join(',')}
            className="hidden"
            data-testid="forum-image-input"
            onChange={handleImageSelect}
          />
        </div>
      )}

      {/* Link editor — styled replacement for window.prompt (M24), with
          validation (M24: the prompt applied any string unvalidated). */}
      {editable && linkDraft !== null && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line-2 bg-surface p-2">
          <label htmlFor="tiptap-link-url" className="sr-only">
            Link URL
          </label>
          <input
            id="tiptap-link-url"
            type="url"
            autoFocus
            value={linkDraft}
            onChange={(e) => setLinkDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                applyLink();
              } else if (e.key === 'Escape') {
                setLinkDraft(null);
                setLinkError(null);
              }
            }}
            placeholder="https://example.com"
            aria-invalid={!!linkError}
            className="min-h-11 flex-1 rounded border border-line-2 bg-surface-1 px-3 text-sm text-ink"
          />
          <button
            type="button"
            onClick={applyLink}
            className="min-h-11 rounded bg-primary/20 px-3 text-sm font-medium text-ink"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={() => {
              setLinkDraft(null);
              setLinkError(null);
            }}
            className="min-h-11 rounded px-3 text-sm text-ink-2"
          >
            Cancel
          </button>
          {linkError && <span className="w-full text-sm text-error">{linkError}</span>}
        </div>
      )}

      {/* Image upload limits hint (M29). */}
      {editable && (
        <p className="border-b border-line-2 bg-surface px-3 py-1 text-xs text-ink-3">
          Images: {IMAGE_LIMIT_HINT}
        </p>
      )}

      {/* Upload error — persistent live region so a screen reader reads the text
          swap; a conditionally-mounted role node generally is not announced (M26). */}
      <p
        aria-live="assertive"
        aria-atomic="true"
        className={
          imageError ? 'bg-surface border-b border-line-2 px-3 py-2 text-sm text-error' : 'sr-only'
        }
      >
        {imageError}
      </p>

      {/* AI assist error — same persistent-live-region shape as the upload error
          above (M26), so a screen reader announces the text swap. This is the only
          place a "requires a premium account" / "not enabled" reason is surfaced. */}
      <p
        aria-live="polite"
        aria-atomic="true"
        className={
          aiError ? 'bg-surface border-b border-line-2 px-3 py-2 text-sm text-error' : 'sr-only'
        }
      >
        {aiError}
      </p>

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
  disabled?: boolean;
  children: ReactNode;
}

function ToolbarButton({ onClick, isActive, title, disabled, children }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      type="button"
      disabled={disabled}
      title={title}
      // Glyph children ("B", "•") would otherwise BE the accessible name —
      // title never wins name-from-content (AccName 1.2; audit 2026-07-11 H19).
      aria-label={title}
      // min-h-11/min-w-11 = 44px WCAG 2.5.5 tap target (audit L10; was ~32px).
      className={`
        inline-flex min-h-11 min-w-11 items-center justify-center rounded px-3 text-sm font-medium transition-colors
        disabled:cursor-not-allowed disabled:opacity-50
        ${isActive ? 'bg-primary/20 text-ink' : 'bg-surface-2 text-ink-2 hover:bg-surface-3'}
      `}
    >
      {children}
    </button>
  );
}
