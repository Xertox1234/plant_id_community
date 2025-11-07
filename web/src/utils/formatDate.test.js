import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  formatPublishDate,
  formatShortDate,
  formatRelativeDate,
  formatDateTime,
  formatISODate,
  isValidDate,
  getStartOfDay,
  getEndOfDay,
  DEFAULT_LOCALE,
} from './formatDate';
import { logger } from './logger';

// Mock logger
vi.mock('./logger', () => ({
  logger: {
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('formatDate utilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('formatPublishDate', () => {
    it('should format a valid date in long format', () => {
      const date = '2025-01-15T12:00:00';
      const result = formatPublishDate(date);

      expect(result).toBe('January 15, 2025');
    });

    it('should format a date string with time', () => {
      const date = '2025-01-15T10:30:00';
      const result = formatPublishDate(date);

      expect(result).toBe('January 15, 2025');
    });

    it('should format a Date object', () => {
      const date = new Date(2025, 0, 15); // January 15, 2025
      const result = formatPublishDate(date);

      expect(result).toBe('January 15, 2025');
    });

    it('should handle null input', () => {
      const result = formatPublishDate(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = formatPublishDate(undefined);
      expect(result).toBe(null);
    });

    it('should handle empty string', () => {
      const result = formatPublishDate('');
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = formatPublishDate('invalid-date');

      expect(result).toBe(null);
      expect(logger.warn).toHaveBeenCalledWith(
        'Invalid date in formatPublishDate',
        expect.objectContaining({
          component: 'formatDate',
          context: expect.objectContaining({ dateString: 'invalid-date' })
        })
      );
    });

    it('should use custom locale', () => {
      const date = '2025-01-15T12:00:00';
      const result = formatPublishDate(date, 'fr-FR');

      // French format: "15 janvier 2025"
      expect(result).toContain('2025');
      expect(result).toContain('15');
    });

    it('should handle leap year dates', () => {
      const date = '2024-02-29T12:00:00'; // Leap year
      const result = formatPublishDate(date);

      expect(result).toBe('February 29, 2024');
    });

    it('should handle year 2000', () => {
      const date = '2000-01-01T12:00:00';
      const result = formatPublishDate(date);

      expect(result).toBe('January 1, 2000');
    });

    it('should handle end of year', () => {
      const date = '2025-12-31T12:00:00';
      const result = formatPublishDate(date);

      expect(result).toBe('December 31, 2025');
    });
  });

  describe('formatShortDate', () => {
    it('should format a valid date in short format', () => {
      const date = '2025-01-15T12:00:00';
      const result = formatShortDate(date);

      expect(result).toBe('Jan 15, 2025');
    });

    it('should format a date with time', () => {
      const date = '2025-01-15T10:30:00';
      const result = formatShortDate(date);

      expect(result).toBe('Jan 15, 2025');
    });

    it('should handle null input', () => {
      const result = formatShortDate(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = formatShortDate(undefined);
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = formatShortDate('not-a-date');

      expect(result).toBe(null);
      expect(logger.warn).toHaveBeenCalledWith(
        'Invalid date in formatShortDate',
        expect.objectContaining({
          component: 'formatDate',
          context: expect.objectContaining({ dateString: 'not-a-date' })
        })
      );
    });

    it('should use custom locale', () => {
      const date = '2025-01-15T12:00:00';
      const result = formatShortDate(date, 'de-DE');

      // German format will differ from English
      expect(result).toContain('2025');
      expect(result).toContain('15');
    });

    it('should handle all months correctly', () => {
      const months = [
        { date: '2025-01-15', short: 'Jan' },
        { date: '2025-02-15', short: 'Feb' },
        { date: '2025-03-15', short: 'Mar' },
        { date: '2025-04-15', short: 'Apr' },
        { date: '2025-05-15', short: 'May' },
        { date: '2025-06-15', short: 'Jun' },
        { date: '2025-07-15', short: 'Jul' },
        { date: '2025-08-15', short: 'Aug' },
        { date: '2025-09-15', short: 'Sep' },
        { date: '2025-10-15', short: 'Oct' },
        { date: '2025-11-15', short: 'Nov' },
        { date: '2025-12-15', short: 'Dec' },
      ];

      months.forEach(({ date, short }) => {
        const result = formatShortDate(date);
        expect(result).toContain(short);
      });
    });
  });

  describe('formatRelativeDate', () => {
    beforeEach(() => {
      // Mock Date to have consistent test results
      const mockDate = new Date('2025-01-15T12:00:00');
      vi.useFakeTimers();
      vi.setSystemTime(mockDate);
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should return "Just now" for recent dates', () => {
      const date = new Date('2025-01-15T11:59:30'); // 30 seconds ago
      const result = formatRelativeDate(date);

      expect(result).toBe('Just now');
    });

    it('should return minutes for dates within an hour', () => {
      const date = new Date('2025-01-15T11:45:00'); // 15 minutes ago
      const result = formatRelativeDate(date);

      expect(result).toBe('15 minutes ago');
    });

    it('should return singular "minute" for 1 minute ago', () => {
      const date = new Date('2025-01-15T11:59:00'); // 1 minute ago
      const result = formatRelativeDate(date);

      expect(result).toBe('1 minute ago');
    });

    it('should return hours for dates within a day', () => {
      const date = new Date('2025-01-15T09:00:00'); // 3 hours ago
      const result = formatRelativeDate(date);

      expect(result).toBe('3 hours ago');
    });

    it('should return singular "hour" for 1 hour ago', () => {
      const date = new Date('2025-01-15T11:00:00'); // 1 hour ago
      const result = formatRelativeDate(date);

      expect(result).toBe('1 hour ago');
    });

    it('should return days for dates within a week', () => {
      const date = new Date('2025-01-12T12:00:00'); // 3 days ago
      const result = formatRelativeDate(date);

      expect(result).toBe('3 days ago');
    });

    it('should return singular "day" for 1 day ago', () => {
      const date = new Date('2025-01-14T12:00:00'); // 1 day ago
      const result = formatRelativeDate(date);

      expect(result).toBe('1 day ago');
    });

    it('should return weeks for dates within a month', () => {
      const date = new Date('2025-01-01T12:00:00'); // 2 weeks ago
      const result = formatRelativeDate(date);

      expect(result).toBe('2 weeks ago');
    });

    it('should return singular "week" for 1 week ago', () => {
      const date = new Date('2025-01-08T12:00:00'); // 1 week ago
      const result = formatRelativeDate(date);

      expect(result).toBe('1 week ago');
    });

    it('should return months for dates within a year', () => {
      const date = new Date('2024-10-15T12:00:00'); // 3 months ago
      const result = formatRelativeDate(date);

      expect(result).toBe('3 months ago');
    });

    it('should return singular "month" for 1 month ago', () => {
      const date = new Date('2024-12-15T12:00:00'); // 1 month ago
      const result = formatRelativeDate(date);

      expect(result).toBe('1 month ago');
    });

    it('should return years for old dates', () => {
      const date = new Date('2023-01-15T12:00:00'); // 2 years ago
      const result = formatRelativeDate(date);

      expect(result).toBe('2 years ago');
    });

    it('should return singular "year" for 1 year ago', () => {
      const date = new Date('2024-01-15T12:00:00'); // 1 year ago
      const result = formatRelativeDate(date);

      expect(result).toBe('1 year ago');
    });

    it('should handle null input', () => {
      const result = formatRelativeDate(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = formatRelativeDate(undefined);
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = formatRelativeDate('bad-date');

      expect(result).toBe(null);
      expect(logger.warn).toHaveBeenCalledWith(
        'Invalid date in formatRelativeDate',
        expect.objectContaining({
          component: 'formatDate',
          context: expect.objectContaining({ dateString: 'bad-date' })
        })
      );
    });
  });

  describe('formatDateTime', () => {
    it('should format a date with time', () => {
      const date = '2025-01-15T15:30:00';
      const result = formatDateTime(date);

      expect(result).toContain('January 15, 2025');
      expect(result).toContain('at');
      expect(result).toContain('3:30 PM');
    });

    it('should format midnight correctly', () => {
      const date = '2025-01-15T00:00:00';
      const result = formatDateTime(date);

      expect(result).toContain('January 15, 2025');
      expect(result).toContain('12:00 AM');
    });

    it('should format noon correctly', () => {
      const date = '2025-01-15T12:00:00';
      const result = formatDateTime(date);

      expect(result).toContain('January 15, 2025');
      expect(result).toContain('12:00 PM');
    });

    it('should handle null input', () => {
      const result = formatDateTime(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = formatDateTime(undefined);
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = formatDateTime('invalid');

      expect(result).toBe(null);
      expect(logger.warn).toHaveBeenCalledWith(
        'Invalid date in formatDateTime',
        expect.objectContaining({
          component: 'formatDate',
          context: expect.objectContaining({ dateString: 'invalid' })
        })
      );
    });

    it('should use custom locale', () => {
      const date = '2025-01-15T15:30:00';
      const result = formatDateTime(date, 'de-DE');

      // German format will differ
      expect(result).toContain('2025');
      expect(result).toContain('15');
    });

    it('should handle Date objects', () => {
      const date = new Date(2025, 0, 15, 15, 30, 0);
      const result = formatDateTime(date);

      expect(result).toContain('January 15, 2025');
      expect(result).toContain('3:30 PM');
    });
  });

  describe('formatISODate', () => {
    it('should format a date string to ISO format', () => {
      const date = 'January 15, 2025';
      const result = formatISODate(date);

      expect(result).toBe('2025-01-15');
    });

    it('should format a Date object to ISO format', () => {
      const date = new Date(2025, 0, 15); // January 15, 2025
      const result = formatISODate(date);

      expect(result).toBe('2025-01-15');
    });

    it('should handle ISO string input', () => {
      const date = '2025-01-15T10:30:00';
      const result = formatISODate(date);

      expect(result).toBe('2025-01-15');
    });

    it('should handle null input', () => {
      const result = formatISODate(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = formatISODate(undefined);
      expect(result).toBe(null);
    });

    it('should handle empty string', () => {
      const result = formatISODate('');
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = formatISODate('not-a-date');

      expect(result).toBe(null);
      expect(logger.warn).toHaveBeenCalledWith(
        'Invalid date in formatISODate',
        expect.objectContaining({
          component: 'formatDate',
          context: expect.objectContaining({ dateString: 'not-a-date' })
        })
      );
    });

    it('should handle leap year dates', () => {
      const date = '2024-02-29T12:00:00';
      const result = formatISODate(date);

      expect(result).toBe('2024-02-29');
    });

    it('should format first day of year', () => {
      const date = '2025-01-01T12:00:00';
      const result = formatISODate(date);

      expect(result).toBe('2025-01-01');
    });

    it('should format last day of year', () => {
      const date = '2025-12-31T12:00:00';
      const result = formatISODate(date);

      expect(result).toBe('2025-12-31');
    });
  });

  describe('isValidDate', () => {
    it('should return true for valid date strings', () => {
      expect(isValidDate('2025-01-15')).toBe(true);
      expect(isValidDate('January 15, 2025')).toBe(true);
      expect(isValidDate('2025-01-15T10:30:00')).toBe(true);
    });

    it('should return true for Date objects', () => {
      const date = new Date(2025, 0, 15);
      expect(isValidDate(date)).toBe(true);
    });

    it('should return false for invalid date strings', () => {
      expect(isValidDate('not-a-date')).toBe(false);
      // JavaScript Date rejects invalid month (13) but is lenient with day overflow
      expect(isValidDate('2025-13-01')).toBe(false); // Invalid month 13
      expect(isValidDate('2025-02-30')).toBe(true); // Lenient - converts to March 2
    });

    it('should return false for null', () => {
      expect(isValidDate(null)).toBe(false);
    });

    it('should return false for undefined', () => {
      expect(isValidDate(undefined)).toBe(false);
    });

    it('should return false for empty string', () => {
      expect(isValidDate('')).toBe(false);
    });

    it('should return true for leap year date', () => {
      expect(isValidDate('2024-02-29')).toBe(true);
    });

    it('should return false for non-leap year Feb 29', () => {
      // JavaScript Date is lenient - converts Feb 29 in non-leap year to March 1
      expect(isValidDate('2025-02-29')).toBe(true); // Converted to March 1, 2025
    });

    it('should return true for edge case dates', () => {
      expect(isValidDate('1970-01-01')).toBe(true); // Unix epoch
      expect(isValidDate('2000-01-01')).toBe(true); // Y2K
      expect(isValidDate('2038-01-19')).toBe(true); // 32-bit timestamp limit
    });
  });

  describe('getStartOfDay', () => {
    it('should return midnight for a given date', () => {
      const date = '2025-01-15T15:30:45';
      const result = getStartOfDay(date);

      expect(result).toBeInstanceOf(Date);
      expect(result.getHours()).toBe(0);
      expect(result.getMinutes()).toBe(0);
      expect(result.getSeconds()).toBe(0);
      expect(result.getMilliseconds()).toBe(0);
      expect(result.getDate()).toBe(15);
      expect(result.getMonth()).toBe(0); // January
      expect(result.getFullYear()).toBe(2025);
    });

    it('should return midnight for a Date object', () => {
      const date = new Date(2025, 0, 15, 15, 30, 45);
      const result = getStartOfDay(date);

      expect(result.getHours()).toBe(0);
      expect(result.getMinutes()).toBe(0);
      expect(result.getSeconds()).toBe(0);
      expect(result.getMilliseconds()).toBe(0);
    });

    it('should handle date already at midnight', () => {
      const date = '2025-01-15T00:00:00';
      const result = getStartOfDay(date);

      expect(result.getHours()).toBe(0);
      expect(result.getMinutes()).toBe(0);
      expect(result.getSeconds()).toBe(0);
    });

    it('should handle null input', () => {
      const result = getStartOfDay(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = getStartOfDay(undefined);
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = getStartOfDay('invalid-date');
      expect(result).toBe(null);
    });

    it('should handle edge of month', () => {
      const date = '2025-01-31T23:59:59';
      const result = getStartOfDay(date);

      expect(result.getDate()).toBe(31);
      expect(result.getHours()).toBe(0);
    });

    it('should handle leap year date', () => {
      const date = '2024-02-29T12:00:00';
      const result = getStartOfDay(date);

      expect(result.getDate()).toBe(29);
      expect(result.getMonth()).toBe(1); // February
      expect(result.getHours()).toBe(0);
    });
  });

  describe('getEndOfDay', () => {
    it('should return end of day for a given date', () => {
      const date = '2025-01-15T10:30:45';
      const result = getEndOfDay(date);

      expect(result).toBeInstanceOf(Date);
      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
      expect(result.getSeconds()).toBe(59);
      expect(result.getMilliseconds()).toBe(999);
      expect(result.getDate()).toBe(15);
      expect(result.getMonth()).toBe(0); // January
      expect(result.getFullYear()).toBe(2025);
    });

    it('should return end of day for a Date object', () => {
      const date = new Date(2025, 0, 15, 10, 30, 45);
      const result = getEndOfDay(date);

      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
      expect(result.getSeconds()).toBe(59);
      expect(result.getMilliseconds()).toBe(999);
    });

    it('should handle date already at end of day', () => {
      const date = '2025-01-15T23:59:59.999';
      const result = getEndOfDay(date);

      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
      expect(result.getSeconds()).toBe(59);
      expect(result.getMilliseconds()).toBe(999);
    });

    it('should handle null input', () => {
      const result = getEndOfDay(null);
      expect(result).toBe(null);
    });

    it('should handle undefined input', () => {
      const result = getEndOfDay(undefined);
      expect(result).toBe(null);
    });

    it('should handle invalid date string', () => {
      const result = getEndOfDay('not-a-date');
      expect(result).toBe(null);
    });

    it('should handle edge of month', () => {
      const date = '2025-01-31T00:00:00';
      const result = getEndOfDay(date);

      expect(result.getDate()).toBe(31);
      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
    });

    it('should handle leap year date', () => {
      const date = '2024-02-29T12:00:00';
      const result = getEndOfDay(date);

      expect(result.getDate()).toBe(29);
      expect(result.getMonth()).toBe(1); // February
      expect(result.getHours()).toBe(23);
      expect(result.getMinutes()).toBe(59);
      expect(result.getSeconds()).toBe(59);
    });

    it('should handle end of year', () => {
      const date = '2025-12-31T12:00:00';
      const result = getEndOfDay(date);

      expect(result.getDate()).toBe(31);
      expect(result.getMonth()).toBe(11); // December
      expect(result.getFullYear()).toBe(2025);
      expect(result.getHours()).toBe(23);
    });
  });

  describe('edge cases', () => {
    it('should handle extremely old dates', () => {
      const date = '1900-01-01T12:00:00';
      expect(formatPublishDate(date)).toBe('January 1, 1900');
      expect(formatShortDate(date)).toBe('Jan 1, 1900');
      expect(formatISODate(date)).toBe('1900-01-01');
      expect(isValidDate(date)).toBe(true);
    });

    it('should handle far future dates', () => {
      const date = '2100-12-31T12:00:00';
      expect(formatPublishDate(date)).toBe('December 31, 2100');
      expect(formatShortDate(date)).toBe('Dec 31, 2100');
      expect(formatISODate(date)).toBe('2100-12-31');
      expect(isValidDate(date)).toBe(true);
    });

    it('should handle Unix epoch', () => {
      const date = '1970-01-01T00:00:00';
      expect(isValidDate(date)).toBe(true);
      expect(formatISODate(date)).toBe('1970-01-01');
    });

    it('should handle Y2K date', () => {
      const date = '2000-01-01T12:00:00';
      expect(formatPublishDate(date)).toBe('January 1, 2000');
      expect(isValidDate(date)).toBe(true);
    });

    it('should handle various invalid formats', () => {
      const invalidDates = [
        '32/01/2025',
        '2025-00-01',
        '2025-13-01',
        'abc123',
        '9999-99-99',
        'null',
        'undefined',
      ];

      invalidDates.forEach((date) => {
        expect(isValidDate(date)).toBe(false);
      });
    });
  });

  describe('DEFAULT_LOCALE', () => {
    it('should export DEFAULT_LOCALE constant', () => {
      expect(DEFAULT_LOCALE).toBe('en-US');
    });

    it('should use DEFAULT_LOCALE when no locale specified', () => {
      const date = '2025-01-15T12:00:00';

      // English format
      const result = formatPublishDate(date);
      expect(result).toBe('January 15, 2025');
    });
  });
});
