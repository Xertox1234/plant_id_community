import { describe, it, expect } from 'vitest';
import { parseLiveEvent } from './forumLiveSocket';

const frame = (obj: unknown) => JSON.stringify(obj);

describe('parseLiveEvent', () => {
  it.each(['post.created', 'post.updated', 'post.removed'] as const)('parses %s', (type) => {
    expect(parseLiveEvent(frame({ v: 1, type, topic_id: 12, post_id: 7 }))).toEqual({
      type,
      topicId: 12,
      postId: '7',
    });
  });

  it.each(['topic.updated', 'topic.removed'] as const)('parses %s', (type) => {
    expect(parseLiveEvent(frame({ v: 1, type, topic_id: 12 }))).toEqual({ type, topicId: 12 });
  });

  it('maps a pong', () => {
    expect(parseLiveEvent(frame({ v: 1, type: 'pong' }))).toBe('pong');
  });

  it('null for v !== 1', () => {
    expect(
      parseLiveEvent(frame({ v: 2, type: 'post.created', topic_id: 1, post_id: 2 }))
    ).toBeNull();
  });

  it('null for an unknown type', () => {
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.reacted', topic_id: 1, post_id: 2 }))
    ).toBeNull();
  });

  it('null for bad JSON', () => {
    expect(parseLiveEvent('{not json')).toBeNull();
  });

  it('null for non-string data (a Blob/ArrayBuffer)', () => {
    expect(parseLiveEvent(new ArrayBuffer(4))).toBeNull();
    expect(parseLiveEvent(new Blob(['x']))).toBeNull();
  });

  it('null for a post event with no integer post_id', () => {
    expect(parseLiveEvent(frame({ v: 1, type: 'post.created', topic_id: 1 }))).toBeNull();
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.created', topic_id: 1, post_id: '2' }))
    ).toBeNull();
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.created', topic_id: 1, post_id: 2.5 }))
    ).toBeNull();
  });

  it('null for a non-integer topic_id', () => {
    expect(parseLiveEvent(frame({ v: 1, type: 'topic.updated', topic_id: '12' }))).toBeNull();
    expect(parseLiveEvent(frame({ v: 1, type: 'topic.updated' }))).toBeNull();
  });

  it('null for a JSON value that is not an object', () => {
    expect(parseLiveEvent('null')).toBeNull();
    expect(parseLiveEvent('[1]')).toBeNull();
  });

  it('ignores extra fields', () => {
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.removed', topic_id: 3, post_id: 4, body: 'x' }))
    ).toEqual({ type: 'post.removed', topicId: 3, postId: '4' });
  });
});
