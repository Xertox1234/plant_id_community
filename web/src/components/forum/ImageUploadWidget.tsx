import { useState, useRef, useEffect, ChangeEvent, DragEvent, KeyboardEvent } from 'react';
import { uploadPostImage, deletePostImage, reorderPostImages } from '../../services/forumService';
import Button from '../ui/Button';
import { logger } from '../../utils/logger';
import {
  MAX_IMAGES,
  MAX_FILE_SIZE,
  ALLOWED_IMAGE_TYPES,
  MAX_IMAGES_ERROR,
  FILE_SIZE_ERROR,
  INVALID_TYPE_ERROR,
  MAX_FILE_SIZE_MB
} from '../../utils/constants';
import type { Attachment } from '@/types';

interface ImageUploadWidgetProps {
  postId: string;
  attachments?: Attachment[];
  onUploadComplete?: (attachment: Attachment) => void;
  onDeleteComplete?: (attachmentId: string) => void;
  onReorderComplete?: (attachments: Attachment[]) => void;
}

function getAttachmentImageUrl(attachment: Attachment): string {
  return attachment.thumbnail_url || attachment.image_thumbnail || attachment.thumbnail || attachment.image_url || attachment.image || '';
}

/**
 * ImageUploadWidget Component
 *
 * Drag-and-drop image upload widget for forum posts.
 *
 * Features:
 * - Drag and drop support
 * - File input fallback
 * - Image preview with thumbnails
 * - Delete uploaded images
 * - Validation (max 6 images, 10MB per image, image types only)
 * - Progress indication
 */
