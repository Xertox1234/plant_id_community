import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import { ReactNode, useEffect, useRef, useState } from 'react';
import {
  Bold,
  Code,
  Image as ImageIcon,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  LoaderCircle,
  Quote,
  Sparkles,
  Unlink,
} from 'lucide-react';
import {
  ComposeAssistError,
  improveDraft,
  isComposeAssistUnavailable,
  markComposeAssistUnavailable,
  uploadPostImage,
} from '../../services/forumService';
import { logger } from '../../utils/logger';
import { ForumBlockquoteAttrs } from './forumBlockquoteAttrs';
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
      // Quoted-post id on blockquotes (todo 342) — see forumBlockquoteAttrs.
      ForumBlockquoteAttrs,
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
  // Alt-text prompt (M7): null = closed. Collected BEFORE upload so the authored
  // value rides the one multipart request — there is no alt PATCH endpoint, and
  // htmlToBodyBlocks drops the editor node's alt on write, so upload time is the
  // only moment the value can be captured. `previewUrl` is an object URL that
  // MUST be revoked (see closeAltPrompt) or every inserted image leaks a blob.
  const [altPrompt, setAltPrompt] = useState<{
    file: File;
    previewUrl: string;
    alt: string;
  } | null>(null);
  // The live preview URL, mirrored in a ref because the unmount cleanup below
  // cannot read it from state: React DISCARDS a setState on an unmounting
  // component without ever invoking the updater, so revoking inside a
  // functional updater silently does nothing on that path (measured: 0 calls).
  // A ref is a plain object and is still readable during cleanup.
  const previewUrlRef = useRef<string | null>(null);

  // Close the alt prompt and release its object URL. Every exit path — confirm,
  // skip, Escape, unmount — must go through here or the blob leaks.
  const closeAltPrompt = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setAltPrompt(null);
  };

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
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
    // Ask for alt text BEFORE uploading (M7) — the value has to ride the upload
    // request, so there is no second chance to collect it.
    closeAltPrompt(); // revoke a previous preview if one was somehow still open
    const previewUrl = URL.createObjectURL(file);
    previewUrlRef.current = previewUrl;
    setAltPrompt({ file, previewUrl, alt: '' });
  };

  // Upload the pending image and insert it. `alt` is passed explicitly so the
  // Skip path sends "" rather than whatever happens to be typed — an empty alt
  // is a legitimate choice (decorative image) and must never block posting.
  const uploadPendingImage = async (alt: string) => {
    if (!altPrompt || !editor) return;
    const { file } = altPrompt;
    closeAltPrompt();
    setUploadingImage(true);
    try {
      const image = await uploadPostImage(file, alt);
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

  // Release a pending alt-prompt preview if the composer unmounts while it is
  // open — e.g. navigating away mid-prompt (this editor is also remounted via
  // `key=` after every reply). Reads the ref, not state: see previewUrlRef.
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
    };
  }, []);

  if (!editor) {
    return <div className="p-4 text-ink-3">Loading editor...</div>;
  }

  return (
    <div className={`border border-line-2 rounded-sm overflow-hidden ${className}`}>
      {/* Toolbar */}
      {editable && (
        <div className="bg-surface border-b border-line-2 p-2 flex gap-1 flex-wrap">
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            isActive={editor.isActive('bold')}
            title="Bold (Ctrl+B)"
          >
            <Bold className="h-4 w-4" aria-hidden="true" />
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            isActive={editor.isActive('italic')}
            title="Italic (Ctrl+I)"
          >
            <Italic className="h-4 w-4" aria-hidden="true" />
          </ToolbarButton>

          {/* Strike / headings / code-block are intentionally omitted: the
              server's nh3 allowlist keeps only bold, italic, links, lists and
              inline code, so those marks would silently flatten to plain text
              (Spec 2 PR-3). Blockquote is the exception — see the Quote button
              below: it is not kept as inline markup either, but a TOP-LEVEL
              blockquote is lifted out into its own `quote` StreamField block by
              forumBody.ts, so it survives the round-trip (todo 276 / M1). */}

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            isActive={editor.isActive('bulletList')}
            title="Bullet List"
          >
            <List className="h-4 w-4" aria-hidden="true" />
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            isActive={editor.isActive('orderedList')}
            title="Numbered List"
          >
            <ListOrdered className="h-4 w-4" aria-hidden="true" />
          </ToolbarButton>

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            isActive={editor.isActive('blockquote')}
            title="Quote"
          >
            <Quote className="h-4 w-4" aria-hidden="true" />
          </ToolbarButton>

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCode().run()}
            isActive={editor.isActive('code')}
            title="Inline Code"
          >
            <Code className="h-4 w-4" aria-hidden="true" />
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
            <LinkIcon className="h-4 w-4" aria-hidden="true" />
          </ToolbarButton>

          {editor.isActive('link') && (
            <ToolbarButton
              onClick={() => editor.chain().focus().unsetLink().run()}
              title="Remove Link"
            >
              <Unlink className="h-4 w-4" aria-hidden="true" />
            </ToolbarButton>
          )}

          <div className="w-px bg-line-2 mx-1" aria-hidden="true" />

          <ToolbarButton onClick={() => fileInputRef.current?.click()} title="Insert image">
            {uploadingImage ? (
              <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ImageIcon className="h-4 w-4" aria-hidden="true" />
            )}
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
            {aiWorking ? (
              <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="h-4 w-4" aria-hidden="true" />
            )}
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

      {/* Alt-text prompt (M7) — collected before upload, because the value has
          to ride the multipart request. "Skip" is a first-class choice: a
          decorative image is correctly alt="", and empty must never block
          posting. */}
      {editable && altPrompt !== null && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line-2 bg-surface p-2">
          <img
            src={altPrompt.previewUrl}
            alt=""
            className="h-14 w-14 shrink-0 rounded-xs object-cover"
          />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label htmlFor="tiptap-image-alt" className="text-sm font-medium text-ink">
              Describe this image
            </label>
            <input
              id="tiptap-image-alt"
              type="text"
              autoFocus
              maxLength={255}
              value={altPrompt.alt}
              onChange={(e) =>
                setAltPrompt((current) => (current ? { ...current, alt: e.target.value } : current))
              }
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void uploadPendingImage(altPrompt.alt);
                } else if (e.key === 'Escape') {
                  // Escape SKIPS (uploads with no alt); it does not cancel the
                  // insert — the user already chose to add this image.
                  void uploadPendingImage('');
                }
              }}
              placeholder="e.g. A monstera leaf with brown edges"
              aria-describedby="tiptap-image-alt-hint"
              className="min-h-11 w-full rounded-sm border border-line-2 bg-surface px-3 text-sm text-ink"
            />
            <span id="tiptap-image-alt-hint" className="text-xs text-ink-3">
              Helps people using screen readers. Leave blank if the image is decorative. This can
              only be set now — to change it later, remove the image and add it again.
            </span>
          </div>
          <button
            type="button"
            onClick={() => void uploadPendingImage(altPrompt.alt)}
            className="min-h-11 rounded-xs bg-primary/20 px-3 text-sm font-medium text-ink"
          >
            Add image
          </button>
          <button
            type="button"
            onClick={() => void uploadPendingImage('')}
            className="min-h-11 rounded-xs px-3 text-sm text-ink-2"
          >
            Skip
          </button>
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
            className="min-h-11 flex-1 rounded-sm border border-line-2 bg-surface px-3 text-sm text-ink"
          />
          <button
            type="button"
            onClick={applyLink}
            className="min-h-11 rounded-xs bg-primary/20 px-3 text-sm font-medium text-ink"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={() => {
              setLinkDraft(null);
              setLinkError(null);
            }}
            className="min-h-11 rounded-xs px-3 text-sm text-ink-2"
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
        inline-flex min-h-11 min-w-11 items-center justify-center rounded-xs px-3 text-sm font-medium transition-colors
        disabled:cursor-not-allowed disabled:opacity-50
        ${isActive ? 'bg-primary/20 text-ink' : 'bg-surface-2 text-ink-2 hover:bg-surface-3'}
      `}
    >
      {children}
    </button>
  );
}
