import { describe, it, expect, vi, beforeEach } from 'vitest';
import { draftKey, loadDraft, saveDraft, clearDraft, clearAllDrafts } from './forumDrafts';

describe('forumDrafts', () => {
  beforeEach(() => sessionStorage.clear());

  it('round-trips a draft', () => {
    const key = draftKey('reply', '28');
    saveDraft(key, '<p>half-written</p>');
    expect(loadDraft(key)).toBe('<p>half-written</p>');
    clearDraft(key);
    expect(loadDraft(key)).toBeNull();
  });

  it('saving an empty value removes the draft', () => {
    const key = draftKey('new-thread', '54');
    saveDraft(key, '<p>x</p>');
    saveDraft(key, '');
    expect(loadDraft(key)).toBeNull();
  });

  it('swallows storage errors', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    expect(() => saveDraft(draftKey('reply', '1'), 'x')).not.toThrow();
    spy.mockRestore();
  });
});

describe('clearAllDrafts (audit 2026-09-04 L4)', () => {
  beforeEach(() => sessionStorage.clear());

  it('removes every forum draft and nothing else', () => {
    saveDraft(draftKey('reply', '28'), '<p>a</p>');
    saveDraft(draftKey('new-thread', '54'), '<p>b</p>');
    sessionStorage.setItem('user', '{"id":1}');

    clearAllDrafts();

    expect(loadDraft(draftKey('reply', '28'))).toBeNull();
    expect(loadDraft(draftKey('new-thread', '54'))).toBeNull();
    expect(sessionStorage.getItem('user')).toBe('{"id":1}');
  });

  it('swallows storage errors', () => {
    const spy = vi.spyOn(Storage.prototype, 'key').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    saveDraft(draftKey('reply', '1'), 'x');
    expect(() => clearAllDrafts()).not.toThrow();
    spy.mockRestore();
  });
});
