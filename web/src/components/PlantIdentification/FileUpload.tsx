import { useState, useCallback, useEffect, ChangeEvent, DragEvent } from 'react';
import { Upload, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { compressImage, formatFileSize, shouldCompressImage } from '../../utils/imageCompression';

interface FileUploadProps {
  onFileSelect: (file: File | null) => void;
  maxSize?: number;
}

interface CompressionStats {
  originalSize: number;
  compressedSize: number;
  reduction: number;
}

export default function FileUpload({ onFileSelect, maxSize = 10 * 1024 * 1024 }: FileUploadProps) {
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isCompressing, setIsCompressing] = useState<boolean>(false);
  const [compressionStats, setCompressionStats] = useState<CompressionStats | null>(null);

  // Cleanup Object URL when component unmounts or preview changes
  useEffect(() => {
    return () => {
      if (preview && preview.startsWith('blob:')) {
        URL.revokeObjectURL(preview);
      }
    };
  }, [preview]);

  const validateFile = useCallback(
    (file: File): boolean => {
      // Check file type
      if (!file.type.startsWith('image/')) {
        setError('Please upload an image file');
        return false;
      }

      // Check file size (default 10MB)
      if (file.size > maxSize) {
        setError(`File size must be less than ${maxSize / 1024 / 1024}MB`);
        return false;
      }

      setError(null);
      return true;
    },
    [maxSize]
  );

  const handleFile = useCallback(
    async (file: File): Promise<void> => {
      if (validateFile(file)) {
        let finalFile: File = file;
        const originalSize = file.size;

        // Compress if file > 2MB
        if (shouldCompressImage(file)) {
          setIsCompressing(true);
          setCompressionStats(null);

          try {
            const compressedFile = await compressImage(file);
            const compressedSize = compressedFile.size;
            const reduction = Math.round(((originalSize - compressedSize) / originalSize) * 100);

            finalFile = compressedFile;
            setCompressionStats({
              originalSize,
              compressedSize,
              reduction,
            });
          } catch {
            setError('Image compression failed. Using original file.');
            // Continue with original file
          } finally {
            setIsCompressing(false);
          }
        }

        // Create preview using Object URL (more memory-efficient than base64)
        try {
          const objectUrl = URL.createObjectURL(finalFile);
          setPreview(objectUrl);
        } catch {
          setError('Failed to load image preview');
          return;
        }

        // Pass file to parent
        onFileSelect(finalFile);
      }
    },
    [onFileSelect, validateFile]
  );

  const handleDrag = useCallback((e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFile(e.dataTransfer.files[0]);
      }
    },
    [handleFile]
  );

  const handleChange = (e: ChangeEvent<HTMLInputElement>): void => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const clearPreview = useCallback((): void => {
    // Cleanup Object URL before clearing preview
    if (preview && preview.startsWith('blob:')) {
      URL.revokeObjectURL(preview);
    }
    setPreview(null);
    setError(null);
    setCompressionStats(null);
    onFileSelect(null);
  }, [preview, onFileSelect]);

  return (
    <div className="w-full">
      {!preview ? (
        <div
          className={`relative border-2 border-dashed rounded-xl p-12 transition-colors ${
            dragActive
              ? 'border-primary bg-primary/10'
              : error
                ? 'border-error/30 bg-error/10'
                : isCompressing
                  ? 'border-sky/30 bg-sky/10'
                  : 'border-line-2 hover:border-primary'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="file-upload"
            accept="image/*"
            onChange={handleChange}
            className="hidden"
            aria-label="Upload plant image, maximum 10MB, PNG, JPG, or WebP formats supported"
          />

          <label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center cursor-pointer"
          >
            {isCompressing ? (
              <>
                <div className="w-16 h-16 mb-4 bg-sky/20 rounded-full flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-sky animate-spin" />
                </div>
                <p className="text-lg font-medium text-ink mb-2">Compressing image...</p>
                <p className="text-sm text-ink-2">Optimizing for faster upload</p>
              </>
            ) : (
              <>
                <div className="w-16 h-16 mb-4 bg-primary/10 rounded-full flex items-center justify-center">
                  <Upload className="w-8 h-8 text-primary" />
                </div>

                <p className="text-lg font-medium text-ink mb-2">Drop your plant photo here</p>
                <p className="text-sm text-ink-2 mb-4">or click to browse your files</p>
                <p className="text-xs text-ink-3">PNG, JPG, WebP up to 10MB</p>
                <p className="text-xs text-ink-3 mt-2">
                  Large files auto-compressed for faster upload
                </p>
              </>
            )}
          </label>

          {error && (
            <div className="mt-4 flex items-center justify-center gap-2 text-error">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="relative">
          <img
            src={preview}
            alt={
              compressionStats
                ? `Plant preview (compressed from ${formatFileSize(compressionStats.originalSize)} to ${formatFileSize(compressionStats.compressedSize)})`
                : 'Plant preview - ready for identification'
            }
            className="w-full h-96 object-cover rounded-xl"
          />
          <button
            onClick={clearPreview}
            className="absolute top-4 right-4 p-2 bg-surface-2 rounded-full shadow-lg hover:bg-surface-3 transition-colors"
            aria-label="Remove image"
          >
            <X className="w-5 h-5 text-ink-2" />
          </button>

          {compressionStats && (
            <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-lg">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="w-4 h-4 text-leaf" />
                <span className="font-medium text-ink">
                  Compressed {compressionStats.reduction}%
                </span>
              </div>
              <p className="text-xs text-ink-2 mt-1">
                {formatFileSize(compressionStats.originalSize)} →{' '}
                {formatFileSize(compressionStats.compressedSize)}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
