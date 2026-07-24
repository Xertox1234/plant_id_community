/**
 * Forum Test Utilities
 *
 * Mock data factories for forum entities used in tests.
 *
 * Note: This file was recreated during TypeScript migration (Issue #134).
 * Previous version was deleted but not converted, causing test failures.
 */

import type { Category, Thread, Post, ForumAuthor } from '../types/forum';

/**
 * Create a mock Category for testing
 *
 * @param overrides - Partial category data to override defaults
 * @returns Complete Category object with defaults
 */
export function createMockCategory(overrides: Partial<Category> = {}): Category {
  const defaults: Category = {
    id: 'cat-1',
    name: 'Plant Care',
    slug: 'plant-care',
    description: 'Tips for caring for your plants',
    icon: '🌱',
    thread_count: 10,
    post_count: 50,
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString(), // 7 days ago
    children: [],
  };

  return { ...defaults, ...overrides };
}

/**
 * Create a mock ForumAuthor for testing — the unified author object every
 * topic/post payload carries (todo 257 H26).
 *
 * @param overrides - Partial author data to override defaults
 * @returns Complete ForumAuthor object with defaults
 */
export function createMockForumAuthor(overrides: Partial<ForumAuthor> = {}): ForumAuthor {
  const defaults: ForumAuthor = {
    username: 'testuser',
    display_name: 'Test User',
    avatar: null,
    trust_level: 1,
  };

  return { ...defaults, ...overrides };
}

/**
 * Create a mock Thread for testing
 *
 * @param overrides - Partial thread data to override defaults
 * @returns Complete Thread object with defaults
 */
export function createMockThread(overrides: Partial<Thread> = {}): Thread {
  const defaults: Thread = {
    id: 'thread-1',
    title: 'How to water succulents?',
    slug: 'how-to-water-succulents',
    excerpt: 'Looking for advice on watering frequency',
    category: createMockCategory(),
    author: createMockForumAuthor(),
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(), // 3 days ago
    updated_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    last_activity_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    post_count: 5,
    view_count: 150,
    is_pinned: false,
    is_locked: false,
    is_active: true,
  };

  return { ...defaults, ...overrides };
}

/**
 * Create a mock Post for testing
 *
 * @param overrides - Partial post data to override defaults
 * @returns Complete Post object with defaults
 */
export function createMockPost(overrides: Partial<Post> = {}): Post {
  const defaults: Post = {
    id: 'post-1',
    thread: 'thread-1',
    author: createMockForumAuthor({ trust_level: 1 }),
    content_raw: '<p>This is a test post content</p>',
    content_html: '<p>This is a test post content</p>',
    content_format: 'rich',
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    updated_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    edited_at: null,
    edited_by: undefined,
    is_edited: false,
    is_first_post: false,
    is_active: true,
    reaction_counts: {},
  };

  return { ...defaults, ...overrides };
}
