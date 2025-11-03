import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ImageUploadWidget from './ImageUploadWidget';
import * as forumService from '../../services/forumService';

// Mock the forumService
vi.mock('../../services/forumService');

/**
 * Create mock attachment
 */
function createMockAttachment(overrides = {}) {
  return {
    id: 'attachment-123',
    image: 'https://example.com/image.jpg',
    image_thumbnail: 'https://example.com/image-thumb.jpg',
    file_size: 1024000,
    created_at: '2025-11-02T12:00:00Z',
    ...overrides,
  };
}

/**
 * Create mock file
 */
function createMockFile(name = 'test.jpg', type = 'image/jpeg', size = 1024000) {
  const file = new File(['test content'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('ImageUploadWidget', () => {
  const mockPostId = 'post-123';
  const mockOnUploadComplete = vi.fn();
  const mockOnDeleteComplete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('renders upload area with instructions', () => {
      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      expect(screen.getByText(/Click to upload/i)).toBeInTheDocument();
      expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
      expect(screen.getByText(/PNG, JPG, GIF, WEBP/i)).toBeInTheDocument();
    });

    it('shows current image count', () => {
      const attachments = [
        createMockAttachment({ id: '1' }),
        createMockAttachment({ id: '2' }),
      ];

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={attachments}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      expect(screen.getByText(/2\/6 images/i)).toBeInTheDocument();
    });

    it('renders uploaded images as thumbnails', () => {
      const attachments = [
        createMockAttachment({ id: '1' }),
        createMockAttachment({ id: '2' }),
      ];

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={attachments}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const images = screen.getAllByAltText('Uploaded image');
      expect(images).toHaveLength(2);
    });

    it('has accessible file input', () => {
      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveAttribute('type', 'file');
      expect(fileInput).toHaveAttribute('accept');
    });
  });

  describe('File Upload', () => {
    it('uploads image when file is selected', async () => {
      const user = userEvent.setup();
      const mockAttachment = createMockAttachment();
      vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(mockAttachment);

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const file = createMockFile();

      await user.upload(fileInput, file);

      await waitFor(() => {
        expect(forumService.uploadPostImage).toHaveBeenCalledWith(mockPostId, file);
      });

      await waitFor(() => {
        expect(mockOnUploadComplete).toHaveBeenCalledWith(mockAttachment);
      });
    });

    it('shows loading state during upload', async () => {
      const user = userEvent.setup();
      vi.spyOn(forumService, 'uploadPostImage').mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const file = createMockFile();

      await user.upload(fileInput, file);

      await waitFor(() => {
        expect(screen.getByText('Uploading...')).toBeInTheDocument();
      });
    });

    it('displays error when upload fails', async () => {
      const user = userEvent.setup();
      vi.spyOn(forumService, 'uploadPostImage').mockRejectedValue(
        new Error('Upload failed')
      );

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const file = createMockFile();

      await user.upload(fileInput, file);

      await waitFor(() => {
        expect(screen.getByText('Upload failed')).toBeInTheDocument();
      });
    });
  });

  describe('File Validation', () => {
    it('rejects files that are too large', async () => {
      const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const largeFile = createMockFile('large.jpg', 'image/jpeg', 11 * 1024 * 1024); // 11MB

      // Use fireEvent instead of userEvent to bypass browser file filtering
      fireEvent.change(fileInput, { target: { files: [largeFile] } });

      await waitFor(() => {
        expect(screen.getByText(/File too large/i)).toBeInTheDocument();
      });

      expect(uploadSpy).not.toHaveBeenCalled();
    });

    it('rejects invalid file types', async () => {
      const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const invalidFile = createMockFile('document.pdf', 'application/pdf', 1024000);

      // Use fireEvent instead of userEvent to bypass browser file filtering
      fireEvent.change(fileInput, { target: { files: [invalidFile] } });

      await waitFor(() => {
        expect(screen.getByText(/Invalid file type/i)).toBeInTheDocument();
      });

      expect(uploadSpy).not.toHaveBeenCalled();
    });

    it('rejects upload when max images reached', async () => {
      const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');
      const attachments = Array.from({ length: 6 }, (_, i) =>
        createMockAttachment({ id: `${i}` })
      );

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={attachments}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const file = createMockFile();

      // Use fireEvent instead of userEvent to bypass browser file filtering
      fireEvent.change(fileInput, { target: { files: [file] } });

      await waitFor(() => {
        expect(screen.getByText(/Maximum 6 images allowed/i)).toBeInTheDocument();
      });

      expect(uploadSpy).not.toHaveBeenCalled();
    });

    it('disables file input when max images reached', () => {
      const attachments = Array.from({ length: 6 }, (_, i) =>
        createMockAttachment({ id: `${i}` })
      );

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={attachments}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      expect(fileInput).toBeDisabled();
    });
  });

  describe('Image Deletion', () => {
    it('deletes image when delete button clicked', async () => {
      const user = userEvent.setup();
      const attachment = createMockAttachment();
      vi.spyOn(forumService, 'deletePostImage').mockResolvedValue();

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[attachment]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const deleteButton = screen.getByLabelText('Delete image');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(forumService.deletePostImage).toHaveBeenCalledWith(
          mockPostId,
          attachment.id
        );
      });

      await waitFor(() => {
        expect(mockOnDeleteComplete).toHaveBeenCalledWith(attachment.id);
      });
    });

    it('displays error when delete fails', async () => {
      const user = userEvent.setup();
      const attachment = createMockAttachment();
      vi.spyOn(forumService, 'deletePostImage').mockRejectedValue(
        new Error('Delete failed')
      );

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[attachment]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const deleteButton = screen.getByLabelText('Delete image');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('Delete failed')).toBeInTheDocument();
      });
    });
  });

  describe('Drag and Drop', () => {
    it('highlights drop zone when dragging over', async () => {
      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const uploadArea = screen.getByRole('button', { name: 'Upload image' });

      // Simulate drag over
      const dragOverEvent = new Event('dragover', { bubbles: true });
      Object.defineProperty(dragOverEvent, 'dataTransfer', {
        value: { files: [] },
      });

      uploadArea.dispatchEvent(dragOverEvent);

      // Check that the drop zone is highlighted (has green border class)
      await waitFor(() => {
        expect(uploadArea).toHaveClass('border-green-500');
      });
    });

    it('removes highlight when drag leaves', async () => {
      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const uploadArea = screen.getByRole('button', { name: 'Upload image' });

      // Simulate drag over then drag leave
      const dragOverEvent = new Event('dragover', { bubbles: true });
      const dragLeaveEvent = new Event('dragleave', { bubbles: true });

      uploadArea.dispatchEvent(dragOverEvent);
      uploadArea.dispatchEvent(dragLeaveEvent);

      // Check that highlight is removed
      await waitFor(() => {
        expect(uploadArea).not.toHaveClass('border-green-500');
      });
    });

    it('uploads image when dropped', async () => {
      const mockAttachment = createMockAttachment();
      vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(mockAttachment);

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const uploadArea = screen.getByRole('button', { name: 'Upload image' });
      const file = createMockFile();

      // Simulate drop event
      const dropEvent = new Event('drop', { bubbles: true });
      Object.defineProperty(dropEvent, 'dataTransfer', {
        value: { files: [file] },
      });

      uploadArea.dispatchEvent(dropEvent);

      await waitFor(() => {
        expect(forumService.uploadPostImage).toHaveBeenCalledWith(mockPostId, file);
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      expect(screen.getByLabelText('Upload image')).toBeInTheDocument();
      expect(screen.getByLabelText('File input')).toBeInTheDocument();
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const uploadArea = screen.getByRole('button', { name: 'Upload image' });

      // Should be focusable
      uploadArea.focus();
      expect(uploadArea).toHaveFocus();

      // Should have tabIndex
      expect(uploadArea).toHaveAttribute('tabIndex', '0');
    });

    it('uses semantic HTML for image grid', () => {
      const attachments = [
        createMockAttachment({ id: '1' }),
        createMockAttachment({ id: '2' }),
      ];

      const { container } = render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={attachments}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      // Check for grid layout
      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles empty attachments array', () => {
      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onUploadComplete={mockOnUploadComplete}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      expect(screen.getByText(/0\/6 images/i)).toBeInTheDocument();
      expect(screen.queryByAltText('Uploaded image')).not.toBeInTheDocument();
    });

    it('handles missing onUploadComplete callback', async () => {
      const user = userEvent.setup();
      const mockAttachment = createMockAttachment();
      vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(mockAttachment);

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[]}
          onDeleteComplete={mockOnDeleteComplete}
        />
      );

      const fileInput = screen.getByLabelText('File input');
      const file = createMockFile();

      // Should not throw error
      await user.upload(fileInput, file);

      await waitFor(() => {
        expect(forumService.uploadPostImage).toHaveBeenCalled();
      });
    });

    it('handles missing onDeleteComplete callback', async () => {
      const user = userEvent.setup();
      const attachment = createMockAttachment();
      vi.spyOn(forumService, 'deletePostImage').mockResolvedValue();

      render(
        <ImageUploadWidget
          postId={mockPostId}
          attachments={[attachment]}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const deleteButton = screen.getByLabelText('Delete image');

      // Should not throw error
      await user.click(deleteButton);

      await waitFor(() => {
        expect(forumService.deletePostImage).toHaveBeenCalled();
      });
    });
  });
});
