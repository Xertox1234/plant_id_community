import { describe, it, expect } from 'vitest';
import { sanitizeSearchQuery, validateEmail } from './validation';

describe('validation utilities', () => {
  describe('sanitizeSearchQuery', () => {
    it('should return sanitized query for valid input', () => {
      expect(sanitizeSearchQuery('hello world')).toBe('hello world');
      expect(sanitizeSearchQuery('plant care')).toBe('plant care');
      expect(sanitizeSearchQuery('123 test')).toBe('123 test');
    });

    it('should trim whitespace', () => {
      expect(sanitizeSearchQuery('  hello world  ')).toBe('hello world');
      expect(sanitizeSearchQuery('\thello\t')).toBe('hello');
      expect(sanitizeSearchQuery('\nhello\n')).toBe('hello');
    });

    it('should remove control characters', () => {
      expect(sanitizeSearchQuery('hello\x00world')).toBe('helloworld');
      expect(sanitizeSearchQuery('test\x01query')).toBe('testquery');
      expect(sanitizeSearchQuery('test\x7Fquery')).toBe('testquery');
    });

    it('should limit length to 200 characters', () => {
      const longQuery = 'a'.repeat(300);
      const result = sanitizeSearchQuery(longQuery);
      expect(result.length).toBe(200);
    });

    it('should return empty string for null or undefined', () => {
      expect(sanitizeSearchQuery(null)).toBe('');
      expect(sanitizeSearchQuery(undefined)).toBe('');
    });

    it('should return empty string for empty input', () => {
      expect(sanitizeSearchQuery('')).toBe('');
    });

    it('should return empty string for non-string types', () => {
      expect(sanitizeSearchQuery(123 as unknown as string)).toBe('');
      expect(sanitizeSearchQuery({} as unknown as string)).toBe('');
      expect(sanitizeSearchQuery([] as unknown as string)).toBe('');
    });

    it('should preserve special characters (not a validator, just sanitizer)', () => {
      expect(sanitizeSearchQuery('hello-world')).toBe('hello-world');
      expect(sanitizeSearchQuery('hello@world.com')).toBe('hello@world.com');
      expect(sanitizeSearchQuery('50%')).toBe('50%');
    });

    it('should handle unicode characters', () => {
      expect(sanitizeSearchQuery('café')).toBe('café');
      expect(sanitizeSearchQuery('你好')).toBe('你好');
      expect(sanitizeSearchQuery('🌱')).toBe('🌱');
    });
  });

  describe('validateEmail', () => {
    it('should accept valid email addresses', () => {
      expect(validateEmail('user@example.com')).toBe('user@example.com');
      expect(validateEmail('test.user@example.com')).toBe('test.user@example.com');
      expect(validateEmail('user+tag@example.co.uk')).toBe('user+tag@example.co.uk');
      expect(validateEmail('user_123@example-domain.com')).toBe('user_123@example-domain.com');
    });

    it('should convert to lowercase', () => {
      expect(validateEmail('User@Example.Com')).toBe('user@example.com');
      expect(validateEmail('TEST@EXAMPLE.COM')).toBe('test@example.com');
    });

    it('should trim whitespace', () => {
      expect(validateEmail('  user@example.com  ')).toBe('user@example.com');
      expect(validateEmail('\tuser@example.com\n')).toBe('user@example.com');
    });

    it('should reject null or undefined', () => {
      expect(() => validateEmail(null)).toThrow('Email is required and must be a string');
      expect(() => validateEmail(undefined)).toThrow('Email is required and must be a string');
    });

    it('should reject empty string', () => {
      expect(() => validateEmail('')).toThrow('Email is required and must be a string');
    });

    it('should reject invalid formats', () => {
      expect(() => validateEmail('invalid')).toThrow('Invalid email address format');
      expect(() => validateEmail('invalid@')).toThrow('Invalid email address format');
      expect(() => validateEmail('@example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@example')).toThrow('Invalid email address format'); // No TLD
    });

    it('should reject emails with spaces', () => {
      expect(() => validateEmail('user @example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@ example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@example .com')).toThrow('Invalid email address format');
    });

    it('should reject multiple @ signs', () => {
      expect(() => validateEmail('user@@example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@example@com')).toThrow('Invalid email address format');
    });

    it('should reject XSS-shaped input', () => {
      // Defense-in-depth: script/handler payloads have no valid email shape.
      const xssAttacks = [
        '<script>alert(1)</script>',
        'javascript:alert(1)',
        'onerror=alert(1)',
        '<img src=x onerror=alert(1)>',
      ];
      xssAttacks.forEach((attack) => {
        expect(() => validateEmail(attack)).toThrow();
      });
    });
  });
});
