import { describe, it, expect, vi, beforeEach } from 'vitest';
import { draftKey, loadDraft, saveDraft, clearDraft } from './forumDrafts';

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
