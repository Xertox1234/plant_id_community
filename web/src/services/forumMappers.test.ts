import { describe, it, expect } from 'vitest';
import {
  mapBoardToCategory,
  mapTopicListItemToThread,
  mapTopicDetailToThread,
  mapPostToPost,
  mapSearchTopicToThread,
  mapSearchPostToPost,
} from './forumMappers';

describe('forumMappers (wagtail_forum contract)', () => {
  // -------------------------------------------------------------------------
  // Boards → Category
  // -------------------------------------------------------------------------

  it('mapBoardToCategory maps id, title→name, slug, counts', () => {
    const c = mapBoardToCategory({
      id: 3,
      title: 'Plant Care',
      slug: 'plant-care',
      description: 'Tips',
      topic_count: 10,
      post_count: 42,
    });
    expect(c).toMatchObject({
      id: '3',
      name: 'Plant Care',
      slug: 'plant-care',
      description: 'Tips',
      thread_count: 10,
      post_count: 42,
    });
  });

  it('mapBoardToCategory defaults counts to 0 when absent', () => {
    const c = mapBoardToCategory({ id: 1, title: 'X', slug: 'x' });
    expect(c.thread_count).toBe(0);
    expect(c.post_count).toBe(0);
  });

  // -------------------------------------------------------------------------
  // TopicListItem → Thread
  // -------------------------------------------------------------------------

  it('mapTopicListItemToThread maps core fields', () => {
    const t = mapTopicListItemToThread({
      id: 12,
      title: 'Succulent help',
      slug: 'succulent-help',
      author: 'jdoe',
      is_pinned: false,
      is_closed: false,
      locked: false,
      reply_count: 4,
      view_count: 99,
      last_post_at: '2026-01-02T00:00:00Z',
      last_post_author: 'jdoe',
    });
    expect(t).toMatchObject({
      id: '12',
      title: 'Succulent help',
      slug: 'succulent-help',
      post_count: 4,
      view_count: 99,
      last_activity_at: '2026-01-02T00:00:00Z',
      is_pinned: false,
      is_locked: false,
    });
    expect(t.author?.username).toBe('jdoe');
  });

  it('mapTopicListItemToThread handles null author ([deleted])', () => {
    const t = mapTopicListItemToThread({
      id: 1,
      title: 'T',
      slug: 't',
      author: null,
      is_pinned: false,
      is_closed: false,
      locked: false,
      reply_count: 0,
      view_count: 0,
      last_post_at: null,
      last_post_author: null,
    });
    expect(t.author?.username).toBe('[deleted]');
  });

  it('mapTopicListItemToThread maps is_closed OR locked → is_locked', () => {
    const base = {
      id: 1,
      title: 'T',
      slug: 't',
      author: 'u',
      is_pinned: false,
      is_closed: true,
      locked: false,
      reply_count: 0,
      view_count: 0,
      last_post_at: null,
      last_post_author: null,
    };
    expect(mapTopicListItemToThread(base).is_locked).toBe(true);
    // Wagtail-locked but open: previously invisible in lists (audit 2026-07-11 L3)
    expect(mapTopicListItemToThread({ ...base, is_closed: false, locked: true }).is_locked).toBe(
      true
    );
    expect(mapTopicListItemToThread({ ...base, is_closed: false, locked: false }).is_locked).toBe(
      false
    );
    expect(mapTopicListItemToThread({ ...base, is_pinned: true }).is_pinned).toBe(true);
  });

  // -------------------------------------------------------------------------
  // TopicDetail → Thread
  // -------------------------------------------------------------------------

  it('mapTopicDetailToThread maps board→category and all fields', () => {
    const t = mapTopicDetailToThread({
      id: 12,
      title: 'Succulent help',
      slug: 'succulent-help',
      board: { id: 3, slug: 'plant-care', title: 'Plant Care' },
      author: 'jdoe',
      is_pinned: true,
      is_closed: false,
      locked: false,
      reply_count: 5,
      view_count: 99,
      created_at: '2026-01-01T00:00:00Z',
      last_post_at: '2026-01-02T00:00:00Z',
      last_post_author: 'jdoe',
      opening_post_id: 50,
    });
    expect(t).toMatchObject({
      id: '12',
      title: 'Succulent help',
      slug: 'succulent-help',
      created_at: '2026-01-01T00:00:00Z',
      last_activity_at: '2026-01-02T00:00:00Z',
      post_count: 5,
      view_count: 99,
      is_pinned: true,
      is_locked: false,
    });
    expect(t.category).toMatchObject({ id: '3', slug: 'plant-care', name: 'Plant Care' });
  });

  it('mapTopicDetailToThread treats locked=true as is_locked', () => {
    const t = mapTopicDetailToThread({
      id: 1,
      title: 'T',
      slug: 't',
      board: { id: 1, slug: 'b', title: 'B' },
      author: null,
      is_pinned: false,
      is_closed: false,
      locked: true,
      reply_count: 0,
      view_count: 0,
      created_at: '2026-01-01T00:00:00Z',
      last_post_at: null,
      last_post_author: null,
      opening_post_id: null,
    });
    expect(t.is_locked).toBe(true);
  });

  // -------------------------------------------------------------------------
  // BackendPost → Post
  // -------------------------------------------------------------------------

  it('mapPostToPost maps id, thread, author object, body, reaction_counts', () => {
    const p = mapPostToPost(
      {
        id: 50,
        topic_id: 12,
        author: { username: 'jdoe', display_name: 'Jane Doe', trust_level: 'member' },
        body: [{ type: 'paragraph', value: 'hello', id: 'blk-1' }],
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        edited_at: null,
        is_opening_post: true,
        status: 'live',
        reaction_counts: { like: 3 },
        can_edit: true,
        can_delete: false,
      },
      '12'
    );
    expect(p).toMatchObject({
      id: '50',
      thread: '12',
      is_first_post: true,
      is_active: true,
      reaction_counts: { like: 3 },
      can_edit: true,
      can_delete: false,
    });
    expect(p.author?.username).toBe('jdoe');
    expect(p.author?.display_name).toBe('Jane Doe');
    expect(p.body).toHaveLength(1);
    expect(p.body?.[0].type).toBe('paragraph');
  });

  it('mapPostToPost maps [deleted] author object', () => {
    const p = mapPostToPost(
      {
        id: 51,
        topic_id: 12,
        author: { username: '[deleted]', display_name: '[deleted]', trust_level: null },
        body: [],
        created_at: '2026-01-01T00:00:00Z',
        is_opening_post: false,
        status: 'live',
        reaction_counts: {},
        can_edit: false,
        can_delete: false,
      },
      '12'
    );
    expect(p.author?.username).toBe('[deleted]');
    expect(p.author?.display_name).toBe('[deleted]');
  });

  it('mapPostToPost sets is_active=false for pending posts', () => {
    const p = mapPostToPost(
      {
        id: 52,
        topic_id: 12,
        author: { username: 'u', display_name: 'U', trust_level: null },
        body: [],
        created_at: '2026-01-01T00:00:00Z',
        is_opening_post: false,
        status: 'pending',
        reaction_counts: {},
        can_edit: false,
        can_delete: false,
      },
      '12'
    );
    expect(p.is_active).toBe(false);
  });

  // -------------------------------------------------------------------------
  // Search mappers
  // -------------------------------------------------------------------------

  it('mapSearchTopicToThread maps id, title, slug', () => {
    const t = mapSearchTopicToThread({ id: 7, slug: 'my-topic', title: 'My Topic' });
    expect(t).toMatchObject({ id: '7', title: 'My Topic', slug: 'my-topic' });
  });

  it('mapSearchPostToPost maps id, topic_id→thread, excerpt→content_raw', () => {
    const p = mapSearchPostToPost({
      id: 99,
      topic_id: 7,
      topic_title: 'My Topic',
      excerpt: 'Some excerpt',
    });
    expect(p).toMatchObject({ id: '99', thread: '7', content_raw: 'Some excerpt' });
  });
});
