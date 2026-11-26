import { describe, expect, it } from 'vitest';
import type { Post } from '@/types';
import { sortsAfter } from './postOrder';

const post = (id: string, created_at: string) => ({ id, created_at }) as Post;

describe('sortsAfter (audit F44)', () => {
  it('orders by created_at first', () => {
    expect(sortsAfter(post('1', '2026-11-26T10:00:01Z'), post('9', '2026-11-26T10:00:00Z'))).toBe(
      true
    );
    expect(sortsAfter(post('9', '2026-11-26T10:00:00Z'), post('1', '2026-11-26T10:00:01Z'))).toBe(
      false
    );
  });

  it('parses times: a string without fractional seconds is not out of order', () => {
    // As text, "10:00:00Z" > "10:00:00.500000Z" ('Z' sorts after '.').
    expect(
      sortsAfter(post('1', '2026-11-26T10:00:00Z'), post('2', '2026-11-26T10:00:00.500000Z'))
    ).toBe(false);
  });

  it('breaks a tie by numeric id, not text', () => {
    const at = '2026-11-26T10:00:00Z';
    expect(sortsAfter(post('10', at), post('9', at))).toBe(true);
    expect(sortsAfter(post('9', at), post('10', at))).toBe(false);
    expect(sortsAfter(post('9', at), post('9', at))).toBe(false);
  });

  it('never appends past an unreadable date', () => {
    expect(sortsAfter(post('2', 'not a date'), post('1', '2026-11-26T10:00:00Z'))).toBe(false);
    expect(sortsAfter(post('2', '2026-11-26T10:00:00Z'), post('1', ''))).toBe(false);
  });
});
