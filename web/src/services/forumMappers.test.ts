import { describe, it, expect } from 'vitest';
import {
  mapUser,
  mapForumToCategory,
  mapTopicToThread,
  mapPostToPost,
  mapImageToAttachment,
} from './forumMappers';

describe('forumMappers', () => {
  it('maps a backend user to a forum author with a display name', () => {
    expect(
      mapUser({ id: 1, username: 'jdoe', first_name: 'Jane', last_name: 'Doe' })
    ).toMatchObject({
      id: '1',
      username: 'jdoe',
      display_name: 'Jane Doe',
    });
    expect(mapUser({ id: 2, username: 'nobody', first_name: '', last_name: '' }).display_name).toBe(
      'nobody'
    );
    const deleted = mapUser(null);
    expect(deleted.id).toBe('');
    expect(deleted.username).toBe('[deleted]');
    expect(deleted.display_name).toBe('[deleted]');
  });

  it('maps a forum to a category (renames counts, derives slug)', () => {
    const c = mapForumToCategory({
      id: 3,
      name: 'Plant Care',
      description: 'Tips',
      topics_count: 10,
      posts_count: 42,
      last_activity: '2026-01-02T00:00:00Z',
    });
    expect(c).toMatchObject({
      id: '3',
      name: 'Plant Care',
      slug: 'plant-care',
      thread_count: 10,
      post_count: 42,
    });
  });

  it('maps a topic to a thread (subject->title, last_post_on->last_activity_at)', () => {
    const t = mapTopicToThread({
      id: 12,
      subject: 'Succulent help',
      poster: { id: 1, username: 'jdoe', first_name: 'Jane', last_name: 'Doe' },
      forum: { id: 3, name: 'Plant Care', slug: 'plant-care' },
      created: '2026-01-01T00:00:00Z',
      posts_count: 5,
      last_post_on: '2026-01-02T00:00:00Z',
      replies_count: 4,
      views_count: 99,
    });
    expect(t).toMatchObject({
      id: '12',
      title: 'Succulent help',
      slug: 'succulent-help',
      category: { id: '3', name: 'Plant Care', slug: 'plant-care' },
      last_activity_at: '2026-01-02T00:00:00Z',
      post_count: 5,
      view_count: 99,
    });
    expect(t.author?.display_name).toBe('Jane Doe');
  });

  it('maps a post (content->content_raw, created->created_at)', () => {
    const p = mapPostToPost(
      {
        id: 50,
        content: '<p>hello</p>',
        poster: { id: 1, username: 'jdoe', first_name: '', last_name: '' },
        created: '2026-01-01T00:00:00Z',
        updated: '2026-01-01T00:00:00Z',
        content_format: 'html',
      },
      '12'
    );
    expect(p).toMatchObject({
      id: '50',
      thread: '12',
      content_raw: '<p>hello</p>',
      content_format: 'html',
      reaction_counts: {},
    });
  });

  it('maps an image to an attachment (image_url->image, upload_order->display_order)', () => {
    const a = mapImageToAttachment({
      id: 7,
      image_url: 'http://x/a.jpg',
      thumbnail_url: 'http://x/a_t.jpg',
      large_thumbnail_url: 'http://x/a_l.jpg',
      upload_order: 2,
      alt_text: 'a plant',
      original_filename: 'a.jpg',
      file_size: 1234,
      created_at: '2026-01-01T00:00:00Z',
    });
    expect(a).toMatchObject({
      id: '7',
      image: 'http://x/a.jpg',
      image_url: 'http://x/a.jpg',
      thumbnail_url: 'http://x/a_t.jpg',
      display_order: 2,
      alt_text: 'a plant',
    });
  });
});
