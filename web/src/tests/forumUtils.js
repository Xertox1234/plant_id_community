/**
 * Test utilities for forum components
 */

/**
 * Create mock category data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock category object
 */
export function createMockCategory(overrides = {}) {
  return {
    id: 'cat-123-uuid',
    name: 'Plant Care',
    slug: 'plant-care',
    description: 'Tips and advice for taking care of your plants',
    icon: '🌱',
    parent: null,
    children: [],
    thread_count: 42,
    post_count: 315,
    display_order: 1,
    is_active: true,
    ...overrides,
  };
}

/**
 * Create mock thread data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock thread object
 */
export function createMockThread(overrides = {}) {
  return {
    id: 'thread-456-uuid',
    title: 'How to water succulents?',
    slug: 'how-to-water-succulents',
    author: {
      id: 1,
      username: 'plantlover',
      display_name: 'Plant Lover',
    },
    category: {
      id: 'cat-123-uuid',
      name: 'Plant Care',
      slug: 'plant-care',
      icon: '🌱',
    },
    excerpt: 'Looking for advice on proper watering techniques for succulents.',
    is_pinned: false,
    is_locked: false,
    is_active: true,
    view_count: 240,
    post_count: 15,
    last_activity_at: '2025-10-30T10:30:00Z',
    created_at: '2025-10-28T14:20:00Z',
    ...overrides,
  };
}

/**
 * Create mock post data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock post object
 */
export function createMockPost(overrides = {}) {
  return {
    id: 'post-789-uuid',
    thread: {
      id: 'thread-456-uuid',
      title: 'How to water succulents?',
      slug: 'how-to-water-succulents',
    },
    author: {
      id: 1,
      username: 'plantlover',
      display_name: 'Plant Lover',
      trust_level: 'basic',
    },
    content_raw: '<p>Water sparingly, about once every 2-3 weeks.</p>',
    content_format: 'rich',
    is_first_post: false,
    is_active: true,
    reaction_counts: {
      like: 5,
      helpful: 3,
      love: 1,
      thanks: 2,
    },
    edited_at: null,
    edited_by: null,
    created_at: '2025-10-28T15:45:00Z',
    ...overrides,
  };
}

/**
 * Create mock reaction data
 * @param {Object} overrides - Override default values
 * @returns {Object} Mock reaction object
 */
export function createMockReaction(overrides = {}) {
  return {
    id: 'reaction-101-uuid',
    post: 'post-789-uuid',
    user: {
      id: 2,
      username: 'gardener',
      display_name: 'Green Gardener',
    },
    reaction_type: 'helpful',
    is_active: true,
    created_at: '2025-10-29T09:12:00Z',
    ...overrides,
  };
}
