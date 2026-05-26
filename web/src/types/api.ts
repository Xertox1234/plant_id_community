/**
 * Generic API Response Types
 *
 * Used for Wagtail API v2 and DRF responses
 */

/**
 * Paginated API response wrapper
 */
export interface ApiResponse<T> {
  items: T[];
  meta: {
    total_count: number;
    page?: number;
    next?: string | null;
    previous?: string | null;
  };
}

/**
 * Wagtail API v2 response format
 */
export interface WagtailApiResponse<T> {
  meta: {
    total_count: number;
  };
  items: T[];
}

/**
 * DRF paginated response format
 */
export interface DRFPaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * API error response — canonical flat shape emitted by custom_exception_handler
 * and create_error_response in users/views.py.
 * Shape: {error: true, message, code, status_code, errors?, detail?}
 */
export interface ApiError {
  error: true;
  message: string;
  code?: string;
  status_code?: number;
  detail?: string;
  errors?: Record<string, unknown>;
}
