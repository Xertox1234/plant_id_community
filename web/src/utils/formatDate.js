/**
 * Date Formatting Utilities
 *
 * Centralized date formatting functions for consistent display across the application.
 * All functions handle null/undefined inputs gracefully.
 *
 * @module utils/formatDate
 */

import { logger } from './logger'

/**
 * Default locale for date formatting.
 * Change this single constant to update all dates across the app.
 */
export const DEFAULT_LOCALE = 'en-US';

/**
 * Format a publish date in long format (e.g., "January 15, 2025").
 *
 * This is the standard format used throughout the blog for publish dates.
 * Returns null for invalid dates rather than throwing errors.
 *
 * @param {string|Date|null|undefined} dateString - Date to format
 * @param {string} [locale=DEFAULT_LOCALE] - Locale code for formatting
 * @returns {string|null} Formatted date string, or null if invalid
 *
 * @example
 * formatPublishDate('2025-01-15')
 * // Returns: 'January 15, 2025'
 *
 * @example
 * formatPublishDate(null)
 * // Returns: null
 *
 * @example
 * formatPublishDate('2025-01-15', 'fr-FR')
 * // Returns: '15 janvier 2025' (in French)
 */
export function formatPublishDate(dateString, locale = DEFAULT_LOCALE) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    // Check if date is valid
    if (isNaN(date.getTime())) {
      logger.warn('Invalid date in formatPublishDate', {
        component: 'formatDate',
        context: { dateString },
      });
      return null;
    }

    return date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch (error) {
    logger.error('Error formatting date in formatPublishDate', {
      component: 'formatDate',
      error,
      context: { dateString },
    });
    return null;
  }
}

/**
 * Format a date in short format (e.g., "Jan 15, 2025").
 *
 * Useful for compact displays like cards, lists, or mobile views.
 *
 * @param {string|Date|null|undefined} dateString - Date to format
 * @param {string} [locale=DEFAULT_LOCALE] - Locale code for formatting
 * @returns {string|null} Formatted date string, or null if invalid
 *
 * @example
 * formatShortDate('2025-01-15')
 * // Returns: 'Jan 15, 2025'
 */
export function formatShortDate(dateString, locale = DEFAULT_LOCALE) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      logger.warn('Invalid date in formatShortDate', {
        component: 'formatDate',
        context: { dateString },
      });
      return null;
    }

    return date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch (error) {
    logger.error('Error formatting date in formatShortDate', {
      component: 'formatDate',
      error,
      context: { dateString },
    });
    return null;
  }
}

/**
 * Format a date relative to now (e.g., "2 hours ago", "3 days ago").
 *
 * Useful for showing how recent a post or comment is.
 *
 * @param {string|Date|null|undefined} dateString - Date to format
 * @param {string} [locale=DEFAULT_LOCALE] - Locale code for formatting
 * @returns {string|null} Relative time string, or null if invalid
 *
 * @example
 * formatRelativeDate('2025-01-15T10:00:00')
 * // Returns: '2 hours ago' (if current time is 2025-01-15T12:00:00)
 *
 * @example
 * formatRelativeDate('2025-01-10')
 * // Returns: '5 days ago' (if today is 2025-01-15)
 */
export function formatRelativeDate(dateString) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      logger.warn('Invalid date in formatRelativeDate', {
        component: 'formatDate',
        context: { dateString },
      });
      return null;
    }

    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    const diffWeek = Math.floor(diffDay / 7);
    const diffMonth = Math.floor(diffDay / 30);
    const diffYear = Math.floor(diffDay / 365);

    if (diffSec < 60) {
      return 'Just now';
    } else if (diffMin < 60) {
      return `${diffMin} ${diffMin === 1 ? 'minute' : 'minutes'} ago`;
    } else if (diffHour < 24) {
      return `${diffHour} ${diffHour === 1 ? 'hour' : 'hours'} ago`;
    } else if (diffDay < 7) {
      return `${diffDay} ${diffDay === 1 ? 'day' : 'days'} ago`;
    } else if (diffWeek < 4) {
      return `${diffWeek} ${diffWeek === 1 ? 'week' : 'weeks'} ago`;
    } else if (diffMonth < 12) {
      return `${diffMonth} ${diffMonth === 1 ? 'month' : 'months'} ago`;
    } else {
      return `${diffYear} ${diffYear === 1 ? 'year' : 'years'} ago`;
    }
  } catch (error) {
    logger.error('Error formatting date in formatRelativeDate', {
      component: 'formatDate',
      error,
      context: { dateString },
    });
    return null;
  }
}

