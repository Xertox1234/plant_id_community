import { useState, useRef, ChangeEvent, DragEvent, KeyboardEvent } from 'react';
import { uploadPostImage, deletePostImage } from '../../services/forumService';
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
}: ImageUploadWidgetProps) {
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /**
   * Validate image file
   */
  const validateFile = (file: File): void => {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      throw new Error(INVALID_TYPE_ERROR);
    }

    if (file.size > MAX_FILE_SIZE) {
      throw new Error(FILE_SIZE_ERROR);
    }

    if (attachments.length >= MAX_IMAGES) {
      throw new Error(MAX_IMAGES_ERROR);
    }
  };

  /**
   * Handle file selection or drop
   */
  const handleFiles = async (files: File[]): Promise<void> => {
    setError(null);

    // Only process first file if multiple selected
    const file = files[0];
    if (!file) return;

    try {
      validateFile(file);

      setUploading(true);
      logger.info('[IMAGE_UPLOAD] Uploading image', {
        postId,
        fileName: file.name,
        fileSize: file.size,
      });

      const attachment = await uploadPostImage(postId, file);

      logger.info('[IMAGE_UPLOAD] Upload successful', {
        postId,
        attachmentId: attachment.id,
      });

      if (onUploadComplete) {
        onUploadComplete(attachment);
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

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  /**
   * Handle delete image
   */
  const handleDelete = async (attachmentId: string): Promise<void> => {
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
   * Open file picker
   */
  const handleClick = (): void => {
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
          ${attachments.length >= MAX_IMAGES ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        aria-label="Upload image"
        onKeyPress={(e: KeyboardEvent<HTMLDivElement>) => {
          if (e.key === 'Enter' || e.key === ' ') {
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
          disabled={attachments.length >= MAX_IMAGES}
          aria-label="File input"
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

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Image Previews */}
      {attachments.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {attachments.map((attachment) => (
            <div
              key={attachment.id}
              className="relative group rounded-lg overflow-hidden border border-gray-200"
            >
              <img
                src={attachment.image_thumbnail || attachment.image}
                alt="Uploaded image"
                className="w-full h-32 object-cover"
              />
              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-opacity flex items-center justify-center">
                <Button
                  onClick={() => handleDelete(attachment.id)}
                  variant="danger"
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label="Delete image"
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
