import { useEditor, EditorContent, type Editor } from '@tiptap/react';
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
  Type,
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

/**
 * One key per file SELECTION, reused across retries of that selection, so the
 * backend's M36 replay path collapses a double-submit into a single stored
 * image instead of orphaning a duplicate row + file.
 *
 * `randomUUID` is unavailable on insecure origins and in some test DOMs, so
 * fall back rather than throwing — a missing key only costs the replay
 * guarantee, while an exception would break the upload outright.
 */
function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `forum-img-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * The position of the image node the user means, or null.
 *
 * `editor.isActive('image')` is NOT usable for this: it is only true for a
 * NodeSelection, and ProseMirror only falls back to one after an insert when no
 * text position exists nearby — i.e. only when the image is the entire
 * document. In any real post it is false, which is why gating the alt-edit
 * button on it made the button permanently disabled.
 */
function imagePosAt(editor: Editor): number | null {
  const { selection, doc } = editor.state;
  // Clicking a leaf node gives a NodeSelection.
  const selected = (selection as { node?: { type: { name: string } } }).node;
  if (selected?.type.name === 'image') return selection.from;
  // Just-inserted / caret adjacent.
  const { $from } = selection;
  if ($from.nodeBefore?.type.name === 'image') return $from.pos - $from.nodeBefore.nodeSize;
  if ($from.nodeAfter?.type.name === 'image') return $from.pos;
  // Otherwise: unambiguous only when the document holds exactly one image.
  const found: number[] = [];
  doc.descendants((node, pos) => {
    if (node.type.name === 'image') found.push(pos);
  });
  return found.length === 1 ? found[0] : null;
}

/**
 * An image `src` safe to render in the alt-text preview, or '' .
 *
 * The edit path reads `src` off a node in the live document, and a user can put
 * arbitrary markup there by pasting — so this is attacker-influenced DOM text
 * flowing into a rendered attribute (CodeQL js/xss-through-dom, high). React
 * does not sanitize `src`. Allowlist the three schemes that can legitimately
 * appear: http/https (a served rendition) and blob (our own createObjectURL
 * preview). Structural on purpose — code scanning ignores in-code suppression
 * comments, so an annotation would not have closed this.
 */
function safeImageSrc(src: string): string {
  try {
    const { protocol } = new URL(src, window.location.origin);
    return protocol === 'http:' || protocol === 'https:' || protocol === 'blob:' ? src : '';
  } catch {
    return '';
  }
}

/** The first image file on a paste/drop payload, or null. */
function imageFileFromTransfer(data: DataTransfer | null | undefined): File | null {
  if (!data) return null;
  const files = Array.from(data.files ?? []);
  return files.find((f) => f.type.startsWith('image/')) ?? null;
}

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
  // Assigned on every render (below) so ProseMirror's paste/drop handlers —
  // configured once, before `editor` exists — always invoke the CURRENT
  // closure rather than the first render's, where `editor` was still null.
  const handleImageFileRef = useRef<(file: File) => void>(() => {});

  const editor = useEditor({
    editorProps: {
      // Paste and drop route through the SAME validation gate as the toolbar
      // button (handleImageFile) — deliberately not a second upload path.
      // Returning true tells ProseMirror we handled it, which also stops it
      // inserting the raw file as a base64 <img> that no body block could
      // represent.
      handlePaste: (_view, event) => {
        const file = imageFileFromTransfer(event.clipboardData);
        if (!file) return false;
        event.preventDefault();
        handleImageFileRef.current(file);
        return true;
      },
      handleDrop: (view, event) => {
        const file = imageFileFromTransfer((event as DragEvent).dataTransfer);
        if (!file) return false;
        event.preventDefault();
        // Remember WHERE it was dropped. The upload resolves later, by which
        // point the selection is wherever the caret was — so without this an
        // image dropped at the end of a long unfocused post lands at the top.
        const dropped = view.posAtCoords({
          left: (event as DragEvent).clientX,
          top: (event as DragEvent).clientY,
        });
        dropPosRef.current = dropped ? dropped.pos : null;
        handleImageFileRef.current(file);
        return true;
      },
    },
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
  // A COUNT, not the boolean: `uploadingImage` is only what the spinner reads.
  // With a boolean, the first upload to settle cleared the flag while a second
  // was still in flight and re-opened the gate. A ref (not state) because
  // handleImageFile is also called from ProseMirror's paste/drop handlers,
  // which would otherwise read a stale closure.
  const uploadsInFlightRef = useRef(0);
  // The key of the last upload that FAILED, so re-picking that same file reuses
  // its Idempotency-Key. Without this every retry got a fresh key, which is
  // exactly what makes the server store a duplicate row and orphan a file —
  // the thing M36 exists to prevent.
  const failedUploadRef = useRef<{ signature: string; idempotencyKey: string } | null>(null);
  // Where a dropped file landed, so the image is inserted THERE rather than at
  // whatever the caret happened to be (dropping at the end of a long unfocused
  // post otherwise puts the image at the top).
  const dropPosRef = useRef<number | null>(null);
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
  // Alt-text prompt: null = closed. Two modes since the ImageBlock migration
  // (todo 357) made alt a PER-USAGE value stored in the body block:
  //
  //   'upload' — a new file. Alt is still collected before upload so the
  //              authored value also lands on Image.description as the row's
  //              default. `previewUrl` is an object URL that MUST be revoked
  //              (see closeAltPrompt) or every inserted image leaks a blob.
  //   'edit'   — an image already in the document. Re-authoring its alt is now
  //              a plain attribute update: no re-upload, no new row. That was
  //              impossible while alt lived only on the image row.
  const [altPrompt, setAltPrompt] = useState<
    | {
        kind: 'upload';
        file: File;
        previewUrl: string;
        alt: string;
        /** One key per file SELECTION, reused across retries of it (M36). */
        idempotencyKey: string;
      }
    | {
        kind: 'edit';
        src: string;
        alt: string;
        /** The node this prompt was opened FOR. Committing against the live
         *  selection instead would rewrite whichever image the user clicked
         *  while the prompt was open, with the preview still showing the
         *  original. */
        pos: number;
      }
    | null
  >(null);
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

  // The ONE validation gate for every way an image can enter the composer:
  // the toolbar's file picker, a paste, and a drop. Adding a route means
  // calling this, never re-implementing the checks.
  /** Identifies a file well enough to know it is "the same one" on a retry. */
  const fileSignature = (file: File) => `${file.name}:${file.size}:${file.lastModified}`;

  const handleImageFile = (file: File) => {
    if (!editor) return;
    // Paste and drop reach this too, so the in-flight gate lives HERE rather
    // than only on the toolbar button — otherwise pasting twice starts two
    // concurrent uploads and AC 4's "one request" does not hold.
    if (uploadsInFlightRef.current > 0) {
      setImageError('Wait for the current image to finish uploading.');
      return;
    }
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
    // Ask for alt text BEFORE uploading — the value rides the upload request so
    // it also becomes the image row's default description.
    closeAltPrompt(); // revoke a previous preview if one was somehow still open
    const previewUrl = URL.createObjectURL(file);
    previewUrlRef.current = previewUrl;
    // Same file as the last failed attempt -> same key, so the server replays
    // instead of storing a second row.
    const signature = fileSignature(file);
    const reuse =
      failedUploadRef.current?.signature === signature
        ? failedUploadRef.current.idempotencyKey
        : null;
    setAltPrompt({
      kind: 'upload',
      file,
      previewUrl,
      alt: '',
      idempotencyKey: reuse ?? newIdempotencyKey(),
    });
  };

  // Paste and drop reach the editor through ProseMirror's own handlers, which
  // were configured before this function existed — so they call through a ref
  // to always get the CURRENT closure (the one with a non-null `editor`).
  // Assigned in an effect, not during render (react-hooks/refs): both events
  // are user-driven and therefore always fire after an effect flush, so the
  // ref is current by the time either handler reads it.
  useEffect(() => {
    handleImageFileRef.current = handleImageFile;
  });

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow re-selecting the same file after an error
    if (!file) return;
    handleImageFile(file);
  };

  /** Re-author an image's alt — no re-upload. */
  const openAltEditor = () => {
    if (!editor) return;
    const pos = imagePosAt(editor);
    if (pos === null) {
      // Deliberately a message rather than a disabled button: `isActive('image')`
      // is false in every document that is not JUST the image, and this
      // component does not re-render on selection-only transactions, so a
      // disabled gate would be both wrong and permanently stuck.
      setImageError('Select an image first to edit its alt text.');
      return;
    }
    setImageError(null);
    closeAltPrompt();
    const node = editor.state.doc.nodeAt(pos);
    const attrs = (node?.attrs ?? {}) as Record<string, unknown>;
    setAltPrompt({
      kind: 'edit',
      pos,
      // Sanitised at the boundary, where it enters component state.
      src: typeof attrs.src === 'string' ? safeImageSrc(attrs.src) : '',
      alt: typeof attrs.alt === 'string' ? attrs.alt : '',
    });
  };

  // Commit the prompt. `alt` is passed explicitly so the Skip path sends "" no
  // matter what is typed — a decorative image is correctly alt="", and empty
  // must never block posting. A blank alt IS the decorative declaration.
  const commitAltPrompt = async (alt: string) => {
    if (!altPrompt || !editor) return;
    const trimmed = alt.trim();
    const decorative = trimmed === '';

    if (altPrompt.kind === 'edit') {
      const { pos } = altPrompt;
      closeAltPrompt();
      // Target the node the prompt was OPENED for, via its captured position —
      // not the live selection, which the user may have moved to another image
      // while the prompt (still showing the first one's preview) was open.
      editor
        .chain()
        .focus()
        .command(({ tr }) => {
          const node = tr.doc.nodeAt(pos);
          if (!node || node.type.name !== 'image') return false;
          tr.setNodeMarkup(pos, undefined, { ...node.attrs, alt: trimmed, decorative });
          return true;
        })
        .run();
      return;
    }

    const { file, idempotencyKey } = altPrompt;
    const signature = fileSignature(file);
    const insertAt = dropPosRef.current;
    dropPosRef.current = null;
    closeAltPrompt();
    uploadsInFlightRef.current += 1;
    setUploadingImage(true);
    try {
      const image = await uploadPostImage(file, trimmed, idempotencyKey);
      failedUploadRef.current = null;
      const attrs = {
        // alt/decorative come from what the AUTHOR typed, not the response:
        // an idempotent replay returns the ORIGINAL alt (the server excludes
        // alt from the fingerprint on purpose), which would silently discard
        // a correction made on the retry.
        src: image.url,
        alt: trimmed,
        decorative,
        imageId: image.id,
      };
      // insertContent (not setImage) so the custom attrs ride along.
      const chain = editor.chain().focus();
      if (insertAt !== null) {
        chain.insertContentAt(insertAt, { type: 'image', attrs });
      } else {
        chain.insertContent({ type: 'image', attrs });
      }
      chain.run();
    } catch (err) {
      logger.error('[forum] image upload failed', err);
      // Remember the key so re-picking THIS file retries under it rather than
      // minting a new one (which would store a duplicate server-side).
      failedUploadRef.current = { signature, idempotencyKey };
      setImageError(err instanceof Error ? err.message : 'Image upload failed');
    } finally {
      uploadsInFlightRef.current -= 1;
      setUploadingImage(uploadsInFlightRef.current > 0);
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

          <ToolbarButton
            onClick={() => fileInputRef.current?.click()}
            // Disabled while a upload is in flight: without this a second
            // activation reopens the picker mid-upload and starts a concurrent
            // request, so AC 4's "one multipart request" would not hold. Matches
            // the AI button's shape below.
            disabled={uploadingImage}
            title={uploadingImage ? 'Uploading image…' : 'Insert image'}
          >
            {uploadingImage ? (
              <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ImageIcon className="h-4 w-4" aria-hidden="true" />
            )}
          </ToolbarButton>

          {/* Re-author an inserted image's alt (todo 357). Only reachable while
              the caret is on an image — and only possible at all because
              ImageBlock moved alt onto the USAGE; under ImageChooserBlock this
              would have meant re-uploading the file. */}
          <ToolbarButton onClick={openAltEditor} title="Edit image alt text">
            <Type className="h-4 w-4" aria-hidden="true" />
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

      {/* Alt-text prompt. On upload it is collected before the request so the
          value also becomes the image row's default description; on edit it
          rewrites the node's attribute with no upload at all (todo 357).
          "Skip" is a first-class choice: a decorative image is correctly
          alt="", and empty must never block posting. */}
      {editable && altPrompt !== null && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line-2 bg-surface p-2">
          <img
            src={altPrompt.kind === 'upload' ? altPrompt.previewUrl : safeImageSrc(altPrompt.src)}
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
                  void commitAltPrompt(altPrompt.alt);
                } else if (e.key === 'Escape') {
                  // Escape SKIPS (commits with no alt, i.e. decorative); it
                  // does not cancel — the user already chose this image.
                  void commitAltPrompt('');
                }
              }}
              placeholder="e.g. A monstera leaf with brown edges"
              aria-describedby="tiptap-image-alt-hint"
              className="min-h-11 w-full rounded-sm border border-line-2 bg-surface px-3 text-sm text-ink"
            />
            <span id="tiptap-image-alt-hint" className="text-xs text-ink-3">
              Helps people using screen readers. Leave blank if the image is decorative — you can
              change this later with the toolbar&apos;s alt-text button.
            </span>
          </div>
          <button
            type="button"
            onClick={() => void commitAltPrompt(altPrompt.alt)}
            className="min-h-11 rounded-xs bg-primary/20 px-3 text-sm font-medium text-ink"
          >
            {altPrompt.kind === 'edit' ? 'Save alt text' : 'Add image'}
          </button>
          <button
            type="button"
            onClick={() => void commitAltPrompt('')}
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