export default function ImageUploadWidget({
  postId,
  attachments = [],
  onUploadComplete,
  onDeleteComplete,
  onReorderComplete,
}: ImageUploadWidgetProps) {
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [reordering, setReordering] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [orderedAttachments, setOrderedAttachments] = useState<Attachment[]>(attachments);
  const [draggedAttachmentId, setDraggedAttachmentId] = useState<string | null>(null);
  const [dragOverAttachmentId, setDragOverAttachmentId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isUploadDisabled = uploading || attachments.length >= MAX_IMAGES;

  useEffect(() => {
    setOrderedAttachments(attachments);
  }, [attachments]);

  /**
   * Validate image file
   */
  const validateFile = (file: File, selectedCount: number): void => {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type as typeof ALLOWED_IMAGE_TYPES[number])) {
      throw new Error(INVALID_TYPE_ERROR);
    }

    if (file.size > MAX_FILE_SIZE) {
      throw new Error(FILE_SIZE_ERROR);
    }

    if (attachments.length + selectedCount > MAX_IMAGES) {
      throw new Error(MAX_IMAGES_ERROR);
    }
  };

  /**
   * Handle file selection or drop
   */
  const handleFiles = async (files: File[]): Promise<void> => {
    setError(null);

    if (uploading) return;

    if (files.length === 0) return;

    const remainingSlots = MAX_IMAGES - attachments.length;
    if (remainingSlots <= 0 || files.length > remainingSlots) {
      setError(MAX_IMAGES_ERROR);
      return;
    }

    const filesToUpload = files.slice(0, remainingSlots);

    try {
      filesToUpload.forEach((file) => validateFile(file, filesToUpload.length));

      setUploading(true);
      logger.info('[IMAGE_UPLOAD] Uploading image(s)', {
        postId,
        fileCount: filesToUpload.length,
      });

      for (const file of filesToUpload) {
        const attachment = await uploadPostImage(postId, file);

        logger.info('[IMAGE_UPLOAD] Upload successful', {
          postId,
          attachmentId: attachment.id,
        });

        if (onUploadComplete) {
          onUploadComplete(attachment);
        }
      }
    } catch (err) {
      const error = err as Error;
      logger.error('[IMAGE_UPLOAD] Upload failed', {
        postId,
        error: error.message,
      });
      setError(error.message);
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  /**
   * Handle file input change
   */
  const handleFileInput = (e: ChangeEvent<HTMLInputElement>): void => {
    const files = Array.from(e.target.files || []);
    handleFiles(files);
  };

  /**
   * Handle drag over
   */
  const handleDragOver = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();

    if (isUploadDisabled) return;

    setIsDragging(true);
  };

  /**
   * Handle drag leave
   */
  const handleDragLeave = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  /**
   * Handle drop
   */
  const handleDrop = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (isUploadDisabled) {
      if (attachments.length >= MAX_IMAGES) {
        setError(MAX_IMAGES_ERROR);
      }
      return;
    }

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  /**
   * Handle delete image
   */
  const handleDelete = async (attachmentId: string): Promise<void> => {
    const shouldDelete = typeof window.confirm === 'function'
      ? window.confirm('Delete this image? This action cannot be undone.')
      : true;

    if (!shouldDelete) return;

    try {
      setError(null);
      logger.info('[IMAGE_UPLOAD] Deleting image', {
        postId,
        attachmentId,
      });

      await deletePostImage(postId, attachmentId);

      logger.info('[IMAGE_UPLOAD] Delete successful', {
        postId,
        attachmentId,
      });

      if (onDeleteComplete) {
        onDeleteComplete(attachmentId);
      }
    } catch (err) {
      const error = err as Error;
      logger.error('[IMAGE_UPLOAD] Delete failed', {
        postId,
        attachmentId,
        error: error.message,
      });
      setError(error.message);
    }
  };

  /**
   * Persist a reordered attachment list.
   */
  const persistReorder = async (nextAttachments: Attachment[]): Promise<void> => {
    const previousAttachments = orderedAttachments;

    try {
      setError(null);
      setReordering(true);
      setOrderedAttachments(nextAttachments);

      const reorderedAttachments = await reorderPostImages(
        postId,
        nextAttachments.map((attachment) => attachment.id)
      );

      setOrderedAttachments(reorderedAttachments);

      if (onReorderComplete) {
        onReorderComplete(reorderedAttachments);
      }
    } catch (err) {
      const error = err as Error;
      setOrderedAttachments(previousAttachments);
      logger.error('[IMAGE_UPLOAD] Reorder failed', {
        postId,
        error: error.message,
      });
      setError(error.message);
    } finally {
      setReordering(false);
      setDraggedAttachmentId(null);
      setDragOverAttachmentId(null);
    }
  };

  /**
   * Move one attachment to another index.
   */
  const reorderAttachments = async (fromIndex: number, toIndex: number): Promise<void> => {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;

    const nextAttachments = [...orderedAttachments];
    const [movedAttachment] = nextAttachments.splice(fromIndex, 1);
    nextAttachments.splice(toIndex, 0, movedAttachment);

    await persistReorder(nextAttachments);
  };

  /**
   * Handle preview drag start for image reordering.
   */
  const handlePreviewDragStart = (attachmentId: string): void => {
    setDraggedAttachmentId(attachmentId);
  };

  /**
   * Handle preview drop for image reordering.
   */
  const handlePreviewDrop = async (attachmentId: string): Promise<void> => {
    if (!draggedAttachmentId || draggedAttachmentId === attachmentId) {
      setDraggedAttachmentId(null);
      setDragOverAttachmentId(null);
      return;
    }

    const fromIndex = orderedAttachments.findIndex((attachment) => attachment.id === draggedAttachmentId);
    const toIndex = orderedAttachments.findIndex((attachment) => attachment.id === attachmentId);
    await reorderAttachments(fromIndex, toIndex);
  };

  const moveAttachment = async (index: number, direction: -1 | 1): Promise<void> => {
    await reorderAttachments(index, index + direction);
  };

  /**
   * Open file picker
   */
  const handleClick = (): void => {
    if (isUploadDisabled) {
      if (attachments.length >= MAX_IMAGES) {
        setError(MAX_IMAGES_ERROR);
      }
      return;
    }

    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="space-y-4">
      {/* Upload Area */}
      <div
        className={`
          border-2 border-dashed rounded-lg p-6 text-center transition-colors
          ${isDragging ? 'border-green-500 bg-green-50' : 'border-gray-300 hover:border-gray-400'}
          ${isUploadDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        aria-disabled={isUploadDisabled}
        aria-label="Upload image"
        onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleClick();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_IMAGE_TYPES.join(',')}
          onChange={handleFileInput}
          className="hidden"
          disabled={isUploadDisabled}
          aria-label="File input"
          multiple
        />

        {uploading ? (
          <div className="py-4">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-green-600" />
            <p className="mt-2 text-sm text-gray-600">Uploading...</p>
          </div>
        ) : (
          <>
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
              aria-hidden="true"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="mt-2 text-sm text-gray-600">
              <span className="font-semibold text-green-600">Click to upload</span> or drag and drop
            </p>
            <p className="text-xs text-gray-500 mt-1">
              PNG, JPG, GIF, WEBP up to {MAX_FILE_SIZE_MB}MB ({attachments.length}/{MAX_IMAGES} images)
            </p>
          </>
        )}
      </div>

      {attachments.length >= MAX_IMAGES && !error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3" role="status" aria-live="polite">
          <p className="text-sm text-amber-800">{MAX_IMAGES_ERROR}</p>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3" role="alert" aria-live="assertive">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Image Previews */}
      {orderedAttachments.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4" role="list" aria-label="Uploaded images">
          {orderedAttachments.map((attachment, index) => (
            <div
              key={attachment.id}
              className={`relative group rounded-lg overflow-hidden border ${dragOverAttachmentId === attachment.id ? 'border-green-500 ring-2 ring-green-200' : 'border-gray-200'}`}
              role="listitem"
              draggable={!reordering}
              onDragStart={(e) => {
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', attachment.id);
                handlePreviewDragStart(attachment.id);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                setDragOverAttachmentId(attachment.id);
              }}
              onDragLeave={() => setDragOverAttachmentId(null)}
              onDrop={(e) => {
                e.preventDefault();
                handlePreviewDrop(attachment.id);
              }}
              onDragEnd={() => {
                setDraggedAttachmentId(null);
                setDragOverAttachmentId(null);
              }}
              aria-label={`Image ${index + 1} of ${orderedAttachments.length}. Drag to reorder.`}
            >
              <img
                src={getAttachmentImageUrl(attachment)}
                alt={attachment.alt_text || attachment.original_filename || 'Uploaded image'}
                className="w-full h-32 object-cover"
              />
              <div className="absolute top-2 left-2 rounded bg-black bg-opacity-60 px-2 py-1 text-xs text-white">
                {index + 1}
              </div>
              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-opacity flex items-center justify-center">
                <div className="flex flex-wrap justify-center gap-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                  <Button
                    onClick={() => moveAttachment(index, -1)}
                    variant="secondary"
                    className="bg-white text-gray-900 hover:bg-gray-100 disabled:opacity-50"
                    aria-label="Move image left"
                    disabled={index === 0 || reordering}
                  >
                    ←
                  </Button>
                  <Button
                    onClick={() => moveAttachment(index, 1)}
                    variant="secondary"
                    className="bg-white text-gray-900 hover:bg-gray-100 disabled:opacity-50"
                    aria-label="Move image right"
                    disabled={index === orderedAttachments.length - 1 || reordering}
                  >
                    →
                  </Button>
                  <Button
                    onClick={() => handleDelete(attachment.id)}
                    variant="secondary"
                    className="bg-red-600 hover:bg-red-700 text-white"
                    aria-label="Delete image"
                    disabled={reordering}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {reordering && (
        <p className="text-sm text-gray-600" role="status" aria-live="polite">
          Saving image order...
        </p>
      )}
    </div>
  );
}
