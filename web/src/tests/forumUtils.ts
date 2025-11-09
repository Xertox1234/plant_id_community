/**
 * Forum Test Utilities
 *
 * Mock data factories for forum entities used in tests.
 *
 * Note: This file was recreated during TypeScript migration (Issue #134).
 * Previous version was deleted but not converted, causing test failures.
 */

import type { Category, Thread, Post } from '../types/forum';
import type { User } from '../types/auth';

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
 * Create a mock User for testing
 *
 * @param overrides - Partial user data to override defaults
 * @returns Complete User object with defaults
 */
function createMockUser(overrides: Partial<User> = {}): User {
  const defaults: User = {
    id: 1,
    email: 'testuser@example.com',
    username: 'testuser',
    display_name: 'Test User',
    first_name: 'Test',
    last_name: 'User',
    trust_level: 'basic',
    date_joined: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString(), // 30 days ago
    is_active: true,
    is_staff: false,
    is_moderator: false,
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
    author: createMockUser(),
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
    author: {
      ...createMockUser(),
      trust_level: 'basic',
    },
    content_raw: '<p>This is a test post content</p>',
    content_html: '<p>This is a test post content</p>',
    content_format: 'rich',
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    updated_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    edited_at: null,
    edited_by: undefined,
    attachments: [],
    is_edited: false,
    is_first_post: false,
    is_active: true,
    reaction_counts: {},
  };

  return { ...defaults, ...overrides };
}