/**
 * Format a date with time (e.g., "January 15, 2025 at 3:30 PM").
 *
 * Useful for showing exact timestamps for comments, updates, or events.
 *
 * @param {string|Date|null|undefined} dateString - Date to format
 * @param {string} [locale=DEFAULT_LOCALE] - Locale code for formatting
 * @returns {string|null} Formatted date/time string, or null if invalid
 *
 * @example
 * formatDateTime('2025-01-15T15:30:00')
 * // Returns: 'January 15, 2025 at 3:30 PM'
 */
export function formatDateTime(dateString, locale = DEFAULT_LOCALE) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      logger.warn('Invalid date in formatDateTime', {
        component: 'formatDate',
        context: { dateString },
      });
      return null;
    }

    const datePart = date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });

    const timePart = date.toLocaleTimeString(locale, {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });

    return `${datePart} at ${timePart}`;
  } catch (error) {
    logger.error('Error formatting date in formatDateTime', {
      component: 'formatDate',
      error,
      context: { dateString },
    });
    return null;
  }
}

/**
 * Format a date in ISO 8601 format (e.g., "2025-01-15").
 *
 * Useful for API requests, database queries, or machine-readable dates.
 *
 * @param {string|Date|null|undefined} dateString - Date to format
 * @returns {string|null} ISO date string (YYYY-MM-DD), or null if invalid
 *
 * @example
 * formatISODate('January 15, 2025')
 * // Returns: '2025-01-15'
 *
 * @example
 * formatISODate(new Date(2025, 0, 15))
 * // Returns: '2025-01-15'
 */
export function formatISODate(dateString) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      logger.warn('Invalid date in formatISODate', {
        component: 'formatDate',
        context: { dateString },
      });
      return null;
    }

    return date.toISOString().split('T')[0];
  } catch (error) {
    logger.error('Error formatting date in formatISODate', {
      component: 'formatDate',
      error,
      context: { dateString },
    });
    return null;
  }
}

/**
 * Check if a date is valid.
 *
 * @param {string|Date|null|undefined} dateString - Date to validate
 * @returns {boolean} True if date is valid, false otherwise
 *
 * @example
 * isValidDate('2025-01-15')  // true
 * isValidDate('invalid')      // false
 * isValidDate(null)           // false
 */
export function isValidDate(dateString) {
  if (!dateString) {
    return false;
  }

  try {
    const date = new Date(dateString);
    return !isNaN(date.getTime());
  } catch {
    return false;
  }
}

/**
 * Get the start of day for a given date (midnight).
 *
 * @param {string|Date|null|undefined} dateString - Date to process
 * @returns {Date|null} Date object at midnight, or null if invalid
 *
 * @example
 * getStartOfDay('2025-01-15T15:30:00')
 * // Returns: Date object for 2025-01-15T00:00:00
 */
export function getStartOfDay(dateString) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      return null;
    }

    date.setHours(0, 0, 0, 0);
    return date;
  } catch {
    return null;
  }
}

/**
 * Get the end of day for a given date (23:59:59.999).
 *
 * @param {string|Date|null|undefined} dateString - Date to process
 * @returns {Date|null} Date object at end of day, or null if invalid
 *
 * @example
 * getEndOfDay('2025-01-15T10:00:00')
 * // Returns: Date object for 2025-01-15T23:59:59.999
 */
export function getEndOfDay(dateString) {
  if (!dateString) {
    return null;
  }

  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      return null;
    }

    date.setHours(23, 59, 59, 999);
    return date;
  } catch {
    return null;
  }
}

// Default export with all functions
export default {
  formatPublishDate,
  formatShortDate,
  formatRelativeDate,
  formatDateTime,
  formatISODate,
  isValidDate,
  getStartOfDay,
  getEndOfDay,
  DEFAULT_LOCALE,
};
